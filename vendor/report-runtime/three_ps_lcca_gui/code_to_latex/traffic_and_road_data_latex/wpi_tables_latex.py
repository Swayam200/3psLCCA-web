import pandas as pd
from pylatex import Table, Tabular, MultiColumn, NoEscape
from pylatex.utils import bold
from ...gui.components.traffic_data.wpi_table import _VEHICLES, _COLUMNS, _col_key
from ..SETTINGS import DECIMAL_PLACES_FOR_LATEX, DECIMAL_PLACES_FOR_LATEX_RATIO

_N_COLS   = 1 + len(_COLUMNS)
_COL_SPEC = "l" + "r" * len(_COLUMNS)
_EMDASH   = NoEscape(r"\textemdash")


def _full_width(latex: str) -> str:
    return (
        latex
        .replace(r"\begin{tabular}", r"\begin{adjustbox}{width=\linewidth}\begin{tabular}", 1)
        .replace(r"\end{tabular}",   r"\end{tabular}\end{adjustbox}", 1)
    )


# ── Shared pandas builder ─────────────────────────────────────────────────────

def _wpi_to_styler(data: dict, fmt: str):
    col_keys   = [_col_key(c) for c in _COLUMNS]
    col_labels = [c.label      for c in _COLUMNS]

    rows = []
    for vkey, _ in _VEHICLES:
        vdata = data.get(vkey, {})
        rows.append([vdata.get(k) for k in col_keys])

    index = [label for _, label in _VEHICLES]
    df = pd.DataFrame(rows, index=index, columns=col_labels)
    df.index.name = "Vehicle"
    return df.style.format(fmt, na_rep=r"\textemdash")


# ── Individual tables (pandas) ────────────────────────────────────────────────

def _get_wpi_base(data: dict) -> str:
    return _full_width(_wpi_to_styler(data, f"{{:.{DECIMAL_PLACES_FOR_LATEX}f}}").to_latex(
        caption="WPI Base Adjustment Factors (2019 Base Year). All values in INR.",
        label="tab:wpi_base",
        hrules=True,
        column_format=_COL_SPEC,
        position="h!",
        position_float="centering",
    ) or "")


def _get_wpi_selected(data: dict) -> str:
    return _full_width(_wpi_to_styler(data, f"{{:.{DECIMAL_PLACES_FOR_LATEX}f}}").to_latex(
        caption="WPI Selected Year Adjustment Factors. All values in INR.",
        label="tab:wpi_selected",
        hrules=True,
        column_format=_COL_SPEC,
        position="h!",
        position_float="centering",
    ) or "")


def _get_wpi_ratio(data: dict) -> str:
    return _full_width(_wpi_to_styler(data, f"{{:.{DECIMAL_PLACES_FOR_LATEX_RATIO}f}}").to_latex(
        caption="WPI Adjustment Ratios (Selected / Base). All values in INR.",
        label="tab:wpi_ratio",
        hrules=True,
        column_format=_COL_SPEC,
        position="h!",
        position_float="centering",
    ) or "")


# ── Combined mixed table (pylatex) ────────────────────────────────────────────

def _add_section(tabular: Tabular, header: str, data: dict, dp: int):
    tabular.append(NoEscape(
        MultiColumn(_N_COLS, align="l", data=bold(header)).dumps() + r" \\"
    ))
    tabular.append(NoEscape(r"\midrule"))

    col_keys = [_col_key(c) for c in _COLUMNS]
    for vkey, vlabel in _VEHICLES:
        vdata = data.get(vkey, {})
        row = [vlabel]
        for ck in col_keys:
            val = vdata.get(ck)
            row.append(f"{float(val):,.{dp}f}" if val is not None else _EMDASH)
        tabular.add_row(row)


def _wpi_combined_table(base: dict, selected: dict, ratio: dict) -> str:
    col_labels = [c.label for c in _COLUMNS]

    tabular = Tabular(_COL_SPEC)
    tabular.append(NoEscape(r"\toprule"))
    tabular.add_row(["Vehicle"] + col_labels)
    tabular.append(NoEscape(r"\midrule"))

    _add_section(tabular, "Ratio (Selected / Base)",  ratio,    DECIMAL_PLACES_FOR_LATEX_RATIO)
    tabular.append(NoEscape(r"\midrule"))
    _add_section(tabular, "Selected Year Values",      selected, DECIMAL_PLACES_FOR_LATEX)
    tabular.append(NoEscape(r"\midrule"))
    _add_section(tabular, "Base Year Values (2019)",   base,     DECIMAL_PLACES_FOR_LATEX)
    tabular.append(NoEscape(r"\bottomrule"))

    table = Table(position="h!")
    table.append(NoEscape(r"\centering"))
    table.add_caption("WPI Adjustment Factors — Combined. All values in INR.")
    table.append(NoEscape(r"\label{tab:wpi_combined}"))
    table.append(tabular)

    return _full_width(table.dumps())
