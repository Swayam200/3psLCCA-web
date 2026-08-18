"""
defaults.py
===========
Single source of truth for structure page default components and their
SOR search categories.

search_cat stores {"component": ..., "sheet": ...} — the structured form
used by the material dialog type-filter.  If the SOR has no entry that
matches the component name, the dialog falls back to "All components".
"""

# ─── Registry seed written to str_component_registry at project creation ─────

STRUCTURE_DEFAULTS: dict[str, dict[str, dict]] = {
    "str_foundation": {
        "Excavation": {"search_cat": {"component": "Excavation", "sheet": "Foundation"}, "is_deleted": False},
        "Pile":        {"search_cat": {"component": "Pile",       "sheet": "Foundation"}, "is_deleted": False},
        "Pile Cap":    {"search_cat": {"component": "Pile Cap",   "sheet": "Foundation"}, "is_deleted": False},
    },
    "str_sub_structure": {
        "Pier":      {"search_cat": {"component": "Pier",      "sheet": "Sub Structure"}, "is_deleted": False},
        "Pier Cap":  {"search_cat": {"component": "Pier Cap",  "sheet": "Sub Structure"}, "is_deleted": False},
        "Pedestal":  {"search_cat": {"component": "Pedestal",  "sheet": "Sub Structure"}, "is_deleted": False},
        "Bearings":  {"search_cat": {"component": "Bearings",  "sheet": "Sub Structure"}, "is_deleted": False},
    },
    "str_super_structure": {
        "Girder":         {"search_cat": {"component": "Girder",         "sheet": "Super Structure"}, "is_deleted": False},
        "Deck Slab":      {"search_cat": {"component": "Deck Slab",      "sheet": "Super Structure"}, "is_deleted": False},
        "Diaphragm":      {"search_cat": {"component": "Diaphragm",      "sheet": "Super Structure"}, "is_deleted": False},
        "Cross Bracings": {"search_cat": {"component": "Cross Bracings", "sheet": "Super Structure"}, "is_deleted": False},
    },
    "str_misc": {
        "Railing  & Crash Barrier & Median":      {"search_cat": {"component": "Railing  & Crash Barrier & Median",      "sheet": "Miscellaneous"}, "is_deleted": False},
        "Drainage":                                {"search_cat": {"component": "Drainage",                                "sheet": "Miscellaneous"}, "is_deleted": False},
        "Asphalt, Utilities and Other Materials": {"search_cat": {"component": "Asphalt, Utilities and Other Materials", "sheet": "Miscellaneous"}, "is_deleted": False},
        "Waterproofing":                          {"search_cat": {"component": "Waterproofing",                          "sheet": "Miscellaneous"}, "is_deleted": False},
    },
}

# Default SOR sheet per page — used when user adds a custom component
PAGE_DEFAULT_SHEET: dict[str, str] = {
    "str_foundation":      "Foundation",
    "str_sub_structure":   "Sub Structure",
    "str_super_structure": "Super Structure",
    "str_misc":            "Miscellaneous",
}
