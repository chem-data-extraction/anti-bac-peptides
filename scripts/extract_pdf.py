from __future__ import annotations

import csv
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
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


def parse_mic_value(raw: object) -> tuple[object, object, str]:
    """Assume reported concentration is µg-relevant scalar; verbatim token in measurement_value."""
    if raw is None or str(raw).strip() == "":
        return "", "", ""
    raw_mv = str(raw).strip()
    text = raw_mv.replace(",", ".").replace("−", "-")
    censored = text.startswith((">", "<"))
    prefix = ">" if text.startswith(">") else ("<" if text.startswith("<") else "")
    try:
        num = float(text.lstrip("><"))
    except ValueError:
        return raw_mv, raw_mv, ""
    if censored:
        return raw_mv, f"{prefix}{num}", f"censored bound {raw_mv}"
    return raw_mv, num, ""


def normalize_mic_to_ug_ml(
    value: object, unit: str, mw_da: float | None
) -> tuple[object, object, str]:
    """Derive comparable µg/mL when possible; measurement_value stays verbatim."""
    unit_l = str(unit or "ug/mL").strip().lower().replace("µ", "u").replace("μ", "u")
    notes = f"unit={unit_l}"
    if value is None or str(value).strip() == "":
        return "", "", notes

    raw_mv = str(value).strip()
    text = raw_mv.replace(",", ".").replace("−", "-")
    censored = text.startswith((">", "<"))
    prefix = ">" if text.startswith(">") else ("<" if text.startswith("<") else "")
    try:
        num = float(text.lstrip("><"))
    except ValueError:
        return raw_mv, raw_mv, notes

    norm: float | str
    if unit_l in ("ug/ml",):
        norm = round(num, 6)
    elif unit_l in ("mg/l",):
        norm = round(num, 6)
    elif unit_l in ("um", "u m") and mw_da:
        norm = round(num * float(mw_da) / 1000.0, 6)
    elif unit_l in ("um", "u m"):
        norm = round(num, 6) if not censored else f"{prefix}{num}"
    else:
        norm = round(num, 6) if not censored else f"{prefix}{num}"

    if censored:
        nv = f"{prefix}{norm}" if isinstance(norm, (int, float)) else str(norm)
        notes = f"{notes}; censored bound"
        return raw_mv, nv, notes

    return raw_mv, norm, notes


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

    pdf_dir = root / "data/raw/pdf"
    if pdf_dir.is_dir():
        for pdf_file in sorted(pdf_dir.glob("*.pdf")):
            candidates.append(pdf_file)

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

LUO_PEPTIDES = (
    "RP556", "LZ1", "AA139", "PA13", "Oligo10",
    "R1", "R10", "R11", "R12", "R13", "R14",
)
LUO_PATHOGENS = [
    ("Escherichia coli", "ATCC 25922", "Gram-negative"),
    ("Pseudomonas aeruginosa", "ATCC 27853", "Gram-negative"),
    ("Klebsiella pneumoniae", "ATCC 700603", "Gram-negative"),
    ("Enterococcus faecium", "ATCC 19434", "Gram-positive"),
    ("Staphylococcus aureus", "ATCC 25923", "Gram-positive"),
    ("Cutibacterium acnes", "ATCC 6919", "Gram-positive"),
]

KIM_PEPTIDES = [
    {
        "col_index": 0,
        "peptide_name": "H. cecropia cecropin A",
        "peptide_sequence": "KWKLFKKIEKVGQNIRDGIIKAGPAVAVVGQATQIAK",
        "molecular_weight_da": 4110.0,
        "organism_source": "Hyalophora cecropia",
    },
    {
        "col_index": 1,
        "peptide_name": "T. ni cecropin A",
        "peptide_sequence": "RWKFFKKIEKVGQNIRDGIIKAGPAVAVVGQAASITGK",
        "molecular_weight_da": 4240.0,
        "organism_source": "Trichoplusia ni",
    },
]

KIM_STRAIN_MAP = {
    "e. coli": ("Escherichia coli", "ATCC 25922", "Gram-negative"),
    "a. baumannii": ("Acinetobacter baumannii", "ATCC 19606", "Gram-negative"),
    "p. aeruginosa": ("Pseudomonas aeruginosa", "ATCC 27853", "Gram-negative"),
    "k. pneumoniae": ("Klebsiella pneumoniae", "ATCC 13883", "Gram-negative"),
    "colrec 1557": ("Escherichia coli", "ColREC 1557", "Gram-negative"),
    "colrec 12": ("Escherichia coli", "ColREC 12", "Gram-negative"),
    "colrab 1915": ("Acinetobacter baumannii", "ColRAB 1915", "Gram-negative"),
    "colrkp 139": ("Klebsiella pneumoniae", "ColRKP 139", "Gram-negative"),
}


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
        for page_num in pages_used:
            if 1 <= page_num <= len(pdf.pages):
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
        "measurement_type": "MIC",
        "assay_method": assay.get("assay_method", ""),
        "medium": assay.get("medium", ""),
        "medium_composition": assay.get("medium_composition", ""),
        "inoculum_cfu_ml": assay.get("inoculum_cfu_ml", ""),
        "temperature_c": assay.get("temperature_c", ""),
        "incubation_time_h": assay.get("incubation_time_h", ""),
        "extraction_method": "pdf_text",
        "extraction_confidence": "high",
        "organism_source": "synthetic",
        "synthesis_type": "synthetic",
    }


def parse_luo_text(text: str, source: dict) -> list[dict]:
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
        for (pname, strain, gram), raw_mic in zip(LUO_PATHOGENS, values):
            mv, nv, note = parse_mic_value(raw_mic)
            rows.append({
                **_base_row(source, source_id),
                "record_id": (
                    f"rec_{slugify(peptide_name)[:14]}_{slugify(strain)[:10]}"
                    f"_ramata2023_{len(rows) + 1:03d}"
                ),
                "peptide_name": peptide_name,
                "peptide_sequence": seq,
                "peptide_length": len(seq) if seq else "",
                "pathogen_name": pname,
                "pathogen_strain": strain,
                "gram_stain": gram,
                "measurement_value": mv,
                "normalized_value_ug_ml": nv,
                "notes": f"Ramata-Stunda et al. 2023 (Antibiotics) Table 2; unit=ug/mL; {note}".strip("; "),
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


def parse_wang_text(page_texts: dict[int, str], source: dict) -> list[dict]:
    source_id = source["source_id"]
    text_all = "\n".join(page_texts.values())
    peptides: dict[str, dict] = {}
    for m in re.finditer(
        r"^(W[1-5])\s+(W[RGS]+-NH2)\s+([\d.]+)\s+([\d.]+)",
        text_all,
        re.MULTILINE,
    ):
        seq = normalize_sequence(m.group(2).replace("-NH2", ""))
        peptides[m.group(1)] = {
            "sequence": seq,
            "mw": float(m.group(3)),
            "peptide_length": len(seq),
        }

    rows: list[dict] = []
    table_text = page_texts.get(5, "")
    for strain_label, pattern in [
        ("MRSA 544", r"^MRSA 544\s+(.+)$"),
        ("MRSA 103", r"^MRSA 103\s+(.+)$"),
    ]:
        block = re.search(pattern, table_text, re.MULTILINE)
        if not block:
            continue
        tokens = _parse_mic_tokens(block.group(1))
        for pep_name, raw_mic in zip(["W1", "W2", "W3", "W4", "W5"], tokens[:5]):
            meta = peptides.get(pep_name, {})
            mw = meta.get("mw")
            mv, nv, note = normalize_mic_to_ug_ml(raw_mic, "uM", mw)
            rows.append({
                **_base_row(source, source_id),
                "record_id": (
                    f"rec_{pep_name.lower()}_{slugify(strain_label)[:12]}"
                    f"_zhang2024_{len(rows) + 1:03d}"
                ),
                "peptide_name": pep_name,
                "peptide_sequence": meta.get("sequence", ""),
                "peptide_length": meta.get("peptide_length", ""),
                "molecular_weight_da": mw or "",
                "peptide_modifications": "C-terminal amide",
                "pathogen_name": "Staphylococcus aureus",
                "pathogen_strain": strain_label,
                "gram_stain": "Gram-positive",
                "measurement_value": mv,
                "normalized_value_ug_ml": nv,
                "notes": f"Zhang 2024 Table 2; unit=uM; {note}".strip("; "),
            })
    return rows


def parse_kim_text(page_texts: dict[int, str], source: dict) -> list[dict]:
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
        if org_key not in KIM_STRAIN_MAP or len(vals) < 2:
            continue
        pname, strain, gram = KIM_STRAIN_MAP[org_key]
        for pep_info, raw_mic in zip(KIM_PEPTIDES, vals[:2]):
            if raw_mic.startswith(">"):
                mv, nv, note = raw_mic, raw_mic, "censored bound"
            else:
                mv, nv, note = normalize_mic_to_ug_ml(
                    raw_mic, "uM", pep_info["molecular_weight_da"]
                )
            rows.append({
                **_base_row(source, source_id),
                "record_id": (
                    f"rec_{slugify(pep_info['peptide_name'])[:12]}_{slugify(strain)[:10]}"
                    f"_lee2023_{len(rows) + 1:03d}"
                ),
                "peptide_name": pep_info["peptide_name"],
                "peptide_sequence": pep_info["peptide_sequence"],
                "peptide_length": len(pep_info["peptide_sequence"]),
                "molecular_weight_da": pep_info["molecular_weight_da"],
                "organism_source": pep_info["organism_source"],
                "peptide_modifications": "C-terminal amide",
                "pathogen_name": pname,
                "pathogen_strain": strain,
                "gram_stain": gram,
                "measurement_value": mv,
                "normalized_value_ug_ml": nv,
                "notes": f"Lee et al. 2023 (Pharmaceutics) Table 1; unit=uM; {note}".strip("; "),
            })
    return rows


TEXT_PARSERS: dict[str, Callable[[dict[int, str], dict], list[dict]]] = {
    "paper_ramata_stunda_2023": lambda texts, src: parse_luo_text("\n".join(texts.values()), src),
    "paper_zhang_2024": parse_wang_text,
    "paper_lee_2023": parse_kim_text,
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
    print(f"Output columns: {len(output_columns)}")

    for src in manifest.get("input_sources", []):
        source_id = src["source_id"]
        pdf_path = resolve_pdf_path(src)
        print(f"\n[{source_id}]")
        print(f"  PDF found: {pdf_path is not None}")
        if pdf_path:
            print(f"  Resolved : {pdf_path.relative_to(ROOT)}")

        rows, method, pdf_found = extract_from_pdf(src)
        if not rows:
            print("  No records extracted for this PDF.")

        print(f"  Method   : {method}")
        print(f"  Records  : {len(rows)}")
        for row in rows[:3]:
            print(
                f"    + {row.get('record_id')}: {row.get('peptide_name')} "
                f"vs {row.get('pathogen_name')} MIC={row.get('normalized_value_ug_ml')}"
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
