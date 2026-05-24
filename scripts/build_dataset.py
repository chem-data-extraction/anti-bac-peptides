#!/usr/bin/env python3
"""Merge extracted CSVs and write interim and processed datasets."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

PDF_CSV = ROOT / "data/extracted/pdf_extracted_records.csv"
WEB_CSV = ROOT / "data/extracted/web_extracted_records.csv"
SCHEMA_PATH = ROOT / "specs/dataset_schema.json"
MERGED_PATH = ROOT / "data/interim/merged_records.csv"
DATASET_PATH = ROOT / "data/processed/dataset.csv"


def load_schema_columns() -> list[str]:
    with SCHEMA_PATH.open(encoding="utf-8") as f:
        schema = json.load(f)
    return [field["name"] for field in schema["fields"]]


def map_pdf_row(row: pd.Series) -> dict:
    notes = str(row.get("extraction_notes", "") or "")
    return {
        "record_id": row["record_id"],
        "aptamer_sequence": row["aptamer_sequence"],
        "target_name": row["target_name"],
        "target_type": row.get("target_type", ""),
        "measurement_type": row["measurement_type"],
        "measurement_value": row.get("measurement_value"),
        "measurement_unit": row.get("measurement_unit", ""),
        "normalized_value_nm": row.get("measurement_value")
        if str(row.get("measurement_unit", "")).lower() in ("nm", "nanomolar")
        else None,
        "assay_method": row.get("assay_method", ""),
        "buffer": "",
        "temperature_c": None,
        "source_id": row["source_id"],
        "source_type": "scientific_paper",
        "source_url": "",
        "doi": "",
        "extraction_method": "pdf_table",
        "extraction_confidence": row.get("extraction_confidence", ""),
        "notes": notes,
    }


def map_web_row(row: pd.Series) -> dict:
    notes = str(row.get("extraction_notes", "") or "")
    unit = str(row.get("measurement_unit", "") or "")
    val = row.get("measurement_value")
    norm = val if unit.lower() in ("nm", "nanomolar") else None
    return {
        "record_id": row["record_id"],
        "aptamer_sequence": row["aptamer_sequence"],
        "target_name": row["target_name"],
        "target_type": row.get("target_type", ""),
        "measurement_type": row["measurement_type"],
        "measurement_value": val,
        "measurement_unit": unit,
        "normalized_value_nm": norm,
        "assay_method": "",
        "buffer": "",
        "temperature_c": None,
        "source_id": row["source_id"],
        "source_type": "database",
        "source_url": row.get("source_url", ""),
        "doi": "",
        "extraction_method": "web_scrape",
        "extraction_confidence": row.get("extraction_confidence", ""),
        "notes": notes,
    }


def build() -> pd.DataFrame:
    pdf_df = pd.read_csv(PDF_CSV)
    web_df = pd.read_csv(WEB_CSV)
    rows = [map_pdf_row(r) for _, r in pdf_df.iterrows()]
    rows += [map_web_row(r) for _, r in web_df.iterrows()]
    columns = load_schema_columns()
    return pd.DataFrame(rows, columns=columns)


def main() -> None:
    MERGED_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATASET_PATH.parent.mkdir(parents=True, exist_ok=True)

    df = build()
    df.to_csv(MERGED_PATH, index=False)
    df.to_csv(DATASET_PATH, index=False)

    print(f"Wrote {len(df)} rows to {MERGED_PATH.relative_to(ROOT)}")
    print(f"Wrote {len(df)} rows to {DATASET_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
