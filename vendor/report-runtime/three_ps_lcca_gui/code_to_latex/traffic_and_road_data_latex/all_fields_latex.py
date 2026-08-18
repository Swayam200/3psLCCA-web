import pandas as pd
from pylatex.utils import escape_latex
from ...gui.components.traffic_data.main import TRAFFIC_FIELDS, _BY_CODE
from ...gui.components.utils.common_requested_data import get_currency
from ..common_code import fields_to_latex
from ..SETTINGS import DECIMAL_PLACES_FOR_LATEX


def _traffic_fields(data: dict) -> str:
    display_data = dict(data)
    code = display_data.get("alternate_road_carriageway", "")
    display_data["alternate_road_carriageway"] = _BY_CODE.get(code, code)

    return fields_to_latex(
        TRAFFIC_FIELDS,
        display_data,
        "Traffic and Road Data",
        "tab:traffic_and_road_data",
    )


def _global_traffic_fields(data: dict) -> str:
    currency = escape_latex(get_currency())
    global_entry = data.get("global_entry", {})
    cost = global_entry.get("road_user_cost_per_day")
    source = (global_entry.get("source") or "").strip()
    comments = (global_entry.get("comments") or "").strip()

    cost_str = (
        f"{float(cost):,.{DECIMAL_PLACES_FOR_LATEX}f}"
        if cost is not None
        else r"\textemdash"
    )

    source_sent = (
        rf" This estimate is based on {escape_latex(source)}."
        if source else " Source not mentioned."
    )
    comments_sent = (
        rf" {escape_latex(comments)}"
        if comments else ""
    )

    paragraph = (
        rf"For this project, the road user cost incurred during the construction phase "
        rf"has been assessed on a per-day basis. The total road user cost per day, "
        rf"accounting for delays, detours, and associated user inconveniences, is "
        rf"\textbf{{{cost_str}}}~{currency}/day.{source_sent}{comments_sent}"
    )

    rows = [
        ("Road User Cost per Day", rf"\textbf{{{cost_str}}}~{currency}/day"),
        ("Source", escape_latex(source) if source else "Not mentioned"),
    ]
    if comments:
        rows.append(("Comments", escape_latex(comments)))

    detail = "\n".join(
        rf"  \noindent\textbf{{{escape_latex(label)}:}}\quad {value} \par\smallskip"
        for label, value in rows
    )

    return (
        "\n\\medskip\n"
        + rf"\noindent {paragraph}"
        + "\n\n\\medskip\n"
        + detail
        + "\n\\medskip\n"
    )


def _peak_hour_distribution(data: dict) -> str:
    peak_data = data.get("peak_hour_distribution", {})
    n = data.get("num_peak_hours", len(peak_data))

    rows = []
    for i in range(1, int(n) + 1):
        val = peak_data.get(f"peak_hour_{i}")
        rows.append({
            "Hour": f"Peak Hour {i}",
            r"Traffic Proportion (\%)": val * 100 if val is not None else None,
        })

    df = pd.DataFrame(rows)
    return ((
        df.style
        .hide(axis="index")
        .format(
            {r"Traffic Proportion (\%)": f"{{:.{DECIMAL_PLACES_FOR_LATEX}f}}"},
            na_rep=r"\multicolumn{1}{c}{\textemdash}",
        )
        .to_latex(
            caption="Peak Hour Traffic Distribution",
            label="tab:peak_hour_distribution",
            hrules=True,
            column_format="lr",
            position="h!",
            position_float="centering",
        )
    ) or "").replace("Hour & Traffic Proportion (\\%)", r"\textbf{Hour} & \textbf{Traffic Proportion (\%)}")
