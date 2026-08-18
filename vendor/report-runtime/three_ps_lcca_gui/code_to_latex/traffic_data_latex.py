import pandas as pd
from ..gui.components.traffic_data.main import _VEHICLES, _HAS_PWR, CHUNK
from ..gui.project_controller import ProjectController


def vehicle_traffic_data_to_latex(controller: ProjectController) -> str:
    vehicle_data = controller.get_chunk(CHUNK).get("vehicle_data", {})

    rows = []
    for key, label in _VEHICLES:
        v = vehicle_data.get(key, {})
        rows.append({
            "Vehicle Type": label,
            "Vehicles / Day": v.get("vehicles_per_day", 0),
            r"Accident (\% of vehicles)": v.get("accident_percentage", 0.0),
            "PWR": f"{v.get('pwr', 0.0):.2f}" if key in _HAS_PWR else "-",
        })

    df = pd.DataFrame(rows)
    return df.style.hide(axis="index").to_latex(
        caption="Vehicle Traffic Data",
        label="tab:vehicle_traffic_data",
        hrules=True,
        column_format="lrrr",
        position="h!",
        position_float="centering",
    ) or ""
