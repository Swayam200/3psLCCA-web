from pylatex import NoEscape
from pylatex.utils import escape_latex

from ..gui.components.utils.common_requested_data import get_chunk, get_currency
from .SETTINGS import DECIMAL_PLACES_FOR_LATEX
from .html_to_latex import format_remarks_latex
from .structure_work_data_latex import (
    get_all_structure_chunks,
    collect_for_recycling,
    longtable_sections,
)
from .common_code import latex_layout

_EMDASH = r"\textemdash"

_INC_COLS = 6
_INC_SPEC = latex_layout("recycling_included")

_EXC_COLS    = 2
_EXC_SPEC    = latex_layout("recycling_excluded")
_EXC_HEADERS = ["Material", "Reason"]


def _fmt(val) -> str:
    try:
        return f"{float(val):,.{DECIMAL_PLACES_FOR_LATEX}f}"
    except (TypeError, ValueError):
        return _EMDASH


def _get_included_table(included: dict) -> str:
    if not included:
        return ""

    currency = escape_latex(get_currency())
    headers = [
        "Material",
        NoEscape(r"Recyclability \%"),
        "Recyclable Quantity",
        "Unit",
        f"Scrap Rate ({currency})",
        f"Recovered Value ({currency})",
    ]

    sections = []
    for (category, comp_name), rows in included.items():
        cells = [
            [
                escape_latex(r["name"]),
                _fmt(r["pct"]),
                _fmt(r["rec_qty"]),
                escape_latex(r["unit"]),
                _fmt(r["scrap"]),
                _fmt(r["rec_val"]),
            ]
            for r in rows
        ]
        sections.append((f"{category} — {comp_name}", cells))

    return longtable_sections(
        _INC_SPEC, _INC_COLS,
        "Materials Included in Recyclability Calculation",
        "tab:recycling_included",
        headers, sections,
    )


def _get_excluded_table(excluded: dict) -> str:
    if not excluded:
        return ""

    sections = []
    for (category, comp_name), rows in excluded.items():
        cells = [
            [escape_latex(r["name"]), escape_latex(r["reason"]) if r["reason"] else _EMDASH]
            for r in rows
        ]
        sections.append((f"{category} — {comp_name}", cells))

    return longtable_sections(
        _EXC_SPEC, _EXC_COLS,
        "Materials Excluded from Recyclability Calculation",
        "tab:recycling_excluded",
        _EXC_HEADERS, sections,
    )


def recycling_to_latex(controller=None) -> str:
    all_chunks = get_all_structure_chunks()
    included, excluded = collect_for_recycling(all_chunks)

    parts = [_get_included_table(included), _get_excluded_table(excluded)]
    out = "\n\n".join(t for t in parts if t)

    data = get_chunk("recycling_data")
    remarks = format_remarks_latex(data)
    if remarks:
        out += "\n\n" + remarks
    return out
