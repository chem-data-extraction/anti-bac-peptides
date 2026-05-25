# Practice 4 — Web extraction

> Align with `specs/web_extraction_manifest.json` and `data/extracted/web_extracted_records.csv`.

## Selected web sites

| source_id | page_id | URL / artefact |
|-----------|---------|----------------|
| `db_dbaasp` | dbaasp_peptide_cards | `GET https://dbaasp.org/peptides?page=&size=` + `/peptides/{id}?format=json` |
| `db_dramp` | dramp_antimicrobial_workbook | Local Excel at `data/raw/web/Antimicrobial.xlsx` (DRAMP 4.0 `Antimicrobial.xlsx`) |

CAMPR4 (`db_campr4`) was tested but **removed** — HTML crawl gave only ~12 MIC rows.

## Why these sites were selected

- **DBAASP** has structured peptide cards with MIC per bacterial target (`targetActivities[]`).
- **DRAMP** provides a bulk Excel export by activity class (`Antimicrobial.xlsx` on the DRAMP 4.0 downloads page); we use this instead of the general AMP workbook bundle.

Both are open access and complement PDF extraction with large structured datasets.

## Page structure

**DBAASP:** REST JSON API. Paginated peptide list; each card has `sequence`, `name`, and `targetActivities[]` with concentration, unit, target species, and medium metadata. No HTML parsing needed.

**DRAMP:** Excel workbook `Antimicrobial.xlsx`, typically worksheet `general_amps` (configurable via manifest). Columns include `DRAMP_ID`, `Sequence`, `Name`, `Activity`, `Target_Organism`, `Pubmed_ID`. MIC values are embedded in free-text `Target_Organism` fields as `(MIC …)` clauses.

## Extraction methods

**DBAASP** (`fetch_dbaasp` in `scripts/extract_web.py`):
- Paginate JSON list; filter to monomer peptides with bacterial MIC entries.
- Rate limit ≥ 1 s between requests.
- Snapshot: `data/raw/web/dbaasp_antibacterial_search.json`

**DRAMP** (`fetch_dramp`):
- Read workbook with `pandas.read_excel`.
- Filter rows where `Activity` contains "Antibacterial".
- Parse `(MIC …)` segments from `Target_Organism` with regex helpers.
- Snapshot: `data/raw/web/dramp_extraction_run_meta.json`

Dependencies: `requests`, `pandas`, `openpyxl`.

## Extracted fields

| Source fragment | Schema columns |
|-----------------|----------------|
| Sequence / FASTA | `peptide_sequence` |
| Name / Title | `peptide_name` |
| Organism hint | `organism_source` |
| Target species (+ strain split) | `pathogen_name`, `pathogen_strain` |
| MIC text + unit | `measurement_value` (required), `measurement_unit` |

MIC numbers stay verbatim (including `>200`); `measurement_value` must be non-empty on every exported row. Units are canonicalized via `scripts/utils.py`.

## Extraction problems

- DBAASP crawling is slow due to rate limiting and pagination.
- DRAMP free text is messy: Gram-stain markers (`##Gram-positive`), lab codes (`L287`), inhibition percentages in pathogen names.
- DRAMP rows often duplicate DBAASP/literature data — dedupe in Practice 5.
- DBAASP requires a live network connection.

## Output files

- `data/extracted/web_extracted_records.csv`
- `data/raw/web/dbaasp_antibacterial_search.json`
- `data/raw/web/dramp_extraction_run_meta.json`
- `data/extracted/extraction_log.jsonl` (web-related lines)
