# Practice 4 — Web extraction

## Selected web sources

| source_id | page_id | URL |
|-----------|---------|-----|
| db_dbaasp | dbaasp_antibacterial_search | https://dbaasp.org/api/v1 |
| db_dramp | dramp_general_dataset_download | https://dramp.cpu-bioinfor.org/downloads/ |

## Why these sites were selected

**DBAASP v3** is the primary curated AMP database with per-pathogen MIC, assay medium, inoculum, and temperature — fields that map directly to our schema. REST API is documented at https://dbaasp.org/help and free for academic use.

**DRAMP 4.0** provides a bulk Excel general dataset (~11k experimental entries) under CC BY 4.0, with ~70% sequence novelty vs DBAASP — useful complementary coverage.

Both sources are open access, structured, and reproducible via `scripts/extract_web.py`.

## API / page structure

### DBAASP

- **Base URL:** `GET https://dbaasp.org/peptides` (JSON list pagination)
- **Step 1 — list:** `?page=&size=` → peptide summaries (`id`, complexity filtered to monomer in script)
- **Step 2 — detail:** `GET https://dbaasp.org/peptides/{id}?format=json` → sequence + `targetActivities[]` MIC rows
- **Rate limit:** 1 request/second (enforced in script)
- **Snapshot:** `data/raw/web/dbaasp_antibacterial_search.json` (page metadata JSON written by script)

### DRAMP

- **Download:** `GET https://dramp.cpu-bioinfor.org/downloads/files/download/DRAMP_generalData.xlsx`
- **Format:** Excel workbook, parsed with `pandas.read_excel(..., engine="openpyxl")`
- **Cache validation:** file must start with ZIP magic bytes (`PK`) and be >1 KB; invalid cache is re-downloaded
- **Snapshot:** `data/raw/web/dramp_general_dataset.xlsx`

## Extraction methods

| Source | Tool | Method label (log / `extraction_method` in rows) |
|--------|------|---------------------------------------------------|
| DBAASP | `requests` GET + JSON (`/peptides`) | `web_api` |
| DRAMP | `requests` GET + `pandas`/`openpyxl` | `bulk_download_excel` |

If dependencies, network, or parsing fail for a source, that source contributes **zero** rows; the script exits with status 1 when no records were collected overall.

**Volume limit:** `max_records_per_source: 200` in manifest.

## Extracted fields

| API / Excel field | Schema field |
|-------------------|--------------|
| peptideCard.sequence / Sequence | `peptide_sequence`, `peptide_length` |
| peptideCard.name / Name | `peptide_name` |
| peptideCard.mw | `molecular_weight_da` |
| peptideCard.organism / Source_Organism | `organism_source` |
| targetActivity.target / Target_Organism | `pathogen_name` |
| targetActivity.strain | `pathogen_strain` |
| targetActivity.value / MIC_value | `measurement_value` |
| Unit (in API or MIC_unit col) | recorded in `notes` as `unit=...` (not a separate CSV column) |
| Converted µg/mL | `normalized_value_ug_ml` |
| Assay / medium / CFU / temperature | `assay_method`, `medium`, `inoculum_cfu_ml`, `temperature_c` |

## Extraction problems

- DBAASP `search` returns IDs only — full MIC data requires N+1 `peptide_card` calls; limited to 200 records per run.
- DBAASP field names vary (`activityMeasure` vs `measurementType`); parser accepts multiple aliases.
- DRAMP patent subset lacks assay detail — we use the **general dataset** only.
- DRAMP µM rows without MW cannot be converted to µg/mL; `normalized_value_ug_ml` may equal raw value with `unit=uM` in notes.
- If API or download fails, script falls back to 2 example rows per source from manifest.

## Output files

- `data/extracted/web_extracted_records.csv` — 30 columns (schema + provenance fields)
- `data/raw/web/dbaasp_antibacterial_search.json` — valid JSON snapshot
- `data/raw/web/dramp_general_dataset.xlsx` — binary Excel snapshot
- `data/extracted/extraction_log.jsonl` — method, record count, snapshot path

