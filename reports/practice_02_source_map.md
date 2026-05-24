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

Five open-access papers with explicit peptide MIC tables/PDF parsers were pinned in `specs/pdf_extraction_manifest.json` (`data/raw/pdf/*.pdf`): they widen pathogen/peptide-design coverage relative to databases alone — from ESKAPE + *C. acnes* grids (Ramata‑Stunda) and insect cecropins (Lee), through symmetrical W‑peptide MRSA studies (Zhang), a large α‑helical screening matrix (Hu *Frontiers* 2022), to melittin‑derived analogue panels (*Processes*, 2026).

### Axis 3 — Literature snowballing (non-ingested context)

Citation graphs around the DBAASP / CAMPR database papers surfaced additional review articles featuring MIC tables **outside** our automated ingestion scope — they informed paper selection criteria but **are not scripted into `extract_web.py`**. Auxiliary ML-oriented mirrors (benchmark packs on hubs like Hugging Face) were consciously excluded unless they expose independent experimental provenance, because duplicates would simply restate curated DBAASP rows.

---

## Source groups

All sources are registered in `specs/source_map.json`. Full machine-readable metadata (URL, DOI, access method, license, expected fields, extraction strategy) is in that file. This section summarises each group.

### Databases (`source_id` prefix: `db_`)

Three databases provide the bulk of structured, experimentally validated MIC records:

**`db_dbaasp`** — DBAASP v3 (https://dbaasp.org).
The primary database source. DBAASP is the only major AMP database that stores MIC at the resolution of a single peptide–pathogen–assay triple (matching our one-record definition exactly). Each entry in its `TargetActivity` list maps to one row in our dataset. The REST API supports filtered queries by target group (bacteria), target species, and activity measure (MIC). Output formats: JSON, FASTA, CSV. Expected yield: ~2,000 records after filtering to bacteria and records with a numeric MIC value. Manually curated with PubMed back-links.

**`db_dramp`** — DRAMP 4.0 (http://dramp.cpu-bioinfor.org).
Secondary database source mirrored through the reproducible workbook at `data/raw/web/dramp_general_dataset.xlsx` (see Practice 4 manifest + `FETCHERS["db_dramp"]`). `fetch_dramp()` filters antibacterial rows and mines `(MIC …)` clauses encoded inside **`Target_Organism`**. DRAMP overlaps heavily with DBAASP and primary citations; treat supplementation/dedupe as a downstream Practice 5 decision rather than rejecting rows at ingest.

**`db_campr4`** — CAMPR4 portal (https://camp.bicnirrh.res.in).
Tertiary database source backed by ICMR CAMPR sequencing browser. Automated extraction (`scripts/extract_web.py`) traverses curated `seqDb.php` pagination, opens each CAMPSQ detail tab, reads `FASTA`/Activity/Target fields and only persists antibacterial rows containing explicit `(MIC …)` clauses in Target text. Yield is capped by modest `campr_max_list_pages`/`max_records` defaults because many peptides lack MIC values on-screen (entries without MIC are intentionally skipped).

### Scientific papers (`source_id` prefix: `paper_`)

Five open-access articles are wired for PDF ingestion (`scripts/extract_pdf.py` + `specs/pdf_extraction_manifest.json`); each PDF is listed under **`data/raw/pdf/`** exactly as **`pdf_path`** in the manifest.

**`paper_ramata_stunda_2023`** — Ramata-Stunda et al. 2023, *Antibiotics* 12(3):551 (doi: 10.3390/antibiotics12030551); first author **Anna Ramata-Stunda**.
Table 2 contains MIC values in µg/mL for 11 AMPs (6 de novo designed: R1, R10–R14; 5 reference: RP556, LZ1, AA139, PA13, Oligo10) against 6 pathogens (E. coli, P. aeruginosa, K. pneumoniae, E. faecium, S. aureus, C. acnes). All sequences are in Table 1. Assay: broth microdilution, MHB. Estimated 66 records.

**`paper_zhang_2024`** — Zhang et al. 2024, _Microbiology Spectrum_ (doi: 10.1128/spectrum.00265-24; PMC11537005); first author surname Zhang.
MIC table for 5 symmetrical AMPs (W1–W5) against MRSA/MSSA panels; MIC values stored as **`measurement_value`** with **`measurement_unit`** canonicalized to **`uM`** (no automatic µg/mL conversion). (This replaces an earlier erroneous pointer to Frontiers in Microbiology and DOI `10.3389/...`; the repo PDF matches ASM Spectrum.)

**`paper_lee_2023`** — Lee et al. 2023, _Pharmaceutics_ 15(6):1752 (doi: 10.3390/pharmaceutics15061752); first author **Hyeju Lee**.
Table panels report MIC versus standard and colistin-resistant pathogens; the extractor parses values as **µM** (`pages_used: [9]` in `pdf_extraction_manifest.json`). Only the **T. ni** and **H. cecropia** cecropin rows are modeled as peptide MIC records (antibiotic controls such as polymyxins are excluded despite appearing in tables).

**`paper_hu_fmicb_2022_alpha_helix`** — Hu et al., *Frontiers in Microbiology* (doi: 10.3389/fmicb.2022.870361).
Bench-style TABLE 1: many α-helical peptide codes (**S1–S60**) vs CMCC bacterial strain columns (**µg/mL**); `pages_used: [8]`. Intended for **bulk screening-style coverage**; expect overlap with DBAASP/DRAMP citations for catalogue peptides — keep separate `source_id` rows and optionally dedupe in cleaning.

**`paper_melittin_processes_mdpi`** — Melittin-derived analogues, *Processes* MDPI (doi: 10.3390/pr14101630; PDF `processes-14-01630.pdf`).
MIC-oriented tables (**µg/mL**, CAMHB + assay DMSO per Methods; `pages_used: [10, 12, 13]`) for melittin, TT-1, FKW, WKW versus Gram-positive/Gram-negative panels documented in `pdf_extraction_manifest.json`. Bridges natural-toxin scaffold design with antibacterial MIC reporting.

---

## Priority sources

Sources are ranked by reliability, expected yield, MIC completeness, and extraction difficulty:

| Priority | source_id | Rationale |
|----------|-----------|-----------|
| 1 | `db_dbaasp` | Highest structural fit to schema; MIC per peptide–pathogen–assay triple; REST-ish JSON crawler; continuously curated backbone |
| 2 | `db_dramp` | Local Excel bundle + `(MIC …)` mining; complements coverage but overlaps DBAASP/literature |
| 3 | `paper_ramata_stunda_2023` | Best-structured table; all required fields in same paper; broth microdilution; CC BY 4.0 |
| 4 | `paper_zhang_2024` | MRSA clinical isolate coverage; structured MIC table in µM (`measurement_unit` = `uM`) |
| 5 | `paper_lee_2023` | Insect AMP natural origin; colistin-resistant isolates |
| 6 | `paper_hu_fmicb_2022_alpha_helix` | High-density peptide × strain MIC grid (µg/mL); overlaps curated DB literature |
| 7 | `paper_melittin_processes_mdpi` | Melittin-scaffold analogues + CAMHB MIC tables documented in manifest |
| 8 | `db_campr4` | HTML-only CAMPR portal enrichment; skips entries without MIC text |

Extraction proceeds **first** along the programmatic database axis (`db_*` ingest), **then** the PDF manifests in roughly this priority tier (dense curated tables → specialist screens/extra PDFs → HTML CAMPR as a tertiary scrape).

---

## Access conditions

| source_id | Access status | Registration | API key | Institutional access | Notes |
|-----------|--------------|--------------|---------|----------------------|-------|
| `db_dbaasp` | Open | No | No | No | REST API, no auth; web export also available |
| `db_dramp` | Open | No | No | No | Direct download from dramp.cpu-bioinfor.org/downloads/ |
| `db_campr4` | Open | No | No | No | ICMR-hosted HTML UI; scripted polite crawl (~1 s delay) |
| `paper_ramata_stunda_2023` | Open (CC BY 4.0) | No | No | No | MDPI; direct PDF and HTML access |
| `paper_zhang_2024` | Open-access | No | No | No | ASM Spectrum / PMC canonical PDF (`spectrum.00265-24`) |
| `paper_lee_2023` | Open (CC BY 4.0) | No | No | No | MDPI; direct PDF access |
| `paper_hu_fmicb_2022_alpha_helix` | Open (CC BY Frontiers-style) | No | No | No | Journal/PMC Frontiers PDF (`fmicb-13-870361.pdf`) |
| `paper_melittin_processes_mdpi` | Open (CC BY 4.0) | No | No | No | MDPI Processes (`processes-14-01630.pdf`) |

All sources are freely accessible without institutional subscription. No paywalled sources are included in this source map.

---

## Expected data types

| source_id | Primary data type | Format | Structure quality |
|-----------|------------------|--------|-------------------|
| `db_dbaasp` | Structured records with per-assay MIC | JSON (API) or CSV (export) | High — each record has defined fields |
| `db_dramp` | Structured records with target organism MIC | Excel / CSV | High — all fields annotated |
| `db_campr4` | HTML cards with optional MIC in Target column | Requests + regex | Medium — heterogeneous formatting in Target field |
| `paper_ramata_stunda_2023` | PDF table (Table 2) | PDF → pdfplumber CSV | High — clean grid table, numeric values |
| `paper_zhang_2024` | PDF table (MIC grid) | PDF → pdfplumber CSV | Medium — merged cells possible; MIC quoted in µM |
| `paper_lee_2023` | PDF table (Table 1) | PDF → pdfplumber | High — clean table, explicit strain names |
| `paper_hu_fmicb_2022_alpha_helix` | Large PDF MIC grid (TABLE 1) | PDF → pdfplumber | High — dense matrix; relies on caption pathogen mapping |
| `paper_melittin_processes_mdpi` | PDF MIC tables | PDF → pdfplumber | Medium — multi-table layout across several pages |

---

## Expected conflicts and overlaps

### Inter-database overlap

DBAASP, DRAMP, and CAMPR4 all curate from the same primary literature, so the same MIC value can appear in multiple databases traced to the same DOI. Expected overlap is significant for well-known peptides (LL-37, magainin-2, defensins).

**Resolution rule:** Keep all database records as separate rows with distinct `source_id` values. Cross-link via shared DOI in the `doi` field and shared peptide sequence. Deduplication (choosing a canonical record per peptide–pathogen pair) is deferred to Practice 5.

### Database vs. paper overlap

A paper included in our PDF set (e.g., `paper_ramata_stunda_2023`) may already be curated in DBAASP or DRAMP. The paper record and the database record represent the same experimental measurement but are extracted through different processes.

**Resolution rule:** Both records are retained with their respective `source_id`. The paper record provides higher assay-condition fidelity (medium, CFU stated in Methods); the database record may have additional computed fields. Flag in `notes` when paper and database diverge on numeric MIC value.

### Unit inconsistency (µg/mL vs. µM)

`paper_zhang_2024`, `paper_lee_2023`, and several other peptide-centric tables report MIC in **µM** (`measurement_unit` = `uM`). Ramata-Stunda, Hu *Frontiers*, melittin *Processes*, and most database snapshots express MIC chiefly as **µg/mL**.

**Resolution rule:** Store MIC text in `measurement_value` exactly as decoded from the publication; canonicalize declared units via `measurement_unit` (`ug/mL`, `uM`, …).

### Numeric MIC value disagreement

Two databases may cite the same paper but report different MIC values (e.g., rounding differences, different strains mapped to the same species name).

**Resolution rule:** Prefer the record with a traceable PubMed ID and strain-level specificity. Document the discrepancy in `notes`. If both are within a twofold dilution step (the inherent MIC assay precision), treat as equivalent; otherwise flag for manual review in Practice 5.

### Censored and range values

Sources report MIC as ranges ("4–8 µg/mL"), greater-than bounds (">128 µg/mL"), or less-than bounds ("<1 µg/mL").

**Resolution rule (Practice 1 schema):** Preserve ranges and censored bounds inside `measurement_value` wherever possible (`>128`, `4-8 µg/mL`, etc.).

---


## Coverage gaps

### Pathogen coverage

The five PDF-backed paper sources widen coverage beyond databases alone (*E. coli*, *S. aureus*, MRSA cohorts, *C. acnes*, selected CMCC reference strains, CAMHB panels); they still tilt toward intensely studied pathogens. DBAASP and DRAMP broaden taxonomic breadth, but rarity increases quickly beyond model/clinical favourites.

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

The anchored PDF corpus spans **2022–2026**, while DBAASP/DRAMP index decades of literature through 2024+. Older records occasionally lack peptide sequences altogether (pre-modern sequencing eras).

**Plan:** No explicit date filter applied. Records without `peptide_sequence` are excluded (required field per schema).

### Peptide type coverage

Databases over-represent synthetic AMPs (DRAMP: 17,886 patent entries). Our extraction prioritises experimentally validated, sequence-confirmed peptides. Non-ribosomal and lipopeptide AMPs are covered by DBAASP but may require special handling of non-standard amino acid codes in `peptide_sequence`.

**Plan:** Accept the bias toward synthetic/designed AMPs as a realistic reflection of the current literature. Record `synthesis_type` whenever the extractor can infer it so downstream stratification remains possible.

### Geographic and language coverage

PubMed search was conducted in English only. Non-English publications (Chinese, Japanese, German) may contain MIC tables not indexed in the selected databases.

**Plan:** DBAASP and DRAMP curate from non-English primary sources — their coverage compensates for the English-only paper search. No additional multilingual search planned within this course project.
