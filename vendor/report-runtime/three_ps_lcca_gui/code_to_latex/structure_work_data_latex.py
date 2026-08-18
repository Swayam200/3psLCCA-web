from collections import defaultdict

from pylatex import LongTable, MultiColumn, NoEscape
from pylatex.utils import bold, italic, escape_latex

from ..gui.components.utils.common_requested_data import get_chunk, get_currency
from ..gui.components.utils.definitions import STRUCTURE_CHUNKS, UNIT_DISPLAY
from .SETTINGS import DECIMAL_PLACES_FOR_LATEX
from .common_code import latex_layout

_EMDASH     = NoEscape(r"\textemdash")
_CENTER_DASH = NoEscape(r"\multicolumn{1}{c}{\textemdash}")
_MIDRULE    = NoEscape(r"\midrule")
_BOTTOMRULE = NoEscape(r"\bottomrule")
_N_COLS     = 6
_COL_SPEC = latex_layout("structure_work")

_SOURCE_MARK = {
    "db":             "",
    "manual":         r"$^{\#}$",
    "db_modified":    r"$^{\S}$",
    "excel":          r"$^{\dagger}$",
    "excel_modified": r"$^{\ddagger}$",
}


# ── Shared utilities (used by emissions + recycling latex modules) ─────────────

def get_all_structure_chunks() -> dict:
    """Fetch all four structure chunks once; returns {chunk_id: data_dict}."""
    return {chunk_id: get_chunk(chunk_id) for chunk_id, _ in STRUCTURE_CHUNKS}


def longtable_sections(col_spec: str, n_cols: int, caption: str, label: str,
                       headers: list, sections: list) -> str:
    """Build a longtable from pre-built section rows.

    sections: list of (header_text, [[cell, ...], ...])
    """
    table = LongTable(col_spec)
    header_row = [NoEscape(r"\textbf{" + str(h) + "}") if isinstance(h, NoEscape) else bold(h) for h in headers]

    table.append(NoEscape(
        rf"\caption{{{escape_latex(caption)}}} \label{{{label}}} \\"
    ))
    table.append(NoEscape(r"\toprule"))
    table.add_row(header_row)
    table.append(NoEscape(r"\midrule"))
    table.append(NoEscape(r"\endhead"))

    table.append(NoEscape(r"\midrule"))
    table.append(NoEscape(
        rf"\multicolumn{{{n_cols}}}{{r}}{{\footnotesize\textit{{continued on next page}}}} \\"
    ))
    table.append(NoEscape(r"\endfoot"))

    table.append(NoEscape(r"\bottomrule"))
    table.append(NoEscape(r"\endlastfoot"))

    first = True
    for header_text, rows in sections:
        if not rows:
            continue
        if not first:
            table.append(NoEscape(r"\midrule"))
        first = False

        table.append(NoEscape(
            MultiColumn(n_cols, align="l",
                        data=bold(escape_latex(header_text))).dumps() + r" \\"
        ))
        table.append(NoEscape(r"\midrule"))

        for row in rows:
            table.add_row(row)

    return table.dumps()


def _fmt_emission(val) -> str:
    try:
        return f"{float(val):,.{DECIMAL_PLACES_FOR_LATEX}f}"
    except (TypeError, ValueError):
        return r"\textemdash"


def collect_for_emissions(all_chunks: dict) -> tuple[defaultdict, defaultdict]:
    """Split structure items into (included, excluded) for material-emissions tables.

    all_chunks: output of get_all_structure_chunks()
    Returns two defaultdict(list) keyed by (category, comp_name).
      included values: dicts with material/qty/unit/cf/ef/ef_unit/total keys
      excluded values: (material_name, reason) tuples
    """
    included = defaultdict(list)
    excluded = defaultdict(list)

    for chunk_id, category in STRUCTURE_CHUNKS:
        for comp_name, items in (all_chunks.get(chunk_id) or {}).items():
            for item in items:
                if item.get("state", {}).get("in_trash", False):
                    continue
                values = item.get("values", {})
                state  = item.get("state", {})
                key    = (category, comp_name)

                qty     = float(values.get("quantity",          0) or 0)
                cf      = float(values.get("conversion_factor", 1) or 1)
                ef      = float(values.get("carbon_emission",   0) or 0)
                unit    = UNIT_DISPLAY.get(values.get("unit", ""), values.get("unit", ""))
                ef_unit = values.get("carbon_unit", "")

                if state.get("included_in_carbon_emission") is True:
                    included[key].append({
                        "material": values.get("material_name", ""),
                        "qty": qty, "unit": unit,
                        "cf": cf, "ef": ef,
                        "ef_unit": ef_unit,
                        "total": qty * cf * ef,
                    })
                else:
                    reason = (values.get("exclusion_reason") or {}).get("carbon", "") or "Incomplete Data"
                    excluded[key].append((values.get("material_name", ""), reason))

    return included, excluded


def _recycle_pct(v: dict) -> float:
    return float(
        v.get("post_demolition_recovery_percentage")
        or v.get("recyclability_percentage")
        or 0
    )


def collect_for_recycling(all_chunks: dict) -> tuple[defaultdict, defaultdict]:
    """Split structure items into (included, excluded) for recycling tables.

    all_chunks: output of get_all_structure_chunks()
    Returns two defaultdict(list) keyed by (category, comp_name).
      included values: dicts with name/qty/unit/pct/rec_qty/scrap/rec_val keys
      excluded values: dicts with name/qty/unit/pct/scrap/reason keys
    """
    included = defaultdict(list)
    excluded = defaultdict(list)

    for chunk_id, category in STRUCTURE_CHUNKS:
        for comp_name, items in (all_chunks.get(chunk_id) or {}).items():
            for item in items:
                if item.get("state", {}).get("in_trash", False):
                    continue
                values = item.get("values", {})
                state  = item.get("state", {})
                key    = (category, comp_name)

                qty   = float(values.get("quantity",   0) or 0)
                pct   = _recycle_pct(values)
                scrap = float(values.get("scrap_rate", 0) or 0)
                unit  = UNIT_DISPLAY.get(values.get("unit", ""), values.get("unit", ""))
                name  = values.get("material_name", "")

                valid         = pct > 0 and scrap > 0 and qty > 0
                included_flag = state.get("included_in_recyclability", True)

                if valid and included_flag:
                    rec_qty = qty * (pct / 100)
                    included[key].append({
                        "name": name, "qty": qty, "unit": unit,
                        "pct": pct, "rec_qty": rec_qty,
                        "scrap": scrap, "rec_val": rec_qty * scrap,
                    })
                else:
                    reason = "Incomplete Data" if not valid else "Manually Excluded"
                    excluded[key].append({
                        "name": name, "qty": qty, "unit": unit,
                        "pct": pct, "scrap": scrap, "reason": reason,
                    })

    return included, excluded


# ── Structure work table (private) ────────────────────────────────────────────

def _legend(currency: str) -> NoEscape:
    cur = escape_latex(currency)
    return NoEscape(
        r"\par\smallskip\footnotesize"
        rf" All rates and totals in {cur}.\quad"
        r"\textemdash\,Database value (default);\quad"
        r"$^{\#}$\,Manually entered;\quad"
        r"$^{\S}$\,Modified from database;\quad"
        r"$^{\dagger}$\,Imported from Excel;\quad"
        r"$^{\ddagger}$\,Imported from Excel and modified"
    )


def _fmt(val):
    if val is None:
        return _CENTER_DASH
    return f"{val:,.{DECIMAL_PLACES_FOR_LATEX}f}"


def _mat_cell(name: str, source: str):
    mark = _SOURCE_MARK.get(source, "")
    if not name:
        return _CENTER_DASH
    return NoEscape(escape_latex(name) + mark)


def _padded_text(value):
    if not value:
        return _CENTER_DASH
    return NoEscape(r"\hspace{0.35em}" + escape_latex(str(value)))


def _structure_table(chunk: dict, caption: str, label: str, currency: str) -> str:
    headers = ["Material", "Quantity", "Unit", "Rate/Unit", "Rate Source", f"Total ({currency})"]

    table = LongTable(_COL_SPEC)

    table.append(NoEscape(
        r"\caption{" + escape_latex(caption) + r"}"
        r"\label{" + label + r"}\\"
    ))
    table.append(_MIDRULE)
    table.add_row([bold(h) for h in headers])
    table.append(_MIDRULE)
    table.append(NoEscape(r"\endfirsthead"))

    table.add_row([MultiColumn(_N_COLS, align="l",
                               data=italic("Continued from previous page"))])
    table.append(_MIDRULE)
    table.add_row([bold(h) for h in headers])
    table.append(_MIDRULE)
    table.end_table_header()

    table.append(_MIDRULE)
    table.add_row([MultiColumn(_N_COLS, align="r",
                               data=italic("Continued on next page"))])
    table.end_table_footer()

    table.append(_BOTTOMRULE)
    table.end_table_last_footer()

    first = True
    for component_name, items in chunk.items():
        if not first:
            table.append(_MIDRULE)
        first = False

        table.add_row([MultiColumn(_N_COLS, align="l", data=bold(component_name))])
        table.append(_MIDRULE)

        for item in items:
            if item.get("state", {}).get("in_trash"):
                continue
            v      = item.get("values", {})
            source = item.get("meta", {}).get("source", "db")
            qty    = v.get("quantity")
            rate   = v.get("rate")
            total  = (qty * rate) if (qty is not None and rate is not None) else None

            table.add_row([
                _mat_cell(v.get("material_name", ""), source),
                _fmt(qty),
                UNIT_DISPLAY.get(v.get("unit", ""), v.get("unit")) or _CENTER_DASH,
                _fmt(rate),
                _padded_text(v.get("rate_source")),
                _fmt(total),
            ])

    return table.dumps() + "\n" + str(_legend(currency))


# ── Entry point ───────────────────────────────────────────────────────────────

def structure_work_data_to_latex(controller=None) -> str:
    currency   = get_currency()
    all_chunks = get_all_structure_chunks()

    tables = []
    for chunk_id, label in STRUCTURE_CHUNKS:
        captions = {
            "str_foundation":      ("Structure Work Data: Foundation",      "tab:str_foundation"),
            "str_sub_structure":   ("Structure Work Data: Sub-Structure",   "tab:str_sub_structure"),
            "str_super_structure": ("Structure Work Data: Super Structure", "tab:str_super_structure"),
            "str_misc":            ("Structure Work Data: Miscellaneous",   "tab:str_misc"),
        }
        caption, tab_label = captions[chunk_id]
        tables.append(_structure_table(all_chunks[chunk_id], caption, tab_label, currency))

    return "\n\n".join(tables)
