# Processed data

This folder holds the **publication-ready** dataset: one row per record, columns aligned with `specs/dataset_schema.json`.

## Main file

- `dataset.csv` — final dataset produced by `scripts/build_dataset.py` and `scripts/clean_dataset.py`, validated with `scripts/validate_project.py`

## Guidelines

- Regenerate this file from scripts; do not hand-edit.
- Dataset version **0.5.0** (commit `bfdfee3`) is recorded in `reports/final_report.md` and `dataset_card.md`.
