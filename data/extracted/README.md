# Extracted outputs

Intermediate CSV extracts from PDF and web (`pdf_extracted_records.csv`, `web_extracted_records.csv`) plus the append-only **`extraction_log.jsonl`** (one JSON object per extractor step per source run).

Each new run of `scripts/extract_pdf.py` or `scripts/extract_web.py` **appends** to `extraction_log.jsonl`; truncate or archive the file if you need a fresh-only log tail.
