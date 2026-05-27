from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from utils import load_schema_field_names

PDF_CSV = ROOT / "data/extracted/pdf_extracted_records.csv"
WEB_CSV = ROOT / "data/extracted/web_extracted_records.csv"
MERGED_PATH = ROOT / "data/interim/merged_records.csv"


def load_extract_csv(path: Path, columns: list[str]) -> pd.DataFrame:
    if not path.is_file():
        raise FileNotFoundError(f"Missing extraction file: {path.relative_to(ROOT)}")
    df = pd.read_csv(path, dtype={"inoculum_cfu_ml": "string"})
    for col in columns:
        if col not in df.columns:
            df[col] = None
    return df[columns]


def build() -> pd.DataFrame:
    columns = load_schema_field_names()
    pdf_df = load_extract_csv(PDF_CSV, columns)
    web_df = load_extract_csv(WEB_CSV, columns)
    return pd.concat([pdf_df, web_df], ignore_index=True)


def main() -> None:
    MERGED_PATH.parent.mkdir(parents=True, exist_ok=True)

    df = build()
    df.to_csv(MERGED_PATH, index=False)

    print(f"Wrote {len(df)} rows to {MERGED_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
