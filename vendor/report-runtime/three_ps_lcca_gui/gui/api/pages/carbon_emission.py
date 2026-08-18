"""
gui/api/pages/carbon_emission.py

Registers the Carbon Emissions Data page's chunks. The page is a
CarbonEmissionTabView with five tabs, each owning its own chunk - but
`widget_map["Carbon Emissions Data"]` only ever gives back the tab-view
container, which has no get_data_dict()/load_data_dict() of its own (only an
aggregate get_data() used by the page's own "save all" path). So every chunk
here registers Tier C style (field_defs=None, refresh_via_signal=True): the
API writes via controller.save_chunk_data() only, never drives a widget
directly, and the affected tab repaints itself off an explicit refresh_widget
hook (same pattern as gui/api/pages/structure.py).

This file currently registers only "social_cost_data". The remaining three
sub-chunks (diversion_emissions, machinery_emissions_data,
transport_emissions_data) are tracked in
devtools/dev_notes_log/API_plan.md, Tier C item 6.

social_cost_data write semantics
---------------------------------
Two mutually exclusive modes, selected by "source". Only the ACTIVE mode's
fields are required - the inactive mode's sub-object is stored as-is (or
patched, if sent) but never required. POST body:

    {
        "source": "K. Ricke et al. (Country-Level)" | "Custom / Manual Override",
        "ricke":  {<subset of the 8 ricke fields + usd_to_local_rate/cpi_ratio>},
        "custom": {<subset of scc_value/source/comments>},
    }

All three top-level keys are optional - omitted ones keep their current
value (merge/PATCH semantics), same as every other chunk. "result" is
server-computed (mirrors RickeWidget.get_cost()/get_result_data() and
CustomWidget.get_result_data(), reused - not reimplemented - via the pure
module-level DB/lookup helpers in scc_tabs/ricke.py) and rejected if a
caller tries to send it directly.
"""

import copy

from three_ps_lcca_gui.gui.components.carbon_emission.main import CarbonEmissionTabView
from three_ps_lcca_gui.gui.components.carbon_emission.widgets.scc_widget import SCCWidget
from three_ps_lcca_gui.gui.components.carbon_emission.widgets.scc_tabs.custom import CUSTOM_FIELDS
from three_ps_lcca_gui.gui.components.carbon_emission.widgets.scc_tabs.ricke import (
    RICKE_FIELDS,
    _CLIMATE_LABEL_MAP,
    _CLOSEST_RCP,
    _DISC_MAP,
    _DMG_FUNC_LABEL_MAP,
    _DMG_PARAMS_LABEL_MAP,
    _PERCENTILE_MAP,
    _RCP_LABEL_MAP,
    _SSP_LABEL_MAP,
    _get_db,
    _lookup,
)
from three_ps_lcca_gui.gui.components.utils.common_requested_data import get_currency, get_project_iso3
from three_ps_lcca_gui.gui.components.utils.form_builder.form_builder import _PLACEHOLDER
from three_ps_lcca_gui.gui.components.utils.form_builder.form_definitions import FieldDef
from ..registry import register_chunk

_PAGE_NAME = "Carbon Emissions Data"

_SOURCE_RICKE = "K. Ricke et al. (Country-Level)"
_SOURCE_CUSTOM = "Custom / Manual Override"
_SOURCES = (_SOURCE_RICKE, _SOURCE_CUSTOM)


def _iso3_options() -> list[str]:
    try:
        df = _get_db()
        return sorted(df.index.get_level_values("ISO3").unique())
    except Exception:
        return []


def _field_schema(fd) -> dict:
    """Reduces a FieldDef (from RICKE_FIELDS/CUSTOM_FIELDS, both flat lists
    of FieldDef with no Section entries) to the same shape describe_chunk_fields
    produces for a normal FieldDef chunk, so callers see one consistent field
    schema format across the whole API."""
    info = {
        "key": fd.key,
        "label": fd.title,
        "description": fd.explanation,
        "field_type": fd.field_type,
        "unit": fd.unit or None,
        "required": fd.required,
        "default": fd.default,
    }
    if fd.field_type == "combo":
        info["options"] = list(fd.options) if fd.options else []
    elif fd.field_type == "float" and fd.options:
        info["min"], info["max"], info["decimals"] = fd.options
    return info


# Both lists mix in Section markers (used to group the GUI form into
# collapsible headings) alongside the actual FieldDefs - drop those here,
# same as describe_chunk_fields() does for ordinary field_defs chunks.
_RICKE_FIELD_DEFS = [fd for fd in RICKE_FIELDS if isinstance(fd, FieldDef)]
_CUSTOM_FIELD_DEFS = [fd for fd in CUSTOM_FIELDS if isinstance(fd, FieldDef)]
_RICKE_FIELD_MAP = {fd.key: fd for fd in _RICKE_FIELD_DEFS}
_CUSTOM_FIELD_MAP = {fd.key: fd for fd in _CUSTOM_FIELD_DEFS}
_RICKE_REQUIRED_KEYS = [fd.key for fd in _RICKE_FIELD_DEFS if fd.required]


def _social_cost_schema() -> dict:
    ricke_fields = []
    for fd in _RICKE_FIELD_DEFS:
        info = _field_schema(fd)
        if info["key"] == "iso3":
            # Drop the static FieldDef.options ["WLD"] placeholder (the GUI
            # only ever uses it before _populate_iso3() fills the real list
            # at runtime) - the real list is ~170 ISO3 codes (see
            # _iso3_options()), which would dominate this schema's size for
            # a field callers essentially never need to set (see "note"
            # below). Validity is still fully enforced when it matters: an
            # unrecognized/unusable code is caught by the same
            # no-data-in-SCC-database check any other bad combination hits
            # (_apply -> _ricke_cost), not by an enum check here.
            info.pop("options", None)
            info["note"] = (
                "Usually auto-set from the project's own country and "
                "locked (any value you send is ignored) - same as this "
                "field being disabled in the GUI. Omit it. Only becomes "
                "caller-settable if the project's country has no data in "
                "this specific database, in which case it defaults to "
                "'WLD' (global) unless you set an ISO 3166-1 alpha-3 code "
                "yourself."
            )
        ricke_fields.append(info)
    custom_fields = [_field_schema(fd) for fd in _CUSTOM_FIELD_DEFS]

    return {
        "chunk": "social_cost_data",
        "description": (
            "Social Cost of Carbon (SCC) tab. Two mutually exclusive modes, "
            "selected by \"source\": the Ricke et al. (2018) country-level "
            "SCC model (\"ricke\"), or a custom/manual override "
            "(\"custom\"). Both sub-objects are stored regardless of which "
            "is active, so switching source doesn't lose the other's inputs. "
            "\"result\" is server/GUI-computed from whichever mode is active "
            "- never caller-writable."
        ),
        "source_note": (
            "\"source\" is the MODE SELECTOR - it says which of the two "
            "calculation methods below is currently active and used for "
            "\"result\", NOT a data source/citation field (that's "
            "\"custom.source\", a free-text reference like a report name). "
            "Set \"source\" to "
            f"{_SOURCE_RICKE!r} to calculate the SCC from the Ricke et al. "
            "country-level model (\"ricke\" inputs), or to "
            f"{_SOURCE_CUSTOM!r} to use a manually-entered value "
            "(\"custom.scc_value\") instead of calculating one."
        ),
        "update_semantics": {
            "granularity": (
                "PATCH-like: send any subset of \"source\"/\"ricke\"/"
                "\"custom\" - omitted keys keep their current value. "
                "\"ricke\"/\"custom\" are themselves merged key-by-key, not "
                "replaced wholesale."
            ),
            "required_fields_depend_on_source": (
                "Only the ACTIVE mode's fields are required. If the "
                "resulting \"source\" (after this patch, or the current one "
                "if not sent) is Ricke: 7 of the 8 \"required\": true ricke "
                "fields must be filled by you (not left at \"-- select --\") "
                "- \"iso3\" is the 8th and is normally auto-set/locked (see "
                "its \"note\"), so you usually don't send it - and the "
                "resulting combination must resolve to a row in the "
                "underlying SCC database (see field_groups.ricke.iso3.note "
                "for how that's enforced). Custom fields are never "
                "required. If \"source\" is Custom, no field is required "
                "(matches the GUI) - ricke fields are never checked."
            ),
            "server_owned": (
                "\"result\" (selected_mode, cost_of_carbon_local, currency, "
                "unit) is computed from whichever mode is active after this "
                "patch - sending it directly is rejected."
            ),
        },
        # NOT "fields" - server.py's GET route treats a top-level "fields"
        # key as the flat-list shape FieldDef chunks use, and forwards ONLY
        # that key to the caller (dropping "description", "update_semantics",
        # the examples below, everything) - see get_chunk_data() in
        # gui/api/server.py. "field_groups" avoids that collision so the
        # whole schema (incl. usage notes an API caller needs) is what
        # actually reaches the response, not just the field list.
        "field_groups": {
            "source": {
                "label": "Mode",
                "description": (
                    "Which calculation mode is active for \"result\" - "
                    "Ricke et al. model vs. a manually-entered value. See "
                    "this schema's top-level \"source_note\" for details."
                ),
                "field_type": "combo",
                "options": list(_SOURCES),
            },
            "ricke": {
                "label": "Ricke et al. (Country-Level) inputs",
                "active_when": f"source == {_SOURCE_RICKE!r}",
                "fields": ricke_fields,
            },
            "custom": {
                "label": "Custom / Manual Override inputs",
                "active_when": f"source == {_SOURCE_CUSTOM!r}",
                "fields": custom_fields,
            },
            "result": {
                "label": "Computed result",
                "description": (
                    "Read-only. Recomputed by the server whenever the "
                    "active mode's inputs change."
                ),
                "fields": [
                    {"key": "selected_mode", "field_type": "text"},
                    {"key": "cost_of_carbon_local", "field_type": "float",
                     "unit": "Currency/kgCO2e"},
                    {"key": "currency", "field_type": "text"},
                    {"key": "unit", "field_type": "text"},
                ],
            },
        },
        "example_post_body_ricke": {
            "source": _SOURCE_RICKE,
            "ricke": {
                # "iso3" intentionally omitted - see field_groups.ricke.iso3.note
                "ssp": "SSP1 (Sustainability)",
                "rcp": "RCP4.5 (≈ +2.5°C in 2100)", "dmg_func": "BHM LR (Long Run)",
                "dmg_params": "Bootstrap (Full Uncertainty)",
                "climate_uncertainty": "Expected (Central Projections)",
                "discounting": "Growth-adjusted (prtp=1%, η=0.7)", "percentile": "50.0% (Central)",
                "usd_to_local_rate": 83.0, "cpi_ratio": 1.1,
            },
        },
        "example_post_body_custom": {
            "source": _SOURCE_CUSTOM,
            "custom": {"scc_value": 5.2, "source": "Internal guidance note"},
        },
    }


def _check_field(where: str, fd: FieldDef, value) -> list[str]:
    if fd.key == "iso3":
        # Not a combo-options check (see _social_cost_schema's "note" on
        # this field for why the ~170-code list isn't enumerated) - just a
        # cheap shape check here. _apply() overrides this value from the
        # project's own country whenever possible (see _resolve_iso3), and
        # for the rare case it doesn't, an unusable/unrecognized code is
        # caught by the same no-data-in-SCC-database check every other bad
        # ricke combination hits, which names the actual problem instead of
        # dumping the whole valid list on every unrelated typo.
        if not isinstance(value, str) or not value.strip():
            return [f"{where}.iso3: must be a non-empty string (ISO 3166-1 alpha-3 code, e.g. 'IND', or 'WLD' for global)"]
        return []
    if fd.field_type == "combo":
        options = fd.options or []
        if value not in options and value != _PLACEHOLDER:
            return [f"{where}.{fd.key}: {value!r} is not a valid option - must be one of {options}"]
        return []
    if fd.field_type == "float":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return [f"{where}.{fd.key}: must be a number, got {value!r}"]
        if fd.options:
            low, high = fd.options[0], fd.options[1]
            if not (low <= value <= high):
                return [f"{where}.{fd.key}: {value} is out of range [{low}, {high}]"]
        return []
    if not isinstance(value, str):
        return [f"{where}.{fd.key}: must be a string, got {value!r}"]
    return []


def _check_sub_patch(where: str, patch, field_map: dict) -> list[str]:
    if not isinstance(patch, dict):
        return [f"'{where}' must be an object"]
    errors = []
    unknown = set(patch) - set(field_map)
    if unknown:
        errors.append(f"'{where}': unrecognized key(s) {sorted(unknown)} - allowed: {sorted(field_map)}")
    for key, value in patch.items():
        fd = field_map.get(key)
        if fd is not None:
            errors.extend(_check_field(where, fd, value))
    return errors


def _ricke_cost(ricke: dict) -> float | None:
    """Mirrors RickeWidget.get_cost() (scc_tabs/ricke.py) exactly, but off a
    plain dict instead of live QWidget field values - reuses the same pure
    label maps/DB lookup, not a reimplementation."""
    iso3, ssp_label, rcp_label = ricke.get("iso3"), ricke.get("ssp"), ricke.get("rcp")
    dmg_label, par_label = ricke.get("dmg_func"), ricke.get("dmg_params")
    cli_label, dis_label, pct_label = (
        ricke.get("climate_uncertainty"), ricke.get("discounting"), ricke.get("percentile"),
    )
    if any(v in (None, "", _PLACEHOLDER) for v in
           (iso3, ssp_label, rcp_label, dmg_label, par_label, cli_label, dis_label, pct_label)):
        return None

    ssp = _SSP_LABEL_MAP.get(ssp_label)
    rcp_raw = _RCP_LABEL_MAP.get(rcp_label)
    rcp = rcp_raw if rcp_raw is not None else _CLOSEST_RCP.get(ssp, "rcp60")
    run = _DMG_FUNC_LABEL_MAP.get(dmg_label)
    dmgfuncpar = _DMG_PARAMS_LABEL_MAP.get(par_label)
    climate = _CLIMATE_LABEL_MAP.get(cli_label)
    disc = _DISC_MAP.get(dis_label)
    pct_idx = _PERCENTILE_MAP.get(pct_label)
    if any(v is None for v in (ssp, run, dmgfuncpar, climate, disc, pct_idx)):
        return None

    try:
        result, reason = _lookup(_get_db(), iso3, run, dmgfuncpar, climate, ssp, rcp, disc)
    except Exception:
        return None
    if reason != "ok":
        return None

    cpi_ratio = ricke.get("cpi_ratio") or 1.0
    usd_to_local = ricke.get("usd_to_local_rate") or 1.0
    # DB values are USD/tCO2; system expects currency/kgCO2e -> divide by 1000.
    return result[pct_idx] * cpi_ratio * usd_to_local / 1000


def _resolve_iso3(current_value) -> str:
    """Mirrors RickeWidget._apply_country_lock() exactly: if the project's
    own ISO3 has data in the SCC DB, it's used and locked (any caller value
    for "ricke.iso3" is silently overridden here, same as the GUI disabling
    that combo) - otherwise the field stays whatever was already stored (or
    defaults to WLD if unset), matching the GUI's fallback branch."""
    project_iso3 = get_project_iso3()
    if project_iso3 and project_iso3 in _iso3_options():
        return project_iso3
    if current_value in (None, "", _PLACEHOLDER):
        return "WLD"
    return current_value


def _result_for(merged: dict, ricke_cost: float | None = None) -> dict:
    """`ricke_cost` lets the caller pass in a cost already computed by
    _ricke_cost() during validation (see _apply) so the DB lookup isn't
    repeated - pass None to have this recompute it itself (e.g. for a
    chunk that was never validated through _apply, such as GET-time reuse)."""
    source = merged.get("source")
    currency = merged.get("result", {}).get("currency") or get_currency()
    if source == _SOURCE_RICKE:
        cost = ricke_cost if ricke_cost is not None else _ricke_cost(merged.get("ricke", {}))
    elif source == _SOURCE_CUSTOM:
        cost = merged.get("custom", {}).get("scc_value")
    else:
        cost = None
    return {
        "selected_mode": source,
        "cost_of_carbon_local": float(cost) if cost is not None else 0.0,
        "currency": currency,
        "unit": f"{currency}/kgCO₂e",
    }


_TOP_KEYS = {"source", "ricke", "custom"}


def _apply(current: dict, payload: dict) -> tuple[dict, list[str]]:
    """Pure merge + validate of `payload` into `current`. Returns
    (merged, errors); on any error the merge result must be discarded."""
    errors: list[str] = []
    if not isinstance(payload, dict) or not payload:
        return current, ["payload must be a non-empty object with any of: source, ricke, custom"]

    unknown = set(payload) - _TOP_KEYS
    if unknown:
        errors.append(f"unrecognized key(s) {sorted(unknown)} - allowed: {sorted(_TOP_KEYS)} ('result' is server-computed, never caller-writable)")

    source = payload.get("source", current.get("source"))
    if "source" in payload and source not in _SOURCES:
        errors.append(f"'source': {source!r} is not a valid option - must be one of {list(_SOURCES)}")

    if "ricke" in payload:
        errors.extend(_check_sub_patch("ricke", payload["ricke"], _RICKE_FIELD_MAP))
    if "custom" in payload:
        errors.extend(_check_sub_patch("custom", payload["custom"], _CUSTOM_FIELD_MAP))

    if errors:
        return current, errors

    merged = copy.deepcopy(current)
    if "source" in payload:
        merged["source"] = source
    merged.setdefault("ricke", {}).update(payload.get("ricke", {}))
    merged.setdefault("custom", {}).update(payload.get("custom", {}))
    # Runs unconditionally (not just when source is Ricke) so switching
    # source to Ricke later, after iso3 was never explicitly set, still
    # finds it correctly resolved - same as the GUI locking/defaulting the
    # combo the moment the tab is built, before the user ever picks a mode.
    merged["ricke"]["iso3"] = _resolve_iso3(merged["ricke"].get("iso3"))

    ricke_cost = None
    if source == _SOURCE_RICKE:
        missing = [
            _RICKE_FIELD_MAP[k].title for k in _RICKE_REQUIRED_KEYS
            if merged["ricke"].get(k) in (None, "", _PLACEHOLDER)
        ]
        if missing:
            errors.append(f"ricke: missing required field(s) (source is {_SOURCE_RICKE!r}): {', '.join(missing)}")
        else:
            # Single source of truth: run the SAME function that computes
            # the saved result to decide whether this combination is even
            # usable, instead of a separate combination-checking function
            # that could drift out of sync with it. None covers every way a
            # combination can be unusable - no DB row, or the underlying
            # pickle's occasional malformed "NA"-as-string cells that raise
            # instead of cleanly reporting missing data (_ricke_cost already
            # catches those) - so a caller never gets 0.0 silently saved for
            # a combination that doesn't actually resolve to real data.
            ricke_cost = _ricke_cost(merged["ricke"])
            if ricke_cost is None:
                errors.append(
                    "ricke: selected combination has no data in the SCC "
                    "database - change one or more of "
                    "iso3/ssp/rcp/dmg_func/dmg_params/climate_uncertainty/discounting"
                )
    # source == _SOURCE_CUSTOM (or unset): no required fields, mirrors the GUI.

    if errors:
        return current, errors

    merged["result"] = _result_for(merged, ricke_cost)
    return merged, errors


def _validate_payload(payload: dict, current: dict | None) -> list[str]:
    if current is None:
        # Server-side pre-check without stored data (Flask worker thread,
        # before the main-thread round-trip): structural checks only.
        if not isinstance(payload, dict) or not payload:
            return ["payload must be a non-empty object with any of: source, ricke, custom"]
        unknown = set(payload) - _TOP_KEYS
        errors = [f"unrecognized key(s) {sorted(unknown)} - allowed: {sorted(_TOP_KEYS)}"] if unknown else []
        if "ricke" in payload and not isinstance(payload["ricke"], dict):
            errors.append("'ricke' must be an object")
        if "custom" in payload and not isinstance(payload["custom"], dict):
            errors.append("'custom' must be an object")
        return errors
    _merged, errors = _apply(current, payload)
    return errors


def _merge_payload(current: dict, payload: dict) -> dict:
    merged, _errors = _apply(current, payload)
    return merged


def _refresh_widget(page_widget, chunk: str) -> None:
    """Called by the bridge, on the main thread, only after its own write
    and only if `page_widget` (the CarbonEmissionTabView) is already open -
    reuses SCCWidget's own refresh_from_engine(), which re-fetches this
    chunk and reloads both sub-tabs, exactly like a GUI-native chunk_updated
    listener would.

    RickeWidget.load_data_dict() (base_widget.py) blocks all widget signals
    while it sets values - including the currentTextChanged/valueChanged
    connections _connect_combo_logging() uses to trigger _print_ricke_cost(),
    the method that actually repaints the displayed SCC value/range labels.
    So refresh_from_engine() alone updates the fields but leaves those labels
    showing the pre-write value. Call it explicitly here, once, right after
    the reload - scoped to the API write path only, not a change to
    RickeWidget's own reload behavior."""
    for i in range(page_widget.tab_view.count()):
        tab = page_widget.tab_view.widget(i)
        if isinstance(tab, SCCWidget):
            tab.refresh_from_engine()
            tab._sub_a._print_ricke_cost()
            return


register_chunk(
    "social_cost_data",
    page_name=_PAGE_NAME,
    widget_cls=CarbonEmissionTabView,
    field_defs=None,
    schema=_social_cost_schema,
    validate_payload=_validate_payload,
    merge_payload=_merge_payload,
    refresh_widget=_refresh_widget,
    refresh_via_signal=True,
)
