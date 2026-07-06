from __future__ import annotations

import json
import sys
import copy
from pathlib import Path


(
    core_root,
    fixture_path,
    wpi_path,
    global_output_path,
    india_project_path,
    india_output_path,
) = map(Path, sys.argv[1:7])
web_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(core_root / "src"))
sys.path.insert(0, str(web_root / "src"))

from wasm.python.web_to_core import calculate_project, configure_wpi_database


project = json.loads(fixture_path.read_text(encoding="utf-8"))
wpi_database = json.loads(wpi_path.read_text(encoding="utf-8"))
configure_wpi_database(wpi_database)
calculation = calculate_project(project, 50, debug=False)
global_output_path.write_text(
    json.dumps({"status": "success", **calculation}, indent=2, allow_nan=False) + "\n",
    encoding="utf-8",
)

vehicle_types = (
    "small_cars",
    "big_cars",
    "two_wheelers",
    "o_buses",
    "d_buses",
    "lcv",
    "hcv",
    "mcv",
)
vehicles = {
    vehicle: {
        "vehicles_per_day": 0,
        "accident_percentage": 0,
        "pwr": 7.22 if vehicle == "hcv" else 8.0 if vehicle == "mcv" else 0,
    }
    for vehicle in vehicle_types
}
vehicles["small_cars"].update({"vehicles_per_day": 100, "accident_percentage": 100})
wpi_2024 = next(
    entry for entry in wpi_database["entries"] if entry["metadata"]["name"] == "2024"
)

india_project = copy.deepcopy(project)
india_project["traffic_data"] = {
    "calculation_mode": "INDIA",
    "vehicles": vehicles,
    "severity": {
        "severity_minor": 60,
        "severity_major": 30,
        "severity_fatal": 10,
    },
    "alternate_road": {
        "alternate_road_carriageway": "Two Lane (Two Way)",
        "carriage_width_in_m": 7,
        "hourly_capacity": 2400,
    },
    "road_params": {
        "road_roughness_mm_per_km": 2000,
        "road_rise_m_per_km": 0,
        "road_fall_m_per_km": 0,
        "additional_reroute_distance_km": 2,
        "additional_travel_time_min": 10,
        "crash_rate_accidents_per_million_km": 0.5,
        "work_zone_multiplier": 0.5,
    },
    "peak_distribution": {"hour_1": 0.1, "hour_2": 0.1},
    "force_free_flow": True,
    "wpi_profile": "2024",
    "wpi_year": "2024",
    "wpi_data": wpi_2024["data"],
}
india_calculation = calculate_project(india_project, 50, debug=False)
india_project_path.write_text(
    json.dumps(india_project, indent=2, allow_nan=False) + "\n",
    encoding="utf-8",
)
india_output_path.write_text(
    json.dumps({"status": "success", **india_calculation}, indent=2, allow_nan=False) + "\n",
    encoding="utf-8",
)
