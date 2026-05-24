from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pandas as pd

from utils import canonical_measurement_unit, pathogen_contains_nonbacterial_hint

ROOT = Path(__file__).resolve().parents[1]

MERGED_PATH = ROOT / "data/interim/merged_records.csv"
SCHEMA_PATH = ROOT / "specs/dataset_schema.json"
DATASET_PATH = ROOT / "data/processed/dataset.csv"

MISSING_TOKENS = {"", "na", "n/a", "none", "null", "-", "nan"}
STANDARD_AA = set("ACDEFGHIKLMNPQRSTVWYX")
SYNTHESIS_TYPE_MAP = {
    "non-ribosomal": "nonribosomal",
    "non ribosomal": "nonribosomal",
}


def normalize_sequence(seq: object) -> str:
    if pd.isna(seq):
        return ""
    text = str(seq).upper().strip().replace(" ", "").replace("-", "")
    return "".join(c for c in text if c in STANDARD_AA)


def normalize_missing_values(value: object):
    if pd.isna(value):
        return None
    text = str(value).strip()
    if text.lower() in MISSING_TOKENS:
        return None
    return text


def parse_numeric_measurement(value: object) -> float | None:
    """Parse a lone numeric MIC; used for auxiliary numeric fields only."""
    if pd.isna(value) or value is None:
        return None
    text = str(value).strip()
    if not text or text.startswith(">") or text.startswith("<"):
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def normalize_verbatim_mic(value: object) -> str | None:
    """Keep MIC as reported (digits, censored bounds, ranges); blank only for placeholders."""
    if pd.isna(value) or value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in MISSING_TOKENS:
        return None
    return text


def normalize_synthesis_type(value: object) -> str | None:
    if pd.isna(value):
        return None
    text = str(value).strip()
    if not text:
        return None
    mapped = SYNTHESIS_TYPE_MAP.get(text.lower(), text.lower())
    allowed = {"ribosomal", "nonribosomal", "synthetic", "unknown"}
    return mapped if mapped in allowed else text


def normalize_gram_stain(value: object) -> str | None:
    if pd.isna(value):
        return None
    text = str(value).strip()
    if not text:
        return None
    lowered = text.lower()
    if lowered in ("gram-positive", "gram positive", "gram+"):
        return "Gram-positive"
    if lowered in ("gram-negative", "gram negative", "gram-"):
        return "Gram-negative"
    if lowered == "unknown":
        return "unknown"
    return text


def normalize_measurement_unit(value: object) -> str | None:
    if pd.isna(value) or value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in MISSING_TOKENS:
        return None
    canon = canonical_measurement_unit(text)
    out = str(canon).strip()
    return out if out else None


def normalize_integer(value: object) -> int | None:
    if pd.isna(value) or value is None or str(value).strip() == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def normalize_float(value: object) -> float | None:
    if pd.isna(value) or value is None or str(value).strip() == "":
        return None
    return parse_numeric_measurement(value)


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    if "pathogen_name" in out.columns:
        before_nb = len(out)
        fungal_mask = out["pathogen_name"].map(pathogen_contains_nonbacterial_hint)
        out = out.loc[~fungal_mask].copy()
        dropped_nb = before_nb - len(out)
        if dropped_nb:
            print(
                f"Dropped {dropped_nb} row(s) with yeast/fungi/virus/mammalian pathogen hints in pathogen_name."
            )

    if "peptide_sequence" in out.columns:
        out["peptide_sequence"] = out["peptide_sequence"].map(normalize_sequence)

    if "synthesis_type" in out.columns:
        out["synthesis_type"] = out["synthesis_type"].map(normalize_synthesis_type)

    if "gram_stain" in out.columns:
        out["gram_stain"] = out["gram_stain"].map(normalize_gram_stain)

    for col in ("temperature_c", "incubation_time_h"):
        if col in out.columns:
            out[col] = out[col].map(normalize_float)

    if "publication_year" in out.columns:
        out["publication_year"] = out["publication_year"].map(normalize_integer)

    if "measurement_value" in out.columns:
        out["measurement_value"] = out["measurement_value"].map(normalize_verbatim_mic)

    if "measurement_unit" in out.columns:
        out["measurement_unit"] = out["measurement_unit"].map(normalize_measurement_unit)

    for col in out.columns:
        if col in (
            "record_id",
            "peptide_sequence",
            "measurement_value",
            "measurement_unit",
            "temperature_c",
            "incubation_time_h",
            "publication_year",
            "synthesis_type",
            "gram_stain",
        ):
            continue
        out[col] = out[col].map(normalize_missing_values)

    if "measurement_type" in out.columns:
        out["measurement_type"] = out["measurement_type"].fillna("MIC").replace("", "MIC")

    schema_cols = load_schema_columns()
    content_cols = [c for c in schema_cols if c != "record_id" and c in out.columns]
    if content_cols:
        before = len(out)
        out = out.drop_duplicates(subset=content_cols, keep="first")
        if len(out) < before:
            print(f"Dropped {before - len(out)} duplicate row(s) by assay + peptide + pathogen + MIC fingerprint.")

    if "record_id" in out.columns:
        out = out.drop_duplicates(subset=["record_id"], keep="first")

    return out


def load_schema_columns() -> list[str]:
    with SCHEMA_PATH.open(encoding="utf-8") as f:
        schema = json.load(f)
    return [field["name"] for field in schema["fields"]]


def load_input_frame() -> pd.DataFrame:
    if MERGED_PATH.is_file():
        return pd.read_csv(MERGED_PATH)
    build_path = ROOT / "scripts" / "build_dataset.py"
    spec = importlib.util.spec_from_file_location("build_dataset", build_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {build_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build()


def main() -> None:
    df = load_input_frame()
    columns = load_schema_columns()
    for col in columns:
        if col not in df.columns:
            df[col] = None
    df = df[columns]
    cleaned = clean_dataframe(df)
    DATASET_PATH.parent.mkdir(parents=True, exist_ok=True)
    cleaned.to_csv(DATASET_PATH, index=False)
    print(f"Wrote {len(cleaned)} cleaned rows to {DATASET_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
