"""
material_catalog.py
===================
Auto-discovers every material database JSON file under a configurable
root folder (default: material_database/), validates each file's
integrity, and writes a single catalog manifest (material_catalog.json)
that downstream tools (search_engine.py, etc.) use to locate and filter
databases by region / city.

Folder convention expected
--------------------------
material_database/
└── <COUNTRY>/                        e.g. INDIA
    ├── <File>.json                   e.g. MumbaiSOR.json        → db_key: INDIA/MumbaiSOR
    └── <REGION>/[<SUB>/...]          e.g. Maharashtra/PWD/
        └── <File>.json               e.g. PWD_SOR.json          → db_key: INDIA/Maharashtra/PWD/PWD_SOR

db_key is the full relative path from the material_database root, without the
.json extension, using forward slashes.  This guarantees uniqueness even when
multiple regions use identically-named JSON files.

Schema (v2)
-----------
Sections are grouped by sheetName only — one object per sheet.
"type" has been removed; "component" on each entry is the sole authority.
  [
    {
      "sheetName": "Foundation",
      "data": [
        {
          "name": "...", "unit": "...", "rate": 239,
          "component": "Excavation" | ["Pier", "Pier Cap"],
          "rate_src": "...",
          "carbon_emission": null | <float>,
          "carbon_emission_units_den": null | "<unit>",
          "conversion_factor": null | <float>,
          "carbon_emission_src": null | "IFC" | ...,
          "description": null | "..."   (optional field)
        }, ...
      ]
    }, ...
  ]

Usage
-----
# Build / refresh the registry manifest
python material_catalog.py

# In other modules
from material_catalog import get_registry, get_path, load, search, check_integrity
"""

import json
import os
import hashlib
import datetime
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
#  CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

# Increment when the manifest JSON structure changes incompatibly
SCHEMA_VERSION = 3

# Root folder that contains <COUNTRY>/<REGION>/ sub-trees
MATERIAL_DB_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "material_database")

# Output manifest written by build_registry()
CATALOG_MANIFEST_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                      "material_catalog.json")

# Schema every SOR JSON file must satisfy
EXPECTED_SCHEMA = {
    "required_top_keys": ["sheetName", "data"],
    "required_item_keys": [
        "name", "unit", "rate", "component",
        "rate_src", "carbon_emission", "carbon_emission_units_den",
        "conversion_factor", "carbon_emission_src",
    ],
    "numeric_item_fields": ["rate", "conversion_factor"],
}


# ─────────────────────────────────────────────────────────────────────────────
#  PRIVATE HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _serialize_path(path: Path) -> list[str]:
    """Convert a Path to a list of parts for OS-agnostic JSON storage."""
    return list(path.parts)


def _deserialize_path(val) -> Path:
    """Reconstruct a Path from a stored list of parts (or a legacy string)."""
    if isinstance(val, list):
        return Path(*val)
    return Path(val)


def _md5(file_path: str) -> str:
    h = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _file_meta(file_path: str) -> dict:
    stat = os.stat(file_path)
    return {
        "size_bytes": stat.st_size,
        "last_modified": datetime.datetime.fromtimestamp(stat.st_mtime).isoformat(),
        "md5": _md5(file_path),
    }


def _derive_region_info(json_path: str, root: str) -> dict:
    """
    Walk up the path relative to root and extract:
      country  ← top-level folder under root          (e.g. INDIA)
      region   ← everything between country and file  (e.g. Maharashtra/PWD)
      db_key   ← full relative path without extension   (e.g. INDIA/Maharashtra/PWD/PWD_SOR)
    """
    rel          = Path(json_path).relative_to(root)
    parts        = rel.parts

    country      = parts[0]              if len(parts) >= 1 else "UNKNOWN"
    region_parts = list(parts[1:-1])
    stem         = Path(parts[-1]).stem

    region = "/".join(region_parts)
    db_key = "/".join([country] + region_parts + [stem])

    return {"country": country, "region": region, "db_key": db_key}


def _component_matches(component_val, query: str) -> bool:
    """Case-insensitive check whether query matches any component in the entry."""
    q = query.lower()
    if isinstance(component_val, list):
        return any(q in c.lower() for c in component_val)
    return q in str(component_val).lower()


def _validate_data(data, db_key: str) -> tuple[list[str], list[str]]:
    """
    Returns (errors, warnings) lists for the parsed JSON array.
    Does NOT touch the filesystem.
    """
    errors, warnings = [], []

    if not isinstance(data, list):
        errors.append(f"Top-level must be a JSON array, got {type(data).__name__}.")
        return errors, warnings

    if len(data) == 0:
        warnings.append("File contains an empty array - no records found.")
        return errors, warnings

    required_top  = EXPECTED_SCHEMA["required_top_keys"]
    required_item = EXPECTED_SCHEMA["required_item_keys"]
    numeric_item  = set(EXPECTED_SCHEMA["numeric_item_fields"])

    for idx, record in enumerate(data):
        ref = f"Record[{idx}] (sheetName='{record.get('sheetName', '?')}')"

        # Top-level keys
        for key in required_top:
            if key not in record:
                errors.append(f"{ref}: missing top-level key '{key}'.")

        items = record.get("data", [])
        if not isinstance(items, list):
            errors.append(f"{ref}: 'data' field is not a list.")
            continue

        if len(items) == 0:
            warnings.append(f"{ref}: 'data' array is empty.")

        for i_idx, item in enumerate(items):
            _src_id     = item.get("src_id", "")
            _item_label = f"[{_src_id}] {item.get('name', '?')}" if _src_id else item.get("name", "?")
            iref        = f"{ref} › Item[{i_idx}] ('{_item_label}')"

            for key in required_item:
                if key not in item:
                    errors.append(f"{iref}: missing key '{key}'.")

            for field in numeric_item:
                val = item.get(field)
                if val is not None and not isinstance(val, (int, float)):
                    errors.append(
                        f"{iref}: '{field}' must be numeric or null, "
                        f"got {type(val).__name__} ({val!r})."
                    )

            # component must be a non-empty str or a list of non-empty strings
            comp = item.get("component")
            if comp is not None:
                if isinstance(comp, list):
                    if not comp:
                        errors.append(f"{iref}: 'component' array is empty.")
                    elif not all(isinstance(c, str) and c.strip() for c in comp):
                        errors.append(f"{iref}: 'component' array must contain non-empty strings.")
                elif not isinstance(comp, str) or not comp.strip():
                    errors.append(f"{iref}: 'component' must be a non-empty string or array.")

            if item.get("carbon_emission") is None:
                warnings.append(f"{iref}: carbon_emission is not available.")

    return errors, warnings


# ─────────────────────────────────────────────────────────────────────────────
#  PRIVATE - collect index fields from a loaded SOR file
# ─────────────────────────────────────────────────────────────────────────────

def _collect_indexes(raw: list[dict]) -> tuple[list[str], list[str], dict[str, list[str]]]:
    """
    Return (sheets, components, component_map) sorted lists/dictionaries for the manifest index.
    sheets        — unique sheetName values
    components    — unique component values collected from every entry
    component_map — dictionary mapping each sheetName to a sorted list of unique component values within that sheet
    """
    sheets: set[str] = set()
    components: set[str] = set()
    component_map: dict[str, set[str]] = {}

    for section in raw:
        sheet = section.get("sheetName", "")
        if not sheet:
            continue
        sheets.add(sheet)
        if sheet not in component_map:
            component_map[sheet] = set()
        for entry in section.get("data", []):
            comp = entry.get("component")
            if comp:
                if isinstance(comp, list):
                    valid_comps = [c for c in comp if isinstance(c, str) and c.strip()]
                    components.update(valid_comps)
                    component_map[sheet].update(valid_comps)
                elif isinstance(comp, str) and comp.strip():
                    components.add(comp)
                    component_map[sheet].add(comp)

    # Convert sets to sorted lists in component_map
    sorted_component_map = {k: sorted(list(v)) for k, v in component_map.items()}

    return sorted(sheets), sorted(components), sorted_component_map


# ─────────────────────────────────────────────────────────────────────────────
#  PUBLIC - INTEGRITY CHECK (single file, by path OR db_key)
# ─────────────────────────────────────────────────────────────────────────────

def check_integrity_by_path(file_path: str) -> dict:
    """
    Run a full integrity check on any SOR JSON path (no registry required).
    Returns a report dict.
    """
    checked_at = datetime.datetime.now().isoformat()
    result = {
        "path": file_path,
        "status": "OK",
        "errors": [],
        "warnings": [],
        "record_count": 0,
        "file_meta": {},
        "checked_at": checked_at,
    }

    if not os.path.isfile(file_path):
        result["status"] = "FAILED"
        result["errors"].append(f"File not found: {file_path}")
        return result

    result["file_meta"] = _file_meta(file_path)

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        result["status"] = "FAILED"
        result["errors"].append(f"JSON parse error: {e}")
        return result

    errors, warnings = _validate_data(data, Path(file_path).stem)
    result["errors"]       = errors
    result["warnings"]     = warnings
    result["record_count"] = len(data) if isinstance(data, list) else 0

    if errors:
        result["status"] = "FAILED"

    return result


def check_integrity(db_key: str) -> dict:
    """
    Run integrity check by db_key (requires registry manifest to exist).
    """
    registry = get_registry()
    if db_key not in registry:
        return {
            "db_key": db_key, "path": None, "status": "FAILED",
            "errors": [f"'{db_key}' not found in registry."],
            "warnings": [], "record_count": 0, "file_meta": {},
            "checked_at": datetime.datetime.now().isoformat(),
        }
    entry    = registry[db_key]
    abs_path = str((Path(CATALOG_MANIFEST_PATH).parent / _deserialize_path(entry["path"])).resolve())
    report   = check_integrity_by_path(abs_path)
    report["db_key"]  = db_key
    report["country"] = entry.get("country")
    report["region"]  = entry.get("region")
    return report


# ─────────────────────────────────────────────────────────────────────────────
#  PUBLIC - REGISTRY MANIFEST BUILD  (the core crawler)
# ─────────────────────────────────────────────────────────────────────────────

def build_registry(root: str = MATERIAL_DB_ROOT,
                   manifest_path: str = CATALOG_MANIFEST_PATH) -> dict:
    """
    Crawl `root` recursively, validate every *.json file, and write
    `manifest_path` (material_catalog.json).

    Manifest structure
    ------------------
    {
      "_meta": { "schema_version": 3, "built_at": "...", "root": [...], "total": N, "ok": N, "failed": N },
      "INDIA/Bihar/Darbhanga-2025": {
          "db_key":       "INDIA/Bihar/Darbhanga-2025",
          "path":         ["material_database", "INDIA", "Bihar", "Darbhanga-2025.json"],
          "country":      "INDIA",
          "region":       "Bihar",
          "status":       "OK" | "FAILED",
          "record_count": 4,
          "sheets":       ["Foundation", "Sub Structure", ...],   ← unique sheetName values
          "components":   ["Excavation", "Pier", "Pile", ...],    ← unique component values
          "component_map": {"Foundation": ["Excavation"], ...},   ← mapping of sheet to its components
          "errors":       [],
          "warnings":     [...],
          "file_meta":    { "size_bytes": ..., "last_modified": ..., "md5": ... }
      },
      ...
    }

    Returns the manifest dict.
    """
    if not os.path.isdir(root):
        raise FileNotFoundError(f"Material database root not found: {root}")

    manifest = {}
    manifest_abs = Path(manifest_path).resolve()
    json_files = [
        jf for jf in sorted(Path(root).rglob("*.json"))
        if jf.resolve() != manifest_abs
    ]

    for jf in json_files:
        jf_str = str(jf)
        info   = _derive_region_info(jf_str, root)
        db_key = info["db_key"]

        report = check_integrity_by_path(jf_str)

        sheets, components, component_map = [], [], {}
        if report["status"] == "OK" and report["record_count"] > 0:
            try:
                with open(jf_str, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                sheets, components, component_map = _collect_indexes(raw)
            except Exception:
                pass

        manifest_dir = Path(manifest_path).parent
        rel_path = _serialize_path(jf.relative_to(manifest_dir))

        manifest[db_key] = {
            "db_key":       db_key,
            "path":         rel_path,
            "country":      info["country"],
            "region":       info["region"],
            "status":       report["status"],
            "record_count": report["record_count"],
            "sheets":       sheets,       # unique sheetName values → categories
            "components":   components,   # unique component values → sub-categories
            "component_map": component_map, # mapping of sheetName to list of components
            "errors":       report["errors"],
            "warnings":     report["warnings"],
            "file_meta":    report["file_meta"],
        }

    ok_count     = sum(1 for v in manifest.values() if v["status"] == "OK")
    failed_count = sum(1 for v in manifest.values() if v["status"] == "FAILED")

    manifest_dir = Path(manifest_path).parent
    manifest["_meta"] = {
        "schema_version": SCHEMA_VERSION,
        "built_at":       datetime.datetime.now().isoformat(),
        "root":           _serialize_path(Path(root).relative_to(manifest_dir)),
        "total_files":    len(json_files),
        "ok":             ok_count,
        "failed":         failed_count,
    }

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"[material_catalog] Registry written -> {manifest_path}")
    print(f"[material_catalog] Scanned {len(json_files)} file(s): "
          f"{ok_count} OK, {failed_count} FAILED")
    return manifest


# ─────────────────────────────────────────────────────────────────────────────
#  PUBLIC - REGISTRY ACCESSORS
# ─────────────────────────────────────────────────────────────────────────────

def get_registry(manifest_path: str = CATALOG_MANIFEST_PATH) -> dict:
    """
    Load and return the registry manifest (minus the _meta key).
    Auto-builds if the manifest is missing or on a schema version mismatch.
    """
    if not os.path.isfile(manifest_path):
        print("[material_catalog] Manifest not found - building now …")
        build_registry(manifest_path=manifest_path)

    with open(manifest_path, "r", encoding="utf-8") as f:
        full = json.load(f)

    stored_version = full.get("_meta", {}).get("schema_version")
    if stored_version != SCHEMA_VERSION:
        print(
            f"[material_catalog] Schema version mismatch "
            f"(manifest={stored_version}, current={SCHEMA_VERSION}) - rebuilding …"
        )
        build_registry(manifest_path=manifest_path)
        with open(manifest_path, "r", encoding="utf-8") as f:
            full = json.load(f)

    return {k: v for k, v in full.items() if k != "_meta"}


def get_path(db_key: str, manifest_path: str = CATALOG_MANIFEST_PATH) -> str:
    """Return absolute path for a registered db_key."""
    registry = get_registry(manifest_path)
    if db_key not in registry:
        raise KeyError(f"'{db_key}' not in registry. "
                       f"Available: {list(registry.keys())}")
    rel_path = _deserialize_path(registry[db_key]["path"])
    abs_path = str((Path(manifest_path).parent / rel_path).resolve())
    if not os.path.isfile(abs_path):
        raise FileNotFoundError(f"File for '{db_key}' missing on disk: {abs_path}")
    return abs_path


def list_databases(
    country: str = None,
    region: str = None,
    sheet: str = None,
    component: str = None,
) -> list[dict]:
    """
    Return all registered databases, optionally filtered by:
      country   — exact match (case-insensitive)
      region    — exact match (case-insensitive)
      sheet     — sheetName must be present in the db's sheets index
      component — component must be present in the db's components index
    """
    registry = get_registry()
    result = []
    for entry in registry.values():
        if country and entry.get("country", "").upper() != country.upper():
            continue
        if region and entry.get("region", "").upper() != region.upper():
            continue
        if sheet:
            if not any(sheet.lower() == s.lower() for s in entry.get("sheets", [])):
                continue
        if component:
            if not any(component.lower() == c.lower() for c in entry.get("components", [])):
                continue
        result.append(entry)
    return result


def load(db_key: str, strict: bool = True) -> list[dict]:
    """
    Integrity-check then return parsed JSON for `db_key`.
    Raises RuntimeError on failure when strict=True.
    """
    report = check_integrity(db_key)

    if report["status"] != "OK":
        msg = (f"Integrity check FAILED for '{db_key}':\n"
               + "\n".join(f"  ✗ {e}" for e in report["errors"]))
        if strict:
            raise RuntimeError(msg)
        print(f"[material_catalog WARNING] {msg}")

    for w in report.get("warnings", []):
        print(f"[material_catalog WARNING] {w}")

    path = get_path(db_key)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ─────────────────────────────────────────────────────────────────────────────
#  PUBLIC - ADVANCED SEARCH
# ─────────────────────────────────────────────────────────────────────────────

def search(
    query: str = "",
    *,
    country: str = None,
    region: str = None,
    db_key_filter: str = None,
    sheet: str = None,
    component: str = None,
    limit: int = 200,
) -> list[dict]:
    """
    Search across all registered databases. Returns a flat list of matching
    entries, each augmented with source metadata:
      _db_key, _sheet, _country, _region

    Parameters
    ----------
    query        : case-insensitive substring match on entry name
    country      : restrict to databases from this country
    region       : restrict to databases from this region
    db_key_filter: restrict to a single db_key
    sheet        : restrict to entries in this sheetName (case-insensitive)
    component    : restrict to entries whose component matches (case-insensitive,
                   works for both str and list component values)
    limit        : max results returned (default 200)
    """
    registry = get_registry()
    query_lower     = query.lower()
    sheet_lower     = sheet.lower()     if sheet     else None
    component_lower = component.lower() if component else None
    results: list[dict] = []

    for db_key, meta in registry.items():
        if db_key_filter and db_key != db_key_filter:
            continue
        if country and meta.get("country", "").upper() != country.upper():
            continue
        if region and meta.get("region", "").upper() != region.upper():
            continue
        if meta.get("status") != "OK":
            continue

        # Use manifest index to skip databases that can't match sheet/component
        if sheet_lower:
            if not any(sheet_lower == s.lower() for s in meta.get("sheets", [])):
                continue
        if component_lower:
            if not any(component_lower == c.lower() for c in meta.get("components", [])):
                continue

        # Load and search entries
        try:
            abs_path = get_path(db_key)
            with open(abs_path, "r", encoding="utf-8") as f:
                sections = json.load(f)
        except Exception:
            continue

        for section in sections:
            sheet_name = section.get("sheetName", "")
            if sheet_lower and sheet_lower != sheet_name.lower():
                continue

            for entry in section.get("data", []):
                # Component filter
                if component_lower:
                    if not _component_matches(entry.get("component"), component_lower):
                        continue

                # Name query
                if query_lower and query_lower not in entry.get("name", "").lower():
                    continue

                results.append({
                    **entry,
                    "_db_key":  db_key,
                    "_sheet":   sheet_name,
                    "_country": meta.get("country", ""),
                    "_region":  meta.get("region", ""),
                })

                if len(results) >= limit:
                    return results

    return results


# ─────────────────────────────────────────────────────────────────────────────
#  CLI  - python material_catalog.py
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "═" * 64)
    print("  DB REGISTRY - BUILD & INTEGRITY REPORT")
    print("═" * 64)

    manifest = build_registry()

    print()
    meta = manifest.get("_meta", {})
    print(f"  Built at   : {meta.get('built_at')}")
    print(f"  Root       : {meta.get('root')}")
    print(f"  Total      : {meta.get('total_files')}  "
          f"( OK: {meta.get('ok')}  FAILED: {meta.get('failed')} )")

    print("\n" + "─" * 64)
    print(f"  {'DB KEY':<30} {'REGION':<16} {'STATUS':<8} {'RECORDS':<8} COMPONENTS")
    print("─" * 64)

    for key, entry in manifest.items():
        if key == "_meta":
            continue
        status_icon = "✓" if entry["status"] == "OK" else "✗"
        comp_preview = ", ".join(entry.get("components", [])[:4])
        if len(entry.get("components", [])) > 4:
            comp_preview += ", …"
        print(f"  {key:<30} "
              f"{entry.get('region','?'):<16} "
              f"{status_icon} {entry['status']:<6} "
              f"{entry['record_count']:<8} "
              f"{comp_preview}")
        for e in entry.get("errors", []):
            print(f"      ✗ {e}")
        for w in entry.get("warnings", []):
            print(f"      ⚠ {w}")
