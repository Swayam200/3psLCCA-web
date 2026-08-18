from pylatex import LongTable, MultiColumn, NoEscape
from pylatex.utils import bold, escape_latex
from ..gui.components.outputs.lcc_data import _MASTER_ROWS, _CREDIT_KEYS, _get, stage_totals
from ..gui.components.utils.common_requested_data import get_currency
from .SETTINGS import DECIMAL_PLACES_FOR_LATEX

_N_COLS  = 2
_COL_SPEC = "p{12cm}r"

_CAT_LABELS = {
    "economic":      "Economic",
    "environmental": "Environmental",
    "social":        "Social",
}


def _fmt(val: float) -> str:
    return f"{val:,.{DECIMAL_PLACES_FOR_LATEX}f}"


def _bold_val(val: float) -> NoEscape:
    return NoEscape(r"\textbf{" + _fmt(val) + r"}")


def _stage_header(title: str) -> NoEscape:
    return NoEscape(
        MultiColumn(_N_COLS, align="l", data=bold(title)).dumps() + r" \\"
    )


def _cat_header(cat: str) -> NoEscape:
    label = escape_latex(_CAT_LABELS.get(cat, cat))
    return NoEscape(
        MultiColumn(_N_COLS, align="l",
                    data=NoEscape(r"\quad\textit{" + label + r"}")).dumps() + r" \\"
    )


def _item_row(label: str, cat: str, val: float) -> list:
    return [
        NoEscape(r"\hangindent=2em\hangafter=1 \quad\quad " + escape_latex(label)),
        _fmt(val),
    ]


def _stage_has_data(results: dict, result_key: str) -> bool:
    """Mirror lcc_plot LCCDetailsTable: a stage is shown only if stage_totals() is non-empty.

    Reconstruction is additionally gated by whether its economic data is a dict
    (mirrors the BREAKDOWN_STAGES optional check in lcc_plot._build).
    """
    if result_key == "reconstruction":
        stage_data = results.get("reconstruction", {})
        if not isinstance(stage_data.get("economic"), dict):
            return False
        # Also skip if all values are zero
        rows = [(cat, key) for sk, cat, key, _ in _MASTER_ROWS if sk == "reconstruction"]
        if all(_get(results, "reconstruction", cat, key) == 0.0 for cat, key in rows):
            return False
        return True

    # For other stages, mirror LCCDetailsTable: skip if stage_totals() is empty.
    # Build cat_keys exactly as STAGE_DEFS does (capitalised category names).
    cat_keys: dict = {}
    for row_sk, cat, key, *_ in _MASTER_ROWS:
        if row_sk != result_key:
            continue
        cat_keys.setdefault(cat.capitalize(), []).append(key)
    totals = stage_totals(results, result_key, cat_keys)
    return bool(totals)


def results_to_latex(controller) -> str:
    cache = (controller.get_chunk("comparison_cache") or {}) if controller else {}
    if not cache.get("is_valid"):
        return ""

    results  = cache.get("results", {})
    currency_val = cache.get("currency")
    if not currency_val or currency_val == "Currency":
        currency_val = get_currency()
    currency = escape_latex(currency_val)

    # Mirror lcc_plot: reconstruction only shown when its economic data is a real dict
    # and at least some values are non-zero.
    has_recon = _stage_has_data(results, "reconstruction")

    table = LongTable(_COL_SPEC)

    # ── Caption (inside longtable so it repeats on continued pages) ───────────
    table.append(NoEscape(r"\caption{Life Cycle Cost Analysis Results} "
                          r"\label{tab:lcca_results} \\"))

    # ── Repeating header ──────────────────────────────────────────────────────
    table.append(NoEscape(r"\toprule"))
    table.add_row(["Description", f"Present Value ({currency})"])
    table.append(NoEscape(r"\midrule"))
    table.append(NoEscape(r"\endhead"))

    # ── Continued footer (every page except last) ─────────────────────────────
    table.append(NoEscape(r"\midrule"))
    table.append(NoEscape(
        rf"\multicolumn{{{_N_COLS}}}{{r}}{{\footnotesize\textit{{continued on next page}}}} \\"
    ))
    table.append(NoEscape(r"\endfoot"))

    # ── Last footer ───────────────────────────────────────────────────────────
    table.append(NoEscape(r"\bottomrule"))
    table.append(NoEscape(r"\endlastfoot"))

    # ── Data rows ─────────────────────────────────────────────────────────────
    # Mirrors LCCDetailsTable._build_data():
    #   - Iterate initial_stage → use_stage → end_of_life (reconstruction never
    #     gets its own row; it is folded into end_of_life when it exists).
    #   - Skip any stage whose totals are empty / all-zero.
    #   - When reconstruction exists, its rows are emitted first inside the
    #     End-of-Life block, prefixed with "Reconstruction | <label>".
    grand_total = 0.0
    first_stage = True

    report_stages = [
        ("initial_stage", "Initial Stage"),
        ("use_stage",     "Use Stage"),
        ("end_of_life",   "End-of-Life Stage"),
    ]

    for sk, chart_title in report_stages:

        # Skip this stage if it carries no data (mirrors `if not totals: continue`)
        if not _stage_has_data(results, sk):
            continue

        if not first_stage:
            table.append(NoEscape(r"\midrule"))
        first_stage = False

        table.append(_stage_header(chart_title))
        table.append(NoEscape(r"\midrule"))

        # Build the ordered list of (source_stage, cat, key, label) rows for
        # this block.  Reconstruction rows are prepended to end_of_life (when
        # they exist), exactly as lcc_plot prefixes them with "Reconstruction |".
        source_stages: list[str] = []
        if sk == "end_of_life" and has_recon:
            source_stages.append("reconstruction")
        source_stages.append(sk)

        stage_rows = [
            (s, cat, key, lbl)
            for s, cat, key, lbl in _MASTER_ROWS
            if s in source_stages
        ]
        # Preserve the order: reconstruction rows first, then end_of_life rows
        # (_MASTER_ROWS already lists reconstruction before end_of_life, so the
        # filter above maintains that order as long as we keep list ordering).

        current_cat = None
        stage_total = 0.0

        for source_sk, cat, key, label in stage_rows:
            if cat != current_cat:
                table.append(_cat_header(cat))
                current_cat = cat

            val = _get(results, source_sk, cat, key)
            display_val = -val if key in _CREDIT_KEYS else val
            stage_total += display_val
            grand_total += display_val

            # Prefix reconstruction rows so they are visually distinguished
            # inside the End-of-Life block (mirrors lcc_plot "Reconstruction | …")
            if source_sk == "reconstruction":
                label = f"Reconstruction | {label}"

            table.add_row(_item_row(label, cat, display_val))

        table.append(NoEscape(r"\cmidrule(l){1-2}"))
        table.add_row([bold(f"Stage Total — {chart_title}"), _bold_val(stage_total)])

    # ── Grand total ───────────────────────────────────────────────────────────
    table.append(NoEscape(r"\midrule"))
    table.add_row([bold("Total life cycle cost"), _bold_val(grand_total)])

    return table.dumps()
