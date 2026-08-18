"""
gui/components/outputs/plots_helper/AggregateChart.py

Two-view bar chart widget:
  Default  - Stage-wise bars  (Initial / Use+Rec / End-of-Life, solid colours)
  Checkbox - Pillar-wise bars (stacked Economic / Environmental / Social per stage)
"""

import os
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.ticker
import numpy as np
from matplotlib.figure import Figure
from matplotlib.patches import Patch
from matplotlib import font_manager as _fm

matplotlib.use("QtAgg")

try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
except ImportError:
    from matplotlib.backends.backend_qt import FigureCanvasQTAgg

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QBoxLayout,
    QCheckBox,
    QLabel,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
    QFrame,
    QScrollArea,
)

from three_ps_lcca_gui.gui.theme import (
    FONT_FAMILY,
    FS_SM, FS_BASE, FS_LG, FS_SUBHEAD, FS_XS, FS_MD,
    FW_NORMAL, FW_BOLD,
    SP2, SP4, SP6, RADIUS_LG, RADIUS_XL,
)
from three_ps_lcca_gui.gui.themes import get_token
from three_ps_lcca_gui.gui.styles import font as _f
from three_ps_lcca_gui.gui.components.utils.display_format import fmt_currency
from ..helper_functions.lifecycle_summary import compute_all_summaries
from ..helper_functions.ratio_helper import format_ratio_string
from ..helper_functions.lcc_colors import COLORS as LCC_COLORS
from .plot_utils import register_ubuntu_fonts, WheelForwarder, ChartToolbar, currency_note

# ── Register Ubuntu fonts ────────────────────────────────────────────────────
register_ubuntu_fonts()
matplotlib.rcParams["font.family"] = FONT_FAMILY

# ─────────────────────────────────────────────────────────────────────────────
# COLORS
# ─────────────────────────────────────────────────────────────────────────────

STAGE_COLORS = {
    "Initial":     "#CCCCCC",
    "Use":         "#00C49A",
    "End-of-Life": "#EA9E9E",
}

PILLAR_COLORS = {
    "Economic":      LCC_COLORS["eco_color"],
    "Environmental": LCC_COLORS["env_color"],
    "Social":        LCC_COLORS["soc_color"],
}

# ─────────────────────────────────────────────────────────────────────────────
# DATA HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _build_stage_data(results: dict) -> list:
    """[(label, raw_value, color), ...]- one entry per stage."""
    st = compute_all_summaries(results).get("stagewise", {})
    mapping = [
        ("initial",     "Initial",     STAGE_COLORS["Initial"]),
        ("use",         "Use",         STAGE_COLORS["Use"]),
        ("end_of_life", "End-of-Life", STAGE_COLORS["End-of-Life"]),
    ]
    return [(label, st.get(key, 0), color)
            for key, label, color in mapping if st.get(key, 0) != 0]


def _build_pillar_total_data(results: dict) -> list:
    """[(label, raw_value, color), ...]- one bar per pillar total (negatives included)."""
    pt = compute_all_summaries(results).get("pillar_totals", {})
    rows = [
        ("Economic",      pt.get("eco",    0), PILLAR_COLORS["Economic"]),
        ("Environmental", pt.get("env",    0), PILLAR_COLORS["Environmental"]),
        ("Social",        pt.get("social", 0), PILLAR_COLORS["Social"]),
    ]
    return [(l, v, c) for l, v, c in rows if v != 0]


def _build_pillar_data(results: dict) -> list:
    """[{"stage": label, "pillars": [(name, raw_value), ...]}, ...]- pillar stacked."""
    pw = compute_all_summaries(results).get("pillar_wise", {})
    mapping = [
        ("initial",     "Initial"),
        ("use",         "Use"),
        ("end_of_life", "End-of-Life"),
    ]
    data = []
    for key, label in mapping:
        p = pw.get(key, {})
        if not p or all(v == 0 for v in p.values()):
            continue
        data.append({
            "stage": label,
            "pillars": [
                ("Economic",      p.get("eco",    0)),
                ("Environmental", p.get("env",    0)),
                ("Social",        p.get("social", 0)),
            ],
        })
    return data


# ─────────────────────────────────────────────────────────────────────────────
# SHARED HELPERS
# ─────────────────────────────────────────────────────────────────────────────

class _BasePlotter:
    def __init__(self, currency: str):
        self.currency = currency
        self.fig = Figure(figsize=(9, 6))
        self.fig.patch.set_alpha(0.0)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor("none")
        self.fig.subplots_adjust(left=0.18, right=0.75, bottom=0.15, top=0.9)
        self.fig.canvas.mpl_connect("motion_notify_event", self._hover)

    def _hover(self, event):
        if event.inaxes != self.ax or not hasattr(self, "annot"):
            return
        
        info = self._get_hover_info(event)
        if info:
            text, xy = info
            self.annot.set_text(text)
            self.annot.xy = xy
            self.annot.set_visible(True)
        else:
            self.annot.set_visible(False)
        self.fig.canvas.draw_idle()

    def _get_hover_info(self, event):
        """To be implemented by subclasses. Returns (text, xy) or None."""
        return None

    def _setup_spines(self, tc):
        for s in self.ax.spines.values():
            s.set_visible(False)
        for spine in ("left", "bottom"):
            self.ax.spines[spine].set_visible(True)
            self.ax.spines[spine].set_edgecolor(tc)
            self.ax.spines[spine].set_linewidth(0.8)

    def _setup_annotation(self, tc):
        self.annot = self.ax.annotate(
            "", xy=(0, 0), xytext=(15, 15), textcoords="offset points",
            bbox=dict(boxstyle="round,pad=0.5", fc=get_token("base"),
                      ec=get_token("surface_mid"), alpha=0.9),
            zorder=10, fontweight="bold", color=tc, fontsize=8,
        )
        self.annot.set_visible(False)

    def _make_legend(self, handles, title, tc):
        leg = self.ax.legend(
            handles=handles, title=title,
            loc="center left", bbox_to_anchor=(1.02, 0.5),
            frameon=False, fontsize=8, title_fontsize=9, labelcolor=tc,
        )
        plt.setp(leg.get_title(), color=tc)

    def _setup_axes_style(self, tc, gc, x, xlabels, ylabel):
        self.ax.set_xticks(x)
        self.ax.set_xticklabels(xlabels, fontweight="bold", color=tc, fontsize=9)
        self.ax.set_ylabel(ylabel, fontweight="bold", color=tc, fontsize=9)
        self.ax.tick_params(axis="both", colors=tc, labelsize=8)
        self.ax.yaxis.grid(True, linestyle="--", alpha=0.3, color=gc)
        self.ax.set_axisbelow(True)

    def _setup_y_formatter(self):
        self.ax.yaxis.set_major_formatter(
            matplotlib.ticker.FuncFormatter(
                lambda v, _: fmt_currency(v, self.currency, decimals=0, style="short")
            )
        )


# ─────────────────────────────────────────────────────────────────────────────
# CHART 0 - Stage-wise bars  (default)
# ─────────────────────────────────────────────────────────────────────────────

class StageBarPlotter(_BasePlotter):
    def __init__(self, data: list, currency: str = "INR"):
        super().__init__(currency)
        self.labels     = [d[0] for d in data]
        self.raw_values = [d[1] for d in data]
        self.values     = [float(v) for v in self.raw_values]
        self.colors     = [d[2] for d in data]
        self._patches: list = []

    def _get_hover_info(self, event):
        if not self._patches:
            return None
        for i, p in enumerate(self._patches):
            if p is not None and p.contains(event)[0]:
                text = (
                    f"{self.labels[i]}\n"
                    f"{fmt_currency(self.raw_values[i], self.currency, decimals=0, style='short')}"
                )
                return text, (event.xdata, event.ydata)
        return None

    def setup_plot(self):
        tc = get_token("text")
        gc = get_token("surface_mid")
        x  = np.arange(len(self.labels)) * 0.75

        bars = self.ax.bar(x, self.values, color=self.colors, edgecolor="none", width=0.5)
        self._patches = bars.patches

        max_v = max(self.values) if self.values else 1.0
        min_v = min(self.values) if self.values else 0.0
        pad   = (max_v - min_v) * 0.12 or 1.0
        for i, raw in enumerate(self.raw_values):
            val = self.values[i]
            if val > 0:
                self.ax.text(x[i], val + pad * 0.18,
                    fmt_currency(raw, self.currency, decimals=0, style="short"),
                    ha="center", va="bottom", fontsize=8, fontweight="bold", color=tc)
            elif val < 0:
                self.ax.text(x[i], val - pad * 0.18,
                    fmt_currency(raw, self.currency, decimals=0, style="short"),
                    ha="center", va="top", fontsize=8, fontweight="bold", color=tc)

        self._setup_axes_style(tc, gc, x, self.labels, "Cost")
        self._setup_y_formatter()
        if self.values:
            self.ax.set_ylim(min(0, min_v) - pad, max(0, max_v) + pad)

        self._setup_spines(tc)
        self._setup_annotation(tc)
        self._make_legend(
            [Patch(facecolor=c, label=l) for l, c in zip(self.labels, self.colors)],
            "Life Cycle Stages", tc,
        )
        self.fig.text(0.98, 0.97, currency_note(self.currency),
                      ha="right", va="top", fontsize=8,
                      color=get_token("text"), alpha=0.85)
        return self.fig


# ─────────────────────────────────────────────────────────────────────────────
# CHART 1 - Pillar-wise stacked bars
# ─────────────────────────────────────────────────────────────────────────────

class SustainabilityBarPlotter(_BasePlotter):
    def __init__(self, data: list, currency: str = "INR"):
        super().__init__(currency)
        self.data       = data
        self.stages     = [d["stage"] for d in data]
        self.categories = ["Economic", "Environmental", "Social"]
        self.raw_values = {
            cat: [next((p[1] for p in d["pillars"] if p[0] == cat), 0) for d in data]
            for cat in self.categories
        }
        self.values = {
            cat: [float(v) for v in self.raw_values[cat]]
            for cat in self.categories
        }

    def _get_hover_info(self, event):
        for patch in self.ax.patches:
            if patch.contains(event)[0]:
                for cat in self.categories:
                    if np.allclose(patch.get_facecolor()[:3],
                                   matplotlib.colors.to_rgb(PILLAR_COLORS[cat])):
                        x_pos     = patch.get_x() + patch.get_width() / 2
                        stage_idx = int(round(x_pos / 0.75))
                        if 0 <= stage_idx < len(self.stages):
                            raw = self.raw_values[cat][stage_idx]
                            text = (
                                f"{self.stages[stage_idx]}\n"
                                f"{cat}: {fmt_currency(raw, self.currency, decimals=0, style='short')}"
                            )
                            return text, (event.xdata, event.ydata)
        return None

    def setup_plot(self):
        tc  = get_token("text")
        gc  = get_token("surface_mid")
        x          = np.arange(len(self.stages)) * 0.75
        pos_bottom = np.zeros(len(self.stages))
        neg_bottom = np.zeros(len(self.stages))

        # Pre-compute y range for label threshold (segments < 6% of range are skipped)
        all_pos = sum(np.where(np.array(self.values[c]) > 0, np.array(self.values[c]), 0.0)
                      for c in self.categories)
        all_neg = sum(np.where(np.array(self.values[c]) < 0, np.array(self.values[c]), 0.0)
                      for c in self.categories)
        est_range    = float(np.max(all_pos) - np.min(all_neg)) or 1.0
        min_label_h  = est_range * 0.06

        # Environmental drawn last so it sits on top of the stack
        draw_order = ["Economic", "Social", "Environmental"]
        env_color  = PILLAR_COLORS["Environmental"]

        for cat in draw_order:
            vals     = np.array(self.values[cat])
            pos_vals = np.where(vals > 0, vals, 0.0)
            neg_vals = np.where(vals < 0, vals, 0.0)
            if pos_vals.any():
                seg_bot = pos_bottom.copy()
                self.ax.bar(x, pos_vals, bottom=pos_bottom,
                    color=PILLAR_COLORS[cat], edgecolor="none", width=0.5)
                pos_bottom += pos_vals
                if cat != "Environmental":          # Env is always labelled above the bar
                    for i, (v, b) in enumerate(zip(pos_vals, seg_bot)):
                        if v >= min_label_h:
                            self.ax.text(
                                x[i], b + v / 2,
                                f"{cat}\n{fmt_currency(v, self.currency, decimals=0, style='short')}",
                                ha="center", va="center", fontsize=7, fontweight="bold",
                                color="white", clip_on=True, linespacing=1.3,
                            )
            if neg_vals.any():
                seg_bot = neg_bottom.copy()
                self.ax.bar(x, neg_vals, bottom=neg_bottom,
                    color=PILLAR_COLORS[cat], edgecolor="none", width=0.5)
                neg_bottom += neg_vals
                if cat != "Environmental":
                    for i, (v, b) in enumerate(zip(neg_vals, seg_bot)):
                        if abs(v) >= min_label_h:
                            self.ax.text(
                                x[i], b + v / 2,
                                f"{cat}\n{fmt_currency(v, self.currency, decimals=0, style='short')}",
                                ha="center", va="center", fontsize=7, fontweight="bold",
                                color="white", clip_on=True, linespacing=1.3,
                            )

        y_max = max(pos_bottom) if pos_bottom.any() else 0.0
        y_min = min(neg_bottom) if neg_bottom.any() else 0.0
        pad   = (y_max - y_min) * 0.22 or 1.0

        for i in range(len(self.stages)):
            env_v = self.values["Environmental"][i] if self.values["Environmental"] else 0.0
            if pos_bottom[i] > 0:
                if env_v > 0:
                    # Env label just above bar top
                    self.ax.text(x[i], pos_bottom[i] + pad * 0.05,
                        f"Environmental: \n{fmt_currency(env_v, self.currency, decimals=0, style='short')}",
                        ha="center", va="bottom", fontsize=7.5, fontweight="bold",
                        color=env_color, clip_on=False)
                    # Total well above env label (single line, no overlap)
                    self.ax.text(x[i], pos_bottom[i] + pad * 0.42,
                        fmt_currency(pos_bottom[i], self.currency, decimals=0, style="short"),
                        ha="center", va="bottom", fontsize=8, fontweight="bold", color=tc)
                else:
                    self.ax.text(x[i], pos_bottom[i] + pad * 0.12,
                        fmt_currency(pos_bottom[i], self.currency, decimals=0, style="short"),
                        ha="center", va="bottom", fontsize=8, fontweight="bold", color=tc)
            if neg_bottom[i] < 0:
                self.ax.text(x[i], neg_bottom[i] - pad * 0.12,
                    fmt_currency(neg_bottom[i], self.currency, decimals=0, style="short"),
                    ha="center", va="top", fontsize=8, fontweight="bold", color=tc)

        self._setup_axes_style(tc, gc, x, self.stages, "Cost")
        self._setup_y_formatter()
        self.ax.set_ylim(min(0, y_min) - pad * 0.3, max(0, y_max) + pad)

        self._setup_spines(tc)
        self._setup_annotation(tc)
        self._make_legend(
            [Patch(facecolor=PILLAR_COLORS[cat], label=cat) for cat in self.categories],
            "Sustainability Pillars", tc,
        )
        self.fig.text(0.98, 0.97, currency_note(self.currency),
                      ha="right", va="top", fontsize=8,
                      color=get_token("text"), alpha=0.85)
        return self.fig


# ─────────────────────────────────────────────────────────────────────────────
# CHART 2 - Pillar x-axis, stage-stacked bars  (Pie.py breakdown view)
# ─────────────────────────────────────────────────────────────────────────────

def _lbl_color(hex_color: str) -> str:
    """White text on dark/saturated bars, dark text on light bars."""
    r, g, b = int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)
    return "#333333" if (0.299*r + 0.587*g + 0.114*b) / 255 > 0.58 else "white"


class PillarBreakdownBarPlotter(_BasePlotter):
    """Bars per pillar (Eco / Env / Soc) stacked by life cycle stage."""

    def __init__(self, data: list, currency: str = "INR"):
        super().__init__(currency)
        self.stages     = [d["stage"] for d in data]
        self.categories = ["Economic", "Environmental", "Social"]
        # pillar → {stage → raw_value}
        self.raw_values: dict[str, dict[str, float]] = {cat: {} for cat in self.categories}
        for d in data:
            for name, raw_val in d["pillars"]:
                self.raw_values[name][d["stage"]] = raw_val

    def _get_hover_info(self, event):
        for patch in self.ax.patches:
            if patch.contains(event)[0]:
                for stage in self.stages:
                    color = STAGE_COLORS.get(stage, "#AAAAAA")
                    if np.allclose(patch.get_facecolor()[:3], matplotlib.colors.to_rgb(color)[:3]):
                        x_pos   = patch.get_x() + patch.get_width() / 2
                        cat_idx = int(round(x_pos / 0.75))
                        if 0 <= cat_idx < len(self.categories):
                            cat = self.categories[cat_idx]
                            raw = self.raw_values[cat].get(stage, 0.0)
                            if raw != 0.0:
                                text = (
                                    f"{cat}\n"
                                    f"{stage}: {fmt_currency(raw, self.currency, decimals=0, style='short')}"
                                )
                                return text, (event.xdata, event.ydata)
        return None

    def setup_plot(self):
        tc  = get_token("text")
        gc  = get_token("surface_mid")
        x   = np.arange(len(self.categories)) * 0.75

        pos_bottom = np.zeros(len(self.categories))
        neg_bottom = np.zeros(len(self.categories))

        total_pos_per_cat = [
            sum(max(0.0, self.raw_values[cat].get(st, 0)) for st in self.stages)
            for cat in self.categories
        ]
        est_range   = max(total_pos_per_cat) if total_pos_per_cat else 1.0
        min_label_h = est_range * 0.06

        # missed[i] = [(abbrev, formatted_value, color), ...] - only used if no inside labels at all
        missed:        dict[int, list] = {i: [] for i in range(len(self.categories))}
        inside_count:  dict[int, int]  = {i: 0  for i in range(len(self.categories))}

        for stage in self.stages:
            color      = STAGE_COLORS.get(stage, "#AAAAAA")
            lc         = _lbl_color(color)
            stage_vals = np.array([self.raw_values[cat].get(stage, 0.0) for cat in self.categories])
            pos_vals   = np.where(stage_vals > 0, stage_vals, 0.0)
            neg_vals   = np.where(stage_vals < 0, stage_vals, 0.0)

            if pos_vals.any():
                seg_bot = pos_bottom.copy()
                self.ax.bar(x, pos_vals, bottom=pos_bottom, color=color, edgecolor="none", width=0.5)
                pos_bottom += pos_vals
                for i, (v, b) in enumerate(zip(pos_vals, seg_bot)):
                    if v >= min_label_h:
                        self.ax.text(
                            x[i], b + v / 2,
                            f"{stage}\n{fmt_currency(v, self.currency, decimals=0, style='short')}",
                            ha="center", va="center", fontsize=7, fontweight="bold",
                            color=lc, clip_on=True, linespacing=1.3,
                        )
                        inside_count[i] += 1
                    elif v > 0:
                        missed[i].append((
                            stage,
                            fmt_currency(v, self.currency, decimals=0, style="short"),
                            color,
                        ))
            if neg_vals.any():
                seg_bot = neg_bottom.copy()
                self.ax.bar(x, neg_vals, bottom=neg_bottom, color=color, edgecolor="none", width=0.5)
                neg_bottom += neg_vals
                for i, (v, b) in enumerate(zip(neg_vals, seg_bot)):
                    if abs(v) >= min_label_h:
                        self.ax.text(
                            x[i], b + v / 2,
                            f"{stage}\n{fmt_currency(v, self.currency, decimals=0, style='short')}",
                            ha="center", va="center", fontsize=7, fontweight="bold",
                            color=lc, clip_on=True, linespacing=1.3,
                        )
                        inside_count[i] += 1
                    elif v < 0:
                        missed[i].append((
                            stage,
                            fmt_currency(v, self.currency, decimals=0, style="short"),
                            color,
                        ))

        y_max = float(np.max(pos_bottom)) if pos_bottom.any() else 0.0
        y_min = float(np.min(neg_bottom)) if neg_bottom.any() else 0.0
        pad   = (y_max - y_min) * 0.12 or 1.0

        for i in range(len(self.categories)):
            if pos_bottom[i] > 0:
                self.ax.text(x[i], pos_bottom[i] + pad * 0.18,
                    fmt_currency(pos_bottom[i], self.currency, decimals=0, style="short"),
                    ha="center", va="bottom", fontsize=8, fontweight="bold", color=tc)
            if neg_bottom[i] < 0:
                self.ax.text(x[i], neg_bottom[i] - pad * 0.18,
                    fmt_currency(neg_bottom[i], self.currency, decimals=0, style="short"),
                    ha="center", va="top", fontsize=8, fontweight="bold", color=tc)

        # Callout boxes only when the bar had zero inside labels (all segments were tiny)
        box_style = dict(boxstyle="round,pad=0.35", fc=get_token("base"),
                         ec=get_token("surface_mid"), alpha=0.93, lw=0.8)
        arrow_style = dict(arrowstyle="-", color=get_token("surface_mid"), lw=0.8)
        for i, items in missed.items():
            if not items or inside_count[i] > 0:
                continue
            label_text = "\n".join(f"{abbrev}: {val_str}" for abbrev, val_str, _ in items)
            self.ax.annotate(
                label_text,
                xy=(x[i], pos_bottom[i]),
                xytext=(x[i], pos_bottom[i] + pad * 0.9),
                ha="center", va="bottom",
                fontsize=6.5, fontweight="bold", color=tc,
                bbox=box_style,
                arrowprops=arrow_style,
                clip_on=False,
            )

        self._setup_axes_style(tc, gc, x, self.categories, "Cost")
        self._setup_y_formatter()
        self.ax.set_ylim(min(0, y_min) - pad, max(0, y_max) + pad)
        self._setup_spines(tc)
        self._setup_annotation(tc)
        self._make_legend(
            [Patch(facecolor=STAGE_COLORS.get(st, "#AAAAAA"), label=st) for st in self.stages],
            "Life Cycle Stages", tc,
        )
        self.fig.text(0.98, 0.97, currency_note(self.currency),
                      ha="right", va="top", fontsize=8,
                      color=get_token("text"), alpha=0.85)
        return self.fig


# ─────────────────────────────────────────────────────────────────────────────
# WIDGET
# ─────────────────────────────────────────────────────────────────────────────

class AggregateChartWidget(QWidget):
    def __init__(self, results: dict, currency: str = "INR",
                 default_pillar_view: bool = False,
                 note: str = "",
                 parent=None):
        super().__init__(parent)
        self._results             = results
        self._currency            = currency
        self._default_pillar_view = default_pillar_view
        self._note                = note
        self._setup_ui()

    def _setup_ui(self):
        self._main_v = QVBoxLayout(self)
        self._main_v.setContentsMargins(0, SP4, 0, SP4)

        self.card = QFrame()
        self.card.setObjectName("aggCard")
        self.card.setStyleSheet(
            f"#aggCard {{"
            f"  background-color: transparent;"
            f"  border: 1.5px solid {get_token('surface_mid')};"
            f"  border-radius: {RADIUS_XL}px;"
            f"}}"
        )
        self.card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        self._card_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight, self.card)
        self._card_layout.setContentsMargins(SP6, SP6, SP6, SP6)
        self._card_layout.setSpacing(SP6)

        # ── Text panel ───────────────────────────────────────────────────────
        self._text_panel = QWidget()
        self._text_panel.setStyleSheet("background: transparent; border: none;")
        text_v = QVBoxLayout(self._text_panel)
        text_v.setContentsMargins(0, 0, 0, 0)
        text_v.setSpacing(SP4)
        text_v.setAlignment(Qt.AlignCenter)

        title = QLabel("Across 3 Stages")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(_f(FS_SUBHEAD, FW_BOLD))
        title.setStyleSheet(
            f"color: {get_token('text')}; border: none; background: transparent; letter-spacing: 0.5px;"
        )
        text_v.addWidget(title)

        # Ratio box- normalized so smallest = 1
        summary = compute_all_summaries(self._results)
        st      = summary.get("stagewise", {})

        c_init = get_token("init")
        c_use  = get_token("use")
        c_end  = get_token("end")

        v_ini = st.get("initial",     0)
        v_use = st.get("use",         0)
        v_end = st.get("end_of_life", 0)

        sum_stages = sum(abs(v) for v in [v_ini, v_use, v_end]) or 1.0
        p_ini = v_ini / sum_stages * 100
        p_use = v_use / sum_stages * 100
        p_end = v_end / sum_stages * 100

        a_ini = fmt_currency(v_ini, self._currency, decimals=0, style="short", use_short_suffix=True).title()
        a_use = fmt_currency(v_use, self._currency, decimals=0, style="short", use_short_suffix=True).title()
        a_end = fmt_currency(v_end, self._currency, decimals=0, style="short", use_short_suffix=True).title()

        _sep = f"<span style='color:{get_token('text_disabled')}'><b>:</b></span>"

        ratio_box = QFrame()
        ratio_box.setStyleSheet(
            f"background-color: {get_token('surface_mid', 'hover')}; "
            f"border: 1px solid {get_token('surface_mid', 'focus')}; "
            f"border-radius: {RADIUS_LG}px;"
        )
        ratio_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        rb_v = QVBoxLayout(ratio_box)
        rb_v.setContentsMargins(SP4, SP4, SP4, SP4)
        rb_v.setSpacing(SP2)

        rb_label = QLabel(
            f"<span style='color:{c_init}'>Initial</span> {_sep} "
            f"<span style='color:{c_use}'>Use</span> {_sep} "
            f"<span style='color:{c_end}'>End-of-Life</span>"
        )
        rb_label.setAlignment(Qt.AlignCenter)
        rb_label.setWordWrap(True)
        rb_label.setTextFormat(Qt.RichText)
        rb_label.setFont(_f(FS_MD, FW_BOLD))
        rb_label.setStyleSheet(f"color: {get_token('text')}; letter-spacing: 1.2px; border: none; background: transparent;")
        rb_v.addWidget(rb_label)

        rb_pct = QLabel(
            f"<span style='color:{c_init}'>{p_ini:.1f}%</span> {_sep} "
            f"<span style='color:{c_use}'>{p_use:.1f}%</span> {_sep} "
            f"<span style='color:{c_end}'>{p_end:.1f}%</span>"
        )
        rb_pct.setAlignment(Qt.AlignCenter)
        rb_pct.setTextFormat(Qt.RichText)
        rb_pct.setFont(QFont("Consolas", FS_MD, FW_BOLD))
        rb_pct.setStyleSheet("border: none; background: transparent;")
        rb_v.addWidget(rb_pct)

        rb_amt = QLabel(
            f"<span style='color:{c_init}'>{a_ini}</span> {_sep} "
            f"<span style='color:{c_use}'>{a_use}</span> {_sep} "
            f"<span style='color:{c_end}'>{a_end}</span>"
        )
        rb_amt.setAlignment(Qt.AlignCenter)
        rb_amt.setTextFormat(Qt.RichText)
        rb_amt.setFont(_f(FS_MD, FW_BOLD))
        rb_amt.setStyleSheet(f"border: none; background: transparent; color: {get_token('text_secondary')};")
        rb_v.addWidget(rb_amt)

        text_v.addWidget(ratio_box)

        # "Show pillar wise" checkbox
        self._pillar_cb = QCheckBox("Show pillar wise")
        self._pillar_cb.setFont(_f(FS_BASE))
        self._pillar_cb.setStyleSheet(
            f"color: {get_token('text_secondary')}; background: transparent; border: none;"
        )
        text_v.addWidget(self._pillar_cb, 0, Qt.AlignCenter)

        if self._note:
            note_lbl = QLabel(self._note)
            note_lbl.setAlignment(Qt.AlignCenter)
            note_lbl.setWordWrap(True)
            note_lbl.setFont(_f(FS_XS, FW_NORMAL, italic=True))
            note_lbl.setStyleSheet(
                f"color: {get_token('text_secondary')}; border: none; background: transparent;"
            )
            text_v.addWidget(note_lbl)

        self._card_layout.addWidget(self._text_panel, 1)

        # ── Chart stack ──────────────────────────────────────────────────────
        self._chart_stack = QStackedWidget()
        self._chart_stack.setMaximumHeight(420)
        self._chart_stack.setStyleSheet("background: transparent; border: none;")
        self._toolbar_stack = QStackedWidget()
        self._toolbar_stack.setStyleSheet("background: transparent; border: none;")

        scroller = WheelForwarder(self)

        # Chart 0: stage-wise
        stage_data = _build_stage_data(self._results)
        if stage_data:
            p0   = StageBarPlotter(stage_data, currency=self._currency)
            fig0 = p0.setup_plot()
            c0   = FigureCanvasQTAgg(fig0)
            c0.setStyleSheet("background: transparent; border: none;")
            c0.setMinimumHeight(280)
            c0.setMaximumHeight(420)
            c0.installEventFilter(scroller)
            self._chart_stack.addWidget(c0)
            self._toolbar_stack.addWidget(ChartToolbar(c0, self))
        else:
            lbl = QLabel("Insufficient data.")
            lbl.setAlignment(Qt.AlignCenter)
            self._chart_stack.addWidget(lbl)
            self._toolbar_stack.addWidget(QWidget())

        # Chart 1: pillar-wise (stacked)
        pillar_data = _build_pillar_data(self._results)
        if pillar_data:
            p1   = SustainabilityBarPlotter(pillar_data, currency=self._currency)
            fig1 = p1.setup_plot()
            c1   = FigureCanvasQTAgg(fig1)
            c1.setStyleSheet("background: transparent; border: none;")
            c1.setMinimumHeight(280)
            c1.setMaximumHeight(420)
            c1.installEventFilter(scroller)
            self._chart_stack.addWidget(c1)
            self._toolbar_stack.addWidget(ChartToolbar(c1, self))
        else:
            lbl = QLabel("Insufficient data.")
            lbl.setAlignment(Qt.AlignCenter)
            self._chart_stack.addWidget(lbl)
            self._toolbar_stack.addWidget(QWidget())

        self._pillar_cb.toggled.connect(
            lambda checked: self._chart_stack.setCurrentIndex(1 if checked else 0)
        )
        self._pillar_cb.toggled.connect(
            lambda checked: self._toolbar_stack.setCurrentIndex(1 if checked else 0)
        )

        if self._default_pillar_view:
            self._pillar_cb.setChecked(True)

        self._chart_cont = QWidget()
        self._chart_cont.setStyleSheet("background: transparent; border: none;")
        chart_cv = QVBoxLayout(self._chart_cont)
        chart_cv.setContentsMargins(0, 0, 0, 0)
        chart_cv.setSpacing(0)
        chart_cv.addWidget(self._chart_stack)
        chart_cv.addWidget(self._toolbar_stack)

        self._card_layout.addWidget(self._chart_cont, 2)

        self._main_v.addWidget(self.card)

    # ── responsive layout ─────────────────────────────────────────────────────

    def resizeEvent(self, event):
        super().resizeEvent(event)
        is_narrow = event.size().width() < 880
        if is_narrow:
            self._card_layout.setDirection(QBoxLayout.Direction.TopToBottom)
            self._card_layout.insertWidget(0, self._text_panel)
            self._text_panel.setMinimumWidth(0)
            self._text_panel.setMaximumWidth(16777215)
        else:
            self._card_layout.setDirection(QBoxLayout.Direction.LeftToRight)
            self._card_layout.insertWidget(0, self._text_panel)
            self._text_panel.setFixedWidth(350)

    def minimumSizeHint(self):
        return QSize(0, 400)
