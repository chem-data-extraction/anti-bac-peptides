# Dataset card — Aptamer–protein binding dataset

## Dataset title

Aptamer–protein binding dataset (course template v0.1.0)

## Dataset summary

Tabular collection of experimentally reported aptamer–protein binding measurements, including sequences, targets, affinity values, assay metadata, and provenance fields. This repository is a **template** with illustrative example rows.

## Scientific task

Support comparison of reported binding affinities (e.g. Kd) and assay conditions across literature and curated database sources for aptamer–protein pairs.

## Record unit

One row = one experimentally reported binding measurement for one aptamer–target pair from one source.

## Data sources

Defined in `specs/source_map.json`: journal PDFs, supplementary tables, aptamer databases, metadata aggregators, GitHub releases, and optional ML dataset exports (with license review).

## Data extraction procedure

1. PDF: `scripts/extract_pdf.py` guided by `specs/pdf_extraction_manifest.json`
2. Web: `scripts/extract_web.py` guided by `specs/web_extraction_manifest.json`
3. Logs: `data/extracted/extraction_log.jsonl`

## Data cleaning and normalization

`scripts/build_dataset.py` merges extracts; `scripts/clean_dataset.py` normalizes sequences, units (to nM), missing values, and deduplicates per `specs/cleaning_pipeline.json`.

## Dataset schema

Field definitions, types, and examples: `specs/dataset_schema.json`. Final columns in `data/processed/dataset.csv`.

## Validation

Rules in `specs/validation_rules.json`; checks via `scripts/validate_project.py` and `tests/test_required_artifacts.py`.

## Known limitations

- Example DOIs and URLs are placeholders.
- Template rows are not verified against live sources.
- Some sources may be paywalled or not redistributable—confirm LICENSE before publication.

## Recommended use

Teaching structured scientific data extraction; prototyping pipelines; benchmarking parsing workflows on aptamer binding tables.

## Not recommended use

Clinical decision-making; uncritical meta-analysis without re-verifying primary sources; commercial use without license review.

## License

See `LICENSE` — replace placeholder before publication (e.g. CC-BY-4.0 or CC0-1.0 subject to upstream data licenses).

## Citation

See `CITATION.cff`. Update authors, version, and repository URL before release.
