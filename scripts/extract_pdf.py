from __future__ import annotations

import csv
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from utils import canonical_measurement_unit, unit_context_note, verbatim_measurement_value

SCHEMA_PATH = ROOT / "specs/dataset_schema.json"
PROVENANCE_FIELDS = ("extraction_method", "extraction_confidence", "notes")
STANDARD_AA = set("ACDEFGHIKLMNPQRSTVWYX")


def load_schema_field_names() -> list[str]:
    with SCHEMA_PATH.open(encoding="utf-8") as f:
        schema = json.load(f)
    return [field["name"] for field in schema["fields"]]


def default_output_columns() -> list[str]:
    return load_schema_field_names() + list(PROVENANCE_FIELDS)


def load_output_columns(manifest: dict) -> list[str]:
    columns = manifest.get("output_columns")
    if columns:
        return list(columns)
    return default_output_columns()


def normalize_sequence(seq: object) -> str:
    if seq is None or str(seq).strip() == "":
        return ""
    text = str(seq).upper().strip().replace(" ", "").replace("-", "")
    return "".join(c for c in text if c in STANDARD_AA)


def row_to_output(row: dict, columns: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for col in columns:
        val = row.get(col, "")
        if val is None:
            val = ""
        out[col] = val
    return out


def write_extract_csv(rows: list[dict], path: Path, columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row_to_output(row, columns))


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def resolve_pdf_path(source: dict, root: Path = ROOT) -> Path | None:
    """Find PDF on disk using manifest path, pdf_url basename, or doi slug."""
    candidates: list[Path] = []
    pdf_path = source.get("pdf_path", "")
    if pdf_path:
        candidates.append(root / pdf_path)

    pdf_url = source.get("pdf_url", "")
    if pdf_url:
        candidates.append(root / "data/raw/pdf" / Path(pdf_url).name)

    doi = source.get("doi", "")
    if doi:
        slug = doi.split("/")[-1]
        for pattern in (f"{slug}.pdf", f"*{slug}*.pdf"):
            candidates.extend(root.glob(f"data/raw/pdf/{pattern}"))

    seen: set[Path] = set()
    for path in candidates:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        if path.is_file() and path.stat().st_size > 1000:
            return path
    return None


MANIFEST = ROOT / "specs/pdf_extraction_manifest.json"
OUTPUT_CSV = ROOT / "data/extracted/pdf_extracted_records.csv"
LOG_PATH = ROOT / "data/extracted/extraction_log.jsonl"

# ---------------------------------------------------------------------------
# Pathogen lookup tables shared by multiple parsers
# ---------------------------------------------------------------------------

RAMATA_STUNDA_PATHOGENS = [
    ("Escherichia coli", "ATCC 25922"),
    ("Pseudomonas aeruginosa", "ATCC 27853"),
    ("Klebsiella pneumoniae", "ATCC 700603"),
    ("Enterococcus faecium", "ATCC 19434"),
    ("Staphylococcus aureus", "ATCC 25923"),
    ("Cutibacterium acnes", "ATCC 6919"),
]

LEE_PEPTIDES = [
    {
        "col_index": 0,
        "peptide_name": "H. cecropia cecropin A",
        "peptide_sequence": "KWKLFKKIEKVGQNIRDGIIKAGPAVAVVGQATQIAK",
        "organism_source": "Hyalophora cecropia",
    },
    {
        "col_index": 1,
        "peptide_name": "T. ni cecropin A",
        "peptide_sequence": "RWKFFKKIEKVGQNIRDGIIKAGPAVAVVGQAASITGK",
        "organism_source": "Trichoplusia ni",
    },
]

LEE_STRAIN_MAP = {
    "e. coli": ("Escherichia coli", "ATCC 25922"),
    "a. baumannii": ("Acinetobacter baumannii", "ATCC 19606"),
    "p. aeruginosa": ("Pseudomonas aeruginosa", "ATCC 27853"),
    "k. pneumoniae": ("Klebsiella pneumoniae", "ATCC 13883"),
    "colrec 1557": ("Escherichia coli", "ColREC 1557"),
    "colrec 12": ("Escherichia coli", "ColREC 12"),
    "colrab 1915": ("Acinetobacter baumannii", "ColRAB 1915"),
    "colrkp 139": ("Klebsiella pneumoniae", "ColRKP 139"),
}

PROCESSES_PEPTIDE_NAMES = ("Melittin", "TT-1", "FKW", "WKW")


def parse_melittin_processes_text(page_texts: dict[int, str], source: dict) -> list[dict]:
    """MDPI Processes — Table 3 (S. aureus ATCC 25923); Table 4 ESKAPE panel MIC (µg/mL); sequences from Table 2."""
    source_id = source["source_id"]
    text_all = "\n".join(page_texts.get(p, "") for p in sorted(page_texts))

    pep_meta: dict[str, dict[str, Any]] = {}
    for m in re.finditer(
        r"^(Melittin|TT-1|FKW|WKW)\s+([A-Z]+)\s+([\d.]+)\s+([\d.]+)\s*$",
        text_all,
        re.MULTILINE,
    ):
        raw_name = m.group(1)
        seq = normalize_sequence(m.group(2))
        if not seq:
            continue
        pep_meta[raw_name] = {"sequence": seq}

    rows: list[dict] = []

    def add_row(*, peptide: str, pname: str, strain: str, raw_mic: str, table_note: str) -> None:
        mic_s = raw_mic.strip()
        if mic_s.upper() == "N.R." or mic_s in ("-", "–", ""):
            return
        meta = pep_meta.get(peptide, {})
        seq = meta.get("sequence", "")
        mv = verbatim_measurement_value(mic_s)
        rows.append({
            **_base_row(source, source_id),
            "record_id": (
                f"rec_{slugify(peptide)}_{slugify(strain)[:14]}"
                f"_proc14101630_{len(rows) + 1:04d}"
            ),
            "peptide_name": peptide,
            "peptide_sequence": seq,
            "organism_source": (
                "Apis mellifera" if peptide == "Melittin" else "synthetic"
            ),
            "pathogen_name": pname,
            "pathogen_strain": strain,
            "measurement_value": mv,
            "measurement_unit": "ug/mL",
            "notes": f"Processes (MDPI) {table_note}; {unit_context_note('ug/mL')}".strip(
                "; "
            ),
        })

    def _canon_processes_peptide(name: str) -> str | None:
        ls = name.strip().lower()
        if ls == "melittin":
            return "Melittin"
        if ls in ("tt-1", "tt1"):
            return "TT-1"
        if ls == "fkw":
            return "FKW"
        if ls == "wkw":
            return "WKW"
        return None

    t3_anchor = re.search(r"Table\s+3\.\s*MIC[^\n]*\n[^\n]+\n", text_all, re.IGNORECASE)
    if t3_anchor:
        for line in text_all[t3_anchor.end():].splitlines():
            line_st = line.strip()
            if not line_st:
                continue
            if (
                line_st.startswith("MIC:")
                or re.match(r"^3(?:\.)?\s+Multidrug", line_st, re.I)
                or line_st.lower().startswith("table 4")
            ):
                break
            mlin = re.match(r"^(Melittin|TT-1|FKW|WKW)\s+(\S+)\s+\S+\s*$", line_st, re.I)
            if not mlin:
                continue
            pkey = _canon_processes_peptide(mlin.group(1))
            if not pkey:
                continue
            add_row(
                peptide=pkey,
                pname="Staphylococcus aureus",
                strain="ATCC 25923",
                raw_mic=mlin.group(2),
                table_note="Table 3 vs S. aureus ATCC 25923 (MIC column)",
            )

    t4_pat = re.compile(
        r"^(S(?:\.)?\s*epidermidis|S(?:\.)?\s*aureus|E(?:\.)?\s*faecalis|E(?:\.)?\s*faecium|"
        r"K(?:\.)?\s*pneumoniae|E(?:\.)?\s*coli|A(?:\.)?\s*baumannii|P(?:\.)?\s*aeruginosa)\s+"
        r"ATCC\s+([\d,]+)\s+\*{1,2}\s+(.+)\s*$",
        re.I,
    )
    species_abbr: dict[str, str] = {
        "s.epidermidis": "Staphylococcus epidermidis",
        "s.aureus": "Staphylococcus aureus",
        "e.faecalis": "Enterococcus faecalis",
        "e.faecium": "Enterococcus faecium",
        "k.pneumoniae": "Klebsiella pneumoniae",
        "e.coli": "Escherichia coli",
        "a.baumannii": "Acinetobacter baumannii",
        "p.aeruginosa": "Pseudomonas aeruginosa",
    }

    for line in text_all.splitlines():
        line_st = line.strip()
        m4 = t4_pat.match(line_st)
        if not m4:
            continue
        abbr_compact = re.sub(r"\s+", "", m4.group(1).lower())
        pname = species_abbr.get(abbr_compact, "")
        if not pname:
            continue
        atcc = "ATCC " + m4.group(2).replace(",", "").strip()
        rest = m4.group(3).strip().split()
        if len(rest) < 4:
            continue
        mic4 = rest[:4]
        for peptide, raw_mic in zip(PROCESSES_PEPTIDE_NAMES, mic4):
            add_row(
                peptide=peptide,
                pname=pname,
                strain=atcc,
                raw_mic=raw_mic,
                table_note=f"Table 4 ({m4.group(1)} {atcc})",
            )
    return rows


def append_log(entry: dict) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def extract_page_texts(pdf_path: Path, pages_used: list[int]) -> dict[int, str]:
    try:
        import pdfplumber
    except ImportError:
        return {}
    texts: dict[int, str] = {}
    with pdfplumber.open(pdf_path) as pdf:
        n_pages = len(pdf.pages)
        page_nums = pages_used if pages_used else list(range(1, n_pages + 1))
        for page_num in page_nums:
            if 1 <= page_num <= n_pages:
                texts[page_num] = pdf.pages[page_num - 1].extract_text() or ""
    return texts


def _base_row(source: dict, source_id: str) -> dict[str, Any]:
    assay = source.get("assay_conditions", {})
    return {
        "source_id": source_id,
        "source_type": "scientific_paper",
        "publication_year": source.get("publication_year", ""),
        "source_url": source.get("source_url", ""),
        "doi": source.get("doi", ""),
        "assay_method": assay.get("assay_method", ""),
        "medium": assay.get("medium", ""),
        "inoculum_cfu_ml": assay.get("inoculum_cfu_ml", ""),
        "temperature_c": assay.get("temperature_c", ""),
        "incubation_time_h": assay.get("incubation_time_h", ""),
        "extraction_method": "pdf_text",
        "extraction_confidence": "high",
        "organism_source": source.get("default_organism_source", ""),
    }


def parse_ramata_stunda_text(text: str, source: dict) -> list[dict]:
    """Parse Ramata-Stunda et al. 2023 (Antibiotics) MIC table; source_id `paper_ramata_stunda_2023`."""
    source_id = source["source_id"]
    block = text
    start = re.search(r"Table2\.Minimal", text, re.IGNORECASE)
    end = re.search(r"Noclearcorrelations|Table3\.", text, re.IGNORECASE)
    if start:
        block = text[start.start(): end.start() if end else len(text)]

    sequences: dict[str, str] = {}
    seq_start = re.search(r"Table1\.", text, re.IGNORECASE)
    seq_end = re.search(r"Table2\.", text, re.IGNORECASE)
    seq_block = text[seq_start.start(): seq_end.start()] if seq_start and seq_end else text
    for m in re.finditer(
        r"^(RP556|LZ1|AA139|PA13|Oligo10|R14|R13|R12|R11|R10|R1)\s+([A-Z]{5,})",
        seq_block,
        re.MULTILINE,
    ):
        sequences[m.group(1)] = normalize_sequence(m.group(2))

    mic_pat = re.compile(
        r"^(RP556|LZ1|AA139|PA13|Oligo10|R14|R13|R12|R11|R10|R1)\s+"
        r"(?:\[\d+\]|This\s*work|Commercial[^\d]*)\s+"
        r"([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)",
        re.MULTILINE | re.IGNORECASE,
    )
    rows: list[dict] = []
    for m in mic_pat.finditer(block):
        peptide_name = m.group(1)
        values = [m.group(i) for i in range(2, 8)]
        seq = sequences.get(peptide_name, "")
        for (pname, strain), raw_mic in zip(RAMATA_STUNDA_PATHOGENS, values):
            mv = verbatim_measurement_value(raw_mic)
            rows.append({
                **_base_row(source, source_id),
                "record_id": (
                    f"rec_{slugify(peptide_name)[:14]}_{slugify(strain)[:10]}"
                    f"_ramata2023_{len(rows) + 1:03d}"
                ),
                "peptide_name": peptide_name,
                "peptide_sequence": seq,
                "organism_source": "synthetic",
                "pathogen_name": pname,
                "pathogen_strain": strain,
                "measurement_value": mv,
                "measurement_unit": "ug/mL",
                "notes": (
                    f"Ramata-Stunda et al. 2023 (Antibiotics) Table 2; "
                    f"{unit_context_note('ug/mL')}"
                ).strip(),
            })
    return rows


def _parse_mic_tokens(line: str) -> list[str]:
    parts = line.strip().split()
    tokens: list[str] = []
    i = 0
    while i < len(parts):
        if parts[i] == ">" and i + 1 < len(parts):
            tokens.append(f">{parts[i + 1]}")
            i += 2
        else:
            tokens.append(parts[i])
            i += 1
    return tokens


def parse_zhang_text(page_texts: dict[int, str], source: dict) -> list[dict]:
    """Zhang et al. 2024 Spectrum — Table 1 peptide/MW; Table 2 MIC (µM) vs MRSA strains."""
    source_id = source["source_id"]
    text_all = "\n".join(page_texts.get(p, "") for p in sorted(page_texts))

    peptides: dict[str, dict] = {}
    for m in re.finditer(
        r"^\s*(W[1-5])\s+([A-Z0-9]+-NH2)\s+([\d.]+)\s+([\d.]+)",
        text_all,
        re.MULTILINE,
    ):
        raw_tok = m.group(2).replace("-NH2", "")
        seq = normalize_sequence(raw_tok)
        try:
            float(m.group(3))
            float(m.group(4))
        except ValueError:
            continue
        if not seq:
            continue
        peptides[m.group(1)] = {"sequence": seq}

    rows: list[dict] = []
    for line in text_all.splitlines():
        line_st = line.strip()
        m_lin = re.match(r"^MRSA\s+(544|103)\s+([>≤<≥\d].*)$", line_st)
        if not m_lin:
            continue
        strain_label = f"MRSA {m_lin.group(1)}"
        tokens = _parse_mic_tokens(m_lin.group(2).strip())
        if len(tokens) < 5:
            continue
        for pep_name, raw_mic in zip(["W1", "W2", "W3", "W4", "W5"], tokens[:5]):
            meta = peptides.get(pep_name, {})
            seq = meta.get("sequence", "")
            mv = verbatim_measurement_value(raw_mic)
            rows.append({
                **_base_row(source, source_id),
                "record_id": (
                    f"rec_{pep_name.lower()}_{slugify(strain_label)[:12]}"
                    f"_zhang2024_{len(rows) + 1:03d}"
                ),
                "peptide_name": pep_name,
                "peptide_sequence": seq,
                "organism_source": "synthetic",
                "pathogen_name": "Staphylococcus aureus",
                "pathogen_strain": strain_label,
                "measurement_value": mv,
                "measurement_unit": canonical_measurement_unit("uM"),
                "notes": f"Zhang 2024 Table 2; {unit_context_note('uM')}".strip("; "),
            })
    return rows


def parse_lee_text(page_texts: dict[int, str], source: dict) -> list[dict]:
    """Parse Lee et al. 2023 (Pharmaceutics) MIC table for cecropin peptides; source_id `paper_lee_2023`."""
    source_id = source["source_id"]
    text_all = "\n".join(page_texts.values())
    rows: list[dict] = []
    org_pattern = re.compile(
        r"^(E\. coli|A\. baumannii|P\. aeruginosa|K\. pneumoniae|"
        r"ColREC \d+|ColRAB \d+|ColRKP \d+)\s+(.+)$"
    )
    for line in text_all.splitlines():
        line = line.strip()
        if not line or line.lower().startswith(("table", "minimal", "microorganism", "pharmaceutics")):
            continue
        if any(line.lower().startswith(p) for p in ("gm ", "hc10", "relative", "*", "colrec:", "colrab:", "colrkp:")):
            continue
        m = org_pattern.match(line)
        if not m:
            continue
        org_key = m.group(1).lower()
        vals = m.group(2).split()
        if org_key not in LEE_STRAIN_MAP or len(vals) < 2:
            continue
        pname, strain = LEE_STRAIN_MAP[org_key]
        for pep_info, raw_mic in zip(LEE_PEPTIDES, vals[:2]):
            mv = verbatim_measurement_value(raw_mic)
            rows.append({
                **_base_row(source, source_id),
                "record_id": (
                    f"rec_{slugify(pep_info['peptide_name'])[:12]}_{slugify(strain)[:10]}"
                    f"_lee2023_{len(rows) + 1:03d}"
                ),
                "peptide_name": pep_info["peptide_name"],
                "peptide_sequence": pep_info["peptide_sequence"],
                "organism_source": pep_info["organism_source"],
                "pathogen_name": pname,
                "pathogen_strain": strain,
                "measurement_value": mv,
                "measurement_unit": canonical_measurement_unit("uM"),
                "notes": (
                    f"Lee et al. 2023 (Pharmaceutics) Table 1; "
                    f"{unit_context_note('uM')}"
                ).strip(),
            })
    return rows


# ---------------------------------------------------------------------------
# New parsers: deepAMP, AI-designed AMPs, D-TN peptides, SK peptides,
# B7-005 variants, C14R vs ESKAPE
# ---------------------------------------------------------------------------

# deepAMP (Nature Comm 2024): Table 1 — peptide/sequence/MIC matrix
DEEPAMP_PATHOGENS: list[tuple[str, str]] = [
    ("Escherichia coli", "laboratory strain"),
    ("Staphylococcus aureus", "ATCC 25923"),
    ("Klebsiella pneumoniae", "laboratory strain"),
    ("Pseudomonas aeruginosa", "laboratory strain"),
    ("Staphylococcus aureus", "MRSA"),
]
def parse_deepamp_text(page_texts: dict[int, str], source: dict) -> list[dict]:
    """Li et al. 2024 Nature Comm — Table 1 deepAMP peptides MIC (µg/mL) vs 5 organisms."""
    source_id = source["source_id"]
    text_all = "\n".join(page_texts.get(p, "") for p in sorted(page_texts))

    rows: list[dict] = []
    pep_pat = re.compile(
        r"^(Penetratin|T[12]-\d+)\s+([A-Z]{10,})\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)",
        re.MULTILINE,
    )
    for m in pep_pat.finditer(text_all):
        pep_name = m.group(1)
        seq = normalize_sequence(m.group(2))
        mic_vals = [m.group(i) for i in range(3, 13, 2)]  # groups 3,5,7,9,11 = MIC cols
        for (pname, strain), raw_mic in zip(DEEPAMP_PATHOGENS, mic_vals):
            mv = verbatim_measurement_value(raw_mic)
            if not mv:
                continue
            rows.append({
                **_base_row(source, source_id),
                "record_id": (
                    f"rec_{slugify(pep_name)}_{slugify(pname.split()[1])[:8]}"
                    f"_deepamp2024_{len(rows) + 1:04d}"
                ),
                "peptide_name": pep_name,
                "peptide_sequence": seq,
                "organism_source": "synthetic",
                "pathogen_name": pname,
                "pathogen_strain": strain,
                "measurement_value": mv,
                "measurement_unit": "ug/mL",
                "notes": f"Li et al. 2024 (Nature Comm) Table 1; {unit_context_note('ug/mL')}",
            })
    return rows


# AI-designed AMPs (Curr Microbiol 2025): Table 2 — 12 peptides vs 4 bacterial species in µM
_AI_AMP_PATHOGENS: list[tuple[str, str]] = [
    ("Escherichia coli", "ATCC 25922"),        # E.c
    ("Klebsiella pneumoniae", "ATCC 700603"),  # K.q (quasipneumoniae)
    ("Staphylococcus aureus", "ATCC 25923"),   # S.a
    ("Pseudomonas aeruginosa", "ATCC 27853"),  # P.a
]


def parse_ai_amp_text(page_texts: dict[int, str], source: dict) -> list[dict]:
    """Mesa et al. 2025 Curr Microbiol — Table 2: AI-designed peptides MIC (µM) vs 4 bacteria."""
    source_id = source["source_id"]
    text_all = "\n".join(page_texts.get(p, "") for p in sorted(page_texts))

    rows: list[dict] = []
    # Pattern: PeptideName Sequence C.a_MIC E.c_MIC K.q_MIC S.a_MIC P.a_MIC ...
    # Skip first col (C.albicans = fungal), take cols 2-5
    pep_pat = re.compile(
        r"^(OrP\d+M?|VeP\d+M?)\s+([A-Z]{8,})\s+([\d.>]+)\s+([\d.>]+)\s+([\d.>]+)\s+([\d.>]+)\s+([\d.>]+)",
        re.MULTILINE,
    )
    for m in pep_pat.finditer(text_all):
        pep_name = m.group(1)
        seq = normalize_sequence(m.group(2))
        # group 3=C.a (skip), 4=E.c, 5=K.q, 6=S.a, 7=P.a
        mic_vals = [m.group(i) for i in range(4, 8)]
        for (pname, strain), raw_mic in zip(_AI_AMP_PATHOGENS, mic_vals):
            if raw_mic.lstrip(">") == "":
                continue
            mv = verbatim_measurement_value(raw_mic)
            if not mv:
                continue
            rows.append({
                **_base_row(source, source_id),
                "record_id": (
                    f"rec_{slugify(pep_name)}_{slugify(pname.split()[1])[:8]}"
                    f"_aiamp2025_{len(rows) + 1:04d}"
                ),
                "peptide_name": pep_name,
                "peptide_sequence": seq,
                "organism_source": "synthetic",
                "pathogen_name": pname,
                "pathogen_strain": strain,
                "measurement_value": mv,
                "measurement_unit": canonical_measurement_unit("uM"),
                "notes": f"Mesa et al. 2025 (Curr Microbiol) Table 2; {unit_context_note('uM')}",
            })
    return rows


# D-TN peptides (Life 2025): Table 1 — TN/D-TN peptides MIC (µg/mL) vs 3 bacteria
_LIFE_TN_PATHOGENS: list[tuple[str, str]] = [
    ("Staphylococcus aureus", "ATCC 29213"),
    ("Escherichia coli", "ATCC 25922"),
    ("Pseudomonas aeruginosa", "ATCC 27853"),
]
_LIFE_TN6_2_SEQ = "RLLRLLRLLLRLLRLLR"


def parse_life_tn_text(page_texts: dict[int, str], source: dict) -> list[dict]:
    """Kocagoz et al. 2025 Life — Table 1: TN/D-TN peptides MIC (µg/mL) vs 3 bacteria."""
    source_id = source["source_id"]
    text_all = "\n".join(page_texts.get(p, "") for p in sorted(page_texts))

    rows: list[dict] = []
    pep_pat = re.compile(
        r"^(D-TN\d+[A-Z\d/]*|TN\d+[A-Z\d\-]*(?:\(\d\))?|RTN\d+|D/L-TN\d+)\s+([A-Z]+)\s+(>?\d+)\s+(>?\d+)\s+(>?\d+)\s+(>?\d+)",
        re.MULTILINE,
    )
    for m in pep_pat.finditer(text_all):
        pep_name = m.group(1)
        seq = normalize_sequence(m.group(2))
        # groups 3=S.aureus, 4=E.coli, 5=P.aeruginosa, 6=C.albicans (skip)
        mic_vals = [m.group(i) for i in range(3, 6)]
        for (pname, strain), raw_mic in zip(_LIFE_TN_PATHOGENS, mic_vals):
            mv = verbatim_measurement_value(raw_mic)
            if not mv:
                continue
            rows.append({
                **_base_row(source, source_id),
                "record_id": (
                    f"rec_{slugify(pep_name)}_{slugify(pname.split()[1])[:8]}"
                    f"_lifedtn2025_{len(rows) + 1:04d}"
                ),
                "peptide_name": pep_name,
                "peptide_sequence": seq,
                "organism_source": "synthetic",
                "pathogen_name": pname,
                "pathogen_strain": strain,
                "measurement_value": mv,
                "measurement_unit": "ug/mL",
                "notes": f"Kocagoz et al. 2025 (Life) Table 1; {unit_context_note('ug/mL')}",
            })

    # Handle TN6(2) whose sequence wraps across lines in PDF text
    tn62_pat = re.compile(
        r"TN6\(2\)\s+(>?\d+)\s+(>?\d+)\s+(>?\d+)\s+(>?\d+)", re.MULTILINE
    )
    for m in tn62_pat.finditer(text_all):
        mic_vals = [m.group(i) for i in range(1, 4)]
        for (pname, strain), raw_mic in zip(_LIFE_TN_PATHOGENS, mic_vals):
            mv = verbatim_measurement_value(raw_mic)
            if not mv:
                continue
            rows.append({
                **_base_row(source, source_id),
                "record_id": (
                    f"rec_tn6_2_{slugify(pname.split()[1])[:8]}"
                    f"_lifedtn2025_{len(rows) + 1:04d}"
                ),
                "peptide_name": "TN6(2)",
                "peptide_sequence": _LIFE_TN6_2_SEQ,
                "organism_source": "synthetic",
                "pathogen_name": pname,
                "pathogen_strain": strain,
                "measurement_value": mv,
                "measurement_unit": "ug/mL",
                "notes": f"Kocagoz et al. 2025 (Life) Table 1; sequence reconstructed from split PDF line; {unit_context_note('ug/mL')}",
            })
    return rows


# SK peptides (Springer 2025): Table 4 organism-as-rows format
_SK_PEPTIDE_SEQS: dict[str, str] = {
    "SK1203": "AAWWKAKKWAWAKAWAWKKAW",
    "SK1217": "AFWWKAKKFAWAKKFAWWKAW",
    "SK1260": "KAFAVKFAWKFHAWKAWKKAW",
    "SK1286": "HFAPKKSKPAHFPHKSKPKAW",
    "SK1281": "HFAVKHAVWAHVWHKAKSR",
    "SK1283": "HFAVKKAKVAHFVHKAKSKAW",
}
_SK_PEPTIDE_ORDER = ("SK1203", "SK1217", "SK1260", "SK1281", "SK1283", "SK1286")
_SK_ORGANISM_MAP: dict[str, tuple[str, str]] = {
    "e.coli":       ("Escherichia coli",      "ATCC 8739"),
    "s.aureus":     ("Staphylococcus aureus",  "ATCC 6538"),
    "k.pneumonia":  ("Klebsiella pneumoniae",  "ATCC 700603"),
    "p.aeruginsa":  ("Pseudomonas aeruginosa", "ATCC 9027"),
    "p.aeruginosa": ("Pseudomonas aeruginosa", "ATCC 9027"),
}


def parse_sk_peptides_text(page_texts: dict[int, str], source: dict) -> list[dict]:
    """Kakkerla et al. 2025 Discover Medicine — Table 4: SK peptides MIC (µg/mL) vs 4 bacteria."""
    source_id = source["source_id"]
    text_all = "\n".join(page_texts.get(p, "") for p in sorted(page_texts))

    rows: list[dict] = []
    row_pat = re.compile(
        r"^(E\.coli|S\.aureus|K\.pneumonia|P\.aeruginsa|P\.aeruginosa)\s+"
        r"([\d.>]+)\s+([\d.>]+)\s+([\d.>]+)\s+([\d.>]+)\s+([\d.>]+)\s+([\d.>]+)",
        re.MULTILINE | re.IGNORECASE,
    )
    for m in row_pat.finditer(text_all):
        org_key = re.sub(r"\s+", "", m.group(1)).lower()
        organism_info = _SK_ORGANISM_MAP.get(org_key)
        if not organism_info:
            continue
        pname, strain = organism_info
        mic_vals = [m.group(i) for i in range(2, 8)]
        for pep_name, raw_mic in zip(_SK_PEPTIDE_ORDER, mic_vals):
            mv = verbatim_measurement_value(raw_mic)
            if not mv:
                continue
            seq = _SK_PEPTIDE_SEQS.get(pep_name, "")
            rows.append({
                **_base_row(source, source_id),
                "record_id": (
                    f"rec_{slugify(pep_name)}_{slugify(pname.split()[1])[:8]}"
                    f"_sk2025_{len(rows) + 1:04d}"
                ),
                "peptide_name": pep_name,
                "peptide_sequence": seq,
                "organism_source": "synthetic",
                "pathogen_name": pname,
                "pathogen_strain": strain,
                "measurement_value": mv,
                "measurement_unit": "ug/mL",
                "notes": f"Kakkerla et al. 2025 (Discover Med) Table 4; {unit_context_note('ug/mL')}",
            })
    return rows


# B7-005 variants (Antibiotics 2025): Table 2 — 3 peptides vs E.coli + 2 P.aeruginosa in µM
_B7_PEPTIDE_SEQS: dict[str, str] = {
    "B7-005": "WRIRRRWPRLPRPRWR",
    "B7-006": "WRIRRWPRLPRPRWR",
    "B7-007": "WRIRRWPRLPRWR",
}
_B7_PEPTIDE_ORDER = ("B7-005", "B7-006", "B7-007")
_B7_ORGANISM_MAP: dict[str, tuple[str, str]] = {
    "e.coliatcc25922":             ("Escherichia coli",       "ATCC 25922"),
    "p.aeruginosapao1":            ("Pseudomonas aeruginosa", "ATCC 15692 PAO1"),
    "p.aeruginosaatcc27823":       ("Pseudomonas aeruginosa", "ATCC 27823"),
}


def parse_b7_proline_text(page_texts: dict[int, str], source: dict) -> list[dict]:
    """Cappella et al. 2025 Antibiotics — Table 2: B7-005/B7-006/B7-007 MIC (µM) vs 3 strains."""
    source_id = source["source_id"]
    text_all = "\n".join(page_texts.get(p, "") for p in sorted(page_texts))

    rows: list[dict] = []
    row_pat = re.compile(
        r"^(E\.coliATCC25922|P\.aeruginosaPAO1(?:\(ATCC15692\))?|P\.aeruginosaATCC27823)\s+"
        r"([\d.]+)\s+([\d.]+)\s+([\d.]+)",
        re.MULTILINE | re.IGNORECASE,
    )
    for m in row_pat.finditer(text_all):
        org_key = re.sub(r"[\s()]+", "", m.group(1)).lower()
        organism_info = _B7_ORGANISM_MAP.get(org_key)
        if not organism_info:
            continue
        pname, strain = organism_info
        mic_vals = [m.group(i) for i in range(2, 5)]
        for pep_name, raw_mic in zip(_B7_PEPTIDE_ORDER, mic_vals):
            mv = verbatim_measurement_value(raw_mic)
            if not mv:
                continue
            seq = _B7_PEPTIDE_SEQS.get(pep_name, "")
            rows.append({
                **_base_row(source, source_id),
                "record_id": (
                    f"rec_{slugify(pep_name)}_{slugify(pname.split()[1])[:8]}"
                    f"_b72025_{len(rows) + 1:04d}"
                ),
                "peptide_name": pep_name,
                "peptide_sequence": seq,
                "organism_source": "synthetic",
                "pathogen_name": pname,
                "pathogen_strain": strain,
                "measurement_value": mv,
                "measurement_unit": canonical_measurement_unit("uM"),
                "notes": f"Cappella et al. 2025 (Antibiotics) Table 2; {unit_context_note('uM')}",
            })
    return rows


# Canonical C14R sequence from Mildenberger et al. 2024, Pharmaceuticals 17:83 (not reproduced in Antibiotics 2026 MIC paper).
_C14R_CANON_SEQUENCE = "CSSGSLWRLIRRFLRR"


# C14R vs ESKAPE (Antibiotics 2026): Table 1 — single peptide vs 6 ESKAPE strains in µg/mL
_C14R_ORGANISM_MAP: dict[str, tuple[str, str]] = {
    "e.faecium,vre":            ("Enterococcus faecium",    "DSM 17050 VRE"),
    "s.aureus,mrsa":            ("Staphylococcus aureus",   "ATCC 43300 MRSA"),
    "k.quasipneumoniae,esbl":   ("Klebsiella pneumoniae",   "ATCC 700603 ESBL"),
    "a.baumannii":              ("Acinetobacter baumannii", "ATCC 19606"),
    "p.aeruginosa":             ("Pseudomonas aeruginosa",  "PAO1"),
    "e.coli,esbl":              ("Escherichia coli",        "BSU1286 ESBL"),
}


def parse_c14r_text(page_texts: dict[int, str], source: dict) -> list[dict]:
    """Gruber et al. 2026 Antibiotics — Table 1: C14R MIC (µg/mL) vs 6 ESKAPE pathogens."""
    source_id = source["source_id"]
    text_all = "\n".join(page_texts.get(p, "") for p in sorted(page_texts))

    rows: list[dict] = []
    # Table rows: "Organism MIC[µg/mL] MBIC[µg/mL]"
    row_pat = re.compile(
        r"^(E\.faecium[,\s]+VRE|S\.aureus[,\s]+MRSA|K\.quasipneumoniae[,\s]+ESBL"
        r"|A\.baumannii|P\.aeruginosa|E\.coli[,\s]+ESBL)\s+([\d.]+)\s+([\d.]+|n\.a\.)",
        re.MULTILINE | re.IGNORECASE,
    )
    for m in row_pat.finditer(text_all):
        org_raw = re.sub(r"\s+", "", m.group(1)).lower()
        org_info = _C14R_ORGANISM_MAP.get(org_raw)
        if not org_info:
            continue
        pname, strain = org_info
        mv = verbatim_measurement_value(m.group(2))
        if not mv:
            continue
        rows.append({
            **_base_row(source, source_id),
            "record_id": (
                f"rec_c14r_{slugify(pname.split()[1])[:8]}"
                f"_c14r2026_{len(rows) + 1:04d}"
            ),
            "peptide_name": "C14R",
            "peptide_sequence": _C14R_CANON_SEQUENCE,
            "organism_source": "synthetic",
            "pathogen_name": pname,
            "pathogen_strain": strain,
            "measurement_value": mv,
            "measurement_unit": "ug/mL",
            "notes": f"Gruber et al. 2026 (Antibiotics) Table 1; Gompertz-fit MIC; sequence from Mildenberger et al. 2024 (Pharmaceuticals 17:83); {unit_context_note('ug/mL')}",
        })
    return rows


TEXT_PARSERS: dict[str, Callable[[dict[int, str], dict], list[dict]]] = {
    "paper_ramata_stunda_2023": lambda texts, src: parse_ramata_stunda_text("\n".join(texts.values()), src),
    "paper_zhang_2024": parse_zhang_text,
    "paper_lee_2023": parse_lee_text,
    "paper_melittin_processes_mdpi": parse_melittin_processes_text,
    "paper_deepamp_nature_2024": parse_deepamp_text,
    "paper_ai_amp_curr_microbiol_2025": parse_ai_amp_text,
    "paper_life_tn_peptides_2025": parse_life_tn_text,
    "paper_sk_peptides_springer_2025": parse_sk_peptides_text,
    "paper_b7_proline_rich_2025": parse_b7_proline_text,
    "paper_c14r_eskape_2026": parse_c14r_text,
}


def extract_from_pdf(source: dict) -> tuple[list[dict], str, bool]:
    pdf_path = resolve_pdf_path(source)
    if pdf_path is None:
        return [], "missing_pdf", False

    page_texts = extract_page_texts(pdf_path, source.get("pages_used", []))
    parser = TEXT_PARSERS.get(source["source_id"])
    if parser and page_texts:
        rows = parser(page_texts, source)
        if rows:
            return rows, "pdf_text", True
    return [], "parse_failed", True


def main() -> None:
    with MANIFEST.open(encoding="utf-8") as f:
        manifest = json.load(f)

    output_columns = load_output_columns(manifest)
    all_rows: list[dict] = []

    print(f"PDF extraction — schema v{manifest.get('schema_version', '')}")

    cap_raw = manifest.get("max_records_per_source")
    try:
        per_source_cap = int(cap_raw) if cap_raw is not None else None
    except (TypeError, ValueError):
        per_source_cap = None
    if per_source_cap is not None:
        print(f"max_records_per_source: {per_source_cap}")
    print(f"Output columns: {len(output_columns)}")

    for src in manifest.get("input_sources", []):
        source_id = src["source_id"]
        print(f"\n[{source_id}]")

        pdf_path = resolve_pdf_path(src)
        print(f"  PDF found: {pdf_path is not None}")
        if pdf_path:
            print(f"  Resolved : {pdf_path.relative_to(ROOT)}")

        rows, method, pdf_found = extract_from_pdf(src)
        if per_source_cap is not None and rows and len(rows) > per_source_cap:
            before = len(rows)
            rows = rows[:per_source_cap]
            print(f"  Records capped: {before} → {len(rows)} (max_records_per_source)")
        if not rows:
            print("  No records extracted for this PDF.")

        print(f"  Method   : {method}")
        print(f"  Records  : {len(rows)}")
        for row in rows[:3]:
            print(
                f"    + {row.get('record_id')}: {row.get('peptide_name')} "
                f"vs {row.get('pathogen_name')} MIC={row.get('measurement_value')}"
            )
        if len(rows) > 3:
            print(f"    ... and {len(rows) - 3} more")

        all_rows.extend(rows)
        append_log({
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "step": "pdf_extraction",
            "source_id": source_id,
            "status": "success" if rows else "empty",
            "method": method,
            "records_written": len(rows),
            "pdf_found": pdf_found,
            "output": manifest.get("output_records_file"),
            "doi": src.get("doi", ""),
        })

    if not all_rows:
        print("\nNo records found. Nothing written.")
        sys.exit(1)

    out_path = ROOT / manifest.get("output_records_file", OUTPUT_CSV.relative_to(ROOT).as_posix())
    write_extract_csv(all_rows, out_path, output_columns)
    print(f"\nWrote {len(all_rows)} records to {out_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
