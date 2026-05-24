# Practice 5 — Cleaning, normalization and publication

> Follow `specs/cleaning_pipeline.json`. Run `scripts/clean_dataset.py` and `scripts/validate_project.py`.

## Input files

- `data/extracted/pdf_extracted_records.csv`
- `data/extracted/web_extracted_records.csv`
- (optional) `data/interim/merged_records.csv`

Web sources in the final dataset: **`db_dbaasp`** and **`db_dramp`** only (`db_campr4` was evaluated but excluded — 12-row yield vs ~1000 expected).

## Cleaning steps

Walk through each step in `specs/cleaning_pipeline.json`:

1. **merge_sources** — concatenate PDF and web extract CSVs (`scripts/build_dataset.py` → `data/interim/merged_records.csv`).
2. **drop_non_bacterial_pathogens** — remove rows whose `pathogen_name` matches yeast/fungal/virus/mammalian hints (`scripts/utils.py`).
3. **canonical_measurement_units** — canonicalize `measurement_unit` labels; preserve `measurement_value` as verbatim MIC text.
4. **standardize_sequences** — uppercase `peptide_sequence`, strip whitespace and non-standard amino acids.
5. **standardize_missing_values** — map `NA`, `N/A`, `-`, empty strings to null-like values (except verbatim MIC tokens).
6. **deduplicate_records** — drop rows identical across all schema fields except `record_id`, then dedupe by `record_id`.
7. **export_final_dataset** — write schema-aligned columns to `data/processed/dataset.csv`.
8. **validate_schema** — run `scripts/validate_project.py`.

## Normalization rules

- **MIC values:** stored verbatim in `measurement_value` (including `>128`, ranges, censored bounds). No numeric conversion and **no unit conversion to nM**.
- **MIC units:** canonical labels via `scripts/utils.py` — e.g. `ug/mL`, `uM`, `ng/mL`. Source papers and databases may report µg/mL or µM; both are retained with their declared unit.
- **Sequences:** uppercase; spaces and hyphens removed; non-standard amino acid characters filtered.
- **Inoculum:** `inoculum_cfu_ml` kept as reported string (e.g. `5e5`, `2e5`) per schema — not converted to float.
- **Missing values:** tokens `{empty, na, n/a, none, null, -, nan}` → null.

## Deduplication strategy

Primary fingerprint: all schema columns except `record_id` (peptide + pathogen + assay conditions + MIC + source metadata). Secondary pass: unique `record_id`.

## Validation results

```
$ python scripts/validate_project.py
Validation passed.

$ pytest tests/test_required_artifacts.py
(all tests passed)
```

No schema errors or duplicate `record_id` violations after the latest rebuild.

## Final dataset description

| Metric | Value |
|--------|-------|
| Row count | ~1816 (after CAMPR4 removal and cleaning) |
| Path | `data/processed/dataset.csv` |
| Built | 2026-05-24 |
| PDF sources | 5 (`paper_*` in source map) |
| Web sources | 2 (`db_dbaasp`, `db_dramp`) |
| Top contributors | DRAMP (~1000), Hu FMICB paper (~600), DBAASP (~90), Ramata-Stunda (~66) |

## Publication readiness checklist

- [x] `dataset.csv` matches `specs/dataset_schema.json`
- [x] All `source_id` values documented in source map
- [ ] LICENSE replaced (not placeholder)
- [ ] `CITATION.cff` completed
- [ ] `dataset_card.md` updated
- [ ] `reports/final_report.md` complete
- [x] `reports/practice_05_cleaning_publication.md` complete
