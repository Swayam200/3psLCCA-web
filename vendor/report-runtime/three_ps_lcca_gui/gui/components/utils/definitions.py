# ---------------------------------------------------------------------------
# utils/definitions.py
# ---------------------------------------------------------------------------
# Unit data is loaded from units.json at import time.
# All exports below keep the same names and types as before - no other file
# needs to change.
# ---------------------------------------------------------------------------

import json
import os

_UNITS_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "units.json")


def _load_units_json() -> tuple[dict, dict]:
    """Load units.json and return (raw_data, merged_units).

    merged_units = _common + every non-underscore, non-'dimensions' system block,
    plus alias expansion so legacy codes like 'sqm', 'cum', 'tonne', 'rm' remain
    valid lookup keys alongside their canonical counterparts.
    """
    with open(_UNITS_JSON, "r", encoding="utf-8") as f:
        raw = json.load(f)

    merged: dict = {}
    merged.update(raw.get("_common", {}))
    for key, value in raw.items():
        if not key.startswith("_") and key != "dimensions":
            merged.update(value)

    # Expand aliases that look like simple unit codes (no spaces / punctuation)
    # so that e.g. UNIT_TO_SI["sqm"] and UNIT_TO_SI["m2"] both work.
    for unit_data in list(merged.values()):
        for alias in unit_data.get("aliases", []):
            alias_key = alias.strip().lower()
            if alias_key and alias_key not in merged:
                if all(c.isalnum() or c == "_" for c in alias_key):
                    merged[alias_key] = unit_data

    return raw, merged


_raw_data, _all_units = _load_units_json()

# ---------------------------------------------------------------------------
# Public exports - same names, same types, now driven by units.json
# ---------------------------------------------------------------------------

# Maps unit code → how many SI base units it equals
UNIT_TO_SI: dict[str, float] = {
    code: u["to_si"] for code, u in _all_units.items()
}

# Maps unit code → its physical dimension
UNIT_DIMENSION: dict[str, str] = {
    code: u["dimension"] for code, u in _all_units.items()
}

# Maps dimension name → its SI base unit code
SI_BASE_UNITS: dict[str, str] = {
    dim: info["si"] for dim, info in _raw_data["dimensions"].items()
}

# Maps unit code → pretty display symbol (falls back to code if not set)
UNIT_DISPLAY: dict[str, str] = {
    code: u.get("display", code) for code, u in _all_units.items()
}

# Mass-only convenience dict (kept for backward compatibility)
UNIT_TO_KG: dict[str, float] = {
    code: u["to_si"]
    for code, u in _all_units.items()
    if u["dimension"] == "Mass"
}


# ---------------------------------------------------------------------------
# ConstructionUnits - grouped dropdown data, built from units.json
# ---------------------------------------------------------------------------

# Dimension display order for dropdowns
_DIM_ORDER = ["Length", "Area", "Volume", "Mass", "Count"]


class ConstructionUnits:
    def __init__(self):
        self.units: dict[str, dict] = {dim: {} for dim in _DIM_ORDER}
        self._populate("metric")   # default

    def _populate(self, system: str) -> None:
        """Rebuild self.units from _common + the given system block only."""
        for dim in _DIM_ORDER:
            self.units[dim] = {}
        for block_key in ("_common", system):
            for code, u in _raw_data.get(block_key, {}).items():
                dim = u.get("dimension")
                if dim not in self.units:
                    self.units[dim] = {}
                self.units[dim][code] = {
                    "name":    f"{u.get('display', code)} , {u.get('name', code)}",
                    "example": u.get("example", ""),
                }

    def reload(self, system: str) -> None:
        """Switch active unit system and repopulate dropdown data in-place."""
        self._populate(system)

    def get_dropdown_data(self) -> list[tuple]:
        """Returns a list of tuples: (Code, Name, Example)"""
        data = []
        for cat in _DIM_ORDER:
            for code, info in self.units.get(cat, {}).items():
                data.append((code, info["name"], info["example"]))
        return data


_CONSTRUCTION_UNITS = ConstructionUnits()
UNIT_DROPDOWN_DATA = _CONSTRUCTION_UNITS.get_dropdown_data()


def set_active_unit_system(system: str) -> None:
    """Call this when a project loads to filter unit dropdowns by system.

    UNIT_TO_SI / UNIT_DIMENSION / UNIT_DISPLAY are unchanged (all units kept
    for lookup). Only _CONSTRUCTION_UNITS (the dropdown) is filtered.
    Defaults to 'metric' for old projects without a unit_system field.
    """
    valid = [k for k in _raw_data if not k.startswith("_") and k != "dimensions"]
    active = system if system in valid else "metric"
    _CONSTRUCTION_UNITS.reload(active)


STRUCTURE_CHUNKS = [
    ("str_foundation", "Foundation"),
    ("str_sub_structure", "Sub-Structure"),
    ("str_super_structure", "Super-Structure"),
    ("str_misc", "Misc"),
]


# Vehicle presets - EF values from IPCC AR5 (WGIII, 2014) / matching CSV source.
# gross_weight = fully loaded vehicle weight (vehicle tare + full payload).
# capacity     = net payload capacity (cargo only).
# empty_weight is derived at runtime: gross_weight - capacity.
DEFAULT_VEHICLES = {
    "Light Duty Vehicle (<4.5T)": {
        "name": "Light Duty Vehicle (<4.5T)",
        "capacity": 2.5,
        "gross_weight": 3.5,
        "emission_factor": 1.2,
    },
    "HDV Small (4.5-9T)": {
        "name": "HDV Small (4.5-9T)",
        "capacity": 7.0,
        "gross_weight": 9.5,
        "emission_factor": 0.7,
    },
    "HDV Medium (9-12T)": {
        "name": "HDV Medium (9-12T)",
        "capacity": 10.5,
        "gross_weight": 14.0,
        "emission_factor": 0.55,
    },
    "HDV Large (>12T)": {
        "name": "HDV Large (>12T)",
        "capacity": 24.5,
        "gross_weight": 35.0,
        "emission_factor": 0.19,
    },
}


