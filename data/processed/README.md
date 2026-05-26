# Processed data

This folder holds the **publication-ready** dataset: one row per record, columns aligned with `specs/dataset_schema.json`.

## Main file

- `dataset.csv` — written by **`scripts/clean_dataset.py`** (after `scripts/build_dataset.py` produces `data/interim/merged_records.csv`), validated with `scripts/validate_project.py`.

## Guidelines

- Regenerate this file from scripts; do not hand-edit.
- Dataset version **0.5.0** is recorded in `project.json`; refresh counts in `README.md` / `dataset_card.md` when you regenerate `dataset.csv`.
