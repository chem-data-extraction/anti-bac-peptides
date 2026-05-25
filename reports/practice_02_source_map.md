# Practice 2 — Source map

## Source search strategy

Two search paths:

1. **Databases** — surveyed major AMP databases with MIC data (DBAASP, DRAMP, CAMPR4).
2. **Papers** — PubMed and Google Scholar for open-access articles with MIC tables and peptide sequences.

Filters: open access, papers ~2020–2026, broth microdilution, common pathogens (*E. coli*, *S. aureus*, *P. aeruginosa*, etc.).


## Source groups

All sources are in `specs/source_map.json` (version 1.8.2).

### databases

| source_id | Name | Access |
|-----------|------|--------|
| `db_dbaasp` | DBAASP v3 | REST API via `scripts/extract_web.py` |
| `db_dramp` | DRAMP 4.0 | Local Excel `data/raw/web/Antimicrobial.xlsx` |

### scientific_papers

Ten open-access PDFs parsed by `scripts/extract_pdf.py`:

| source_id | Paper (short) | ~Records |
|-----------|---------------|----------|
| `paper_ramata_stunda_2023` | Ramata-Stunda 2023, *Antibiotics* | 66 |
| `paper_zhang_2024` | Zhang 2024, *Microbiology Spectrum* | 10 |
| `paper_lee_2023` | Lee 2023, *Pharmaceutics* | 16 |
| `paper_melittin_processes_mdpi` | Melittin analogues, *Processes* 2026 | 34 |
| `paper_deepamp_nature_2024` | deepAMP, *Nature Comm* 2024 | 150 |
| `paper_ai_amp_curr_microbiol_2025` | AI-designed AMPs, 2025 | 76 |
| `paper_life_tn_peptides_2025` | D-TN peptides, *Life* 2025 | 45 |
| `paper_sk_peptides_springer_2025` | SK peptides, 2025 | 24 |
| `paper_b7_proline_rich_2025` | B7-005 variants, *Antibiotics* 2025 | 6 |
| `paper_c14r_eskape_2026` | C14R vs ESKAPE, *Antibiotics* 2026 | 6 |

## Priority sources

| Priority | source_id | Why |
|----------|-----------|-----|
| 1 | `db_dbaasp` | Best structured MIC data; one row = one peptide–pathogen–MIC |
| 2 | `db_dramp` | Extra coverage; overlaps with DBAASP |
| 3 | `paper_*` | Sequences and assay details from primary literature |

Extract databases first, then PDFs.

## Access conditions

All sources are open access. No registration or API keys.

| source_id | Access | License |
|-----------|--------|---------|
| `db_dbaasp` | https://dbaasp.org | Free for academic use |
| `db_dramp` | Local workbook | CC BY 4.0 |
| `paper_*` | Direct PDF via DOI | Mostly CC BY 4.0 |

## Expected data types

| source_id | Data type | Format |
|-----------|-----------|--------|
| `db_dbaasp` | Structured MIC records | JSON (REST API) |
| `db_dramp` | Activity narratives in Excel | `.xlsx` |
| `paper_*` | MIC tables in papers | PDF → CSV via pdfplumber |

## Expected conflicts and overlaps

- **DBAASP vs DRAMP:** same MIC from the same paper may appear in both. Keep separate rows; 
- **Database vs paper:** a paper may already be in DBAASP/DRAMP. Keep both; paper rows often have better assay details.
- **Units:** some sources use µM, others µg/mL. Store as reported — no automatic conversion.

## Coverage gaps

- Most data cover common lab strains.
- Rare pathogens and anaerobes are under-represented.
- Some DRAMP rows lack `publication_year` or have messy pathogen names.
