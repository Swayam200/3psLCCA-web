"""
report/plot_exporter.py

Static (print-ready) chart generation for the LCCA PDF report.

Each function produces a white-background matplotlib Figure with permanent,
compact labels matching the visible GUI chart labels, so the PNG is fully
self-explanatory without interactivity.

PNGs are created via tempfile.mkstemp inside output_dir so pdflatex can resolve
them by basename alone (it runs from that same directory).
"""

import concurrent.futures
import contextlib
import os
import tempfile

import matplotlib
matplotlib.use('Agg')
import matplotlib.ticker
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.patches import Patch

from ..gui.components.outputs.plots_helper.Pie import (
    _build_pillar_data,
    _build_nested_pie_data,
    _pillar_totals_ok,
    _nested_data_ok,
    SimplePillarPlotter,
    SustainabilityCircularPlotter,
    COLORS as _PIE_COLORS,
)
from ..gui.components.outputs.plots_helper.AggregateChart import (
    _build_stage_data,
    _build_pillar_data as _build_agg_pillar_data,
    StageBarPlotter,
    SustainabilityBarPlotter,
    STAGE_COLORS,
    PILLAR_COLORS,
)
from ..gui.components.utils.display_format import fmt_currency
from .constants import (
    KEY_PLOT_PILLAR_DONUT,
    KEY_PLOT_SUSTAINABILITY_MATRIX,
    KEY_PLOT_STAGE_BARS,
    KEY_PLOT_PILLAR_BARS,
)

# ── Print palette (dark text, white background) ───────────────────────────────
_TC  = "#1a1a1a"   # primary text
_TC2 = "#555555"   # secondary text
_GC  = "#cccccc"   # grid / separator
_BG  = "white"
_DPI = 150

# tempfile prefix per plot type
_PREFIXES = {
    KEY_PLOT_PILLAR_DONUT:          "lcca_plot_pillar_donut_",
    KEY_PLOT_SUSTAINABILITY_MATRIX: "lcca_plot_sustainability_matrix_",
    KEY_PLOT_STAGE_BARS:            "lcca_plot_stage_bars_",
    KEY_PLOT_PILLAR_BARS:           "lcca_plot_pillar_bars_",
}


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _save(fig: plt.Figure, fd: int, path: str) -> None:
    os.close(fd)
    fig.savefig(path, dpi=_DPI, bbox_inches="tight")
    plt.close(fig)


def _make_temp(key: str, output_dir: str) -> tuple:
    return tempfile.mkstemp(suffix=".png", prefix=_PREFIXES[key], dir=output_dir)


def _fmt_plot_value(value: float, currency: str) -> str:
    return fmt_currency(value, currency, decimals=0, style="short")


def _add_currency_note(fig: Figure, currency: str) -> None:
    fig.text(0.98, 0.97, f"All values in {currency}",
             ha="right", va="top", fontsize=8, color=_TC2, alpha=0.85)


def _setup_y_formatter(ax, currency: str) -> None:
    ax.yaxis.set_major_formatter(
        matplotlib.ticker.FuncFormatter(
            lambda value, _: _fmt_plot_value(value, currency)
        )
    )


def _annotate_wedge(ax, wedge, label: str, val: float, total: float,
                    currency: str, r_tip: float, r_text: float,
                    min_span_deg: float = 8.0) -> None:
    """Draw a leader-line annotation from the centre of a pie wedge outward.

    Shows the same compact visible label style used by the GUI charts.
    Skips wedges narrower than *min_span_deg* degrees to avoid crowding.
    """
    span = abs(wedge.theta2 - wedge.theta1)
    if span < min_span_deg or val <= 0:
        return
    mid_rad = np.radians((wedge.theta1 + wedge.theta2) / 2)
    cos_m, sin_m = np.cos(mid_rad), np.sin(mid_rad)
    txt = f"{label}\n{_fmt_plot_value(val, currency)}"
    ax.annotate(
        txt,
        xy=(r_tip * cos_m, r_tip * sin_m),
        xytext=(r_text * cos_m, r_text * sin_m),
        ha="center", va="center",
        fontsize=8.5, color=_TC,
        arrowprops=dict(arrowstyle="-", color=_GC, lw=0.7),
        bbox=dict(boxstyle="round,pad=0.28", fc=_BG, ec=_GC, alpha=0.96),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Plot 1 - Pillar distribution donut
# ─────────────────────────────────────────────────────────────────────────────

def _plot_pillar_donut(results: dict, currency: str) -> plt.Figure:
    items  = _build_pillar_data(results)   # [(label, raw_value, color), ...]
    labels = [i[0] for i in items]
    values = [i[1] for i in items]
    colors = [i[2] for i in items]
    total  = sum(values) or 1.0

    fig = Figure(figsize=(9, 7))
    ax = fig.add_subplot(111)
    fig.patch.set_facecolor(_BG)
    ax.set_facecolor(_BG)
    ax.set_aspect("equal")
    fig.subplots_adjust(left=0.05, right=0.95, bottom=0.08, top=0.92)

    wedges, _ = ax.pie(
        values, radius=1.05, colors=colors,
        wedgeprops={"width": 0.42, "edgecolor": _BG, "linewidth": 1.5},
    )

    # Centre: total value (same text as GUI centre_text)
    ax.text(0, 0,
            f"Total\n{_fmt_plot_value(total, currency)}",
            ha="center", va="center", fontsize=8.5,
            fontweight="bold", color=_TC)

    # Annotate each wedge with the compact visible GUI label style.
    for wedge, label, val in zip(wedges, labels, values):
        _annotate_wedge(ax, wedge, label, val, total, currency,
                        r_tip=0.84, r_text=1.55, min_span_deg=5.0)

    ax.set_xlim(-2.5, 2.5)
    ax.set_ylim(-2.2, 2.2)
    ax.axis("off")

    # Legend so even tiny wedges are identified
    ax.legend(
        handles=[Patch(facecolor=c, label=l) for l, c in zip(labels, colors)],
        loc="lower center", bbox_to_anchor=(0.5, -0.04),
        ncol=len(labels), frameon=False, fontsize=8, labelcolor=_TC,
    )
    ax.set_title("Pillar Distribution- Economic : Environmental : Social",
                 fontsize=10, fontweight="bold", color=_TC, pad=8)
    _add_currency_note(fig, currency)
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# Plot 2 - Sustainability matrix (nested stage+pillar donut)
# ─────────────────────────────────────────────────────────────────────────────

def _plot_sustainability_matrix(results: dict, currency: str) -> plt.Figure:
    data = _build_nested_pie_data(results)

    inner_vals, inner_colors, inner_labels = [], [], []
    outer_vals, outer_colors, outer_labels = [], [], []
    for entry in data:
        stage_total = sum(p[1] for p in entry["pillars"])
        inner_vals.append(stage_total)
        inner_labels.append(entry["stage"])
        inner_colors.append(_PIE_COLORS["stages"].get(entry["stage"], "#DDDDDD"))
        for name, val, color in entry["pillars"]:
            outer_vals.append(val)
            outer_labels.append(f"{entry['stage']}- {name}")
            outer_colors.append(color)

    total = sum(inner_vals) or 1.0

    fig = Figure(figsize=(9, 7))
    ax = fig.add_subplot(111)
    fig.patch.set_facecolor(_BG)
    ax.set_facecolor(_BG)
    ax.set_aspect("equal")
    fig.subplots_adjust(left=0.02, right=0.98, bottom=0.08, top=0.92)

    # inner ring: r = 0.5 → 0.8  (width 0.30, radius 0.8)
    inner_wedges, _ = ax.pie(
    inner_vals, radius=1.0, colors=inner_colors,
    wedgeprops={"width": 0.35, "edgecolor": _BG, "linewidth": 1.5},
)
    # outer ring: r = 0.8 → 1.1  (width 0.30, radius 1.1)
    outer_wedges, _ = ax.pie(
    outer_vals, radius=1.40, colors=outer_colors,
    wedgeprops={"width": 0.35, "edgecolor": _BG, "linewidth": 1.5},
)

    # Stage boundary separator lines
    angles = np.cumsum(inner_vals) / total * 2 * np.pi
    for angle in angles:
        ax.plot(
            [0.65 * np.cos(angle), 1.40 * np.cos(angle)],
            [0.65 * np.sin(angle), 1.40 * np.sin(angle)],
            color=_GC, lw=1.2,
        )

    ax.text(0, 0, f"Total\n{_fmt_plot_value(total, currency)}",
            ha="center", va="center", fontsize=8.5,
            fontweight="bold", color=_TC)

    # Outer pillar labels with dot + orthogonal leader lines.
    label_entries = []
    for wedge, label, val in zip(outer_wedges, outer_labels, outer_vals):
        if val <= 0:
            continue
        mid_rad = np.radians((wedge.theta1 + wedge.theta2) / 2)
        cos_m, sin_m = np.cos(mid_rad), np.sin(mid_rad)
        pillar = label.split("- ", 1)[1] if "- " in label else label
        label_entries.append({
            "side": "right" if cos_m >= 0 else "left",
            "x0": 1.40 * cos_m,
            "y0": 1.40 * sin_m,
            "y": 1.45 * sin_m,
            "pillar": pillar,
            "value": _fmt_plot_value(val, currency),
        })

    def _spread(entries):
        entries = sorted(entries, key=lambda e: e["y"], reverse=True)
        min_gap = 0.30
        for _ in range(80):
            moved = False
            for j in range(len(entries) - 1):
                gap = entries[j]["y"] - entries[j + 1]["y"]
                if gap < min_gap:
                    shift = (min_gap - gap) / 2
                    entries[j]["y"] += shift
                    entries[j + 1]["y"] -= shift
                    moved = True
            if not moved:
                break
        return entries

    for side, x_text, x_elbow, ha in (
        ("right", 2.05, 1.62, "left"),
        ("left", -2.05, -1.62, "right"),
    ):
        for entry in _spread([e for e in label_entries if e["side"] == side]):
            x_end = x_text - 0.08 if side == "right" else x_text + 0.08
            ax.plot(
                [entry["x0"], x_elbow, x_elbow, x_end],
                [entry["y0"], entry["y0"], entry["y"], entry["y"]],
                color=_TC2, lw=0.9, solid_capstyle="round",
            )
            ax.plot(entry["x0"], entry["y0"], "o",
                    color=_TC2, markersize=3.0)
            ax.text(x_text, entry["y"] + 0.07, entry["pillar"],
                    ha=ha, va="center", fontsize=9,
                    fontweight="bold", color=_TC)
            ax.text(x_text, entry["y"] - 0.08, entry["value"],
                    ha=ha, va="center", fontsize=8.5, color=_TC2)

    ax.set_xlim(-2.6, 2.6)
    ax.set_ylim(-2.4, 2.4)
    ax.axis("off")

    # Combined legend
    stage_handles  = [Patch(facecolor=_PIE_COLORS["stages"].get(l, "#AAA"), label=l)
                      for l in inner_labels]
    pillar_handles = [Patch(facecolor=c, label=p)
                      for p, c in _PIE_COLORS["pillars"].items()]
    ax.legend(
        handles=stage_handles + pillar_handles,
        loc="lower center", bbox_to_anchor=(0.5, -0.03),
        ncol=len(stage_handles) + len(pillar_handles),
        frameon=False, fontsize=9, labelcolor=_TC,
    )
    ax.set_title("Sustainability Matrix- Stage and Pillar Decomposition",
                 fontsize=10, fontweight="bold", color=_TC, pad=8)
    _add_currency_note(fig, currency)
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# Plot 3 - Stage-wise bars
# ─────────────────────────────────────────────────────────────────────────────

def _plot_stage_bars(results: dict, currency: str) -> plt.Figure:
    """Stage bar chart with the same compact visible labels as the GUI."""
    data   = _build_stage_data(results)    # [(label, raw_value, color), ...]
    labels = [d[0] for d in data]
    values = [d[1] for d in data]
    colors = [d[2] for d in data]

    fig = Figure(figsize=(9, 6))
    ax = fig.add_subplot(111)
    fig.patch.set_facecolor(_BG)
    ax.set_facecolor(_BG)
    fig.subplots_adjust(left=0.10, right=0.75, bottom=0.15, top=0.90)

    x    = np.arange(len(labels))
    bars = ax.bar(x, values, color=colors, edgecolor="none", width=0.5)

    max_v  = max(values) if values else 1.0
    min_v  = min(values) if values else 0.0
    pad    = (max_v - min_v) * 0.12 or 1.0

    for i, val in enumerate(values):
        label_text = _fmt_plot_value(val, currency)
        if val >= 0:
            ax.text(i, val + pad * 0.10, label_text,
                    ha="center", va="bottom",
                    fontsize=7.5, fontweight="bold", color=_TC)
        else:
            ax.text(i, val - pad * 0.10, label_text,
                    ha="center", va="top",
                    fontsize=7.5, fontweight="bold", color=_TC)

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontweight="bold", color=_TC, fontsize=9)
    ax.set_ylabel("Cost",
                  fontweight="bold", color=_TC, fontsize=9)
    ax.tick_params(axis="both", colors=_TC, labelsize=8)
    ax.yaxis.grid(True, linestyle="--", alpha=0.3, color=_GC)
    ax.set_axisbelow(True)
    if values:
        ax.set_ylim(min(0, min_v) - pad, max(0, max_v) + pad * 2.0)

    for s in ax.spines.values():
        s.set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_visible(True)
        ax.spines[spine].set_edgecolor(_TC)
        ax.spines[spine].set_linewidth(0.8)

    ax.legend(
        handles=[Patch(facecolor=c, label=l) for l, c in zip(labels, colors)],
        title="Life Cycle Stages", loc="center left", bbox_to_anchor=(1.02, 0.5),
        frameon=False, fontsize=8, title_fontsize=9, labelcolor=_TC,
    )
    plt.setp(ax.get_legend().get_title(), color=_TC)
    ax.set_title("Life Cycle Disaggregation- Stage-wise Cost",
                 fontsize=10, fontweight="bold", color=_TC, pad=8)
    _add_currency_note(fig, currency)
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# Plot 4 - Pillar-wise stacked bars
# ─────────────────────────────────────────────────────────────────────────────

def _plot_pillar_bars(results: dict, currency: str) -> plt.Figure:
    """Stacked pillar bar chart with compact per-segment value labels."""
    data       = _build_agg_pillar_data(results)
    stages     = [d["stage"] for d in data]
    categories = ["Economic", "Environmental", "Social"]
    values     = {
        cat: [next((p[1] for p in d["pillars"] if p[0] == cat), 0.0) for d in data]
        for cat in categories
    }

    fig = Figure(figsize=(9, 6))
    ax = fig.add_subplot(111)
    fig.patch.set_facecolor(_BG)
    ax.set_facecolor(_BG)
    fig.subplots_adjust(left=0.10, right=0.75, bottom=0.15, top=0.90)

    x          = np.arange(len(stages))
    pos_bottom = np.zeros(len(stages))
    neg_bottom = np.zeros(len(stages))

    for cat in categories:
        vals     = np.array(values[cat])
        pos_vals = np.where(vals > 0, vals, 0.0)
        neg_vals = np.where(vals < 0, vals, 0.0)

        for sign_vals, bottom_arr in ((pos_vals, pos_bottom), (neg_vals, neg_bottom)):
            if not sign_vals.any():
                continue
            ax.bar(x, sign_vals, bottom=bottom_arr,
                   color=PILLAR_COLORS[cat], edgecolor="none", width=0.5)

            # Per-segment label matching the compact visible GUI style.
            for i, (seg_val, bot) in enumerate(zip(sign_vals, bottom_arr)):
                if abs(seg_val) < 1e-6:
                    continue
                mid_y = bot + seg_val / 2
                label_text = f"{cat}\n{_fmt_plot_value(seg_val, currency)}"
                # Only annotate if segment is tall enough to read
                seg_height = abs(seg_val)
                if seg_height > (max(pos_bottom.max(), abs(neg_bottom.min()), 0.1) * 0.06):
                    ax.text(i, mid_y, label_text,
                            ha="center", va="center",
                            fontsize=5.5, color=_TC,
                            bbox=dict(boxstyle="round,pad=0.15",
                                      fc=_BG, ec="none", alpha=0.75))

            if sign_vals is pos_vals:
                pos_bottom += pos_vals
            else:
                neg_bottom += neg_vals

    y_max = float(pos_bottom.max()) if pos_bottom.any() else 0.0
    y_min = float(neg_bottom.min()) if neg_bottom.any() else 0.0
    pad   = (y_max - y_min) * 0.12 or 1.0

    # Total value above / below the full stack
    for i in range(len(stages)):
        if pos_bottom[i] > 0:
            ax.text(i, pos_bottom[i] + pad * 0.12,
                    f"Total\n{_fmt_plot_value(pos_bottom[i], currency)}",
                    ha="center", va="bottom",
                    fontsize=7.5, fontweight="bold", color=_TC)
        if neg_bottom[i] < 0:
            ax.text(i, neg_bottom[i] - pad * 0.12,
                    f"Total\n{_fmt_plot_value(neg_bottom[i], currency)}",
                    ha="center", va="top",
                    fontsize=7.5, fontweight="bold", color=_TC)

    ax.set_xticks(x)
    ax.set_xticklabels(stages, fontweight="bold", color=_TC, fontsize=9)
    ax.set_ylabel("Cost",
                  fontweight="bold", color=_TC, fontsize=9)
    ax.tick_params(axis="both", colors=_TC, labelsize=8)
    ax.yaxis.grid(True, linestyle="--", alpha=0.3, color=_GC)
    ax.set_axisbelow(True)
    ax.set_ylim(min(0, y_min) - pad, max(0, y_max) + pad * 2.5)

    for s in ax.spines.values():
        s.set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_visible(True)
        ax.spines[spine].set_edgecolor(_TC)
        ax.spines[spine].set_linewidth(0.8)

    ax.legend(
        handles=[Patch(facecolor=PILLAR_COLORS[c], label=c) for c in categories],
        title="Sustainability Pillars", loc="center left", bbox_to_anchor=(1.02, 0.5),
        frameon=False, fontsize=8, title_fontsize=9, labelcolor=_TC,
    )
    plt.setp(ax.get_legend().get_title(), color=_TC)
    ax.set_title("Life Cycle Disaggregation- Pillar-wise Stacked Bars",
                 fontsize=10, fontweight="bold", color=_TC, pad=8)
    _add_currency_note(fig, currency)
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────

def generate_plots(results: dict, output_dir: str, currency: str = "INR") -> dict:
    """Generate all four report chart PNGs into output_dir via tempfile.

    Returns {KEY_PLOT_*: basename} for every plot that was successfully saved.
    The basename is what goes into \\includegraphics- pdflatex resolves it
    because it runs from the same directory.
    """
    os.makedirs(output_dir, exist_ok=True)
    out = {}

    _jobs = [
        (KEY_PLOT_PILLAR_DONUT,
         lambda: _pillar_totals_ok(results) and bool(_build_pillar_data(results)),
         lambda: SimplePillarPlotter(results, currency).setup_plot()),
        (KEY_PLOT_SUSTAINABILITY_MATRIX,
         lambda: _nested_data_ok(results) and bool(_build_nested_pie_data(results)),
         lambda: SustainabilityCircularPlotter(_build_nested_pie_data(results), currency).setup_plot()),
        (KEY_PLOT_STAGE_BARS,
         lambda: bool(_build_stage_data(results)),
         lambda: StageBarPlotter(_build_stage_data(results), currency).setup_plot()),
        (KEY_PLOT_PILLAR_BARS,
         lambda: bool(_build_agg_pillar_data(results)),
         lambda: SustainabilityBarPlotter(_build_agg_pillar_data(results), currency).setup_plot()),
    ]

    def _run_job(job):
        key, guard, builder = job
        try:
            if not guard():
                return key, None
            fig = builder()
            # Force white background regardless of theme
            fig.patch.set_facecolor("white")
            fig.patch.set_alpha(1.0)
            for ax in fig.get_axes():
                ax.set_facecolor("none")
            fd, path = _make_temp(key, output_dir)
            _save(fig, fd, path)
            return key, os.path.basename(path)
        except Exception as e:
            print(f"[plot_exporter] {key} failed: {e}")
            return key, None

    # Temporarily override theme tokens so plotters render with print-safe
    # dark text regardless of whether the app is in dark mode.
    from ..gui import themes as _themes
    _PRINT_TOKENS = {"text": "#1a1a1a", "surface_mid": "#cccccc",
                     "text_secondary": "#555555", "text_disabled": "#888888"}
    _themes._ensure_tokens()
    _saved = {k: _themes._active_tokens.get(k) for k in _PRINT_TOKENS}
    _themes._active_tokens.update(_PRINT_TOKENS)
    try:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            for key, basename in executor.map(_run_job, _jobs):
                if basename:
                    out[key] = basename
    finally:
        for k, v in _saved.items():
            if v is None:
                _themes._active_tokens.pop(k, None)
            else:
                _themes._active_tokens[k] = v

    return out
