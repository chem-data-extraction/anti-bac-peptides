# Practice 3 — PDF extraction


## Selected PDF sources

| source_id | pdf_id | Year | Path |
|-----------|--------|------|------|
| paper_ramata_stunda_2023 | ramata_stunda_2023_amp_ssti | 2023 | `data/raw/pdf/antibiotics-12-00551.pdf` |
| paper_zhang_2024 | zhang_2024_symmetric_amp_mrsa | 2024 | `data/raw/pdf/spectrum.00265-24.pdf` |
| paper_lee_2023 | lee_2023_tni_cecropin_colrec | 2023 | `data/raw/pdf/pharmaceutics-15-01752.pdf` |
| paper_hu_fmicb_2022_alpha_helix | hu_2022_alpha_helical_amp_screen | 2022 | `data/raw/pdf/fmicb-13-870361.pdf` |
| paper_melittin_processes_mdpi | melittin_derived_amp_processes_2026 | 2026 | `data/raw/pdf/processes-14-01630.pdf` |

## Why these PDFs were selected

All five sources are **open access** under their respective publishers (mostly CC BY variants; ASM Spectrum publishes open-access MIC tables under its licence — confirm on landing page).

They collectively report antibacterial peptide MICs with peptide sequences anchored in-document (main text or supplementary, depending on the article):

- Designed synthetic AMP grids against an ESKAPE + *C. acnes* panel (Ramata-Stunda et al. 2023 — *Antibiotics*, CC BY 4.0)
- Symmetrical W-peptides against MRSA cohorts at **µM** (Zhang 2024 — *Microbiology Spectrum*)
- Insect cecropins vs standard and colistin-resistant pathogens at **µM** (Lee et al. 2023 — *Pharmaceutics*, CC BY 4.0)
- Large α-helical screening MIC matrix at **µg/mL** (Hu et al. 2022 — *Frontiers in Microbiology*)
- Melittin-scaffold analogue MIC grids at **µg/mL** in CAMHB (*Processes*, CC BY 4.0)

They complement programmatic database pulls (DBAASP, DRAMP) with reproducible assay context and heterogeneous strain panels.

## Pages used

| source_id | Pages | Content |
|-----------|-------|---------|
| paper_ramata_stunda_2023 | 4–5 | Table 1: peptide names + sequences; Table 2: MIC matrix (µg/mL) |
| paper_zhang_2024 | **4–5** | Matches manifest / PMC PDF pagination: peptides + MIC (µM) vs MRSA 544 / MRSA 103 (see extractor) |
| paper_lee_2023 | **9** | MDPI PDF page index (`pages_used` in manifest): MIC table parsed as µM vs listed strains/resistant isolates |
| paper_hu_fmicb_2022_alpha_helix | **8** | TABLE 1: S1–S60 MIC versus CMCC pathogens (µg/mL per footnote caption) |
| paper_melittin_processes_mdpi | **10, 12, 13** | Sequences plus MIC-heavy tables (`Table 3` / `Table 4` analogue grids in manuscript pagination) |

## Extraction methods

**Primary:** `pdfplumber` — text from `pages_used`, parsed by source-specific logic in `scripts/extract_pdf.py` (`TEXT_PARSERS` keyed by `source_id`).

If the PDF is missing or parsing yields no MIC rows, the script logs an empty extraction for that source and does **not** inject placeholder records.

**Path resolution:** script checks `pdf_path` in manifest, then `pdf_url` basename, then any `.pdf` in `data/raw/pdf/`.

## Extracted fields

| PDF field | Schema field |
|-----------|--------------|
| Peptide name | `peptide_name` |
| Amino acid sequence | `peptide_sequence` |
| Pathogen + strain (column header) | `pathogen_name`, `pathogen_strain`, `gram_stain` |
| MIC value (as printed) | `measurement_value` |
| Printed unit (`µg/mL`, `µM`, …) | `measurement_unit` (canonical labels: `ug/mL`, `uM`, …) |
| Assay block in paper | `assay_method`, `medium`, `inoculum_cfu_ml`, `temperature_c`, `incubation_time_h` |
| DOI / URL | `source_url`, `doi`, `source_id` |

**Unit policy:** MIC is stored exactly as printed in `measurement_value`; publication units appear in canonical form in `measurement_unit`.

Censored values (`>64 µM`): preserved as strings in extract CSV (`measurement_value` non-empty).

## Extraction problems

- Merged cells and multi-line headers in publisher PDF layouts can misalign columns; parsers match pathogen names heuristically.
- Zhang Table 2 reports MIC in µM (`measurement_unit` = `uM`) whereas databases and µg/mL-heavy PDFs coexist — compare only after inspecting `measurement_unit`.
- Lee Table 1 mixes peptide and antibiotic rows — polymyxin/colistin/melittin rows are excluded.
- Novel peptide sequences in Ramata-Stunda et al. Table 1 may require manual verification if pdfplumber splits sequence strings across cells.
- Hu TABLE 1 is dense (`S60` peptides × strains); overlaps with curated DB peptides are inevitable — downstream dedupe is a cleaning decision only.
- Melittin *Processes* distributes sequences and MIC summaries across pages; parsers target manifest page indices deliberately.

## Output files

- `data/extracted/pdf_extracted_records.csv` — schema-aligned columns plus `extraction_method`, `extraction_confidence`, `notes`
- `data/extracted/extraction_log.jsonl` — per-source method, record count, PDF found flag
- Raw PDFs: `data/raw/pdf/*.pdf`

