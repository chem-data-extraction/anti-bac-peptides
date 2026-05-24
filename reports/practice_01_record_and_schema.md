# Practice 1 — Record definition and dataset schema

> Antibacterial peptides against bacterial pathogens — MIC dataset.

## Topic

Antibacterial peptides against bacterial pathogens.

## Scientific task

Collect experimentally reported **MIC** (minimum inhibitory concentration) values of antibacterial peptides against bacterial pathogens for cross-source comparison of activity, assay conditions, and data provenance.

Pathogen coverage is **broad**: any bacterial pathogen for which an experimental MIC is reported in a source.

## One-record definition

**One record** = one experimentally reported **MIC** value for a specific peptide against a specific bacterial pathogen (strain/isolate when reported) under defined assay conditions, from a single source (one row in `data/processed/dataset.csv`).

## Examples of records

| Example | Why it counts |
|---------|----------------|
| MIC = 8 µM for LL-37 against *E. coli* ATCC 25922 from Table 2 of a paper | One numeric MIC + sequence + pathogen + source |
| MIC = 16 µg/mL for magainin-2 against *S. aureus* from a supplementary table | One measurement for one peptide–pathogen pair |
| MIC = 32 µg/mL for nisin against *L. monocytogenes* from a DBAASP database entry | One curated record with MIC and provenance |

## Non-record examples

| Example | Why it is not a record |
|---------|-------------------------|
| Review paragraph on AMP mechanism without MIC | No measurement |
| List of 30 sequences without MIC for each | Not one measurement per row |
| MBC, IC50, hemolysis, inhibition zone | Out of dataset scope (MIC only) |
| Predicted activity without experimental citation | Out of scope (experimental data only) |

## Dataset fields

### Peptide identity

| Field | Required | How populated |
|-------|----------|---------------|
| `record_id` | yes | Stable ID: `rec_{peptide}_{pathogen}_{source}_{nnn}` |
| `peptide_sequence` | no | Single-letter amino acid code from paper/table/database |
| `peptide_name` | no | Common name (LL-37, magainin-2) when reported |
| `organism_source` | no | Biological origin: binomial species name, or `synthetic` |
| `synthesis_type` | no | `ribosomal` / `nonribosomal` / `synthetic` / `unknown` |

### Target organism

| Field | Required | How populated |
|-------|----------|---------------|
| `pathogen_name` | yes | Binomial or genus name from source |
| `pathogen_strain` | no | ATCC code, clinical isolate ID, etc. |
| `gram_stain` | no | `Gram-positive` / `Gram-negative` / `unknown` |

### MIC measurement

| Field | Required | How populated |
|-------|----------|---------------|
| `measurement_type` | yes | Always `MIC` for this dataset |
| `measurement_value` | no | Verbatim MIC from the source: number, censored (`>128`), ranges, symbols as reported |
| `measurement_unit` | no | Canonical unit label from the extractor (`ug/mL`, `uM`, `mg/L`, etc.) |

Values are kept **in publication units**; downstream consumers normalize if needed.

### Assay conditions

| Field | Required | How populated |
|-------|----------|---------------|
| `assay_method` | no | broth microdilution, agar dilution, etc. |
| `medium` | no | Base medium name when reported: MHB, LB, CAMHB, etc. |
| `medium_composition` | no | Concentrations of substances in the assay medium  |
| `inoculum_cfu_ml` | no | Bacterial inoculum size (e.g. `5e5`); affects absolute MIC values |
| `temperature_c` | no | Assay temperature in °C |
| `incubation_time_h` | no | Incubation duration in hours |



### Provenance

| Field | Required | How populated |
|-------|----------|---------------|
| `source_id` | yes | Key from `specs/source_map.json` |
| `source_type` | no | `scientific_paper` / `database` / `web_page` / `unknown` |
| `publication_year` | no | Year of source publication or database entry |
| `source_url` | no | DOI landing page or database URL |
| `doi` | no | When available |


Full field definitions with types and normalization rules: `specs/dataset_schema.json`.

## Ambiguous cases

- **One peptide, multiple strains of the same species** → separate records with different `pathogen_strain`.
- **MIC reported as a range ("4–8 µg/mL")** → `measurement_value` keeps the verbatim range string (`4-8`) when typed that way by the extractor; optionally describe range semantics in extractor `notes`.
- **MIC > 128 µg/mL ("`>128`")** → preserve `>` / `<` in `measurement_value`.
- **Modified peptides (D-amino acids, cyclization, N-terminal modifications)** → describe in extractor `notes` if needed; canonical sequence stays in `peptide_sequence`.
- **Synthetic peptide known only by name / structure in the publication** → optional `peptide_sequence`; anchor on `peptide_name` until the sequence can be inferred from supplementary material.
- **Duplicate in paper and database** → allow separate source rows upstream; downstream cleaning collapses identical rows (all fields except `record_id`).
- **Different units (µg/mL vs µM)** → verbatim concentration in `measurement_value`; `measurement_unit` holds the canonicalized label (`ug/mL`, `uM`, …).
- **Standard medium with no extra details** → `medium` = `MHB`; `medium_composition` = null.
- **Modified medium (e.g. "MHB + 150 mM NaCl")** → `medium` = `MHB`; `medium_composition` = `150 mM NaCl`.
- **Synthetic / de-novo designed peptide with no natural source** → `organism_source` = `synthetic`; `synthesis_type` = `synthetic`.
