from pylatex import NoEscape
from pylatex.utils import escape_latex

from ..gui.components.utils.common_requested_data import get_social_cost_data, get_currency
from ..gui.components.carbon_emission.widgets.scc_tabs.ricke import RICKE_FIELDS
from .SETTINGS import DECIMAL_PLACES_FOR_LATEX
from .common_code import fields_to_latex

_FMT = f"{{:.{DECIMAL_PLACES_FOR_LATEX}f}}"

_RICKE_SOURCES = {"K. Ricke et al. (Country-Level)", "ricke"}

_UNICODE_LATEX = [
    ("≈", r"$\approx$"),
    ("η", r"$\eta$"),
    ("°", r"$^\circ$"),
]


def _sanitize_ricke(d: dict) -> dict:
    """Escape string values for LaTeX, converting known unicode to math equivalents."""
    out = {}
    for k, v in d.items():
        if isinstance(v, str):
            safe = escape_latex(v)
            for char, repl in _UNICODE_LATEX:
                safe = safe.replace(char, repl)
            out[k] = NoEscape(safe)
        else:
            out[k] = v
    return out


_EXPLORER_URL = "https://country-level-scc.github.io/explorer/"


def _result_para(data: dict) -> str:
    result = data.get("result", {})
    currency = escape_latex(get_currency())
    cost = result.get("cost_of_carbon_local")
    try:
        cost_str = _FMT.format(float(cost))
    except (TypeError, ValueError):
        cost_str = "---"
    return (
        f"The applied Social Cost of Carbon is "
        f"\\textbf{{{cost_str}~{currency}/kgCO\\textsubscript{{2}}e}}. "
        f"For further reference, see \\textcolor{{blue}}{{\\href{{{_EXPLORER_URL}}}{{Country-level SCC Explorer}}}}."
    )


def _custom_para(data: dict) -> str:
    custom = data.get("custom", {})
    currency = escape_latex(get_currency())
    value = custom.get("entered_value") if custom.get("entered_value") is not None else custom.get("scc_value")
    try:
        value_str = _FMT.format(float(value))
    except (TypeError, ValueError):
        value_str = "---"
    source_raw = (custom.get("source") or "").strip()
    source_str = escape_latex(source_raw) if source_raw else "Source not mentioned"
    comments_raw = (custom.get("comments") or "").strip()
    comments_part = f" {escape_latex(comments_raw)}" if comments_raw else ""
    return (
        f"The Social Cost of Carbon (SCC) is entered manually as "
        f"\\textbf{{{value_str}~{currency}/kgCO\\textsubscript{{2}}e}}. "
        f"Source: {source_str}.{comments_part}"
    )


def social_cost_data_to_latex(controller=None) -> str:
    data = get_social_cost_data()
    source = data.get("source") or data.get("mode", "")

    if source in _RICKE_SOURCES:
        currency = escape_latex(get_currency())
        table = fields_to_latex(
            RICKE_FIELDS,
            _sanitize_ricke(data.get("ricke", {})),
            "Social Cost of Carbon --- Ricke et al. Parameters",
            "tab:scc_ricke_params",
            unit_overrides={"usd_to_local_rate": f"({currency}/USD)"},
        )
        return "\n\n".join(p for p in [table, _result_para(data)] if p)

    return _custom_para(data)
