"""
gui/api/registry.py

Chunk-agnostic API engine: the registry pages register themselves into, plus
the schema introspection and payload validation logic that runs off it. None
of this file knows anything about Bridge Data specifically - see
gui/api/pages/ for how each page plugs in.

Two kinds of registrations:

- FieldDef form pages (Tier A/B): pass `field_defs` (+ optional warn_rules) -
  schema and validation are derived automatically.
- Table/nested pages (Tier C/D): pass `field_defs=None` and a hand-written
  `schema` dict, plus optional pure hooks `validate_payload(payload, current)`
  and `merge_payload(current, payload)`. `refresh_via_signal=True` makes the
  bridge write via the controller only (no widget driving) and let the page
  repaint itself off `controller.chunk_updated`. `read_only=True` rejects
  POSTs with 405.
"""

from three_ps_lcca_gui.gui.components.utils.form_builder.form_definitions import (
    FieldDef,
    Section,
)

# chunk_name -> registration entry (see register_chunk for the shape).
# Populated by importing gui/api/pages (each module there calls register_chunk()
# as a side effect of being imported). Never edit this dict directly - use
# register_chunk() so every entry has a consistent shape.
CHUNK_PAGE_MAP: dict = {}


def register_chunk(
    chunk: str,
    *,
    page_name: str,
    widget_cls=None,
    field_defs: list | None = None,
    warn_rules: dict | None = None,
    schema: dict | None = None,
    validate_payload=None,
    merge_payload=None,
    redact_response=None,
    refresh_widget=None,
    add_from_catalog=None,
    add_manual=None,
    trash_by_id=None,
    read_only: bool = False,
    refresh_via_signal: bool = False,
    dynamic_options: dict | None = None,
) -> None:
    """Registers a chunk with the API. Call this once, at import time, from a
    module under gui/api/pages/ - see pages/bridge_data.py for the pattern.

    chunk        - chunk name as stored by the engine (e.g. "bridge_data")
    page_name    - key in ProjectWindow.widget_map for this page's widget
    widget_cls   - the page widget's class (its `_LOCKED` set, if any, marks
                   fields the API must never let a caller change). May be None
                   for chunks not driven through a widget.
    field_defs   - the FieldDef/Section list driving that page's form, or None
                   for table/nested chunks (then pass `schema` instead)
    warn_rules   - optional dict of {field_key: (low, high, ...)} warn ranges.
                   Keys not in the dict fall back to each FieldDef's own
                   `warn=` tuple, so pages that declare warns inline (e.g.
                   Maintenance) are covered without a module-level dict.
    schema       - hand-written schema dict returned by describe_chunk_fields
                   for chunks without field_defs (Tier C/D pages)
    validate_payload - optional pure hook `(payload, current) -> list[str]`
                   replacing the FieldDef validator for this chunk
    merge_payload    - optional pure hook `(current, payload) -> dict`
                   replacing the default top-level {**current, **payload}
    redact_response  - optional pure hook `(data) -> data` applied to the
                   "data" field of GET/POST responses only - the full data
                   (as returned by this hook's input) is still what's stored
                   on disk. Used to keep server-owned bookkeeping (e.g. entry
                   "meta") out of what callers see without weakening what's
                   persisted.
    refresh_widget   - optional hook `(page_widget, chunk)`, called by the
                   bridge on the main thread AFTER its own write, and ONLY
                   if `page_widget` is already open (in win.widget_map) - so
                   it repaints the GUI to reflect an API write without ever
                   running as a side effect of the GUI's own native actions
                   (which already update themselves and would double-render
                   if something else also refreshed on every write).
    add_from_catalog - optional hook `(current, payload, registry, chunk) ->
                   (merged, registry_patch, warning, errors)` powering
                   POST /{project_id}/{chunk}/add_from_catalog - a single-
                   material "search the catalog by exact name and add it"
                   shortcut, separate from the generic entry-patch POST.
                   `current` is the chunk's stored data, `registry` a
                   sibling chunk's data the hook may also need (e.g. the
                   component registry); `merged`/`registry_patch` are only
                   read if `errors` is empty, `registry_patch` only applied
                   if not None.
    add_manual   - optional hook, same signature/contract as add_from_catalog,
                   powering POST /{project_id}/{chunk}/add_manual - a single-
                   material "give me the values directly" shortcut (flat
                   {component, values} body, no catalog lookup).
    trash_by_id  - optional hook `(current, payload) -> (merged, errors)`
                   powering POST /{project_id}/{chunk}/trash - trashes one
                   entry addressed by `{"id": ...}` alone (no component
                   needed - the hook searches for it).
    read_only    - POSTs are rejected with 405 read_only_chunk
    refresh_via_signal - bridge updates write via the controller only and emit
                   controller.chunk_updated; the page widget (which has no
                   load_data_dict) repaints itself from that signal
    dynamic_options - optional {field_key: (current_data) -> list[str]} for
                   FieldDef combo fields whose real options aren't known at
                   FieldDef-declaration time and are instead computed at
                   runtime from the chunk's own stored data - e.g.
                   general_info's "sor_database", whose GUI widget
                   (GeneralInfo._populate_sor_combo) fills the combo from
                   the material catalog filtered by project_country, not
                   from a fixed list. Without this, describe_chunk_fields()
                   would always report that field's static (placeholder,
                   usually empty) FieldDef.options instead of what the GUI
                   actually offers. Called fresh on every GET - never
                   cached - so it reflects the chunk's current data (e.g.
                   the current project_country).
    """
    merged_warns = dict(warn_rules or {})
    for fd in field_defs or []:
        if isinstance(fd, FieldDef) and fd.warn and fd.key not in merged_warns:
            merged_warns[fd.key] = fd.warn

    CHUNK_PAGE_MAP[chunk] = {
        "page_name": page_name,
        "widget_cls": widget_cls,
        "field_defs": field_defs,
        "warn_rules": merged_warns,
        "schema": schema,
        "validate_payload": validate_payload,
        "merge_payload": merge_payload,
        "redact_response": redact_response,
        "refresh_widget": refresh_widget,
        "add_from_catalog": add_from_catalog,
        "add_manual": add_manual,
        "trash_by_id": trash_by_id,
        "read_only": read_only,
        "refresh_via_signal": refresh_via_signal,
        "dynamic_options": dynamic_options or {},
    }


def describe_chunk_fields(chunk: str, data: dict | None = None) -> dict | None:
    """Static schema for a chunk's fields - label, type, options/min/max,
    unit, required/locked flags, default, and warn-range if any. Pure data
    introspection (no Qt/engine access), safe to call from any thread.
    Returns None if `chunk` isn't registered.

    FieldDef chunks derive the schema from their defs; schema-registered
    chunks (field_defs=None) return their hand-written schema. `schema` may
    be a plain dict (computed once, at register_chunk time) or a zero-arg
    callable (invoked fresh on every call) - use a callable for anything that
    can change at runtime, e.g. a units list that grows as custom units are
    defined, so GET never serves a stale snapshot.

    `data` - the chunk's current stored data (as returned by GET), used only
    to evaluate `dynamic_options` hooks (e.g. general_info's "sor_database",
    whose real options depend on project_country) - pass None to skip that
    (options then fall back to the field's static FieldDef.options, usually
    empty for a dynamic field)."""
    entry = CHUNK_PAGE_MAP.get(chunk)
    if entry is None:
        return None

    if entry["field_defs"] is None:
        raw_schema = entry.get("schema") or {}
        schema = dict(raw_schema() if callable(raw_schema) else raw_schema)
        schema.setdefault("chunk", chunk)
        if entry.get("read_only"):
            schema.setdefault("read_only", True)
        return schema

    locked_keys = getattr(entry["widget_cls"], "_LOCKED", set())
    warn_rules = entry.get("warn_rules", {})
    dynamic_options = entry.get("dynamic_options") or {}

    fields = []
    for item in entry["field_defs"]:
        if isinstance(item, Section):
            fields.append({"type": "section", "title": item.title})
            continue
        info = _describe_field(item, locked_keys, warn_rules)
        provider = dynamic_options.get(info["key"])
        if provider is not None and data is not None:
            try:
                info["options"] = list(provider(data))
            except Exception:
                pass  # keep the static (fallback) options rather than 500ing the whole GET
        fields.append(info)

    return {"chunk": chunk, "fields": fields}


def _describe_field(fd: FieldDef, locked_keys: set, warn_rules: dict) -> dict:
    info = {
        "type": "field",
        "key": fd.key,
        "label": fd.title,
        "description": fd.explanation,
        "field_type": fd.field_type,
        "unit": fd.unit or None,
        "required": fd.required,
        "default": fd.default,
        "locked": fd.key in locked_keys or fd.blocked,
    }

    if fd.field_type == "combo":
        info["options"] = list(fd.options) if fd.options else []
    elif fd.field_type == "int" and fd.options:
        info["min"], info["max"] = fd.options
    elif fd.field_type == "float" and fd.options:
        info["min"], info["max"], info["decimals"] = fd.options
    elif fd.field_type == "upload_img":
        # Accepts either a raw base64 string (as stored) or an http(s) image
        # URL - see gui/api/image_upload.py, which fetches/decodes + validates
        # both before the payload reaches storage. Only JPEG/PNG are accepted;
        # anything else (GIF included) is rejected regardless of source.
        info["format"] = "base64_or_url"
        info["accepted_image_formats"] = ["JPEG", "PNG"]

    # A page can declare warn ranges two ways: a module-level {key: (...)}
    # dict passed to register_chunk() as warn_rules (e.g. bridge_data,
    # demolition), or inline per-field via FieldDef(..., warn=(...)) (e.g.
    # maintenance). The external dict takes precedence if both are present.
    warn = warn_rules.get(fd.key) or fd.warn
    if warn:
        low, high = warn[0], warn[1]
        info["warn_range"] = {"low": low, "high": high}

    return info


def validate_payload_keys(chunk: str, payload: dict, current: dict | None = None) -> list[str]:
    """Checks a POST payload against the chunk's field schema before it ever
    reaches a widget. Catches what `_apply_value()` in base_widget.py would
    otherwise silently swallow - e.g. a combo value not in its options list
    just fails `findText()` and no-ops, so the caller would get a 200 with
    their change quietly dropped. Returns a list of human-readable errors;
    empty list means the payload is valid. Pure data check, no Qt/engine
    access - safe to call from the Flask worker thread directly.

    Chunks registered with a `validate_payload` hook delegate to it (`current`
    is the stored chunk data, or None when the caller can't supply it - hooks
    must tolerate that)."""
    entry = CHUNK_PAGE_MAP.get(chunk)
    if entry is None:
        return []

    if entry.get("validate_payload") is not None:
        return entry["validate_payload"](payload, current)

    if entry["field_defs"] is None:
        return []

    field_map = {fd.key: fd for fd in entry["field_defs"] if isinstance(fd, FieldDef)}
    errors = []

    for key, value in payload.items():
        fd = field_map.get(key)
        if fd is None:
            errors.append(f"'{key}' is not a recognized field for {chunk}")
            continue

        if fd.field_type == "combo":
            options = fd.options or []
            if value not in options:
                errors.append(f"'{key}': {value!r} is not a valid option - must be one of {options}")

        elif fd.field_type in ("int", "float"):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                errors.append(f"'{key}': must be a number, got {value!r}")
                continue
            if fd.options:
                low, high = fd.options[0], fd.options[1]
                if not (low <= value <= high):
                    errors.append(f"'{key}': {value} is out of range [{low}, {high}]")

        elif fd.field_type in ("text", "textarea", "phone", "upload_img") and not isinstance(value, str):
            errors.append(f"'{key}': must be a string, got {value!r}")

    return errors
