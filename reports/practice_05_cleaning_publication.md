# Practice 5 — Cleaning, normalization and publication

> Follow `specs/cleaning_pipeline.json`. Run `scripts/clean_dataset.py` and `scripts/validate_project.py`.

## Input files

- `data/extracted/pdf_extracted_records.csv`
- `data/extracted/web_extracted_records.csv`
- (optional) `data/interim/merged_records.csv`

Web sources in the final dataset: **`db_dbaasp`** and **`db_dramp`** only.

## Cleaning steps

Walk through each step in `specs/cleaning_pipeline.json`:

1. **merge_sources** — concatenate PDF and web CSVs (`scripts/build_dataset.py` → `data/interim/merged_records.csv`).
2. **drop_non_bacterial_pathogens** — remove yeast/fungal/virus/mammalian rows (`scripts/utils.py`).
3. **canonical_measurement_units** — canonicalize `measurement_unit`; keep required `measurement_value` verbatim.
4. **standardize_sequences** — uppercase `peptide_sequence`, strip invalid characters.
5. **standardize_missing_values** — map `NA`, `N/A`, `-`, empty strings to null for nullable string columns.
6. **require_peptide_sequence** — drop rows with empty `peptide_sequence` after normalization (required field).
7. **deduplicate_records** — drop rows identical across schema content fields, then dedupe by `record_id`.
8. **export_final_dataset** — write `data/processed/dataset.csv` (`scripts/clean_dataset.py`).
9. **validate_schema** — run `scripts/validate_project.py`.

## Normalization rules

- **MIC values:** required field `measurement_value`; stored verbatim (`>128`, ranges, censored bounds). No unit conversion. Rows with empty MIC are dropped before export.
- **MIC units:** canonical labels via `scripts/utils.py` (`ug/mL`, `uM`, `ng/mL`, `mg/L`, `pmol/ml`).
- **Sequences:** uppercase; spaces and hyphens removed; required non-empty peptide sequence after this step or row is discarded.
- **Inoculum:** kept as string (e.g. `5e5`), not converted to float.
- **Missing values:** `{empty, na, n/a, none, null, -, nan}` → null.

## Deduplication strategy

Primary key: all schema columns except `record_id`. Secondary pass: unique `record_id`.

## Validation results

```
$ python scripts/validate_project.py
Validation passed. (2 warnings)

$ pytest tests/test_required_artifacts.py
(all tests passed)
```

Warnings: 7 rows with non-canonical unit `AU/μg` (DRAMP); suspicious pathogen names in some DRAMP rows.

## Final dataset description

| Metric | Value |
|--------|-------|
| Row count | 1521 |
| Path | `data/processed/dataset.csv` |
| Built | 2026-05-25 |
| PDF sources | 10 (`paper_*` in source map) |
| Web sources | 2 (`db_dbaasp`, `db_dramp`) |
| Top contributors | DRAMP (~999), deepAMP paper (~150), DBAASP (~90) |

## Publication readiness checklist

- [x] `dataset.csv` matches `specs/dataset_schema.json`
- [x] All `source_id` values documented in source map
- [x] LICENSE replaced (CC BY 4.0)
- [x] `CITATION.cff` completed
- [x] `dataset_card.md` updated
- [x] `reports/final_report.md` complete
- [x] `reports/practice_05_cleaning_publication.md` complete
