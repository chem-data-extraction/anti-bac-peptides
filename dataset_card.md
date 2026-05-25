# Dataset card — Antibacterial peptide MIC dataset

## Dataset title

Antibacterial peptide MIC dataset (v0.5.0)

## Dataset summary

Curated tabular collection of experimentally reported minimum inhibitory concentration (MIC) values for antibacterial peptides against bacterial pathogens. Each row represents one MIC measurement of one peptide against one pathogen from a specific source. The dataset integrates records from two curated databases (DRAMP, DBAASP) and ten peer-reviewed papers published between 2023 and 2026.

Every row retains the **verbatim** MIC (`measurement_value`) and normalized unit label (`measurement_unit`). This release stores **MIC-only** antibacterial measurements; peptide sequence is mandatory on each row after extraction and cleaning.

**1 521 records · 18 fields · 12 sources**

## Scientific task

Support comparison of antibacterial peptide activity across sources, assay conditions, and pathogen species. Enables meta-analysis, ML training, and benchmarking of computational AMP design.

## Record unit

One row = one experimentally reported MIC measurement for one antibacterial peptide against one bacterial pathogen from one source, with assay metadata and provenance.

## Schema (18 fields)

Defined in `specs/dataset_schema.json` (v0.8.0).

**Required fields:** `record_id`, `peptide_sequence`, `pathogen_name`, `measurement_value`, `source_id`.

| Field | Description |
|-------|-------------|
| `record_id` | Unique identifier |
| `peptide_sequence` | **Required.** Amino acid sequence (standard 1-letter codes) |
| `peptide_name` | Name or identifier from source |
| `organism_source` | Biological origin of the peptide |
| `pathogen_name` | Species name of tested bacterium |
| `pathogen_strain` | Strain designation (ATCC, MRSA, etc.) |
| `measurement_value` | **Required.** Verbatim reported MIC value (e.g. `4.0`, `>64`) |
| `measurement_unit` | Canonical unit (`ug/mL`, `uM`, `nM`, `ng/mL`, `mg/L`, `pmol/ml`) |
| `assay_method` | Assay protocol (e.g. `broth microdilution`) |
| `medium` | Growth medium (e.g. `MHB`, `LB`) |
| `inoculum_cfu_ml` | Inoculum size (verbatim, e.g. `5e5`) |
| `temperature_c` | Incubation temperature (°C) |
| `incubation_time_h` | Incubation time (hours) |
| `source_id` | Source identifier from `specs/source_map.json` |
| `source_type` | `scientific_paper` or `database` |
| `publication_year` | Year of publication (integer) |
| `source_url` | URL of source document or record |
| `doi` | DOI of source |

_Removed compared to schema v0.7:_ `synthesis_type`, `gram_stain`, `measurement_type` (implicitly MIC for this corpus), `medium_composition`.

## Data sources

Defined in `specs/source_map.json` (v1.8.1):

| source_id | Type | Records | License |
|-----------|------|---------|---------|
| `db_dramp` | Database | ~999 | CC-BY |
| `db_dbaasp` | Database | ~90 | Free academic use |
| Other paper IDs | Papers | varies | CC-BY or publisher OA terms |

See `specs/source_map.json` for the full inventory of 12 `source_id` values.

## Data extraction procedure

1. PDF: `scripts/extract_pdf.py` guided by `specs/pdf_extraction_manifest.json` — paper-specific pdfplumber parsers
2. Web: `scripts/extract_web.py` guided by `specs/web_extraction_manifest.json` — DBAASP REST API + DRAMP Excel workbook
3. Logs: `data/extracted/extraction_log.jsonl`

## Data cleaning and normalization

`scripts/build_dataset.py` merges all extracts into `data/interim/merged_records.csv`.

`scripts/clean_dataset.py` applies:
- Sequence normalization (uppercase standard amino acids only)
- MIC unit canonicalization (`ug/mL`, `uM`, `nM`, `ng/mL`, `mg/L`, `pmol/ml`)
- `publication_year` cast to integer
- Non-bacterial row removal (fungal, viral, mammalian targets)
- **Rows without `peptide_sequence` after normalization are dropped**
- Content-fingerprint deduplication

`paper_c14r_eskape_2026`: MIC table is paired with peptide sequence CSSGSLWRLIRRFLRR reported in Mildenberger et al. 2024 (Pharmaceuticals 17:83), not reproduced in Antibiotics 2026.

## Validation

Rules in `specs/validation_rules.json`; automated checks via `scripts/validate_project.py` and `pytest`.

Validation checks include:
- Required file presence
- Column alignment with schema
- `record_id` uniqueness and non-null
- **`peptide_sequence` non-null** (required on every finalized row)
- `measurement_value` non-null (verbatim MIC token)
- `source_id` against source map
- Enum validation for `measurement_unit` (canonical set) and `source_type`

## Data quality summary

| Metric | Value |
|--------|-------|
| Non-canonical `measurement_unit` | 7 rows (`AU/μg` from DRAMP) |
| Duplicate rows removed (fingerprint dedup) | ~913 |

## Known limitations

- DRAMP records lack `publication_year` (~72 % of rows have no year).
- 7 DRAMP rows carry `AU/μg` (activity units) which are not concentration-comparable.
- DRAMP pathogen name field occasionally contains inhibition-percentage strings (source data artifact).
- MIC values are verbatim strings (censored bounds `>64` retained); numeric comparison requires parsing.

## Recommended use

- Cross-source comparison of AMP activity and assay conditions
- Training and evaluation of computational AMP design models
- Meta-analysis of spectrum and potency across bacterial pathogens
- Teaching structured scientific data extraction pipelines

## Not recommended use

- Clinical decision-making without re-verification of primary sources
- Commercial use without license review of upstream databases (DRAMP, DBAASP)
- Direct numeric aggregation of `measurement_value` without unit harmonization

## License

CC-BY-4.0. See `LICENSE`. Downstream users must comply with the terms of DRAMP and DBAASP for database-sourced records.

## Citation

See `CITATION.cff`.
