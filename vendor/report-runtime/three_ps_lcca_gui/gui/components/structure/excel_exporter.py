"""
excel_exporter.py
=================
Export construction materials from engine chunks in multiple file formats.

Supported formats
-----------------
  xlsx  openpyxl  MIT       installed
  csv   pandas    BSD-3     installed (built-in)
  ods   odfpy     Apache-2  optional  (pip install odfpy)

Adding a new format
-------------------
Add an entry to EXPORT_FORMATS.  If the format requires an optional
dependency, set "requires" to the pip package name - the UI will check
for it at runtime and show an install hint if missing.
"""

from __future__ import annotations

import importlib
import datetime as _dt
import pandas as pd

CHUNKS = [
    ("CAT#Foundation",      "str_foundation"),
    ("CAT#Sub-Structure",   "str_sub_structure"),
    ("CAT#Super-Structure", "str_super_structure"),
    ("CAT#Misc",            "str_misc"),
]

METADATA_KEYS = ["Date"]

CID_COLUMNS = [
    "CID#ID",
    "CID#Name",
    "CID#Quantity",
    "CID#Unit",
    "CID#Rate",
    "CID#Rate_Src",
    "CID#Carbon_Emission_Factor",
    "CID#Carbon_Emission_units_Den",
    "CID#Conversion_Factor",
    "CID#Carbon_Emission_Src",
    "CID#Scrap_Rate",
    "CID#Recovery_Pct",
    "CID#Component",
]

# ---------------------------------------------------------------------------
# Format registry
# Each entry:
#   label    - shown in the dropdown menu
#   ext      - file extension (with dot)
#   filter   - QFileDialog filter string
#   engine   - pandas ExcelWriter engine, or None for CSV
#   requires - pip package to check at runtime, or None
# ---------------------------------------------------------------------------
EXPORT_FORMATS: list[dict] = [
    {
        "label":    "Excel (.xlsx)",
        "ext":      ".xlsx",
        "filter":   "Excel Files (*.xlsx)",
        "engine":   "openpyxl",
        "requires": None,           # openpyxl is a core dependency
    },
    {
        "label":    "OpenDocument (.ods)",
        "ext":      ".ods",
        "filter":   "OpenDocument Spreadsheet (*.ods)",
        "engine":   "odf",
        "requires": "odf",           # pip install odfpy  (Apache-2 licence)
    },
]


def format_available(fmt: dict) -> tuple[bool, str]:
    """
    Return (True, '') if the format can be used, or (False, hint) if not.
    *hint* is a human-readable install instruction.
    """
    pkg = fmt.get("requires")
    if pkg and importlib.util.find_spec(pkg) is None:
        return False, f"pip install {pkg}"
    return True, ""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _carbon_denom(carbon_unit: str) -> str:
    """'kgCO₂e/kg' → 'kg'.  Returns '' if blank or no slash."""
    if not carbon_unit:
        return ""
    parts = carbon_unit.split("/", 1)
    return parts[1].strip() if len(parts) == 2 else ""


def _blank_if_zero(val) -> object:
    """Return '' for 0/0.0 so optional numeric fields export as blank cells."""
    try:
        return "" if float(val) == 0.0 else val
    except (TypeError, ValueError):
        return val if val is not None else ""


def _chunk_to_rows(engine, chunk_key: str) -> list[dict]:
    data = engine.fetch_chunk(chunk_key) or {}
    rows = []
    for comp_name, items in data.items():
        for item in items:
            if item.get("state", {}).get("in_trash", False):
                continue
            v = item.get("values", {})
            db_orig = item.get("meta", {}).get("db_original", {})
            rows.append({
                "CID#ID":                     v.get("src_id") or db_orig.get("src_id") or "",
                "CID#Name":                   v.get("material_name", ""),
                "CID#Quantity":               v.get("quantity", ""),
                "CID#Unit":                   v.get("unit", ""),
                "CID#Rate":                   v.get("rate", ""),
                "CID#Rate_Src":               v.get("rate_source", ""),
                "CID#Carbon_Emission_Factor": _blank_if_zero(v.get("carbon_emission")),
                "CID#Carbon_Emission_units_Den": _carbon_denom(v.get("carbon_unit", "")),
                "CID#Conversion_Factor":      _blank_if_zero(v.get("conversion_factor")),
                "CID#Carbon_Emission_Src":    db_orig.get("carbon_emission_src") or "",
                "CID#Scrap_Rate":             _blank_if_zero(v.get("scrap_rate")),
                "CID#Recovery_Pct":           _blank_if_zero(v.get("post_demolition_recovery_percentage")),
                "CID#Component":              comp_name,
            })
    return rows


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def count_active_all(engine) -> int:
    """Return total number of non-trashed materials across all 4 chunks."""
    return sum(
        1
        for _, chunk_key in CHUNKS
        for items in (engine.fetch_chunk(chunk_key) or {}).values()
        for item in items
        if not item.get("state", {}).get("in_trash", False)
    )


def export_all_chunks(engine, path: str, fmt: dict) -> tuple[int, list[str]]:
    """
    Export all chunks to *path* as a multi-sheet spreadsheet.
    Sheet names use the CAT# prefix (e.g. CAT#Foundation) to match the import format.
    A Metadata sheet is always written first containing the export date.
    Returns (total_rows_written, [sheet_names_with_data]).
    """
    total = 0
    sheets_with_data: list[str] = []

    # Pre-fetch all chunk rows so counts are available for the Metadata sheet
    chunk_rows: list[tuple[str, list[dict]]] = [
        (sheet_name, _chunk_to_rows(engine, chunk_key))
        for sheet_name, chunk_key in CHUNKS
    ]

    # Pull project identity fields from general_info
    gi = engine.fetch_chunk("general_info") or {}

    # Build metadata: project info + date + per-sheet material counts
    meta_rows = [
        {"CID#Keys": "Project Name",     "CID#Values": gi.get("project_name", "")},
        {"CID#Keys": "Project Code",     "CID#Values": gi.get("project_code", "")},
        {"CID#Keys": "Country",          "CID#Values": gi.get("project_country", "")},
        {"CID#Keys": "Currency",         "CID#Values": gi.get("project_currency", "")},
        {"CID#Keys": "Date",             "CID#Values": _dt.date.today().isoformat()},
    ]
    for sheet_name, rows in chunk_rows:
        meta_rows.append({"CID#Keys": f"{sheet_name} Total", "CID#Values": len(rows)})

    with pd.ExcelWriter(path, engine=fmt["engine"]) as writer:
        # Metadata sheet first
        pd.DataFrame(meta_rows, columns=["CID#Keys", "CID#Values"]).to_excel(
            writer, sheet_name="Metadata", index=False
        )

        for sheet_name, rows in chunk_rows:
            df = pd.DataFrame(rows if rows else [], columns=CID_COLUMNS)
            df.to_excel(writer, sheet_name=sheet_name, index=False)
            if rows:
                sheets_with_data.append(sheet_name)
                total += len(rows)

    return total, sheets_with_data
