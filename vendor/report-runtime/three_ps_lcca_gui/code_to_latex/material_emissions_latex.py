from pylatex import NoEscape
from pylatex.utils import escape_latex

from ..gui.components.utils.common_requested_data import get_chunk
from .SETTINGS import DECIMAL_PLACES_FOR_LATEX
from .html_to_latex import format_remarks_latex
from .structure_work_data_latex import (
    get_all_structure_chunks,
    collect_for_emissions,
    longtable_sections,
)
from .common_code import latex_layout

_EMDASH = r"\textemdash"

_INC_COLS    = 7
_INC_SPEC    = latex_layout("material_emissions")
_INC_HEADERS = [
    "Material", "Quantity", "Unit",
    "Conversion Factor", "Emission Factor",
    NoEscape(r"Emission Factor Unit"),
    NoEscape(r"Total (kgCO\textsubscript{2}e)"),
]

_EXC_COLS    = 2
_EXC_SPEC    = latex_layout("material_emissions_excluded")
_EXC_HEADERS = ["Material", "Exclusion Reason"]


def _fmt(val) -> str:
    try:
        return f"{float(val):,.{DECIMAL_PLACES_FOR_LATEX}f}"
    except (TypeError, ValueError):
        return _EMDASH


def _fmt_ef_unit(unit: str) -> str:
    return (unit or "").replace("CO2e", "CO₂e").replace("m2", "m²").replace("m3", "m³")


def _get_included_table(included: dict) -> str:
    if not included:
        return ""

    sections = []
    for (category, comp_name), rows in included.items():
        cells = [
            [
                escape_latex(r["material"]),
                _fmt(r["qty"]),
                escape_latex(r["unit"]),
                _fmt(r["cf"]),
                _fmt(r["ef"]),
                escape_latex(_fmt_ef_unit(r["ef_unit"])),
                _fmt(r["total"]),
            ]
            for r in rows
        ]
        sections.append((f"{category} — {comp_name}", cells))

    return longtable_sections(
        _INC_SPEC, _INC_COLS,
        "Materials Included in Carbon Emissions Calculation",
        "tab:material_emissions_included",
        _INC_HEADERS, sections,
    )


def _get_excluded_table(excluded: dict) -> str:
    if not excluded:
        return ""

    sections = []
    for (category, comp_name), entries in excluded.items():
        sections.append(
            (f"{category} — {comp_name}",
             [[escape_latex(name), escape_latex(reason) if reason else _EMDASH]
              for name, reason in entries])
        )

    return longtable_sections(
        _EXC_SPEC, _EXC_COLS,
        "Materials Excluded from Carbon Emissions Calculation",
        "tab:material_emissions_excluded",
        _EXC_HEADERS, sections,
    )


def material_emissions_to_latex(controller=None) -> str:
    all_chunks = get_all_structure_chunks()
    included, excluded = collect_for_emissions(all_chunks)

    parts = [_get_included_table(included), _get_excluded_table(excluded)]
    out = "\n\n".join(t for t in parts if t)

    data = get_chunk("material_emissions_data")
    remarks = format_remarks_latex(data)
    if remarks:
        out += "\n\n" + remarks
    return out
