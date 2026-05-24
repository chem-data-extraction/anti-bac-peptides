#!/usr/bin/env python3
"""
Placeholder PDF extraction driver.

Real implementation: install PyMuPDF (fitz), pdfplumber, or Camelot and parse
tables from paths listed in specs/pdf_extraction_manifest.json.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "specs/pdf_extraction_manifest.json"
LOG_PATH = ROOT / "data/extracted/extraction_log.jsonl"


def append_log(entry: dict) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def main() -> None:
    with MANIFEST.open(encoding="utf-8") as f:
        manifest = json.load(f)

    print(manifest.get("pdf_extraction_process", "PDF extraction"))
    print(f"Output: {manifest.get('output_records_file')}")
    print("\nPDFs to process:")

    for src in manifest.get("input_sources", []):
        print(
            f"  - {src['pdf_id']}: {src['pdf_path']} "
            f"(source_id={src['source_id']}, status={src.get('extraction_status')})"
        )
        # Example integration points:
        # import pdfplumber
        # with pdfplumber.open(ROOT / src["pdf_path"]) as pdf:
        #     table = pdf.pages[src["pages_used"][0] - 1].extract_table()

    append_log(
        {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "step": "pdf_extraction",
            "source_id": "manifest_placeholder",
            "status": "template",
            "tool": "extract_pdf.py",
            "output": str(manifest.get("output_records_file")),
            "issue": "No PDF library invoked; add pdfplumber/PyMuPDF/Camelot",
        }
    )
    print(f"\nAppended placeholder event to {LOG_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
