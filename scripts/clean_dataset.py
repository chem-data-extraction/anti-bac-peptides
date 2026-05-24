#!/usr/bin/env python3
"""Clean and normalize merged or extracted records into the final dataset."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

MERGED_PATH = ROOT / "data/interim/merged_records.csv"
PDF_CSV = ROOT / "data/extracted/pdf_extracted_records.csv"
WEB_CSV = ROOT / "data/extracted/web_extracted_records.csv"
SCHEMA_PATH = ROOT / "specs/dataset_schema.json"
DATASET_PATH = ROOT / "data/processed/dataset.csv"

MISSING_TOKENS = {"", "na", "n/a", "none", "null", "-", "nan"}


def normalize_sequence(seq: object) -> str:
    if pd.isna(seq):
        return ""
    text = str(seq).upper().strip()
    return "".join(c for c in text if c in "ACGTU")


def normalize_missing_values(value: object):
    if pd.isna(value):
        return None
    text = str(value).strip().lower()
    if text in MISSING_TOKENS:
        return None
    return value


def normalize_measurement_to_nm(value: object, unit: object):
    if pd.isna(value) or value == "" or value is None:
        return None
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(unit):
        return None
    u = str(unit).strip().lower()
    factors = {
        "nm": 1.0,
        "nanomolar": 1.0,
        "pm": 0.001,
        "picomolar": 0.001,
        "μm": 1000.0,
        "um": 1000.0,
        "micromolar": 1000.0,
        "µm": 1000.0,
        "m": 1e9,
        "molar": 1e9,
    }
    factor = factors.get(u)
    if factor is None:
        return None
    return num * factor


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "aptamer_sequence" in out.columns:
        out["aptamer_sequence"] = out["aptamer_sequence"].map(normalize_sequence)
    for col in out.columns:
        if col in ("record_id", "aptamer_sequence"):
            continue
        out[col] = out[col].map(normalize_missing_values)
    if "measurement_value" in out.columns and "measurement_unit" in out.columns:
        out["normalized_value_nm"] = [
            normalize_measurement_to_nm(v, u)
            for v, u in zip(out["measurement_value"], out["measurement_unit"])
        ]
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
    import importlib.util

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
