from pylatex.utils import escape_latex

from .SETTINGS import LATEX_FONT_SIZE
from ..gui.components.utils.common_requested_data import (
    get_project_name, get_currency, get_bridge_data, get_analysis_period,
    get_general_info, get_traffic_and_road_data,
)
from .bridge_data_latex         import bridge_data_to_latex
from .financial_data_latex      import financial_data_to_latex
from .maintenance_data_latex    import maintenance_data_to_latex
from .structure_work_data_latex import structure_work_data_to_latex
from .traffic_and_road_data_latex.get_all_data import (
    traffic_fields_to_latex,
    global_traffic_fields_to_latex,
    vehicle_data_to_latex,
    diversion_emissions_to_latex,
    peak_hour_distribution_to_latex,
    wpi_tables_to_latex,
)
from .material_emissions_latex  import material_emissions_to_latex
from .transport_emissions_latex import transport_emissions_to_latex
from .machinery_emissions_latex import machinery_emissions_to_latex
from .recycling_latex           import recycling_to_latex
from .results_latex             import results_to_latex
from .html_to_latex             import format_remarks_latex


# ── Global document styling ───────────────────────────────────────────────────
# Import this in devmode (and anywhere else that builds a document) so all
# outputs share the same margins, fonts, and overflow handling.

PREAMBLE = [
    r"\documentclass{article}",
    r"\usepackage{booktabs}",
    r"\usepackage{array}",
    r"\usepackage{longtable}",
    r"\usepackage[a4paper, top=2.5cm, bottom=2.5cm, left=2.5cm, right=2.5cm]{geometry}",
    r"\usepackage{adjustbox}",
    r"\usepackage{pdflscape}",
    r"\usepackage[utf8]{inputenc}",
    r"\DeclareUnicodeCharacter{2082}{\textsubscript{2}}",
    # Table global styling
    r"\setlength{\tabcolsep}{4pt}",
    r"\renewcommand{\arraystretch}{1.2}",
    # longtable: flush left so it respects margins
    r"\setlength{\LTleft}{0pt}",
    r"\setlength{\LTright}{0pt}",
]

DOCUMENT_FONT = LATEX_FONT_SIZE   # \small | \footnotesize | \normalsize etc.


def build_document(body: str) -> str:
    """Wrap *body* in a complete LaTeX document using the shared PREAMBLE."""
    return "\n".join(PREAMBLE + [r"\begin{document}", DOCUMENT_FONT, body, r"\end{document}"])


# ── LaTeX helpers ─────────────────────────────────────────────────────────────

def _sec(title: str) -> str:
    return r"\section{" + escape_latex(title) + r"}"


def _subsec(title: str) -> str:
    return r"\subsection{" + escape_latex(title) + r"}"


def _para(text: str) -> str:
    return r"\par\medskip " + text + r"\par\medskip"


def _clearpage() -> str:
    return r"\clearpage"


# ── Section descriptions ──────────────────────────────────────────────────────

_DESC = {
    "bridge":       ("Bridge and Project Data",
                     "This section summarises the physical characteristics of the bridge, "
                     "the financial parameters used in discounting future costs, and the "
                     "maintenance schedule assumed over the analysis period."),
    "structure":    ("Structure Work Data",
                     "This section lists all structural work items grouped by component "
                     "(Foundation, Sub-Structure, Super-Structure, and Miscellaneous). "
                     "Each item shows the quantity, unit, unit rate, rate source, and "
                     "computed total cost. Items marked as source-modified are indicated "
                     "with footnote symbols."),
    "traffic":      ("Traffic and Road Data",
                     "This section documents the traffic and road parameters used in "
                     "computing road user costs during construction and maintenance events, "
                     "including vehicle composition, peak-hour distribution, rerouting "
                     "configuration, and WPI adjustment factors."),
    "emissions":    ("Carbon Emissions",
                     "This section quantifies the embodied carbon emissions associated "
                     "with construction materials, transportation of those materials to "
                     "site, and machinery and equipment operation. Emission factors are "
                     "expressed in kgCO\\textsubscript{2}e per unit. It also presents "
                     "the recyclability of construction materials at end of life, including "
                     "recovered quantities and salvage values."),
    "results":      ("Life Cycle Cost Analysis Results",
                     "This section presents the full life cycle cost breakdown, organised "
                     "by project stage (Initial, Use, Reconstruction, End-of-Life) and "
                     "cost category (Economic, Environmental, Social). All values are "
                     "present values discounted to the base year."),
}


# ── Section builders ──────────────────────────────────────────────────────────

def _build_section(key: str, fns: list, controller, subsections: list | None = None) -> list:
    title, description = _DESC[key]
    section_parts = []

    for i, fn in enumerate(fns):
        try:
            out = fn(controller)
            if out and out.strip():
                if subsections and i < len(subsections):
                    section_parts.append(_subsec(subsections[i]))
                section_parts.append(out)
        except Exception:
            pass

    if not section_parts:
        return []

    return [
        _sec(title),
        _para(description),
    ] + section_parts


# ── Public entry point ────────────────────────────────────────────────────────

def final_report_to_latex(controller=None) -> str:
    project_name   = get_project_name()     or "Unnamed Project"
    currency       = get_currency()         or "Currency"
    analysis_period = get_analysis_period()
    bridge         = get_bridge_data()
    design_life    = bridge.get("design_life", "—")

    intro_lines = [
        rf"This report presents the Life Cycle Cost Analysis (LCCA) for the bridge project "
        rf"\textbf{{{escape_latex(project_name)}}}. ",
    ]
    if analysis_period:
        intro_lines.append(
            rf"The analysis covers a period of \textbf{{{analysis_period} years}}, "
            rf"with a bridge design life of \textbf{{{design_life} years}}. "
        )
    intro_lines.append(
        rf"All monetary values are expressed in \textbf{{{escape_latex(currency)}}} "
        rf"as present values discounted to the base year unless stated otherwise."
    )

    parts = [
        r"\par\medskip\noindent " + "".join(intro_lines) + r"\par\medskip",
        format_remarks_latex(get_general_info(), label="Project Remarks"),
        _clearpage(),
    ]

    # ── Section 1: Bridge, Financial, Maintenance ─────────────────────────────
    parts += _build_section("bridge", [
        bridge_data_to_latex,
        financial_data_to_latex,
        maintenance_data_to_latex,
    ], controller, subsections=[
        "Bridge Data",
        "Financial Parameters",
        "Maintenance Schedule",
    ])

    parts.append(_clearpage())

    # ── Section 2: Structure Work Data ────────────────────────────────────────
    parts += _build_section("structure", [structure_work_data_to_latex], controller)

    parts.append(_clearpage())

    # ── Section 3: Traffic and Road Data ─────────────────────────────────────
    _traffic_mode = get_traffic_and_road_data().get("mode", "")
    if _traffic_mode == "GLOBAL":
        parts += _build_section("traffic", [
            global_traffic_fields_to_latex,
        ], controller)
    else:
        parts += _build_section("traffic", [
            traffic_fields_to_latex,
            vehicle_data_to_latex,
            diversion_emissions_to_latex,
            peak_hour_distribution_to_latex,
            wpi_tables_to_latex,
        ], controller, subsections=[
            "Road and Traffic Parameters",
            "Vehicle Traffic Data",
            "Traffic Diversion Emissions",
            "Peak Hour Distribution",
            "Wholesale Price Index (WPI) Adjustment Factors",
        ])

    parts.append(_clearpage())

    # ── Section 4: Carbon Emissions ───────────────────────────────────────────
    parts += _build_section("emissions", [
        material_emissions_to_latex,
        transport_emissions_to_latex,
        machinery_emissions_to_latex,
        recycling_to_latex,
    ], controller, subsections=[
        "Material Embodied Carbon",
        "Transport Emissions",
        "Machinery and Equipment Emissions",
        "Recyclability",
    ])

    parts.append(_clearpage())

    # ── Section 5: LCCA Results ───────────────────────────────────────────────
    parts += _build_section("results", [results_to_latex], controller)

    return "\n\n".join(p for p in parts if p and p.strip())
