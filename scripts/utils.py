"""Shared helpers for extract / build / clean / validate pipelines.

MIC unit normalization, extractor-side verbatim/string helpers,
``coerce_mic_measurement_to_scalar_string`` for ``clean_dataset``,
plus pathogen substring hints for extraction filters and validation warnings.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA_PATH = ROOT / "specs/dataset_schema.json"


def load_schema_field_names(schema_path: Path | None = None) -> list[str]:
    """Return ordered field names from specs/dataset_schema.json."""
    path = schema_path or DEFAULT_SCHEMA_PATH
    with path.open(encoding="utf-8") as f:
        schema = json.load(f)
    return [field["name"] for field in schema["fields"]]


def _compact_unit(unit_raw: object) -> str:
    if unit_raw is None:
        return ""
    s = (
        str(unit_raw)
        .strip()
        .replace("\u2212", "-")
        .replace("\u03bc", "u")
        .replace("μ", "u")
        .replace("µ", "u")
    )
    s = re.sub(r"\s+", "", s.lower())
    s = s.replace("microg/ml", "ug/ml").replace("microgram/ml", "ug/ml").replace("micrograms/ml", "ug/ml")
    return s


def canonical_measurement_unit(unit_raw: Any) -> str:
    """Stable label stored in CSV measurement_unit column."""
    c = _compact_unit(unit_raw)
    if c.endswith("ng/ml"):
        return "ng/mL"
    if c.endswith("nm"):
        return "nM"
    if c.endswith("pmol/ml") or "pmol/ml" in c:
        return "pmol/ml"
    if c.endswith("mg/l") or c.endswith("mg/ml"):
        return "mg/L"
    if c in ("ug/ml",) or c.endswith("ug/ml"):
        return "ug/mL"
    if c in ("um", "umol/l", "umol/ml"):
        return "uM"
    stripped = "" if unit_raw is None else str(unit_raw).strip()
    return stripped


def unit_context_note(unit_raw: object) -> str:
    """Short provenance snippet for extractor notes (e.g. ``unit=uM``)."""
    compact = _compact_unit(unit_raw)
    return f"unit={compact}" if compact else "unit="


def verbatim_measurement_value(raw: object) -> str:
    """Strip MIC token for ``measurement_value``; empty if missing."""
    if raw is None:
        return ""
    s = str(raw).strip()
    return "" if str(s).upper() in ("NA", "N/A", "-", "") else s.replace(",", ".").replace("−", "-")


_PLUS_MINUS_SPLIT = re.compile(r"(?:±|\u00b1|\s*\+\s*/\s*-\s*)", re.IGNORECASE)
_LEADING_COMPARISON = re.compile(r"^[<>=≤≥≈~\s\u2264\u2265]+")
_TRAILING_COMPARISON = re.compile(r"[<>=≤≥≈~\s]+$")
# Two decimal tokens separated by a hyphen / minus / dash (not unary minus on the LHS).
_MIC_RANGE = re.compile(
    r"""^\s*
        (?P<a>[0-9]+(?:\.[0-9]+)?|[0-9]*\.[0-9]+)
        \s*[-−–—]\s*
        (?P<b>[0-9]+(?:\.[0-9]+)?|[0-9]*\.[0-9]+)
        \s*$""",
    re.VERBOSE,
)


def _strip_comparison_decorators(token: str) -> str:
    prev = ""
    s = token
    while prev != s:
        prev = s
        s = _LEADING_COMPARISON.sub("", s)
        s = _TRAILING_COMPARISON.sub("", s)
    return s.strip()


def coerce_mic_measurement_to_scalar_string(raw: object) -> str | None:
    """Turn MIC text into one float-compatible string.

    Rules: drop leading/trailing comparison symbols (> < = ≤ ≥ ≈ ~);
    split on ± / +/- and keep the main (left) part;
    for a-b ranges take max(a, b); lone numbers become str(float(..)).
    Returns None if nothing coherent remains."""
    if raw is None:
        return None
    text = str(raw).strip()
    if not text or str(text).upper() in ("NA", "N/A", "-", "NAN"):
        return None
    text = text.replace(",", ".").replace("−", "-")
    head = _PLUS_MINUS_SPLIT.split(text, maxsplit=1)[0].strip()
    head = _strip_comparison_decorators(head)
    if not head:
        return None
    rng = _MIC_RANGE.match(head)
    if rng is not None:
        a_v = float(rng.group("a"))
        b_v = float(rng.group("b"))
        return str(max(a_v, b_v))
    try:
        return str(float(head))
    except ValueError:
        return None


NONBACTERIAL_PATHOGEN_SUBSTRINGS: tuple[str, ...] = (
    "aspergillus",
    "blastomyces",
    "candida",
    "coccidioides",
    "cryptococcus",
    "erythrocyte",
    "fungal",
    "fungus",
    "fusarium",
    "hela",
    "histoplasma",
    "human",
    "mammalian",
    "microsporum",
    "mouse",
    "mucor",
    "paracoccidioides",
    "penicillium",
    "pneumocystis",
    "rhizopus",
    "saccharomyces",
    "trichophyton",
    "tumor",
    "virus",
    "viral",
    "cancer",
)


def pathogen_contains_nonbacterial_hint(pathogen_raw: object) -> bool:
    """True if ``pathogen_name`` text matches a yeast/fungal/non-bacterial assay target hint."""
    if pathogen_raw is None:
        return False
    text = str(pathogen_raw).lower().strip()
    if not text or text == "nan":
        return False
    return any(h in text for h in NONBACTERIAL_PATHOGEN_SUBSTRINGS)
