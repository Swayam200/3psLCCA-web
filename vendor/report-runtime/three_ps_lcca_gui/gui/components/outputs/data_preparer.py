"""
gui/components/outputs/data_preparer.py
Helper class to map raw UI data dictionaries to Core LCCA objects.
"""

import datetime

from three_ps_lcca_gui.gui._CONFIG import DEV_MODE
from three_ps_lcca_core.inputs.input import (
    InputMetaData,
    GeneralParameters,
    TrafficAndRoadData,
    VehicleData,
    VehicleMetaData,
    AccidentSeverityDistribution,
    AdditionalInputs,
    MaintenanceAndStageParameters,
    UseStageCost,
    Routine,
    RoutineInspection,
    RoutineMaintenance,
    Major,
    MajorInspection,
    MajorRepair,
    ReplacementCost,
    EndOfLifeStageCosts,
    DemolitionDisposal,
)
from three_ps_lcca_core.inputs.input_global import (
    InputGlobalMetaData,
    DailyRoadUserCost,
    TotalCarbonEmission,
)
from three_ps_lcca_core.inputs.wpi import WPIMetaData


def print_dev(*args) -> None:
    """Print a loud dev warning — only fires when DEV_MODE is True."""
    if DEV_MODE:
        msg = " ".join(str(a) for a in args)
        print(f"\n{'='*60}")
        print(f"  [DEV] DATA PREPARER WARNING")
        print(f"  {msg}")
        print(f"{'='*60}\n")


def _check(value, field: str, section: str = "") -> None:
    """Warn loudly in dev mode when a required field resolved to None."""
    if value is None:
        loc = f"{section}.{field}" if section else field
        print_dev(f"MISSING VALUE: '{loc}' is None — float/int conversion will crash!")


class DataPreparer:
    @staticmethod
    def prepare_life_cycle_construction_cost(data: dict):
        """
        Creates the life cycle construction cost breakdown dict.
        """
        if data.get("carbon_emission_data") is None:
            print_dev("'carbon_emission_data' missing in prepare_life_cycle_construction_cost!")
        if data.get("construction_work_data") is None:
            print_dev("'construction_work_data' missing in prepare_life_cycle_construction_cost!")
        if data.get("recycling_data") is None:
            print_dev("'recycling_data' missing in prepare_life_cycle_construction_cost!")

        carbon_emissions = data.get("carbon_emission_data")
        carbon_cost_per_kg = (
            carbon_emissions.get("social_cost_data")
            .get("result")
            .get("cost_of_carbon_local")
        )

        mat_co2 = float(
            carbon_emissions.get("material_emissions_data").get("total_kgCO2e")
        )
        trans_co2 = float(
            carbon_emissions.get("transport_emissions_data").get("total_kgCO2e")
        )
        mach_co2 = float(
            carbon_emissions.get("machinery_emissions_data").get("total_kgCO2e")
        )
        total_kgCO2e = mat_co2 + trans_co2 + mach_co2

        construction_work_data = data.get("construction_work_data")
        grand_total = float(construction_work_data.get("grand_total"))
        super_total = float(construction_work_data.get("Super-Structure").get("total"))
        scrap_value = float(data.get("recycling_data").get("total_recovered_value"))

        return {
            "initial_construction_cost": grand_total,
            "initial_carbon_emissions_cost": total_kgCO2e * carbon_cost_per_kg,
            "superstructure_construction_cost": super_total,
            "total_scrap_value": scrap_value,
        }

    @staticmethod
    def prepare_wpi_object(data: dict):
        """
        Creates a WPIMetaData object.
        """
        wpi_data = data.get("traffic_and_road_data").get("wpi")
        wpi_dict = wpi_data.get("data_snapshot").get("ratio")
        year = int(
            wpi_data.get("selected_profile_year")
            or wpi_data.get("selected_profile_name", 0)
        )
        return WPIMetaData.from_dict({"year": year, "WPI": wpi_dict})

    @staticmethod
    def prepare_data_object(data: dict, analysis_period_years: int):
        """
        Creates Core Data Object (InputMetaData or InputGlobalMetaData).
        """
        _financial_data = data.get("financial_data")
        if _financial_data is None:
            print_dev("'financial_data' section is entirely missing from inputs!")
            raise ValueError(
                "Financial Data is missing from the calculation inputs.\n"
                "Fill in the Financial Data page and try again."
            )

        _check(_financial_data.get("discount_rate"), "discount_rate", "financial_data")
        _check(_financial_data.get("inflation_rate"), "inflation_rate", "financial_data")
        _check(_financial_data.get("interest_rate"), "interest_rate", "financial_data")
        _check(_financial_data.get("investment_ratio"), "investment_ratio", "financial_data")
        discount_rate_percent = float(_financial_data.get("discount_rate"))
        inflation_rate_percent = float(_financial_data.get("inflation_rate"))
        interest_rate_percent = float(_financial_data.get("interest_rate"))
        investment_ratio = float(_financial_data.get("investment_ratio"))

        scc_from_fin = _financial_data.get("social_cost_of_carbon")
        if scc_from_fin is not None:
            social_cost_of_carbon_per_mtco2e = float(scc_from_fin) * 1000
        else:
            _result = (
                data.get("carbon_emission_data", {})
                .get("social_cost_data", {})
                .get("result", {})
            )
            social_cost_of_carbon_per_mtco2e = (
                float(_result.get("cost_of_carbon_local", 0.0)) * 1000
            )

        currency_conversion = float(_financial_data.get("currency_conversion", 1.0))

        _bridge_data = data.get("bridge_data")
        if _bridge_data is None:
            print_dev("'bridge_data' section is entirely missing from inputs!")
        else:
            _check(_bridge_data.get("design_life"), "design_life", "bridge_data")
            _check(_bridge_data.get("duration_construction_months"), "duration_construction_months", "bridge_data")
            _check(_bridge_data.get("working_days_per_month"), "working_days_per_month", "bridge_data")
            _check(_bridge_data.get("days_per_month"), "days_per_month", "bridge_data")
        service_life_years = int(_bridge_data.get("design_life"))
        construction_period_months = float(
            _bridge_data.get("duration_construction_months")
        )
        working_days_per_month = float(_bridge_data.get("working_days_per_month"))
        days_per_month = float(_bridge_data.get("days_per_month"))

        use_global_road_user_calculations = (
            data.get("traffic_and_road_data").get("mode") == "GLOBAL"
        )

        general_parameters = GeneralParameters(
            service_life_years=service_life_years,
            analysis_period_years=analysis_period_years,
            discount_rate_percent=discount_rate_percent,
            inflation_rate_percent=inflation_rate_percent,
            interest_rate_percent=interest_rate_percent,
            investment_ratio=investment_ratio,
            social_cost_of_carbon_per_mtco2e=social_cost_of_carbon_per_mtco2e,
            currency_conversion=currency_conversion,
            construction_period_months=construction_period_months,
            working_days_per_month=working_days_per_month,
            days_per_month=days_per_month,
            use_global_road_user_calculations=use_global_road_user_calculations,
        )

        _maintenance_data = data.get("maintenance_data")
        _demolition_data = data.get("demolition_data")

        if _maintenance_data is None:
            print_dev("'maintenance_data' section is entirely missing from inputs!")
        else:
            for _mf in (
                "routine_inspection_cost", "routine_inspection_freq",
                "periodic_maintenance_cost", "periodic_maintenance_carbon_cost", "periodic_maintenance_freq",
                "major_inspection_cost", "major_inspection_freq",
                "major_repair_cost", "major_repair_carbon_cost", "major_repair_freq",
                "major_repair_duration", "bearing_exp_joint_cost",
                "bearing_exp_joint_freq", "bearing_exp_joint_duration",
            ):
                _check(_maintenance_data.get(_mf), _mf, "maintenance_data")

        if _demolition_data is None:
            print_dev("'demolition_data' section is entirely missing from inputs!")
        else:
            for _df in ("demolition_cost_pct", "demolition_carbon_cost_pct", "demolition_duration"):
                _check(_demolition_data.get(_df), _df, "demolition_data")

        routine_inspection_picc_per_year = float(
            _maintenance_data.get("routine_inspection_cost")
        )
        routine_inspection_interval_in_years = int(
            _maintenance_data.get("routine_inspection_freq")
        )
        routine_maintenance_picc_per_year = float(
            _maintenance_data.get("periodic_maintenance_cost")
        )
        routine_maintenance_picec = float(
            _maintenance_data.get("periodic_maintenance_carbon_cost")
        )
        routine_maintenance_interval_in_years = int(
            _maintenance_data.get("periodic_maintenance_freq")
        )
        major_inspection_picc = float(_maintenance_data.get("major_inspection_cost"))
        major_inspection_interval_in_years = int(
            _maintenance_data.get("major_inspection_freq")
        )
        major_repair_picc = float(_maintenance_data.get("major_repair_cost"))
        major_repair_picec = float(_maintenance_data.get("major_repair_carbon_cost"))
        major_repair_interval_in_years = int(_maintenance_data.get("major_repair_freq"))
        major_repair_duration_months = int(_maintenance_data.get("major_repair_duration"))
        replace_bne_joint_pssc = float(_maintenance_data.get("bearing_exp_joint_cost"))
        replace_bne_joint_interval_in_years = int(
            _maintenance_data.get("bearing_exp_joint_freq")
        )
        replace_bne_joint_duration_in_days = int(
            _maintenance_data.get("bearing_exp_joint_duration")
        )
        eol_picc = float(_demolition_data.get("demolition_cost_pct"))
        eol_picec = float(_demolition_data.get("demolition_carbon_cost_pct"))
        eol_dd_in_months = int(_demolition_data.get("demolition_duration"))

        maintenance_and_stage_parameters = MaintenanceAndStageParameters(
            use_stage_cost=UseStageCost(
                routine=Routine(
                    inspection=RoutineInspection(
                        percentage_of_initial_construction_cost_per_year=routine_inspection_picc_per_year,
                        interval_in_years=routine_inspection_interval_in_years,
                    ),
                    maintenance=RoutineMaintenance(
                        percentage_of_initial_construction_cost_per_year=routine_maintenance_picc_per_year,
                        percentage_of_initial_carbon_emission_cost=routine_maintenance_picec,
                        interval_in_years=routine_maintenance_interval_in_years,
                    ),
                ),
                major=Major(
                    inspection=MajorInspection(
                        percentage_of_initial_construction_cost=major_inspection_picc,
                        interval_for_repair_and_rehabitation_in_years=major_inspection_interval_in_years,
                    ),
                    repair=MajorRepair(
                        percentage_of_initial_construction_cost=major_repair_picc,
                        percentage_of_initial_carbon_emission_cost=major_repair_picec,
                        interval_for_repair_and_rehabitation_in_years=major_repair_interval_in_years,
                        repairs_duration_months=major_repair_duration_months,
                    ),
                ),
                replacement_costs_for_bearing_and_expansion_joint=ReplacementCost(
                    percentage_of_super_structure_cost=replace_bne_joint_pssc,
                    interval_of_replacement_in_years=replace_bne_joint_interval_in_years,
                    duration_of_replacement_in_days=replace_bne_joint_duration_in_days,
                ),
            ),
            end_of_life_stage_costs=EndOfLifeStageCosts(
                demolition_and_disposal=DemolitionDisposal(
                    percentage_of_initial_construction_cost=eol_picc,
                    percentage_of_initial_carbon_emission_cost=eol_picec,
                    duration_for_demolition_and_disposal_in_months=eol_dd_in_months,
                )
            ),
        )

        if not use_global_road_user_calculations:
            _traffic_road_data = data.get("traffic_and_road_data")
            _traffic_vehicle_data = _traffic_road_data.get("vehicle_data")
            _ef = (
                data.get("carbon_emission_data", {})
                .get("diversion_emissions", {})
                .get("emission_factors", {})
            )
            _emission_factors = {k: float(v or 0.0) for k, v in _ef.items()}

            small_cars = VehicleMetaData(
                int(_traffic_vehicle_data.get("small_cars").get("vehicles_per_day")),
                _emission_factors.get("small_cars", 0.0),
                float(_traffic_vehicle_data.get("small_cars").get("accident_percentage")),
            )
            big_cars = VehicleMetaData(
                int(_traffic_vehicle_data.get("big_cars").get("vehicles_per_day")),
                _emission_factors.get("big_cars", 0.0),
                float(_traffic_vehicle_data.get("big_cars").get("accident_percentage")),
            )
            two_wheelers = VehicleMetaData(
                int(_traffic_vehicle_data.get("two_wheelers").get("vehicles_per_day")),
                _emission_factors.get("two_wheelers", 0.0),
                float(_traffic_vehicle_data.get("two_wheelers").get("accident_percentage")),
            )
            o_buses = VehicleMetaData(
                int(_traffic_vehicle_data.get("o_buses").get("vehicles_per_day")),
                _emission_factors.get("o_buses", 0.0),
                float(_traffic_vehicle_data.get("o_buses").get("accident_percentage")),
            )
            d_buses = VehicleMetaData(
                int(_traffic_vehicle_data.get("d_buses").get("vehicles_per_day")),
                _emission_factors.get("d_buses", 0.0),
                float(_traffic_vehicle_data.get("d_buses").get("accident_percentage")),
            )
            lcv = VehicleMetaData(
                int(_traffic_vehicle_data.get("lcv").get("vehicles_per_day")),
                _emission_factors.get("lcv", 0.0),
                float(_traffic_vehicle_data.get("lcv").get("accident_percentage")),
            )
            hcv = VehicleMetaData(
                int(_traffic_vehicle_data.get("hcv").get("vehicles_per_day")),
                _emission_factors.get("hcv", 0.0),
                float(_traffic_vehicle_data.get("hcv").get("accident_percentage")),
                pwr=float(_traffic_vehicle_data.get("hcv").get("pwr")),
            )
            mcv = VehicleMetaData(
                int(_traffic_vehicle_data.get("mcv").get("vehicles_per_day")),
                _emission_factors.get("mcv", 0.0),
                float(_traffic_vehicle_data.get("mcv").get("accident_percentage")),
                pwr=float(_traffic_vehicle_data.get("mcv").get("pwr")),
            )

            minor = float(_traffic_road_data.get("severity_minor"))
            major = float(_traffic_road_data.get("severity_major"))
            fatal = float(_traffic_road_data.get("severity_fatal"))

            alternate_road_carriageway = _traffic_road_data.get("alternate_road_carriageway")
            carriage_width_in_m = float(_traffic_road_data.get("carriage_width_in_m"))
            road_roughness_mm_per_km = float(_traffic_road_data.get("road_roughness_mm_per_km"))
            road_rise_m_per_km = float(_traffic_road_data.get("road_rise_m_per_km"))
            road_fall_m_per_km = float(_traffic_road_data.get("road_fall_m_per_km"))
            additional_reroute_distance_km = float(
                _traffic_road_data.get("additional_reroute_distance_km")
            )
            additional_travel_time_min = float(
                _traffic_road_data.get("additional_travel_time_min")
            )
            crash_rate_accidents_per_million_km = float(
                _traffic_road_data.get("crash_rate_accidents_per_million_km")
            )
            work_zone_multiplier = float(_traffic_road_data.get("work_zone_multiplier"))
            peak_hour_traffic_percent_per_hour = list(
                _traffic_road_data.get("peak_hour_distribution").values()
            )
            hourly_capacity = int(_traffic_road_data.get("hourly_capacity"))
            force_free_flow_off_peak = bool(_traffic_road_data.get("force_free_flow_off_peak"))

            traffic_and_road_data = TrafficAndRoadData(
                vehicle_data=VehicleData(
                    small_cars=small_cars,
                    big_cars=big_cars,
                    two_wheelers=two_wheelers,
                    o_buses=o_buses,
                    d_buses=d_buses,
                    lcv=lcv,
                    hcv=hcv,
                    mcv=mcv,
                ),
                accident_severity_distribution=AccidentSeverityDistribution(
                    minor=minor,
                    major=major,
                    fatal=fatal,
                ),
                additional_inputs=AdditionalInputs(
                    alternate_road_carriageway=alternate_road_carriageway,
                    carriage_width_in_m=carriage_width_in_m,
                    road_roughness_mm_per_km=road_roughness_mm_per_km,
                    road_rise_m_per_km=road_rise_m_per_km,
                    road_fall_m_per_km=road_fall_m_per_km,
                    additional_reroute_distance_km=additional_reroute_distance_km,
                    additional_travel_time_min=additional_travel_time_min,
                    crash_rate_accidents_per_million_km=crash_rate_accidents_per_million_km,
                    work_zone_multiplier=work_zone_multiplier,
                    peak_hour_traffic_percent_per_hour=peak_hour_traffic_percent_per_hour,
                    hourly_capacity=hourly_capacity,
                    force_free_flow_off_peak=force_free_flow_off_peak,
                ),
            )
            return False, InputMetaData(
                general_parameters=general_parameters,
                traffic_and_road_data=traffic_and_road_data,
                maintenance_and_stage_parameters=maintenance_and_stage_parameters,
            )
        else:
            _global_diversion = data.get("carbon_emission_data", {}).get(
                "diversion_emissions", {}
            )
            if _global_diversion.get("mode") == "Calculate by Vehicle":
                total_vehicular_carbon_emission = float(
                    _global_diversion.get("total_calculated_emissions", 0.0)
                )
            else:
                total_vehicular_carbon_emission = float(
                    _global_diversion.get("direct_entry", {}).get("total_direct_emissions", 0.0)
                )

            total_daily_ruc = float(
                data.get("traffic_and_road_data", {}).get("global_entry", {}).get("road_user_cost_per_day", 0.0)
            )
            daily_road_user_cost_with_vehicular_emissions = DailyRoadUserCost(
                total_daily_ruc=total_daily_ruc,
                total_carbon_emission=TotalCarbonEmission(
                    total_emission_kgCO2e=total_vehicular_carbon_emission
                ),
            )
            return True, InputGlobalMetaData(
                general_parameters=general_parameters,
                daily_road_user_cost_with_vehicular_emissions=daily_road_user_cost_with_vehicular_emissions,
                maintenance_and_stage_parameters=maintenance_and_stage_parameters,
            )

    @staticmethod
    def build_export_dict(all_data: dict, lcc_breakdown: dict, results: dict) -> dict:
        """
        Build the full export dict written to a .3ps file.

        Structure
        ---------
        {
          "format":      "3psLCCAFile",
          "version":     "1.0",
          "exported_at": "<ISO timestamp>",
          "inputs":  { ... },   # raw UI data from all pages
          "computed": { ... },  # initial_construction_cost, etc.
          "results": { ... }    # direct output of run_full_lcc_analysis
        }

        All values are sanitised to JSON-safe primitives.
        """
        def _sanitize(obj):
            """Recursively coerce non-JSON-serialisable values to primitives."""
            if obj is None or isinstance(obj, (bool, str)):
                return obj
            if isinstance(obj, float):
                return float(obj)
            if isinstance(obj, int):
                return int(obj)
            if isinstance(obj, dict):
                return {str(k): _sanitize(v) for k, v in obj.items()}
            if isinstance(obj, (list, tuple)):
                return [_sanitize(i) for i in obj]
            try:
                from dataclasses import asdict, fields
                fields(obj)
                return _sanitize(asdict(obj))
            except TypeError:
                pass
            try:
                return _sanitize(obj._asdict())
            except AttributeError:
                pass
            return str(obj)

        return {
            "format": "3psLCCAFile",
            "version": "1.0",
            "exported_at": datetime.datetime.now().isoformat(),
            "inputs": _sanitize(all_data),
            "computed": _sanitize(lcc_breakdown),
            "results": _sanitize(results),
        }
