"""
excel_importer.py
=================
Excel → Material import pipeline.

Flow:
  1. User picks an .xlsx file via ExcelImportDialog
  2. Parser reads every sheet (sheet name = structural category)
  3. Schema verifier checks columns and flags row-level errors
  4. ImportPreviewWindow opens - one tab per sheet
     - Invalid cells highlighted red
     - "Issues" column summarises problems per row
     - User can edit cells inline before confirming
  5. On confirm → validated dicts printed to console
       (replace the print() call with your controller / engine write)

Column format  (CID# prefix)
----------------------------
Every recognised column must be prefixed with "CID#" (case-insensitive).
The part after "cid#" must match the canonical field name EXACTLY.

  Valid  : CID#Name, cid#name, CID#NAME, Cid#Rate
  Invalid: CID#Mat_Name, CID#material_name, Name, rate

Canonical field names
  Required : ID, Name, Quantity, Unit, Rate, Component
  Optional : Rate_Src, Carbon_Emission_Factor, Carbon_Emission_units,
             Conversion_Factor, Carbon_Emission_Src,
             Scrap_Rate, Recovery_Pct, Grade, Type

Sheet → chunk routing
---------------------
Sheet names are matched (case-insensitive) against SHEET_TO_CHUNK.
Unrecognised sheet names are routed to str_misc and the sheet name is used
as the component name (auto-created if it doesn't exist yet).
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from PySide6.QtCore import Qt, QEvent, QSize, QTimer, Signal
from PySide6.QtGui import QColor, QBrush, QDoubleValidator
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtWidgets import QButtonGroup, QRadioButton, QGroupBox
from three_ps_lcca_gui.gui.themes import get_token
from .widgets.material_dialog import build_excel_snapshot
from .registry.material_entry import resolve_carbon_denom
import sys
from ..utils.table_widgets import round_table_viewport, WordWrapHeaderView
from ..utils.unit_resolver import (
    get_unit_info as _gui,
    get_known_units as _gku,
)
from ..utils.unit_resolver import get_known_units as _gku
from ..utils.unit_resolver import get_unit_info
from PySide6.QtWidgets import QPlainTextEdit
import traceback
import json
import datetime as _dt

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Canonical field names recognised after the "CID#" prefix.
# The prefix match is case-insensitive; the field name must match EXACTLY.
# e.g.  "CID#Name" → "Name", "cid#rate" → "Rate"  ✓
#        "CID#material_name"                         ✗  (not in this set)
CID_PREFIX = "cid#"

CID_FIELDS: set[str] = {
    "ID",
    "Name",
    "Quantity",
    "Unit",
    "Rate",
    "Rate_Src",
    "Carbon_Emission_Factor",
    "Carbon_Emission_units",
    "Conversion_Factor",
    "Carbon_Emission_Src",
    "Scrap_Rate",
    "Recovery_Pct",
    "Component",
}

# All keys are lowercase - lookup uses field_part.lower() for case-insensitive matching.
# Required columns: name, unit, rate.  All others (including id) are optional.
CID_TO_INTERNAL: dict[str, str] = {
    "id": "src_id",  # optional — Excel column CID#ID maps to internal src_id
    "name": "name",
    "quantity": "quantity",
    "unit": "unit",
    "rate": "rate",
    "rate_src": "rate_src",
    "carbon_emission_factor": "carbon_emission",
    "carbon_emission_units": "carbon_emission_units",
    "carbon_emission_units_den": "carbon_emission_units_den",
    "conversion_factor": "conversion_factor",
    "carbon_emission_src": "carbon_emission_src",
    "scrap_rate": "scrap_rate",
    "recovery_pct": "recovery_pct",
    "component": "component",
}

REQUIRED_FIELDS = {"name", "unit", "rate"}

UNCATEGORISED = "Uncategorised"

NUMERIC_FIELDS = {
    "rate",
    "carbon_emission",
    "conversion_factor",
    "scrap_rate",
    "recovery_pct",
    "quantity",
}

# Sheet name (lowercase) → engine chunk key.
# Unrecognised sheets fall back to str_misc with the sheet name as component.
SHEET_TO_CHUNK: dict[str, str] = {
    "foundation": "str_foundation",
    "sub-structure": "str_sub_structure",
    "substructure": "str_sub_structure",
    "super-structure": "str_super_structure",
    "superstructure": "str_super_structure",
    "misc": "str_misc",
    "miscellaneous": "str_misc",
}

FALLBACK_CHUNK = "str_misc"


# No OK_COLOR - default background is left untouched (inherits theme)

_DARK_TEXT = QColor("#000000")
_LIGHT_TEXT = QColor("#ffffff")


def _text_color(bg: QColor) -> QColor:
    """Return dark or light text so it contrasts against *bg*."""
    # Perceived luminance (0-255)
    lum = 0.299 * bg.red() + 0.587 * bg.green() + 0.114 * bg.blue()
    if lum > 128:
        return QColor(_DARK_TEXT)
    return QColor(_LIGHT_TEXT)


# ---------------------------------------------------------------------------
# Step 1 - Raw parse
# ---------------------------------------------------------------------------


def _normalise_header(h: str) -> str:
    return str(h).strip().lower()


def _parse_cid_header(raw: str) -> str | None:
    """
    Return the internal key if raw header is a valid CID# column, else None.
    Entire header is lowercased before matching - case-insensitive throughout.
    e.g. "CID#Name" → "name",  "cid#rate" → "rate",  "Name" → None
    """
    stripped = str(raw).strip().lower()
    if not stripped.startswith(CID_PREFIX):
        return None
    field_part = stripped[len(CID_PREFIX) :]
    return CID_TO_INTERNAL.get(field_part)


def _build_column_map(
    headers: list[str],
) -> tuple[dict[str, int], list[str], list[str]]:
    """
    Return ({internal_key: col_index}, [unrecognised_cid_headers], [duplicate_cid_headers]).
    - Unrecognised: CID# prefix present but field name wrong.
    - Duplicate: valid CID# field seen more than once (first occurrence wins).
    """
    col_map: dict[str, int] = {}
    unrecognised: list[str] = []
    duplicates: list[str] = []
    for col_idx, raw in enumerate(headers):
        internal = _parse_cid_header(raw)
        if internal is not None:
            if internal not in col_map:
                col_map[internal] = col_idx
            else:
                duplicates.append(str(raw).strip())
        elif str(raw).strip().lower().startswith(CID_PREFIX):
            unrecognised.append(str(raw).strip())
    return col_map, unrecognised, duplicates


def parse_excel(path: str) -> dict:
    """
    Read all sheets.  Returns:
        {
            "materials": { sheet_name: [ {raw_fields…, _row_num, _errors: [], _warnings: []} ] },
            "metadata":  [ {"key": ..., "value": ...}, ... ]   # empty if no Metadata sheet
        }
    Only CAT# sheets are processed as material sheets; all others are skipped.
    A sheet named "Metadata" (case-insensitive) is parsed separately into the metadata list.
    """
    try:
        all_sheets: dict[str, pd.DataFrame] = pd.read_excel(
            path, sheet_name=None, header=None, dtype=str
        )
    except PermissionError:
        raise ValueError(
            "Could not open the file - it may be open in Excel or another application. "
            "Close it and try again."
        )
    except Exception as exc:
        raise ValueError(f"Could not open file: {exc}") from exc

    materials: dict[str, list[dict]] = {}
    metadata: list[dict] = []

    for sheet_name, df in all_sheets.items():
        if df.empty:
            continue

        # Metadata sheet - parse separately, never as materials
        if sheet_name.strip().lower() == "metadata":
            metadata = _parse_metadata_sheet(df)
            continue

        # Only process CAT# sheets as material sheets
        if not sheet_name.strip().lower().startswith("cat#"):
            continue

        # Find header row - first row that contains at least one CID# column
        header_row_idx = _find_header_row(df)
        if header_row_idx is None:
            continue

        headers = [str(c) for c in df.iloc[header_row_idx].tolist()]
        col_map, unrecognised_hdrs, duplicate_hdrs = _build_column_map(headers)
        data_rows = df.iloc[header_row_idx + 1 :].reset_index(drop=True)

        # EC2: header-only sheet - add a placeholder so the tab still appears
        if data_rows.empty or data_rows.shape[0] == 0:
            materials[sheet_name] = []
            continue

        # Build per-sheet warnings that apply to every row
        sheet_warns: list[str] = []
        if unrecognised_hdrs:
            sheet_warns.append(
                f"Unrecognised CID# column(s) ignored: {', '.join(unrecognised_hdrs)}"
            )
        if duplicate_hdrs:
            sheet_warns.append(
                f"Duplicate CID# column(s) - first occurrence used: {', '.join(duplicate_hdrs)}"
            )

        rows: list[dict] = []
        for i, row in data_rows.iterrows():
            raw_values = row.tolist()

            # Skip completely blank rows
            if all((v is None or str(v).strip() in ("", "nan")) for v in raw_values):
                continue

            row_warns = list(sheet_warns)  # copy so each row has its own list

            record: dict[str, Any] = {
                "_row_num": header_row_idx + 2 + i,  # 1-based Excel row
                "_errors": [],
                "_warnings": row_warns,
            }
            for field, col_idx in col_map.items():
                raw = raw_values[col_idx] if col_idx < len(raw_values) else None
                val = _clean_value(raw)
                # EC4: flag formula strings in numeric fields
                if val.startswith("=") and field in NUMERIC_FIELDS:
                    record["_warnings"].append(
                        f"'{field}' contains a formula '{val}' - replace with a plain number"
                    )
                    val = ""
                record[field] = val

            rows.append(record)

        materials[sheet_name] = rows

    return {"materials": materials, "metadata": metadata}


def _find_header_row(df: pd.DataFrame) -> int | None:
    """
    Return index of first row that contains at least one valid CID# column.
    Note: pandas reads merged cells as value-in-first-cell, NaN elsewhere,
    so a merged CID#Name header is still detected correctly on the first cell.
    """
    for row_idx in range(min(20, len(df))):
        row_vals = [str(v).strip() for v in df.iloc[row_idx].tolist()]
        if any(_parse_cid_header(v) is not None for v in row_vals):
            return row_idx
    return None


def _clean_value(raw: Any) -> str:
    if raw is None:
        return ""
    s = str(raw).strip()
    return "" if s.lower() == "nan" else s


def _parse_metadata_sheet(df: pd.DataFrame) -> list[dict]:
    """Parse a Metadata sheet (CID#Keys / CID#Values columns) into a list of dicts."""
    key_col = val_col = header_row = None
    for row_idx in range(min(10, len(df))):
        row = [str(v).strip() for v in df.iloc[row_idx].tolist()]
        for col_idx, cell in enumerate(row):
            if cell.lower() == "cid#keys":
                key_col = col_idx
            elif cell.lower() == "cid#values":
                val_col = col_idx
        if key_col is not None and val_col is not None:
            header_row = row_idx
            break
    if header_row is None:
        return []
    result = []
    for i in range(header_row + 1, len(df)):
        row_vals = df.iloc[i].tolist()
        key = _clean_value(row_vals[key_col] if key_col < len(row_vals) else None)
        val = _clean_value(row_vals[val_col] if val_col < len(row_vals) else None)
        if key:
            result.append({"key": key, "value": val})
    return result


# ---------------------------------------------------------------------------
# Step 2 - Schema verification
# ---------------------------------------------------------------------------


def verify_schema(parsed: dict[str, list[dict]]) -> dict[str, list[dict]]:
    """
    Validate every row in-place.  Appends to _errors / _warnings lists.
    Also stamps _chunk_key and _is_fallback_chunk on each record.
    Returns the same dict (mutated).
    """
    # EC13: track IDs globally across all sheets to catch duplicates
    seen_ids: dict[str, str] = {}  # id_value → "SheetName:row"

    # EC5: track chunk→component combos to detect cross-sheet collisions
    seen_chunk_comps: dict[tuple[str, str], str] = {}  # (chunk, comp) → sheet_name

    for sheet_name, rows in parsed.items():
        # Strip CAT# prefix before routing so "CAT#Foundation" → "foundation"
        _bare = sheet_name.strip()
        if _bare.lower().startswith("cat#"):
            _bare = _bare[4:].strip()
        chunk_key = SHEET_TO_CHUNK.get(_bare.lower(), FALLBACK_CHUNK)
        is_fallback = (
            chunk_key == FALLBACK_CHUNK
            and _bare.lower() not in SHEET_TO_CHUNK
        )

        for record in rows:
            errs: list[str] = record.setdefault("_errors", [])
            warns: list[str] = record.setdefault("_warnings", [])

            # Stamp routing info onto every record
            record["_chunk_key"] = chunk_key
            record["_is_fallback_chunk"] = is_fallback

            # EC6: whitespace-only component → normalise to empty
            comp_val = record.get("component", "")
            if comp_val != comp_val.strip():
                record["component"] = comp_val.strip()

            # For unrecognised CAT# sheets routed to str_misc, prefix component with
            # the bare suffix: "ABC - Expansion Joint"
            if is_fallback:
                comp = record.get("component", "").strip()
                prefix = f"{_bare} - "
                if not comp:
                    record["component"] = UNCATEGORISED
                elif not comp.startswith(prefix):
                    record["component"] = f"{prefix}{comp}"
            elif not record.get("component", "").strip():
                # Recognised sheet with blank component → Uncategorised
                record["component"] = UNCATEGORISED

            # Required field check
            for field in REQUIRED_FIELDS:
                val = record.get(field, "")
                if not val:
                    errs.append(f"Missing required field: '{field}'")

            # Numeric type check
            for field in NUMERIC_FIELDS:
                val = record.get(field, "")
                if val:
                    try:
                        float(val)
                    except ValueError:
                        errs.append(f"'{field}' must be a number (got '{val}')")

            # Unit validation - use get_unit_info which covers canonical,
            # aliases (rmt→rm, t→tonne etc.) and custom units from DB
            unit = record.get("unit", "").strip()
            if unit:
                try:

                    _si, _ = _gui(unit)
                    if _si is None:
                        warns.append(
                            f"Unknown unit '{unit}' - not in standard list or "
                            f"custom units. Verify before importing."
                        )
                except Exception:
                    # unit_resolver not available (standalone mode) - derive from definitions
                    try:

                        _known = _gku()
                    except Exception:
                        _known = set()
                    if _known and unit.lower() not in _known:
                        warns.append(f"Unknown unit '{unit}' - verify before importing")

            # EC8: rate = 0 warning
            rate_str = record.get("rate", "")
            if rate_str:
                try:
                    rate_val = float(rate_str)
                    if rate_val < 0:
                        warns.append("Rate is negative - please verify")
                    elif rate_val == 0:
                        warns.append("Rate is zero - verify this is intentional")
                except ValueError:
                    pass

            # Carbon emission present but missing denominator
            ef_str = record.get("carbon_emission", "")
            den = record.get("carbon_emission_units_den", "")
            units = record.get("carbon_emission_units", "")
            if ef_str and not den and not units:
                warns.append(
                    "carbon_emission provided but neither carbon_emission_units_den "
                    "nor carbon_emission_units is filled in"
                )

            # carbon_emission_units_den is the bare-denominator column (e.g. "kg") -
            # it must NEVER carry a full "numerator/denominator" ratio. A value
            # containing "co2" here means the row belongs in carbon_emission_units
            # instead - reject rather than silently importing a corrupted unit.
            if den and "co2" in str(den).lower().replace("₂", "2"):
                errs.append(
                    f"'carbon_emission_units_den' must be a bare denominator "
                    f"(e.g. 'kg'), not a full ratio - got '{den}'. Use "
                    f"'carbon_emission_units' for the full 'kgCO2e/<unit>' string."
                )

            # carbon_emission_units is the full-ratio column - it must always
            # start with the fixed numerator (kgCO2/kgCO2e). Anything else is
            # either a bare unit typed in the wrong column or garbage - reject
            # rather than guessing.
            if units and "co2" not in str(units).lower().replace("₂", "2"):
                errs.append(
                    f"'carbon_emission_units' must be a full ratio starting with "
                    f"'kgCO2e/' (e.g. 'kgCO2e/kg') - got '{units}', which doesn't "
                    f"contain 'CO2'. If this is meant to be a bare denominator, use "
                    f"'carbon_emission_units_den' instead."
                )

            # EC9: carbon EF = 0 but denominator is filled
            if ef_str and (den or units):
                try:
                    if float(ef_str) == 0:
                        warns.append(
                            "Carbon emission factor is zero - carbon calc will produce 0"
                        )
                except ValueError:
                    pass

            # EC13: duplicate CID#ID across all sheets
            id_val = record.get("src_id", "").strip()
            if id_val:
                loc = f"{sheet_name}:row {record.get('_row_num', '?')}"
                if id_val in seen_ids:
                    warns.append(
                        f"CID#ID '{id_val}' already seen at {seen_ids[id_val]} - may cause conflicts"
                    )
                else:
                    seen_ids[id_val] = loc

            # EC5: cross-sheet chunk+component collision
            comp = record.get("component", "").strip()
            if comp:
                key = (chunk_key, comp)
                if key in seen_chunk_comps and seen_chunk_comps[key] != sheet_name:
                    warns.append(
                        f"Component '{comp}' also appears in sheet "
                        f"'{seen_chunk_comps[key]}' under the same chunk - "
                        f"rows will be merged on import"
                    )
                else:
                    seen_chunk_comps[key] = sheet_name

    return parsed


# ---------------------------------------------------------------------------
# Step 3 - Convert to final dict format
# ---------------------------------------------------------------------------


def record_to_material_dict(record: dict) -> dict:
    """
    Convert a verified record into the exact dict format that
    StructureManagerWidget.add_material() expects - i.e. the same
    structure produced by MaterialDialog.get_values().
    """

    def _float_or_none(key: str):
        raw = record.get(key)
        if raw is None or str(raw).strip() == "":
            return None
        try:
            return float(raw)
        except (ValueError, TypeError):
            return None

    raw_unit = record.get("unit", "").strip()
    carbon_ef = _float_or_none("carbon_emission")
    carbon_denom = resolve_carbon_denom(record) or ""
    scrap = _float_or_none("scrap_rate")
    recovery = _float_or_none("recovery_pct")
    has_carbon = (carbon_ef or 0) > 0 and bool(carbon_denom)
    has_recycle = (scrap or 0) > 0 or (recovery or 0) > 0

    unit_to_si, _ = get_unit_info(raw_unit)
    if unit_to_si is None:
        unit_to_si = 1.0

    cf = _float_or_none("conversion_factor")

    return {
        "values": {
            "src_id": record.get("src_id", "").strip() or None,
            "material_name": record.get("name", "").strip(),
            "quantity": _float_or_none("quantity"),
            "unit": raw_unit,
            "unit_to_si": unit_to_si,
            "rate": _float_or_none("rate"),
            "rate_source": record.get("rate_src", "").strip() or None,
            "carbon_emission": carbon_ef,
            "carbon_unit": f"kgCO₂e/{carbon_denom}" if carbon_denom else None,
            "carbon_emission_src": record.get("carbon_emission_src", "").strip() or None,
            "conversion_factor": cf,
            "scrap_rate": scrap,
            "post_demolition_recovery_percentage": recovery,
            "is_recyclable": has_recycle,
        },
        "meta": {
            "source": "excel",
            "source_db_key": "",
            "db_original": build_excel_snapshot(record),
        },
        "state": {
            "included_in_carbon_emission": has_carbon,
            "included_in_recyclability": has_recycle,
        },
        # Top-level routing/control flags - consumed before add_material() is called
        "_force_overwrite": bool(record.get("_duplicate_name", False)),
        "_component": record.get("component", "").strip(),
        "_chunk_key": record.get("_chunk_key", FALLBACK_CHUNK),
    }


# ---------------------------------------------------------------------------
# Step 4 - Pre-write engine validation
# ---------------------------------------------------------------------------


def _validate_for_engine(
    values_dict: dict,
    comp_name: str,
    chunk_key: str,
    manager,
    force_overwrite: bool = False,
) -> list[str]:
    """
    Enforces the EXACT rules from MaterialDialog.validate_and_accept()
    and StructureManagerWidget.open_dialog(). No more, no less.

    *values_dict* is the structured dict from record_to_material_dict()
    ({values, meta, state}).  Mutates values_dict["state"] in-place for
    auto-exclusions.
    Returns a list of block reasons - empty = safe to call add_material().

    HARD BLOCKS (row skipped entirely):
      1. material_name empty                  - validate_and_accept critical
      2. quantity <= 0                        - validate_and_accept critical
      3. duplicate material_name in component - open_dialog warning block

    AUTO-EXCLUSIONS (row imports, flag silently set to False):
      4. state.included_in_carbon_emission → False if EF <= 0 or CF <= 0
      5. state.included_in_recyclability   → False if scrap <= 0 AND recovery <= 0
    """
    reasons: list[str] = []
    v = values_dict.get("values", {})

    # ── 1. material_name ─────────────────────────────────────────────────────
    name = str(v.get("material_name", "")).strip()
    if not name:
        reasons.append("material_name is empty")

    # ── 2. quantity ──────────────────────────────────────────────────────────
    try:
        qty = float(v.get("quantity") or 0)
    except (ValueError, TypeError):
        qty = 0.0
    if qty <= 0:
        reasons.append(f"quantity must be > 0 (got {qty})")

    # ── 2b. unit ─────────────────────────────────────────────────────────────
    unit = str(v.get("unit", "")).strip()
    if not unit:
        reasons.append("unit is empty - every material must have a unit")

    # ── 2c. rate ─────────────────────────────────────────────────────────────
    rate_raw = v.get("rate")
    if rate_raw is None:
        reasons.append("rate is required")
    else:
        try:
            rate = float(rate_raw)
        except (ValueError, TypeError):
            rate = 0.0
        if rate < 0:
            reasons.append(
                f"rate must be >= 0 (got {rate_raw!r}) - negative rate is not allowed"
            )

    # ── 3. duplicate name ────────────────────────────────────────────────────
    # Skipped when force_overwrite=True (user explicitly checked a duplicate row)
    if name and manager is not None and not force_overwrite:
        try:
            existing_data = manager.controller.engine.fetch_chunk(chunk_key) or {}
            taken = {
                item.get("values", {}).get("material_name", "").strip().lower()
                for item in existing_data.get(comp_name, [])
                if not item.get("state", {}).get("in_trash", False)
            }
            if name.lower() in taken:
                reasons.append(
                    f'"{name}" already exists in "{comp_name}" - '
                    f"use a different name or choose Merge"
                )
        except Exception:
            pass  # can't check → allow through

    # Return early if hard blocks found - no point running auto-exclusions
    if reasons:
        return reasons

    state = values_dict.setdefault("state", {})

    # ── 4. carbon auto-exclusion ─────────────────────────────────────────────
    if state.get("included_in_carbon_emission") is True:
        try:
            ef = float(v.get("carbon_emission") or 0)
        except (ValueError, TypeError):
            ef = 0.0
        try:
            cf = float(v.get("conversion_factor") or 0)
        except (ValueError, TypeError):
            cf = 0.0
        if ef <= 0 or cf <= 0:
            state["included_in_carbon_emission"] = False

    # ── 5. recyclability auto-exclusion ──────────────────────────────────────
    if state.get("included_in_recyclability"):
        try:
            scrap = float(v.get("scrap_rate") or 0)
        except (ValueError, TypeError):
            scrap = 0.0
        try:
            recovery = float(v.get("post_demolition_recovery_percentage") or 0)
        except (ValueError, TypeError):
            recovery = 0.0
        if scrap <= 0 and recovery <= 0:
            state["included_in_recyclability"] = False

    return reasons


# (internal_field, header_label, numeric_only)
IMPORT_COLUMNS: list[tuple[str, str, bool]] = [
    ("src_id", "ID", False),
    ("name", "Name *", False),
    ("quantity", "Quantity", True),
    ("unit", "Unit *", False),
    ("rate", "Rate *", True),
    ("rate_src", "Rate Source", False),
    ("carbon_emission", "Carbon EF", True),
    ("carbon_emission_units_den", "Carbon Unit", False),
    ("conversion_factor", "Conversion Factor", True),
    ("carbon_emission_src", "Carbon EF Source", False),
    ("scrap_rate", "Scrap Rate", True),
    ("recovery_pct", "Recovery %", True),
    ("_issues", "Issues", False),
]

# Column widths - tuned to content, not header length
#  ID   Name   Quantity   Unit  Rate  RateSrc  CEF  CUnit  CF  CESrc  Scrap  Rec%  Issues
_COL_WIDTHS = [55, 200, 55, 65, 80, 140, 80, 110, 90, 140, 75, 80, 200]

# Col 0 is the selection checkbox; all IMPORT_COLUMNS data starts at col 1
_CB_COL = 0
_DATA_START = 1

# Issues column index - +1 because col 0 is the checkbox
_ISSUES_COL = (
    next(i for i, (f, _, _n) in enumerate(IMPORT_COLUMNS) if f == "_issues")
    + _DATA_START
)


# ---------------------------------------------------------------------------
# Delegate - enforces numeric-only input on designated columns
# ---------------------------------------------------------------------------


class _CellDelegate(QStyledItemDelegate):
    """
    Paints the cell-editable-bg tint on editable cells.
    When numeric=True, also attaches a QDoubleValidator to the editor.
    """

    def __init__(self, numeric: bool = False, parent=None):
        super().__init__(parent)
        self._numeric = numeric
        from three_ps_lcca_gui.gui.themes import theme_manager
        theme_manager().theme_changed.connect(self._on_theme_changed)

    def _on_theme_changed(self):
        p = self.parent()
        if p and hasattr(p, "viewport"):
            p.viewport().update()

    def paint(self, painter, option, index):
        # Determine background color: explicit (error/warning) or tint (editable)
        bg = index.data(Qt.BackgroundRole)
        if isinstance(bg, QBrush):
            bg = bg.color()
            
        if (bg is None or not bg.isValid()) and (index.flags() & Qt.ItemIsEditable):
            bg = QColor(get_token("cell-editable-bg"))

        if bg and bg.isValid():
            painter.save()
            painter.fillRect(option.rect, bg)
            painter.restore()
            
        # To prevent QSS 'background-color' from painting over our manual fill,
        # we pass a modified option with a transparent background brush.
        new_option = QStyleOptionViewItem(option)
        new_option.backgroundBrush = QBrush(Qt.NoBrush)
        super().paint(painter, new_option, index)

    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        editor.setStyleSheet(
            "QLineEdit { background: palette(base); border: 1px solid palette(highlight);"
            " border-radius: 0; margin: 0; padding: 0 2px; min-height: 0; }"
        )
        if self._numeric:
            validator = QDoubleValidator(editor)
            validator.setNotation(QDoubleValidator.StandardNotation)
            editor.setValidator(validator)
        return editor

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)


# ---------------------------------------------------------------------------
# ImportComponentTable - one per component group box
# ---------------------------------------------------------------------------


class ImportComponentTable(QTableWidget):
    """
    Table for one component's rows inside the preview window.
    - Col 0 is a selection checkbox (disabled for error rows).
    - Numeric columns use QDoubleValidator via a delegate - alpha input is blocked.
    - Inline double-click editing with live re-validation.
    """

    selection_changed = Signal()

    def __init__(self, component_name: str, rows: list[dict], parent=None):
        super().__init__(parent)
        self.setHorizontalHeader(WordWrapHeaderView(Qt.Horizontal, parent=self))
        round_table_viewport(self)
        self.component_name = component_name
        self._rows = rows

        # Col 0 = checkbox; cols 1..N = IMPORT_COLUMNS
        self.setColumnCount(len(IMPORT_COLUMNS) + _DATA_START)
        self.setHorizontalHeaderLabels([""] + [lbl for _, lbl, _ in IMPORT_COLUMNS])

        # Checkbox column: fixed, narrow
        self.horizontalHeader().setSectionResizeMode(_CB_COL, QHeaderView.Fixed)
        self.setColumnWidth(_CB_COL, 28)

        # Show the Excel CID# column name on header hover (data cols only)
        for col, (field, _, _n) in enumerate(IMPORT_COLUMNS):
            actual_col = col + _DATA_START
            if field != "_issues":
                cid_name = next(
                    (k for k, v in CID_TO_INTERNAL.items() if v == field), field
                )
                self.horizontalHeaderItem(actual_col).setToolTip(
                    f"Excel column: CID#{cid_name}"
                )

        self.horizontalHeader().setVisible(True)
        self.horizontalHeader().setFixedHeight(32)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.horizontalHeader().setSectionResizeMode(_CB_COL, QHeaderView.Fixed)
        self.horizontalHeader().setStretchLastSection(False)
        self.horizontalHeader().setMinimumSectionSize(60)
        self.verticalHeader().setDefaultSectionSize(32)
        self.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.setWordWrap(True)
        self.setTextElideMode(Qt.ElideNone)
        self.setAlternatingRowColors(True)
        self.setEditTriggers(QTableWidget.DoubleClicked | QTableWidget.SelectedClicked)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        for col, w in enumerate(_COL_WIDTHS):
            self.setColumnWidth(col + _DATA_START, w)

        # Install cell delegate on every editable data column:
        # tints the cell with cell-editable-bg and enforces numeric input where needed.
        _plain_delegate = _CellDelegate(numeric=False, parent=self)
        _numeric_delegate = _CellDelegate(numeric=True, parent=self)
        for col, (field, _, numeric) in enumerate(IMPORT_COLUMNS):
            if field == "_issues":
                continue
            actual_col = col + _DATA_START
            self.setItemDelegateForColumn(
                actual_col, _numeric_delegate if numeric else _plain_delegate
            )

        self._valid_core_only: bool = False
        QTimer.singleShot(0, self._populate)
        self.itemChanged.connect(self._on_item_changed)

    # -- build ----------------------------------------------------------------

    def _populate(self):
        self.blockSignals(True)
        self.setRowCount(0)
        for rows_idx, record in enumerate(self._rows):
            if self._valid_core_only:
                try:
                    qty = float(record.get("quantity") or 0)
                except (ValueError, TypeError):
                    qty = 0.0
                try:
                    rate = float(record.get("rate") or 0)
                except (ValueError, TypeError):
                    rate = 0.0
                name = str(record.get("name", "") or "").strip()
                unit = str(record.get("unit", "") or "").strip()
                if qty <= 0 or rate <= 0 or not name or not unit:
                    continue
            self._append_record(record, rows_idx)
        self.blockSignals(False)
        self._update_height()
        self.updateGeometry()

    def _append_record(self, record: dict, rows_idx: int):
        row = self.rowCount()
        self.insertRow(row)

        errs = record.get("_errors", [])
        warns = record.get("_warnings", [])
        is_dup = bool(record.get("_duplicate_name")) and not bool(errs)
        has_error = bool(errs)
        has_warn = (bool(warns) or is_dup) and not has_error
        
        # Use theme-aware alpha-blended backgrounds
        color = QColor(get_token("cell-invalid-bg")) if has_error else (QColor(get_token("cell-warn-bg")) if has_warn else None)

        # Short label shown in the Issues cell
        if errs:
            issues_short = f"{len(errs)} error(s)" if len(errs) > 1 else errs[0][:60]
        elif warns:
            issues_short = (
                f"{len(warns)} warning(s)" if len(warns) > 1 else warns[0][:60]
            )
        elif is_dup:
            issues_short = "Name exists"
        else:
            issues_short = "OK"

        # Full detail shown as tooltip on hover
        all_issues = errs + warns
        dup_note = (
            "Name already exists in this component - unchecked by default. Check to force-import."
            if is_dup
            else ""
        )
        tooltip_parts = (
            ["\n".join(f"• {m}" for m in all_issues)] if all_issues else []
        ) + ([dup_note] if dup_note else [])
        tooltip = "\n".join(tooltip_parts)

        # Col 0 - selection checkbox
        cb_item = QTableWidgetItem()
        if has_error:
            # Error rows: visible but not checkable
            cb_item.setFlags(Qt.ItemIsEnabled)
            cb_item.setCheckState(Qt.Unchecked)
        else:
            cb_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            # Duplicate rows default to unchecked; all others default to checked
            cb_item.setCheckState(Qt.Unchecked if is_dup else Qt.Checked)
        cb_item.setData(Qt.UserRole + 1, rows_idx)  # rows index stored here
        self.setItem(row, _CB_COL, cb_item)

        # Data cols (shifted by _DATA_START)
        for col, (field, _, _numeric) in enumerate(IMPORT_COLUMNS):
            actual_col = col + _DATA_START
            if field == "_issues":
                item = QTableWidgetItem(issues_short)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            elif field == "carbon_emission_units_den":
                # The row's carbon denom may have landed in either field -
                # display whichever one resolve_carbon_denom() finds so a
                # value entered via "carbon_emission_units" (the full-ratio
                # column) doesn't show as a blank cell here even though it
                # will save correctly. Edits still write back to this
                # canonical field only (see _on_item_changed).
                item = QTableWidgetItem(resolve_carbon_denom(record) or "")
                item.setData(Qt.UserRole, field)
            else:
                item = QTableWidgetItem(str(record.get(field, "") or ""))
                item.setData(Qt.UserRole, field)

            if color is not None:
                item.setBackground(QBrush(color))
                item.setForeground(QBrush(_text_color(color)))

            if tooltip:
                item.setToolTip(tooltip)

            self.setItem(row, actual_col, item)

    # -- edit sync ------------------------------------------------------------

    def _on_item_changed(self, item: QTableWidgetItem):
        # Checkbox column - only notify selection change
        if item.column() == _CB_COL:
            self.selection_changed.emit()
            return

        field = item.data(Qt.UserRole)
        if not field:
            return
        # rows_idx is stored on the checkbox item in col 0
        cb = self.item(item.row(), _CB_COL)
        rows_idx = cb.data(Qt.UserRole + 1) if cb else None
        if rows_idx is None:
            rows_idx = item.row()
        if rows_idx < len(self._rows):
            self._rows[rows_idx][field] = item.text().strip()
            self._revalidate_row(item.row(), rows_idx)

    def _revalidate_row(self, table_row: int, rows_idx: int):
        record = self._rows[rows_idx]
        # Preserve routing keys set during initial parse - don't let the
        # synthetic sheet name "_" overwrite them with the fallback chunk.
        saved_chunk = record.get("_chunk_key")
        saved_fallback = record.get("_is_fallback_chunk")
        record["_errors"] = []
        record["_warnings"] = []
        verify_schema({record.get("component", "_"): [record]})
        # Restore routing keys in case verify_schema overwrote them
        if saved_chunk is not None:
            record["_chunk_key"] = saved_chunk
        if saved_fallback is not None:
            record["_is_fallback_chunk"] = saved_fallback

        errs = record.get("_errors", [])
        warns = record.get("_warnings", [])
        is_dup = bool(record.get("_duplicate_name")) and not bool(errs)
        has_error = bool(errs)
        has_warn = (bool(warns) or is_dup) and not has_error

        if errs:
            issues_short = f"{len(errs)} error(s)" if len(errs) > 1 else errs[0][:60]
        elif warns:
            issues_short = (
                f"{len(warns)} warning(s)" if len(warns) > 1 else warns[0][:60]
            )
        elif is_dup:
            issues_short = "Name exists"
        else:
            issues_short = "OK"

        all_issues = errs + warns
        tooltip = "\n".join(f"• {m}" for m in all_issues) if all_issues else ""
        
        # Use theme-aware alpha-blended backgrounds
        color = QColor(get_token("cell-invalid-bg")) if has_error else (QColor(get_token("cell-warn-bg")) if has_warn else None)

        self.blockSignals(True)
        for col in range(self.columnCount()):
            if col == _CB_COL:
                continue  # never recolour the checkbox cell
            it = self.item(table_row, col)
            if it:
                if color is not None:
                    it.setBackground(QBrush(color))
                    it.setForeground(QBrush(_text_color(color)))
                else:
                    it.setBackground(QBrush())
                    it.setForeground(QBrush())
                it.setToolTip(tooltip)
        if self.item(table_row, _ISSUES_COL):
            self.item(table_row, _ISSUES_COL).setText(issues_short)
        # If the row gained an error, disable its checkbox; if fixed, re-enable
        cb = self.item(table_row, _CB_COL)
        if cb:
            if has_error:
                cb.setFlags(Qt.ItemIsEnabled)
                cb.setCheckState(Qt.Unchecked)
            else:
                cb.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
        self.blockSignals(False)
        self.selection_changed.emit()

    # -- filter ---------------------------------------------------------------

    def apply_valid_qty_filter(self, enabled: bool):
        """Show/hide rows where Name, Quantity, Rate, or Unit are missing/zero."""
        self._valid_core_only = enabled
        self._populate()

    # -- sizing ---------------------------------------------------------------

    def _update_height(self):
        """Let the layout engine know our preferred height changed."""
        self.updateGeometry()
        self.setFixedHeight(self.sizeHint().height())

    def sizeHint(self):
        header_h = self.horizontalHeader().height()
        if header_h < 30:
            header_h = 35
        # Sum actual row heights because they can wrap/resize
        rows_h = sum(self.rowHeight(i) for i in range(self.rowCount()))
        return QSize(super().sizeHint().width(), header_h + rows_h + 4)

    def minimumSizeHint(self):
        return self.sizeHint()

    # -- selection ------------------------------------------------------------

    def set_all_checked(self, checked: bool):
        """Check or uncheck all rows that are selectable (no errors)."""
        self.blockSignals(True)
        for row in range(self.rowCount()):
            cb = self.item(row, _CB_COL)
            if cb and (cb.flags() & Qt.ItemIsUserCheckable):
                cb.setCheckState(Qt.Checked if checked else Qt.Unchecked)
        self.blockSignals(False)
        self.selection_changed.emit()

    def selectable_count(self) -> int:
        """Rows that can be checked (no errors)."""
        return sum(
            1
            for row in range(self.rowCount())
            if self.item(row, _CB_COL)
            and (self.item(row, _CB_COL).flags() & Qt.ItemIsUserCheckable)
        )

    def selected_count(self) -> int:
        """Rows currently checked."""
        return sum(
            1
            for row in range(self.rowCount())
            if self.item(row, _CB_COL)
            and self.item(row, _CB_COL).checkState() == Qt.Checked
        )

    def get_selected_valid_records(self) -> list[dict]:
        """Records that are checked AND have no errors."""
        result = []
        for row in range(self.rowCount()):
            cb = self.item(row, _CB_COL)
            if not cb or cb.checkState() != Qt.Checked:
                continue
            rows_idx = cb.data(Qt.UserRole + 1)
            if rows_idx is not None and rows_idx < len(self._rows):
                rec = self._rows[rows_idx]
                if not rec.get("_errors"):
                    result.append(rec)
        return result

    # -- export ---------------------------------------------------------------

    def get_valid_records(self) -> list[dict]:
        return [r for r in self._rows if not r.get("_errors")]

    def error_count(self) -> int:
        return sum(1 for r in self._rows if r.get("_errors"))

    def warn_count(self) -> int:
        return sum(1 for r in self._rows if r.get("_warnings") and not r.get("_errors"))


# ---------------------------------------------------------------------------
# ComponentBlock - group box with a select-all header and one ImportComponentTable
# ---------------------------------------------------------------------------


class ComponentBlock(QGroupBox):
    """
    A styled group box for one component.

    Visual layout (inside the group box):
        ┌─ Component Name ──────────────────────────────┐
        │  [☑ Select all]          (3 / 5 selected)     │  ← inner header
        │  ImportComponentTable                          │
        └───────────────────────────────────────────────┘
    """

    selection_changed = Signal()

    def __init__(
        self, comp_name: str, comp_rows: list[dict], is_uncat: bool = False, parent=None
    ):
        super().__init__(comp_name, parent)
        self.setStyleSheet(
            f"QGroupBox {{ font-weight: bold; font-size: 12px; color: {get_token('text_disabled')}; }}"
            if is_uncat
            else "QGroupBox { font-weight: bold; font-size: 12px; }"
        )

        bl = QVBoxLayout(self)
        bl.setContentsMargins(4, 12, 4, 4)
        bl.setSpacing(4)

        # ── Inner header row: checkbox + count label ──────────────────────
        hdr = QWidget()
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(2, 0, 2, 0)
        hl.setSpacing(6)

        self._chk = QCheckBox("Select all")
        self._chk.setTristate(True)  # tristate for visual only; click logic below
        self._chk.setStyleSheet("font-weight: normal; font-size: 11px;")
        hl.addWidget(self._chk)

        hl.addStretch()

        self._count_lbl = QLabel()
        self._count_lbl.setStyleSheet(f"font-size: 11px; color: {get_token('text_secondary')};")
        hl.addWidget(self._count_lbl)

        bl.addWidget(hdr)

        # ── Table ─────────────────────────────────────────────────────────
        self._tbl = ImportComponentTable(comp_name, comp_rows)
        bl.addWidget(self._tbl)

        # ── Empty placeholder (shown when filter hides everything) ────────
        self._empty_lbl = QLabel(
            "All rows hidden by filter (missing/zero Name, Quantity, Rate, or Unit)."
        )
        self._empty_lbl.setStyleSheet(f"color: {get_token('text_disabled')}; font-style: italic; padding: 4px;")
        self._empty_lbl.setVisible(False)
        bl.addWidget(self._empty_lbl)

        # ── Connections ───────────────────────────────────────────────────
        self._tbl.selection_changed.connect(self._on_table_selection_changed)
        self._chk.clicked.connect(self._on_chk_clicked)

        self._update_chk()

    # -- internal -------------------------------------------------------------

    def _on_table_selection_changed(self):
        self._update_chk()
        self.selection_changed.emit()

    def _on_chk_clicked(self):
        """Check all if not fully selected; uncheck all if fully selected."""
        sel = self._tbl.selected_count()
        total = self._tbl.selectable_count()
        self._tbl.set_all_checked(sel < total)

    def _update_chk(self):
        sel = self._tbl.selected_count()
        total = self._tbl.selectable_count()
        self._count_lbl.setText(f"({sel} / {total} selected)")
        self._chk.blockSignals(True)
        if total == 0 or sel == 0:
            self._chk.setCheckState(Qt.Unchecked)
        elif sel == total:
            self._chk.setCheckState(Qt.Checked)
        else:
            self._chk.setCheckState(Qt.PartiallyChecked)
        self._chk.blockSignals(False)

    # -- public ---------------------------------------------------------------

    def set_all_checked(self, checked: bool):
        self._tbl.set_all_checked(checked)

    def apply_valid_qty_filter(self, enabled: bool):
        self._tbl.apply_valid_qty_filter(enabled)
        has_rows = self._tbl.rowCount() > 0
        self._tbl.setVisible(has_rows)
        self._empty_lbl.setVisible(not has_rows)
        self._update_chk()

    def selected_count(self) -> int:
        return self._tbl.selected_count()

    def selectable_count(self) -> int:
        return self._tbl.selectable_count()

    def get_selected_valid_records(self) -> list[dict]:
        return self._tbl.get_selected_valid_records()

    def error_count(self) -> int:
        return self._tbl.error_count()

    def warn_count(self) -> int:
        return self._tbl.warn_count()


# ---------------------------------------------------------------------------
# SheetPreviewWidget - scroll area containing one group box per component
# ---------------------------------------------------------------------------


class SheetPreviewWidget(QWidget):
    """
    Groups rows by CID#Component into ComponentBlock instances.
    Adds a sheet-level "Select all" checkbox above the scroll area.
    """

    selection_changed = Signal()

    def __init__(self, rows: list[dict], parent=None):
        super().__init__(parent)
        self._all_rows = rows
        self._component_blocks: dict[str, ComponentBlock] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # EC2: sheet had headers but no data rows
        if not rows:
            lbl = QLabel("This sheet has no data rows.")
            lbl.setStyleSheet(f"color: {get_token('text_disabled')}; font-style: italic; padding: 12px;")
            outer.addWidget(lbl)
            return

        # ── Sheet-level select-all header ─────────────────────────────────
        sheet_hdr = QWidget()
        sheet_hdr.setStyleSheet("background: transparent;")
        shl = QHBoxLayout(sheet_hdr)
        shl.setContentsMargins(6, 4, 6, 4)
        shl.setSpacing(8)

        self._sheet_chk = QCheckBox("Select all in sheet")
        self._sheet_chk.setTristate(True)
        self._sheet_chk.setStyleSheet("font-size: 11px;")
        shl.addWidget(self._sheet_chk)
        shl.addStretch()

        self._sheet_count_lbl = QLabel()
        self._sheet_count_lbl.setStyleSheet("font-size: 11px; color: #777;")
        shl.addWidget(self._sheet_count_lbl)

        outer.addWidget(sheet_hdr)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        outer.addWidget(sep)

        # ── Scroll area with one ComponentBlock per component ─────────────
        # Group rows by component name
        grouped: dict[str, list[dict]] = {}
        for record in rows:
            comp = record.get("component", "").strip() or UNCATEGORISED
            grouped.setdefault(comp, []).append(record)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        container = QWidget()
        container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        cl = QVBoxLayout(container)
        cl.setSpacing(10)
        cl.setContentsMargins(4, 4, 4, 4)
        scroll.setWidget(container)
        outer.addWidget(scroll, stretch=1)

        # Render named components first, Uncategorised pinned to bottom
        ordered = [c for c in grouped if c != UNCATEGORISED]
        if UNCATEGORISED in grouped:
            ordered.append(UNCATEGORISED)

        for comp_name in ordered:
            comp_rows = grouped[comp_name]
            is_uncat = comp_name == UNCATEGORISED

            if is_uncat and len(ordered) > 1:
                divider = QFrame()
                divider.setFrameShape(QFrame.HLine)
                divider.setFrameShadow(QFrame.Sunken)
                divider.setStyleSheet("color: #bbb;")
                cl.addWidget(divider)

            block = ComponentBlock(comp_name, comp_rows, is_uncat=is_uncat)
            block.selection_changed.connect(self._on_block_selection_changed)
            cl.addWidget(block)
            self._component_blocks[comp_name] = block

        cl.addStretch()

        self._sheet_chk.clicked.connect(self._on_sheet_chk_clicked)
        self._update_sheet_chk()

    # -- internal -------------------------------------------------------------

    def _on_block_selection_changed(self):
        self._update_sheet_chk()
        self.selection_changed.emit()

    def _on_sheet_chk_clicked(self):
        sel = self.selected_count()
        total = self.selectable_count()
        self.set_all_checked(sel < total)

    def _update_sheet_chk(self):
        if not hasattr(self, "_sheet_chk"):
            return
        sel = self.selected_count()
        total = self.selectable_count()
        self._sheet_count_lbl.setText(f"({sel} / {total} selected)")
        self._sheet_chk.blockSignals(True)
        if total == 0 or sel == 0:
            self._sheet_chk.setCheckState(Qt.Unchecked)
        elif sel == total:
            self._sheet_chk.setCheckState(Qt.Checked)
        else:
            self._sheet_chk.setCheckState(Qt.PartiallyChecked)
        self._sheet_chk.blockSignals(False)

    # -- public ---------------------------------------------------------------

    def set_all_checked(self, checked: bool):
        for block in self._component_blocks.values():
            block.set_all_checked(checked)

    def selected_count(self) -> int:
        return sum(b.selected_count() for b in self._component_blocks.values())

    def selectable_count(self) -> int:
        return sum(b.selectable_count() for b in self._component_blocks.values())

    def apply_valid_qty_filter(self, enabled: bool):
        for block in self._component_blocks.values():
            block.apply_valid_qty_filter(enabled)
        self._update_sheet_chk()

    def get_selected_valid_records(self) -> list[dict]:
        result = []
        for block in self._component_blocks.values():
            result.extend(block.get_selected_valid_records())
        return result

    def get_valid_records(self) -> list[dict]:
        """Kept for backward compatibility - returns all non-error records."""
        result = []
        for block in self._component_blocks.values():
            for rec in block._tbl._rows:
                if not rec.get("_errors"):
                    result.append(rec)
        return result

    def error_count(self) -> int:
        return sum(b.error_count() for b in self._component_blocks.values())

    def warn_count(self) -> int:
        return sum(b.warn_count() for b in self._component_blocks.values())

    @property
    def _rows(self) -> list[dict]:
        """Expose all rows for _collect compatibility."""
        return self._all_rows


class DuplicateComponentDialog(QDialog):
    """
    Shown when incoming component names already exist in the engine data.
    For each conflict the user picks: Merge (append) or Rename (auto-suffix).
    """

    MERGE = "merge"
    RENAME = "rename"

    def __init__(self, conflicts: list[str], parent=None):
        """
        conflicts: list of component names that already exist in the chunk.
        """
        super().__init__(parent)
        self.setWindowTitle("Duplicate Component Names")
        self.setMinimumWidth(520)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self._choices: dict[str, str] = {}  # comp_name → MERGE | RENAME

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 16, 20, 16)

        desc = QLabel(
            "The following component name(s) already exist in the target chunk.\n"
            "Choose what to do for each:"
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)


        for comp in conflicts:
            box = QGroupBox(comp)
            bl = QHBoxLayout(box)
            bg = QButtonGroup(box)

            merge_rb = QRadioButton("Merge  (append rows into existing component)")
            rename_rb = QRadioButton("Rename  (import as new component with suffix)")
            merge_rb.setChecked(True)
            bg.addButton(merge_rb)
            bg.addButton(rename_rb)
            bl.addWidget(merge_rb)
            bl.addWidget(rename_rb)
            layout.addWidget(box)

            # Store reference so we can read it on accept
            self._choices[comp] = self.MERGE
            merge_rb.toggled.connect(
                lambda checked, c=comp: (
                    self._choices.__setitem__(c, self.MERGE) if checked else None
                )
            )
            rename_rb.toggled.connect(
                lambda checked, c=comp: (
                    self._choices.__setitem__(c, self.RENAME) if checked else None
                )
            )

        btn_row = QHBoxLayout()
        ok_btn = QPushButton("Continue")
        ok_btn.setDefault(True)
        ok_btn.setMinimumHeight(34)
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setMinimumHeight(34)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addStretch()
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)

    def get_choices(self) -> dict[str, str]:
        """Returns {component_name: 'merge' | 'rename'}"""
        return dict(self._choices)


def _build_metadata_tab(metadata: list[dict]) -> QWidget:
    """Read-only widget displaying Metadata sheet key→value pairs as label rows."""
    w = QWidget()
    outer = QVBoxLayout(w)
    outer.setContentsMargins(16, 16, 16, 16)
    outer.setSpacing(8)

    if not metadata:
        lbl = QLabel("No metadata entries.")
        lbl.setStyleSheet(f"color: {get_token('text_disabled')}; font-style: italic;")
        outer.addWidget(lbl)
        outer.addStretch()
        return w

    for entry in metadata:
        row_w = QWidget()
        row_l = QHBoxLayout(row_w)
        row_l.setContentsMargins(0, 0, 0, 0)
        row_l.setSpacing(12)

        key_lbl = QLabel(f"<b>{entry.get('key', '')}</b>")
        key_lbl.setFixedWidth(160)
        key_lbl.setStyleSheet("font-size: 12px;")

        val_lbl = QLabel(entry.get("value", "") or "-")
        val_lbl.setStyleSheet(f"font-size: 12px; color: {get_token('text_secondary')};")

        row_l.addWidget(key_lbl)
        row_l.addWidget(val_lbl, stretch=1)
        outer.addWidget(row_w)

    outer.addStretch()
    return w


class ImportPreviewWindow(QDialog):
    """
    Main preview dialog.

    One tab per sheet.  Footer shows error / warning summary.
    "Import Valid Rows" skips rows that still have errors.
    "Import All" imports everything (errors included - user accepted risk).
    """

    def __init__(
        self,
        parsed: dict[str, list[dict]],
        existing_components: dict[str, set[str]] | None = None,
        manager=None,
        metadata: list[dict] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Import Preview - Review & Correct")
        self.setMinimumSize(900, 500)
        self.setWindowFlags(
            Qt.Window
            | Qt.WindowTitleHint
            | Qt.WindowSystemMenuHint
            | Qt.WindowCloseButtonHint
            | Qt.WindowMaximizeButtonHint
        )
        self._parsed = parsed
        self._sheet_tables: dict[str, SheetPreviewWidget] = {}
        self._existing_components: dict[str, set[str]] = existing_components or {}
        self._manager = manager

        root = QVBoxLayout(self)
        root.setSpacing(6)
        root.setContentsMargins(12, 12, 12, 12)

        # ── Top bar: info + select-all + filter ───────────────────────────────
        top_bar = QHBoxLayout()

        info = QLabel(
            "<b>Double-click</b> a cell to edit.  "
            "<span style='color:#c0392b'>■</span> Red = errors (cannot import).  "
            "<span style='color:#d68910'>■</span> Yellow = warnings."
        )
        info.setWordWrap(True)
        info.setStyleSheet("font-size: 11px; color: #555;")
        top_bar.addWidget(info, stretch=1)

        # Global select-all checkbox
        self._select_all_chk = QCheckBox("Select all")
        self._select_all_chk.setTristate(True)
        self._select_all_chk.setToolTip(
            "Check / uncheck every selectable row across all sheets"
        )
        self._select_all_chk.clicked.connect(self._on_select_all_clicked)
        top_bar.addWidget(self._select_all_chk)

        self._select_all_count_lbl = QLabel()
        self._select_all_count_lbl.setStyleSheet("font-size: 11px; color: #777;")
        top_bar.addWidget(self._select_all_count_lbl)

        top_bar.addSpacing(16)

        self._qty_chk = QCheckBox("Valid rows only")
        self._qty_chk.setChecked(False)
        self._qty_chk.setToolTip(
            "Hide rows where Name, Quantity, Rate, or Unit are missing or zero"
        )
        self._qty_chk.toggled.connect(self._on_qty_filter_changed)
        top_bar.addWidget(self._qty_chk)

        root.addLayout(top_bar)

        # ── Pre-mark rows whose name already exists in the engine ────────────
        _chunk_cache: dict[str, dict] = {}
        _engine = (
            getattr(getattr(manager, "controller", None), "engine", None)
            if manager
            else None
        )
        if _engine:
            for _rows in parsed.values():
                for rec in _rows:
                    if rec.get("_errors"):
                        continue  # already invalid - skip
                    _chunk_key = rec.get("_chunk_key", FALLBACK_CHUNK)
                    _comp = rec.get("component", "").strip()
                    _name = rec.get("name", "").strip().lower()
                    if not _name or not _comp:
                        continue
                    if _chunk_key not in _chunk_cache:
                        try:
                            _chunk_cache[_chunk_key] = (
                                _engine.fetch_chunk(_chunk_key) or {}
                            )
                        except Exception:
                            _chunk_cache[_chunk_key] = {}
                    _taken = {
                        item.get("values", {}).get("material_name", "").strip().lower()
                        for item in _chunk_cache[_chunk_key].get(_comp, [])
                        if not item.get("state", {}).get("in_trash", False)
                    }
                    if _name in _taken:
                        rec["_duplicate_name"] = True

        # ── Overwrite warning banner (shown only when duplicates exist) ───────
        _dup_count = sum(
            1
            for _rows in parsed.values()
            for rec in _rows
            if rec.get("_duplicate_name")
        )
        if _dup_count:
            warn_frame = QFrame()
            warn_frame.setFrameShape(QFrame.StyledPanel)
            warn_frame.setStyleSheet(
                f"background:{get_token('warning')}; border-radius:4px; padding:2px;"
            )
            warn_layout = QHBoxLayout(warn_frame)
            warn_layout.setContentsMargins(10, 6, 10, 6)
            warn_lbl = QLabel(
                f"⚠  <b>{_dup_count} row(s)</b> in this file already exist in the "
                f"project (matched by name &amp; component, case-insensitive). "
                f"They are <b>unchecked by default</b> - check them to overwrite."
            )
            warn_lbl.setWordWrap(True)
            warn_lbl.setStyleSheet(f"color:{_text_color(QColor(get_token('warning'))).name()}; background:transparent;")
            warn_layout.addWidget(warn_lbl)
            root.addWidget(warn_frame)

        # ── Tabs - one per sheet ─────────────────────────────────────────────
        self.tabs = QTabWidget()
        root.addWidget(self.tabs, stretch=1)

        for sheet_name, rows in parsed.items():
            widget = SheetPreviewWidget(rows)
            widget.selection_changed.connect(self._on_selection_changed)
            self._sheet_tables[sheet_name] = widget

            tab_label = self._tab_label(sheet_name, rows)
            self.tabs.addTab(widget, tab_label)

        # Metadata tab - read-only, shown only when sheet was present
        if metadata:
            self.tabs.addTab(_build_metadata_tab(metadata), "Metadata")

        # ── Summary label ────────────────────────────────────────────────────
        self._summary_lbl = QLabel()
        self._summary_lbl.setStyleSheet("font-size: 11px;")
        root.addWidget(self._summary_lbl)
        self._refresh_summary()

        print("[IPW] G. done")
        # ── Buttons ──────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()

        self._import_valid_btn = QPushButton("Import Rows")
        self._import_valid_btn.setMinimumHeight(34)
        self._import_valid_btn.setToolTip(
            "Import selected rows - error rows are always skipped, warnings are included"
        )
        self._import_valid_btn.clicked.connect(self._on_import_valid)

        btn_row.addStretch()
        btn_row.addWidget(self._import_valid_btn)
        root.addLayout(btn_row)

    # -- helpers --------------------------------------------------------------

    def _on_qty_filter_changed(self, enabled: bool):
        for widget in self._sheet_tables.values():
            widget.apply_valid_qty_filter(enabled)
        self._on_selection_changed()

    def _on_selection_changed(self):
        """Called whenever any row checkbox changes - update top-level state."""
        self._refresh_summary()

    def _on_select_all_clicked(self):
        sel = sum(w.selected_count() for w in self._sheet_tables.values())
        total = sum(w.selectable_count() for w in self._sheet_tables.values())
        check = sel < total
        for widget in self._sheet_tables.values():
            widget.set_all_checked(check)

    def _tab_label(self, sheet_name: str, rows: list[dict]) -> str:
        if not rows:
            return sheet_name
        errs = sum(1 for r in rows if r.get("_errors"))
        if errs:
            return f"{sheet_name} ({errs} ✗)"
        warns = sum(1 for r in rows if r.get("_warnings"))
        if warns:
            return f"{sheet_name} ({warns} ⚠)"
        return sheet_name

    def _refresh_summary(self):
        total = sum(len(rows) for rows in self._parsed.values())
        errs = sum(w.error_count() for w in self._sheet_tables.values())
        warns = sum(w.warn_count() for w in self._sheet_tables.values())
        valid = total - errs
        sel = sum(w.selected_count() for w in self._sheet_tables.values())
        selectable = sum(w.selectable_count() for w in self._sheet_tables.values())

        self._summary_lbl.setText(
            f"Total rows: <b>{total}</b>  |  "
            f"<span style='color:#c0392b'>Errors: {errs}</span>  |  "
            f"<span style='color:#d68910'>Warnings: {warns}</span>  |  "
            f"<span style='color:#1a7a43'>Valid: {valid}</span>  |  "
            f"<b>Selected: {sel}</b>"
        )

        # Update import button label
        if hasattr(self, "_import_valid_btn"):
            self._import_valid_btn.setText(f"Import {sel} Row{'s' if sel != 1 else ''}")

        # Update top-level select-all checkbox
        if hasattr(self, "_select_all_chk"):
            self._select_all_count_lbl.setText(f"({sel} / {selectable})")
            self._select_all_chk.blockSignals(True)
            if selectable == 0 or sel == 0:
                self._select_all_chk.setCheckState(Qt.Unchecked)
            elif sel == selectable:
                self._select_all_chk.setCheckState(Qt.Checked)
            else:
                self._select_all_chk.setCheckState(Qt.PartiallyChecked)
            self._select_all_chk.blockSignals(False)

    # -- actions --------------------------------------------------------------

    def _collect(self) -> dict[str, dict[str, list[dict]]] | None:
        """
        Returns { chunk_key: { component_name: [material_dict, …] } }
        or None if the user cancelled the duplicate-resolution dialog.

        Only collects rows that are both selected AND have no errors.
        """
        # Build raw grouped data first
        raw: dict[str, dict[str, list[dict]]] = {}
        for sheet_name, widget in self._sheet_tables.items():
            records = widget.get_selected_valid_records()
            for record in records:
                mat = record_to_material_dict(record)
                chunk = mat.pop("_chunk_key", FALLBACK_CHUNK)
                comp = mat.pop("_component", "") or sheet_name
                raw.setdefault(chunk, {}).setdefault(comp, []).append(mat)

        # Detect duplicate component names against existing engine data
        conflicts: list[str] = []
        for chunk_key, components in raw.items():
            existing = self._existing_components.get(chunk_key, set())
            for comp_name in components:
                if comp_name in existing:
                    conflicts.append(comp_name)

        choices: dict[str, str] = {}
        if conflicts:
            dlg = DuplicateComponentDialog(conflicts, parent=self)
            if dlg.exec() != QDialog.Accepted:
                return None
            choices = dlg.get_choices()

        # Apply rename choices - auto-suffix with " (Imported)"
        # and increment if that also clashes
        result: dict[str, dict[str, list[dict]]] = {}
        for chunk_key, components in raw.items():
            existing = self._existing_components.get(chunk_key, set())
            for comp_name, rows in components.items():
                action = choices.get(comp_name, DuplicateComponentDialog.MERGE)
                if comp_name in existing and action == DuplicateComponentDialog.RENAME:
                    base = f"{comp_name} (Imported)"
                    candidate = base
                    counter = 2
                    while candidate in existing or candidate in result.get(
                        chunk_key, {}
                    ):
                        candidate = f"{base} {counter}"
                        counter += 1
                    final_name = candidate
                else:
                    final_name = comp_name
                result.setdefault(chunk_key, {}).setdefault(final_name, []).extend(rows)

        return result

    def _on_import_valid(self):
        data = self._collect()
        if data is None:
            return
        total = sum(len(rows) for comp in data.values() for rows in comp.values())
        if total == 0:
            QMessageBox.warning(
                self,
                "Nothing to Import",
                "No rows selected for import, or all selected rows have errors.",
            )
            return
        imported, skipped, failures = _emit_result(data, self._manager)
        self._show_import_result(imported, skipped, failures)
        self.accept()

    def _show_import_result(self, imported: int, skipped: int, failures: list[str]):
        if not failures:
            QMessageBox.information(
                self, "Import Complete", f"{imported} row(s) imported."
            )
            return

        full_text = "\n".join(f"• {f}" for f in failures)

        dlg = QDialog(self)
        dlg.setWindowTitle("Import Complete with Issues")
        dlg.setWindowFlags(dlg.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        dlg.setMinimumWidth(560)

        # Bound height to 70% of screen so it never goes off-screen
        screen = QApplication.primaryScreen().availableGeometry()
        dlg.setMaximumHeight(int(screen.height() * 0.70))

        layout = QVBoxLayout(dlg)
        layout.setSpacing(10)

        summary = QLabel(
            f"<b>{imported}</b> row(s) imported.  " f"<b>{skipped}</b> row(s) skipped:"
        )
        layout.addWidget(summary)


        txt = QPlainTextEdit()
        txt.setReadOnly(True)
        txt.setPlainText(full_text)
        txt.setMinimumHeight(180)
        layout.addWidget(txt)

        btn_row = QHBoxLayout()
        copy_btn = QPushButton("Copy to Clipboard")
        copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(full_text))
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dlg.accept)
        btn_row.addWidget(copy_btn)
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        dlg.exec()


# ---------------------------------------------------------------------------
# Output - replace print() with your controller / engine write call
# ---------------------------------------------------------------------------


def _emit_result(
    data: dict[str, dict[str, list[dict]]],
    manager=None,
) -> tuple[int, int, list[str]]:
    """
    Write imported rows into the engine via StructureManagerWidget.add_material().
    Returns (imported_count, skipped_count, failure_messages).

    If *manager* is None (standalone / test mode), falls back to printing.
    """
    if manager is None:
        print("\n===== IMPORT RESULT =====")
        for chunk_key, components in data.items():
            print(f"\n[chunk: {chunk_key}]")
            for comp_name, rows in components.items():
                print(f"  [component: {comp_name}]  ({len(rows)} rows)")
                for row in rows:
                    try:
                        print("   ", json.dumps(row, ensure_ascii=False))
                    except (UnicodeEncodeError, UnicodeDecodeError):
                        print("   ", json.dumps(row, ensure_ascii=True))
        print("=========================\n")
        return (
            len([r for c in data.values() for rows in c.values() for r in rows]),
            0,
            [],
        )

    imported = 0
    skipped = 0
    failures: list[str] = []

    # Validate controller and engine are alive before touching anything
    if not manager or not getattr(manager, "controller", None):
        return 0, 0, ["Import aborted: manager has no controller."]
    if not getattr(manager.controller, "engine", None):
        return 0, 0, ["Import aborted: controller has no engine."]

    # Track names added during this import batch to catch within-sheet duplicates
    # Key: (chunk_key, comp_name) → set of lowercased material_names written so far
    _batch_seen: dict[tuple, set] = {}

    for chunk_key, components in data.items():
        for comp_name, rows in components.items():

            # Ensure component bucket exists before writing any rows
            try:
                current = manager.controller.engine.fetch_chunk(chunk_key) or {}
                if comp_name not in current:
                    current[comp_name] = []
                    manager.controller.engine.stage_update(
                        chunk_name=chunk_key, data=current
                    )
            except Exception as exc:
                failures.append(
                    f"[{chunk_key} / {comp_name}] Could not initialise component: {exc}"
                )
                skipped += len(rows)
                continue

            batch_key = (chunk_key, comp_name)
            _batch_seen.setdefault(batch_key, set())

            for row_idx, values_dict in enumerate(rows):
                mat_name = values_dict.get("values", {}).get("material_name", f"row {row_idx + 1}")
                try:
                    # --- Within-batch duplicate check ------------------------
                    if mat_name.strip().lower() in _batch_seen[batch_key]:
                        failures.append(
                            f'[{comp_name}] "{mat_name}" skipped - '
                            f"duplicate name in this import batch"
                        )
                        skipped += 1
                        continue

                    # --- Pre-write validation --------------------------------
                    force_overwrite = bool(values_dict.pop("_force_overwrite", False))
                    reasons = _validate_for_engine(
                        values_dict,
                        comp_name,
                        chunk_key,
                        manager,
                        force_overwrite=force_overwrite,
                    )
                    if reasons:
                        failures.append(
                            f'[{comp_name}] "{mat_name}" skipped - '
                            + "; ".join(reasons)
                        )
                        skipped += 1
                        continue

                    # --- Write to engine -------------------------------------
                    if force_overwrite:
                        # Update the existing entry in-place (overwrite)
                        included_carbon = values_dict["state"].get("included_in_carbon_emission", False)
                        included_recycle = values_dict["state"].get("included_in_recyclability", False)

                        # Preserve SOR reference ID
                        _ref_id = values_dict.get("values", {}).get("src_id")

                        _engine = manager.controller.engine
                        _chunk_data = _engine.fetch_chunk(chunk_key) or {}
                        _items = _chunk_data.get(comp_name, [])
                        _name_lower = mat_name.strip().lower()
                        _found = False

                        for _item in _items:
                            _ev = (
                                _item.get("values", {})
                                .get("material_name", "")
                                .strip()
                                .lower()
                            )
                            if _ev == _name_lower and not _item.get("state", {}).get(
                                "in_trash", False
                            ):
                                _item["values"] = dict(values_dict["values"])
                                _item["meta"]["modified_on"] = _dt.datetime.now().isoformat()
                                _item["meta"]["source"] = "excel"  # re-import resets to clean excel
                                _item["meta"]["db_original"] = values_dict["meta"].get("db_original", {})
                                _item["state"]["included_in_carbon_emission"] = included_carbon
                                _item["state"]["included_in_recyclability"] = included_recycle
                                _found = True
                                break

                        if _found:
                            _engine.stage_update(chunk_name=chunk_key, data=_chunk_data)
                        else:
                            # Fallback if item was deleted
                            manager.add_material(comp_name, values_dict)

                    elif chunk_key != manager.chunk_name:
                        # Route to a different chunk via a lightweight proxy
                        class _Proxy:
                            def __init__(self, mgr, chunk):
                                self.controller = mgr.controller
                                self.chunk_name = chunk
                                self.save_current_state = mgr.save_current_state
                                self.on_refresh = lambda: None  # deferred
                                self._page_registry = {}
                                self._del_comp_btn_map = {}

                            def _get_registry(self):
                                return self.controller.engine.fetch_chunk("str_component_registry") or {}

                            def _save_registry(self, registry):
                                self.controller.engine.stage_update(
                                    chunk_name="str_component_registry", data=registry
                                )

                        proxy = _Proxy(manager, chunk_key)
                        from .widgets.manager import StructureManagerWidget as _SMW

                        _SMW.add_material(proxy, comp_name, dict(values_dict))
                    else:
                        # Suppress per-row on_refresh - do one batch refresh after
                        _orig_refresh = manager.on_refresh
                        manager.on_refresh = lambda: None
                        try:
                            manager.add_material(comp_name, dict(values_dict))
                        finally:
                            manager.on_refresh = _orig_refresh

                    _batch_seen[batch_key].add(mat_name.strip().lower())
                    imported += 1

                except Exception as exc:

                    failures.append(
                        f'[{comp_name}] "{mat_name}" failed - {exc}\n'
                        + traceback.format_exc(limit=3)
                    )
                    skipped += 1

    # Single batch refresh + save after all rows written
    try:
        manager.save_current_state()
        manager.on_refresh()
    except Exception as exc:
        failures.append(f"Warning: post-import refresh failed - {exc}")

    return imported, skipped, failures


# ---------------------------------------------------------------------------
# Standalone test runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":

    app = QApplication.instance() or QApplication(sys.argv)
    path, _ = QFileDialog.getOpenFileName(
        None, "Select Excel File", "", "Excel Files (*.xlsx *.xls)"
    )
    if path:
        result = parse_excel(path)
        materials = verify_schema(result["materials"])
        preview = ImportPreviewWindow(materials, metadata=result["metadata"])
        preview.showMaximized()
        preview.exec()


