#!/usr/bin/env python3
"""
Placeholder web extraction driver.

Real implementation: use requests + BeautifulSoup (or Playwright for JS pages)
following parser_plan in specs/web_extraction_manifest.json.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "specs/web_extraction_manifest.json"
LOG_PATH = ROOT / "data/extracted/extraction_log.jsonl"


def append_log(entry: dict) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def write_placeholder_snapshot(page: dict) -> Path:
    snap_path = ROOT / page["raw_snapshot_path"]
    snap_path.parent.mkdir(parents=True, exist_ok=True)
    html = (
        f"<!-- placeholder snapshot for {page['page_id']} -->\n"
        f"<html><body><p>Replace with downloaded content from {page['url']}</p></body></html>\n"
    )
    snap_path.write_text(html, encoding="utf-8")
    return snap_path


def main() -> None:
    with MANIFEST.open(encoding="utf-8") as f:
        manifest = json.load(f)

    print(f"Web extraction v{manifest.get('web_extraction_version')}")
    print(f"Script: {manifest.get('script')}")
    print(f"Output: {manifest.get('output_records_file')}")
    print("\nPages to process:")

    for page in manifest.get("input_pages", []):
        print(
            f"  - {page['page_id']}: {page['url']} "
            f"(source_id={page['source_id']}, status={page.get('extraction_status')})"
        )
        snap = write_placeholder_snapshot(page)
        print(f"    Wrote placeholder snapshot: {snap.relative_to(ROOT)}")
        # Example integration:
        # import requests
        # from bs4 import BeautifulSoup
        # resp = requests.get(page["url"], timeout=30)
        # soup = BeautifulSoup(resp.text, "html.parser")
        # rows = soup.select(page["parser_plan"]["selectors"]["row"])

    append_log(
        {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "step": "web_extraction",
            "source_id": "manifest_placeholder",
            "status": "template",
            "tool": "extract_web.py",
            "output": str(manifest.get("output_records_file")),
            "issue": "Placeholder HTML only; add requests/BeautifulSoup parser",
        }
    )
    print(f"\nAppended placeholder event to {LOG_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
