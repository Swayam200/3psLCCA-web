"""
structure/registry/material_entry.py

Qt-free helpers for building and validating material entries - the canonical
`{id, values, meta, state}` dicts stored in the four str_* chunks. Extracted
from widgets/material_dialog.py so headless callers (the local HTTP API, the
Excel importer, tests) share the exact same entry pipeline as the GUI dialog;
material_dialog.py re-imports everything here.

Note: MaterialDialog.validate_and_accept() still carries its own interactive
copy of the validation rules (interleaved with QMessageBox confirm prompts).
validate_material_values() below is the pure equivalent used by the API; if a
rule changes in one place it must change in both.
"""

import math
import uuid as _uuid_mod

from three_ps_lcca_gui.gui.components.utils.unit_resolver import canonical_unit_code

_REQUIRED_ITEM_KEYS = (
    "name",
    "unit",
    "rate",
    "rate_src",
    "carbon_emission",
    "carbon_emission_units",
    "carbon_emission_units_den",
    "conversion_factor",
    "carbon_emission_src",
)
_ITEM_DEFAULTS = {
    "rate": None,
    "rate_src": None,
    "carbon_emission": None,
    "carbon_emission_units": None,
    "carbon_emission_units_den": None,
    "conversion_factor": None,
    "carbon_emission_src": None,
}


def _validate_item(item: dict) -> bool:
    """
    Ensure item has all required schema keys, filling optional ones with
    'not_available' defaults rather than dropping the item entirely.
    Returns False only if the truly essential keys (name, unit) are missing.
    """
    if not item.get("name") or not item.get("unit"):
        return False
    for key, default in _ITEM_DEFAULTS.items():
        item.setdefault(key, default)
    return True


def resolve_carbon_denom(item: dict) -> str | None:
    """
    Return the bare carbon-emission denominator unit (e.g. "kg") for a raw
    SOR/database item, regardless of which Excel column it came from.

    Source data has two distinct fields, kept separate (never aliased onto
    each other) because they come from two different, deliberately named
    Excel columns:
      - "carbon_emission_units_den": always the bare denominator, e.g. "kg".
      - "carbon_emission_units": the older/ambiguous column - historically
        filled with the full ratio (e.g. "kgCO2/kg") by data preparers
        reading the name at face value. Take the segment after the last "/"
        so a full ratio still resolves to the correct bare unit; a value
        with no "/" is already bare and passes through unchanged.
    "_den" wins when both are present (it's the unambiguous one).

    This is the canonical implementation - material_dialog.py imports it
    from here rather than keeping its own copy.
    """
    den = item.get("carbon_emission_units_den")
    if den not in (None, "", 0):
        return str(den).strip()

    units = item.get("carbon_emission_units")
    if units not in (None, "", 0):
        units = str(units).strip()
        return units.rsplit("/", 1)[-1].strip() if "/" in units else units

    return None


def build_excel_snapshot(values_dict: dict) -> dict:
    """
    Build a complete snapshot from an Excel-imported values_dict.
    Captures all parsed fields to ensure 100% data parity for audit logs.
    Blank strings are normalized to None so db_original stays consistent
    with the values dict.
    """
    snapshot = {}
    for k, v in values_dict.items():
        if k.startswith("_"):
            continue
        snapshot[k] = None if (isinstance(v, str) and v.strip() == "") else v
    snapshot["action"] = "excel"
    return snapshot


def _valid(val) -> bool:
    return val not in (None, "", 0, 0.0)


def _valid_carbon_num(val) -> bool:
    """Stricter than _valid() for carbon_emission/conversion_factor
    specifically: a raw catalog/SOR row is untrusted data, and _valid() alone
    would call NaN, Infinity, or a negative number "available" (none of them
    are None/""/0). That would default included_in_carbon_emission=True onto
    a corrupted row, which validate_material_values() now hard-rejects -
    turning one bad database row into an unaddable material with no way for
    the caller to override it (rate/carbon_emission/conversion_factor aren't
    settable via add_from_catalog). Treating a bad value as "not available"
    instead degrades gracefully to the same "no carbon data" fallback a
    genuinely blank row already gets."""
    return (
        isinstance(val, (int, float))
        and not isinstance(val, bool)
        and not math.isnan(val)
        and not math.isinf(val)
        and val > 0
    )


def carbon_data_available(dict_b: dict) -> bool:
    """True if a raw SOR/database row has enough carbon data to be included
    in carbon emission calculations by default - the same three-field check
    convert_sor_item_to_material() uses internally, exposed so callers (e.g.
    the local API's add_from_catalog path) can check eligibility before
    deciding whether to honor an explicit include_in_carbon_emission=true."""
    return (
        _valid_carbon_num(dict_b.get("carbon_emission"))
        and _valid(resolve_carbon_denom(dict_b))
        and _valid_carbon_num(dict_b.get("conversion_factor"))
    )


def convert_sor_item_to_material(dict_b: dict) -> dict:
    """
    Convert a raw SOR/database item (dict_b) into a fully structured material
    entry ready for storage.  The returned dict follows the canonical
    {id, values, meta, state} schema.

    Consumed by the dialog autofill pipeline and the local API's
    add-from-catalog path.
    """
    carbon_eligible = carbon_data_available(dict_b)

    raw_key = dict_b.get("db_key") or ""
    is_custom = raw_key.startswith("custom::")
    source = "custom_db" if is_custom else "db"
    source_db_key = raw_key.removeprefix("custom::")

    values = {
        "material_name": dict_b.get("name", ""),
        "quantity": None,
        # Canonicalized (e.g. "sqm" -> "m2") - the GUI's unit dropdown only
        # matches canonical codes exactly, no alias resolution, so storing
        # an alias verbatim would show the unit field blank when editing.
        "unit": canonical_unit_code(dict_b.get("unit")),
        "unit_to_si": 1.0,
        "src_id": dict_b.get("src_id") if _valid(dict_b.get("src_id")) else None,
        "rate": dict_b.get("rate") if _valid(dict_b.get("rate")) else None,
        "rate_source": dict_b.get("rate_src", "") if _valid(dict_b.get("rate_src")) else "",
        "carbon_emission": dict_b.get("carbon_emission") if _valid(dict_b.get("carbon_emission")) else None,
        "carbon_unit": (
            f"kgCO₂e/{resolve_carbon_denom(dict_b)}"
            if _valid(resolve_carbon_denom(dict_b))
            else None
        ),
        "carbon_emission_src": dict_b.get("carbon_emission_src", "") if _valid(dict_b.get("carbon_emission_src")) else "",
        "conversion_factor": dict_b.get("conversion_factor") if _valid(dict_b.get("conversion_factor")) else None,
        "scrap_rate": None,
        "post_demolition_recovery_percentage": None,
    }
    state = {
        "in_trash": False,
        "included_in_carbon_emission": carbon_eligible,
        "included_in_recyclability": False,
        "allow_edit_checked": False,
    }
    db_original = {
        **dict_b,
        "action": "custom_db" if is_custom else "internal_db",
        "db_key": raw_key,
    }
    return {
        "id": str(_uuid_mod.uuid4()),
        "values": values,
        "meta": {
            "source": source,
            "source_db_key": source_db_key,
            "db_original": db_original,
            "defaults": {"values": dict(values), "state": dict(state)},
        },
        "state": state,
    }


def compute_source_transition(db_original: dict, sor_item: bool, modified: bool) -> str:
    """Determine the source action for entry metadata after an edit - the
    pure core of MaterialDialog._compute_action().

    Rules:
      db + edited          → db_modified   (stays db_modified on re-edit)
      excel + edited       → excel_modified (stays excel_modified on re-edit)
      custom_db + edited   → custom_db_modified
      anything unmodified  → original action
    """
    orig_action = (db_original or {}).get("action", "")

    if orig_action == "excel":
        return "excel_modified" if modified else "excel"
    if orig_action == "internal_db":
        return "db_modified" if modified else "internal_db"
    if orig_action == "custom_db":
        return "custom_db_modified" if modified else "custom_db"
    if sor_item:
        is_custom = ((db_original or {}).get("db_key") or "").startswith("custom::")
        return "custom_db" if is_custom else "internal_db"
    return "user_added"


def action_to_source(action: str, db_original: dict) -> tuple[str, str]:
    """Map a source action to the (source, source_db_key) pair stored in
    entry meta - mirrors the mapping in MaterialDialog.get_values()."""
    raw_key = (db_original or {}).get("db_key", "")
    if action in ("excel", "excel_modified"):
        return action, ""
    if action in ("internal_db", "db_modified"):
        return ("db_modified" if action == "db_modified" else "db"), raw_key
    if action in ("custom_db", "custom_db_modified"):
        return (
            "custom_db_modified" if action == "custom_db_modified" else "custom_db",
            raw_key.removeprefix("custom::"),
        )
    return "manual", ""


def validate_material_values(values: dict, state: dict | None = None) -> dict:
    """Pure equivalent of MaterialDialog.validate_and_accept()'s rules.
    Returns {"errors": [...], "warnings": [...]} - errors are hard rejections
    (the dialog's QMessageBox.critical cases), warnings are the conditions the
    dialog asks "Continue?" about (a non-interactive caller gets them reported
    back instead of prompted).
    """
    errors: list[str] = []
    warnings: list[str] = []
    state = state or {}

    name = (values.get("material_name") or "").strip() if isinstance(values.get("material_name"), str) else values.get("material_name")
    if not name:
        errors.append("material_name is required")

    if not values.get("unit"):
        errors.append("unit is required (select a unit code, e.g. 'cum', 'kg', 'MT')")

    qty = values.get("quantity")
    if not isinstance(qty, (int, float)) or isinstance(qty, bool):
        errors.append(f"quantity must be a number greater than zero, got {qty!r}")
    elif math.isnan(qty) or math.isinf(qty):
        errors.append(f"quantity cannot be NaN or Infinity, got {qty!r}")
    elif qty <= 0:
        errors.append(f"quantity must be a number greater than zero, got {qty!r}")

    rate = values.get("rate")
    if rate is None or (isinstance(rate, str) and not rate.strip()):
        errors.append("rate (unit cost) is required")
    elif not isinstance(rate, (int, float)) or isinstance(rate, bool):
        errors.append(f"rate must be a number, got {rate!r}")
    elif math.isnan(rate) or math.isinf(rate):
        errors.append(f"rate cannot be NaN or Infinity, got {rate!r}")
    elif rate < 0:
        errors.append("rate cannot be negative")
    elif rate == 0:
        warnings.append("rate is 0 - this material will contribute no cost")

    carbon_on = bool(state.get("included_in_carbon_emission"))
    if carbon_on:
        ef = values.get("carbon_emission")
        cf = values.get("conversion_factor")
        if not values.get("carbon_unit"):
            errors.append(
                "carbon_unit is required when included_in_carbon_emission is true "
                "(format: 'kgCO₂e/<unit>')"
            )
        ef_is_num = isinstance(ef, (int, float)) and not isinstance(ef, bool)
        cf_is_num = isinstance(cf, (int, float)) and not isinstance(cf, bool)

        # NaN/Infinity/negative are never a legitimate emission factor or
        # conversion factor - unlike "0 or blank" (which just means "skip
        # carbon costing for this entry", a warning-only, intentional
        # opt-out), these are nonsensical inputs that would corrupt any
        # downstream carbon-cost calculation. Hard reject, same tier as
        # quantity/rate.
        if ef_is_num and (math.isnan(ef) or math.isinf(ef)):
            errors.append(f"carbon_emission cannot be NaN or Infinity, got {ef!r}")
        elif cf_is_num and (math.isnan(cf) or math.isinf(cf)):
            errors.append(f"conversion_factor cannot be NaN or Infinity, got {cf!r}")
        elif ef_is_num and ef < 0:
            errors.append(f"carbon_emission cannot be negative, got {ef!r}")
        elif cf_is_num and cf < 0:
            errors.append(f"conversion_factor cannot be negative, got {cf!r}")
        elif ef is None or not ef_is_num or ef <= 0:
            warnings.append(
                "carbon_emission (emission factor) is 0 or blank - carbon cost "
                "will be skipped for this entry"
            )
        elif cf is None or not cf_is_num or cf <= 0:
            warnings.append(
                "conversion_factor is 0 or blank - carbon cost will be skipped "
                "for this entry"
            )

    recycle_on = bool(state.get("included_in_recyclability"))
    if recycle_on:
        scrap = values.get("scrap_rate")
        recovery = values.get("post_demolition_recovery_percentage")

        # Both fields may be omitted/None (recyclability with no data yet) -
        # that's fine, only ever folds into the "contributes nothing" warning
        # below. But if a value IS given, it must be a sane number: never
        # NaN/Infinity, and never negative (0 is fine - "no scrap value" /
        # "nothing recovered").
        if scrap is not None:
            if not isinstance(scrap, (int, float)) or isinstance(scrap, bool):
                errors.append(f"scrap_rate must be a number, got {scrap!r}")
            elif math.isnan(scrap) or math.isinf(scrap):
                errors.append(f"scrap_rate cannot be NaN or Infinity, got {scrap!r}")
            elif scrap < 0:
                errors.append("scrap_rate cannot be negative")

        if recovery is not None:
            if not isinstance(recovery, (int, float)) or isinstance(recovery, bool):
                errors.append(f"post_demolition_recovery_percentage must be a number, got {recovery!r}")
            elif math.isnan(recovery) or math.isinf(recovery):
                errors.append(f"post_demolition_recovery_percentage cannot be NaN or Infinity, got {recovery!r}")
            elif recovery < 0:
                errors.append("post_demolition_recovery_percentage cannot be negative")
            elif recovery > 100:
                errors.append("post_demolition_recovery_percentage cannot exceed 100")

        scrap_blank_or_zero = scrap is None or scrap == 0
        recovery_blank_or_zero = recovery is None or recovery == 0
        if scrap_blank_or_zero and recovery_blank_or_zero:
            warnings.append(
                "both scrap_rate and post_demolition_recovery_percentage are "
                "zero or blank - recyclability will contribute nothing"
            )

    return {"errors": errors, "warnings": warnings}
