"""
Shared helpers for fetching commonly needed values from project chunks.

Usage:
    # Once, when the controller is created (e.g. in ProjectManager):
    from ...components.utils.common_requested_data import set_controller
    set_controller(controller)

    # Anywhere in the UI — no argument needed:
    from ...components.utils.common_requested_data import get_currency, get_bridge_data
    currency   = get_currency()
    bridge     = get_bridge_data()
"""

from __future__ import annotations

_controller = None


def set_controller(controller) -> None:
    global _controller
    _controller = controller


# ── Known chunks ─────────────────────────────────────────────────────────────

_ALL_CHUNKS = [
    "general_info",
    "bridge_data",
    "analysis_period",
    "financial_data",
    "maintenance_data",
    "demolition_data",
    "traffic_and_road_data",
    "str_foundation",
    "str_sub_structure",
    "str_super_structure",
    "str_misc",
    "transport_data",
    "machinery_emissions_data",
    "social_cost_data",
    "diversion_emissions",
    "str_summary",
]


# ── Generic ───────────────────────────────────────────────────────────────────

def get_chunk(chunk_name: str) -> dict:
    """Return a chunk dict via the controller cache (always reflects latest save).

    Uses controller.get_chunk() — not engine.fetch_chunk() — so staged-but-not-yet-
    flushed saves are included. Always call this after save_chunk_data to get fresh data.
    """
    try:
        if _controller:
            return _controller.get_fresh_chunk(chunk_name) or {}
    except Exception:
        pass
    return {}


def get_all_data() -> dict:
    """Return all known chunks as a flat dict keyed by chunk name."""
    return {name: get_chunk(name) for name in _ALL_CHUNKS}


# def get_all_fresh_data() -> dict:
#     """Return all known chunks as a flat dict, bypassing controller cache."""
#     try:
#         if _controller:
#             return {name: _controller.get_fresh_chunk(name) for name in _ALL_CHUNKS}
#     except Exception:
#         pass
#     return {}


# ── general_info ──────────────────────────────────────────────────────────────

def get_general_info() -> dict:
    return get_chunk("general_info")


def get_currency() -> str:
    """Return the project currency string, or 'Currency' if unavailable."""
    return get_general_info().get("project_currency", "") or "Currency"


def get_project_country() -> str:
    return get_general_info().get("project_country", "")


def get_project_iso3() -> str:
    """Return the ISO3 code for the project country, or '' if not found."""
    from .countries_data import COUNTRY_TO_CODE
    country = get_project_country()
    return COUNTRY_TO_CODE.get(country.upper(), "")


def get_project_name() -> str:
    return get_general_info().get("project_name", "")


# ── bridge_data ───────────────────────────────────────────────────────────────

def get_bridge_data() -> dict:
    """Return the bridge data chunk.

    Expected schema::

        {
            "bridge_name":                  str,    # e.g. "Mumbai Project"
            "user_agency":                  str,
            "project_country":              str,
            "location":                     str,
            "bridge_type":                  str,    # e.g. "Girder"
            "span":                         float,
            "carriageway_width":            float,
            "num_lanes":                    int,
            "vehicle_path_direction":       str,    # e.g. "One Way"
            "footpath":                     str,    # e.g. "No footpath"
            "design_life":                  int,    # e.g. 75
            "analysis_period":              int,    # e.g. 100
            "year_of_construction":         int,    # e.g. 2026
            "duration_construction_months": float,  # e.g. 5.2
            "working_days_per_month":       int,    # e.g. 22
            "days_per_month":               int,    # e.g. 30
        }
    """
    return get_chunk("bridge_data")


def get_design_life() -> int | None:
    val = get_bridge_data().get("design_life")
    return int(val) if val is not None else None


def get_analysis_period() -> int | None:
    val = get_chunk("analysis_period").get("analysis_period")
    return int(val) if val is not None else None


def get_construction_duration_months() -> float | None:
    val = get_bridge_data().get("duration_construction_months")
    return float(val) if val is not None else None


# ── financial_data ────────────────────────────────────────────────────────────

def get_financial_data() -> dict:
    """Return the financial data chunk.

    Expected schema::

        {
            "discount_rate":         float,  # e.g. 6.7
            "discount_rate_source":  str,
            "inflation_rate":        float,  # e.g. 5.15
            "inflation_rate_source": str,
            "interest_rate":         float,  # e.g. 7.75
            "interest_rate_source":  str,
            "investment_ratio":      float,  # e.g. 0.5
            "investment_ratio_source": str,
        }
    """
    return get_chunk("financial_data")


def get_discount_rate() -> float | None:
    val = get_financial_data().get("discount_rate")
    return float(val) if val is not None else None


# ── maintenance_data ──────────────────────────────────────────────────────────

def get_maintenance_data() -> dict:
    """Return the maintenance data chunk.

    Expected schema::

        {
            "routine_inspection_cost":          float,  # % of construction cost, e.g. 0.1
            "routine_inspection_freq":          int,    # years, e.g. 1
            "periodic_maintenance_cost":        float,  # % of construction cost, e.g. 0.6
            "periodic_maintenance_carbon_cost": float,  # % of construction carbon cost, e.g. 0.55
            "periodic_maintenance_freq":        int,    # years, e.g. 5
            "major_inspection_cost":            float,  # % of construction cost, e.g. 0.5
            "major_inspection_freq":            int,    # years, e.g. 5
            "major_repair_cost":                float,  # % of construction cost, e.g. 10.0
            "major_repair_carbon_cost":         float,  # % of construction carbon cost, e.g. 0.55
            "major_repair_freq":                int,    # years, e.g. 60
            "major_repair_duration":            int,    # months, e.g. 3
            "bearing_exp_joint_cost":           float,  # % of construction cost, e.g. 12.5
            "bearing_exp_joint_freq":           int,    # years, e.g. 25
            "bearing_exp_joint_duration":       int,    # months, e.g. 2
        }
    """
    return get_chunk("maintenance_data")


# ── demolition_data ───────────────────────────────────────────────────────────

def get_demolition_data() -> dict:
    """Return the demolition data chunk.

    Expected schema::

        {
            "demolition_cost_pct":        float,  # e.g. 10.0
            "demolition_carbon_cost_pct": float,  # e.g. 10.0
            "demolition_duration":        int,    # in months, e.g. 1
        }
    """
    return get_chunk("demolition_data")


# ── traffic_and_road_data ─────────────────────────────────────────────────────

def get_traffic_and_road_data() -> dict:
    """Return the traffic and road data chunk.

    Expected schema::

        {
            "alternate_road_carriageway": str,    # e.g. "SL"
            "additional_reroute_distance_km": float,
            "mode":                      str,    # e.g. "India"
            "remarks":                   str,    # HTML-formatted rich text
            "vehicle_data": {
                "small_cars": {
                    "vehicles_per_day": int,
                    "accident_percentage": float,
                    "pwr": float,
                },
                # ... other vehicles
            },
            "peak_hour_distribution": {
                "peak_hour_1": float,
                # ... up to num_peak_hours
            },
            "num_peak_hours": int,
            "wpi": {
                "selected_profile_name": str,
                "data_snapshot": {
                    "base": dict,
                    "selected": dict,
                    "ratio": dict,
                }
            }
        }
    """
    return get_chunk("traffic_and_road_data")


# ── str_foundation ────────────────────────────────────────────────────────────

def get_str_foundation() -> dict:
    return get_chunk("str_foundation")


# ── str_sub_structure ─────────────────────────────────────────────────────────

def get_str_sub_structure() -> dict:
    return get_chunk("str_sub_structure")


# ── str_super_structure ───────────────────────────────────────────────────────

def get_str_super_structure() -> dict:
    return get_chunk("str_super_structure")


# ── str_misc ──────────────────────────────────────────────────────────────────

def get_str_misc() -> dict:
    return get_chunk("str_misc")


# ── transport_data ────────────────────────────────────────────────────────────

def get_transport_data() -> dict:
    return get_chunk("transport_data")


# ── machinery_emissions_data ──────────────────────────────────────────────────

def get_machinery_emissions_data() -> dict:
    """Return the machinery emissions data chunk.

    The schema varies by ``mode``.

    **Mode: "detailed"**::

        {
            "mode":         str,    # "detailed"
            "default_days": int,    # e.g. 0
            "detailed": {
                "rows": [
                    {
                        "name":   str,    # e.g. "Backhoe loader (JCB)"
                        "source": str,    # e.g. "Diesel" | "Electricity (Grid)"
                        "rate":   float,  # fuel/energy consumption rate
                        "hrs":    float,  # hours per day
                        "days":   int,    # number of days used
                        "ef":     float,  # emission factor (kgCO2e), e.g. 2.69 for Diesel, 0.71 for Grid
                    },
                    # ... more rows
                ]
            },
            "lumpsum":      dict,   # present but unused in this mode
            "remarks":      str,    # HTML-formatted rich text
            "total_kgCO2e": float,  # e.g. 0.0
        }

    **Mode: "lumpsum"**::

        {
            "mode":         str,    # "lumpsum"
            "default_days": int,
            "detailed":     dict,   # present but unused in this mode
            "lumpsum": {
                "elec_consumption_per_day": float,  # kWh/day
                "elec_days":                int,
                "elec_ef":                  float,  # emission factor for electricity
                "fuel_consumption_per_day": float,  # litres/day
                "fuel_days":                int,
            },
            "remarks":      str,    # HTML-formatted rich text
            "total_kgCO2e": float,
        }
    """
    return get_chunk("machinery_emissions_data")


# ── social_cost_data ──────────────────────────────────────────────────────────

def get_social_cost_data() -> dict:
    """Return the social cost data chunk.

    Expected schema::

        {
            "mode": str,           # e.g. "ricke" or "custom"
            "cost": float,
            "ricke": {
                "iso3":                  str,
                "ssp":                   str,
                "rcp":                   str,
                "dmg_func":              str,
                "dmg_params":            str,
                "climate_uncertainty":   str,
                "discounting":           str,
                "percentile":            str,
                "usd_to_local_rate":     float,
                "cpi_ratio":             float,
            },
            "custom": {
                "scc_value": float,
            },
        }
    """
    return get_chunk("social_cost_data")


def get_social_cost_mode() -> str:
    return get_social_cost_data().get("mode", "")


def get_social_cost() -> float | None:
    val = get_social_cost_data().get("cost")
    return float(val) if val is not None else None


def get_social_cost_ricke() -> dict:
    return get_social_cost_data().get("ricke", {})


def get_social_cost_usd_to_local_rate() -> float | None:
    val = get_social_cost_ricke().get("usd_to_local_rate")
    return float(val) if val is not None else None


def get_social_cost_cpi_ratio() -> float | None:
    val = get_social_cost_ricke().get("cpi_ratio")
    return float(val) if val is not None else None


def get_social_cost_custom_scc_value() -> float | None:
    val = get_social_cost_data().get("custom", {}).get("scc_value")
    return float(val) if val is not None else None


# ── diversion_emissions ───────────────────────────────────────────────────────

def get_diversion_emissions_cost() -> tuple[str, float | None]:
    """Return ``(mode, cost)`` for the active diversion emissions mode.

    - ``"Calculate by Vehicle"`` → ``total_calculated_emissions``
    - ``"Enter Directly"``       → ``total_direct_emissions``

    Returns ``("", None)`` if the mode is unrecognised or the value is missing.
    """
    data = get_diversion_emissions_data()
    mode = data.get("mode", "")
    if mode == "Calculate by Vehicle":
        val = data.get("total_calculated_emissions")
    elif mode == "Enter Directly":
        val = data.get("total_direct_emissions")
    else:
        return "", None
    return mode, (float(val) if val is not None else None)


def get_diversion_emissions_data() -> dict:
    """Return the diversion emissions data chunk.

    The schema varies by ``mode``.

    **Mode: "Calculate by Vehicle"**::

        {
            "mode":                       str,    # "Calculate by Vehicle"
            "emission_factors": {
                "small_cars":             float,  # e.g. 0.103
                "big_cars":               float,  # e.g. 0.269
                "two_wheelers":           float,  # e.g. 0.035
                "o_buses":                float,  # e.g. 0.455
                "d_buses":                float,  # e.g. 0.606
                "lcv":                    float,  # e.g. 0.307
                "hcv":                    float,  # e.g. 0.593
                "mcv":                    float,  # e.g. 0.738
            },
            "total_calculated_emissions": float,  # e.g. 578.49
            "remarks":                    str,    # HTML-formatted rich text
        }

    **Mode: "Enter Directly"**::

        {
            "mode":                  str,    # "Enter Directly"
            "total_direct_emissions": float, # e.g. 1000.0
            "remarks":               str,    # HTML-formatted rich text
        }
    """
    return get_chunk("diversion_emissions")


# ── str_summary ───────────────────────────────────────────────────────────────

def get_str_summary() -> dict:
    """Return the structural summary chunk.

    Expected schema::

        {
            "foundation":      {"total": float, "items": int, "components": int},
            "substructure":    {"total": float, "items": int, "components": int},
            "super_structure": {"total": float, "items": int, "components": int},
            "misc":            {"total": float, "items": int, "components": int},
            "grand_total":     float,
            "total_items":     int,
        }
    """
    return get_chunk("str_summary")


def get_str_summary_grand_total() -> float | None:
    val = get_str_summary().get("grand_total")
    return float(val) if val is not None else None