from __future__ import annotations

import csv
import json
import re
import sys
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from utils import (
    canonical_measurement_unit,
    pathogen_contains_nonbacterial_hint,
    unit_context_note,
    verbatim_measurement_value,
)

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


def effective_record_cap(page: dict, global_default: int) -> int | None:
    """Per-source record ceiling; None = no cap within fetcher safeguards."""
    if "max_records" in page:
        v = page["max_records"]
        if v is None:
            return None
        if isinstance(v, str) and v.lower() in {"unlimited", "none"}:
            return None
        return int(v)
    return int(global_default)


MANIFEST = ROOT / "specs/web_extraction_manifest.json"
OUTPUT_CSV = ROOT / "data/extracted/web_extracted_records.csv"
LOG_PATH = ROOT / "data/extracted/extraction_log.jsonl"

DBAASP_PEPTIDES_URL = "https://dbaasp.org/peptides"
DBAASP_PEPTIDE_PAGE_BASE = "https://dbaasp.org/peptide"
RATE_LIMIT_S = 1.0

STRAIN_CATALOGUE_PREFIXES = (
    "ATCC",
    "DSMZ",
    "CCUG",
    "NCTC",
    "NCIMB",
    "KCTC",
    "CIP",
    "CECT",
    "LMG",
    "JCM",
    "BAA",
    "MRSA",
    "VRE",
    "ESBL",
    "MDR",
    "CRKP",
    "CRE",
    "KPC",
    "PAO1",
)
_STRAIN_PREFIX_GROUP = "|".join(STRAIN_CATALOGUE_PREFIXES)


def is_bacterial_target(species_name: str) -> bool:
    return not pathogen_contains_nonbacterial_hint(species_name)


def pubmed_url(pmid: object) -> str:
    digits = re.sub(r"\D", "", str(pmid or "").strip())
    return f"https://pubmed.ncbi.nlm.nih.gov/{digits}/" if digits else ""


def extract_year_from_reference(reference: object) -> str:
    match = re.search(r"\b(19|20)\d{2}\b", str(reference or ""))
    return match.group(0) if match else ""


def extract_doi_from_text(text: object) -> str:
    match = re.search(r"10\.\d{4,9}/[^\s,;)]+", str(text or ""))
    return match.group(0).rstrip(".") if match else ""


def dbaasp_card_source_url(card: dict) -> str:
    token = card.get("dbaaspId") or card.get("id") or ""
    if token:
        return f"{DBAASP_PEPTIDE_PAGE_BASE}/{token}"
    return DBAASP_PEPTIDES_URL


def index_dbaasp_articles(articles: list[dict] | None) -> dict[str, dict]:
    """Map DBAASP article ``id`` strings to article dicts."""
    indexed: dict[str, dict] = {}
    for article in articles or []:
        if isinstance(article, dict) and article.get("id") is not None:
            indexed[str(article["id"])] = article
    return indexed


def resolve_activity_publication(
    act: dict, articles: list[dict] | None, articles_by_id: dict[str, dict]
) -> tuple[str, str]:
    """Return (publication_year, pubmed_id) for one DBAASP targetActivity.

    ``targetActivities[].reference`` is a **1-based index** into ``articles[]``,
    not the article ``id`` field (e.g. reference ``"1"`` → ``articles[0]``).
    """
    article_list = [a for a in (articles or []) if isinstance(a, dict)]
    ref_raw = act.get("reference")
    article: dict | None = None

    if ref_raw not in (None, ""):
        ref_text = str(ref_raw).strip()
        try:
            ref_idx = int(ref_text)
            if 1 <= ref_idx <= len(article_list):
                article = article_list[ref_idx - 1]
        except (TypeError, ValueError):
            article = articles_by_id.get(ref_text)

    if not article:
        return "", ""

    year_raw = article.get("year")
    publication_year = ""
    if year_raw not in (None, ""):
        try:
            publication_year = str(int(year_raw))
        except (TypeError, ValueError):
            publication_year = str(year_raw).strip()

    pubmed_obj = article.get("pubmed") or {}
    pmid = ""
    if isinstance(pubmed_obj, dict):
        pmid = str(pubmed_obj.get("pubmedId") or "").strip()
    return publication_year, pmid


def dbaasp_card_is_monomer(card: dict) -> bool:
    complexity = card.get("complexity") or {}
    cname = complexity.get("name", "") if isinstance(complexity, dict) else str(complexity or "")
    return not cname or cname.lower() == "monomer"


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
    """Split species phrase and trailing catalogue designation (e.g. ATCC …).

    Also handles DRAMP-specific patterns:
    - Codes like L\\d+ and L-\\d+ (e.g. ``L287``, ``L-8``)
    - Resistance phenotype tags (e.g. ``MRSA``, ``VRE``, ``ESBL``)
    - Gram-stain markers embedded in text (e.g. ``##Gram-positive``)
    """
    s = species_reported.strip()
    if not s:
        return "", ""

    # Strip DRAMP-style Gram-stain markers (##Gram-positive / ##Gram-negative)
    s = re.sub(r"##\s*Gram[- ](positive|negative)\b", "", s, flags=re.IGNORECASE).strip()

    # Split on known catalogue / strain designation prefixes (ATCC, KCTC, PAO1, …).
    catalogue_re = (
        rf"^(.*?)\s+((?:{_STRAIN_PREFIX_GROUP})\s*(?:#\s*)?[\w./\-]+)\s*$"
    )
    m = re.search(catalogue_re, s, re.IGNORECASE)
    if m:
        base, strain = m.group(1).strip(), m.group(2).strip()
        return (base, strain) if base else (strain, "")

    # Standalone PAO1 without catalogue number suffix.
    m_pao1 = re.search(r"^(.*?)\s+(PAO1)\s*$", s, re.IGNORECASE)
    if m_pao1:
        base, strain = m_pao1.group(1).strip(), m_pao1.group(2).strip()
        if base:
            return base, strain

    # DRAMP laboratory code pattern: word ending with L\d+ or L-\d+ (e.g. ``Escherichia coli L287``)
    m2 = re.search(
        r"^(.*?)\s+(L-?\d+(?:\s*\w+)*)\s*$",
        s,
        re.IGNORECASE,
    )
    if m2:
        base2, strain2 = m2.group(1).strip(), m2.group(2).strip()
        if base2:
            return base2, strain2

    return s, ""


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
    peptide_page_url = dbaasp_card_source_url(card)
    articles_by_id = index_dbaasp_articles(card.get("articles"))

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
        meas_unit_out = canonical_measurement_unit(unit)
        raw_value = act.get("concentration", "")
        if str(raw_value).upper() in ("NA", "N/A", "-", ""):
            continue

        mv = verbatim_measurement_value(raw_value)
        if not mv:
            continue

        medium_obj = act.get("medium") or {}
        medium = medium_obj.get("name", "") if isinstance(medium_obj, dict) else ""

        slug_path = (
            slugify(pathogen_name.split()[0])[:6] if pathogen_name else "unk"
        )

        idx = idx_start + len(rows) + 1
        una = unit_context_note(unit)
        publication_year, pmid = resolve_activity_publication(
            act, card.get("articles"), articles_by_id
        )
        row_source_url = pubmed_url(pmid) or peptide_page_url or source_url
        note_parts = [
            f"DBAASP peptide card; dbaaspId={card.get('dbaaspId', '')}",
            f"PMID={pmid}" if pmid else "",
            una,
        ]
        rows.append({
            "record_id": (
                f"rec_{slugify(str(name))[:12]}_{slug_path}"
                f"_{source_id[:6]}_{idx:03d}"
            ),
            "peptide_sequence": seq,
            "peptide_name": name,
            "organism_source": organism,
            "pathogen_name": pathogen_name,
            "pathogen_strain": strain,
            "measurement_value": mv,
            "measurement_unit": meas_unit_out,
            "assay_method": "",
            "medium": medium,
            "inoculum_cfu_ml": format_inoculum_cfu(act),
            "temperature_c": "",
            "incubation_time_h": "",
            "source_id": source_id,
            "source_type": "database",
            "publication_year": publication_year,
            "source_url": row_source_url,
            "doi": "",
            "extraction_method": "web_api",
            "extraction_confidence": "high",
            "notes": "; ".join(part for part in note_parts if part),
        })
    return rows


def _dbaasp_probe_total_count(requests: Any, headers: dict[str, str]) -> int:
    resp = requests.get(
        DBAASP_PEPTIDES_URL,
        params={"page": 0, "size": 1, "format": "json"},
        headers=headers,
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    try:
        return max(0, int(data.get("totalCount") or 0))
    except (TypeError, ValueError):
        return 0


def _dbaasp_fetch_card(requests: Any, pid: int, headers: dict[str, str]) -> dict | None:
    try:
        card_resp = requests.get(
            f"{DBAASP_PEPTIDES_URL}/{pid}",
            params={"format": "json"},
            headers=headers,
            timeout=60,
        )
        if card_resp.status_code == 400:
            return None
        card_resp.raise_for_status()
        card = card_resp.json()
    except Exception as exc:
        print(f"  [DBAASP] Card {pid} error: {exc}")
        return None
    return card if isinstance(card, dict) else None


def _fetch_dbaasp_by_id_walk(
    page: dict,
    record_cap: int | None,
    requests: Any,
    headers: dict[str, str],
    source_id: str,
) -> tuple[list[dict], list[dict]]:
    """Walk numeric peptide IDs — list pagination on dbaasp.org returns duplicate pages."""
    id_start_raw = page.get("dbaasp_id_start", 1)
    try:
        id_start = max(1, int(id_start_raw))
    except (TypeError, ValueError):
        id_start = 1

    id_end_raw = page.get("dbaasp_max_peptide_id")
    if id_end_raw is None:
        print("  [DBAASP] Probing totalCount for ID walk upper bound …")
        time.sleep(RATE_LIMIT_S)
        id_end = _dbaasp_probe_total_count(requests, headers)
    else:
        try:
            id_end = max(id_start, int(id_end_raw))
        except (TypeError, ValueError):
            id_end = _dbaasp_probe_total_count(requests, headers)

    if id_end <= 0:
        id_end = 25069

    fallback_url = page.get("url", DBAASP_PEPTIDES_URL)
    rows: list[dict] = []
    snapshot: list[dict] = [{
        "ingest_mode": "id_walk",
        "id_start": id_start,
        "id_end": id_end,
        "ids_attempted": 0,
        "cards_fetched": 0,
        "cards_with_sequence": 0,
        "rows_written": 0,
    }]

    print(f"  [DBAASP] ID walk {id_start}…{id_end} (cap={record_cap if record_cap is not None else 'unlimited'})")

    for pid in range(id_start, id_end + 1):
        if record_cap is not None and len(rows) >= record_cap:
            rows = rows[:record_cap]
            break

        snapshot[0]["ids_attempted"] = int(snapshot[0]["ids_attempted"]) + 1
        if pid == id_start or pid % 500 == 0:
            print(f"  [DBAASP] ID {pid}/{id_end} … rows so far: {len(rows)}")

        time.sleep(RATE_LIMIT_S)
        card = _dbaasp_fetch_card(requests, pid, headers)
        if not card:
            continue

        snapshot[0]["cards_fetched"] = int(snapshot[0]["cards_fetched"]) + 1
        if not dbaasp_card_is_monomer(card):
            continue
        if not card.get("sequence"):
            continue

        snapshot[0]["cards_with_sequence"] = int(snapshot[0]["cards_with_sequence"]) + 1
        parsed = parse_dbaasp_card(card, source_id, fallback_url, len(rows))
        rows.extend(parsed)
        snapshot[0]["rows_written"] = len(rows)

    return rows, snapshot


def _fetch_dbaasp_by_list_pages(
    page: dict,
    record_cap: int | None,
    requests: Any,
    headers: dict[str, str],
    source_id: str,
) -> tuple[list[dict], list[dict]]:
    """Legacy list pagination (known broken on dbaasp.org — kept for manifest compatibility)."""
    fallback_url = page.get("url", DBAASP_PEPTIDES_URL)
    rows: list[dict] = []
    seen_pids: set[int] = set()
    snapshot_pages: list[dict] = []
    page_num = 0
    page_size = 50

    max_pages_raw = page.get("dbaasp_max_list_pages", 260)
    try:
        max_pages = max(1, int(max_pages_raw))
    except (TypeError, ValueError):
        max_pages = 260

    while True:
        if page_num >= max_pages:
            break
        if record_cap is not None and len(rows) >= record_cap:
            break

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

        snapshot_pages.append({
            "ingest_mode": "list_pages",
            "page": page_num,
            "totalCount": data.get("totalCount"),
            "count": len(data.get("data", [])),
        })
        peptides = data.get("data") or []
        if not peptides:
            break

        for summary in peptides:
            if record_cap is not None and len(rows) >= record_cap:
                break
            pid = summary.get("id")
            if not dbaasp_card_is_monomer(summary):
                continue
            if not pid or pid in seen_pids:
                continue
            seen_pids.add(pid)

            card = _dbaasp_fetch_card(requests, int(pid), headers)
            if not card or not card.get("sequence"):
                continue

            parsed = parse_dbaasp_card(card, source_id, fallback_url, len(rows))
            rows.extend(parsed)
            if record_cap is not None and len(rows) >= record_cap:
                rows = rows[:record_cap]
                break

        if record_cap is not None and len(rows) >= record_cap:
            break
        page_num += 1

    return rows, snapshot_pages


def fetch_dbaasp(page: dict, record_cap: int | None) -> tuple[list[dict], str]:
    requests = _try_import("requests")
    if requests is None:
        print("  [DBAASP] requests not installed — skipping.")
        return [], "missing_dependency"

    snap_path = ROOT / page["raw_snapshot_path"]
    source_id = page["source_id"]
    headers = {"Accept": "application/json", "User-Agent": "AMP-MIC-Dataset/1.0 (academic)"}

    ingest_mode = str(page.get("dbaasp_ingest_mode", "id_walk")).strip().lower()
    if ingest_mode == "list_pages":
        rows, snapshot = _fetch_dbaasp_by_list_pages(page, record_cap, requests, headers, source_id)
    else:
        rows, snapshot = _fetch_dbaasp_by_id_walk(page, record_cap, requests, headers, source_id)

    save_snapshot(snap_path, json.dumps(snapshot, ensure_ascii=False).encode("utf-8"))
    print(f"  [DBAASP] Parsed {len(rows)} MIC record(s); snapshot: {snap_path.relative_to(ROOT)}")
    return rows, "web_api"


# --- DRAMP: Antimicrobial workbook (`Antimicrobial.xlsx`; upstream Antimicrobial_amps); Target_Organism `(MIC …)` ---
MIC_IN_PARENS = re.compile(r"\(\s*MIC\b\s*([^)]+)\)", re.IGNORECASE)

def _split_mic_numeric_and_unit(fragment: str) -> tuple[str, str]:
    """Split DRAMP/CAMP inner MIC text into value + compound unit suffix."""
    frag = unicodedata.normalize("NFKC", fragment or "").strip()
    frag = frag.lstrip("=").strip().replace(",", ".")
    frag = (
        frag.replace("microgram/ml", "µg/ml")
        .replace("micrograms/ml", "µg/ml")
        .replace("microg/ml", "µg/ml")
    )
    # Optional comparison symbol fused to digits: ≤13μg/ml
    m_space = re.match(
        r"^([≤≥=<>]?)\s*([\d.]+\s*(?:/\s+|[-−–]\s*[\d.]*)?)\s+(.+)$",
        frag,
    )
    if m_space:
        sym, nums, tail = m_space.group(1), m_space.group(2), m_space.group(3)
        val = verbatim_measurement_value(sym + nums.replace(" ", ""))
        return val.strip() if isinstance(val, str) else "", tail.strip()

    m_tight = re.match(
        r"^([≤≥=<>]?)([\d.]+(?:/[\d.]+|[-−–][\d.]+)?)([^\d][^\s]*)$",
        frag,
    )
    if m_tight:
        sym2, nums2, trailing = m_tight.group(1), m_tight.group(2), (m_tight.group(3) or "").lstrip("/")
        val2 = verbatim_measurement_value(sym2 + nums2.replace(" ", ""))
        combined_unit = trailing.strip()
        return (val2 or "").strip(), combined_unit

    return "", ""


def _dramp_mic_inner_to_value_unit(inner_raw: str) -> tuple[str, str]:
    """Return (verbatim_measurement_value, unit_raw_hint) from DRAMP `(MIC …)` payload."""
    vv, unit_raw_hint = _split_mic_numeric_and_unit(inner_raw)
    if not vv:
        return "", ""
    unit_raw_hint = unicodedata.normalize("NFKC", unit_raw_hint)
    unit_compact = re.sub(r"\s+", "", unit_raw_hint) if unit_raw_hint else ""
    return vv, unit_compact


def organism_before_mic_paren(text_full: str, mic_open_idx: int) -> str:
    """Best-effort pathogen substring before ``(MIC …)`` from a comma-/semicolon-heavy field.

    DRAMP-specific cleaning applied to candidate fragment:
    - Strips laboratory code prefixes that are not organism names (e.g. ``L287``, ``L-8``).
    - Strips ``##Gram-positive`` / ``##Gram-negative`` markers embedded in the text.
    """
    pre = text_full[:mic_open_idx].rstrip(",; ")
    cand = ""
    for sep in (",", ";", ":"):
        j = pre.rfind(sep)
        if j != -1:
            fragment = pre[j + 1 :].strip(",; ")
            if fragment:
                cand = fragment
                break
    if not cand:
        cand = pre.strip(",; ")

    # Strip DRAMP Gram-stain markers
    cand = re.sub(r"##\s*Gram[- ](positive|negative)\b", "", cand, flags=re.IGNORECASE).strip(",; ")

    # Strip leading standalone lab codes like "L287 " or "L-8 " that appear before the organism name
    cand = re.sub(r"^\bL-?\d+\b\s*", "", cand, flags=re.IGNORECASE).strip(",; ")

    return cand


def iter_dramp_target_mic_rows(target_text: str) -> list[tuple[str, str, str]]:
    """Yield (organism_fragment, verbatim_value, raw_unit_fragment) segments from DRAMP Target_Organism."""
    if not target_text or str(target_text).strip().upper() == "NAN":
        return []
    nt = unicodedata.normalize("NFKC", str(target_text))
    out: list[tuple[str, str, str]] = []
    for m in MIC_IN_PARENS.finditer(nt):
        inner = (m.group(1) or "").strip()
        if not inner.lstrip("=≤≥<>").strip():
            continue
        vv, unit = _dramp_mic_inner_to_value_unit(inner)
        if not vv:
            continue
        org_frag = organism_before_mic_paren(nt, m.start()).strip(",; ")
        if not org_frag or len(org_frag) < 3:
            continue
        out.append((org_frag, vv, unit))
    return out


def fetch_dramp(page: dict, record_cap: int | None) -> tuple[list[dict], str]:
    pd_local = _try_import("pandas")
    if pd_local is None:
        print("  [DRAMP] pandas not installed — skipping.")
        return [], "missing_dependency"
    raw_rel = page.get("local_workbook_path") or "data/raw/web/Antimicrobial.xlsx"
    path = ROOT / raw_rel
    if not path.is_file():
        print(f"  [DRAMP] Missing workbook {path.relative_to(ROOT)} — skipping.")
        return [], "missing_file"

    sheet_raw = page.get("sheet_name")
    sheet = 0 if sheet_raw is None else sheet_raw
    source_id = page["source_id"]
    source_base = page.get("url", "https://dramp.cpu-bioinfor.org").rstrip("/")
    database_doi = page.get("doi", "10.1093/nar/gkae1008")

    df = pd_local.read_excel(path, sheet_name=sheet)

    rows: list[dict] = []
    for _, r in df.iterrows():
        if record_cap is not None and len(rows) >= record_cap:
            break
        act = str(r.get("Activity", "") or "").lower()
        if "antibacterial" not in act:
            continue
        tgt = str(r.get("Target_Organism") or "").strip()
        seq = normalize_sequence(str(r.get("Sequence") or "").strip())
        if not seq:
            continue

        peptide_name = str(r.get("Name") or "").strip()
        organism_source = str(r.get("Source") or "").strip()
        dramp_id = str(r.get("DRAMP_ID") or "").strip()
        reference = str(r.get("Reference") or "").strip()
        publication_year = extract_year_from_reference(reference)
        pmid = re.sub(r"\D", "", str(r.get("Pubmed_ID") or "").strip())
        row_source_url = pubmed_url(pmid) if pmid else source_base
        row_doi = extract_doi_from_text(reference)

        segments = iter_dramp_target_mic_rows(tgt)
        if not segments:
            continue

        for org_frag, vv, unit_raw_hint in segments:
            if record_cap is not None and len(rows) >= record_cap:
                break
            pathogen_name, strain = split_pathogen_strain(org_frag)
            if not pathogen_name or pathogen_contains_nonbacterial_hint(pathogen_name + " " + strain):
                continue

            slug_path = slugify(pathogen_name.split()[0])[:8] if pathogen_name else "unk"
            idx = len(rows) + 1
            canon_u = canonical_measurement_unit(unit_raw_hint or "")
            mv = vv
            if not mv:
                continue
            note_parts = [
                f"DRAMP row {dramp_id}",
                f"PMID={pmid}" if pmid else "",
                f"DRAMP_db_doi={database_doi}",
                unit_context_note(unit_raw_hint),
            ]
            notes = "; ".join(part for part in note_parts if part)
            rows.append(
                {
                    "record_id": f"rec_dramp_{slugify(dramp_id)[:14]}_{slug_path}_{idx:04d}",
                    "peptide_sequence": seq,
                    "peptide_name": peptide_name,
                    "organism_source": organism_source,
                    "pathogen_name": pathogen_name,
                    "pathogen_strain": strain,
                    "measurement_value": mv,
                    "measurement_unit": canon_u if canon_u else (unit_raw_hint or ""),
                    "assay_method": "",
                    "medium": "",
                    "inoculum_cfu_ml": "",
                    "temperature_c": "",
                    "incubation_time_h": "",
                    "source_id": source_id,
                    "source_type": "database",
                    "publication_year": publication_year,
                    "source_url": row_source_url,
                    "doi": row_doi,
                    "extraction_method": "local_bulk_xlsx",
                    "extraction_confidence": "medium",
                    "notes": notes,
                }
            )

    meta = {
        "workbook_relative": raw_rel,
        "sheet": sheet,
        "rows_written": len(rows),
        "workbook_mtime": datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    snap_path = ROOT / page.get(
        "raw_snapshot_path",
        "data/raw/web/dramp_extraction_run_meta.json",
    )
    save_snapshot(snap_path, json.dumps(meta, ensure_ascii=False, indent=2).encode("utf-8"))

    print(
        f"  [DRAMP] Parsed {len(rows)} MIC record(s); metadata snapshot: "
        f"{snap_path.relative_to(ROOT)}"
    )
    return rows, "local_bulk_xlsx"


FETCHERS = {
    "db_dbaasp": fetch_dbaasp,
    "db_dramp": fetch_dramp,
}


def main() -> None:
    with MANIFEST.open(encoding="utf-8") as f:
        manifest = json.load(f)

    output_columns = load_output_columns(manifest)
    global_cap_raw = manifest.get("max_records_per_source", 2500)
    try:
        global_cap_default = int(global_cap_raw)
    except (TypeError, ValueError):
        global_cap_default = 2500

    print(f"Web extraction v{manifest.get('web_extraction_version')}")
    print(f"Default max_records_per_source: {global_cap_default}")
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
                cap = effective_record_cap(page, global_cap_default)
                cap_display = cap if cap is not None else "unlimited"
                print(f"  Record cap for this source: {cap_display}")
                rows, method = fetcher(page, cap)
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
