import pandas as pd
from ..gui.components.utils.common_requested_data import get_machinery_emissions_data
from .SETTINGS import DECIMAL_PLACES_FOR_LATEX
from .html_to_latex import format_remarks_latex

_FMT = f"{{:,.{DECIMAL_PLACES_FOR_LATEX}f}}"
_EMDASH = r"\textemdash"


def _fmt(val, decimals=None) -> float | None:
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _detailed_to_latex(data: dict) -> str:
    rows = []
    for row in data.get("detailed", {}).get("rows", []):
        rate = _fmt(row.get("rate", 0))
        hrs  = _fmt(row.get("hrs", 0))
        days = _fmt(row.get("days", 0))
        ef   = _fmt(row.get("ef", 0))
        consumption = (rate or 0) * (hrs or 0) * (days or 0)
        emission    = consumption * (ef or 0)
        rows.append({
            "Equipment Name":                row.get("name", ""),
            "Energy Source":                 row.get("source", ""),
            "Fuel / Power Rating":           rate,
            "Avg Hrs / Day":                 hrs,
            "No. of Days":                   days,
            "Emission Factor (kgCO₂e/unit)": ef,
            "Consumption":                   consumption,
            "Emissions (kgCO₂e)":           emission,
        })

    df = pd.DataFrame(rows)
    return ((
        df.style.hide(axis="index")
        .format(_FMT, subset=["Fuel / Power Rating", "Avg Hrs / Day", "No. of Days",
                               "Emission Factor (kgCO₂e/unit)", "Consumption",
                               "Emissions (kgCO₂e)"], na_rep=_EMDASH)
        .to_latex(
            caption="Machinery and Equipment Emissions (Detailed)",
            label="tab:machinery_equipment_emissions",
            hrules=True,
            column_format=(
                r">{\raggedright\arraybackslash}p{2.8cm}"
                r">{\raggedright\arraybackslash}p{1.6cm}"
                r">{\raggedleft\arraybackslash}p{1.2cm}"
                r">{\raggedleft\arraybackslash}p{1.1cm}"
                r">{\raggedleft\arraybackslash}p{1.1cm}"
                r">{\raggedleft\arraybackslash}p{1.7cm}"
                r">{\raggedleft\arraybackslash}p{1.8cm}"
                r">{\raggedleft\arraybackslash}p{2.1cm}"
            ),
            environment="longtable",
        )
    ) or "").replace(
        "Equipment Name & Energy Source & Fuel / Power Rating & Avg Hrs / Day & No. of Days & Emission Factor (kgCO₂e/unit) & Consumption & Emissions (kgCO₂e)",
        r"\textbf{Equipment Name} & \textbf{Energy Source} & \textbf{Fuel / Power Rating} & \textbf{Avg Hrs / Day} & \textbf{No. of Days} & \textbf{Emission Factor (kgCO₂e/unit)} & \textbf{Consumption} & \textbf{Emissions (kgCO₂e)}",
    )


def _lumpsum_to_latex(data: dict) -> str:
    ls = data.get("lumpsum", {})
    rows = []
    total = 0.0
    for label, cons_key, days_key, ef_key in [
        ("Electricity", "elec_consumption_per_day", "elec_days", "elec_ef"),
        ("Fuel",        "fuel_consumption_per_day", "fuel_days", "fuel_ef"),
    ]:
        cons = _fmt(ls.get(cons_key, 0))
        days = _fmt(ls.get(days_key, 0))
        ef   = _fmt(ls.get(ef_key, 0))
        emission = (cons or 0) * (days or 0) * (ef or 0)
        total += emission
        rows.append({
            "Source":                        label,
            "Consumption / Day":             cons,
            "Days":                          days,
            "Emission Factor (kgCO₂e/unit)": ef,
            "Emissions (kgCO₂e)":           emission,
        })

    paragraph = (
        rf"Machinery and equipment emissions have been entered as a lump sum. "
        rf"The total on-site carbon emissions amount to "
        rf"\textbf{{{total:.{DECIMAL_PLACES_FOR_LATEX}f}}}~kgCO\textsubscript{{2}}e, "
        rf"comprising contributions from electricity consumption and fuel usage as detailed below."
    )

    df = pd.DataFrame(rows)
    table = (
        df.style.hide(axis="index")
        .format(_FMT, subset=["Consumption / Day", "Days",
                               "Emission Factor (kgCO₂e/unit)", "Emissions (kgCO₂e)"],
                na_rep=_EMDASH)
        .to_latex(
            caption="Machinery and Equipment Emissions (Lump Sum)",
            label="tab:lumpsum_machinery_equipment_emissions",
            hrules=True,
            column_format="p{3cm}rrrr",
            position="h!",
        )
    ) or ""

    return "\n\\medskip\n" + rf"\noindent {paragraph}" + "\n\n" + table


def machinery_emissions_to_latex(controller=None) -> str:
    data = get_machinery_emissions_data()
    if data.get("mode", "detailed") == "lumpsum":
        out = _lumpsum_to_latex(data)
    else:
        out = _detailed_to_latex(data)
    
    remarks = format_remarks_latex(data)
    if remarks:
        out += "\n\n" + remarks
    return out
