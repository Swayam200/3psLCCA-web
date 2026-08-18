"""
gui/api/pages/structure.py

Registers the four Construction Works Data chunks (str_foundation,
str_sub_structure, str_super_structure, str_misc) plus the read-only
str_component_registry. These are table pages, not FieldDef forms, so they
use the registry's schema/hook path (Tier C):

- Chunk shape: {component_name: [entry, ...]} where each entry is the
  canonical {id, values, meta, state} material dict.
- Writes are ENTRY-GRANULAR, not raw-chunk-granular: a POST body is
  {component_name: [entry_patch, ...]} - each patch either targets an
  existing entry by "id" (its values/state are deep-merged) or, without an
  "id", creates a new entry server-side (from "catalog_item" via
  convert_sor_item_to_material, or manually from "values"). Components and
  entries not mentioned are untouched; entries are never deleted - set
  state.in_trash instead (mirrors the GUI's trash).
- "meta" (id, source lineage, db_original, timestamps) is server-owned and
  never caller-writable.
- All entry values pass validate_material_values - the same rules the GUI's
  material dialog enforces.
"""

import copy
import datetime
import uuid

from three_ps_lcca_gui.gui.components.structure.main import StructureTabView
from three_ps_lcca_gui.gui.components.structure.registry.material_entry import (
    action_to_source,
    carbon_data_available,
    compute_source_transition,
    convert_sor_item_to_material,
    validate_material_values,
)
from three_ps_lcca_gui.gui.components.utils.unit_resolver import (
    get_unit_info,
    list_available_units,
    save_custom_unit,
    validate_custom_unit,
)
from ..catalog import get_engine
from ..registry import register_chunk

_PAGE_NAME = "Construction Works Data"

_CHUNK_TABS = {
    "str_foundation": "Foundation",
    "str_sub_structure": "Sub-Structure",
    "str_super_structure": "Super-Structure",
    "str_misc": "Miscellaneous",
}

_PATCH_KEYS = {"id", "values", "state", "catalog_item", "custom_unit"}
_CUSTOM_UNIT_KEYS = {"symbol", "name", "dimension", "to_si"}
_STATE_KEYS = {
    "in_trash",
    "included_in_carbon_emission",
    "included_in_recyclability",
    "allow_edit_checked",
}
_VALUE_KEYS = {
    "src_id",
    "material_name",
    "quantity",
    "unit",
    "unit_to_si",
    "rate",
    "rate_source",
    "carbon_emission",
    "carbon_unit",
    "carbon_emission_src",
    "conversion_factor",
    "scrap_rate",
    "post_demolition_recovery_percentage",
}
_EMPTY_VALUES = {key: None for key in sorted(_VALUE_KEYS)}


def _unit_to_si(unit_code: str) -> float:
    factor, _dim = get_unit_info(unit_code)
    return factor or 1.0


def _new_entry(patch: dict, now: str) -> dict:
    """Builds a full entry for a patch without an "id" - from a catalog item
    if given (identical to the GUI's add-from-catalog pipeline), else a
    manual entry. Caller-sent values/state are overlaid on the base."""
    values_in = dict(patch.get("values") or {})
    state_in = dict(patch.get("state") or {})

    if "catalog_item" in patch:
        entry = convert_sor_item_to_material(dict(patch["catalog_item"]))
        # Anything beyond quantity is a deviation from the catalog snapshot -
        # same lineage rule as editing a db entry in the dialog.
        modified = bool(set(values_in) - {"quantity"})
        entry["values"].update(values_in)
        if entry["values"].get("unit") and entry["values"].get("unit_to_si", 1.0) == 1.0:
            entry["values"]["unit_to_si"] = _unit_to_si(entry["values"]["unit"])
        entry["state"].update(state_in)
        if modified:
            action = compute_source_transition(entry["meta"]["db_original"], True, True)
            source, source_db_key = action_to_source(action, entry["meta"]["db_original"])
            entry["meta"]["source"] = source
            entry["meta"]["source_db_key"] = source_db_key
    else:
        values = {**_EMPTY_VALUES, **values_in}
        if values.get("material_name") is None:
            values["material_name"] = ""
        if values.get("unit") and not values_in.get("unit_to_si"):
            values["unit_to_si"] = _unit_to_si(values["unit"])
        carbon_fields_set = all(
            values.get(k) not in (None, "", 0, 0.0)
            for k in ("carbon_emission", "carbon_unit", "conversion_factor")
        )
        state = {
            "in_trash": False,
            "included_in_carbon_emission": carbon_fields_set,
            "included_in_recyclability": False,
            "allow_edit_checked": False,
            **state_in,
        }
        entry = {
            "id": str(uuid.uuid4()),
            "values": values,
            "meta": {
                "source": "manual",
                "source_db_key": "",
                "db_original": {},
            },
            "state": state,
        }

    entry["meta"]["created_on"] = now
    entry["meta"]["modified_on"] = now
    # Audit marker: distinguishes entries added through this API from ones
    # added via the GUI's material dialog. Internal bookkeeping only - "meta"
    # (including this) is stripped from every API response by
    # _redact_response, never something a caller can read back or set.
    entry["meta"]["created_via"] = "api"
    return entry


def _resolve_unit(entry: dict, custom_unit, where: str) -> list[str]:
    """Checks the entry's (possibly just-set) unit is usable. If it's already
    a recognized code (built-in, alias, existing custom, or a compound like
    "kg/m2") this is a no-op. If it's NOT recognized, the caller must supply
    "custom_unit": {symbol, dimension, to_si} in the same request - exactly
    the fields the GUI's "+ Add Custom Unit..." dialog collects - which is
    validated, persisted, and immediately used for this entry's unit_to_si.
    Mutates `entry["values"]["unit_to_si"]` in place on success; returns a
    list of errors (empty on success)."""
    unit = entry.get("values", {}).get("unit")
    if not unit:
        return []

    to_si, _dim = get_unit_info(unit)
    if to_si is not None:
        return []  # already resolvable - nothing to do

    if custom_unit is None:
        return [
            f"{where}: unit {unit!r} is not a recognized unit - see this "
            f"chunk's schema \"units\" list for valid codes, or include "
            f"\"custom_unit\": {{\"symbol\", \"dimension\", \"to_si\"}} in this "
            f"same request to define a new one (like the GUI's "
            f"'+ Add Custom Unit...' dialog)"
        ]
    if not isinstance(custom_unit, dict):
        return [f"{where}: 'custom_unit' must be an object"]

    bad_keys = set(custom_unit) - _CUSTOM_UNIT_KEYS
    if bad_keys:
        return [
            f"{where}: unrecognized custom_unit key(s) {sorted(bad_keys)} - "
            f"allowed: {sorted(_CUSTOM_UNIT_KEYS)}"
        ]
    symbol = (custom_unit.get("symbol") or "").strip()
    if symbol != unit:
        return [
            f"{where}: custom_unit.symbol ({symbol!r}) must match "
            f"values.unit ({unit!r})"
        ]

    cu_errors = validate_custom_unit(custom_unit)
    if cu_errors:
        return [f"{where}: {e}" for e in cu_errors]

    saved = save_custom_unit(custom_unit)
    entry["values"]["unit_to_si"] = saved["to_si"]
    return []


def _check_single_entry(payload: dict) -> list[str]:
    """Bulk operations are not supported - a POST may change exactly one
    entry (one component, one patch). Returns errors describing why, or []
    if the payload has the right shape to proceed to per-field validation."""
    if len(payload) != 1:
        return [
            f"exactly one component is allowed per request (got {len(payload)}: "
            f"{sorted(payload)}) - bulk operations are not supported; send one "
            f"POST per material change"
        ]
    comp, patches = next(iter(payload.items()))
    if isinstance(patches, list) and len(patches) != 1:
        return [
            f"'{comp}': exactly one entry patch is allowed per request (got "
            f"{len(patches)}) - bulk operations are not supported; send one "
            f"POST per material change"
        ]
    return []


def _apply(current: dict, payload: dict) -> tuple[dict, list[str]]:
    """Entry-granular merge of `payload` into `current`. Returns
    (merged, errors); on any error the merge result must be discarded.
    Pure - no Qt, no engine."""
    errors: list[str] = []
    if not isinstance(payload, dict) or not payload:
        return current, [
            "payload must be {component_name: [entry_patch]} - see the "
            "schema in the GET response"
        ]

    single_entry_errors = _check_single_entry(payload)
    if single_entry_errors:
        return current, single_entry_errors

    merged = copy.deepcopy(current)
    now = datetime.datetime.now().isoformat()

    for comp, patches in payload.items():
        if not isinstance(patches, list):
            errors.append(f"'{comp}': must be a list of entry patches")
            continue
        if comp not in merged:
            errors.append(
                f"'{comp}' is not an existing component - valid components: "
                f"{sorted(merged.keys())} (components are managed in the app, "
                f"not created via the API)"
            )
            continue

        by_id = {e.get("id"): e for e in merged[comp] if isinstance(e, dict)}

        for i, patch in enumerate(patches):
            where = f"{comp}[{i}]"
            if not isinstance(patch, dict):
                errors.append(f"{where}: each entry patch must be an object")
                continue

            if "meta" in patch:
                errors.append(f"{where}: 'meta' is server-managed and cannot be written")
                continue
            unknown = set(patch) - _PATCH_KEYS
            if unknown:
                errors.append(f"{where}: unrecognized key(s) {sorted(unknown)} - allowed: {sorted(_PATCH_KEYS)}")
                continue

            values_in = patch.get("values")
            if values_in is not None:
                if not isinstance(values_in, dict):
                    errors.append(f"{where}: 'values' must be an object")
                    continue
                bad_vals = set(values_in) - _VALUE_KEYS
                if bad_vals:
                    errors.append(f"{where}: unknown values key(s) {sorted(bad_vals)} - allowed: {sorted(_VALUE_KEYS)}")
                    continue
            state_in = patch.get("state")
            if state_in is not None:
                if not isinstance(state_in, dict):
                    errors.append(f"{where}: 'state' must be an object")
                    continue
                bad_state = set(state_in) - _STATE_KEYS
                if bad_state:
                    errors.append(f"{where}: unknown state key(s) {sorted(bad_state)} - allowed: {sorted(_STATE_KEYS)}")
                    continue

            if "id" in patch:
                entry = by_id.get(patch["id"])
                if entry is None:
                    errors.append(
                        f"{where}: no entry with id {patch['id']!r} in '{comp}' - "
                        f"GET this page to list entries and their ids"
                    )
                    continue
                values_changed = any(
                    entry.get("values", {}).get(k) != v for k, v in (values_in or {}).items()
                )
                entry.setdefault("values", {}).update(values_in or {})
                entry.setdefault("state", {}).update(state_in or {})
                if values_changed:
                    meta = entry.setdefault("meta", {})
                    db_original = meta.get("db_original") or {}
                    action = compute_source_transition(db_original, bool(db_original), True)
                    source, source_db_key = action_to_source(action, db_original)
                    meta["source"] = source
                    meta["source_db_key"] = source_db_key
                    meta["modified_on"] = now
            else:
                if "catalog_item" in patch:
                    ci = patch["catalog_item"]
                    if not isinstance(ci, dict) or not ci.get("name") or not ci.get("unit"):
                        errors.append(
                            f"{where}: 'catalog_item' must be an object with at "
                            f"least 'name' and 'unit' (a row from the SOR catalog)"
                        )
                        continue
                entry = _new_entry(patch, now)
                merged[comp].append(entry)

            unit_errors = _resolve_unit(entry, patch.get("custom_unit"), where)
            if unit_errors:
                errors.extend(unit_errors)

            result = validate_material_values(entry.get("values", {}), entry.get("state", {}))
            if result["errors"]:
                errors.extend(f"{where}: {e}" for e in result["errors"])

    return merged, errors


def _validate_payload(payload: dict, current: dict | None) -> list[str]:
    if current is None:
        # Server-side pre-check without stored data: structural shape and
        # single-entry cardinality only (fails fast, before the main-thread
        # round-trip, for the common case of an obviously-bulk request).
        if not isinstance(payload, dict) or not payload:
            return [
                "payload must be {component_name: [entry_patch]} - see the "
                "schema in the GET response"
            ]
        single_entry_errors = _check_single_entry(payload)
        if single_entry_errors:
            return single_entry_errors
        return [
            f"'{comp}': must be a list of entry patches"
            for comp, patches in payload.items()
            if not isinstance(patches, list)
        ]
    _merged, errors = _apply(current, payload)
    return errors


def _merge_payload(current: dict, payload: dict) -> dict:
    merged, _errors = _apply(current, payload)
    return merged


def _refresh_widget(page_widget, chunk: str) -> None:
    """Called by the bridge, on the main thread, only after its own write
    and only if `page_widget` (the StructureTabView) is already open -
    repaints the affected tab so an API write shows up live. Reuses the
    same, unmodified public method a GUI-native chunk_updated listener would
    call; this file has no connection to that signal, so it never runs as a
    side effect of the GUI's own add/edit/trash actions (which already
    update their own UI) and can never race or double-render against them.

    The Trash Bin view (page_widget.trash_view) is a separate widget with
    its own state, not touched by refresh_tab_by_chunk - any write can
    change what belongs there (state.in_trash isn't exclusive to the
    dedicated /trash shortcut; the generic entry-patch endpoint can set it
    too), so refresh it too. Cheap and safe to call unconditionally: its
    on_refresh() always does a full rebuild from fresh engine data, never an
    incremental patch."""
    page_widget.refresh_tab_by_chunk(chunk)
    page_widget.trash_view.on_refresh()


def _auto_create_registry_patch(registry: dict, chunk: str, comp: str) -> dict:
    """Builds the registry_patch for auto-creating a new component - same
    defaults the GUI uses for a brand-new component typed into its Add
    Material dialog. Caller decides whether to apply it (only when the
    component didn't already exist)."""
    from three_ps_lcca_gui.gui.components.structure.widgets.defaults import PAGE_DEFAULT_SHEET
    default_sheet = PAGE_DEFAULT_SHEET.get(chunk, "Miscellaneous")
    patch = copy.deepcopy(registry)
    patch.setdefault(chunk, {})[comp] = {
        "search_cat": {"component": comp, "sheet": default_sheet},
        "is_deleted": False,
    }
    return patch


def _duplicate_name_error(current: dict, comp: str, name: str) -> str | None:
    """Same rule as the GUI's Add Material dialog (manager.py
    _existing_names): active (non-trashed) entries in this component only,
    case/whitespace-insensitive. Returns an error string, or None if the
    name is free to use."""
    name_norm = name.strip().lower()
    active_names = {
        e.get("values", {}).get("material_name", "").strip().lower()
        for e in current.get(comp, [])
        if not e.get("state", {}).get("in_trash", False)
    }
    if name_norm in active_names:
        return (
            f"a material named {name!r} already exists in '{comp}' - use a "
            f"different name, or update the existing entry by id instead"
        )
    return None


_ADD_FROM_CATALOG_KEYS = {
    "component", "db_key", "material_name", "quantity",
    "include_in_carbon_emission", "include_in_recyclability",
    "scrap_rate", "post_demolition_recovery_percentage",
}
_ADD_FROM_CATALOG_REQUIRED = {"component", "db_key", "material_name", "quantity"}


def _add_from_catalog(
    current: dict, payload: dict, registry: dict, chunk: str
) -> tuple[dict, dict | None, str | None, list[str]]:
    """Search-and-add shortcut: caller gives (component, db_key, an EXACT
    material_name, quantity, optional carbon/recyclability flags) instead of
    pasting a full catalog row - the server does the search, builds the
    entry via convert_sor_item_to_material (same lineage the GUI's search
    dialog produces), and appends it. Never updates existing entries; the
    envelope is a single flat object (no list) - exactly one material per
    call, no bulk. If `component` doesn't exist yet in this chunk, it's
    auto-created (mirrors manager.py's add_material(), which does the same
    for a brand-new component typed into the GUI's dialog) - the caller
    doesn't have to pre-create it. Pure except for the catalog engine lookup
    (read-only, shared, no Qt). `registry` is the full str_component_registry
    chunk. Returns (merged_data, registry_patch_or_None, warning_or_None,
    errors) - registry_patch is the full registry to persist, only returned
    when a new component was created; on any error, both merged_data and
    registry_patch are unusable and must be discarded, matching _apply()."""
    if not isinstance(payload, dict):
        return current, None, None, ["payload must be a JSON object - see this chunk's schema"]

    unknown = set(payload) - _ADD_FROM_CATALOG_KEYS
    if unknown:
        return current, None, None, [
            f"unrecognized key(s) {sorted(unknown)} - allowed: {sorted(_ADD_FROM_CATALOG_KEYS)}"
        ]
    missing = _ADD_FROM_CATALOG_REQUIRED - set(payload)
    if missing:
        return current, None, None, [f"missing required key(s): {sorted(missing)}"]

    comp = payload["component"]
    db_key = payload["db_key"]
    name = payload["material_name"]
    quantity = payload["quantity"]
    if not isinstance(comp, str) or not comp.strip():
        return current, None, None, ["'component' must be a non-empty string"]
    if not isinstance(db_key, str) or not db_key.strip():
        return current, None, None, ["'db_key' must be a non-empty string - see GET /catalog/databases"]
    if not isinstance(name, str) or not name.strip():
        return current, None, None, ["'material_name' must be a non-empty string"]

    component_is_new = comp not in current

    dup_error = _duplicate_name_error(current, comp, name)
    if dup_error:
        return current, None, None, [dup_error]

    # Exact-name search, scoped to db_key only - NOT filtered by this app's
    # component names, since a catalog row's own "component"/"category"
    # tagging doesn't line up with the app's four Construction Works tabs
    # (e.g. many SOR databases tag everything just "Super-Structure").
    name_norm = name.strip().lower()
    matches = [
        item for item in get_engine()._iter_items(db_key=db_key)
        if (item.get("name") or "").strip().lower() == name_norm
    ]
    if not matches:
        return current, None, None, [
            f"no material named {name!r} found in database {db_key!r} - "
            f"search GET /catalog/search?q=...&db_key={db_key} to find the exact name"
        ]
    if len(matches) > 1:
        candidates = [
            f"category={m.get('category')!r} component={m.get('component')!r} src_id={m.get('src_id')!r}"
            for m in matches
        ]
        return current, None, None, [
            f"{len(matches)} materials named {name!r} found in {db_key!r} - ambiguous: "
            + "; ".join(candidates)
            + f". Use POST /{{project_id}}/{{chunk}} with \"catalog_item\" set to the "
              f"specific row instead (see GET /catalog/search?q=...&db_key={db_key})."
        ]

    row = matches[0]
    entry = convert_sor_item_to_material(dict(row))
    now = datetime.datetime.now().isoformat()
    entry["meta"]["created_on"] = now
    entry["meta"]["modified_on"] = now
    entry["meta"]["created_via"] = "api"
    entry["values"]["quantity"] = quantity
    if entry["values"].get("unit"):
        entry["values"]["unit_to_si"] = _unit_to_si(entry["values"]["unit"])

    errors: list[str] = []
    warning = None

    carbon_available = carbon_data_available(row)
    requested_carbon = payload.get("include_in_carbon_emission")
    if requested_carbon is not None and not isinstance(requested_carbon, bool):
        errors.append("'include_in_carbon_emission' must be a boolean")
    elif requested_carbon is True and not carbon_available:
        entry["state"]["included_in_carbon_emission"] = False
        warning = (
            f"{name!r} has no carbon emission data in {db_key!r}, so it was added "
            f"with included_in_carbon_emission=false. To specify custom carbon "
            f"values for this material, add it as a custom material instead "
            f"(not available via this endpoint yet)."
        )
    elif requested_carbon is False:
        entry["state"]["included_in_carbon_emission"] = False
    # requested_carbon is None (omitted), or True-and-available: keep the
    # default convert_sor_item_to_material already computed.

    # The source SOR databases don't carry recycling data - unlike carbon,
    # there's nothing to fall back to, so scrap_rate/recovery must always
    # come from the caller when opting in.
    requested_recycle = payload.get("include_in_recyclability")
    if requested_recycle is not None and not isinstance(requested_recycle, bool):
        errors.append("'include_in_recyclability' must be a boolean")
    elif requested_recycle is True:
        scrap = payload.get("scrap_rate")
        recovery = payload.get("post_demolition_recovery_percentage")
        if scrap is None or recovery is None:
            errors.append(
                "include_in_recyclability=true requires both 'scrap_rate' and "
                "'post_demolition_recovery_percentage' in the payload - the "
                "source database does not provide recycling data"
            )
        else:
            entry["state"]["included_in_recyclability"] = True
            entry["values"]["scrap_rate"] = scrap
            entry["values"]["post_demolition_recovery_percentage"] = recovery
    elif "scrap_rate" in payload or "post_demolition_recovery_percentage" in payload:
        errors.append(
            "'scrap_rate'/'post_demolition_recovery_percentage' were given but "
            "'include_in_recyclability' is not true - remove them or set the flag"
        )

    result = validate_material_values(entry["values"], entry["state"])
    if result["errors"]:
        errors.extend(result["errors"])

    if errors:
        return current, None, None, errors

    merged = copy.deepcopy(current)
    merged.setdefault(comp, []).append(entry)

    registry_patch = _auto_create_registry_patch(registry, chunk, comp) if component_is_new else None
    return merged, registry_patch, warning, []


_ADD_MANUAL_TOP_KEYS = {"component", "values", "state", "custom_unit"}
_ADD_MANUAL_STATE_KEYS = {"included_in_carbon_emission", "included_in_recyclability"}
_ADD_MANUAL_VALUE_KEYS = {
    "material_name", "unit", "quantity", "rate", "rate_source", "src_id",
    "carbon_emission", "carbon_unit_den", "carbon_unit_num", "carbon_emission_src",
    "conversion_factor", "scrap_rate", "post_demolition_recovery_percentage",
}
_ADD_MANUAL_REQUIRED_VALUE_KEYS = {"material_name", "unit", "quantity", "rate"}


def _add_manual(
    current: dict, payload: dict, registry: dict, chunk: str
) -> tuple[dict, dict | None, str | None, list[str]]:
    """Search-free shortcut: caller supplies the material's values directly
    instead of a catalog row. Flat envelope: {"component": ..., "values":
    {...}, "state": {...}?, "custom_unit": {...}?} - no list wrapper, one
    material per call, no bulk. Instead of the full "carbon_unit" string
    (e.g. "kgCO₂e/kg", awkward to type by hand), accepts "carbon_unit_den"
    - the denominator (e.g. "kg", or a compound like "m^2/kg" to match an
    emission factor expressed per that ratio) - plus an optional
    "carbon_unit_num" (default "kgCO₂e") and joins them as "num/den". If
    `component` doesn't exist yet in this chunk, it's auto-created, same as
    add_from_catalog. Returns (merged_data, registry_patch_or_None,
    warning_or_None, errors) - always None warning (nothing here has a
    fallback-with-warning case like add_from_catalog's carbon lookup)."""
    if not isinstance(payload, dict):
        return current, None, None, ["payload must be a JSON object - see this chunk's schema"]

    unknown = set(payload) - _ADD_MANUAL_TOP_KEYS
    if unknown:
        return current, None, None, [
            f"unrecognized key(s) {sorted(unknown)} - allowed: {sorted(_ADD_MANUAL_TOP_KEYS)}"
        ]

    comp = payload.get("component")
    if not isinstance(comp, str) or not comp.strip():
        return current, None, None, ["'component' is required and must be a non-empty string"]

    values_in = payload.get("values")
    if not isinstance(values_in, dict):
        return current, None, None, ["'values' is required and must be an object"]
    bad_vals = set(values_in) - _ADD_MANUAL_VALUE_KEYS
    if bad_vals:
        return current, None, None, [
            f"unrecognized values key(s) {sorted(bad_vals)} - allowed: "
            f"{sorted(_ADD_MANUAL_VALUE_KEYS)} (use \"carbon_unit_den\" - the "
            f"denominator, e.g. \"kg\" - and optionally \"carbon_unit_num\" "
            f"(default \"kgCO₂e\") instead of the full \"carbon_unit\" string; "
            f"the server joins them as \"num/den\")"
        ]
    missing = _ADD_MANUAL_REQUIRED_VALUE_KEYS - set(values_in)
    if missing:
        return current, None, None, [f"'values' is missing required key(s): {sorted(missing)}"]

    state_in = payload.get("state") or {}
    if not isinstance(state_in, dict):
        return current, None, None, ["'state' must be an object"]
    bad_state = set(state_in) - _ADD_MANUAL_STATE_KEYS
    if bad_state:
        return current, None, None, [
            f"unrecognized state key(s) {sorted(bad_state)} - allowed: {sorted(_ADD_MANUAL_STATE_KEYS)}"
        ]
    for k in _ADD_MANUAL_STATE_KEYS:
        if k in state_in and not isinstance(state_in[k], bool):
            return current, None, None, [f"'state.{k}' must be a boolean"]

    name = values_in.get("material_name")
    if not isinstance(name, str) or not name.strip():
        return current, None, None, ["'values.material_name' must be a non-empty string"]

    component_is_new = comp not in current

    dup_error = _duplicate_name_error(current, comp, name)
    if dup_error:
        return current, None, None, [dup_error]

    # Build values: start from the full field set (defaults None), overlay
    # everything the caller sent except carbon_unit_den/carbon_unit_num,
    # which get joined into carbon_unit instead of being stored under their
    # own names.
    values = dict(_EMPTY_VALUES)
    for k, v in values_in.items():
        if k not in ("carbon_unit_den", "carbon_unit_num"):
            values[k] = v
    den = values_in.get("carbon_unit_den")
    if den:
        num = values_in.get("carbon_unit_num") or "kgCO₂e"
        values["carbon_unit"] = f"{num}/{den}"

    if values.get("unit") and not values_in.get("unit_to_si"):
        values["unit_to_si"] = _unit_to_si(values["unit"])

    now = datetime.datetime.now().isoformat()
    entry = {
        "id": str(uuid.uuid4()),
        "values": values,
        "meta": {
            "source": "manual",
            "source_db_key": "",
            "db_original": {},
            "created_on": now,
            "modified_on": now,
            "created_via": "api",
        },
        "state": {
            "in_trash": False,
            "included_in_carbon_emission": bool(state_in.get("included_in_carbon_emission", False)),
            "included_in_recyclability": bool(state_in.get("included_in_recyclability", False)),
            "allow_edit_checked": False,
        },
    }

    where = f"{comp}[0]"
    errors = _resolve_unit(entry, payload.get("custom_unit"), where)

    result = validate_material_values(entry["values"], entry["state"])
    if result["errors"]:
        errors.extend(result["errors"])

    if errors:
        return current, None, None, errors

    merged = copy.deepcopy(current)
    merged.setdefault(comp, []).append(entry)

    registry_patch = _auto_create_registry_patch(registry, chunk, comp) if component_is_new else None
    return merged, registry_patch, None, []


def _trash_by_id(current: dict, payload: dict) -> tuple[dict, list[str]]:
    """POST /{project_id}/{chunk}/trash - trash (or, with "untrash": true,
    restore) a single entry by id alone. Searches every component in the
    chunk, so the caller doesn't need to already know which component the
    entry is in. Idempotent: setting a state it's already in succeeds with
    no change (mirrors the generic entry-patch endpoint's state-only-change
    behavior - no meta/lineage change either, since only `state` is
    touched, not `values`)."""
    if not isinstance(payload, dict):
        return current, ["payload must be a JSON object"]
    unknown = set(payload) - {"id", "untrash"}
    if unknown:
        return current, [f"unrecognized key(s) {sorted(unknown)} - only 'id' and 'untrash' are accepted"]
    entry_id = payload.get("id")
    if not isinstance(entry_id, str) or not entry_id.strip():
        return current, ["'id' is required and must be a non-empty string"]
    untrash = payload.get("untrash", False)
    if not isinstance(untrash, bool):
        return current, ["'untrash' must be a boolean"]

    merged = copy.deepcopy(current)
    for entries in merged.values():
        if not isinstance(entries, list):
            continue
        for e in entries:
            if isinstance(e, dict) and e.get("id") == entry_id:
                e.setdefault("state", {})["in_trash"] = not untrash
                return merged, []

    return current, [
        f"no entry with id {entry_id!r} found in this chunk - GET this page "
        f"or GET .../trash to list entries and their ids"
    ]


def _redact_response(data: dict) -> dict:
    """Strips "meta" (server-owned lineage/audit bookkeeping) out of every
    entry before a chunk's data is returned over the API - callers can
    address entries by "id" but never see or set their lineage. Builds
    entirely new dicts/lists rather than mutating `data` in place, since the
    same object is what's cached by the controller and (eventually) written
    to disk - this function must be safe to call on that object without
    corrupting it."""
    result = {}
    for comp, entries in data.items():
        if not isinstance(entries, list):
            result[comp] = entries
            continue
        result[comp] = [
            {k: v for k, v in entry.items() if k != "meta"} if isinstance(entry, dict) else entry
            for entry in entries
        ]
    return result


def _chunk_schema(chunk: str, tab: str) -> dict:
    return {
        "chunk": chunk,
        "description": (
            f"Materials/work items of the '{tab}' tab on the Construction "
            f"Works Data page, grouped by component. Data shape: "
            f"{{component_name: [entry, ...]}}; each entry is "
            f"{{id, values, state}} as returned here - \"meta\" (source "
            f"lineage, timestamps) exists internally but is never included "
            f"in API responses and can never be written."
        ),
        "update_semantics": {
            "granularity": (
                "One entry per request - no bulk operations. POST "
                "{component_name: [entry_patch]}: exactly one component key, "
                "exactly one patch. A patch WITH an \"id\" updates that entry "
                "(its values/state keys are merged); a patch WITHOUT an \"id\" "
                "creates a new entry. Sending more than one component or more "
                "than one patch is rejected with 400 - make one API call per "
                "material change."
            ),
            "create_from_catalog": (
                "Send {\"catalog_item\": <SOR row with name/unit/rate/...>, "
                "\"values\": {\"quantity\": <n>}} - the server builds the full "
                "entry with correct source lineage, exactly like picking it in "
                "the GUI's material search dialog. For the common case of "
                "adding one material by its exact catalog name, "
                "POST /{project_id}/{chunk}/add_from_catalog is simpler - see "
                "\"add_from_catalog\" below."
            ),
            "create_manual": (
                "Send {\"values\": {\"material_name\", \"unit\", \"quantity\", "
                "\"rate\", ...}} - required: material_name, unit, quantity > 0, "
                "rate >= 0."
            ),
            "delete": (
                "Never. Set {\"id\": ..., \"state\": {\"in_trash\": true}} to "
                "move an entry to the trash (restore with false), same as the GUI."
            ),
            "server_owned": (
                "\"meta\" (source lineage, db_original snapshot, timestamps) and "
                "entry ids are managed by the server, cannot be written, and are "
                "never included in any response - entries here only ever show "
                "id/values/state."
            ),
            "components": (
                "Component groups themselves (add/rename/delete) are managed in "
                "the app - a POST naming an unknown component is rejected."
            ),
            "units": (
                "\"unit\" must be one of the codes in this schema's \"units\" "
                "list (built-in or already-defined custom), or any expression "
                "get_unit_info() resolves (aliases, ratios like 'kg/m2'). If "
                "it's genuinely new, include \"custom_unit\": {\"symbol\", "
                "\"dimension\" (one of Mass/Length/Area/Volume/Count), \"to_si\" "
                "(positive number), \"name\" (optional)} in the SAME request - "
                "this defines it (like the GUI's '+ Add Custom Unit...' dialog) "
                "and it becomes usable immediately, including for future entries."
            ),
        },
        "units": list_available_units(),
        "add_from_catalog": {
            "endpoint": f"POST /{{project_id}}/{chunk}/add_from_catalog",
            "description": (
                "Shortcut for adding exactly one material by its exact "
                "catalog name, instead of pasting a full row as "
                "\"catalog_item\" in the endpoint above. The server searches "
                "for the name in db_key and builds the entry itself."
            ),
            "request_body": {
                "component": "string, required - auto-created if it doesn't already exist in this chunk (unlike the main endpoint, which rejects unknown components)",
                "db_key": "string, required - from GET /catalog/databases or a search result's db_key",
                "material_name": "string, required - must EXACTLY match one catalog row's name in db_key (case/whitespace-insensitive); ambiguous or no match is rejected",
                "quantity": "number > 0, required",
                "include_in_carbon_emission": (
                    "bool, optional. Default: true if the matched row has "
                    "carbon data, else false. Requesting true when the row "
                    "has no carbon data does NOT reject the material - it's "
                    "added with this forced to false and a warning returned."
                ),
                "include_in_recyclability": (
                    "bool, optional, default false. If true, \"scrap_rate\" "
                    "and \"post_demolition_recovery_percentage\" are REQUIRED "
                    "in this same request - catalog rows never carry "
                    "recycling data, so there's nothing to fall back to."
                ),
                "scrap_rate": "number - required only if include_in_recyclability is true",
                "post_demolition_recovery_percentage": "number 0-100 - required only if include_in_recyclability is true",
            },
            "notes": [
                "Exactly one material per call - this endpoint has no list/batch form.",
                "Rejects if a non-trashed entry in \"component\" already has this exact material_name.",
                "rate, carbon_emission, conversion_factor, src_id, etc. all come from the matched catalog row - they cannot be overridden here (use \"catalog_item\" on the main endpoint for that).",
                "If \"component\" doesn't already exist in this chunk, it's created automatically (same defaults the GUI uses for a new component typed into its Add Material dialog) - the main endpoint, by contrast, rejects unknown components.",
            ],
        },
        "add_manual": {
            "endpoint": f"POST /{{project_id}}/{chunk}/add_manual",
            "description": (
                "Shortcut for adding exactly one material with values you "
                "supply directly - no catalog lookup. Flat "
                "{component, values} body instead of the main endpoint's "
                "{component: [entry_patch]} list-wrapped form."
            ),
            "request_body": {
                "component": "string, required - auto-created if it doesn't already exist in this chunk (same as add_from_catalog)",
                "values": {
                    "material_name": "string, required",
                    "unit": "string, required - a code from this schema's \"units\" list, or pair with \"custom_unit\"",
                    "quantity": "number > 0, required",
                    "rate": "number >= 0, required",
                    "rate_source": "string, optional",
                    "src_id": "string, optional - your own reference id",
                    "carbon_emission": "number, optional - emission factor",
                    "carbon_unit_den": (
                        "string, optional - the denominator unit (e.g. \"kg\", "
                        "or a compound like \"m^2/kg\" to match an emission "
                        "factor expressed per that ratio), not the full "
                        "\"carbon_unit\" string. The server joins it with "
                        "carbon_unit_num as \"<carbon_unit_num>/<carbon_unit_den>\" "
                        "and stores that - you never type the ₂ subscript by "
                        "hand. Required if state.included_in_carbon_emission "
                        "is true."
                    ),
                    "carbon_unit_num": (
                        "string, optional, default \"kgCO₂e\" - the numerator "
                        "half of the carbon_unit ratio, paired with "
                        "carbon_unit_den. Only needed to override the default."
                    ),
                    "carbon_emission_src": "string, optional",
                    "conversion_factor": "number, optional",
                    "scrap_rate": "number, optional",
                    "post_demolition_recovery_percentage": "number 0-100, optional",
                },
                "state": {
                    "included_in_carbon_emission": "bool, optional, default false",
                    "included_in_recyclability": "bool, optional, default false",
                },
                "custom_unit": "optional - {symbol, dimension, to_si, name?} - required if \"unit\" isn't already known; see this schema's \"units\" list first",
            },
            "notes": [
                "Exactly one material per call - this endpoint has no list/batch form.",
                "Send \"carbon_unit_den\" (e.g. \"kg\"), not \"carbon_unit\" - sending \"carbon_unit\" directly is rejected with a pointer to this field.",
                "Rejects if a non-trashed entry in \"component\" already has this exact material_name.",
                "If \"component\" doesn't already exist in this chunk, it's created automatically, same as add_from_catalog.",
            ],
        },
        "trash_shortcut": {
            "endpoints": {
                "trash_or_restore": f"POST /{{project_id}}/{chunk}/trash",
                "list_trashed": f"GET /{{project_id}}/{chunk}/trash",
            },
            "description": (
                "Trash (or restore) one entry by id alone - you don't need "
                "to know or send its component; the server searches every "
                "component in this chunk for a matching id. GET the same "
                "path to list only the currently-trashed entries."
            ),
            "request_body": {
                "id": "string, required - the entry's id, see GET .../trash to find ids",
                "untrash": "bool, optional, default false - true restores the entry instead of trashing it",
            },
            "response": "{\"project_id\", \"chunk\", \"data\": <full chunk data (POST) or trashed-only data (GET)>}.",
            "notes": [
                "Idempotent - trashing an already-trashed entry (or restoring an already-active one) succeeds with no change.",
                "GET .../trash returns the same {component: [entry, ...]} shape as the main GET, but only entries with state.in_trash=true - components with none are omitted.",
            ],
        },
        "entry_schema": {
            "id": "server-generated UUID - use it to address the entry in patches",
            "values": {
                "material_name": "string, required",
                "unit": "string unit code, required - see this schema's \"units\" list, or \"custom_unit\" in update_semantics",
                "quantity": "number > 0, required",
                "unit_to_si": "number - SI conversion for the unit (server fills for known units)",
                "rate": "number >= 0, required - unit cost in project currency",
                "rate_source": "string or null - where the rate came from",
                "src_id": "string or null - source row id in the SOR database",
                "carbon_emission": "number or null - emission factor",
                "carbon_unit": "string or null - 'kgCO₂e/<unit>'",
                "carbon_emission_src": "string or null",
                "conversion_factor": "number or null - material unit -> carbon unit",
                "scrap_rate": "number or null - recyclability input",
                "post_demolition_recovery_percentage": "number 0-100 or null",
            },
            "state": {
                "in_trash": "bool - trashed entries are excluded from all totals",
                "included_in_carbon_emission": "bool",
                "included_in_recyclability": "bool",
                "allow_edit_checked": "bool - GUI edit-lock checkbox",
            },
        },
        "example_post_body_update": {
            "Girder" if chunk == "str_super_structure" else tab: [
                {"id": "<existing-entry-uuid>", "values": {"rate": 56000.0}},
            ],
        },
        "example_post_body_create": {
            "Girder" if chunk == "str_super_structure" else tab: [
                {"values": {"material_name": "Structural Steel", "unit": "MT",
                            "quantity": 12.5, "rate": 55000.0}},
            ],
        },
    }


for _chunk, _tab in _CHUNK_TABS.items():
    register_chunk(
        _chunk,
        page_name=_PAGE_NAME,
        widget_cls=StructureTabView,
        field_defs=None,
        # Lazy: _chunk_schema() calls list_available_units(), which changes
        # at runtime as custom units are defined - a plain dict here would
        # freeze the units list at import time. Default args bind the loop
        # variables per-chunk (the usual Python closure-in-loop fix).
        schema=lambda c=_chunk, t=_tab: _chunk_schema(c, t),
        validate_payload=_validate_payload,
        merge_payload=_merge_payload,
        redact_response=_redact_response,
        refresh_widget=_refresh_widget,
        add_from_catalog=_add_from_catalog,
        add_manual=_add_manual,
        trash_by_id=_trash_by_id,
        refresh_via_signal=True,
    )

register_chunk(
    "str_component_registry",
    page_name=_PAGE_NAME,
    widget_cls=StructureTabView,
    field_defs=None,
    schema={
        "chunk": "str_component_registry",
        "description": (
            "Bookkeeping registry of the component groups on each Construction "
            "Works tab (search categories, deletion flags). Derived/managed by "
            "the app - read it to see which components exist per chunk; it "
            "cannot be written via the API."
        ),
    },
    read_only=True,
    refresh_via_signal=True,
)
