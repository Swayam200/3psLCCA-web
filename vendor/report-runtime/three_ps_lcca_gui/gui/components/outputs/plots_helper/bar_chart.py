"""
gui/components/outputs/plots_helper/bar_chart.py

Standalone bar-chart builder for LCC analysis results.
Exposes create_bar_chart(values, labels, stage_info, text_color, bg_color, currency)
which returns (fig, bars) ready for embedding in a matplotlib canvas.
"""

import os
import numpy as np
import matplotlib
matplotlib.use("QtAgg")
from matplotlib.figure import Figure
from matplotlib import font_manager as _fm

from three_ps_lcca_gui.gui.theme import FONT_FAMILY
from three_ps_lcca_gui.gui.themes import get_token

from .plot_utils import register_ubuntu_fonts

# ── Register Ubuntu fonts ────────────────────────────────────────────────────
register_ubuntu_fonts()
matplotlib.rcParams["font.family"] = FONT_FAMILY


def create_bar_chart(
    values: list,
    labels: list,
    stage_info: list,
    text_color: str,
    bg_color: str,
    currency: str = "INR",
):
    """
    Build and return (fig, bars) from pre-computed LCC chart data.

    Parameters
    ----------
    values     : list of float  - bar heights (in millions of currency)
    labels     : list of str    - x-axis tick labels, one per bar
    stage_info : list of dict   - each dict has keys:
                                  start, end, color, tick_color, title
    text_color : str            - hex color for axes text / labels
    bg_color   : str            - hex color for figure / axes background
    currency   : str            - currency code shown on y-axis label
    """
    _N = len(labels)
    x = np.arange(_N)

    fig_width = max(14, _N * 0.65)
    fig = Figure(figsize=(fig_width, 6))
    ax = fig.add_subplot(111)
    fig.patch.set_facecolor(bg_color)
    ax.set_facecolor(bg_color)
    ax.tick_params(axis='x', colors=text_color, labelsize=6)
    ax.tick_params(axis='y', colors=text_color, labelsize=7)
    ax.yaxis.label.set_color(text_color)
    
    for spine in ax.spines.values():
        spine.set_edgecolor(text_color)
        spine.set_linewidth(1.0)

    # Stage background panels
    for stage in stage_info:
        ax.axvspan(
            stage["start"] - 0.5, stage["end"] + 0.5,
            color=stage["color"], alpha=0.9,
        )

    # Bars- red for costs, green for savings/negatives
    bar_colors = ["#8b1a1a" if v >= 0 else "#2e7d32" for v in values]
    bars = ax.bar(x, values, 0.50, color=bar_colors)

    # Stage dividers and titles
    for stage in stage_info[1:]:
        ax.axvline(stage["start"] - 0.5, color="black", linewidth=1.5)
    ax.axhline(0, color="black", linewidth=0.8)

    for stage in stage_info:
        center = (stage["start"] + stage["end"]) / 2
        ax.text(
            center, 1.02, stage["title"],
            transform=ax.get_xaxis_transform(),
            ha="center", va="bottom", fontsize=8, fontweight="bold",
            color=text_color,
        )

    # ── Grand Total at Top ────────────────────────────────────────────────
    total_lcca = sum(values)
    ax.text(
        0.5, 1.12,
        f"Total Life cycle cost (year): {total_lcca:,.2f} Million {currency}",
        transform=ax.transAxes,
        ha="center", va="bottom",
        fontsize=12, fontweight="bold",
        bbox=dict(
            facecolor=bg_color,
            edgecolor=get_token("primary"),
            boxstyle="round,pad=0.6",
            alpha=0.15,
            linewidth=1.5
        ),
        color=text_color,
    )

    # Y-axis limits with generous padding for rotated bar labels
    max_val = float(max(values))
    min_val = float(min(values))

    v_range = max_val - min_val
    if v_range == 0:
        v_range = abs(max_val) if max_val != 0 else 1.0

    padding = v_range * 0.35
    ylim_top = max_val + padding
    ylim_bot = min_val - padding

    if ylim_top < 1.0:
        ylim_top = 1.0
    if ylim_bot > -1.0:
        ylim_bot = -1.0

    ax.set_ylim(ylim_bot, ylim_top)

    # Value labels above / below each bar (rotated)
    offset = v_range * 0.02
    for bar, val in zip(bars, values):
        if abs(val) < 1e-9:
            lbl = "0"
        else:
            lbl = f"{val:.2f}"

        y_pos = val + offset if val >= 0 else val - offset
        ax.text(
            bar.get_x() + bar.get_width() / 2, y_pos, lbl,
            ha="center", va="bottom" if val >= 0 else "top",
            rotation=90, fontsize=7,
            color=bar.get_facecolor(), fontweight="bold",
        )

    # Axes styling
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(True)
    ax.spines["bottom"].set_visible(True)
    ax.spines["left"].set_edgecolor(text_color)
    ax.spines["bottom"].set_edgecolor(text_color)
    
    ax.set_xticks(x)

    wrapped = [
        lbl.replace(" (", "\n(") if len(lbl) > 22 else lbl
        for lbl in labels
    ]
    ax.set_xticklabels(wrapped, rotation=90, fontsize=6, color=text_color)
    ax.set_ylabel(f"Cost (Million {currency})", fontsize=8, color=text_color)
    ax.tick_params(axis="y", labelsize=7, colors=text_color)
    ax.tick_params(axis="x", colors=text_color)
    ax.grid(axis="y", linestyle="--", alpha=0.35)
    ax.set_xlim(-0.5, _N - 0.5)

    # Per-tick text colour driven by stage metadata
    tick_color_map = {
        i: s["tick_color"]
        for s in stage_info
        for i in range(s["start"], s["end"] + 1)
    }
    for i, tick_lbl in enumerate(ax.get_xticklabels()):
        tick_lbl.set_color(tick_color_map.get(i, text_color))

    fig.subplots_adjust(bottom=0.40, top=0.82)
    return fig, bars
