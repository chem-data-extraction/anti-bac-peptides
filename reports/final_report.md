# Final report — Antibacterial peptide MIC dataset

**Version:** 0.5.0  
**Documentation tip:** regenerate `data/processed/dataset.csv` via the scripted pipeline rather than pinning narrative to a historic commit.  
**Date:** 2026-05-25  
**Status:** Complete

---

## Project summary

This project built a structured, reproducible dataset of experimentally reported **minimum inhibitory concentration (MIC)** values for antibacterial peptides against bacterial pathogens. The dataset integrates records from two curated databases (DRAMP, DBAASP) and ten open-access peer-reviewed papers published between 2023 and 2026.

**Final dataset:** `data/processed/dataset.csv` — **2 406 rows × 18 columns** (counts after merge, cleaning, deduplication; see pipeline scripts).

---

## Dataset goal

**Scientific question:** What MIC values have been experimentally reported for antibacterial peptides, and how do they vary across peptide types, pathogen species, assay conditions, and literature sources?

**Intended audience:** Computational chemists and bioinformaticians developing AMP design models; researchers performing meta-analyses of antimicrobial activity; students learning structured scientific data extraction.

---

## Source summary

| Source group | Source ID | Type | Records |
|-------------|-----------|------|---------|
| Database | `db_dramp` | DRAMP bulk `Antimicrobial.xlsx` | 999 |
| Database | `db_dbaasp` | DBAASP REST API | 974 |
| Paper | `paper_deepamp_nature_2024` | Nature Comm 2024 | 150 |
| Paper | `paper_ai_amp_curr_microbiol_2025` | Curr Microbiol 2025 | 76 |
| Paper | `paper_ramata_stunda_2023` | Antibiotics 2023 | 66 |
| Paper | `paper_life_tn_peptides_2025` | Life 2025 | 45 |
| Paper | `paper_melittin_processes_mdpi` | Processes 2026 | 34 |
| Paper | `paper_sk_peptides_springer_2025` | Springer 2025 | 24 |
| Paper | `paper_lee_2023` | Pharmaceutics 2023 | 16 |
| Paper | `paper_zhang_2024` | Spectrum 2024 | 10 |
| Paper | `paper_b7_proline_rich_2025` | Antibiotics 2025 | 6 |
| Paper | `paper_c14r_eskape_2026` | Antibiotics 2026 | 6 |

**Total:** 12 sources, **2 406** records after merge, cleaning filters, and deduplication (`data/processed/dataset.csv`).

All paper PDFs are open-access (CC-BY). DRAMP and DBAASP are free for academic use.

---

## Extraction summary

### PDF extraction (`scripts/extract_pdf.py`, Practice 3)

- **Tool:** pdfplumber (text extraction + regex parsing)
- **Sources:** 10 papers; 434 records extracted before deduplication
- **Method:** paper-specific text parsers registered in `TEXT_PARSERS`; assay conditions pulled from `specs/pdf_extraction_manifest.json`
- **Key challenges:**
  - Table layouts vary significantly across journals; each paper required a bespoke parser
  - deepAMP (Nature Comm 2024) provides MIC data in large supplementary tables; 150 records extracted
  - Hu et al. 2022 paper was **excluded** because all 600 of its rows lacked peptide sequences (supplementary data unavailable as structured sequence table)

### Web extraction (`scripts/extract_web.py`, Practice 4)

- **DRAMP:** antimicrobial activity workbook from DRAMP bulk downloads (`data/raw/web/Antimicrobial.xlsx`, upstream `Antimicrobial_amps.xlsx`); MIC rows parsed from `Target_Organism` `(MIC …)` segments; lab-code prefixes trimmed from organism names where present
- **DBAASP:** REST JSON peptide cards (`dbaasp.org/peptides/{id}`) via numeric ID walk; bacterial MIC rows only; capped per `specs/web_extraction_manifest.json` (`max_records_per_source`). Extracted MIC text is normalized into numeric scalars in the processed dataset (`clean_dataset.py`).

---

## Cleaning and normalization summary (`scripts/clean_dataset.py`, Practice 5)

| Step | Action |
|------|--------|
| Non-bacterial filter | Removed rows where `pathogen_name` contains fungal/viral/mammalian hints |
| Sequence normalization | Upper-case; only standard amino-acid letters; removed gaps |
| Missing peptide sequence | Rows with empty `peptide_sequence` after normalization are **dropped** (required schema field) |
| Unit canonicalization | `μg/ml` → `ug/mL`; `μmol/L` → `uM`; `mg/ml` → `mg/L` etc. via `utils.canonical_measurement_unit()` |
| MIC scalar coercion | `measurement_value` → float-parseable scalar via `utils.coerce_mic_measurement_to_scalar_string()` (comparison symbols stripped; ranges → upper endpoint; see `scripts/clean_dataset.py`) |
| `publication_year` cast | Converted to `pd.Int64Dtype()` |
| Dedup / drop | Filters + fingerprint dedupe + duplicate `record_id` handling reduce **2434 merged → 2406 cleaned** rows in the current artifact |

---

## Validation summary

Run `python scripts/validate_project.py` — **passes** on the bundled `dataset.csv` (fatal checks: required files present, dataset columns ↔ schema alignment, distinct `record_id`, numeric `measurement_value`, non-null mandatory fields). Supplemental warnings may appear for unseen allow-list deviations in `measurement_unit` / `source_type`.

`pytest` runs `tests/test_required_artifacts.py`, `tests/test_extract_web_helpers.py`, etc., when present.

---

## Limitations

1. **Publication year:** ~72 % of rows (from DRAMP) have no `publication_year`; DRAMP workbook does not include year fields per record.
2. **Activity units:** 7 rows carry `AU/μg`, incompatible with µg/mL or µM comparison.
3. **DBAASP dependency:** Live network access to `dbaasp.org` required for DBAASP re-extraction.
4. **Processed MIC semantics:** **`data/processed/dataset.csv`** stores **numeric MIC scalars** after cleaning; censored/range tokens from the literature are not preserved in `measurement_value`. Richer text remains in `data/extracted/*.csv` until `clean_dataset.py` runs.
5. **No unit conversion:** μg/mL and µM are stored separately; cross-unit comparison requires molecular weight of each peptide.

---

## Final artifacts

| Artifact | Path |
|----------|------|
| Processed dataset | `data/processed/dataset.csv` |
| Schema (v0.8.1) | `specs/dataset_schema.json` |
| Source map (v1.8.3) | `specs/source_map.json` |
| PDF manifest (v1.6.0) | `specs/pdf_extraction_manifest.json` |
| Web manifest | `specs/web_extraction_manifest.json` |
| Dataset card | `dataset_card.md` |
| Citation | `CITATION.cff` |
| License | `LICENSE` (CC-BY-4.0) |
| Practice reports | `reports/practice_01_*` through `practice_05_*` |
