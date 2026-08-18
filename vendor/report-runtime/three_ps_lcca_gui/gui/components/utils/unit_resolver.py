"""
gui/components/utils/unit_resolver.py
======================================
Pure-dict unit analysis - mirrors the logic in material_dialog.py.

No SymPy dependency. All lookups use the same UNIT_TO_SI / UNIT_DIMENSION
tables from definitions.py that drive the MaterialDialog UI, so the two
subsystems can never diverge.

Public API (backward-compatible):
    get_unit_info(code, custom_units=None)         -> (to_si, dimension)
    suggest_cf(mat_code, denom_code, ...)          -> float | None
    analyze_conversion_sympy(mat, denom, cf, ...)  -> dict  (main entry point)
    validate_cf_simple(mat, denom, cf)             -> dict
"""

from .definitions import UNIT_TO_SI, UNIT_DIMENSION, SI_BASE_UNITS, _all_units

# ---------------------------------------------------------------------------
# Global custom-units cache
# Loaded once from custom_materials.db at startup (or on demand).
# All functions in this module consult this cache automatically so callers
# don't have to thread a custom_units list through every call.
# ---------------------------------------------------------------------------

_custom_units_cache: list[dict] = []


def load_custom_units() -> None:
    """(Re-)load all user-defined custom units from the DB into the cache.

    Call this once at app startup and again whenever the user adds/deletes
    a custom unit via the UI.
    """
    global _custom_units_cache
    try:
        from ..structure.registry.custom_material_db import CustomMaterialDB
        _custom_units_cache = CustomMaterialDB().list_custom_units()
    except Exception as exc:
        print(f"[unit_resolver] Could not load custom units: {exc}")
        _custom_units_cache = []


def get_custom_units() -> list[dict]:
    """Return the current in-process custom-units list."""
    return _custom_units_cache


# Dimension label -> SI base unit code, mirrors CustomUnitDialog._DIMS in
# structure/widgets/material_dialog.py - the local API's "add a custom unit"
# path must accept exactly the same dimensions the GUI dialog offers.
CUSTOM_UNIT_DIMENSIONS: dict[str, str] = {
    "Mass": "kg", "Length": "m", "Area": "m2", "Volume": "m3", "Count": "nos",
}


def list_available_units() -> list[dict]:
    """Every unit a caller can use as-is: canonical units (deduped across
    their aliases) plus any custom units already defined. Same set
    CustomUnitDialog's combo shows (minus its "+ Add Custom Unit..." control
    row). Pure, no Qt - safe to call from any thread."""
    seen_ids: set[int] = set()
    result: list[dict] = []
    for code, data in _all_units.items():
        if id(data) in seen_ids:
            continue  # alias entry for a canonical unit already listed
        seen_ids.add(id(data))
        result.append({
            "code": code,
            "label": data.get("display", code),
            "name": data.get("name", ""),
            "dimension": data.get("dimension", ""),
            "to_si": data.get("to_si"),
            "custom": False,
        })
    for c in _custom_units_cache:
        result.append({
            "code": c["symbol"],
            "label": c["symbol"],
            "name": c.get("name", ""),
            "dimension": c.get("dimension", ""),
            "to_si": c.get("to_si"),
            "custom": True,
        })
    return result


def validate_custom_unit(unit: dict) -> list[str]:
    """Pure validation mirroring CustomUnitDialog._validate_and_accept() -
    symbol required and not already taken (built-in or custom, case
    insensitive), dimension one of the five the dialog offers, to_si a
    positive number."""
    errors = []
    symbol = (unit.get("symbol") or "").strip()
    if not symbol:
        errors.append("custom_unit.symbol is required")
    else:
        existing = {c.lower() for c in UNIT_TO_SI} | {
            c["symbol"].lower() for c in _custom_units_cache
        }
        if symbol.lower() in existing:
            errors.append(
                f"custom_unit.symbol {symbol!r} already exists - use that "
                f"unit code directly instead of redefining it"
            )

    if unit.get("dimension") not in CUSTOM_UNIT_DIMENSIONS:
        errors.append(
            f"custom_unit.dimension must be one of {sorted(CUSTOM_UNIT_DIMENSIONS)}"
        )

    to_si = unit.get("to_si")
    if isinstance(to_si, bool) or not isinstance(to_si, (int, float)) or to_si <= 0:
        errors.append("custom_unit.to_si must be a positive number")

    return errors


def save_custom_unit(unit: dict) -> dict:
    """Persists a validated custom unit (mirrors
    MaterialDialog._add_custom_unit's save step) and refreshes the in-process
    cache so it's immediately resolvable. Caller must have already run
    validate_custom_unit() and gotten no errors."""
    from ..structure.registry.custom_material_db import CustomMaterialDB

    symbol = unit["symbol"].strip()
    dimension = unit["dimension"]
    record = {
        "symbol": symbol,
        "name": (unit.get("name") or "").strip(),
        "dimension": dimension,
        "to_si": float(unit["to_si"]),
        "si_unit": CUSTOM_UNIT_DIMENSIONS[dimension],
    }
    CustomMaterialDB().save_custom_unit(record)
    load_custom_units()
    return record


def get_known_units() -> set[str]:
    """Return the full set of recognised unit codes (canonical + aliases + custom).

    Derived from UNIT_TO_SI, _UNIT_ALIASES, and the custom units cache so
    there is a single source of truth - no hardcoded lists elsewhere.
    """
    custom = {c["symbol"] for c in _custom_units_cache if c.get("symbol")}
    return set(UNIT_TO_SI.keys()) | set(_UNIT_ALIASES.keys()) | custom


# ---------------------------------------------------------------------------
# Aliases - normalise SOR / registry strings to canonical unit codes.
# Flattened from units.json at import time - no hardcoded entries here.
# Covers both simple codes (sqm, cum) and SOR strings (Sqm., M.T., Nos.)
# ---------------------------------------------------------------------------

def _build_aliases() -> dict[str, str]:
    """Return alias→canonical_code from every unit's aliases list in units.json."""
    result: dict[str, str] = {}
    for code, unit_data in _all_units.items():
        for alias in unit_data.get("aliases", []):
            key = alias.strip().lower()
            if key and key not in result:
                result[key] = code
    return result

_UNIT_ALIASES: dict[str, str] = _build_aliases()


def canonical_unit_code(code: str) -> str:
    """Normalize a unit code to its canonical form (e.g. 'sqm' -> 'm2').
    Raw SOR/database rows often use alias spellings; the GUI's unit dropdown
    only matches canonical codes exactly (no alias resolution), so an alias
    stored verbatim shows the unit field blank when editing that material.
    Callers that persist a unit from a catalog row should store the
    canonical form via this function.

    Note: UNIT_TO_SI is NOT a valid "is this canonical" test - it also
    contains alnum-safe aliases (e.g. "sqm") baked in directly alongside
    their canonical entry (e.g. "m2"), sharing the same to_si value. Only
    _UNIT_ALIASES reliably maps alias -> canonical code, so it's the sole
    source of truth here. Returns `code` unchanged if it's already
    canonical, a custom unit, or not recognized at all (compound
    expressions like 'kg/m2' pass through untouched - only simple
    canonical/alias lookups are handled here)."""
    if not code:
        return code
    return _UNIT_ALIASES.get(code.strip().lower(), code)


# ---------------------------------------------------------------------------
# Core helper - mirrors MaterialDialog._get_unit_info
# ---------------------------------------------------------------------------

def get_unit_info(
    code: str,
    custom_units: list | None = None,
) -> tuple[float | None, str | None]:
    """Return (to_si, dimension) for *code*.

    Handles simple, alias, and compound unit expressions.
    Returns (None, None) when the unit is completely unknown.

    Cases handled (in order):
      1. Empty / None                   → (None, None)
      2. Direct canonical registry hit  → UNIT_TO_SI / UNIT_DIMENSION
      3. Custom unit lookup             → global cache or caller-supplied list
      4. Alias normalisation            → e.g. sqm→m2, M.T.→tonne
      5. CO₂e label stripped            → kgCO₂e/kgCO2e → kg
      6. Power notation                 → m^2, kg^1  (base ** exp)
      7. Ratio (slash-separated)        → kg/mm, kgCO₂e/sqm, kg-mm/m-m^2
      8. Product (dash-separated)       → sqm-mm, kg-mm, m-m2-kg
    """
    # ── Case 1: empty ─────────────────────────────────────────────────────────
    if not code:
        return None, None

    # Normalize whitespace and repeated dashes so compound units are robust.
    # Step 1: strip outer whitespace.
    # Step 2: remove spaces around operators / and ^ (e.g. "kg / mm" → "kg/mm").
    # Step 3: replace remaining spaces with dash (e.g. "sqm mm" → "sqm-mm").
    # Step 4: collapse repeated dashes (e.g. "sqm - mm" → "sqm--mm" → "sqm-mm").
    code = code.strip()
    for _op in ("/", "^"):
        code = _op.join(p.strip() for p in code.split(_op))
    code = code.replace(" ", "-")
    while "--" in code:
        code = code.replace("--", "-")

    # ── Case 2: direct canonical registry ─────────────────────────────────────
    si_val = UNIT_TO_SI.get(code)
    dim = UNIT_DIMENSION.get(code)
    if si_val is not None:
        return si_val, dim

    # ── Case 3: custom units (global cache + caller-supplied list) ─────────────
    for source in (_custom_units_cache, custom_units or []):
        cu = next((c for c in source if c.get("symbol") == code), None)
        if cu:
            return float(cu.get("to_si", 1.0)), cu.get("dimension")

    # ── Case 4: alias normalisation (sqm→m2, Sqm.→m2, M.T.→tonne, …) ─────────
    alias = _UNIT_ALIASES.get(code.lower())
    if alias and alias != code:
        return get_unit_info(alias, custom_units)

    # ── Case 5: CO₂e label stripped (kgCO₂e → kg, tCO2e → tonne) ─────────────
    for suffix in ("CO₂e", "CO2e"):
        if code.endswith(suffix):
            return get_unit_info(code[: -len(suffix)], custom_units)

    # ── Case 6: power notation (m^2, kg^1) - no slash or dash ─────────────────
    if "^" in code and "/" not in code and "-" not in code:
        base, _, exp_str = code.partition("^")
        try:
            exp = float(exp_str)
            si, dim = get_unit_info(base.strip(), custom_units)
            if si is not None:
                return si ** exp, dim
        except (ValueError, TypeError):
            pass

    # ── Case 7: ratio - split on first "/" ─────────────────────────────────────
    # Numerator and denominator may themselves be products or power expressions.
    # e.g.  kg/mm  →  1.0 / 0.001 = 1000   (dim "Mass/Length")
    #       kg-mm/m-m^2  →  (1.0*0.001) / (1.0*1.0) = 0.001
    if "/" in code:
        num_str, _, den_str = code.partition("/")
        num_si, num_dim = get_unit_info(num_str.strip(), custom_units)
        den_si, den_dim = get_unit_info(den_str.strip(), custom_units)
        if num_si is not None and den_si is not None:
            combined_dim = (
                f"{num_dim}/{den_dim}" if num_dim and den_dim else None
            )
            return num_si / den_si, combined_dim
        return None, None

    # ── Case 8: product - dash-separated parts ─────────────────────────────────
    # Each part is resolved independently (may itself be a power expression).
    # e.g.  sqm-mm  →  1.0 * 0.001 = 0.001   (dim "Area*Length")
    #       kg-mm-m →  1.0 * 0.001 * 1.0 = 0.001
    if "-" in code:
        parts = [p.strip() for p in code.split("-") if p.strip()]
        total_si = 1.0
        dims: list[str] = []
        for part in parts:
            si, dim = get_unit_info(part, custom_units)
            if si is None:
                return None, None
            total_si *= si
            if dim and dim not in dims:
                dims.append(dim)
        return total_si, "*".join(dims) if dims else None

    return None, None


# ---------------------------------------------------------------------------
# CF suggestion - mirrors MaterialDialog._update_cf
# ---------------------------------------------------------------------------

def suggest_cf(
    mat_code: str,
    denom_code: str,
    custom_units: list | None = None,
) -> float | None:
    """Return the auto-suggested conversion factor, or None if not determinable.

    Logic identical to MaterialDialog._update_cf:
      • mat == denom      → 1.0  (hidden field in the UI)
      • same dimension    → mat_si / denom_si  (unit conversion)
      • different dims    → None  (user must supply a physical value, e.g. density)
    """
    if mat_code == denom_code:
        return 1.0

    mat_si, mat_dim = get_unit_info(mat_code, custom_units)
    denom_si, denom_dim = get_unit_info(denom_code, custom_units)

    if (mat_si is not None and denom_si is not None
            and mat_dim is not None and mat_dim == denom_dim):
        return mat_si / denom_si

    return None


# ---------------------------------------------------------------------------
# Main analysis - replaces the old SymPy-based analyze_conversion_sympy
# ---------------------------------------------------------------------------

def analyze_conversion_sympy(
    mat_unit: str,
    carbon_unit_denom: str,
    conv_factor,
    custom_units: list | None = None,
) -> dict:
    """Analyse whether *conv_factor* is plausible for the given unit pair.

    Returns a dict matching the original shape so all existing callers work:
        {
            "kg_factor":      float | None,
            "is_suspicious":  bool,
            "comment":        str,
            "debug_dim_match": bool,
        }

    Suspicion rules mirror MaterialDialog._update_cf / validate_and_accept:
      0. CF ≤ 0                  → always suspicious.
      1. Same unit code          → CF should be 1; flag if not.
      2. Same dimension, diff unit → expected CF = mat_si/denom_si; flag if >1% off.
      3. Material is Mass        → kg_factor = mat_si; not suspicious on its own.
      4. Denominator is Mass     → CF converts qty → mass; flag if CF = 1 (placeholder).
      5. Different non-mass dims → flag only if CF = 1 (likely placeholder).
      6. Unknown units           → string-equality fallback.
    """
    res = {
        "kg_factor": None,
        "is_suspicious": False,
        "comment": "",
        "debug_dim_match": False,
    }

    try:
        cf = float(conv_factor)
    except (TypeError, ValueError):
        cf = 0.0

    # ── Case 0: invalid CF ────────────────────────────────────────────────────
    if cf <= 0:
        res.update(is_suspicious=True, comment="CF must be positive.")
        return res

    mat_si, mat_dim = get_unit_info(mat_unit, custom_units)
    denom_si, denom_dim = get_unit_info(carbon_unit_denom, custom_units)

    res["debug_dim_match"] = (mat_dim is not None) and (mat_dim == denom_dim)

    # ── Case 6: unknown unit(s) - string-equality fallback ───────────────────
    if mat_si is None or denom_si is None:
        if mat_unit == carbon_unit_denom:
            res["comment"] = "Unknown unit, but units match by string."
        else:
            suspicious = abs(cf - 1.0) < 1e-6
            res.update(
                is_suspicious=suspicious,
                comment=(
                    "Unknown units; CF=1 may be a placeholder."
                    if suspicious
                    else "Unknown units; cannot verify CF."
                ),
            )
        return res

    # ── Case 1: identical unit codes ──────────────────────────────────────────
    if mat_unit == carbon_unit_denom:
        suspicious = abs(cf - 1.0) > 1e-6
        res.update(
            kg_factor=(mat_si if mat_dim == "Mass" else None),
            is_suspicious=suspicious,
            comment=(
                "Same unit - CF should be 1."
                if suspicious
                else "Same unit, CF=1 correct."
            ),
        )
        return res

    # ── Case 2: same dimension, different unit (e.g. tonne/kg, ft/m, m3/cft) ─
    if mat_dim == denom_dim:
        expected = mat_si / denom_si
        suspicious = abs(cf - expected) / max(abs(expected), 1e-12) > 0.01
        res.update(
            kg_factor=(mat_si if mat_dim == "Mass" else None),
            is_suspicious=suspicious,
            comment=(
                f"Same dimension ({mat_dim}); expected CF≈{expected:g}, got {cf:g}."
                if suspicious
                else f"Same dimension ({mat_dim}), CF={cf:g} matches expected {expected:g}."
            ),
        )
        return res

    # ── Case 3: material is mass (kg, tonne, …) ───────────────────────────────
    if mat_dim == "Mass":
        res.update(
            kg_factor=mat_si,
            comment=f"Material already in mass; kg_factor={mat_si:g}.",
        )
        return res

    # ── Case 4: denominator is mass - CF converts material quantity → mass ────
    if denom_dim == "Mass":
        # 1 mat_unit = cf denom_units; 1 denom_unit = denom_si kg
        kg_factor = cf * denom_si
        suspicious = abs(cf - 1.0) < 1e-6
        res.update(
            kg_factor=kg_factor,
            is_suspicious=suspicious,
            comment=(
                f"CF converts {mat_dim} → mass; kg_factor={kg_factor:g}."
                + (" CF=1 may be a placeholder." if suspicious else "")
            ),
        )
        return res

    # ── Case 5: different non-mass dimensions (e.g. Volume → Length) ─────────
    suspicious = abs(cf - 1.0) < 1e-6
    res.update(
        is_suspicious=suspicious,
        comment=(
            f"Different dimensions ({mat_dim} → {denom_dim}); CF=1 likely a placeholder."
            if suspicious
            else f"Cross-dimension CF ({mat_dim} → {denom_dim}) = {cf:g}."
        ),
    )
    return res


# ---------------------------------------------------------------------------
# Simple CF validation (validate_cf_simple) - improved to use registry
# ---------------------------------------------------------------------------

def validate_cf_simple(mat_unit: str, carbon_unit_denom: str, cf: float) -> dict:
    """Quick plausibility check.

    Returns {"sus": bool, "suggest": str | None}.

    Mirrors MaterialDialog validate_and_accept logic:
      • CF ≤ 0        → sus, suggest="pos"
      • same unit     → sus if CF ≠ 1,   suggest="1"
      • same dim      → sus if CF deviates from mat_si/denom_si, suggest=expected
      • diff dims     → sus if CF = 1,   suggest="!1"
    """
    if cf <= 0:
        return {"sus": True, "suggest": "pos"}

    mat_si, mat_dim = get_unit_info(mat_unit)
    denom_si, denom_dim = get_unit_info(carbon_unit_denom)

    if mat_unit == carbon_unit_denom:
        sus = abs(cf - 1.0) > 1e-6
        return {"sus": sus, "suggest": "1" if sus else None}

    if mat_si is not None and denom_si is not None and mat_dim == denom_dim:
        expected = mat_si / denom_si
        sus = abs(cf - expected) / max(abs(expected), 1e-12) > 0.01
        return {"sus": sus, "suggest": f"{expected:g}" if sus else None}

    # Different or unknown dimensions - CF=1 is suspicious
    sus = abs(cf - 1.0) < 1e-6
    return {"sus": sus, "suggest": "!1" if sus else None}


