# Practice 3 — PDF extraction

> Align with `specs/pdf_extraction_manifest.json` and `data/extracted/pdf_extracted_records.csv`.

## Selected PDF sources

| source_id | pdf_id | Year | Path |
|-----------|--------|------|------|
| paper_ramata_stunda_2023 | ramata_stunda_2023_amp_ssti | 2023 | `data/raw/pdf/antibiotics-12-00551.pdf` |
| paper_zhang_2024 | zhang_2024_symmetric_amp_mrsa | 2024 | `data/raw/pdf/spectrum.00265-24.pdf` |
| paper_lee_2023 | lee_2023_tni_cecropin_colrec | 2023 | `data/raw/pdf/pharmaceutics-15-01752.pdf` |
| paper_melittin_processes_mdpi | melittin_derived_amp_processes_2026 | 2026 | `data/raw/pdf/processes-14-01630.pdf` |
| paper_deepamp_nature_2024 | deepamp_2024_broad_spectrum_amp | 2024 | `data/raw/pdf/s41467-024-51933-2.pdf` |
| paper_ai_amp_curr_microbiol_2025 | ai_amp_curr_microbiol_2025 | 2025 | `data/raw/pdf/s00284-025-04346-3.pdf` |
| paper_life_tn_peptides_2025 | life_tn_peptides_2025 | 2025 | `data/raw/pdf/life-15-00242.pdf` |
| paper_sk_peptides_springer_2025 | sk_peptides_springer_2025 | 2025 | `data/raw/pdf/s44337-025-00335-4.pdf` |
| paper_b7_proline_rich_2025 | b7_proline_rich_2025 | 2025 | `data/raw/pdf/antibiotics-15-00412.pdf` |
| paper_c14r_eskape_2026 | c14r_eskape_2026 | 2026 | `data/raw/pdf/antibiotics-15-00211.pdf` |

## Why these PDFs were selected

All ten sources are **open access** and contain MIC tables with peptide names or sequences.

They add assay context and strain panels that complement DBAASP and DRAMP: designed AMP grids, AI-generated peptides, cecropins, melittin analogues, and ESKAPE-focused studies.

Hu et al. 2022 (*Frontiers*) was removed — sequences were not available in the main text.

## Pages used

| source_id | Pages | Content |
|-----------|-------|---------|
| paper_ramata_stunda_2023 | 4–5 | Table 1: sequences; Table 2: MIC matrix (µg/mL) |
| paper_zhang_2024 | 4–5 | Peptide sequences + MIC vs MRSA strains (µM) |
| paper_lee_2023 | 9 | Cecropin MIC table (µM) |
| paper_melittin_processes_mdpi | 10, 12, 13 | Sequences + MIC tables (µg/mL) |
| paper_deepamp_nature_2024 | 6 | Table 1: 29 peptides × 5 pathogens (µg/mL) |
| paper_ai_amp_curr_microbiol_2025 | 5, 6 | Table 2: AI peptides MIC (µM) |
| paper_life_tn_peptides_2025 | 4 | Table 1: D-TN peptides MIC (µg/mL) |
| paper_sk_peptides_springer_2025 | 3, 8 | Table 1: sequences; Table 4: MIC (µg/mL) |
| paper_b7_proline_rich_2025 | 3 | Table 1–2: sequences + MIC (µM) |
| paper_c14r_eskape_2026 | 4 | Table 1: C14R MIC vs ESKAPE (µg/mL) |

## Extraction methods

**Tool:** `pdfplumber` — text from `pages_used`, parsed by source-specific functions in `scripts/extract_pdf.py` (`TEXT_PARSERS` keyed by `source_id`).

If a PDF is missing or parsing yields no rows, the script logs an empty extraction and does not add placeholder records.

**Path resolution:** manifest `pdf_path` → `pdf_url` basename → any matching `.pdf` in `data/raw/pdf/`.

## Extracted fields

| PDF content | Schema field |
|-------------|--------------|
| Peptide name | `peptide_name` |
| Amino acid sequence | `peptide_sequence` |
| Pathogen + strain | `pathogen_name`, `pathogen_strain` |
| MIC value (as printed) | `measurement_value` (required) |
| Unit (µg/mL, µM, …) | `measurement_unit` |
| Assay block in paper | `assay_method`, `medium`, `inoculum_cfu_ml`, … |
| DOI / URL | `source_url`, `doi`, `source_id` |

MIC values are stored verbatim in `measurement_value` (required on every row); units are canonicalized via `scripts/utils.py`. Rows without a MIC token are not exported.

## Extraction problems

- Merged cells and multi-line headers can misalign columns.
- Zhang and Lee report MIC in **µM**; other papers use **µg/mL** — check `measurement_unit` before comparing.
- Lee Table 1 mixes peptide and antibiotic rows — antibiotic controls are excluded.
- Antibiotics 2026 C14R MIC paper does not reproduce the peptide sequence — `peptide_sequence` is filled from Mildenberger et al. 2024 (Pharmaceuticals 17:83) (`CSSGSLWRLIRRFLRR`).
- Dense tables (deepAMP) need regex-based parsing; occasional missed rows are possible.

## Output files

- `data/extracted/pdf_extracted_records.csv`
- `data/extracted/extraction_log.jsonl` (PDF-related lines)
- Raw PDFs under `data/raw/pdf/`
