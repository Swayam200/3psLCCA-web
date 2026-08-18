"""
gui/components/outputs/plots_helper/Pie.py

Two-tab pie widget:
  Tab 0 - Simple pillar donut  (Eco / Env / Social, lifetime totals)
  Tab 1 - Nested stage+pillar donut (existing Sustainability Matrix)
"""

import os
import matplotlib
import numpy as np
from matplotlib.figure import Figure
from matplotlib.patches import Patch
from matplotlib import font_manager as _fm

matplotlib.use("QtAgg")

try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
except ImportError:
    from matplotlib.backends.backend_qt import FigureCanvasQTAgg

from PySide6.QtCore import QEvent, QObject, QSize, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QBoxLayout,
    QCheckBox,
    QLabel,
    QSizePolicy,
    QHBoxLayout,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
    QFrame,
    QScrollArea,
)

from three_ps_lcca_gui.gui.theme import (
    FONT_FAMILY,
    FS_XS, FS_SM, FS_BASE, FS_LG, FS_SUBHEAD, FS_XL, FS_MD,
    FW_NORMAL, FW_BOLD,
    SP1, SP2, SP3, SP4, SP5, SP6, RADIUS_LG, RADIUS_XL, FW_MEDIUM, FW_SEMIBOLD
)
from three_ps_lcca_gui.gui.themes import get_token, theme_manager
from three_ps_lcca_gui.gui.styles import font as _f
from three_ps_lcca_gui.gui.components.utils.display_format import fmt_currency
from ..helper_functions.lifecycle_summary import compute_all_summaries
from ..helper_functions.ratio_helper import format_ratio_string
from ..helper_functions.lcc_colors import COLORS as LCC_COLORS
from .AggregateChart import (
    StageBarPlotter, SustainabilityBarPlotter, PillarBreakdownBarPlotter,
    _build_pillar_total_data, _build_pillar_data as _build_pillar_bar_data,
)
from .plot_utils import register_ubuntu_fonts, WheelForwarder, ChartToolbar, currency_note

# ── Register Ubuntu fonts ────────────────────────────────────────────────────
register_ubuntu_fonts()
matplotlib.rcParams["font.family"] = FONT_FAMILY

# ─────────────────────────────────────────────────────────────────────────────
# COLORS
# ─────────────────────────────────────────────────────────────────────────────

COLORS = {
    "stages": {
        "Initial":     LCC_COLORS["init_color"],
        "Use":         LCC_COLORS["use_color"],
        "End-of-Life": LCC_COLORS["end_color"],
    },
    "pillars": {
        "Economic":      LCC_COLORS["eco_color"],
        "Environmental": LCC_COLORS["env_color"],
        "Social":        LCC_COLORS["soc_color"],
    },
}

# Original wedge widths preserved
_WEDGE      = {"width": 0.30, "edgecolor": "none", "linewidth": 0}
_WEDGE_SIMP = {"width": 0.42, "edgecolor": "none", "linewidth": 0}

_TAB_META = [
    {
        "title": "Pillar Distribution",
        "desc": "Lifetime cost breakdown across the three sustainability pillars- Economic, Environmental, and Social- aggregated over all life cycle stages.",
    },
    {
        "title": "Across 3 Pillars of Sustainability",
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# DATA & CHART HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _pillar_totals_ok(results: dict) -> bool:
    pt = compute_all_summaries(results).get("pillar_totals", {})
    return all(v >= 0 for v in pt.values())

def _nested_data_ok(results: dict) -> bool:
    pw = compute_all_summaries(results).get("pillar_wise", {})
    return all(v >= 0 for stage in pw.values() for v in stage.values())

def _build_pillar_data(results: dict):
    pt = compute_all_summaries(results).get("pillar_totals", {})
    rows = [
        ("Economic",      pt.get("eco",    0), COLORS["pillars"]["Economic"]),
        ("Environmental", pt.get("env",    0), COLORS["pillars"]["Environmental"]),
        ("Social",        pt.get("social", 0), COLORS["pillars"]["Social"]),
    ]
    return [(l, float(v), c) for l, v, c in rows if v > 0]

def _build_nested_pie_data(results: dict) -> list:
    pw = compute_all_summaries(results).get("pillar_wise", {})
    mapping = [("initial", "Initial"), ("use", "Use"), ("end_of_life", "End-of-Life")]
    data = []
    for key, label in mapping:
        p = pw.get(key, {})
        if not p or sum(p.values()) <= 0: continue
        data.append({
            "stage": label,
            "pillars": [
                ("Economic",      float(p.get("eco",    0)), COLORS["pillars"]["Economic"]),
                ("Environmental", float(p.get("env",    0)), COLORS["pillars"]["Environmental"]),
                ("Social",        float(p.get("social", 0)), COLORS["pillars"]["Social"]),
            ],
        })
    return data
def _add_smart_labels(ax, wedges, labels, threshold=None, leader_radius=1.3):
    """
    Anti-overlap elbow labels.

    Labels are split into left / right hemispheres, stacked vertically with a
    push-apart relaxation pass, then each label is connected back to its slice
    with a two-segment leader:  edge-dot → radial elbow → (adjusted) label column.
    """
    text_color = get_token("text")
    line_color = get_token("surface_mid")
    entries = []
    for i, p in enumerate(wedges):
        angle = (p.theta2 + p.theta1) / 2.0
        rad = np.deg2rad(angle)
        cx, cy = np.cos(rad), np.sin(rad)
        entries.append({
            "idx": i,
            "cx": cx, "cy": cy,
            "x0": cx * p.r, "y0": cy * p.r,
            "y_nat": cy * leader_radius,
            "label": labels[i],
        })

    if not entries:
        return {}

    artists = {}  # wedge_index → [matplotlib artists]

    max_lines = max(len(e["label"].split("\n")) for e in entries)
    MIN_GAP = 0.62 if max_lines >= 3 else 0.32

    def _resolve(group):
        group = sorted(group, key=lambda e: -e["y_nat"])
        ys = [e["y_nat"] for e in group]
        for _ in range(300):
            moved = False
            for j in range(len(ys) - 1):
                gap = ys[j] - ys[j + 1]
                if gap < MIN_GAP:
                    shift = (MIN_GAP - gap) / 2
                    ys[j]     += shift
                    ys[j + 1] -= shift
                    moved = True
            if not moved:
                break
        return group, ys

    def _draw(group, ys, ha, x_col):
        tick = 0.08 if ha == "left" else -0.08
        for e, y_lbl in zip(group, ys):
            line, = ax.plot(
                [e["x0"], e["cx"] * leader_radius, x_col],
                [e["y0"], e["y_nat"],               y_lbl],
                color=line_color, lw=0.8, alpha=0.9,
                solid_capstyle="round", zorder=9, clip_on=False,
            )
            dot, = ax.plot(e["x0"], e["y0"], "o", color=line_color,
                    markersize=2.5, alpha=0.9, zorder=10, clip_on=False)

            parts = e["label"].split("\n")
            x_txt = x_col + tick
            entry_artists = [line, dot]

            if len(parts) == 3:
                stage, name, value = parts
                entry_artists.append(ax.text(x_txt, y_lbl + 0.16, stage, ha=ha, va="center",
                        color=text_color, fontsize=8.0, alpha=0.65,
                        clip_on=False, zorder=11))
                entry_artists.append(ax.text(x_txt, y_lbl, name, ha=ha, va="center",
                        color=text_color, fontsize=9.5, fontweight="bold",
                        clip_on=False, zorder=11))
                entry_artists.append(ax.text(x_txt, y_lbl - 0.16, value, ha=ha, va="center",
                        color=text_color, fontsize=8.5, alpha=0.65,
                        clip_on=False, zorder=11))
            elif len(parts) == 2:
                name, value = parts
                entry_artists.append(ax.text(x_txt, y_lbl + 0.09, name, ha=ha, va="center",
                        color=text_color, fontsize=9.5, fontweight="bold",
                        clip_on=False, zorder=11))
                entry_artists.append(ax.text(x_txt, y_lbl - 0.09, value, ha=ha, va="center",
                        color=text_color, fontsize=8.5, alpha=0.65,
                        clip_on=False, zorder=11))
            else:
                entry_artists.append(ax.text(x_txt, y_lbl, parts[0], ha=ha, va="center",
                        color=text_color, fontsize=9.5, fontweight="bold",
                        clip_on=False, zorder=11))

            artists[e["idx"]] = entry_artists

    right = [e for e in entries if e["cx"] >= 0]
    left  = [e for e in entries if e["cx"] <  0]
    x_col = leader_radius + 0.22

    if right:
        g, ys = _resolve(right)
        _draw(g, ys, "left",  x_col)
    if left:
        g, ys = _resolve(left)
        _draw(g, ys, "right", -x_col)

    return artists

def _add_inner_band_labels(ax, wedges, labels):
    """Stage names rendered inside the inner donut band - no leader lines needed."""
    text_color = get_token("text")
    for i, p in enumerate(wedges):
        if p.theta2 - p.theta1 <= 5.0:
            continue
        angle = (p.theta2 + p.theta1) / 2.0
        rad = np.deg2rad(angle)
        r_mid = p.r - p.width / 2          # radial midpoint of the band
        cx, cy = np.cos(rad) * r_mid, np.sin(rad) * r_mid
        ax.text(
            cx, cy, labels[i],
            ha="center", va="center",
            color=text_color, fontsize=6.5, fontweight="bold",
            clip_on=False, zorder=11,
        )

# ─────────────────────────────────────────────────────────────────────────────
# CHART 0 - Simple pillar donut
# ─────────────────────────────────────────────────────────────────────────────

class SimplePillarPlotter:
    def __init__(self, results: dict, currency: str = "INR"):
        items = _build_pillar_data(results)
        self.labels, self.values, self.colors = [i[0] for i in items], [i[1] for i in items], [i[2] for i in items]
        self.total, self.currency, self.mode = sum(self.values), currency, "Value"
        self._center_text  = None
        self._base_radius  = 1.05

        self.fig = Figure(figsize=(7, 6))
        self.fig.patch.set_alpha(0.0)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor("none")
        self.fig.subplots_adjust(left=0.12, right=0.88, bottom=0.12, top=0.98)
        self.fig.canvas.mpl_connect("motion_notify_event", self._hover)

    def _fmt(self, val: float) -> str:
        if self.mode == "Percentage": return f"{val / (self.total or 1) * 100:.1f}%"
        return fmt_currency(val, self.currency, decimals=0, style="short")

    def _hover(self, event):
        if not hasattr(self, "wedges") or not self.wedges:
            return
        if event.inaxes != self.ax:
            for w in self.wedges:
                w.set_radius(self._base_radius)
                w.set_alpha(1.0)
            self._set_legend_alpha(-1)
            if hasattr(self, "_label_artists"):
                for artists in self._label_artists.values():
                    for a in artists: a.set_visible(True)
        else:
            hit = next((i for i, w in enumerate(self.wedges) if w.contains(event)[0]), -1)
            for i, w in enumerate(self.wedges):
                if hit == -1 or i == hit:
                    w.set_radius(self._base_radius * 1.06 if i == hit else self._base_radius)
                    w.set_alpha(1.0)
                else:
                    w.set_radius(self._base_radius)
                    w.set_alpha(0.25)
            self._set_legend_alpha(hit)
            if hasattr(self, "_label_artists"):
                for i, artists in self._label_artists.items():
                    visible = (hit == -1 or i == hit)
                    for a in artists: a.set_visible(visible)
        self.fig.canvas.draw_idle()

    def _set_legend_alpha(self, hit: int):
        leg = self.ax.get_legend()
        if not leg:
            return
        for i, (handle, text) in enumerate(zip(leg.legend_handles, leg.get_texts())):
            a = 1.0 if hit == -1 or i == hit else 0.25
            handle.set_alpha(a)
            text.set_alpha(a)

    def set_mode(self, is_percentage: bool):
        self.mode = "Percentage" if is_percentage else "Value"
        self.ax.clear()
        self._center_text = None
        self.setup_plot()
        self.fig.canvas.draw_idle()

    def setup_plot(self):
        tc = get_token("text")
        self.ax.set(aspect="equal")
        if not self.values:
            self.ax.text(0, 0, "No Data", ha="center", va="center", color=tc)
            self.ax.axis("off")
            return self.fig

        self.wedges, _ = self.ax.pie(self.values, radius=1.05, colors=self.colors, wedgeprops=_WEDGE_SIMP)

        display_labels = [f"{l}\n{self._fmt(v)}" for l, v in zip(self.labels, self.values)]
        self._label_artists = _add_smart_labels(self.ax, self.wedges, display_labels, threshold=15.0, leader_radius=1.25)

        self._center_text = self.ax.text(0, 0, f"Total\n{self._fmt(self.total)}", ha="center", va="center", fontsize=10, fontweight="bold", color=tc)

        legend_els = [Patch(facecolor=c, label=l) for l, c in zip(self.labels, self.colors)]
        self.ax.legend(handles=legend_els, loc="upper center", bbox_to_anchor=(0.5, -0.05), ncol=3, frameon=False, fontsize=8, labelcolor=tc)

        self.ax.axis("off")
        self.ax.set_xlim(-1.85, 1.85)
        self.ax.set_ylim(-1.85, 1.85)
        self.fig.text(0.98, 0.97, currency_note(self.currency),
                      ha="right", va="top", fontsize=8,
                      color=get_token("text"), alpha=0.85)
        return self.fig

# ─────────────────────────────────────────────────────────────────────────────
# CHART 1 - Nested stage+pillar donut
# ─────────────────────────────────────────────────────────────────────────────

class SustainabilityCircularPlotter:
    def __init__(self, data: list, currency: str = "INR"):
        self.data, self.currency, self.mode = data, currency, "Value"
        self._center_text       = None
        self._base_inner_radius = 0.8
        self._base_outer_radius = 1.1

        self.fig = Figure(figsize=(7, 6))
        self.fig.patch.set_alpha(0.0)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor("none")
        self.fig.subplots_adjust(left=0.14, right=0.86, bottom=0.12, top=0.98)
        self.fig.canvas.mpl_connect("motion_notify_event", self._hover)
        self._prepare_data()

    def _prepare_data(self):
        self.total_value = sum(sum(p[1] for p in e["pillars"]) for e in self.data)
        self.inner_vals, self.inner_colors, self.inner_labels = [], [], []
        self.outer_vals, self.outer_colors, self.outer_labels = [], [], []
        self._stage_to_outer: dict[str, list[int]] = {}
        for entry in self.data:
            self.inner_vals.append(sum(p[1] for p in entry["pillars"]))
            self.inner_labels.append(entry["stage"])
            self.inner_colors.append(COLORS["stages"].get(entry["stage"], "#DDDDDD"))
            for name, val, color in entry["pillars"]:
                j = len(self.outer_vals)
                self._stage_to_outer.setdefault(entry["stage"], []).append(j)
                self.outer_vals.append(val); self.outer_labels.append(f"{entry['stage']} - {name}"); self.outer_colors.append(color)

    def _fmt(self, val: float) -> str:
        if self.mode == "Percentage": return f"{val / (self.total_value or 1) * 100:.1f}%"
        return fmt_currency(val, self.currency, decimals=0, style="short")

    def _hover(self, event):
        if not hasattr(self, "outer_wedges") or not self.outer_wedges:
            return
        if event.inaxes != self.ax:
            for w in self.inner_wedges:
                w.set_radius(self._base_inner_radius)
                w.set_alpha(1.0)
            for w in self.outer_wedges:
                w.set_radius(self._base_outer_radius)
                w.set_alpha(1.0)
            self._set_legend_alpha(-1, -1)
            if self._center_text:
                self._center_text.set_text(f"Total\n{self._fmt(self.total_value)}")
            if hasattr(self, "_label_artists"):
                for artists in self._label_artists.values():
                    for a in artists: a.set_visible(True)
        else:
            # Wedge.contains() doesn't respect the annular hole, so determine
            # which ring the cursor is in via radial distance first.
            r = np.hypot(event.xdata or 0.0, event.ydata or 0.0)
            r_outer_min = self._base_outer_radius - 0.30  # _WEDGE width = 0.30
            r_inner_min = self._base_inner_radius - 0.30

            if r >= r_outer_min:
                hit_outer = next((i for i, w in enumerate(self.outer_wedges) if w.contains(event)[0]), -1)
                hit_inner = -1
            elif r >= r_inner_min:
                hit_inner = next((i for i, w in enumerate(self.inner_wedges) if w.contains(event)[0]), -1)
                hit_outer = -1
            else:
                hit_outer = hit_inner = -1

            # Inner ring
            for i, w in enumerate(self.inner_wedges):
                if hit_outer >= 0:
                    w.set_radius(self._base_inner_radius)
                    w.set_alpha(0.25)
                elif hit_inner == -1 or i == hit_inner:
                    w.set_radius(self._base_inner_radius * 1.06 if i == hit_inner else self._base_inner_radius)
                    w.set_alpha(1.0)
                else:
                    w.set_radius(self._base_inner_radius)
                    w.set_alpha(0.25)

            # Outer ring
            if hit_inner >= 0:
                stage_outer = set(self._stage_to_outer.get(self.inner_labels[hit_inner], []))
                for i, w in enumerate(self.outer_wedges):
                    if i in stage_outer:
                        w.set_radius(self._base_outer_radius * 1.06)
                        w.set_alpha(1.0)
                    else:
                        w.set_radius(self._base_outer_radius)
                        w.set_alpha(0.25)
            else:
                for i, w in enumerate(self.outer_wedges):
                    if hit_outer == -1 or i == hit_outer:
                        w.set_radius(self._base_outer_radius * 1.06 if i == hit_outer else self._base_outer_radius)
                        w.set_alpha(1.0)
                    else:
                        w.set_radius(self._base_outer_radius)
                        w.set_alpha(0.25)

            self._set_legend_alpha(hit_outer, hit_inner)

            if self._center_text:
                if hit_inner >= 0:
                    self._center_text.set_text(
                        f"{self.inner_labels[hit_inner]}\n{self._fmt(self.inner_vals[hit_inner])}"
                    )
                else:
                    self._center_text.set_text(f"Total\n{self._fmt(self.total_value)}")

            if hasattr(self, "_label_artists"):
                if hit_inner >= 0:
                    stage_outer = set(self._stage_to_outer.get(self.inner_labels[hit_inner], []))
                    for i, artists in self._label_artists.items():
                        for a in artists: a.set_visible(i in stage_outer)
                else:
                    for i, artists in self._label_artists.items():
                        visible = (hit_outer == -1 or i == hit_outer)
                        for a in artists: a.set_visible(visible)
        self.fig.canvas.draw_idle()

    # Legend layout (interleaved, ncol=3): even indices = pillars, odd = stages
    # Columns: (Economic, Initial) | (Environmental, Use) | (Social, End-of-Life)
    _LEGEND_PILLAR_ORDER = ["Economic", "Environmental", "Social"]
    _LEGEND_STAGE_ORDER  = ["Initial", "Use", "End-of-Life"]

    def _set_legend_alpha(self, hit_outer: int, hit_inner: int = -1):
        leg = self.ax.get_legend()
        if not leg:
            return
        handles, texts = leg.legend_handles, leg.get_texts()
        for i, (handle, text) in enumerate(zip(handles, texts)):
            if hit_outer == -1 and hit_inner == -1:
                a = 1.0
            elif hit_outer >= 0:
                # Outer hover: highlight matching pillar, keep stages fully visible
                if i % 2 == 1:  # stage entry (odd index)
                    a = 1.0
                else:           # pillar entry (even index)
                    hit_pillar = self.outer_labels[hit_outer].split(" - ")[1]
                    a = 1.0 if text.get_text() == hit_pillar else 0.25
            else:
                # Inner hover: highlight matching stage, keep pillars fully visible
                if i % 2 == 0:  # pillar entry (even index)
                    a = 1.0
                else:           # stage entry (odd index)
                    a = 1.0 if self._LEGEND_STAGE_ORDER[i // 2] == self.inner_labels[hit_inner] else 0.25
            handle.set_alpha(a)
            text.set_alpha(a)

    def set_mode(self, is_percentage: bool):
        self.mode = "Percentage" if is_percentage else "Value"
        self.ax.clear()
        self._center_text = None
        self.setup_plot()
        self.fig.canvas.draw_idle()

    def setup_plot(self):
        tc = get_token("text")
        sep = get_token("surface_mid")
        self.ax.set(aspect="equal")

        self.inner_wedges, _ = self.ax.pie(self.inner_vals, radius=self._base_inner_radius, colors=self.inner_colors, wedgeprops=_WEDGE)
        self.outer_wedges, _ = self.ax.pie(self.outer_vals, radius=self._base_outer_radius, colors=self.outer_colors, wedgeprops=_WEDGE)

        outer_disp = [f"{l.split(' - ')[0]}\n{l.split(' - ')[1]}\n{self._fmt(v)}" for l, v in zip(self.outer_labels, self.outer_vals)]
        self._label_artists = _add_smart_labels(self.ax, self.outer_wedges, outer_disp, threshold=15.0, leader_radius=1.45)

        if self.total_value > 0:
            angles = np.cumsum(self.inner_vals) / self.total_value * 2 * np.pi
            for angle in angles:
                x = [0.5 * np.cos(angle), 1.1 * np.cos(angle)]
                y = [0.5 * np.sin(angle), 1.1 * np.sin(angle)]
                self.ax.plot(x, y, color=sep, lw=1.5, alpha=0.5)

        self._center_text = self.ax.text(0, 0, f"Total\n{self._fmt(self.total_value)}", ha="center", va="center", fontsize=10, fontweight="bold", color=tc)

        # ncol=3 fills column-by-column, so interleave pillar/stage pairs so each
        # column holds one of each → row 1: pillars, row 2: stages.
        _PILLAR_ORDER = ["Economic", "Environmental", "Social"]
        _STAGE_ORDER  = ["Initial", "Use", "End-of-Life"]
        legend_els = []
        for pillar, stage in zip(_PILLAR_ORDER, _STAGE_ORDER):
            legend_els.append(Patch(facecolor=COLORS["pillars"][pillar], label=pillar))
            legend_els.append(Patch(facecolor=COLORS["stages"].get(stage, "#AAA"), label=stage))
        self.ax.legend(handles=legend_els, loc="upper center", bbox_to_anchor=(0.5, -0.05), ncol=3, frameon=False, fontsize=8, labelcolor=tc)

        self.ax.axis("off")
        self.ax.set_xlim(-2.1, 2.1)
        self.ax.set_ylim(-2.1, 2.1)
        self.fig.text(0.98, 0.97, currency_note(self.currency),
                      ha="right", va="top", fontsize=8,
                      color=get_token("text"), alpha=0.85)
        return self.fig

# ─────────────────────────────────────────────────────────────────────────────
# WIDGET
# ─────────────────────────────────────────────────────────────────────────────

class LCCPieWidget(QWidget):
    def __init__(self, results: dict, currency: str = "INR", parent=None):
        super().__init__(parent)
        self._results, self._currency = results, currency
        self._setup_ui()

    def _setup_ui(self):
        self._main_v = QVBoxLayout(self)
        self._main_v.setContentsMargins(0, SP4, 0, SP4)

        self.card = QFrame()
        self.card.setObjectName("pieCard")
        self.card.setStyleSheet(f"#pieCard {{ background: transparent; border: 1.5px solid {get_token('surface_mid')}; border-radius: {RADIUS_XL}px; }}")
        self.card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        card_v = QVBoxLayout(self.card)
        card_v.setContentsMargins(SP6, SP5, SP6, SP6)
        card_v.setSpacing(SP4)

        content_row = QWidget()
        content_row.setStyleSheet("background: transparent; border: none;")
        self._content_h = QHBoxLayout(content_row)
        self._content_h.setContentsMargins(0, 0, 0, 0)
        self._content_h.setSpacing(SP6)

        self._left_panel = QWidget()
        self._left_panel.setStyleSheet("background: transparent; border: none;")
        left_v = QVBoxLayout(self._left_panel)
        left_v.setContentsMargins(0, 0, 0, 0)
        left_v.setSpacing(SP4)
        left_v.setAlignment(Qt.AlignCenter)

        title_lbl = QLabel(_TAB_META[1]["title"])
        title_lbl.setAlignment(Qt.AlignCenter)
        title_lbl.setWordWrap(True)
        title_lbl.setFont(_f(FS_SUBHEAD, FW_BOLD))
        title_lbl.setStyleSheet(f"color: {get_token('text')}; border: none; letter-spacing: 0.5px;")
        left_v.addWidget(title_lbl)

        _desc = _TAB_META[1].get("desc", "")
        if _desc:
            desc_lbl = QLabel(_desc)
            desc_lbl.setWordWrap(True)
            desc_lbl.setAlignment(Qt.AlignCenter)
            desc_lbl.setFont(_f(FS_BASE))
            desc_lbl.setStyleSheet(f"color: {get_token('text_secondary')}; border: none;")
            left_v.addWidget(desc_lbl)

        summary = compute_all_summaries(self._results)
        pt = summary.get("pillar_totals", {})

        c_eco, c_env, c_soc = get_token("eco"), get_token("env"), get_token("soc")
        _pillar_ok, _nested_ok = _pillar_totals_ok(self._results), _nested_data_ok(self._results)

        # Calculate percentages and formatted amounts
        v_eco, v_env, v_soc = pt.get("eco", 0), pt.get("env", 0), pt.get("social", 0)
        sum_pt = sum([v_eco, v_env, v_soc]) or 1.0
        p_eco, p_env, p_soc = v_eco / sum_pt * 100, v_env / sum_pt * 100, v_soc / sum_pt * 100
        
        a_eco = fmt_currency(v_eco, self._currency, decimals=0, style="short", use_short_suffix=True).title()
        a_env = fmt_currency(v_env, self._currency, decimals=0, style="short", use_short_suffix=True).title()
        a_soc = fmt_currency(v_soc, self._currency, decimals=0, style="short", use_short_suffix=True).title()

        ratio_box = QFrame()
        ratio_box.setStyleSheet(
            f"background-color: {get_token('surface_mid')}; "
            f"border: 1px solid {get_token('surface_mid')}; "
            f"border-radius: {RADIUS_LG}px;"
        )
        ratio_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        rb_v = QVBoxLayout(ratio_box)
        rb_v.setContentsMargins(SP4, SP4, SP4, SP4)
        rb_v.setSpacing(SP2)

        rb_label = QLabel(f"<span style='color:{c_eco}'>Economic</span> <span style='color:{get_token('text_disabled')}'>:</span> <span style='color:{c_env}'>Environmental</span> <span style='color:{get_token('text_disabled')}'>:</span> <span style='color:{c_soc}'>Social</span>")
        rb_label.setAlignment(Qt.AlignCenter)
        rb_label.setWordWrap(True)
        rb_label.setTextFormat(Qt.RichText)
        rb_label.setFont(_f(FS_MD, FW_BOLD))
        rb_label.setStyleSheet(f"color: {get_token('text')}; letter-spacing: 1.2px; border: none; background: transparent;")
        rb_v.addWidget(rb_label)

        rb_pct = QLabel(f"<span style='color:{c_eco}'>{p_eco:.1f}%</span> <span style='color:{get_token('text_disabled')}'>:</span> <span style='color:{c_env}'>{p_env:.1f}%</span> <span style='color:{get_token('text_disabled')}'>:</span> <span style='color:{c_soc}'>{p_soc:.1f}%</span>")
        rb_pct.setAlignment(Qt.AlignCenter)
        rb_pct.setTextFormat(Qt.RichText)
        rb_pct.setFont(QFont("Consolas", FS_MD, FW_BOLD))
        rb_pct.setStyleSheet(f"border: none; background: transparent;")
        rb_v.addWidget(rb_pct)

        rb_amt = QLabel(f"<span style='color:{c_eco}'>{a_eco}</span> <span style='color:{get_token('text_disabled')}'>:</span> <span style='color:{c_env}'>{a_env}</span> <span style='color:{get_token('text_disabled')}'>:</span> <span style='color:{c_soc}'>{a_soc}</span>")
        rb_amt.setAlignment(Qt.AlignCenter)
        rb_amt.setTextFormat(Qt.RichText)
        rb_amt.setFont(_f(FS_MD, FW_BOLD))
        rb_amt.setStyleSheet(f"border: none; background: transparent; color: {get_token('text_secondary')};")
        rb_v.addWidget(rb_amt)
        left_v.addWidget(ratio_box)

        # self._mode_cb = QCheckBox("Show Percentage Mode")
        # self._mode_cb.setFont(_f(FS_BASE))
        # self._mode_cb.setStyleSheet(f"color: {get_token('text_secondary')}; background: transparent; border: none;")
        # self._mode_cb.setVisible(_pillar_ok)
        # left_v.addWidget(self._mode_cb, 0, Qt.AlignCenter)

        self._stage_cb = QCheckBox("Include stage-wise break-up")
        self._stage_cb.setFont(_f(FS_BASE))
        self._stage_cb.setStyleSheet(f"color: {get_token('text_secondary')}; background: transparent; border: none;")
        self._stage_cb.setVisible(_pillar_ok)
        self._stage_cb.setEnabled(_nested_ok)
        left_v.addWidget(self._stage_cb, 0, Qt.AlignCenter)

        if _pillar_ok and not _nested_ok:
            _stage_note = QLabel("* Stage breakdown unavailable- negative values in stage data.")
            _stage_note.setAlignment(Qt.AlignCenter)
            _stage_note.setWordWrap(True)
            _stage_note.setFont(_f(FS_XS, FW_NORMAL, italic=True))
            _stage_note.setStyleSheet(f"color: {get_token('text_secondary')}; border: none; background: transparent;")
            left_v.addWidget(_stage_note)

        self._content_h.addWidget(self._left_panel, 1)
        self._plotters = []

        if not _pillar_ok:
            pillar_bar_data = _build_pillar_total_data(self._results)
            if pillar_bar_data:
                p_bar = StageBarPlotter(pillar_bar_data, currency=self._currency)
                c_bar = FigureCanvasQTAgg(p_bar.setup_plot())
                c_bar.setMinimumHeight(400); c_bar.setMaximumHeight(500)
                c_bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                c_bar.setStyleSheet("background: transparent; border: none;")
                c_bar.installEventFilter(WheelForwarder(self))
                chart_cont = QWidget()
                chart_cont.setStyleSheet("background: transparent; border: none;")
                cv = QVBoxLayout(chart_cont)
                cv.setContentsMargins(0, 0, 0, 0)
                cv.setSpacing(0)
                cv.addWidget(c_bar)
                cv.addWidget(ChartToolbar(c_bar, chart_cont))
                self._content_h.addWidget(chart_cont, 2)
            else:
                _no_data = QLabel("No data available.")
                _no_data.setAlignment(Qt.AlignCenter)
                self._content_h.addWidget(_no_data, 2)
        else:
            self._chart_stack = QStackedWidget()
            self._chart_stack.setMaximumHeight(500)
            self._chart_stack.setStyleSheet("background: transparent; border: none;")
            self._toolbar_stack = QStackedWidget()
            self._toolbar_stack.setStyleSheet("background: transparent; border: none;")
            scroller = WheelForwarder(self)

            p0 = SimplePillarPlotter(self._results, currency=self._currency)
            c0 = FigureCanvasQTAgg(p0.setup_plot())
            c0.setMinimumHeight(400); c0.setMaximumHeight(500)
            c0.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            c0.setStyleSheet("background: transparent; border: none;")
            c0.installEventFilter(scroller)
            self._chart_stack.addWidget(c0)
            self._toolbar_stack.addWidget(ChartToolbar(c0, self))
            self._plotters.append(p0)

            if _nested_ok:
                data1 = _build_nested_pie_data(self._results)
                if data1:
                    p1 = SustainabilityCircularPlotter(data1, currency=self._currency)
                    c1 = FigureCanvasQTAgg(p1.setup_plot())
                    c1.setMinimumHeight(400); c1.setMaximumHeight(500)
                    c1.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                    c1.setStyleSheet("background: transparent; border: none;")
                    c1.installEventFilter(scroller)
                    self._chart_stack.addWidget(c1)
                    self._toolbar_stack.addWidget(ChartToolbar(c1, self))
                    self._plotters.append(p1)

            # Pillar totals bar chart (bar + no stage)
            pillar_bar_data = _build_pillar_total_data(self._results)
            self._bar_chart_idx = -1
            if pillar_bar_data:
                p_bar = StageBarPlotter(pillar_bar_data, currency=self._currency)
                c_bar = FigureCanvasQTAgg(p_bar.setup_plot())
                c_bar.setMinimumHeight(400); c_bar.setMaximumHeight(500)
                c_bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                c_bar.setStyleSheet("background: transparent; border: none;")
                c_bar.installEventFilter(scroller)
                self._bar_chart_idx = self._chart_stack.count()
                self._chart_stack.addWidget(c_bar)
                self._toolbar_stack.addWidget(ChartToolbar(c_bar, self))

            # Pillar-x breakdown bar chart (bar + stage): Eco/Env/Soc on x, stacked by stage
            stage_bar_data = _build_pillar_bar_data(self._results)
            self._stage_bar_chart_idx = -1
            if stage_bar_data:
                p_sbar = PillarBreakdownBarPlotter(stage_bar_data, currency=self._currency)
                c_sbar = FigureCanvasQTAgg(p_sbar.setup_plot())
                c_sbar.setMinimumHeight(400); c_sbar.setMaximumHeight(500)
                c_sbar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                c_sbar.setStyleSheet("background: transparent; border: none;")
                c_sbar.installEventFilter(scroller)
                self._stage_bar_chart_idx = self._chart_stack.count()
                self._chart_stack.addWidget(c_sbar)
                self._toolbar_stack.addWidget(ChartToolbar(c_sbar, self))

            self._bar_cb = QCheckBox("Change to bar chart")
            self._bar_cb.setFont(_f(FS_BASE))
            self._bar_cb.setStyleSheet(f"color: {get_token('text_secondary')}; background: transparent; border: none;")
            self._bar_cb.setVisible(self._bar_chart_idx >= 0)
            left_v.addWidget(self._bar_cb, 0, Qt.AlignCenter)

            def _switch_chart():
                bar   = self._bar_cb.isChecked()
                stage = self._stage_cb.isChecked()
                if bar and stage and self._stage_bar_chart_idx >= 0:
                    idx = self._stage_bar_chart_idx   # stacked pillar bar per stage
                elif bar and self._bar_chart_idx >= 0:
                    idx = self._bar_chart_idx          # simple pillar totals bar
                elif stage and _nested_ok:
                    idx = 1                            # nested donut
                else:
                    idx = 0                            # simple pillar donut
                self._chart_stack.setCurrentIndex(idx)
                self._toolbar_stack.setCurrentIndex(idx)

            self._stage_cb.toggled.connect(lambda _: _switch_chart())
            self._bar_cb.toggled.connect(lambda _: _switch_chart())

            chart_cont = QWidget()
            chart_cont.setStyleSheet("background: transparent; border: none;")
            cv = QVBoxLayout(chart_cont)
            cv.setContentsMargins(0, 0, 0, 0)
            cv.setSpacing(0)
            cv.addWidget(self._chart_stack)
            cv.addWidget(self._toolbar_stack)
            self._content_h.addWidget(chart_cont, 2)

        card_v.addWidget(content_row)

        if not _pillar_ok:
            _note = QLabel("* Negative cost values detected- pie chart unavailable, showing bar chart instead.")
            _note.setAlignment(Qt.AlignCenter)
            _note.setWordWrap(True)
            _note.setFont(_f(FS_XS, FW_NORMAL, italic=True))
            _note.setStyleSheet(f"color: {get_token('text_secondary')}; border: none; background: transparent;")
            card_v.addWidget(_note)

        self._main_v.addWidget(self.card)

    def _on_mode_change(self, is_percentage: bool):
        for p in self._plotters:
            if p is not None:
                p.set_mode(is_percentage)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if event.size().width() < 850:
            self._content_h.setDirection(QBoxLayout.Direction.TopToBottom)
            self._left_panel.setMinimumWidth(0)
            self._left_panel.setMaximumWidth(16777215)
        else:
            self._content_h.setDirection(QBoxLayout.Direction.LeftToRight)
            self._left_panel.setFixedWidth(350)

    def minimumSizeHint(self):
        return QSize(0, 400)
