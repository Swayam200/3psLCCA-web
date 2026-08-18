"""
gui/api/pages/machinery_emissions.py

Registers "machinery_emissions_data" (the "Machinery/Equipment Emissions" tab
of Carbon Emissions Data). Same Tier C shape as social_cost_data
(gui/api/pages/carbon_emission.py) - `widget_map["Carbon Emissions Data"]`
only gives back the CarbonEmissionTabView container, which has no
get_data_dict()/load_data_dict() of its own, so this registers field_defs=
None + refresh_via_signal=True: the API writes via controller.save_chunk_data()
only, and the tab repaints itself off an explicit refresh_widget hook.

Two mutually exclusive modes, selected by "mode" (matches the GUI's radio
toggle): "detailed" (a table of equipment rows) or "lumpsum" (aggregate
electricity + fuel consumption). Both are always stored, same as
social_cost_data's source/ricke/custom - switching mode doesn't lose the
other's inputs.

Detailed-table writes are ROW-GRANULAR, not whole-chunk-granular - one row
op per POST (mirrors structure.py's "no bulk" rule): send
{"detailed": {"rows": [row_patch]}} where a patch WITH "row_index" edits (or,
with "delete": true, removes) that existing row, and a patch WITHOUT
"row_index" appends a new one. This reuses the exact 6 fields the GUI's own
"Edit Equipment" dialog (_EditRowDialog in
gui/components/carbon_emission/widgets/machinery_emissions.py) collects:
name, source, rate, hrs, days, ef.

Rows have no persistent id (the GUI itself addresses them by row position
only - _open_edit_dialog/_delete_row both take a row index) - so this API
does the same rather than inventing new id semantics the GUI doesn't have.
row_index is only stable until the next row is added/removed; re-GET after
any add/delete before addressing a row again.

"total_kgCO2e" (plus, for detailed mode, diesel/electricity subtotals) is
server-computed from whichever mode is active - mirrors
MachineryEmissions.collect_data()'s own total, not caller-writable.
"""

import copy

from three_ps_lcca_gui.gui.components.carbon_emission.main import CarbonEmissionTabView
from three_ps_lcca_gui.gui.components.carbon_emission.widgets.machinery_emissions import (
    CONSUMPTION_UNIT,
    EF_DEFAULTS,
    ENERGY_SOURCES,
    MachineryEmissions,
)
from ..registry import register_chunk

_PAGE_NAME = "Carbon Emissions Data"
_CHUNK = "machinery_emissions_data"

_MODES = ("detailed", "lumpsum")

_LUMPSUM_FIELDS = {
    "elec_consumption_per_day": ("float", 0.0, 1e12, "kWh/day"),
    "elec_days": ("int", 0, 9999, "days"),
    "elec_ef": ("float", 0.0, 999.0, "kg CO2e/kWh"),
    "fuel_consumption_per_day": ("float", 0.0, 1e12, "litres/day"),
    "fuel_days": ("int", 0, 9999, "days"),
    "fuel_ef": ("float", 0.0, 999.0, "kg CO2e/litre"),
}
_LUMPSUM_DEFAULTS = {
    "elec_consumption_per_day": 0.0, "elec_days": 0, "elec_ef": 0.0,
    "fuel_consumption_per_day": 0.0, "fuel_days": 0, "fuel_ef": 0.0,
}

_ROW_FIELDS = {
    "name": ("str", None),
    "source": ("combo", ENERGY_SOURCES),
    "rate": ("float", (0.0, 1e9)),
    "hrs": ("float", (0.0, 24.0)),
    "days": ("int", (0, 9999)),
    "ef": ("float", (0.0, 999.0)),
}
_ROW_DEFAULTS = {"name": "", "source": ENERGY_SOURCES[0], "rate": 0.0, "hrs": 0.0, "days": 0, "ef": 0.0}
_ROW_PATCH_KEYS = {"row_index", "delete"} | set(_ROW_FIELDS)

_TOP_KEYS = {"mode", "remarks", "lumpsum", "detailed"}


def _machinery_schema() -> dict:
    return {
        "chunk": _CHUNK,
        "description": (
            "Machinery/Equipment Emissions tab. Two mutually exclusive "
            "modes, selected by \"mode\": \"detailed\" (a table of "
            "equipment rows, each with its own consumption rate/hours/"
            "days/emission factor) or \"lumpsum\" (aggregate electricity + "
            "fuel consumption, no per-equipment breakdown). Both are always "
            "stored regardless of which is active, so switching mode "
            "doesn't lose the other's inputs. \"result\" is server-computed "
            "from whichever mode is active - never caller-writable."
        ),
        "mode_note": (
            "\"mode\" is the toggle shown as \"Detailed Equipment List\" / "
            "\"Lump Sum\" radio buttons in the GUI. Set it to \"detailed\" "
            "to use the equipment table below, or \"lumpsum\" to use "
            "aggregate consumption instead."
        ),
        "update_semantics": {
            "granularity": (
                "PATCH-like: send any subset of \"mode\"/\"remarks\"/"
                "\"lumpsum\"/\"detailed\" - omitted keys keep their current "
                "value. \"lumpsum\" is merged key-by-key, not replaced "
                "wholesale."
            ),
            "detailed_rows_are_row_granular": (
                "\"detailed\": {\"rows\": [row_patch]} takes EXACTLY ONE "
                "row_patch per request - no bulk edits, one API call per "
                "equipment change (same rule Construction Works Data's "
                "entry-patch endpoint uses). A patch WITH \"row_index\" "
                "edits that existing row (only the fields you include "
                "change; with \"delete\": true it's removed instead, and no "
                "other field key may be set in that same patch). A patch "
                "WITHOUT \"row_index\" appends a new row - any omitted "
                "field defaults the same way the GUI's '+ Add Equipment' "
                "button does (name=\"\", source=first option, rate/hrs/"
                "ef=0.0, days=0) - the GUI's auto-fill of \"ef\" to a "
                "per-source default when you change \"source\" in the Edit "
                "Equipment dialog is a UI convenience only and is NOT "
                "replicated here - send \"ef\" explicitly."
            ),
            "row_index_is_positional": (
                "Rows have no persistent id - same as the GUI, which "
                "addresses table rows by their on-screen position, not a "
                "stable key. row_index is 0-based and only valid until the "
                "next row is added or removed; GET this chunk again to see "
                "current indices before addressing a row after any add/"
                "delete."
            ),
            "server_owned": (
                "\"total_kgCO2e\" (and, in detailed mode, "
                "\"diesel_subtotal_kgCO2e\"/\"electricity_subtotal_kgCO2e\") "
                "is recomputed from whichever mode is active after this "
                "patch - sending it directly is rejected."
            ),
        },
        "field_groups": {
            "mode": {
                "label": "Input Method",
                "field_type": "combo",
                "options": list(_MODES),
            },
            "remarks": {
                "label": "Notes",
                "field_type": "text",
                "description": "Free-text notes shown under the tab (plain text or simple HTML, same as the GUI's Notes editor).",
            },
            "lumpsum": {
                "label": "Lump Sum inputs",
                "active_when": "mode == 'lumpsum'",
                "fields": [
                    {"key": key, "field_type": t, "min": lo, "max": hi, "unit": unit}
                    for key, (t, lo, hi, unit) in _LUMPSUM_FIELDS.items()
                ],
            },
            "detailed": {
                "label": "Detailed Equipment List",
                "active_when": "mode == 'detailed'",
                "description": (
                    "{\"rows\": [{\"name\", \"source\", \"rate\", \"hrs\", "
                    "\"days\", \"ef\"}, ...]} - one entry per equipment "
                    "item, same fields as the GUI's Edit Equipment dialog. "
                    "Writes to this are row-granular, see "
                    "update_semantics.detailed_rows_are_row_granular."
                ),
                "row_fields": {
                    "name": "string - equipment name",
                    "source": {"field_type": "combo", "options": list(ENERGY_SOURCES)},
                    "rate": {"field_type": "float", "min": 0.0, "max": 1e9, "description": "Fuel/power rating per hour (unit depends on source: l/hr for Diesel, kW for Electricity, units/hr for Other)"},
                    "hrs": {"field_type": "float", "min": 0.0, "max": 24.0, "unit": "hrs/day"},
                    "days": {"field_type": "int", "min": 0, "max": 9999, "unit": "days"},
                    "ef": {"field_type": "float", "min": 0.0, "max": 999.0, "unit": "kg CO2e/unit", "description": f"Emission factor. GUI defaults by source: {EF_DEFAULTS}"},
                },
                "consumption_units_by_source": CONSUMPTION_UNIT,
            },
            "result": {
                "label": "Computed totals",
                "description": "Read-only. Recomputed by the server whenever mode/lumpsum/detailed rows change.",
                "fields": [
                    {"key": "total_kgCO2e", "field_type": "float", "unit": "kg CO2e"},
                    {"key": "diesel_subtotal_kgCO2e", "field_type": "float", "unit": "kg CO2e", "description": "detailed mode only"},
                    {"key": "electricity_subtotal_kgCO2e", "field_type": "float", "unit": "kg CO2e", "description": "detailed mode only"},
                ],
            },
        },
        "example_post_body_add_row": {
            "mode": "detailed",
            "detailed": {"rows": [
                {"name": "DG set", "source": "Diesel", "rate": 4.0, "hrs": 8.0, "days": 30, "ef": 2.69},
            ]},
        },
        "example_post_body_edit_row": {
            "detailed": {"rows": [{"row_index": 0, "hrs": 6.0, "days": 25}]},
        },
        "example_post_body_delete_row": {
            "detailed": {"rows": [{"row_index": 0, "delete": True}]},
        },
        "example_post_body_lumpsum": {
            "mode": "lumpsum",
            "lumpsum": {"elec_consumption_per_day": 50.0, "elec_days": 20, "elec_ef": 0.71},
        },
    }


def _check_row_fields(where: str, patch: dict) -> list[str]:
    errors = []
    unknown = set(patch) - _ROW_PATCH_KEYS
    if unknown:
        errors.append(f"{where}: unrecognized key(s) {sorted(unknown)} - allowed: {sorted(_ROW_PATCH_KEYS)}")

    is_delete = patch.get("delete", False)
    if not isinstance(is_delete, bool):
        errors.append(f"{where}.delete: must be a boolean")
    if is_delete and (set(patch) - {"row_index", "delete"}):
        errors.append(f"{where}: 'delete': true may not be combined with field edits in the same patch")

    if "row_index" in patch:
        if isinstance(patch["row_index"], bool) or not isinstance(patch["row_index"], int):
            errors.append(f"{where}.row_index: must be an integer")

    if is_delete:
        return errors

    for key, value in patch.items():
        if key not in _ROW_FIELDS:
            continue  # already reported above via `unknown`
        kind = _ROW_FIELDS[key][0]
        if kind == "str":
            if not isinstance(value, str):
                errors.append(f"{where}.{key}: must be a string, got {value!r}")
        elif kind == "combo":
            options = _ROW_FIELDS[key][1]
            if value not in options:
                errors.append(f"{where}.{key}: {value!r} is not a valid option - must be one of {list(options)}")
        elif kind in ("float", "int"):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                errors.append(f"{where}.{key}: must be a number, got {value!r}")
            else:
                lo, hi = _ROW_FIELDS[key][1]
                if not (lo <= value <= hi):
                    errors.append(f"{where}.{key}: {value} is out of range [{lo}, {hi}]")
    return errors


def _check_detailed_patch(patch) -> list[str]:
    if not isinstance(patch, dict):
        return ["'detailed' must be an object"]
    unknown = set(patch) - {"rows"}
    if unknown:
        return [f"'detailed': unrecognized key(s) {sorted(unknown)} - only 'rows' is allowed"]
    if "rows" not in patch:
        return []
    rows = patch["rows"]
    if not isinstance(rows, list) or len(rows) != 1:
        got = len(rows) if isinstance(rows, list) else type(rows).__name__
        return [f"'detailed.rows': exactly one row_patch is allowed per request (got {got}) - bulk operations are not supported; send one POST per equipment change"]
    row_patch = rows[0]
    if not isinstance(row_patch, dict):
        return ["'detailed.rows[0]': must be an object"]
    return _check_row_fields("detailed.rows[0]", row_patch)


def _check_lumpsum_patch(patch) -> list[str]:
    if not isinstance(patch, dict):
        return ["'lumpsum' must be an object"]
    unknown = set(patch) - set(_LUMPSUM_FIELDS)
    errors = [f"'lumpsum': unrecognized key(s) {sorted(unknown)} - allowed: {sorted(_LUMPSUM_FIELDS)}"] if unknown else []
    for key, value in patch.items():
        if key not in _LUMPSUM_FIELDS:
            continue  # already reported above via `unknown`
        kind, lo, hi, _unit = _LUMPSUM_FIELDS[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            errors.append(f"lumpsum.{key}: must be a number, got {value!r}")
            continue
        if not (lo <= value <= hi):
            errors.append(f"lumpsum.{key}: {value} is out of range [{lo}, {hi}]")
    return errors


def _apply_row_patch(rows: list, patch: dict) -> list[str]:
    """Mutates `rows` in place. Returns errors (empty on success)."""
    if "row_index" in patch:
        idx = patch["row_index"]
        if not (0 <= idx < len(rows)):
            return [f"detailed.rows[0].row_index: {idx} is out of range - this chunk currently has {len(rows)} row(s) (0..{len(rows) - 1})"]
        if patch.get("delete", False):
            rows.pop(idx)
            return []
        row = rows[idx]
        for key in _ROW_FIELDS:
            if key in patch:
                row[key] = patch[key]
        return []
    if patch.get("delete", False):
        return ["detailed.rows[0]: 'delete': true requires 'row_index'"]
    new_row = dict(_ROW_DEFAULTS)
    for key in _ROW_FIELDS:
        if key in patch:
            new_row[key] = patch[key]
    rows.append(new_row)
    return []


def _result_for(merged: dict) -> dict:
    mode = merged.get("mode")
    if mode == "lumpsum":
        ls = merged.get("lumpsum", {})
        elec = ls.get("elec_consumption_per_day", 0.0) * ls.get("elec_days", 0) * ls.get("elec_ef", 0.0)
        fuel = ls.get("fuel_consumption_per_day", 0.0) * ls.get("fuel_days", 0) * ls.get("fuel_ef", 0.0)
        return {"total_kgCO2e": round(elec + fuel, 2)}

    rows = merged.get("detailed", {}).get("rows", [])

    def _emissions(r: dict) -> float:
        return r.get("rate", 0.0) * r.get("hrs", 0.0) * r.get("days", 0) * r.get("ef", 0.0)

    diesel = sum(_emissions(r) for r in rows if r.get("source") == "Diesel")
    other = sum(_emissions(r) for r in rows if r.get("source") != "Diesel")
    return {
        "total_kgCO2e": round(diesel + other, 2),
        "diesel_subtotal_kgCO2e": round(diesel, 2),
        "electricity_subtotal_kgCO2e": round(other, 2),
    }


def _apply(current: dict, payload: dict) -> tuple[dict, list[str]]:
    """Pure merge + validate of `payload` into `current`. Returns
    (merged, errors); on any error the merge result must be discarded."""
    errors: list[str] = []
    if not isinstance(payload, dict) or not payload:
        return current, ["payload must be a non-empty object with any of: mode, remarks, lumpsum, detailed"]

    unknown = set(payload) - _TOP_KEYS
    if unknown:
        errors.append(f"unrecognized key(s) {sorted(unknown)} - allowed: {sorted(_TOP_KEYS)} (\"total_kgCO2e\" and subtotals are server-computed, never caller-writable)")

    if "mode" in payload and payload["mode"] not in _MODES:
        errors.append(f"'mode': {payload['mode']!r} is not a valid option - must be one of {list(_MODES)}")
    if "remarks" in payload and not isinstance(payload["remarks"], str):
        errors.append("'remarks': must be a string")
    if "lumpsum" in payload:
        errors.extend(_check_lumpsum_patch(payload["lumpsum"]))
    if "detailed" in payload:
        errors.extend(_check_detailed_patch(payload["detailed"]))

    if errors:
        return current, errors

    merged = copy.deepcopy(current)
    merged.setdefault("mode", "detailed")
    merged.setdefault("remarks", "")
    merged.setdefault("lumpsum", dict(_LUMPSUM_DEFAULTS))
    merged.setdefault("detailed", {}).setdefault("rows", [])

    if "mode" in payload:
        merged["mode"] = payload["mode"]
    if "remarks" in payload:
        merged["remarks"] = payload["remarks"]
    if "lumpsum" in payload:
        merged["lumpsum"].update(payload["lumpsum"])

    row_patch = payload.get("detailed", {}).get("rows")
    if row_patch:
        row_errors = _apply_row_patch(merged["detailed"]["rows"], row_patch[0])
        if row_errors:
            return current, row_errors

    merged.pop("diesel_subtotal_kgCO2e", None)
    merged.pop("electricity_subtotal_kgCO2e", None)
    merged.update(_result_for(merged))

    return merged, errors


def _validate_payload(payload: dict, current: dict | None) -> list[str]:
    if current is None:
        # Server-side pre-check without stored data (Flask worker thread,
        # before the main-thread round-trip): structural checks only.
        if not isinstance(payload, dict) or not payload:
            return ["payload must be a non-empty object with any of: mode, remarks, lumpsum, detailed"]
        unknown = set(payload) - _TOP_KEYS
        errors = [f"unrecognized key(s) {sorted(unknown)} - allowed: {sorted(_TOP_KEYS)}"] if unknown else []
        if "lumpsum" in payload and not isinstance(payload["lumpsum"], dict):
            errors.append("'lumpsum' must be an object")
        if "detailed" in payload and not isinstance(payload["detailed"], dict):
            errors.append("'detailed' must be an object")
        return errors
    _merged, errors = _apply(current, payload)
    return errors


def _merge_payload(current: dict, payload: dict) -> dict:
    merged, _errors = _apply(current, payload)
    return merged


def _refresh_widget(page_widget, chunk: str) -> None:
    """Called by the bridge, on the main thread, only after its own write
    and only if `page_widget` (the CarbonEmissionTabView) is already open -
    finds the MachineryEmissions tab and reuses its own on_refresh()
    (re-fetches this chunk from the engine and reloads), exactly like a
    GUI-native refresh would. Unlike social_cost_data's RickeWidget,
    MachineryEmissions.load_data() drives its total labels through a direct
    call at the end (_on_totals_changed()), not a signal load_data_dict()
    would block - so no extra repaint call is needed here."""
    for i in range(page_widget.tab_view.count()):
        tab = page_widget.tab_view.widget(i)
        if isinstance(tab, MachineryEmissions):
            tab.on_refresh()
            return


register_chunk(
    _CHUNK,
    page_name=_PAGE_NAME,
    widget_cls=CarbonEmissionTabView,
    field_defs=None,
    schema=_machinery_schema,
    validate_payload=_validate_payload,
    merge_payload=_merge_payload,
    refresh_widget=_refresh_widget,
    refresh_via_signal=True,
)
