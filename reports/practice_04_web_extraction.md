# Practice 4 — Web extraction

## Selected web sources (`specs/web_extraction_manifest.json`)

| source_id | page_id | Endpoint / artefact |
|-----------|---------|---------------------|
| `db_dbaasp` | dbaasp_peptide_cards | `GET https://dbaasp.org/peptides?page=&size=` + `/peptides/{id}?format=json` |
| `db_dramp` | dramp_general_workbook | Local Excel at `data/raw/web/dramp_general_dataset.xlsx` (`general_amps` sheet) |

No other programmatic web pipelines are wired in [`scripts/extract_web.py`](../scripts/extract_web.py). Optional aggregators/benchmark archives (UniProt lookups, HF mirrors, etc.) are **out of scope** for Practice 4 unless a future extractor registers them explicitly in both the manifest **and** `FETCHERS`.

**Note:** CAMPR4/CAMP (`db_campr4`) was evaluated during development but **removed** from the final pipeline — HTML crawl yielded only 12 MIC rows vs ~1000 expected, with heavy overlap against DBAASP/DRAMP.

## Why these endpoints were selected

- **DBAASP** exposes fully structured peptide cards (`targetActivities[]`) aligned with [`specs/dataset_schema.json`](../specs/dataset_schema.json) (medium text, CFU metadata, verbatim MIC concentrations).
- **DRAMP** provides CC BY 4.0 bulk datasets; the curator workbook already present in-repo mirrors the upstream column layout for rapid reproducibility (`DRAMP_ID`, `Sequence`, `Target_Organism`…).

## Retrieval mechanism & provenance tooling

### DBAASP

- Pagination over JSON lists; complexity filter restricts to **monomer** peptides.
- Each accepted card triggers exactly one MIC row **per bacterial** `targetActivities[]` MIC entry.
- `extraction_method`: `web_api`
- Snapshot: [`data/raw/web/dbaasp_antibacterial_search.json`](../data/raw/web/dbaasp_antibacterial_search.json) lists `{page,count,totalCount}` metadata emitted by [`scripts/extract_web.py`](../scripts/extract_web.py).

### DRAMP

- `pandas.read_excel` over the workbook path declared under `local_workbook_path`.
- `Activity` rows must contain *Antibacterial*; MIC segments are mined from **`Target_Organism`** parentheses using `(MIC …)` clauses.
- `extraction_method`: `local_bulk_xlsx`, `extraction_confidence`: `medium`.
- Snapshot: [`data/raw/web/dramp_extraction_run_meta.json`](../data/raw/web/dramp_extraction_run_meta.json) captures relative path + row counts + workbook mtime for audit trails.

## Field mapping recap

Columns follow `web_extraction_manifest.json → output_columns` (also consistent with Practice 1):

| Logical source fragment | Columns |
|---|---|
| peptide sequence FASTA/`Sequence`/`sequence` | `peptide_sequence` |
| peptide title / peptide name (`Title`, `Name`, DBAASP `name`) | `peptide_name` |
| organism / source genus-species hint | `organism_source` |
| segmented pathogen substring before MIC parenthesis OR DBAASP `targetSpecies.name` (+ optional ATCC split) | `pathogen_name`, `pathogen_strain` |
| MIC numeric text + inferred unit literal | `measurement_value`, `measurement_unit` |

All MIC numbers remain **verbatim** (including censored inequalities such as `>200`). [`scripts/utils.py`](../scripts/utils.py) only canonicalises textual unit tokens (`ug/mL`, `uM`, `ng/mL`, …).

## Common extraction caveats

- **Throughput:** DBAASP sequential HTTP crawling is intentional (default `RATE_LIMIT_S` / `rate_limit_s` ≥ 1 s). Expect long wall-clock runs if `max_records` is large.
- **DRAMP overlaps:** Rows often reproduce literature that DBAASP already hosts — merge/dedupe using `(source_id, normalized_sequence, bacterial pathogen fingerprint, verbatim MIC)` if duplicate counting matters.
- **Dependencies:** Requires `requests`, `pandas`, `openpyxl`. Parsing uses regex helpers in `scripts/utils.py` (no HTML parser dependency).

## Output artefacts touched by Practice 4 tooling

| Path | Description |
|---|---|
| [`data/extracted/web_extracted_records.csv`](../data/extracted/web_extracted_records.csv) | Consolidated MIC rows for every enabled manifest source |
| [`data/raw/web/dbaasp_antibacterial_search.json`](../data/raw/web/dbaasp_antibacterial_search.json) | DBAASP paginated fetch metadata snapshot |
| [`data/raw/web/dramp_extraction_run_meta.json`](../data/raw/web/dramp_extraction_run_meta.json) | DRAMP workbook provenance snippet |
| [`data/extracted/extraction_log.jsonl`](../data/extracted/extraction_log.jsonl) | Structured run log appended per `{source_id, status, rows}` |
