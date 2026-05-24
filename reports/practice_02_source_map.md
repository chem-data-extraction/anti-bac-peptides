# Practice 2 — Source Map

> Antibacterial peptides against bacterial pathogens — MIC dataset.

## Source search strategy

The search was conducted across three independent axes that together cover the full landscape of experimentally reported AMP MIC data.

### Axis 1 — Specialized AMP databases

The starting point was a survey of purpose-built antimicrobial peptide databases that curate MIC values from primary literature. Three major databases were identified:

| Database | Version | Size | MIC coverage |
|----------|---------|------|--------------|
| DBAASP | v3 (2021, continuously updated) | >15,700 entries | Per peptide–pathogen–assay record; MIC stored with medium, CFU, temperature |
| DRAMP | v4.0 (2024) | 30,260 entries | General (~11k experimental), patent, clinical; MIC per target organism |
| CAMPR4 | v4 (2022) | 24,243 sequences | MIC values for experimentally validated entries |

The databases were identified from the following sources:
- DBAASP: Pirtskhalava et al. 2021, *Nucleic Acids Research* (doi: 10.1093/nar/gkaa991)
- DRAMP 4.0: Ma et al. 2025, *Nucleic Acids Research* (doi: 10.1093/nar/gkae1008)
- CAMPR4: Waghu et al. 2023, *Nucleic Acids Research* (doi: 10.1093/nar/gkac1012)

APD6 (Antimicrobial Peptide Database, version 6; 6,309 entries) was also surveyed but excluded as a primary MIC source because the APD development team confirmed (FAQ, January 2026) that the bulk MIC export is being unified and is not yet available. APD6 will be used only for sequence cross-validation.

### Axis 2 — Primary literature (PubMed / Google Scholar)

**Search queries:**
- PubMed: `("antimicrobial peptide" OR "antibacterial peptide") AND "minimum inhibitory concentration" AND ("broth microdilution") AND ("Escherichia coli" OR "Staphylococcus aureus" OR "Pseudomonas aeruginosa")`
- Google Scholar: `antimicrobial peptide MIC table sequence open access 2022 2023 2024`
- Filters: publication year 2020–2024, full text available, open access

**Selection criteria for PDF sources:**
1. Contains an explicit MIC table (not only figures) with numeric µg/mL or µM values
2. Reports the amino acid sequence of each tested peptide
3. Describes the assay method (broth microdilution preferred; agar dilution acceptable)
4. Published open access under a license permitting data reuse (CC BY 4.0 preferred)
5. Tests clinically relevant pathogens (ESKAPE panel or documented drug-resistant strains)

Three papers were selected that collectively cover a broad pathogen panel (8 species + colistin-resistant clinical isolates) and diverse peptide origins (rationally designed synthetic, insect natural, modified natural).

### Axis 3 — Snowballing and ML datasets

Citations in the DBAASP and DRAMP reference papers were scanned for review articles containing large MIC tables. Additionally, ML-oriented AMP benchmark datasets were surveyed because they often provide pre-processed versions of database MIC data with provenance links:

- QMAP Benchmark (2026, biorXiv doi: 10.64898/2026.02.03.703041): DBAASP-derived MIC regression dataset for E. coli and S. aureus, available on Hugging Face.
- ESCAPE dataset (Harvard Dataverse): large aggregated AMP classification dataset from 27 databases — excluded because it lacks per-record MIC values (classification only, not regression).

DRAMP 3.0 GitHub repository (CPU-DRAMP/DRAMP-3.0) was identified as an alternative access path to DRAMP data when the main download page is slow or unavailable.

---

## Source groups

All sources are registered in `specs/source_map.json`. Full machine-readable metadata (URL, DOI, access method, license, expected fields, extraction strategy) is in that file. This section summarises each group.

### Databases (`source_id` prefix: `db_`)

Three databases provide the bulk of structured, experimentally validated MIC records:

**`db_dbaasp`** — DBAASP v3 (https://dbaasp.org).
The primary database source. DBAASP is the only major AMP database that stores MIC at the resolution of a single peptide–pathogen–assay triple (matching our one-record definition exactly). Each entry in its `TargetActivity` list maps to one row in our dataset. The REST API supports filtered queries by target group (bacteria), target species, and activity measure (MIC). Output formats: JSON, FASTA, CSV. Expected yield: ~2,000 records after filtering to bacteria and records with a numeric MIC value. Manually curated with PubMed back-links.

**`db_dramp`** — DRAMP 4.0 (http://dramp.cpu-bioinfor.org).
The secondary database source. DRAMP's general dataset (~11,612 entries) provides experimentally validated AMPs with MIC annotations. Its bulk download (CC BY 4.0) is categorised by activity type — the antibacterial subset is downloaded directly. DRAMP 4.0 uniquely adds serum and protease stability annotations. Expected yield: ~3,000 records from the antibacterial subset after filtering to entries with numeric MIC values. Significant non-overlap with DBAASP (DRAMP reported ~70% non-overlapping sequences vs APD+CAMP in v2; overlap with DBAASP is smaller but non-negligible — see overlaps section).

**`db_campr4`** — CAMPR4 (https://camp.bicnirrh.res.in).
Tertiary database source. CAMPR4 has a separate curation pipeline and captures records from older literature that the other two databases may have missed. No bulk API, so records are retrieved by querying by target organism through the web interface and exporting results. Lower automation level than DBAASP/DRAMP. Expected yield: ~500 additional records not already covered by the other two databases.

### Scientific papers (`source_id` prefix: `paper_`)

Three open-access papers with explicit MIC tables were selected for PDF extraction:

**`paper_ramata_stunda_2023`** — Ramata-Stunda et al. 2023, *Antibiotics* 12(3):551 (doi: 10.3390/antibiotics12030551); first author **Anna Ramata-Stunda**.
Table 2 contains MIC values in µg/mL for 11 AMPs (6 de novo designed: R1, R10–R14; 5 reference: RP556, LZ1, AA139, PA13, Oligo10) against 6 pathogens (E. coli, P. aeruginosa, K. pneumoniae, E. faecium, S. aureus, C. acnes). All sequences are in Table 1. Assay: broth microdilution, MHB. Estimated 66 records.

**`paper_zhang_2024`** — Zhang et al. 2024, _Microbiology Spectrum_ (doi: 10.1128/spectrum.00265-24; PMC11537005); first author surname Zhang.
MIC table for 5 symmetrical AMPs (W1–W5) against MRSA/MSSA and other panels; values reported in **µM** — convert to µg/mL via `molecular_weight_da` in `scripts/extract_pdf.py`. (This replaces an earlier erroneous pointer to Frontiers in Microbiology and DOI `10.3389/...`; the repo PDF matches ASM Spectrum.)

**`paper_lee_2023`** — Lee et al. 2023, _Pharmaceutics_ 15(6):1752 (doi: 10.3390/pharmaceutics15061752); first author **Hyeju Lee**.
Table panels report MIC versus standard and colistin-resistant pathogens; the extractor parses values as **µM** (`pages_used: [9]` in `pdf_extraction_manifest.json`). Only the **T. ni** and **H. cecropia** cecropin rows are modeled as peptide MIC records (antibiotic controls such as polymyxins are excluded despite appearing in tables).

### Supplementary materials (`source_id` prefix: `supp_`)

**`supp_ramata_stunda_2023_s1`** — Supplementary Table S1 from Ramata-Stunda et al. 2023.
Contains antibiotic control MICs (not peptide records). Included in the source map for completeness and cross-checking assay validity. Not extracted into the dataset.

### Aggregators (`source_id` prefix: `agg_`)

Two standard bioinformatics resources are used for metadata enrichment only — they do not provide MIC values:

**`agg_uniprot`** — UniProt (https://www.uniprot.org). REST API lookup for `organism_source` standardisation (canonical binomial species names).

**`agg_ncbi_taxonomy`** — NCBI Taxonomy (https://www.ncbi.nlm.nih.gov/taxonomy). Biopython Entrez lookup for canonical `pathogen_name` and `gram_stain` classification from taxon lineage (Firmicutes = Gram-positive; Proteobacteria = Gram-negative).

### GitHub repositories (`source_id` prefix: `gh_`)

**`gh_dramp_github`** — CPU-DRAMP/DRAMP-3.0 (https://github.com/CPU-DRAMP/DRAMP-3.0).
Excel workbook with sequences from 4 databases (DRAMP, APD, DBAASP, CAMP). Secondary access path to DRAMP data. Used if the DRAMP downloads page is unavailable; also used to record a fixed commit SHA for reproducibility. CC BY 4.0.

### ML datasets (`source_id` prefix: `ml_`)

**`ml_qmap`** — QMAP Benchmark (https://huggingface.co/datasets/anthol42/qmap_benchmark_2025).
DBAASP-derived MIC regression splits for machine learning benchmarking; citation DOI prefix `10.64898/` links to Cold Spring Harbor’s bioRxiv resolver (canonical URL uses `10.64898/2026.02.03.703041`). Use only as **cross-validation** against `db_dbaasp`; not an independent MIC source because entries duplicate curated DBAASP rows.

### Reference databases (`source_id` prefix: `db_apd6`)

**`db_apd6`** — APD6 (https://aps.unmc.edu).
6,309 peptides (Jan 2026). MIC bulk export pending. Used exclusively for sequence cross-validation against DBAASP/DRAMP entries via peptide name or FASTA search.

---

## Priority sources

Sources are ranked by reliability, expected yield, MIC completeness, and extraction difficulty:

| Priority | source_id | Rationale |
|----------|-----------|-----------|
| 1 | `db_dbaasp` | Highest structural fit to schema; MIC per peptide–pathogen–assay triple; REST API; manually curated; >15k entries |
| 2 | `db_dramp` | Bulk CC BY 4.0 download; large general dataset; complements DBAASP with non-overlapping records; DRAMP 4.0 is the most current version |
| 3 | `paper_ramata_stunda_2023` | Best-structured table; all required fields in same paper; broth microdilution; 6 pathogens; CC BY 4.0 |
| 4 | `paper_zhang_2024` | MRSA clinical isolate coverage; structured table; unit conversion needed (µM) |
| 5 | `paper_lee_2023` | Insect AMP natural origin; colistin-resistant isolates; clean table; smaller yield |
| 6 | `db_campr4` | Supplementary cross-check; no bulk API; overlaps expected with DBAASP/DRAMP |
| 7 | `gh_dramp_github` | Alternate DRAMP snapshot on GitHub; provenance cross-check |
| 8 | `ml_qmap` | Cross-validation against db_dbaasp only; not primary |
| — | `agg_uniprot`, `agg_ncbi_taxonomy` | Metadata enrichment; no MIC data |
| — | `db_apd6` | Sequence cross-validation only |
| — | `supp_ramata_stunda_2023_s1` | Antibiotic controls; not extracted |

Extraction will proceed in priority order: databases first (highest yield with lowest manual effort), then papers.

---

## Access conditions

| source_id | Access status | Registration | API key | Institutional access | Notes |
|-----------|--------------|--------------|---------|----------------------|-------|
| `db_dbaasp` | Open | No | No | No | REST API, no auth; web export also available |
| `db_dramp` | Open | No | No | No | Direct download from dramp.cpu-bioinfor.org/downloads/ |
| `db_campr4` | Open | No | No | No | Web interface only; no bulk API |
| `paper_ramata_stunda_2023` | Open (CC BY 4.0) | No | No | No | MDPI; direct PDF and HTML access |
| `paper_zhang_2024` | Open-access | No | No | No | ASM Spectrum / PMC canonical PDF (`spectrum.00265-24`) |
| `paper_lee_2023` | Open (CC BY 4.0) | No | No | No | MDPI; direct PDF access |
| `agg_uniprot` | Open | No | No | No | REST API; NCBI email recommended for Entrez |
| `agg_ncbi_taxonomy` | Open | Email (recommended) | No | No | Biopython Entrez; register email per NCBI policy |
| `gh_dramp_github` | Open | No (GitHub account optional) | No | No | Public repo; `git clone` or ZIP |
| `ml_qmap` | Open | No (Hugging Face account optional) | No | No | Hugging Face datasets; pip install datasets |
| `db_apd6` | Open | No | No | No | Web download; FASTA lists on downloads page |

All sources are freely accessible without institutional subscription. No paywalled sources are included in this source map.

---

## Expected data types

| source_id | Primary data type | Format | Structure quality |
|-----------|------------------|--------|-------------------|
| `db_dbaasp` | Structured records with per-assay MIC | JSON (API) or CSV (export) | High — each record has defined fields |
| `db_dramp` | Structured records with target organism MIC | Excel / CSV | High — all fields annotated |
| `db_campr4` | Structured records with MIC | HTML table / exported CSV | Medium — web-scraped; some fields inconsistent |
| `paper_ramata_stunda_2023` | PDF table (Table 2) | PDF → pdfplumber CSV | High — clean grid table, numeric values |
| `paper_zhang_2024` | PDF table (MIC grid) | PDF → pdfplumber CSV | Medium — merged cells possible; unit µM |
| `paper_lee_2023` | PDF table (Table 1) | PDF → pdfplumber CSV | High — clean table, explicit strain names |
| `agg_uniprot` | Protein metadata | JSON (REST) | High |
| `agg_ncbi_taxonomy` | Taxonomy metadata | XML (Entrez) | High |
| `gh_dramp_github` | Aggregated sequence data | Excel (.xlsx) | Medium — multiple sheets, nested structure |
| `ml_qmap` | MIC regression splits | Parquet / CSV | High — pre-processed, consistent columns |

---

## Expected conflicts and overlaps

### Inter-database overlap

DBAASP, DRAMP, and CAMPR4 all curate from the same primary literature, so the same MIC value can appear in multiple databases traced to the same DOI. Expected overlap is significant for well-known peptides (LL-37, magainin-2, defensins).

**Resolution rule:** Keep all database records as separate rows with distinct `source_id` values. Cross-link via shared DOI in the `doi` field and shared peptide sequence. Deduplication (choosing a canonical record per peptide–pathogen pair) is deferred to Practice 5.

### Database vs. paper overlap

A paper included in our PDF set (e.g., `paper_ramata_stunda_2023`) may already be curated in DBAASP or DRAMP. The paper record and the database record represent the same experimental measurement but are extracted through different processes.

**Resolution rule:** Both records are retained with their respective `source_id`. The paper record provides higher assay-condition fidelity (medium, CFU stated in Methods); the database record may have additional computed fields. Flag in `notes` when paper and database diverge on numeric MIC value.

### Unit inconsistency (µg/mL vs. µM)

`paper_zhang_2024` reports MIC in µM; all databases and other papers use µg/mL.

**Resolution rule:** Store the value as reported in `measurement_value`; record the original unit in `notes`; compute `normalized_value_ug_ml` in Practice 5 using `molecular_weight_da` via: µM × MW_Da / 1000 = µg/mL.

### Numeric MIC value disagreement

Two databases may cite the same paper but report different MIC values (e.g., rounding differences, different strains mapped to the same species name).

**Resolution rule:** Prefer the record with a traceable PubMed ID and strain-level specificity. Document the discrepancy in `notes`. If both are within a twofold dilution step (the inherent MIC assay precision), treat as equivalent; otherwise flag for manual review in Practice 5.

### Censored and range values

Sources report MIC as ranges ("4–8 µg/mL"), greater-than bounds (">128 µg/mL"), or less-than bounds ("<1 µg/mL").

**Resolution rule (from Practice 1 schema):** `measurement_value` = null; full expression and unit recorded in `notes`. Do not store the bound as an exact value.

### Predicted vs. experimental confusion in ML datasets

`ml_qmap` is derived from DBAASP and should contain only experimental values, but the ESCAPE dataset and similar aggregations explicitly mix experimental and ML-predicted MICs.

**Resolution rule:** Use only `ml_qmap` for cross-validation, not primary extraction. For any record where experimental provenance cannot be confirmed, exclude from the dataset and document in the extraction log.

---

## Coverage gaps

### Pathogen coverage

The three paper sources focus on ESKAPE pathogens (*E. coli*, *S. aureus*, *P. aeruginosa*, *K. pneumoniae*, *E. faecium*, *A. baumannii*) and skin pathogens (*C. acnes*). DBAASP and DRAMP cover a broader taxonomic range, but coverage thins rapidly outside the most-studied species.

**Under-represented taxa:**
- *Mycobacterium tuberculosis* (Gram-indeterminate; different assay conditions — MABA/LORA methods)
- Anaerobic pathogens (*C. difficile*, *Bacteroides fragilis*): rarely tested with standard broth microdilution
- Drug-resistant Gram-positive non-MRSA strains (VRE, VISA)
- Non-pathogenic model organisms used in AMP research (*B. subtilis*, *M. smegmatis*)

**Plan:** Accept the ESKAPE focus as consistent with the core scientific use case. Flag non-standard assay conditions (non-MHB medium, anaerobic incubation) in `notes` to allow downstream filtering.

### Assay condition coverage

Most reported MIC values use CLSI broth microdilution (37°C, MHB, 5×10⁵ CFU/mL, 18–24h). However:
- Some papers use non-standard salt concentrations (MHB + 150 mM NaCl) that alter MIC values
- Inoculum sizes vary between studies (10⁴–10⁶ CFU/mL)
- Temperature variation (35°C vs 37°C) is rarely reported

**Plan:** Record `assay_method`, `medium`, `medium_composition`, `inoculum_cfu_ml`, `temperature_c`, and `incubation_time_h` when available. Leave null otherwise. Non-standard conditions are flagged in `notes`.

### Temporal coverage

The three selected papers span 2023–2024. DBAASP and DRAMP cover literature from 1970s to 2024. Older records may lack sequence data (pre-sequencing era peptides).

**Plan:** No explicit date filter applied. Records without `peptide_sequence` are excluded (required field per schema).

### Peptide type coverage

Databases over-represent synthetic AMPs (DRAMP: 17,886 patent entries). Our extraction prioritises experimentally validated, sequence-confirmed peptides. Non-ribosomal and lipopeptide AMPs are covered by DBAASP but may require special handling of non-standard amino acid codes in `peptide_sequence`.

**Plan:** Accept the bias toward synthetic/designed AMPs as a realistic reflection of the current literature. Record `synthesis_type` and `peptide_modifications` to allow downstream stratification.

### Geographic and language coverage

PubMed search was conducted in English only. Non-English publications (Chinese, Japanese, German) may contain MIC tables not indexed in the selected databases.

**Plan:** DBAASP and DRAMP curate from non-English primary sources — their coverage compensates for the English-only paper search. No additional multilingual search planned within this course project.
