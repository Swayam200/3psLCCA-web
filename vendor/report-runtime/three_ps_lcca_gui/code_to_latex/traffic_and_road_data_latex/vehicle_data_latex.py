import pandas as pd
from ...gui.components.traffic_data.main import _VEHICLES, _HAS_PWR
from ..SETTINGS import DECIMAL_PLACES_FOR_LATEX


def _vehicle_data(data: dict) -> str:
    vehicle_data = data.get("vehicle_data", {})

    rows = []
    for key, label in _VEHICLES:
        v = vehicle_data.get(key, {})
        rows.append({
            "Vehicle Type": label,
            "Vehicles / Day": v.get("vehicles_per_day", 0),
            r"Accident (\% of vehicles)": v.get("accident_percentage", 0.0),
            "PWR": v.get("pwr", 0.0) if key in _HAS_PWR else None,
        })

    df = pd.DataFrame(rows)
    return (
        df.style
        .hide(axis="index")
        .format({"PWR": f"{{:.{DECIMAL_PLACES_FOR_LATEX}f}}", r"Accident (\% of vehicles)": f"{{:.{DECIMAL_PLACES_FOR_LATEX}f}}"}, na_rep=r"\textemdash")
        .to_latex(
            caption="Vehicle Traffic Data",
            label="tab:vehicle_data",
            hrules=True,
            column_format="lrrr",
            position="h!",
            position_float="centering",
        )
    ) or ""
