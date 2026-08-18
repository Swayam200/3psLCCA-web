"""
gui/api/catalog.py

Read-only local API over the material/SOR catalog search engine
(structure/registry/search_engine.py) - lets a caller find real rate/carbon
data (search "steel rebar" -> get name/unit/rate/db_key) before adding a
material via POST /<project_id>/str_*, instead of guessing values.

Pure Python, no Qt, no project window: MaterialSearchEngine loads static JSON
databases from disk, so these routes run directly on the Flask worker thread
- no ApiBridge.call(), no main-thread hop, no project_not_open case. Not
project-scoped (the catalog is the same for every project), but still gated
behind auth: any currently-valid project token is accepted (tokens.check_any)
so the endpoints stay unreachable when no project is open, matching the rest
of the API's "only usable while the app has something open" contract.

Custom, user-defined databases (CustomMaterialDB) are out of scope for this
first cut - only the built-in SOR databases are searchable here.
"""

import threading

from flask import jsonify, request

from . import tokens
from three_ps_lcca_gui.gui.components.structure.registry.material_entry import _validate_item

_DEFAULT_LIMIT = 50
_MAX_LIMIT = 200

_engine = None
_engine_lock = threading.Lock()


def get_engine():
    """Lazily builds one MaterialSearchEngine covering every OK database and
    caches it module-level - it parses every SOR JSON file at construction,
    so this must not happen per-request. Filtering (db_key, region, ...) is
    done per-call against this single cached instance."""
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                from three_ps_lcca_gui.gui.components.structure.registry.search_engine import (
                    MaterialSearchEngine,
                )
                _engine = MaterialSearchEngine()
    return _engine


def _clean_items(items: list[dict]) -> list[dict]:
    """Drop malformed rows the same way the GUI's material dialog does
    (_validate_item requires name+unit, fills optional keys with None)."""
    cleaned = []
    for item in items:
        item = dict(item)
        if _validate_item(item):
            cleaned.append(item)
    return cleaned


def _paginate(items: list[dict]) -> tuple[list[dict], int, int, int]:
    """Applies ?limit=&offset= from the current request. Returns
    (page, total, limit, offset). Caps limit at _MAX_LIMIT so a caller can't
    force the whole catalog (tens of thousands of rows) into one response."""
    total = len(items)
    try:
        limit = int(request.args.get("limit", _DEFAULT_LIMIT))
    except ValueError:
        limit = _DEFAULT_LIMIT
    try:
        offset = int(request.args.get("offset", 0))
    except ValueError:
        offset = 0
    limit = max(1, min(limit, _MAX_LIMIT))
    offset = max(0, offset)
    return items[offset:offset + limit], total, limit, offset


def _unauthorized(usage_info: dict):
    return jsonify({"error": "unauthorized", **usage_info}), 401


def register_catalog_routes(app, usage_info) -> None:
    """Registers /catalog/* routes on `app`. `usage_info` is server.py's
    _usage_info - a zero-arg callable returning {"documentation_url": ...}
    for consistent error shapes with the rest of the API."""

    def _require_token():
        provided = request.headers.get("X-API-Token")
        return tokens.check_any(provided)

    @app.get("/catalog/databases")
    def catalog_databases():
        if not _require_token():
            return _unauthorized(usage_info())
        from three_ps_lcca_gui.gui.components.structure.registry.material_catalog import list_databases

        country = request.args.get("country")
        region = request.args.get("region")
        entries = [
            {"db_key": e["db_key"], "country": e.get("country", ""), "region": e.get("region", "")}
            for e in list_databases(country=country, region=region)
            if e.get("status") == "OK"
        ]
        return jsonify({"databases": entries, "count": len(entries)})

    @app.get("/catalog/components")
    def catalog_components():
        if not _require_token():
            return _unauthorized(usage_info())
        components = get_engine().list_components()
        return jsonify({"components": components, "count": len(components)})

    @app.get("/catalog/items")
    def catalog_items():
        if not _require_token():
            return _unauthorized(usage_info())
        db_key = request.args.get("db_key")
        region = request.args.get("region")
        items = _clean_items(get_engine().search_advanced(
            "", db_key=db_key, region=region,
        ))
        page, total, limit, offset = _paginate(items)
        return jsonify({"items": page, "total": total, "limit": limit, "offset": offset})

    @app.get("/catalog/tokens")
    def catalog_tokens():
        if not _require_token():
            return _unauthorized(usage_info())
        db_key = request.args.get("db_key")
        region = request.args.get("region")
        tokens_list = get_engine().list_tokens(db_key=db_key, region=region)
        return jsonify({
            "tokens": tokens_list, "count": len(tokens_list),
            "note": (
                "Vocabulary of real searchable words for the given filters - "
                "use these as query terms for GET /catalog/search instead of "
                "guessing, since a query word that isn't in this list will "
                "never match anything."
            ),
        })

    @app.get("/catalog/search")
    def catalog_search():
        if not _require_token():
            return _unauthorized(usage_info())
        query = request.args.get("q", "").strip()
        if not query:
            return jsonify({
                "error": "invalid_field_values",
                "details": ["'q' query param is required, e.g. ?q=steel+rebar"],
                **usage_info(),
            }), 400
        db_key = request.args.get("db_key")
        region = request.args.get("region")
        items = _clean_items(get_engine().search_advanced(
            query, db_key=db_key, region=region,
        ))
        page, total, limit, offset = _paginate(items)
        return jsonify({
            "query": query, "items": page, "total": total, "limit": limit, "offset": offset,
            "note": (
                "Each row can be sent directly as \"catalog_item\" in a POST to "
                "/{project_id}/str_* to add it as a material entry with correct "
                "source lineage - see that chunk's schema."
            ),
        })
