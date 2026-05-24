# Practice 3 — PDF extraction


## Selected PDF sources

| source_id | pdf_id | Year | Path |
|-----------|--------|------|------|
| paper_ramata_stunda_2023 | ramata_stunda_2023_amp_ssti | 2023 | `data/raw/pdf/antibiotics-12-00551.pdf` |
| paper_zhang_2024 | zhang_2024_symmetric_amp_mrsa | 2024 | `data/raw/pdf/spectrum.00265-24.pdf` |
| paper_lee_2023 | lee_2023_tni_cecropin_colrec | 2023 | `data/raw/pdf/pharmaceutics-15-01752.pdf` |

## Why these PDFs were selected

All three papers are open access (CC BY 4.0), report experimental MIC values for antibacterial peptides against clinically relevant bacterial pathogens, and include peptide sequences in tables. Together they cover:

- Rationally designed synthetic AMPs against an ESKAPE + *C. acnes* panel (Ramata-Stunda et al., 2023 — *Antibiotics*)
- Symmetric W-peptides against MRSA clinical isolates with MIC in µM (Zhang 2024)
- Insect cecropins against standard and colistin-resistant Gram-negative strains (Lee et al., 2023 — *Pharmaceutics*)

They complement database sources (DBAASP, DRAMP) with primary-literature assay context and strain diversity not always present in curated DBs.

## Pages used

| source_id | Pages | Content |
|-----------|-------|---------|
| paper_ramata_stunda_2023 | 4–5 | Table 1: peptide names + sequences; Table 2: MIC matrix (µg/mL) |
| paper_zhang_2024 | **4–5** | Matches `pdf_extraction_manifest` / PMC PDF pagination: peptides + MIC (µM) vs MRSA 544 / MRSA 103 (see extractor) |
| paper_lee_2023 | **9** | MDPI PDF page index (`pages_used` in manifest): MIC table parsed as µM vs listed strains/resistant isolates |

## Extraction methods

**Primary:** `pdfplumber` — text from `pages_used`, parsed by source-specific logic in `scripts/extract_pdf.py`.

If the PDF is missing or parsing yields no MIC rows, the script logs an empty extraction for that source and does **not** inject placeholder records.

**Path resolution:** script checks `pdf_path` in manifest, then `pdf_url` basename, then any `.pdf` in `data/raw/pdf/`.

## Extracted fields

| PDF field | Schema field |
|-----------|--------------|
| Peptide name | `peptide_name` |
| Amino acid sequence | `peptide_sequence`, `peptide_length` |
| Theoretical MW (when in table) | `molecular_weight_da` |
| Pathogen + strain (column header) | `pathogen_name`, `pathogen_strain`, `gram_stain` |
| MIC numeric value | `measurement_value` |
| MIC in µg/mL | `normalized_value_ug_ml` |
| Assay block in paper | `assay_method`, `medium`, `inoculum_cfu_ml`, `temperature_c`, `incubation_time_h` |
| DOI / URL | `source_url`, `doi`, `source_id` |

Unit conversion (Zhang, Kim): `normalized_value_ug_ml = measurement_value_uM × MW_Da / 1000`.

Censored values (`>64 µM`): stored as string in extract CSV; cleaning step sets numeric fields to null.

## Extraction problems

- Merged cells and multi-line headers in publisher PDF layouts can misalign columns; parsers match pathogen names heuristically.
- Zhang Table 2 reports MIC in µM — MW from Table 1 required for µg/mL normalization.
- Kim Table 1 mixes peptide and antibiotic rows — polymyxin/colistin/melittin rows are excluded.
- Novel peptide sequences in Ramata-Stunda et al. Table 1 may require manual verification if pdfplumber splits sequence strings across cells.

## Output files

- `data/extracted/pdf_extracted_records.csv` — 30 columns (schema + `extraction_method`, `extraction_confidence`, `notes`)
- `data/extracted/extraction_log.jsonl` — per-source method, record count, PDF found flag
- Raw PDFs: `data/raw/pdf/*.pdf`


