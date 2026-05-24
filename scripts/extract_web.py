from __future__ import annotations

import csv
import io
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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


def normalize_mic_to_ug_ml(
    value: object, unit: str, mw_da: float | None
) -> tuple[object, object, str]:
    """Derive comparable µg/mL when possible; measurement_value stays the verbatim concentration string."""
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


MANIFEST = ROOT / "specs/web_extraction_manifest.json"
OUTPUT_CSV = ROOT / "data/extracted/web_extracted_records.csv"
LOG_PATH = ROOT / "data/extracted/extraction_log.jsonl"

DBAASP_PEPTIDES_URL = "https://dbaasp.org/peptides"
RATE_LIMIT_S = 1.0
XLSX_MAGIC = b"PK\x03\x04"

NON_BACTERIAL = (
    "candida", "fungus", "fungal", "virus", "viral", "mammalian",
    "erythrocyte", "human", "mouse", "cancer", "tumor", "hela",
)


def is_bacterial_target(species_name: str) -> bool:
    lower = species_name.lower()
    return not any(x in lower for x in NON_BACTERIAL)


DRAMP_MIC_PATTERN = re.compile(
    r"\(MIC[=<>≤]?\s*([\d.>]+)\s*([μuµ]?g/ml|[μuµ]?M|mg/L|pmol/ml|nM)?\)",
    re.IGNORECASE,
)


def _pathogen_before_mic(text: str, mic_start: int) -> str:
    chunk = text[:mic_start]
    sep = max(chunk.rfind(","), chunk.rfind(";"))
    segment = chunk[sep + 1 :].strip()
    while segment.endswith(")"):
        open_idx = segment.rfind("(")
        if open_idx == -1:
            break
        segment = segment[:open_idx].strip()
    if ":" in segment and segment.index(":") < 40:
        segment = segment.split(":", 1)[1].strip()
    return segment


def append_log(entry: dict) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def save_snapshot(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _try_import(name: str) -> Any | None:
    try:
        import importlib
        return importlib.import_module(name)
    except ImportError:
        return None




def split_pathogen_strain(species_reported: str) -> tuple[str, str]:
    """Split species phrase and trailing catalogue designation (e.g. ATCC …)."""
    s = species_reported.strip()
    if not s:
        return "", ""
    m = re.search(
        r"^(.*?)\s+((?:ATCC|DSMZ|CCUG|NCTC)\s*(?:#\s*)?[\w./\-]+)\s*$",
        s,
        re.IGNORECASE,
    )
    if m:
        base, strain = m.group(1).strip(), m.group(2).strip()
        return (base, strain) if base else (strain, "")
    return s, ""


def compose_medium_composition(act: dict, medium_obj: dict) -> str:
    """Medium details exposed by DBAASP (description, pH, salts, curator note)."""
    parts: list[str] = []
    if isinstance(medium_obj, dict):
        desc = str(medium_obj.get("description") or "").strip()
        if desc:
            parts.append(desc)
    ph = str(act.get("ph") or "").strip()
    if ph:
        parts.append(f"pH {ph}")
    ion = str(act.get("ionicStrength") or "").strip()
    if ion:
        parts.append(f"ionic strength {ion}")
    salt = str(act.get("saltType") or "").strip()
    if salt:
        parts.append(salt)
    note = str(act.get("note") or "").strip()
    if note:
        parts.append(note)
    return "; ".join(parts)


def format_inoculum_cfu(act: dict) -> str:
    parts: list[str] = []
    raw = act.get("cfu")
    if str(raw).strip():
        parts.append(str(raw).strip())
    grp = act.get("cfuGroup") or {}
    gname = grp.get("name", "") if isinstance(grp, dict) else ""
    if str(gname).strip():
        parts.append(f"cfu_range={str(gname).strip()}")
    return "; ".join(parts)


def parse_dbaasp_card(card: dict, source_id: str, source_url: str, idx_start: int) -> list[dict]:
    seq = normalize_sequence(card.get("sequence", ""))
    name = card.get("name") or card.get("majorName") or card.get("dbaaspId") or ""
    length = card.get("sequenceLength", len(seq) if seq else "")
    mw = card.get("molecularWeight") or card.get("mw")
    try:
        mw_f = float(mw) if mw not in (None, "") else None
    except (TypeError, ValueError):
        mw_f = None

    synthesis = ""
    st = card.get("synthesisType")
    if isinstance(st, dict):
        synthesis = st.get("name", "")
    elif st:
        synthesis = str(st)

    organism = ""
    genes = card.get("sourceGenes") or []
    if genes and isinstance(genes[0], dict):
        organism = genes[0].get("source", "")

    rows: list[dict] = []
    for act in card.get("targetActivities") or []:
        measure = act.get("activityMeasureValue") or ""
        group = act.get("activityMeasureGroup") or {}
        group_name = group.get("name", "") if isinstance(group, dict) else ""
        if "MIC" not in str(measure).upper() and "MIC" not in str(group_name).upper():
            continue

        species = act.get("targetSpecies") or {}
        pathogen = species.get("name", "") if isinstance(species, dict) else str(species)
        if not pathogen or not is_bacterial_target(pathogen):
            continue

        pathogen_name, strain = split_pathogen_strain(pathogen)

        unit_obj = act.get("unit") or {}
        unit = unit_obj.get("name", "ug/mL") if isinstance(unit_obj, dict) else str(unit_obj or "ug/mL")
        raw_value = act.get("concentration", "")
        if str(raw_value).upper() in ("NA", "N/A", "-", ""):
            continue

        mv, nv, note = normalize_mic_to_ug_ml(raw_value, unit, mw_f)
        medium_obj = act.get("medium") or {}
        medium = medium_obj.get("name", "") if isinstance(medium_obj, dict) else ""

        medi_compose = compose_medium_composition(act, medium_obj)

        slug_path = slugify(pathogen_name.split()[0])[:6] if pathogen_name else "unk"

        idx = idx_start + len(rows) + 1
        rows.append({
            "record_id": (
                f"rec_{slugify(str(name))[:12]}_{slug_path}"
                f"_{source_id[:6]}_{idx:03d}"
            ),
            "peptide_sequence": seq,
            "peptide_length": length,
            "molecular_weight_da": mw_f or "",
            "peptide_name": name,
            "organism_source": organism,
            "synthesis_type": synthesis.lower() if synthesis else "",
            "peptide_modifications": "",
            "pathogen_name": pathogen_name,
            "pathogen_strain": strain,
            "gram_stain": "",
            "measurement_type": "MIC",
            "measurement_value": mv,
            "normalized_value_ug_ml": nv,
            "assay_method": "",
            "medium": medium,
            "medium_composition": medi_compose,
            "inoculum_cfu_ml": format_inoculum_cfu(act),
            "temperature_c": "",
            "incubation_time_h": "",
            "source_id": source_id,
            "source_type": "database",
            "publication_year": "",
            "source_url": source_url,
            "doi": "",
            "extraction_method": "web_api",
            "extraction_confidence": "high",
            "notes": f"DBAASP /peptides/{{id}}; dbaaspId={card.get('dbaaspId', '')}; {note}".strip("; "),
        })
    return rows


def fetch_dbaasp(page: dict, max_records: int) -> tuple[list[dict], str]:
    requests = _try_import("requests")
    if requests is None:
        print("  [DBAASP] requests not installed — skipping.")
        return [], "missing_dependency"

    snap_path = ROOT / page["raw_snapshot_path"]
    source_id = page["source_id"]
    source_url = page.get("url", DBAASP_PEPTIDES_URL)
    headers = {"Accept": "application/json", "User-Agent": "AMP-MIC-Dataset/1.0 (academic)"}

    rows: list[dict] = []
    snapshot_pages: list[dict] = []
    page_num = 0
    page_size = 50

    while len(rows) < max_records and page_num < 40:
        print(f"  [DBAASP] GET /peptides?page={page_num}&size={page_size}")
        time.sleep(RATE_LIMIT_S)
        try:
            resp = requests.get(
                DBAASP_PEPTIDES_URL,
                params={"page": page_num, "size": page_size, "format": "json"},
                headers=headers,
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            print(f"  [DBAASP] List error on page {page_num}: {exc}")
            break

        snapshot_pages.append({"page": page_num, "totalCount": data.get("totalCount"), "count": len(data.get("data", []))})
        peptides = data.get("data") or []
        if not peptides:
            break

        for summary in peptides:
            if len(rows) >= max_records:
                break
            pid = summary.get("id")
            complexity = summary.get("complexity") or {}
            cname = complexity.get("name", "") if isinstance(complexity, dict) else ""
            if cname and cname.lower() != "monomer":
                continue
            if not pid:
                continue

            time.sleep(RATE_LIMIT_S)
            try:
                card_resp = requests.get(
                    f"{DBAASP_PEPTIDES_URL}/{pid}",
                    params={"format": "json"},
                    headers=headers,
                    timeout=60,
                )
                card_resp.raise_for_status()
                card = card_resp.json()
            except Exception as exc:
                print(f"  [DBAASP] Card {pid} error: {exc}")
                continue

            if not card.get("sequence"):
                continue

            parsed = parse_dbaasp_card(card, source_id, source_url, len(rows))
            rows.extend(parsed)
            if len(rows) >= max_records:
                rows = rows[:max_records]
                break

        page_num += 1

    save_snapshot(snap_path, json.dumps(snapshot_pages, ensure_ascii=False).encode("utf-8"))
    print(f"  [DBAASP] Parsed {len(rows)} MIC record(s); snapshot: {snap_path.relative_to(ROOT)}")
    return rows, "web_api"


def is_valid_xlsx(raw_bytes: bytes) -> bool:
    return len(raw_bytes) > 1000 and raw_bytes.startswith(XLSX_MAGIC)


def parse_dramp_target_field(
    target_field: str,
    row_data: Any,
    source_id: str,
    idx_start: int,
) -> list[dict]:
    rows: list[dict] = []
    seq = normalize_sequence(row_data.get("Sequence", ""))
    name = str(row_data.get("Name", "")).strip()
    organism = str(row_data.get("Source", "")).strip()

    for m in DRAMP_MIC_PATTERN.finditer(str(target_field)):
        pathogen_raw = _pathogen_before_mic(str(target_field), m.start())
        if not pathogen_raw or not is_bacterial_target(pathogen_raw):
            continue
        raw_mic = m.group(1)
        unit = m.group(2) or "ug/mL"
        mv, nv, note = normalize_mic_to_ug_ml(raw_mic, unit, None)
        pathogen_slug = slugify(pathogen_raw.split()[0])[:6] or "unk"
        idx = idx_start + len(rows) + 1
        rows.append({
            "record_id": (
                f"rec_{slugify(name or 'pep')[:12]}_{pathogen_slug}"
                f"_{source_id[:5]}_{idx:03d}"
            ),
            "peptide_sequence": seq,
            "peptide_length": len(seq) if seq else row_data.get("Sequence_Length", ""),
            "molecular_weight_da": "",
            "peptide_name": name,
            "organism_source": organism,
            "synthesis_type": "",
            "peptide_modifications": "",
            "pathogen_name": pathogen_raw.split("(")[0].strip(),
            "pathogen_strain": "",
            "gram_stain": "",
            "measurement_type": "MIC",
            "measurement_value": mv,
            "normalized_value_ug_ml": nv,
            "assay_method": "",
            "medium": "",
            "medium_composition": "",
            "inoculum_cfu_ml": "",
            "temperature_c": "",
            "incubation_time_h": "",
            "source_id": source_id,
            "source_type": "database",
            "publication_year": "",
            "source_url": "",
            "doi": str(row_data.get("Pubmed_ID", "") or ""),
            "extraction_method": "bulk_download_excel",
            "extraction_confidence": "medium",
            "notes": f"DRAMP {row_data.get('DRAMP_ID', '')}; {note}".strip("; "),
        })
    return rows


def fetch_dramp(page: dict, max_records: int) -> tuple[list[dict], str]:
    requests = _try_import("requests")
    pandas = _try_import("pandas")
    if requests is None or pandas is None:
        missing = ", ".join(n for n, m in [("requests", requests), ("pandas", pandas)] if m is None)
        print(f"  [DRAMP] Missing: {missing} — skipping.")
        return [], "missing_dependency"

    download_url = page.get("download_url", "")
    snap_path = ROOT / page["raw_snapshot_path"]
    source_id = page["source_id"]
    source_url = page.get("url", "")

    raw_bytes = b""
    if snap_path.is_file() and is_valid_xlsx(snap_path.read_bytes()):
        print(f"  [DRAMP] Using cached snapshot: {snap_path.relative_to(ROOT)}")
        raw_bytes = snap_path.read_bytes()
    else:
        if snap_path.is_file():
            print(f"  [DRAMP] Invalid cache — re-downloading from {download_url}")
        else:
            print(f"  [DRAMP] Downloading: {download_url}")
        time.sleep(RATE_LIMIT_S)
        try:
            resp = requests.get(
                download_url,
                timeout=120,
                headers={"User-Agent": "AMP-MIC-Dataset/1.0"},
            )
            resp.raise_for_status()
            raw_bytes = resp.content
            if not is_valid_xlsx(raw_bytes):
                raise ValueError(f"Not a valid xlsx ({len(raw_bytes)} bytes)")
            save_snapshot(snap_path, raw_bytes)
            print(f"  [DRAMP] Saved {len(raw_bytes)} bytes to {snap_path.relative_to(ROOT)}")
        except Exception as exc:
            print(f"  [DRAMP] Download error: {exc}")
            return [], "download_error"

    try:
        df = pandas.read_excel(io.BytesIO(raw_bytes), engine="openpyxl")
    except Exception as exc:
        print(f"  [DRAMP] Parse error: {exc}")
        return [], "parse_error"

    print(f"  [DRAMP] Loaded {len(df)} rows")
    rows: list[dict] = []
    for _, row_data in df.iterrows():
        if len(rows) >= max_records:
            break
        target_field = row_data.get("Target_Organism", "")
        if pandas.isna(target_field) or "MIC" not in str(target_field).upper():
            continue
        try:
            parsed = parse_dramp_target_field(str(target_field), row_data, source_id, len(rows))
        except Exception as exc:
            print(f"  [DRAMP] Row parse error: {exc}")
            continue
        for rec in parsed:
            if len(rows) >= max_records:
                break
            rows.append(rec)

    print(f"  [DRAMP] Parsed {len(rows)} MIC record(s).")
    return rows, "bulk_download_excel"


FETCHERS = {
    "db_dbaasp": fetch_dbaasp,
    "db_dramp": fetch_dramp,
}


def main() -> None:
    with MANIFEST.open(encoding="utf-8") as f:
        manifest = json.load(f)

    output_columns = load_output_columns(manifest)
    max_records = int(manifest.get("max_records_per_source", 200))
    print(f"Web extraction v{manifest.get('web_extraction_version')}")
    print(f"Max records per source: {max_records}")
    print(f"Output columns: {len(output_columns)}")

    all_rows: list[dict] = []

    for page in manifest.get("input_pages", []):
        source_id = page["source_id"]
        print(f"\n[{source_id}] {page.get('page_id', '')}")

        fetcher = FETCHERS.get(source_id)
        rows: list[dict] = []
        method = "unknown_source"
        if fetcher:
            try:
                rows, method = fetcher(page, max_records)
            except Exception as exc:
                print(f"  ERROR: {exc}")
                method = "error"

        if not rows:
            print("  No records extracted for this source.")

        print(f"  Method: {method}; records: {len(rows)}")
        for r in rows[:3]:
            print(f"    + {r.get('record_id')}: {r.get('peptide_name')} vs {r.get('pathogen_name')}")
        if len(rows) > 3:
            print(f"    ... and {len(rows) - 3} more")

        all_rows.extend(rows)
        append_log({
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "step": "web_extraction",
            "source_id": source_id,
            "status": "success" if rows else "empty",
            "method": method,
            "records_written": len(rows),
            "snapshot": page.get("raw_snapshot_path", ""),
            "output": manifest.get("output_records_file"),
        })
        time.sleep(RATE_LIMIT_S)

    if not all_rows:
        print("\nNo records collected. Nothing written.")
        sys.exit(1)

    out_path = ROOT / manifest.get("output_records_file", OUTPUT_CSV.relative_to(ROOT).as_posix())
    write_extract_csv(all_rows, out_path, output_columns)
    print(f"\nWrote {len(all_rows)} records to {out_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
