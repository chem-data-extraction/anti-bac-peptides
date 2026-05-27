# Extracted outputs

Intermediate CSV extracts from PDF and web (`pdf_extracted_records.csv`, `web_extracted_records.csv`) plus **`extraction_log.jsonl`** (one JSON object per extractor step per source run).

Each new run of `scripts/extract_pdf.py` or `scripts/extract_web.py` **appends** to `extraction_log.jsonl`; truncate or archive the file if you need a fresh-only log tail. The checked-in log retains the final web extraction pass (`"run": "final"`, 1000 DBAASP + 1000 DRAMP records written) plus one PDF extraction pass per paper source.
