# Practice 1 — Record definition and dataset schema


## Topic

Antibacterial peptides and their activity against bacteria.

## Scientific task

Collect experimentally reported **MIC** values (minimum inhibitory concentration) for antibacterial peptides against bacterial pathogens.

## One-record definition

**One record** = one experimentally reported MIC value for one peptide against one bacterial pathogen from a specific source (one row in `data/processed/dataset.csv`).

## Examples of records

| Example | Why it counts |
|---------|----------------|
| MIC = 8 µM for peptide W1 vs *E. coli* ATCC 25922 from Table 2 | One MIC + peptide + pathogen + source |
| MIC = 16 µg/mL for magainin-2 vs *S. aureus* from a database entry | One measurement for one peptide–pathogen pair |
| MIC = 32 µg/mL for nisin vs *L. monocytogenes* from DRAMP | One curated record with MIC and provenance |

## Non-record examples

| Example | Why it is not a record |
|---------|-------------------------|
| Review text about AMPs without MIC numbers | No measurement |
| List of sequences without MIC for each | Not one measurement per row |
| MBC, IC50, or predicted activity only | Out of dataset scope (MIC only) |

## Dataset fields

Full field definitions are in `specs/dataset_schema.json`. Summary:

**Peptide:** `record_id` (required), `peptide_sequence`, `peptide_name`, `organism_source`, `synthesis_type`

**Pathogen:** `pathogen_name` (required), `pathogen_strain`, `gram_stain`

**MIC:** `measurement_type` (required, always `MIC`), `measurement_value` (required), `measurement_unit`

**Assay:** `assay_method`, `medium`, `medium_composition`, `inoculum_cfu_ml`, `temperature_c`, `incubation_time_h`

**Source:** `source_id` (required), `source_type`, `publication_year`, `source_url`, `doi`

**Required fields (summary):** `record_id`, `pathogen_name`, `measurement_type`, `measurement_value`, `source_id`.

## Ambiguous cases

- Same peptide, different strains → separate records.
- MIC as a range or censored value (`4-8`, `>128`) → keep original text in `measurement_value`.
- Different units (µg/mL vs µM) → do not convert; store canonical unit in `measurement_unit`.
- Same measurement in a paper and a database → two rows with different `source_id`; deduplicate in Practice 5.
- No sequence in the source → leave `peptide_sequence` empty; use `peptide_name` if available.
