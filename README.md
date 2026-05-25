# Antibacterial peptide MIC dataset

Structured, publication-ready dataset of experimentally reported **minimum inhibitory concentration (MIC)** values for antibacterial peptides against bacterial pathogens. Built as part of the course *Extraction and preparation of chemical information*.

## Scientific task

Collect MIC measurements of antibacterial peptides from peer-reviewed literature and curated databases so that activity profiles can be compared across sources, assay conditions, and pathogen types.

## What is one record?

One **record** = one experimentally reported MIC value of one antibacterial peptide against one bacterial pathogen from a specific source (one row in `data/processed/dataset.csv`).

Each record captures (when available): peptide **sequence** and name, organism origin of the peptide, pathogen species and strain, verbatim MIC value and normalized unit; assay fields (`assay_method`, `medium`, inoculum, temperature, incubation time); provenance (`source_id`, URLs, DOI, publication year).

## Dataset at a glance

| Metric | Value |
|--------|-------|
| Rows | **1 521** |
| Unique sources | 12 (2 databases + 10 papers) |
| Schema fields | **18** (see `specs/dataset_schema.json`) |
| Required columns | `record_id`, **`peptide_sequence`**, `pathogen_name`, `measurement_value`, `source_id` |
| Rows without peptide sequence after cleaning | **0** |
| Dominant unit | `ug/mL` (~59 %), `uM` (~34 %) |
| Publication years covered | 2023–2026 |

## Repository structure

| Path | Role |
|------|------|
| `project.json` | Machine-readable project metadata |
| `specs/` | JSON schemas, source map, manifests, pipeline, validation rules |
| `data/raw/` | Unmodified PDFs, web snapshots, external exports |
| `data/extracted/` | Extraction outputs (CSV + `extraction_log.jsonl`) |
| `data/interim/` | Merged table before final cleaning |
| `data/processed/` | Publication dataset (`dataset.csv`) |
| `scripts/` | Reproducible extract, build, clean, validate |
| `reports/` | Practice and final reports |
| `notebooks/` | Exploratory data analysis |
| `tests/` | Pytest checks for required artifacts |

**Formats:** JSON for specs/manifests; CSV for tabular data; Python for pipelines; Markdown for reports.

## Data sources

Defined in `specs/source_map.json` (version 1.8.2):

| Source | Type | Records |
|--------|------|---------|
| DRAMP (`Antimicrobial.xlsx`; upstream `Antimicrobial_amps.xlsx`) | Database | ~999 |
| DBAASP (REST API) | Database | ~89 |
| Ramata-Stunda et al. 2023 | Paper | 66 |
| deepAMP, Nature Comm 2024 | Paper | 150 |
| AI-designed AMPs, Curr Microbiol 2025 | Paper | 76 |
| D-TN peptides, Life 2025 | Paper | 45 |
| Melittin analogues, Processes 2026 | Paper | 34 |
| SK-peptides, Springer 2025 | Paper | 24 |
| Lee et al. 2023 (cecropins) | Paper | 16 |
| Zhang et al. 2024 | Paper | 10 |
| B7-005 proline-rich, Antibiotics 2025 | Paper | 6 |
| C14R vs ESKAPE, Antibiotics 2026 | Paper | 6 |

## Data pipeline

```text
raw (PDF / web / external)
  → extract (pdf + web scripts) → data/extracted/*.csv
  → build (merge) → data/interim/merged_records.csv
  → clean → data/processed/dataset.csv
  → validate (rules + pytest)
```

## How to build the dataset

```bash
pip install -r requirements.txt
python scripts/extract_pdf.py      # parse PDF papers (requires pdfplumber)
python scripts/extract_web.py      # fetch DBAASP API + DRAMP workbook
python scripts/build_dataset.py    # merge → interim
python scripts/clean_dataset.py    # normalize, deduplicate → processed
```

## How to run validation

```bash
python scripts/validate_project.py
pytest
```

## Measurement values

`measurement_value` is a **required** field: every row must carry the MIC as reported in the source. Values are stored **verbatim** (e.g. `4.0`, `>64`, `≤2`). Units are normalized to canonical labels in `measurement_unit` via `scripts/utils.py` (`ug/mL`, `uM`, `nM`, `ng/mL`, `mg/L`, `pmol/ml`). No automatic µM → µg/mL conversion is performed.

See `specs/dataset_schema.json` for required fields and full field list (`peptide_sequence` is required).

## Known limitations

- DRAMP records do not include `publication_year` (field is blank for ~72 % of rows).
- 7 DRAMP rows use `AU/μg` (activity units), which cannot be converted to concentration units.
- DBAASP extraction requires a live network connection to `dbaasp.org`.
- Some DRAMP pathogen names contain inhibition-percentage prefixes (data quality limitation of the source).

## License and citation

See `LICENSE` (CC-BY-4.0) and `CITATION.cff`.
