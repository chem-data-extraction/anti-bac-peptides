"""Shared helpers for extract / build / clean / validate pipelines.

MIC unit normalization + verbatim value handling for extractors and ``clean_dataset``,
plus pathogen substring hints for extraction filters and validation warnings.
"""

from __future__ import annotations

import re
from typing import Any


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
