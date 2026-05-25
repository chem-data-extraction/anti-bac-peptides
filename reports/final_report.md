# Final report — Antibacterial peptide MIC dataset

**Version:** 0.5.0  
**Commit:** `bfdfee3`  
**Date:** 2026-05-25  
**Status:** Complete

---

## Project summary

This project built a structured, reproducible dataset of experimentally reported **minimum inhibitory concentration (MIC)** values for antibacterial peptides against bacterial pathogens. The dataset integrates records from two curated databases (DRAMP, DBAASP) and ten open-access peer-reviewed papers published between 2023 and 2026.

**Final dataset:** `data/processed/dataset.csv` — **1 521 rows × 18 columns**.

---

## Dataset goal

**Scientific question:** What MIC values have been experimentally reported for antibacterial peptides, and how do they vary across peptide types, pathogen species, assay conditions, and literature sources?

**Intended audience:** Computational chemists and bioinformaticians developing AMP design models; researchers performing meta-analyses of antimicrobial activity; students learning structured scientific data extraction.

---

## Source summary

| Source group | Source ID | Type | Records |
|-------------|-----------|------|---------|
| Database | `db_dramp` | DRAMP bulk `Antimicrobial.xlsx` | 999 |
| Database | `db_dbaasp` | DBAASP REST API | 89 |
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

**Total:** 12 sources, 1 521 records after deduplication.

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
- **DBAASP:** REST API (`dbaasp.org/peptides`); 1 000 records fetched with `seen_pids` deduplication; filtered to bacterial targets and MIC measurements

---

## Cleaning and normalization summary (`scripts/clean_dataset.py`, Practice 5)

| Step | Action |
|------|--------|
| Non-bacterial filter | Removed rows where `pathogen_name` contains fungal/viral/mammalian hints |
| Sequence normalization | Upper-case; only standard amino-acid letters; removed gaps |
| Missing peptide sequence | Rows with empty `peptide_sequence` after normalization are **dropped** (required schema field) |
| Unit canonicalization | `μg/ml` → `ug/mL`; `μmol/L` → `uM`; `mg/ml` → `mg/L` etc. via `utils.canonical_measurement_unit()` |
| `publication_year` cast | Converted to `pd.Int64Dtype()` — no more `2023.0` floats |
| Deduplication | Content-fingerprint deduplication removed **913 duplicate rows** |

---

## Validation summary

Run `python scripts/validate_project.py` — **passes** with 2 informational warnings:

```
WARNING: Non-canonical measurement_unit values (7 rows): {'AU/μg': 7}
WARNING: Suspicious pathogen_name patterns (digit/##/lab-code prefix): ...18 rows...
Validation passed.
(2 warning(s))
```

- `AU/μg` — 7 DRAMP records use activity units; cannot be converted to concentration; retained as-is
- Suspicious pathogen names — DRAMP source artifact (inhibition-percentage prefixes in ~18 rows); not fixable without manual curation of the upstream workbook

Required fields enforced by validation: `record_id`, `peptide_sequence`, `pathogen_name`, `measurement_value`, `source_id`.

`pytest` passes all tests in `tests/test_required_artifacts.py`.

---

## Limitations

1. **Publication year:** ~72 % of rows (from DRAMP) have no `publication_year`; DRAMP workbook does not include year fields per record.
2. **Activity units:** 7 rows carry `AU/μg`, incompatible with µg/mL or µM comparison.
3. **DBAASP dependency:** Live network access to `dbaasp.org` required for DBAASP re-extraction.
4. **Verbatim MIC values:** Censored bounds (`>64`, `≤2`) are stored as-is; numeric aggregation requires additional parsing.
5. **No unit conversion:** μg/mL and µM are stored separately; cross-unit comparison requires molecular weight of each peptide.

---

## Final artifacts

| Artifact | Path |
|----------|------|
| Processed dataset | `data/processed/dataset.csv` |
| Schema (v0.8.0) | `specs/dataset_schema.json` |
| Source map (v1.8.2) | `specs/source_map.json` |
| PDF manifest (v1.6.0) | `specs/pdf_extraction_manifest.json` |
| Web manifest | `specs/web_extraction_manifest.json` |
| Dataset card | `dataset_card.md` |
| Citation | `CITATION.cff` |
| License | `LICENSE` (CC-BY-4.0) |
| Practice reports | `reports/practice_01_*` through `practice_05_*` |
