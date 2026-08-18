"""
gui/components/outputs/lcc_data.py

Single source of truth for all LCC stage/row definitions.
Derives _CHART_ROWS, BREAKDOWN_STAGES, and STAGE_DEFS from master tables.
No Qt or matplotlib imports - safe to use from any context.
"""

from .plots_helper.Pie import COLORS
from .helper_functions.lcc_colors import COLORS as _LC  # stage_color values


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _get(d, *keys, default=0.0):
    """Safe nested dict access."""
    node = d
    for k in keys:
        if not isinstance(node, dict):
            return default
        node = node.get(k, default)
    return node if node is not None else default


# Keys treated as credits (negated in charts and totals).
_CREDIT_KEYS = {"total_scrap_value"}


# ---------------------------------------------------------------------------
# Master tables
# ---------------------------------------------------------------------------

# (stage_key, category, result_key, label)
_MASTER_ROWS = [
    # Initial Stage
    ("initial_stage",  "economic",      "initial_construction_cost",
     "Initial Construction Cost"),
    ("initial_stage",  "economic",      "time_cost_of_loan",
     "Time Costs"),
    ("initial_stage",  "environmental", "initial_material_carbon_emission_cost",
     "Initial Carbon Emissions"),
    ("initial_stage",  "environmental", "initial_vehicular_emission_cost",
     "Carbon emissions due to Rerouting (Construction)"),
    ("initial_stage",  "social",        "initial_road_user_cost",
     "Road User Costs (Construction)"),

    # Use Stage
    ("use_stage",      "economic",      "routine_inspection_costs",
     "Routine Inspection Costs"),
    ("use_stage",      "economic",      "periodic_maintenance",
     "Periodic Maintenance Costs"),
    ("use_stage",      "economic",      "major_inspection_costs",
     "Major Inspection Costs"),
    ("use_stage",      "economic",      "major_repair_cost",
     "Major Repair Costs"),
    ("use_stage",      "economic",      "replacement_costs_for_bearing_and_expansion_joint",
     "Replacement Costs of Bearings and Expansion joints"),
    ("use_stage",      "environmental", "periodic_carbon_costs",
     "Periodic Maintenance related Carbon Emissions"),
    ("use_stage",      "environmental", "major_repair_material_carbon_emission_costs",
     "Major Repair related Carbon Emissions"),
    ("use_stage",      "environmental", "major_repair_vehicular_emission_costs",
     "Carbon Emissions due to Rerouting during Major Repairs"),
    ("use_stage",      "environmental", "vehicular_emission_costs_for_replacement_of_bearing_and_expansion_joint",
     "Carbon Emissions due to Rerouting during Replacement of Bearings and Expansion joints"),
    ("use_stage",      "social",        "major_repair_road_user_costs",
     "Road User Costs during Major Repairs"),
    ("use_stage",      "social",        "road_user_costs_for_replacement_of_bearing_and_expansion_joint",
     "Road User Costs during Replacement of Bearings and Expansion joints"),

    # Reconstruction Stage
    ("reconstruction", "economic",      "total_demolition_and_disposal_costs",
     "Demolition and Disposal Costs"),
    ("reconstruction", "economic",      "total_scrap_value",
     "Recycling Costs"),
    ("reconstruction", "economic",      "cost_of_reconstruction_after_demolition",
     "Reconstruction Costs"),
    ("reconstruction", "economic",      "time_cost_of_loan",
     "Time Costs"),
    ("reconstruction", "environmental", "carbon_costs_demolition_and_disposal",
     "Demolition and Disposal related Carbon Emissions"),
    ("reconstruction", "environmental", "demolition_vehicular_emission_cost",
     "Carbon Emissions due to Rerouting during Demolition and Disposal"),
    ("reconstruction", "environmental", "carbon_cost_of_reconstruction_after_demolition",
     "Reconstruction related Carbon Emissions"),
    ("reconstruction", "environmental", "reconstruction_vehicular_emission_cost",
     "Carbon Emissions due to Rerouting during Reconstruction"),
    ("reconstruction", "social",        "ruc_demolition",
     "Road User Costs related to Demolition and Disposal during Reconstruction"),
    ("reconstruction", "social",        "ruc_reconstruction",
     "Road User Costs during Reconstruction"),

    # End of Life Stage
    ("end_of_life",    "economic",      "total_demolition_and_disposal_costs",
     "Demolition and Disposal Costs"),
    ("end_of_life",    "economic",      "total_scrap_value",
     "Recycling Costs"),
    ("end_of_life",    "environmental", "carbon_costs_demolition_and_disposal",
     "Demolition and Disposal related Carbon Emissions"),
    ("end_of_life",    "environmental", "demolition_vehicular_emission_cost",
     "Carbon Emissions due to Rerouting during Demolition and Disposal"),
    ("end_of_life",    "social",        "ruc_demolition",
     "Road User Costs due to Demolition and Disposal"),
]

# (stage_key, chart_title, breakdown_label, color, tick_color, stage_color, optional)
_STAGE_META = [
    ("initial_stage",  "Initial Stage",        "Initial Stage\nCosts",
     "#cfd9e8", "#2c4a75", _LC["init_color"],               False),
    ("use_stage",      "Use Stage",            "Use Stage\nCosts",
     "#cfe8e2", "#1f6f66", _LC["use_color"],                False),
    ("reconstruction", "Reconstruction Stage", "Reconstruction\nStage",
     "#e8d5f0", "#5a3270", _LC.get("recon_color", "#B0BEC5"), True),
    ("end_of_life",    "End-of-Life Stage",    "End-of-Life\nStage",
     "#edd5d5", "#7a3b3b", _LC["end_color"],               False),
]


# ---------------------------------------------------------------------------
# Derived structures (built once at import)
# ---------------------------------------------------------------------------

def _build_chart_rows():
    out = {}
    for sk, cat, key, label in _MASTER_ROWS:
        out.setdefault(sk, []).append((cat, key, label))
    return out


def _build_breakdown_stages():
    rows_by_stage = {}
    for sk, cat, key, label in _MASTER_ROWS:
        rows_by_stage.setdefault(sk, []).append((cat, key, label))
    return [
        {"label": bd_lbl, "stage_color": s_color, "result_key": sk,
         "optional": optional, "rows": rows_by_stage.get(sk, [])}
        for sk, _, bd_lbl, _, _, s_color, optional in _STAGE_META
    ]


def _build_stage_defs():
    out = []
    for sk, chart_title, *_ in _STAGE_META:
        cats = {}
        for row_sk, cat, key, *_ in _MASTER_ROWS:
            if row_sk != sk:
                continue
            entry = f"-{key}" if key in _CREDIT_KEYS else key
            cats.setdefault(cat.capitalize(), []).append(entry)
        out.append((chart_title, sk, cats))
    return out


_CHART_ROWS = _build_chart_rows()
BREAKDOWN_STAGES = _build_breakdown_stages()
STAGE_DEFS = _build_stage_defs()


# ---------------------------------------------------------------------------
# Chart data
# ---------------------------------------------------------------------------

def build_chart_data(results: dict):
    """Returns (values, labels, stage_info). Stage order: Initial → Use → Reconstruction (optional) → End-of-Life."""
    has_recon = bool(results.get("reconstruction"))
    values, labels, stage_info = [], [], []

    for sk, chart_title, _, color, tick_color, _, optional in _STAGE_META:
        if optional and not has_recon:
            continue
        start = len(values)
        for cat, key, label in _CHART_ROWS[sk]:
            val = _get(results, sk, cat, key)
            values.append(-val if key in _CREDIT_KEYS else val)
            labels.append(label)
        stage_info.append({"start": start, "end": len(values) - 1,
                           "color": color, "title": chart_title, "tick_color": tick_color})

    return values, labels, stage_info


# ---------------------------------------------------------------------------
# Summary table
# ---------------------------------------------------------------------------

def stage_totals(results: dict, result_key: str, cat_keys: dict) -> dict:
    """Return {category: total} for one stage."""
    stage_data = results.get(result_key, {})
    if not isinstance(stage_data, dict):
        return {}

    totals = {}
    for cat in cat_keys:
        cat_data = stage_data.get(cat.lower(), {})
        total_val = 0.0
        if isinstance(cat_data, dict):
            for k, v in cat_data.items():
                total_val += (-v if k in _CREDIT_KEYS else v)
        totals[cat] = total_val

    return totals


# Derived from COLORS["pillars"] - lowercased keys for category row colouring
CATEGORY_COLORS = {k.lower(): v for k, v in COLORS["pillars"].items()}
