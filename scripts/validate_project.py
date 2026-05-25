#!/usr/bin/env python3
"""Validate repository artifacts against specs/validation_rules.json."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pandas as pd

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from utils import NONBACTERIAL_PATHOGEN_SUBSTRINGS

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = [
    "project.json",
    "specs/dataset_schema.json",
    "specs/source_map.json",
    "specs/pdf_extraction_manifest.json",
    "specs/web_extraction_manifest.json",
    "specs/cleaning_pipeline.json",
    "specs/validation_rules.json",
    "data/extracted/pdf_extracted_records.csv",
    "data/extracted/web_extracted_records.csv",
    "data/processed/dataset.csv",
    "scripts/build_dataset.py",
    "scripts/clean_dataset.py",
    "scripts/utils.py",
]

def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def schema_field_names(schema: dict) -> list[str]:
    return [field["name"] for field in schema["fields"]]


def source_ids_from_map(source_map: dict) -> set[str]:
    ids: set[str] = set()
    for group_sources in source_map.get("source_groups", {}).values():
        for entry in group_sources:
            sid = entry.get("source_id")
            if sid:
                ids.add(sid)
    return ids


def check_required_files(root: Path = ROOT) -> list[str]:
    issues = []
    for rel in REQUIRED_FILES:
        if not (root / rel).is_file():
            issues.append(f"Missing required file: {rel}")
    return issues


def check_json_parseable(root: Path = ROOT) -> list[str]:
    issues = []
    for path in root.rglob("*.json"):
        if ".pytest_cache" in path.parts or "venv" in path.parts:
            continue
        try:
            load_json(path)
        except json.JSONDecodeError as exc:
            issues.append(f"Invalid JSON: {path.relative_to(root)} ({exc})")
    return issues


def load_dataset(root: Path = ROOT) -> pd.DataFrame:
    path = root / "data/processed/dataset.csv"
    return pd.read_csv(path, dtype={"inoculum_cfu_ml": "string"})


def check_dataset_columns(df: pd.DataFrame, schema: dict) -> list[str]:
    expected = schema_field_names(schema)
    actual = list(df.columns)
    issues = []
    if actual != expected:
        issues.append(
            f"Dataset columns do not match schema. Expected {expected}, got {actual}"
        )
    return issues


def check_record_id(df: pd.DataFrame) -> list[str]:
    issues = []
    if df["record_id"].isna().any() or (df["record_id"].astype(str).str.strip() == "").any():
        issues.append("record_id contains null or empty values")
    if df["record_id"].duplicated().any():
        dupes = df.loc[df["record_id"].duplicated(), "record_id"].tolist()
        issues.append(f"Duplicate record_id values: {dupes}")
    return issues


def check_source_id(df: pd.DataFrame, source_map: dict) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    valid_ids = source_ids_from_map(source_map)

    if df["source_id"].isna().any() or (df["source_id"].astype(str).str.strip() == "").any():
        errors.append("source_id contains null or empty values")

    unknown = set(df["source_id"].dropna().astype(str)) - valid_ids
    if unknown:
        warnings.append(f"source_id not in source map (warning): {sorted(unknown)}")
    return errors, warnings


def check_measurement_value(df: pd.DataFrame) -> list[str]:
    """measurement_value is required verbatim MIC text (digits, censored bounds, ranges)."""
    issues = []
    col = df["measurement_value"]
    empty = col.isna() | (col.astype(str).str.strip() == "") | (col.astype(str).str.lower() == "nan")
    if empty.any():
        issues.append(f"measurement_value contains null or empty values ({int(empty.sum())} rows)")
    for idx, val in col.items():
        if empty.loc[idx]:
            continue
        if isinstance(val, (bool, int, float, str)):
            continue
        issues.append(f"measurement_value has unsupported type at row {idx}: {type(val).__name__}")
    return issues


CANONICAL_MEASUREMENT_UNITS: frozenset[str] = frozenset(
    {"ug/mL", "mg/L", "uM", "nM", "ng/mL", "pmol/ml"}
)


def check_peptide_sequence(df: pd.DataFrame) -> list[str]:
    issues: list[str] = []
    if "peptide_sequence" not in df.columns:
        issues.append("peptide_sequence column is missing")
        return issues
    col = df["peptide_sequence"]
    empty = col.isna() | (col.astype(str).str.strip() == "") | (col.astype(str).str.lower() == "nan")
    if empty.any():
        issues.append(
            f"peptide_sequence contains null or empty values ({int(empty.sum())} rows)"
        )
    return issues


SUSPICIOUS_PATHOGEN_RE = re.compile(
    r"^(\d|##|L\d+\s|L-\d+\s)", re.IGNORECASE
)


def check_measurement_unit_enum(df: pd.DataFrame) -> list[str]:
    warnings: list[str] = []
    if "measurement_unit" not in df.columns:
        return warnings
    non_canon = (
        df["measurement_unit"]
        .dropna()
        .loc[lambda s: ~s.isin(CANONICAL_MEASUREMENT_UNITS)]
    )
    if not non_canon.empty:
        counts = non_canon.value_counts().to_dict()
        warnings.append(
            f"Non-canonical measurement_unit values ({len(non_canon)} rows): {counts}"
        )
    return warnings


def check_suspicious_pathogen_names(df: pd.DataFrame) -> list[str]:
    warnings: list[str] = []
    if "pathogen_name" not in df.columns:
        return warnings
    examples: list[str] = []
    for idx, val in df["pathogen_name"].items():
        if pd.isna(val) or not str(val).strip():
            continue
        text = str(val).strip()
        if SUSPICIOUS_PATHOGEN_RE.search(text) or "##" in text:
            label = df.loc[idx, "record_id"] if "record_id" in df.columns else str(idx)
            examples.append(f"{label}: '{text}'")
    if examples:
        cap = examples[:20]
        more = len(examples) - len(cap)
        msg = "; ".join(cap)
        if more > 0:
            msg += f" …(+{more} more)"
        warnings.append(f"Suspicious pathogen_name patterns (digit/##/lab-code prefix): {msg}")
    return warnings


def check_suspected_nonbacterial_pathogens(df: pd.DataFrame) -> list[str]:
    warnings: list[str] = []
    if "pathogen_name" not in df.columns:
        return warnings
    examples: list[str] = []
    for idx, raw in df["pathogen_name"].items():
        if pd.isna(raw):
            continue
        text = str(raw).lower().strip()
        if not text:
            continue
        for hint in NONBACTERIAL_PATHOGEN_SUBSTRINGS:
            h = hint.strip()
            if h and h in text:
                label = df.loc[idx, "record_id"] if "record_id" in df.columns else str(idx)
                examples.append(f"{label}: pathogen_name contains '{h.strip()}'")
                break
    if examples:
        cap = examples[:40]
        more = len(examples) - len(cap)
        msg = "; ".join(cap)
        if more > 0:
            msg += f" …(+{more} more)"
        warnings.append(f"suspected non-bacterial targets in pathogen_name: {msg}")
    return warnings


def validate(root: Path = ROOT) -> tuple[list[str], list[str]]:
    """Return (errors, warnings)."""
    errors: list[str] = []
    warnings: list[str] = []

    errors.extend(check_required_files(root))
    errors.extend(check_json_parseable(root))

    dataset_path = root / "data/processed/dataset.csv"
    if not dataset_path.is_file():
        return errors, warnings

    schema = load_json(root / "specs/dataset_schema.json")
    source_map = load_json(root / "specs/source_map.json")
    df = load_dataset(root)

    errors.extend(check_dataset_columns(df, schema))
    errors.extend(check_record_id(df))
    errors.extend(check_peptide_sequence(df))
    errors.extend(check_measurement_value(df))

    src_errors, src_warnings = check_source_id(df, source_map)
    errors.extend(src_errors)
    warnings.extend(src_warnings)

    warnings.extend(check_suspected_nonbacterial_pathogens(df))
    warnings.extend(check_measurement_unit_enum(df))
    warnings.extend(check_suspicious_pathogen_names(df))

    return errors, warnings


def main() -> int:
    errors, warnings = validate()
    for w in warnings:
        print(f"WARNING: {w}")
    for e in errors:
        print(f"ERROR: {e}")
    if errors:
        print(f"\nValidation failed with {len(errors)} error(s).")
        return 1
    print("Validation passed.")
    if warnings:
        print(f"({len(warnings)} warning(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
