"""
gui/api/server.py

Local HTTP API for driving the open GUI. Runs a Flask app inside a werkzeug
dev server on a daemon thread so it can be started/stopped alongside the Qt
event loop without blocking it.

Routes are fully generic: GET/POST /<project_id>/<chunk>, where <chunk> is
anything registered in registry.CHUNK_PAGE_MAP (see gui/api/pages/). GET is
self-describing - it returns the field schema (describe_chunk_fields)
alongside the data so a caller never needs a second lookup to know how to
build a valid POST body. Adding a new page never requires touching this file
- see gui/api/pages/__init__.py for how.

Discovery: GET / and GET /help are unauthenticated and return full API
documentation - same convention as GitHub/Stripe leaving their docs public
while the data endpoints require a token. Every error response also carries
a `documentation_url` pointing here (RFC 7807 / GitHub API style), so a
caller that's never seen the docs can always find its way there.
"""

import threading

from flask import Flask, jsonify, request
from werkzeug.serving import make_server

from .bridge import ApiBridge
from .catalog import register_catalog_routes
from .image_upload import resolve_image_urls
from .registry import CHUNK_PAGE_MAP, describe_chunk_fields, validate_payload_keys
from . import tokens

DEFAULT_PORT = 8765

_active_port: int | None = None


def get_active_port() -> int | None:
    """Returns the port the API server is currently listening on, or None if it
    isn't running (disabled in settings, or failed to bind at startup)."""
    return _active_port


def _base_url() -> str:
    return f"http://127.0.0.1:{_active_port}"


def _documentation_url() -> str:
    return f"{_base_url()}/help"


def _help_payload() -> dict:
    """Full, unauthenticated API documentation - the single source of truth
    an LLM/agent (or anyone else) can discover cold, with zero prior context
    and no token, by hitting GET / or GET /help. Structured like a compact
    API reference: quickstart, auth, per-endpoint request/response/example,
    conventions, and error catalogue."""
    base = _base_url()
    return {
        "api": {
            "name": "3psLCCA Local GUI API",
            "version": "1",
            "description": (
                "Read and update an open project's data live in the running "
                "3psLCCA desktop app over HTTP. Every change made through this "
                "API appears immediately in the GUI and is persisted."
            ),
            "base_url": base,
            "host_note": (
                "Bound to 127.0.0.1 only - not reachable from other machines. "
                "The port defaults to 8765 but is picked automatically at "
                "startup if that port is busy; it is not user-configurable. "
                "Trust base_url, or read the actual port from the app under "
                "File > API Access or Settings."
            ),
        },
        "quickstart": [
            f"1. GET {base}/projects - find your project_id (no token needed).",
            f"2. If the project is not open yet: POST {base}/projects/open "
            "with body {\"project_id\": \"...\"}, then wait/poll until it is.",
            "3. Get the project's API token from a human: in the desktop app, "
            "File > API Access shows it (tokens are never returned by the API).",
            f"4. GET {base}/{{project_id}}/{{page}} with header 'X-API-Token: "
            "<token>' - the response contains both the data and the full field "
            "schema (types, options, ranges, locked flags).",
            "5. POST the same URL with only the fields you want to change - "
            "omitted fields keep their current value.",
        ],
        "authentication": {
            "type": "per-project bearer token",
            "header": "X-API-Token",
            "required_for": "all /{project_id}/{page} data endpoints",
            "not_required_for": "discovery and project management endpoints (see endpoints list)",
            "not_required_on": [
                "GET /", "GET /help", "GET /projects", "GET /projects/active",
                "GET /projects/new", "POST /projects/open", "POST /projects/new",
            ],
            "how_to_obtain": (
                "Only from the desktop app: open the project, then File > 'API "
                "Access'. The dialog shows the token with Generate/Regenerate/"
                "Revoke controls. This is deliberate - the API never returns a "
                "token, so a human stays in the loop for data access."
            ),
            "lifetime": (
                "Tokens live in memory only: they reset on every app restart "
                "and are cleared when the project window closes. On a 401, ask "
                "the user for the current token rather than retrying."
            ),
        },
        "endpoints": [
            {
                "method": "GET",
                "path": "/help",
                "auth_required": False,
                "summary": (
                    "This document, always as JSON. GET / serves the same "
                    "content as a human-readable HTML page in browsers."
                ),
            },
            {
                "method": "GET",
                "path": "/projects",
                "auth_required": False,
                "summary": "List every project on this machine.",
                "response": (
                    "{\"projects\": [{project_id, display_name, created_at, "
                    "last_modified, status, open}]} - \"open\" tells whether "
                    "the project is currently open in the app (i.e. reachable "
                    "by data endpoints). status \"locked\" also applies to "
                    "projects open in this very app, so use \"open\", not "
                    "status, to decide reachability."
                ),
                "example": f"curl {base}/projects",
            },
            {
                "method": "GET",
                "path": "/projects/active",
                "auth_required": False,
                "summary": "Like GET /projects, filtered to projects currently open in the app.",
                "response": "{\"projects\": [...same shape...], \"count\": <int>}",
                "example": f"curl {base}/projects/active",
            },
            {
                "method": "POST",
                "path": "/projects/open",
                "auth_required": False,
                "summary": "Open a project in the app (or focus it if already open).",
                "request_body": "{\"project_id\": \"<id from GET /projects>\"}",
                "response": (
                    "{\"project_id\", \"status\": \"opening\"|\"already_open\", \"note\"}. "
                    "Opening is asynchronous: poll GET /{project_id}/{page} "
                    "until it stops returning project_not_open. Unknown ids "
                    "return 404 project_not_found."
                ),
                "example": (
                    f"curl -X POST {base}/projects/open "
                    "-d '{\"project_id\": \"proj_a1b2c3d4\"}'"
                ),
            },
            {
                "method": "GET",
                "path": "/projects/new",
                "auth_required": False,
                "summary": "Field schema for POST /projects/new - the valid country/unit_system options and the country-to-currency map.",
                "response": (
                    "{\"fields\": {project_name, country, unit_system}, "
                    "\"currency_by_country\": {<country>: <currency code>}, \"notes\"}. "
                    "GET this before POSTing to avoid guessing valid country strings."
                ),
                "example": f"curl {base}/projects/new",
            },
            {
                "method": "POST",
                "path": "/projects/new",
                "auth_required": False,
                "summary": "Create and open a new project.",
                "request_body": (
                    "{\"project_name\": \"<string, required>\", "
                    "\"country\": \"<string, required - must exactly match the "
                    "app's country list; a 400 on a bad value returns the full "
                    "valid list>\", "
                    "\"unit_system\": \"metric\"|\"imperial\" (optional, default metric)}"
                ),
                "response": (
                    "{\"project_id\", \"currency\", \"status\": \"created\", \"note\"}. "
                    "Currency is derived from the country and cannot be "
                    "supplied - sending a \"currency\" key is a 400. Country, "
                    "currency and unit system are permanent after creation."
                ),
                "example": (
                    f"curl -X POST {base}/projects/new "
                    "-d '{\"project_name\": \"Highway 5 Bridge\", \"country\": \"India\"}'"
                ),
            },
            {
                "method": "GET",
                "path": "/{project_id}/{page}",
                "auth_required": True,
                "summary": "Read a page's current data plus its full field schema in one call.",
                "response": (
                    "{\"project_id\", \"chunk\", \"data\": {field: value}, "
                    "\"fields\": [{key, label, description, field_type, unit, "
                    "required, default, locked, options?, min?, max?, "
                    "decimals?, warn_range?}]} - everything needed to build a "
                    "valid POST body, no second lookup required."
                ),
                "example": (
                    f"curl {base}/proj_a1b2c3d4/bridge_data "
                    "-H 'X-API-Token: <token>'"
                ),
            },
            {
                "method": "POST",
                "path": "/{project_id}/{page}",
                "auth_required": True,
                "summary": "Update a page. Merge semantics: send only the fields to change.",
                "request_body": (
                    "JSON object with any subset of the page's fields. Omitted "
                    "fields keep their current value; unknown keys or invalid "
                    "values reject the whole request with 400 (nothing is "
                    "partially applied)."
                ),
                "response": (
                    "{\"project_id\", \"chunk\", \"data\": <full saved data>, "
                    "\"validation\": <the GUI's own validation result>, "
                    "\"locked_fields_skipped\"?: [...], \"warning\"?: \"...\"} - "
                    "locked fields are never changed; attempts are reported in "
                    "locked_fields_skipped rather than erroring."
                ),
                "example": (
                    f"curl -X POST {base}/proj_a1b2c3d4/bridge_data "
                    "-H 'X-API-Token: <token>' "
                    "-d '{\"bridge_location\": \"Delhi\"}'"
                ),
            },
            {
                "method": "GET",
                "path": "/{project_id}/validate",
                "auth_required": True,
                "summary": (
                    "Actually operates the GUI's own \"Calculate\" button - "
                    "the open project window's Results page updates exactly "
                    "like a native click (error/warning report, or a success "
                    "indicator plus the real calculation). If the project is "
                    "clean, this call waits for that calculation to finish "
                    "and returns its results in the same response - the "
                    "computed numbers are never persisted to disk, only kept "
                    "in memory on the Results page, so this is the only way "
                    "to read them via the API. Never changes any stored "
                    "chunk data - only Results-page cache/UI state, same as "
                    "clicking the button yourself. If the project is "
                    "already locked (see POST /{project_id}/unlock below), "
                    "this returns 423 project_locked instead of recalculating."
                ),
                "response": (
                    "{\"project_id\", \"valid\": bool, "
                    "\"errors\": {<page name>: [msg, ...]}, "
                    "\"warnings\": {<page name>: [msg, ...]}, "
                    "\"page_chunks\": {<page name>: [chunk id, ...]}, "
                    "\"results\": {results, analysis_period, currency} | "
                    "null - \"all_data\" (every input page's full raw chunk "
                    "data, just an echo of what was already POSTed - "
                    "dwarfed everything else here, ~98% of bytes) and "
                    "\"lcc_breakdown\" (an internal report-building "
                    "intermediate, not meant for direct reading) are "
                    "deliberately excluded. ERRORS must be "
                    "resolved - they block calculation (\"valid\": true "
                    "means zero errors across every page, and is required "
                    "for \"results\" to be non-null). WARNINGS never block "
                    "anything - advisory only. \"page_chunks\" maps each "
                    "page name appearing in errors/warnings to the chunk "
                    "id(s) to GET/POST to fix it (a page name alone isn't "
                    "directly callable, and one page can span several "
                    "chunks). Pages with neither an error nor a warning are "
                    "omitted everywhere."
                ),
                "example": (
                    f"curl {base}/proj_a1b2c3d4/validate "
                    "-H 'X-API-Token: <token>'"
                ),
            },
            {
                "method": "POST",
                "path": "/{project_id}/unlock",
                "auth_required": True,
                "summary": (
                    "The only way to clear a locked project (see "
                    "project_locked in the error catalogue below) - every "
                    "write route, including GET /{project_id}/validate, "
                    "returns 423 while locked. Reuses the GUI lock button's "
                    "own unlock logic, minus its confirmation dialog (this "
                    "call is itself the confirmation)."
                ),
                "response": (
                    "{\"project_id\", \"status\": \"unlocked\"|"
                    "\"already_unlocked\", \"note\"}. Idempotent - "
                    "unlocking an already-unlocked project is a no-op 200, "
                    "not an error. Clears the cached calculation results and "
                    "re-enables editing on every page; does not change any "
                    "input data."
                ),
                "example": (
                    f"curl -X POST {base}/proj_a1b2c3d4/unlock "
                    "-H 'X-API-Token: <token>'"
                ),
            },
            {
                "method": "POST",
                "path": "/{project_id}/{chunk}/add_from_catalog",
                "auth_required": True,
                "summary": (
                    "Construction Works chunks (str_*) only: add exactly one "
                    "material by its exact catalog name - simpler than "
                    "\"catalog_item\" on POST /{project_id}/{chunk} since you "
                    "don't have to paste the full row yourself."
                ),
                "request_body": (
                    "{\"component\" (auto-created if new), \"db_key\", "
                    "\"material_name\" (exact, case-insensitive - ambiguous "
                    "or no match is rejected), \"quantity\", "
                    "\"include_in_carbon_emission\"?, "
                    "\"include_in_recyclability\"?, \"scrap_rate\"?, "
                    "\"post_demolition_recovery_percentage\"?} - see the "
                    "chunk's own schema (\"add_from_catalog\" key) for full "
                    "field rules. Exactly one material per call."
                ),
                "response": "{\"project_id\", \"chunk\", \"data\": <full chunk data>, \"warning\"?}.",
                "example": (
                    f"curl -X POST {base}/proj_a1b2c3d4/str_super_structure/add_from_catalog "
                    "-H 'X-API-Token: <token>' "
                    "-d '{\"component\": \"Girder\", \"db_key\": \"INDIA/Bihar/RCD SOR 2025\", "
                    "\"material_name\": \"Structural Steel main Girder (Fe 410 B)\", \"quantity\": 12.5}'"
                ),
            },
            {
                "method": "POST",
                "path": "/{project_id}/{chunk}/add_manual",
                "auth_required": True,
                "summary": (
                    "Construction Works chunks (str_*) only: add exactly one "
                    "material with values you supply directly - no catalog "
                    "lookup. Flat {component, values} body, not the generic "
                    "endpoint's {component: [patch]} list-wrapped form."
                ),
                "request_body": (
                    "{\"component\" (auto-created if new), \"values\": "
                    "{\"material_name\", \"unit\", \"quantity\", \"rate\" "
                    "required; \"rate_source\"?, \"src_id\"?, "
                    "\"carbon_emission\"?, \"carbon_unit_den\"?, "
                    "\"carbon_emission_src\"?, \"conversion_factor\"?, "
                    "\"scrap_rate\"?, \"post_demolition_recovery_percentage\"?}, "
                    "\"state\": {\"included_in_carbon_emission\"?, "
                    "\"included_in_recyclability\"?}, \"custom_unit\"?} - see "
                    "the chunk's own schema (\"add_manual\" key) for full field "
                    "rules. \"carbon_unit_den\" is just the denominator (e.g. "
                    "\"kg\") - the server builds the full \"kgCO₂e/<unit>\" "
                    "string, so you never type the ₂ subscript by hand."
                ),
                "response": "{\"project_id\", \"chunk\", \"data\": <full chunk data>}.",
                "example": (
                    f"curl -X POST {base}/proj_a1b2c3d4/str_super_structure/add_manual "
                    "-H 'X-API-Token: <token>' "
                    "-d '{\"component\": \"Girder\", \"values\": {\"material_name\": \"Cement\", "
                    "\"unit\": \"kg\", \"quantity\": 40, \"rate\": 350, "
                    "\"carbon_emission\": 0.9, \"carbon_unit_den\": \"kg\", \"conversion_factor\": 1.0}, "
                    "\"state\": {\"included_in_carbon_emission\": true}}'"
                ),
            },
            {
                "method": "GET",
                "path": "/{project_id}/{chunk}/trash",
                "auth_required": True,
                "summary": (
                    "Construction Works chunks (str_*) only: list only the "
                    "currently-trashed entries, across every component."
                ),
                "response": (
                    "{\"project_id\", \"chunk\", \"data\": {component: [entry, "
                    "...]}} - same shape as the main GET, but only "
                    "state.in_trash=true entries; components with none are omitted."
                ),
                "example": f"curl {base}/proj_a1b2c3d4/str_super_structure/trash -H 'X-API-Token: <token>'",
            },
            {
                "method": "POST",
                "path": "/{project_id}/{chunk}/trash",
                "auth_required": True,
                "summary": (
                    "Construction Works chunks (str_*) only: trash (or, with "
                    "\"untrash\": true, restore) one entry by id alone - no "
                    "need to know which component it's in."
                ),
                "request_body": (
                    "{\"id\": \"<entry-uuid>\", \"untrash\"?: bool (default "
                    "false)} - no other keys accepted."
                ),
                "response": "{\"project_id\", \"chunk\", \"data\": <full chunk data>}. Idempotent.",
                "example": (
                    f"curl -X POST {base}/proj_a1b2c3d4/str_super_structure/trash "
                    "-H 'X-API-Token: <token>' "
                    "-d '{\"id\": \"1409a6f7-2f59-43c2-99c4-d40bf14f2536\"}'"
                ),
            },
            {
                "method": "GET",
                "path": "/catalog/databases",
                "auth_required": True,
                "summary": "List the built-in SOR material databases available to search.",
                "response": "{\"databases\": [{db_key, country, region}], \"count\"}. Optional query: country, region.",
                "example": f"curl {base}/catalog/databases -H 'X-API-Token: <any current project token>'",
            },
            {
                "method": "GET",
                "path": "/catalog/components",
                "auth_required": True,
                "summary": "Flat list of every component name across all material types.",
                "response": "{\"components\": [...], \"count\"}.",
                "example": f"curl {base}/catalog/components -H 'X-API-Token: <any current project token>'",
            },
            {
                "method": "GET",
                "path": "/catalog/items",
                "auth_required": True,
                "summary": "All catalog rows across every material type, optionally filtered further.",
                "response": "{\"items\": [...], \"total\", \"limit\", \"offset\"}. Optional query: db_key, region, limit (default 50, max 200), offset.",
                "example": f"curl '{base}/catalog/items?db_key=INDIA/Bihar/RCD+SOR+2025' -H 'X-API-Token: <any current project token>'",
            },
            {
                "method": "GET",
                "path": "/catalog/tokens",
                "auth_required": True,
                "summary": "Vocabulary of real searchable words - check here before guessing a /catalog/search query.",
                "response": "{\"tokens\": [...], \"count\"}. Optional query: db_key, region.",
                "example": f"curl '{base}/catalog/tokens?db_key=INDIA/Bihar/RCD+SOR+2025' -H 'X-API-Token: <any current project token>'",
            },
            {
                "method": "GET",
                "path": "/catalog/search",
                "auth_required": True,
                "summary": "Full-text search across every material type - matches against src_id, name, and description (broader than the GUI's own name-only autocomplete).",
                "response": (
                    "{\"query\", \"items\": [{db_key, region, country, category, "
                    "component, name, unit, rate, src_id, carbon_emission, ...}], "
                    "\"total\", \"limit\", \"offset\"} - each row can be sent "
                    "verbatim as \"catalog_item\" in a POST to /{project_id}/str_* "
                    "to add it as a material with correct source lineage. "
                    "Required query: q. Optional: db_key, "
                    "region, limit (default 50, max 200), offset."
                ),
                "example": f"curl '{base}/catalog/search?q=steel+rebar&limit=5' -H 'X-API-Token: <any current project token>'",
            },
        ],
        "pages": sorted(CHUNK_PAGE_MAP.keys()),
        "conventions": [
            "Updates merge (PATCH-like), never replace: only the keys you send change.",
            "Fields with \"locked\": true in the schema (e.g. country, currency, "
            "unit system) can never be changed via the API - POST keeps their "
            "current value and lists them in \"locked_fields_skipped\".",
            "Fields with \"field_type\": \"upload_img\" accept raw base64 or a "
            "plain http(s) image URL - URLs are downloaded and converted "
            "automatically.",
            "Validation is strict and atomic: a bad enum option, wrong type, "
            "out-of-range number, or unrecognized key rejects the entire "
            "request with 400 and per-field details.",
            "Request bodies are parsed as JSON regardless of Content-Type.",
            "/catalog/* is not project-scoped (the material database is the "
            "same for every project) but still requires a token - any "
            "currently-valid project token works, not just the one for a "
            "specific project. Search it before inventing rate/carbon values: "
            "GET /catalog/search?q=... then POST a result as \"catalog_item\" "
            "into a str_* chunk.",
        ],
        "troubleshooting": [
            "On 401 unauthorized, diagnose before asking for help: first GET "
            "/projects/active (no token needed). If your project is NOT in "
            "that list, its window was closed - tokens are cleared when a "
            "project closes and a NEW token is generated on reopen, so the "
            "old one will never work again. POST /projects/open to bring it "
            "back, then ask the user for the fresh token from File > API "
            "Access. If the project IS in the list, the token itself is "
            "stale or mistyped - ask the user for the current one.",
            "On 404 project_not_open: the project exists but is not open. "
            "POST /projects/open, then poll GET /{project_id}/{page} until "
            "it stops returning project_not_open.",
            "On connection refused / timeout: the app is not running, the "
            "local API is disabled in its Settings, or it is listening on a "
            "different port (the port auto-increments from 8765 when busy) - "
            "try the next few ports or ask the user to check File > API Access.",
            "Tokens also reset on every app restart - a token that worked "
            "yesterday will 401 today if the app was restarted in between.",
        ],
        "errors": {
            "format": (
                "Errors are JSON: {\"error\": \"<code>\", \"details\"?: [...], "
                "\"documentation_url\": \"" + _documentation_url() + "\"}. "
                "Every error links back to these docs."
            ),
            "catalogue": [
                {"status": 400, "error": "invalid_json_body", "meaning": "Body missing or not a JSON object.", "resolve": "Send a JSON object as the request body."},
                {"status": 400, "error": "invalid_field_values", "meaning": "One or more values don't match the field schema; nothing was applied.", "resolve": "Fix the fields listed in \"details\" - the GET response's \"fields\" schema states the valid options/ranges."},
                {"status": 401, "error": "unauthorized", "meaning": "Missing or incorrect X-API-Token.", "resolve": "First GET /projects/active: if the project is not listed, its window was closed and the token is gone for good - reopen via POST /projects/open and ask the user for the new token (File > API Access). If it is listed, ask the user to re-check the current token. See troubleshooting."},
                {"status": 404, "error": "project_not_found", "meaning": "No project with that id exists on this machine.", "resolve": "GET /projects lists valid project ids."},
                {"status": 404, "error": "project_not_open", "meaning": "The project exists but is not open in the app.", "resolve": "POST /projects/open, then retry once it has finished opening."},
                {"status": 404, "error": "not_found", "meaning": "Unknown route or page name.", "resolve": "Check \"available_pages\" in the response and the endpoints list here."},
                {"status": 404, "error": "not_supported", "meaning": "This chunk doesn't support add_from_catalog (only Construction Works str_* chunks do).", "resolve": "Use POST /{project_id}/{chunk} with \"catalog_item\" or \"values\" instead."},
                {"status": 423, "error": "project_locked", "meaning": "A calculation has completed and the project's inputs are frozen (same as the GUI's lock button) - every write route, including GET /{project_id}/validate, is blocked while locked.", "resolve": "POST /{project_id}/unlock, then retry."},
            ],
        },
    }


def _help_html() -> str:
    """Human-friendly landing/docs page (template: api_home.html), rendered
    from the exact same _help_payload() the JSON route serves - the two can
    never drift apart. Served to browsers (Accept: text/html) on GET / and
    GET /help."""
    from html import escape as esc
    from pathlib import Path
    from string import Template

    p = _help_payload()
    api = p["api"]

    quickstart = "".join(
        f"<li>{esc(step.split('. ', 1)[1] if '. ' in step[:4] else step)}</li>"
        for step in p["quickstart"]
    )

    auth = p["authentication"]
    auth_rows = "".join(
        f"<tr><th>{esc(label)}</th><td>{esc(str(auth[key]))}</td></tr>"
        for label, key in [
            ("Type", "type"), ("Header", "header"),
            ("Required for", "required_for"), ("Not required for", "not_required_for"),
            ("How to obtain", "how_to_obtain"), ("Lifetime", "lifetime"),
        ]
    )

    endpoints = []
    for ep in p["endpoints"]:
        badge_cls = "get" if ep["method"] == "GET" else "post"
        auth_chip = (
            '<span class="chip auth">token required</span>'
            if ep["auth_required"] else '<span class="chip open">no auth</span>'
        )
        details = ""
        for label, key in [("Request body", "request_body"), ("Response", "response")]:
            if key in ep:
                details += f"<p class='detail'><b>{label}:</b> {esc(ep[key])}</p>"
        if "example" in ep:
            details += f"<pre>{esc(ep['example'])}</pre>"
        endpoints.append(
            f"<div class='ep'><div class='ep-head'>"
            f"<span class='method {badge_cls}'>{ep['method']}</span>"
            f"<code class='path'>{esc(ep['path'])}</code>{auth_chip}</div>"
            f"<p class='summary'>{esc(ep['summary'])}</p>{details}</div>"
        )

    pages = "".join(f"<code class='page'>{esc(name)}</code>" for name in p["pages"])
    conventions = "".join(f"<li>{esc(c)}</li>" for c in p["conventions"])
    troubleshooting = "".join(f"<li>{esc(t)}</li>" for t in p["troubleshooting"])
    errors = "".join(
        f"<tr><td>{e['status']}</td><td><code>{esc(e['error'])}</code></td>"
        f"<td>{esc(e['meaning'])}</td><td>{esc(e['resolve'])}</td></tr>"
        for e in p["errors"]["catalogue"]
    )

    template = Template((Path(__file__).parent / "api_home.html").read_text(encoding="utf-8"))
    return template.substitute(
        name=esc(api["name"]),
        version=esc(api["version"]),
        description=esc(api["description"]),
        base_url=esc(api["base_url"]),
        host_note=esc(api["host_note"]),
        quickstart=quickstart,
        auth_rows=auth_rows,
        endpoints="".join(endpoints),
        pages=pages,
        conventions=conventions,
        troubleshooting=troubleshooting,
        errors_format=esc(p["errors"]["format"]),
        errors_rows=errors,
    )


def _usage_info() -> dict:
    """Compact self-documentation attached to every error response - a short
    pointer plus a link to the full docs at /help, so a caller can recover
    without a human pasting in documentation. Kept short even on 401s
    (documentation_url only, no available_pages/usage blob) since /help
    itself is unauthenticated and is the actual source of truth."""
    return {"documentation_url": _documentation_url()}


def _not_found_info() -> dict:
    return {
        "usage": (
            "Local GUI API. URL pattern: http://127.0.0.1:{port}/{project_id}/{page}. "
            "See documentation_url for full docs (no auth required)."
        ),
        "available_pages": sorted(CHUNK_PAGE_MAP.keys()),
        **_usage_info(),
    }


def _locked_response(result: dict):
    # Shared by every write route (POST .../{chunk}, add_from_catalog,
    # add_manual, trash, and GET .../validate) - ApiBridge._handle() gates
    # all of them on the same "project_locked" check (see its _WRITE_METHODS
    # set) before ever reaching their own handler, so this one response
    # shape covers every caller. 423 Locked is the correct HTTP status for
    # "the resource is locked" - distinct from 405 (read_only_chunk, which
    # never becomes writable) since a locked project unlocks.
    return jsonify({
        **result,
        "message": (
            "This project is locked (either a calculation completed and "
            "auto-locked it, or a human locked it manually via the GUI's "
            "lock button) - its inputs are frozen either way. POST "
            "/{project_id}/unlock first to clear any results and resume "
            "editing."
        ),
        **_usage_info(),
    }), 423


def _create_app(bridge: ApiBridge) -> Flask:
    app = Flask(__name__)

    @app.errorhandler(404)
    def _not_found(_e):
        return jsonify({"error": "not_found", **_not_found_info()}), 404

    @app.get("/")
    def home_route():
        # Landing page: browsers (Accept: text/html) get the readable HTML
        # page; curl/scripts/agents (Accept: */* or application/json) get the
        # JSON document. /help below is always JSON regardless of caller.
        best = request.accept_mimetypes.best_match(["application/json", "text/html"])
        if best == "text/html":
            return _help_html(), 200, {"Content-Type": "text/html; charset=utf-8"}
        return jsonify(_help_payload())

    @app.get("/help")
    def help_route():
        return jsonify(_help_payload())

    # App-level endpoints. Unauthenticated by design: per-project tokens
    # can't gate them (a token only exists once its project is open), and
    # they expose nothing a local process couldn't already do - the project
    # list mirrors what's readable on disk, and opening only shows a window;
    # reading/writing data still requires the per-project token, which no
    # endpoint ever returns.
    @app.get("/projects")
    def list_projects():
        result = bridge.call("list_projects", "", "")
        if "error" in result:
            return jsonify({**result, **_usage_info()}), 400
        return jsonify({"projects": result["projects"]})

    @app.get("/projects/active")
    def list_active_projects():
        result = bridge.call("list_projects", "", "")
        if "error" in result:
            return jsonify({**result, **_usage_info()}), 400
        active = [p for p in result["projects"] if p.get("open")]
        return jsonify({"projects": active, "count": len(active)})

    @app.get("/projects/new")
    def new_project_schema():
        from three_ps_lcca_gui.gui.components.utils.countries_data import (
            COUNTRIES, COUNTRY_TO_CURRENCY,
        )

        return jsonify({
            "description": "Field schema for POST /projects/new - GET this first to see valid values.",
            "fields": {
                "project_name": {"required": True, "type": "string", "description": "Non-empty display name."},
                "country": {
                    "required": True, "type": "string",
                    "description": "Must exactly match one of \"options\" - determines currency (see \"currency_by_country\") and is permanent after creation.",
                    "options": COUNTRIES,
                },
                "unit_system": {
                    "required": False, "type": "string", "default": "metric",
                    "options": ["metric", "imperial"],
                    "description": "Permanent after creation.",
                },
            },
            "currency_by_country": COUNTRY_TO_CURRENCY,
            "notes": [
                "currency is never supplied - it is derived from \"country\" via "
                "currency_by_country above, exactly like the New Project dialog's "
                "auto-filled, disabled currency box. Sending a \"currency\" key is a 400.",
            ],
        })

    @app.post("/projects/new")
    def create_project():
        from three_ps_lcca_gui.gui.components.utils.countries_data import COUNTRIES

        payload = request.get_json(silent=True, force=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "invalid_json_body", **_usage_info()}), 400

        errors = []
        name = payload.get("project_name")
        country = payload.get("country")
        unit_system = payload.get("unit_system", "metric")
        if not isinstance(name, str) or not name.strip():
            errors.append("'project_name' is required and must be a non-empty string")
        if not isinstance(country, str) or country not in COUNTRIES:
            errors.append(
                f"'country' is required and must exactly match one of: {COUNTRIES}"
            )
        if unit_system not in ("metric", "imperial"):
            errors.append("'unit_system' must be \"metric\" or \"imperial\" (default: metric)")
        unknown = set(payload) - {"project_name", "country", "unit_system"}
        if unknown:
            errors.append(
                f"unrecognized key(s): {sorted(unknown)} - note that currency "
                f"cannot be supplied; it is derived from the country"
            )
        if errors:
            return jsonify({"error": "invalid_field_values", "details": errors, **_usage_info()}), 400

        result = bridge.call(
            "create_project", "", "",
            {"project_name": name.strip(), "country": country, "unit_system": unit_system},
            timeout=30.0,
        )
        if "error" in result:
            return jsonify({**result, **_usage_info()}), 400

        return jsonify({
            "project_id": result["project_id"],
            "currency": result["currency"],
            "status": "created",
            "note": (
                "The project is open in the app and finishing its initial page "
                "load. Data requests need this project's X-API-Token, shown in "
                "the app's File menu ('API Access'). Currency was derived from the "
                "country and cannot be changed."
            ),
        })

    @app.post("/projects/open")
    def open_project():
        payload = request.get_json(silent=True, force=True)
        project_id = payload.get("project_id") if isinstance(payload, dict) else None
        if not project_id or not isinstance(project_id, str):
            return jsonify({
                "error": "invalid_json_body",
                "details": ["body must be a JSON object with a \"project_id\" string"],
                **_usage_info(),
            }), 400

        result = bridge.call("open_project", project_id, "")
        if "error" in result:
            if result["error"] == "project_not_found":
                return jsonify({
                    **result,
                    "hint": "GET /projects lists valid project ids",
                    **_usage_info(),
                }), 404
            return jsonify({**result, **_usage_info()}), 400

        return jsonify({
            "project_id": project_id,
            "status": result["status"],
            "note": (
                "Opening is asynchronous - poll GET /{project_id}/{page} until "
                "it stops returning project_not_open. Data requests need this "
                "project's X-API-Token, shown in the app's File menu ('API Access')."
            ),
        })

    @app.route("/<project_id>/get_tokens", methods=["GET", "POST"])
    def get_project_tokens(project_id):
        # Fast-path checks that never touch the GUI: already delivered once,
        # or this project has hit its per-session popup cap.
        if tokens.is_delivered(project_id):
            return jsonify({
                "error": "token_already_delivered",
                "message": "The API token was already delivered once for this project. Open File -> API Access in the app to view and copy the token.",
                **_usage_info()
            }), 403

        # bridge.call()'s default 10s timeout is far too short for a modal
        # popup waiting on a human - give it a lot more slack, otherwise this
        # route would return {"error": "timeout"} while the dialog is still
        # open, and the click that eventually comes has no one left to
        # receive its result.
        result = bridge.call("get_tokens", project_id, "", timeout=120.0)

        if "error" in result:
            status_code = 400
            if result["error"] == "project_not_open":
                status_code = 404
            elif result["error"] in ("denied", "token_already_delivered"):
                status_code = 403
            elif result["error"] == "too_many_requests":
                status_code = 429
            return jsonify({**result, **_usage_info()}), status_code
        return jsonify(result)

    @app.get("/<project_id>/validate")
    def validate_project(project_id):
        # Actually operates the GUI's own "Calculate" button (see
        # ApiBridge._validate_all()) - the open project window's Results
        # page updates exactly like a native click: an error/warning report
        # if anything's wrong, or a success indicator plus the real
        # calculation (non-blocking - runs on its own thread) if the
        # project is clean. This route's own JSON response never waits on
        # that calculation; it reports the errors/warnings computed at the
        # moment of the call. Not chunk-scoped (no <chunk> segment) - it
        # walks every registered page at once, so it's declared as its own
        # literal route rather than going through CHUNK_PAGE_MAP like every
        # other project data endpoint.
        provided = request.headers.get("X-API-Token")
        if not tokens.check_token(project_id, provided):
            return jsonify({"error": "unauthorized", **_usage_info()}), 401

        # timeout > the bridge's own 60s calculation-wait safety cap (see
        # ApiBridge._validate_all()), so a slow-but-real calculation gets to
        # finish rather than this route returning {"error": "timeout"} first.
        result = bridge.call("validate_all", project_id, "", timeout=75.0)
        if "error" in result:
            if result["error"] == "project_not_open":
                return jsonify({**result, **_not_found_info()}), 404
            if result["error"] == "project_locked":
                return _locked_response(result)
            return jsonify({**result, **_usage_info()}), 400

        # Only mention error-resolution guidance when there actually are
        # errors - stating "errors need to be resolved" on an already-clean
        # response is noise, not guidance.
        note_parts = []
        if result["errors"]:
            note_parts.append("Errors must be resolved before calculating.")
        if result["warnings"]:
            note_parts.append("Warnings are advisory only.")

        return jsonify({
            "project_id": project_id,
            "valid": result["valid"],
            "errors": result["errors"],
            "warnings": result["warnings"],
            "page_chunks": result["page_chunks"],
            "results": result["results"],
            "note": " ".join(note_parts + [
                "Keyed by page name. \"page_chunks\" maps each page to the "
                "chunk id(s) to GET/POST to fix it. \"results\" "
                "({results, analysis_period, currency}) is non-null only "
                "when \"valid\" is true."
            ]),
        })

    @app.get("/<project_id>/<chunk>")
    def get_chunk_data(project_id, chunk):
        if chunk not in CHUNK_PAGE_MAP:
            return jsonify({"error": "not_found", **_not_found_info()}), 404

        provided = request.headers.get("X-API-Token")
        if not tokens.check_token(project_id, provided):
            return jsonify({"error": "unauthorized", **_usage_info()}), 401

        result = bridge.call("get", project_id, chunk)
        if "error" in result:
            if result["error"] == "project_not_open":
                return jsonify({**result, **_not_found_info()}), 404
            return jsonify({**result, **_usage_info()}), 400

        # Self-describing: includes the field schema (labels, types, combo
        # options, locked flags, etc.) alongside the data so a caller (an
        # LLM/agent in particular) never needs a second lookup to know how
        # to construct a valid POST body. FieldDef pages return a flat
        # "fields" list; table/nested pages return their hand-written
        # "schema" dict (shape, update semantics, entry schema).
        schema = describe_chunk_fields(chunk, data=result["data"]) or {}
        response = {
            "project_id": project_id,
            "chunk": chunk,
            "data": result["data"],
        }
        if "fields" in schema:
            response["fields"] = schema["fields"]
        else:
            response["schema"] = schema
        return jsonify(response)

    @app.post("/<project_id>/<chunk>")
    def post_chunk_data(project_id, chunk):
        if chunk not in CHUNK_PAGE_MAP:
            return jsonify({"error": "not_found", **_not_found_info()}), 404

        provided = request.headers.get("X-API-Token")
        if not tokens.check_token(project_id, provided):
            return jsonify({"error": "unauthorized", **_usage_info()}), 401

        payload = request.get_json(silent=True, force=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "invalid_json_body", **_usage_info()}), 400

        # upload_img fields may be given as an http(s) URL instead of raw
        # base64 - fetch + convert those before validating/storing.
        payload, image_errors = resolve_image_urls(chunk, payload)
        if image_errors:
            return jsonify({"error": "invalid_field_values", "details": image_errors, **_usage_info()}), 400

        errors = validate_payload_keys(chunk, payload)
        if errors:
            return jsonify({"error": "invalid_field_values", "details": errors, **_usage_info()}), 400

        result = bridge.call("update", project_id, chunk, payload)
        if "error" in result:
            if result["error"] == "project_not_open":
                return jsonify({**result, **_not_found_info()}), 404
            if result["error"] == "read_only_chunk":
                return jsonify({
                    **result,
                    "message": "This page's data is computed/managed by the app and cannot be written via the API.",
                    **_usage_info(),
                }), 405
            if result["error"] == "project_locked":
                return _locked_response(result)
            return jsonify({**result, **_usage_info()}), 400

        response = {
            "project_id": project_id,
            "chunk": chunk,
            "data": result["data"],
            "validation": result["validation"],
        }
        if "locked_fields_skipped" in result:
            response["locked_fields_skipped"] = result["locked_fields_skipped"]
            response["warning"] = result["warning"]
        return jsonify(response)

    @app.post("/<project_id>/<chunk>/add_from_catalog")
    def add_material_from_catalog(project_id, chunk):
        if chunk not in CHUNK_PAGE_MAP:
            return jsonify({"error": "not_found", **_not_found_info()}), 404

        provided = request.headers.get("X-API-Token")
        if not tokens.check_token(project_id, provided):
            return jsonify({"error": "unauthorized", **_usage_info()}), 401

        payload = request.get_json(silent=True, force=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "invalid_json_body", **_usage_info()}), 400

        result = bridge.call("add_from_catalog", project_id, chunk, payload)
        if "error" in result:
            if result["error"] == "project_not_open":
                return jsonify({**result, **_not_found_info()}), 404
            if result["error"] == "not_supported":
                return jsonify({
                    **result,
                    "message": "This page doesn't support add_from_catalog.",
                    **_usage_info(),
                }), 404
            if result["error"] == "project_locked":
                return _locked_response(result)
            return jsonify({**result, **_usage_info()}), 400

        response = {
            "project_id": project_id,
            "chunk": chunk,
            "data": result["data"],
        }
        if "warning" in result:
            response["warning"] = result["warning"]
        return jsonify(response)

    @app.post("/<project_id>/<chunk>/add_manual")
    def add_material_manual(project_id, chunk):
        if chunk not in CHUNK_PAGE_MAP:
            return jsonify({"error": "not_found", **_not_found_info()}), 404

        provided = request.headers.get("X-API-Token")
        if not tokens.check_token(project_id, provided):
            return jsonify({"error": "unauthorized", **_usage_info()}), 401

        payload = request.get_json(silent=True, force=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "invalid_json_body", **_usage_info()}), 400

        result = bridge.call("add_manual", project_id, chunk, payload)
        if "error" in result:
            if result["error"] == "project_not_open":
                return jsonify({**result, **_not_found_info()}), 404
            if result["error"] == "not_supported":
                return jsonify({
                    **result,
                    "message": "This page doesn't support add_manual.",
                    **_usage_info(),
                }), 404
            if result["error"] == "project_locked":
                return _locked_response(result)
            return jsonify({**result, **_usage_info()}), 400

        return jsonify({
            "project_id": project_id,
            "chunk": chunk,
            "data": result["data"],
        })

    @app.get("/<project_id>/<chunk>/trash")
    def list_trashed_entries(project_id, chunk):
        entry = CHUNK_PAGE_MAP.get(chunk)
        if entry is None or entry.get("trash_by_id") is None:
            return jsonify({
                "error": "not_supported",
                "message": "This page doesn't support the /trash shortcut.",
                **_not_found_info(),
            }), 404

        provided = request.headers.get("X-API-Token")
        if not tokens.check_token(project_id, provided):
            return jsonify({"error": "unauthorized", **_usage_info()}), 401

        result = bridge.call("get", project_id, chunk)
        if "error" in result:
            if result["error"] == "project_not_open":
                return jsonify({**result, **_not_found_info()}), 404
            return jsonify({**result, **_usage_info()}), 400

        # result["data"] is already redact_response'd (no "meta") by the
        # bridge's "get" handler - filter to trashed entries only, same
        # {component: [entry, ...]} shape, omitting components with none.
        trashed = {}
        for comp, entries in result["data"].items():
            if not isinstance(entries, list):
                continue
            only_trashed = [
                e for e in entries
                if isinstance(e, dict) and e.get("state", {}).get("in_trash")
            ]
            if only_trashed:
                trashed[comp] = only_trashed

        return jsonify({"project_id": project_id, "chunk": chunk, "data": trashed})

    @app.post("/<project_id>/<chunk>/trash")
    def trash_entry(project_id, chunk):
        if chunk not in CHUNK_PAGE_MAP:
            return jsonify({"error": "not_found", **_not_found_info()}), 404

        provided = request.headers.get("X-API-Token")
        if not tokens.check_token(project_id, provided):
            return jsonify({"error": "unauthorized", **_usage_info()}), 401

        payload = request.get_json(silent=True, force=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "invalid_json_body", **_usage_info()}), 400

        result = bridge.call("trash_by_id", project_id, chunk, payload)
        if "error" in result:
            if result["error"] == "project_not_open":
                return jsonify({**result, **_not_found_info()}), 404
            if result["error"] == "not_supported":
                return jsonify({
                    **result,
                    "message": "This page doesn't support the /trash shortcut.",
                    **_usage_info(),
                }), 404
            if result["error"] == "project_locked":
                return _locked_response(result)
            return jsonify({**result, **_usage_info()}), 400

        return jsonify({
            "project_id": project_id,
            "chunk": chunk,
            "data": result["data"],
        })

    @app.post("/<project_id>/unlock")
    def unlock_project(project_id):
        # The only way out of the locked state every write route above (and
        # GET .../validate) is gated on - see ApiBridge._handle()'s
        # _WRITE_METHODS check and _unlock(). Idempotent: unlocking an
        # already-unlocked project is a no-op 200, not an error.
        provided = request.headers.get("X-API-Token")
        if not tokens.check_token(project_id, provided):
            return jsonify({"error": "unauthorized", **_usage_info()}), 401

        result = bridge.call("unlock", project_id, "")
        if "error" in result:
            if result["error"] == "project_not_open":
                return jsonify({**result, **_not_found_info()}), 404
            return jsonify({**result, **_usage_info()}), 400

        return jsonify({
            "project_id": project_id,
            "status": result["status"],
            "note": (
                "Unlocking clears the cached calculation results and "
                "re-enables editing on every page, same as the GUI's lock "
                "button - it does not itself change any input data."
            ),
        })

    register_catalog_routes(app, _usage_info)

    return app


class ApiServerHandle:
    def __init__(self, httpd, thread: threading.Thread, bridge: ApiBridge, port: int):
        self._httpd = httpd
        self._thread = thread
        self.bridge = bridge
        self.port = port

    def shutdown(self):
        global _active_port
        try:
            self._httpd.shutdown()
        except Exception:
            pass
        _active_port = None


def start_api_server(manager, port: int = DEFAULT_PORT, max_tries: int = 20) -> ApiServerHandle | None:
    """Starts the local API server on a daemon thread. If the preferred port is
    busy (e.g. another app instance), tries the next ports up to `max_tries` -
    the port is never user-configurable; callers read the actual one from
    get_active_port(). Returns None (and logs a warning) if every candidate
    fails - the GUI must still start normally."""
    global _active_port

    bridge = ApiBridge(manager)
    app = _create_app(bridge)

    httpd = None
    for candidate in range(port, port + max_tries):
        # werkzeug turns a failed bind into sys.exit(1) (printing a friendly
        # message) rather than letting the OSError propagate - catch
        # SystemExit too or a busy port would kill the whole app.
        try:
            httpd = make_server("127.0.0.1", candidate, app)
            break
        except (OSError, SystemExit):
            continue
    if httpd is None:
        print(f"[api] Could not start local API server: ports {port}-{port + max_tries - 1} all busy")
        return None
    if candidate != port:
        print(f"[api] Port {port} busy - local API server listening on {candidate} instead")

    thread = threading.Thread(target=httpd.serve_forever, name="ApiServerThread", daemon=True)
    thread.start()
    _active_port = candidate
    return ApiServerHandle(httpd, thread, bridge, candidate)
