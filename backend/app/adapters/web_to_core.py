from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


MODULE_PATH = Path(__file__).resolve()
# backend/app/adapters/web_to_core.py -> repository root is three levels up.
# Guarded because this module is also executed in the browser (Pyodide), where
# it lives at a shallower virtual path and the repository is not present.
_PARENTS = MODULE_PATH.parents
REPO_ROOT = _PARENTS[3] if len(_PARENTS) > 3 else Path.cwd()
# Development convenience: pick up a sibling checkout of the core engine when
# it is not installed as a package.
CORE_SRC = REPO_ROOT.parent / "3psLCCA-gui-python-venv" / "3psLCCA-core" / "src"
if CORE_SRC.exists() and str(CORE_SRC) not in sys.path:
    sys.path.insert(0, str(CORE_SRC))

from three_ps_lcca_core.core.main import run_full_lcc_analysis
from three_ps_lcca_core.inputs.input import InputMetaData
from three_ps_lcca_core.inputs.input_global import InputGlobalMetaData
from three_ps_lcca_core.inputs.wpi import WPIMetaData


VEHICLE_TYPES = (
    "small_cars",
    "big_cars",
    "two_wheelers",
    "o_buses",
    "d_buses",
    "lcv",
    "hcv",
    "mcv",
)


LANE_CODES = {
    "Single Lane": "SL",
    "Intermediate Lane": "IL",
    "Two Lane": "2L",
    "Four Lane": "4L",
    "Six Lane": "6L",
    "Eight Lane": "8L",
    "Expressway": "EW8",
    "Two Lane (Two Way)": "2L",
    "Two Lane (One Way)": "2L_1W",
    "Three Lane (One Way)": "3L_1W",
    "Four Lane (Two Way)": "4L",
    "Six Lane (Two Way)": "6L",
    "Eight Lane (Two Way)": "8L",
    "4 Lane Expressway (Two Way)": "EW4",
    "6 Lane Expressway (Two Way)": "EW6",
    "8 Lane Expressway (Two Way)": "EW8",
}

WPI_DB_PATH = REPO_ROOT / "src" / "data" / "wpi_db.json"
_WPI_DATABASE: dict[str, Any] | None = None


def configure_wpi_database(database: dict[str, Any]) -> None:
    """Provide the WPI database when filesystem access is unavailable."""
    global _WPI_DATABASE
    _WPI_DATABASE = database


def _load_base_wpi() -> dict[str, Any]:
    database = _WPI_DATABASE
    if database is None:
        with WPI_DB_PATH.open(encoding="utf-8") as handle:
            database = json.load(handle)
    for entry in database.get("entries", []):
        if entry.get("metadata", {}).get("year") == 2019:
            return _as_dict(entry.get("data"))
    raise RuntimeError("The 2019 base WPI profile is missing.")

MAINTENANCE_PERCENT_FIELDS = (
    "routine_inspection_cost",
    "periodic_maintenance_cost",
    "periodic_maintenance_carbon_cost",
    "major_inspection_cost",
    "major_repair_cost",
    "major_repair_carbon_cost",
    "bearing_exp_joint_cost",
)

MAINTENANCE_POSITIVE_FIELDS = (
    "routine_inspection_freq",
    "periodic_maintenance_freq",
    "major_inspection_freq",
    "major_repair_freq",
    "major_repair_duration",
    "bearing_exp_joint_freq",
    "bearing_exp_joint_duration",
)


@dataclass
class PreparedCorePayload:
    input_data: dict[str, Any]
    construction_costs: dict[str, Any]
    wpi: dict[str, Any] | None
    computed: dict[str, Any]
    warnings: list[str]


class AdapterValidationError(ValueError):
    def __init__(self, errors: list[str], warnings: list[str] | None = None):
        super().__init__("; ".join(errors))
        self.errors = errors
        self.warnings = warnings or []


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _num(value: Any, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    try:
        return float(str(value).replace(",", "").replace("%", "").strip())
    except (TypeError, ValueError):
        return default


def _has_value(value: Any) -> bool:
    return value is not None and value != ""


def _first_value(*values: Any) -> Any:
    return next((value for value in values if _has_value(value)), None)


def _parse_number(value: Any) -> float | None:
    if not _has_value(value):
        return None
    try:
        return float(str(value).replace(",", "").replace("%", "").strip())
    except (TypeError, ValueError):
        return None


def _require_number(
    data: dict[str, Any],
    key: str,
    path: str,
    errors: list[str],
    *,
    minimum: float | None = None,
    maximum: float | None = None,
    positive: bool = False,
) -> float | None:
    raw = data.get(key)
    value = _parse_number(raw)
    if not _has_value(raw):
        errors.append(f"{path} is required.")
        return None
    if value is None:
        errors.append(f"{path} must be numeric.")
        return None
    if positive and value <= 0:
        errors.append(f"{path} must be greater than zero.")
    elif minimum is not None and value < minimum:
        errors.append(f"{path} must be at least {minimum:g}.")
    if maximum is not None and value > maximum:
        errors.append(f"{path} must be at most {maximum:g}.")
    return value


def _require_alias_number(
    data: dict[str, Any],
    keys: tuple[str, ...],
    path: str,
    errors: list[str],
    *,
    minimum: float | None = None,
    positive: bool = False,
) -> float | None:
    selected_key = next((key for key in keys if key in data), None)
    raw = data.get(selected_key) if selected_key is not None else None
    value = _parse_number(raw)
    if not _has_value(raw):
        errors.append(f"{path} is required.")
        return None
    if value is None:
        errors.append(f"{path} must be numeric.")
        return None
    if positive and value <= 0:
        errors.append(f"{path} must be greater than zero.")
    elif minimum is not None and value < minimum:
        errors.append(f"{path} must be at least {minimum:g}.")
    return value


def _sum_section_rows(sections: Any) -> float:
    total = 0.0
    for section in _as_list(sections):
        for row in _as_list(_as_dict(section).get("rows")):
            row_data = _as_dict(row)
            if _as_dict(row_data.get("state")).get("in_trash", False):
                continue
            total += _num(row_data.get("rate")) * _num(row_data.get("qty"))
    return total


def _construction_data(project: dict[str, Any]) -> dict[str, Any]:
    foundation = _sum_section_rows(project.get("foundation_data"))
    substructure = _sum_section_rows(project.get("substructure_data"))
    superstructure = _sum_section_rows(project.get("superstructure_data"))
    miscellaneous = _sum_section_rows(project.get("miscellaneous_data"))
    grand_total = foundation + substructure + superstructure + miscellaneous
    return {
        "foundation_total": foundation,
        "substructure_total": substructure,
        "superstructure_total": superstructure,
        "miscellaneous_total": miscellaneous,
        "grand_total": grand_total,
    }


def _material_carbon_total(project: dict[str, Any]) -> float:
    carbon = _as_dict(project.get("carbon_emission_data"))
    material = _as_dict(carbon.get("material_emissions_data"))
    total = _num(material.get("total_kgCO2e"))
    if total:
        return total

    excluded_ids = set(_as_list(material.get("excluded_ids")))
    total_kg = 0.0
    for chunk_key in ("foundation_data", "substructure_data", "superstructure_data", "miscellaneous_data"):
        for section in _as_list(project.get(chunk_key)):
            for row in _as_list(_as_dict(section).get("rows")):
                row_data = _as_dict(row)
                if _as_dict(row_data.get("state")).get("in_trash", False):
                    continue
                row_id = f"{chunk_key}-{row_data.get('id')}"
                if row_id in excluded_ids:
                    continue
                carbon_emission = _as_dict(row_data.get("carbonEmission"))
                total_kg += _num(row_data.get("qty")) * (_num(row_data.get("conversionFactor"), 1.0) or 1.0) * _num(carbon_emission.get("factor"))
    return total_kg


def _carbon_emissions_total(project: dict[str, Any]) -> float:
    carbon = _as_dict(project.get("carbon_emission_data"))
    transport = _as_dict(carbon.get("transport_emissions_data") or carbon.get("transportation_emissions_data"))
    machinery = _as_dict(carbon.get("machinery_emissions_data"))
    return (
        _material_carbon_total(project)
        + _num(transport.get("total_kgCO2e"))
        + _num(machinery.get("total_kgCO2e"))
    )


def _recycling_total(project: dict[str, Any]) -> float:
    recycling = _as_dict(project.get("recycling_data"))
    total = _num(recycling.get("total_recovered_value"))
    if total:
        return total
    return sum(_num(_as_dict(item).get("recoveredValue")) for item in _as_list(recycling.get("included")))


def _general_parameters(project: dict[str, Any], analysis_period_years: int, use_global: bool) -> dict[str, Any]:
    bridge = _as_dict(project.get("bridge_data"))
    financial = _as_dict(project.get("financial_data"))
    carbon = _as_dict(project.get("carbon_emission_data"))
    social = _as_dict(carbon.get("social_cost_data"))

    return {
        "service_life_years": int(_num(bridge.get("design_life"))),
        "analysis_period_years": int(_num(analysis_period_years)),
        "discount_rate_percent": _num(financial.get("discount_rate")),
        "inflation_rate_percent": _num(financial.get("inflation_rate")),
        "interest_rate_percent": _num(financial.get("interest_rate")),
        "investment_ratio": _num(financial.get("investment_ratio")),
        "social_cost_of_carbon_per_mtco2e": _num(
            _first_value(
                financial.get("social_cost_of_carbon"),
                _as_dict(social.get("result")).get("cost_of_carbon_local"),
                social.get("cost_of_carbon_local"),
                social.get("calculated_scc_local"),
            ),
            0.0,
        ) * 1000,
        "currency_conversion": _num(financial.get("currency_conversion"), 1.0),
        "construction_period_months": _num(bridge.get("duration_construction_months")),
        "working_days_per_month": int(_num(bridge.get("working_days_per_month"))),
        "days_per_month": int(_num(bridge.get("days_per_month"))),
        "use_global_road_user_calculations": use_global,
    }


def _maintenance_stage(project: dict[str, Any]) -> dict[str, Any]:
    maintenance = _as_dict(project.get("maintenance_repair_data") or project.get("maintenance_data"))
    demolition = _as_dict(project.get("demolition_data"))
    return {
        "use_stage_cost": {
            "routine": {
                "inspection": {
                    "percentage_of_initial_construction_cost_per_year": _num(maintenance.get("routine_inspection_cost")),
                    "interval_in_years": int(_num(maintenance.get("routine_inspection_freq"))),
                },
                "maintenance": {
                    "percentage_of_initial_construction_cost_per_year": _num(maintenance.get("periodic_maintenance_cost")),
                    "percentage_of_initial_carbon_emission_cost": _num(maintenance.get("periodic_maintenance_carbon_cost")),
                    "interval_in_years": int(_num(maintenance.get("periodic_maintenance_freq"))),
                },
            },
            "major": {
                "inspection": {
                    "percentage_of_initial_construction_cost": _num(maintenance.get("major_inspection_cost")),
                    "interval_for_repair_and_rehabitation_in_years": int(_num(maintenance.get("major_inspection_freq"))),
                },
                "repair": {
                    "percentage_of_initial_construction_cost": _num(maintenance.get("major_repair_cost")),
                    "percentage_of_initial_carbon_emission_cost": _num(maintenance.get("major_repair_carbon_cost")),
                    "interval_for_repair_and_rehabitation_in_years": int(_num(maintenance.get("major_repair_freq"))),
                    "repairs_duration_months": _num(maintenance.get("major_repair_duration")),
                },
            },
            "replacement_costs_for_bearing_and_expansion_joint": {
                "percentage_of_super_structure_cost": _num(maintenance.get("bearing_exp_joint_cost")),
                "interval_of_replacement_in_years": int(_num(maintenance.get("bearing_exp_joint_freq"))),
                "duration_of_replacement_in_days": int(_num(maintenance.get("bearing_exp_joint_duration"))),
            },
        },
        "end_of_life_stage_costs": {
            "demolition_and_disposal": {
                "percentage_of_initial_construction_cost": _num(
                    _first_value(demolition.get("demolition_cost_pct"), demolition.get("demolition_cost"))
                ),
                "percentage_of_initial_carbon_emission_cost": _num(
                    _first_value(demolition.get("demolition_carbon_cost_pct"), demolition.get("demolition_carbon_cost"))
                ),
                "duration_for_demolition_and_disposal_in_months": _num(demolition.get("demolition_duration")),
            }
        },
    }


def _traffic_data(project: dict[str, Any]) -> dict[str, Any]:
    traffic = _as_dict(project.get("traffic_and_road_data") or project.get("traffic_data"))
    carbon = _as_dict(project.get("carbon_emission_data"))
    diversion = _as_dict(carbon.get("diversion_emissions_data"))
    factors = _as_dict(diversion.get("factors"))
    vehicle_data = _as_dict(traffic.get("vehicle_data") or traffic.get("vehicles"))
    vehicles_per_day = _as_dict(traffic.get("vehicles_per_day"))
    severity = _as_dict(traffic.get("severity"))
    alternate_road = _as_dict(traffic.get("alternate_road"))
    road_params = _as_dict(traffic.get("road_params"))

    vehicles = {}
    total_adt = 0
    for key in VEHICLE_TYPES:
        row = _as_dict(vehicle_data.get(key))
        vehicles_per_day_value = int(_num(_first_value(
            row.get("vehicles_per_day"),
            row.get("adt"),
            vehicles_per_day.get(key),
        )))
        total_adt += vehicles_per_day_value
        vehicles[key] = {
            "vehicles_per_day": vehicles_per_day_value,
            "carbon_emissions_kgCO2e_per_km": _num(_first_value(
                row.get("carbon_emissions_kgCO2e_per_km"),
                row.get("emission_factor"),
                factors.get(key),
            )),
            "accident_percentage": _num(row.get("accident_percentage")),
            "pwr": _num(row.get("pwr")) if key in {"hcv", "mcv"} and vehicles_per_day_value > 0 else None,
        }

    peak = (
        traffic.get("peak_hour_traffic_percent_per_hour")
        or traffic.get("peak_hour_distribution")
        or traffic.get("peak_distribution")
        or []
    )
    if isinstance(peak, dict):
        peak = [value for _, value in sorted(peak.items())]
    peak_values = [_num(value) for value in peak if _num(value) > 0]

    carriageway = str(_first_value(
        traffic.get("alternate_road_carriageway"),
        alternate_road.get("alternate_road_carriageway"),
    ) or "")

    return {
        "vehicle_data": vehicles,
        "total_adt": total_adt,
        "accident_severity_distribution": {
            "minor": _num(_first_value(traffic.get("severity_minor"), severity.get("severity_minor"), severity.get("minor"))),
            "major": _num(_first_value(traffic.get("severity_major"), severity.get("severity_major"), severity.get("major"))),
            "fatal": _num(_first_value(traffic.get("severity_fatal"), severity.get("severity_fatal"), severity.get("fatal"))),
        },
        "additional_inputs": {
            "alternate_road_carriageway": LANE_CODES.get(carriageway, carriageway),
            "carriage_width_in_m": _num(_first_value(
                traffic.get("carriage_width_in_m"),
                alternate_road.get("carriage_width_in_m"),
            )),
            "road_roughness_mm_per_km": _num(_first_value(
                traffic.get("road_roughness_mm_per_km"),
                road_params.get("road_roughness_mm_per_km"),
            )),
            "road_rise_m_per_km": _num(_first_value(traffic.get("road_rise_m_per_km"), road_params.get("road_rise_m_per_km"))),
            "road_fall_m_per_km": _num(_first_value(traffic.get("road_fall_m_per_km"), road_params.get("road_fall_m_per_km"))),
            "additional_reroute_distance_km": _num(_first_value(
                traffic.get("additional_reroute_distance_km"),
                road_params.get("additional_reroute_distance_km"),
                diversion.get("reroute_km"),
            )),
            "additional_travel_time_min": _num(_first_value(
                traffic.get("additional_travel_time_min"),
                road_params.get("additional_travel_time_min"),
            )),
            "crash_rate_accidents_per_million_km": _num(_first_value(
                traffic.get("crash_rate_accidents_per_million_km"),
                road_params.get("crash_rate_accidents_per_million_km"),
            )),
            "work_zone_multiplier": _num(_first_value(
                traffic.get("work_zone_multiplier"),
                road_params.get("work_zone_multiplier"),
            )),
            "peak_hour_traffic_percent_per_hour": peak_values,
            "hourly_capacity": int(_num(_first_value(
                traffic.get("hourly_capacity"),
                alternate_road.get("hourly_capacity"),
            ))),
            "force_free_flow_off_peak": bool(_first_value(
                traffic.get("force_free_flow_off_peak"),
                traffic.get("force_free_flow"),
                False,
            )),
        },
    }


def _wpi(project: dict[str, Any]) -> dict[str, Any] | None:
    traffic = _as_dict(project.get("traffic_and_road_data") or project.get("traffic_data"))
    raw = _as_dict(traffic.get("wpi"))
    if raw.get("year") and raw.get("WPI"):
        return raw
    year = int(_num(_first_value(
        raw.get("selected_profile_year"),
        traffic.get("wpi_year"),
        traffic.get("wpi_profile"),
    )))
    snapshot = _as_dict(raw.get("data_snapshot"))
    ratio = _as_dict(snapshot.get("ratio"))
    selected = _as_dict(
        snapshot.get("selected")
        or traffic.get("wpi_data")
        or snapshot
    )
    if not selected and not ratio:
        return None
    if not ratio:
        base = _as_dict(snapshot.get("base")) or _load_base_wpi()
        ratio = {}
        for vehicle in VEHICLE_TYPES:
            selected_row = _as_dict(selected.get(vehicle))
            base_row = _as_dict(base.get(vehicle))
            ratio[vehicle] = {}
            for key, base_value in base_row.items():
                denominator = _num(base_value)
                numerator = _num(selected_row.get(key))
                ratio[vehicle][key] = numerator / denominator if denominator > 0 else 1.0
    return {"year": year, "WPI": ratio}


def _global_daily_ruc(project: dict[str, Any]) -> dict[str, Any]:
    traffic = _as_dict(project.get("traffic_and_road_data") or project.get("traffic_data"))
    carbon = _as_dict(project.get("carbon_emission_data"))
    diversion = _as_dict(carbon.get("diversion_emissions_data"))
    return {
        "total_daily_ruc": _num(traffic.get("road_user_cost_per_day"), 0.0),
        "total_carbon_emission": {
            "total_emission_kgCO2e": _num(
                _first_value(
                    diversion.get("total_kgCO2e_per_day"),
                    diversion.get("total_direct_emissions"),
                    diversion.get("total_calculated_emissions"),
                ),
                0.0,
            )
        },
    }


def _validate_project_fields(
    project: dict[str, Any],
    analysis_period_years: int,
    use_global: bool,
) -> list[str]:
    errors: list[str] = []
    bridge = _as_dict(project.get("bridge_data"))
    financial = _as_dict(project.get("financial_data"))
    maintenance = _as_dict(project.get("maintenance_repair_data") or project.get("maintenance_data"))
    demolition = _as_dict(project.get("demolition_data"))
    carbon = _as_dict(project.get("carbon_emission_data"))
    material_emissions = _as_dict(carbon.get("material_emissions_data"))
    transport_emissions = _as_dict(
        carbon.get("transport_emissions_data") or carbon.get("transportation_emissions_data")
    )
    machinery_emissions = _as_dict(carbon.get("machinery_emissions_data"))
    social_cost = _as_dict(carbon.get("social_cost_data"))
    social_result = _as_dict(social_cost.get("result"))
    recycling = _as_dict(project.get("recycling_data"))
    traffic = _as_dict(project.get("traffic_and_road_data") or project.get("traffic_data"))

    design_life = _require_number(
        bridge, "design_life", "bridge_data.design_life", errors, positive=True
    )
    bridge_analysis_period = _require_number(
        bridge, "analysis_period", "bridge_data.analysis_period", errors, positive=True
    )
    construction_months = _require_number(
        bridge,
        "duration_construction_months",
        "bridge_data.duration_construction_months",
        errors,
        positive=True,
    )
    working_days = _require_number(
        bridge,
        "working_days_per_month",
        "bridge_data.working_days_per_month",
        errors,
        positive=True,
        maximum=31,
    )
    days_per_month = _require_number(
        bridge,
        "days_per_month",
        "bridge_data.days_per_month",
        errors,
        positive=True,
        maximum=31,
    )
    if working_days is not None and days_per_month is not None and working_days > days_per_month:
        errors.append("bridge_data.working_days_per_month cannot exceed bridge_data.days_per_month.")

    analysis_period = _parse_number(analysis_period_years)
    if analysis_period is None or analysis_period <= 0:
        errors.append("analysis_period_years must be greater than zero.")
    elif bridge_analysis_period is not None and analysis_period != bridge_analysis_period:
        errors.append("analysis_period_years must match bridge_data.analysis_period.")
    elif construction_months is not None and construction_months > analysis_period * 12:
        errors.append("bridge_data.duration_construction_months cannot exceed the analysis period.")
    if design_life is not None and design_life != int(design_life):
        errors.append("bridge_data.design_life must be a whole number.")

    _require_number(financial, "discount_rate", "financial_data.discount_rate", errors, minimum=0)
    _require_number(financial, "inflation_rate", "financial_data.inflation_rate", errors, minimum=0)
    _require_number(financial, "interest_rate", "financial_data.interest_rate", errors, minimum=0)
    _require_number(
        financial,
        "investment_ratio",
        "financial_data.investment_ratio",
        errors,
        minimum=0,
        maximum=1,
    )
    if _has_value(financial.get("currency_conversion")):
        _require_number(
            financial,
            "currency_conversion",
            "financial_data.currency_conversion",
            errors,
            positive=True,
        )

    for key in MAINTENANCE_PERCENT_FIELDS:
        _require_number(
            maintenance,
            key,
            f"maintenance_repair_data.{key}",
            errors,
            minimum=0,
        )
    for key in MAINTENANCE_POSITIVE_FIELDS:
        _require_number(
            maintenance,
            key,
            f"maintenance_repair_data.{key}",
            errors,
            positive=True,
        )

    _require_alias_number(
        demolition,
        ("demolition_cost", "demolition_cost_pct"),
        "demolition_data.demolition_cost",
        errors,
        minimum=0,
    )
    _require_alias_number(
        demolition,
        ("demolition_carbon_cost", "demolition_carbon_cost_pct"),
        "demolition_data.demolition_carbon_cost",
        errors,
        minimum=0,
    )
    _require_number(
        demolition,
        "demolition_duration",
        "demolition_data.demolition_duration",
        errors,
        positive=True,
    )

    _require_number(
        material_emissions,
        "total_kgCO2e",
        "carbon_emission_data.material_emissions_data.total_kgCO2e",
        errors,
        minimum=0,
    )
    _require_number(
        transport_emissions,
        "total_kgCO2e",
        "carbon_emission_data.transport_emissions_data.total_kgCO2e",
        errors,
        minimum=0,
    )
    _require_number(
        machinery_emissions,
        "total_kgCO2e",
        "carbon_emission_data.machinery_emissions_data.total_kgCO2e",
        errors,
        minimum=0,
    )
    social_cost_value = _first_value(
        social_result.get("cost_of_carbon_local"),
        social_cost.get("cost_of_carbon_local"),
        social_cost.get("calculated_scc_local"),
    )
    if not _has_value(social_cost_value):
        errors.append("carbon_emission_data.social_cost_data.cost_of_carbon_local is required.")
    elif _parse_number(social_cost_value) is None:
        errors.append("carbon_emission_data.social_cost_data.cost_of_carbon_local must be numeric.")
    elif _num(social_cost_value) < 0:
        errors.append("carbon_emission_data.social_cost_data.cost_of_carbon_local must be non-negative.")

    _require_number(
        recycling,
        "total_recovered_value",
        "recycling_data.total_recovered_value",
        errors,
        minimum=0,
    )

    mode = str(_first_value(traffic.get("mode"), traffic.get("calculation_mode")) or "").upper()
    if mode not in {"GLOBAL", "INDIA"}:
        errors.append("traffic_data.calculation_mode must be GLOBAL or INDIA.")
    elif use_global:
        _require_number(
            traffic,
            "road_user_cost_per_day",
            "traffic_data.road_user_cost_per_day",
            errors,
            minimum=0,
        )

    return errors


def _validate_india_traffic(
    project: dict[str, Any],
    core_traffic: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    traffic = _as_dict(project.get("traffic_and_road_data") or project.get("traffic_data"))
    vehicle_data = _as_dict(traffic.get("vehicle_data") or traffic.get("vehicles"))
    vehicles_per_day = _as_dict(traffic.get("vehicles_per_day"))

    additional = core_traffic["additional_inputs"]
    severity = core_traffic["accident_severity_distribution"]
    if not additional["alternate_road_carriageway"]:
        errors.append("traffic_data.alternate_road.alternate_road_carriageway is required.")
    if additional["carriage_width_in_m"] <= 0:
        errors.append("traffic_data.alternate_road.carriage_width_in_m must be greater than zero.")
    if additional["road_roughness_mm_per_km"] < 2000:
        errors.append("traffic_data.road_params.road_roughness_mm_per_km must be at least 2000.")
    if not 0 <= additional["work_zone_multiplier"] <= 1:
        errors.append("traffic_data.road_params.work_zone_multiplier must be between 0 and 1.")

    if core_traffic["total_adt"] > 0:
        for key in VEHICLE_TYPES:
            row = _as_dict(vehicle_data.get(key))
            raw_vpd = _first_value(row.get("vehicles_per_day"), row.get("adt"), vehicles_per_day.get(key))
            if not _has_value(raw_vpd):
                errors.append(f"traffic_data.vehicles.{key}.vehicles_per_day is required.")
            elif _parse_number(raw_vpd) is None or _num(raw_vpd) < 0:
                errors.append(f"traffic_data.vehicles.{key}.vehicles_per_day must be a non-negative number.")

            raw_accident = row.get("accident_percentage")
            if not _has_value(raw_accident):
                errors.append(f"traffic_data.vehicles.{key}.accident_percentage is required.")
            elif _parse_number(raw_accident) is None or _num(raw_accident) < 0:
                errors.append(f"traffic_data.vehicles.{key}.accident_percentage must be a non-negative number.")

            if key in {"hcv", "mcv"} and _num(raw_vpd) > 0:
                pwr = _parse_number(row.get("pwr"))
                if pwr is None or pwr <= 0:
                    errors.append(f"traffic_data.vehicles.{key}.pwr must be greater than zero when traffic is present.")

        accident_total = sum(
            _num(_as_dict(vehicle_data.get(key)).get("accident_percentage"))
            for key in VEHICLE_TYPES
        )
        if abs(accident_total - 100) > 0.1:
            errors.append("traffic_data vehicle accident percentages must sum to 100.")
        if abs(sum(severity.values()) - 100) > 1e-6:
            errors.append("traffic_data accident severity percentages must sum to 100.")
        if additional["hourly_capacity"] <= 0:
            errors.append("traffic_data.alternate_road.hourly_capacity must be greater than zero.")
        if any(value <= 0 for value in additional["peak_hour_traffic_percent_per_hour"]):
            errors.append("traffic_data.peak_distribution values must be greater than zero.")
        if sum(additional["peak_hour_traffic_percent_per_hour"]) > 1:
            errors.append("traffic_data.peak_distribution values must not sum to more than 1.")

    return errors


def prepare_for_core(project: dict[str, Any], analysis_period_years: int) -> PreparedCorePayload:
    errors: list[str] = []
    warnings: list[str] = []
    project = _as_dict(project)
    traffic = _as_dict(project.get("traffic_and_road_data") or project.get("traffic_data"))
    mode = str(_first_value(traffic.get("mode"), traffic.get("calculation_mode")) or "").upper()
    use_global = mode == "GLOBAL"
    errors.extend(_validate_project_fields(project, analysis_period_years, use_global))

    construction = _construction_data(project)
    if construction["grand_total"] <= 0:
        errors.append("construction cost total is required. Fill Construction Work Data before calculating.")

    total_carbon_kg = _carbon_emissions_total(project)
    carbon = _as_dict(project.get("carbon_emission_data"))
    social = _as_dict(carbon.get("social_cost_data"))
    scc = _num(_first_value(
        _as_dict(social.get("result")).get("cost_of_carbon_local"),
        social.get("cost_of_carbon_local"),
        social.get("calculated_scc_local"),
    ))
    initial_carbon_cost = total_carbon_kg * scc

    general_parameters = _general_parameters(project, analysis_period_years, use_global)
    maintenance_stage = _maintenance_stage(project)

    if errors:
        raise AdapterValidationError(errors, warnings)

    input_data: dict[str, Any] = {
        "general_parameters": general_parameters,
        "maintenance_and_stage_parameters": maintenance_stage,
    }
    wpi = None
    total_adt = 0

    if use_global:
        input_data["daily_road_user_cost_with_vehicular_emissions"] = _global_daily_ruc(project)
        InputGlobalMetaData.from_dict(input_data)
    else:
        core_traffic = _traffic_data(project)
        total_adt = core_traffic["total_adt"]
        errors = _validate_india_traffic(project, core_traffic)
        if errors:
            raise AdapterValidationError(errors, warnings)
        input_data["traffic_and_road_data"] = {
            "vehicle_data": core_traffic["vehicle_data"],
            "accident_severity_distribution": core_traffic["accident_severity_distribution"],
            "additional_inputs": core_traffic["additional_inputs"],
        }
        wpi = _wpi(project)
        if wpi is None:
            raise AdapterValidationError(["traffic_data.wpi is required in INDIA mode."], warnings)
        try:
            WPIMetaData.from_dict(wpi)
        except (KeyError, TypeError, ValueError) as exc:
            raise AdapterValidationError([f"traffic_data.wpi is invalid: {exc}"], warnings) from exc
        InputMetaData.from_dict(input_data)

    construction_costs = {
        "initial_construction_cost": construction["grand_total"],
        "initial_carbon_emissions_cost": initial_carbon_cost,
        "superstructure_construction_cost": construction["superstructure_total"],
        "total_scrap_value": _recycling_total(project),
    }

    computed = {
        "construction": construction,
        "total_initial_emissions_kgCO2e": total_carbon_kg,
        "initial_carbon_emissions_cost": initial_carbon_cost,
        "total_scrap_value": construction_costs["total_scrap_value"],
        "use_global_road_user_calculations": use_global,
        "wpi_required": not use_global,
    }
    return PreparedCorePayload(input_data=input_data, construction_costs=construction_costs, wpi=wpi, computed=computed, warnings=warnings)


def validate_project(project: dict[str, Any], analysis_period_years: int) -> dict[str, list[str]]:
    try:
        prepared = prepare_for_core(project, analysis_period_years)
        return {"errors": [], "warnings": prepared.warnings}
    except AdapterValidationError as exc:
        return {"errors": exc.errors, "warnings": exc.warnings}
    except Exception as exc:  # Core dataclass validation errors should be user-visible.
        return {"errors": [str(exc)], "warnings": []}


def calculate_project(project: dict[str, Any], analysis_period_years: int, debug: bool = False) -> dict[str, Any]:
    prepared = prepare_for_core(project, analysis_period_years)
    results = run_full_lcc_analysis(
        prepared.input_data,
        prepared.construction_costs.copy(),
        wpi=prepared.wpi,
        debug=debug,
    )
    return {
        "results": results,
        "computed": prepared.computed,
        "validation": {
            "errors": [],
            "warnings": prepared.warnings + list(results.get("warnings", [])),
        },
    }
