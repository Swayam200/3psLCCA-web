"""
gui/components/outputs/comparison_page.py

Side-by-side LCCA project comparison.

Flow:
  1. Page scans projects with fit_for_comparison=True via list_all_projects().
  2. User picks ≥2 projects, optionally sets a common analysis period.
  3. Workers re-run run_full_lcc_analysis from the cached all_data + lcc_breakdown.
  4. Results are shown in a KPI table + grouped bar chart.

Reading the comparison_cache from disk without opening an engine instance keeps
other projects' locks untouched and avoids the overhead of a full engine attach.
"""

import json
import os
import traceback
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("QtAgg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
except ImportError:
    from matplotlib.backends.backend_qt import FigureCanvasQTAgg, NavigationToolbar2QT

from matplotlib import font_manager as _fm

from PySide6.QtCore import Qt, QObject, QThread, QTimer, Signal, QSize
from PySide6.QtGui import QPixmap, QPainter, QColor
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QProgressBar,
    QPushButton, QScrollArea, QSizePolicy, QSpinBox, QVBoxLayout, QWidget,
    QCheckBox,
)

from three_ps_lcca_gui.gui.themes import get_token, theme_manager
from three_ps_lcca_gui.gui.styles import font as _f, btn_primary, btn_ghost
from three_ps_lcca_gui.gui.theme import (
    SP1, SP2, SP3, SP4, SP5, SP6, SP8, SP10,
    RADIUS_LG, RADIUS_MD,
    FS_XS, FS_SM, FS_BASE, FS_MD, FS_LG, FS_SUBHEAD, FS_DISP,
    FW_NORMAL, FW_MEDIUM, FW_SEMIBOLD, FW_BOLD,
    BTN_SM, BTN_MD, BTN_LG, FONT_FAMILY,
)
from three_ps_lcca_gui.core.safechunk_engine import SafeChunkEngine, _decode, LCCA_EXT
import three_ps_lcca_gui.core.start_manager as _sm
from three_ps_lcca_core.core.main import run_full_lcc_analysis
from three_ps_lcca_gui.gui.components.utils.display_format import fmt_currency
from .data_preparer import DataPreparer
from .helper_functions.lifecycle_summary import compute_all_summaries
from .helper_functions.lcc_colors import COLORS as LCC_PALETTE

# ── Register Ubuntu fonts for matplotlib ──────────────────────────────────────
_UBUNTU_FONT_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "assets", "themes", "Ubuntu_font")
)
for _ttf in ["Ubuntu-Regular.ttf", "Ubuntu-Medium.ttf", "Ubuntu-Bold.ttf"]:
    _path = os.path.join(_UBUNTU_FONT_DIR, _ttf)
    if os.path.exists(_path):
        _fm.fontManager.addfont(_path)
matplotlib.rcParams["font.family"] = FONT_FAMILY

# ── Constants ─────────────────────────────────────────────────────────────────
CHUNK_COMPARISON = "comparison_cache"

_GUI_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_ASSETS_DIR = os.path.join(_GUI_DIR, "assets")

_STAGE_KEYS   = ["initial", "use_reconstruction", "end_of_life"]
_STAGE_LABELS = ["Initial Construction", "Use & Maintenance", "End of Life"]
_STAGE_COLORS = [
    LCC_PALETTE.get("init_color", "#CCCCCC"),
    LCC_PALETTE.get("use_color",  "#00C49A"),
    LCC_PALETTE.get("end_color",  "#EA9E9E"),
]

# Cycles for unlimited projects
_PROJECT_COLORS = [
    "#4C72B0", "#DD8452", "#55A868", "#C44E52", "#8172B3",
    "#CCB974", "#64B5CD", "#E377C2", "#7F7F7F", "#BCBD22",
]


# ──────────────────────────────────────────────────────────────────────────────
# Date helper
# ──────────────────────────────────────────────────────────────────────────────

def _fmt_date(dt_str: str) -> str:
    try:
        dt = datetime.fromisoformat(dt_str[:19])
    except (ValueError, TypeError):
        return dt_str[:10] if dt_str else ""
    now  = datetime.now()
    diff = now - dt
    secs = int(diff.total_seconds())
    if secs < 60:       return "Just now"
    if secs < 3600:     return f"{secs // 60}m ago"
    if secs < 86400:    return f"{secs // 3600}h ago"
    if secs < 172800:   return "Yesterday"
    if secs < 604800:   return f"{secs // 86400} days ago"
    fmt = "%b %d" if dt.year == now.year else "%b %d, %Y"
    return dt.strftime(fmt)


# ──────────────────────────────────────────────────────────────────────────────
# Disk helper - read cache without opening an engine
# ──────────────────────────────────────────────────────────────────────────────

def _read_cache_from_disk(base_dir: Path, project_id: str) -> dict:
    chunk_path = base_dir / project_id / "chunks" / f"{CHUNK_COMPARISON}{LCCA_EXT}"
    if not chunk_path.exists():
        return {}
    try:
        return _decode(chunk_path.read_bytes())
    except Exception:
        return {}


# ──────────────────────────────────────────────────────────────────────────────
# Background worker - one per project
# ──────────────────────────────────────────────────────────────────────────────

class _ComparisonWorker(QThread):
    """
    Subclasses QThread directly - avoids moveToThread + deleteLater fragility.
    The thread IS the worker; no separate QObject needed.
    """
    finished = Signal(str, object)   # (project_id, results_dict)
    errored  = Signal(str, str)      # (project_id, error_message)

    def __init__(self, project_id: str, all_data: dict,
                 lcc_breakdown: dict, analysis_period: int):
        super().__init__()
        self._project_id    = project_id
        self._all_data      = all_data
        self._lcc_breakdown = lcc_breakdown
        self._ap            = analysis_period
        self._cancel        = False

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            if self._cancel:
                return
            is_global, data_obj = DataPreparer.prepare_data_object(self._all_data, self._ap)
            if self._cancel:
                return
            wpi = None
            if not is_global:
                wpi = DataPreparer.prepare_wpi_object(self._all_data)
            if self._cancel:
                return
            results = run_full_lcc_analysis(
                data_obj, self._lcc_breakdown, wpi=wpi, debug=True
            )
            self.finished.emit(self._project_id, results)
        except Exception as exc:
            self.errored.emit(self._project_id, str(exc))


# ──────────────────────────────────────────────────────────────────────────────
# Project picker card
# ──────────────────────────────────────────────────────────────────────────────

class _ProjectCard(QFrame):
    selection_changed = Signal(str, bool)   # (project_id, is_selected)
    return_requested  = Signal(str)         # project_id

    def __init__(self, project_id: str, display_name: str,
                 analysis_period: int, currency: str, is_locked: bool = False, parent=None):
        super().__init__(parent)
        self._project_id = project_id
        self._selected   = False
        self._is_locked  = is_locked
        self._build(display_name, analysis_period, currency)
        # Even if locked, we want the cursor to change if the user hovers over the card/button area
        self.setCursor(Qt.PointingHandCursor)
        self._apply_style()

    def _build(self, name: str, ap: int, currency: str):
        self.setObjectName("projCard")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(SP4, SP3, SP4, SP3)
        lay.setSpacing(SP3)

        self._check = QFrame()
        self._check.setFixedSize(16, 16)
        self._check.setObjectName("checkBox")
        lay.addWidget(self._check, 0, Qt.AlignVCenter)
        if self._is_locked:
            self._check.hide()

        info = QVBoxLayout()
        info.setSpacing(2)
        info.setContentsMargins(0, 0, 0, 0)

        self._name_lbl = QLabel(name)
        self._name_lbl.setFont(_f(FS_BASE, FW_SEMIBOLD))
        info.addWidget(self._name_lbl)

        self._meta_lbl = QLabel(f"{ap} years  ·  {currency}")
        self._meta_lbl.setFont(_f(FS_SM))
        self._meta_lbl.setStyleSheet(f"color: {get_token('text_secondary')};")
        info.addWidget(self._meta_lbl)

        lay.addLayout(info, 1)

        if self._is_locked:
            self._ret_btn = QPushButton("Return ›")
            self._ret_btn.setObjectName("retBtn")
            self._ret_btn.setFixedSize(64, 22)
            self._ret_btn.setFont(_f(FS_SM, FW_MEDIUM))
            self._ret_btn.setCursor(Qt.PointingHandCursor)
            self._ret_btn.clicked.connect(lambda: self.return_requested.emit(self._project_id))
            lay.addWidget(self._ret_btn, 0, Qt.AlignVCenter)

    def _apply_style(self):
        prim = get_token("primary")
        base = get_token("base")
        hov  = QColor(prim).darker(110).name()

        if self._is_locked:
            border = get_token("surface_mid")
            bg     = get_token("surface_mid")
            text_col     = get_token("text_disabled")
            meta_col     = get_token("info")
        elif self._selected:
            border = get_token("primary")
            bg     = get_token("surface")
            text_col     = get_token("primary")
            meta_col     = get_token("text_secondary")
        else:
            border = get_token("surface_mid")
            bg     = "transparent"
            text_col     = get_token("text")
            meta_col     = get_token("text_secondary")

        # Set unified stylesheet on the card to ensure correct cascading for the child button
        self.setStyleSheet(
            f"#projCard {{ border: 2px solid {border}; "
            f"border-radius: {RADIUS_LG}px; background: {bg}; }}"
            f"#projCard QLabel {{ background: transparent; }}"
            f"#retBtn {{ background: transparent; color: {prim}; border: 1px solid {prim}; "
            f"border-radius: 11px; padding: 0; }}"
            f"#retBtn:hover {{ background: {prim}; color: {base}; }}"
            f"#retBtn:pressed {{ background: {hov}; color: {base}; }}"
        )

        if not self._is_locked:
            check_bg     = get_token("primary") if self._selected else "transparent"
            check_border = get_token("primary") if self._selected else get_token("surface_mid")
            self._check.setStyleSheet(
                f"#checkBox {{ border: 2px solid {check_border}; "
                f"border-radius: 3px; background: {check_bg}; }}"
            )

        self._name_lbl.setStyleSheet(f"color: {text_col};")
        self._meta_lbl.setStyleSheet(f"color: {meta_col};")

    def mousePressEvent(self, event):
        if self._is_locked:
            return
        self._selected = not self._selected
        self._apply_style()
        self.selection_changed.emit(self._project_id, self._selected)
        if event:
            super().mousePressEvent(event)

    @property
    def selected(self) -> bool:
        return self._selected

    @property
    def project_id(self) -> str:
        return self._project_id


# ──────────────────────────────────────────────────────────────────────────────
# KPI comparison table
# ──────────────────────────────────────────────────────────────────────────────

class _KPITable(QWidget):
    """
    Rows = metrics, Columns = projects.
    Best (lowest cost) value per row is highlighted with a green dot.
    """

    def __init__(self, ordered_pids: list[str], display_names: list[str],
                 summaries: dict[str, dict], caches: dict[str, dict],
                 currency: str, parent=None):
        super().__init__(parent)
        self._build(ordered_pids, display_names, summaries, caches, currency)

    def _build(self, pids, names, summaries, caches, currency):
        grid = QGridLayout(self)
        grid.setSpacing(0)
        grid.setContentsMargins(0, 0, 0, 0)

        # ── Column headers ────────────────────────────────────────────────────
        corner = QLabel("Metric")
        corner.setFont(_f(FS_SM, FW_SEMIBOLD))
        corner.setStyleSheet(
            f"color: {get_token('text_secondary')}; "
            f"padding: {SP2}px {SP4}px; "
            f"background: {get_token('surface_mid')};"
        )
        grid.addWidget(corner, 0, 0)

        for col, (pid, name) in enumerate(zip(pids, names), start=1):
            color = _PROJECT_COLORS[(col - 1) % len(_PROJECT_COLORS)]
            lbl = QLabel(name)
            lbl.setFont(_f(FS_SM, FW_SEMIBOLD))
            lbl.setWordWrap(True)
            lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            lbl.setStyleSheet(
                f"color: {color}; padding: {SP2}px {SP4}px; "
                f"background: {get_token('surface_mid')};"
            )
            grid.addWidget(lbl, 0, col)

        # ── Row definitions ───────────────────────────────────────────────────
        def _total(pid):
            sw = summaries[pid]["stagewise"]
            return sum(sw.values())

        rows = [
            ("Total LCCA (NPV)",           lambda pid: _total(pid),                                  True),
            ("Initial Construction",        lambda pid: summaries[pid]["stagewise"]["initial"],        True),
            ("Use & Maintenance",           lambda pid: summaries[pid]["stagewise"]["use_reconstruction"], True),
            ("End of Life",                 lambda pid: summaries[pid]["stagewise"]["end_of_life"],    True),
            ("Economic Pillar",             lambda pid: summaries[pid]["pillar_totals"]["eco"],        True),
            ("Environmental Pillar",        lambda pid: summaries[pid]["pillar_totals"]["env"],        True),
            ("Social Pillar",               lambda pid: summaries[pid]["pillar_totals"]["social"],     True),
            ("Analysis Period",             lambda pid: caches[pid].get("analysis_period", "-"),      False),
        ]

        for row, (label, fn, is_cost) in enumerate(rows, start=1):
            is_total = row == 1
            row_bg = get_token("surface") if row % 2 == 0 else "transparent"
            sep_top = f"border-top: 1px solid {get_token('surface_mid')};" if is_total else ""

            metric_lbl = QLabel(label)
            metric_lbl.setFont(_f(FS_BASE, FW_BOLD if is_total else FW_NORMAL))
            metric_lbl.setStyleSheet(
                f"color: {get_token('text_secondary')}; padding: {SP2}px {SP4}px; "
                f"background: {row_bg}; {sep_top}"
            )
            grid.addWidget(metric_lbl, row, 0)

            # Compute values for all projects
            values = {}
            for pid in pids:
                try:
                    values[pid] = fn(pid)
                except Exception:
                    values[pid] = 0.0

            # Find best (minimum cost)
            best_pid = None
            if is_cost and len(pids) > 1:
                numeric = {p: v for p, v in values.items() if isinstance(v, (int, float))}
                if numeric:
                    best_pid = min(numeric, key=numeric.get)

            for col, pid in enumerate(pids, start=1):
                val = values[pid]
                is_best = (pid == best_pid)

                cell = QWidget()
                cell.setStyleSheet(f"background: {row_bg}; {sep_top}")
                cell_h = QHBoxLayout(cell)
                cell_h.setContentsMargins(SP3, SP2, SP4, SP2)
                cell_h.setSpacing(SP1)
                cell_h.addStretch()

                if is_cost and is_best:
                    dot_wrap = QWidget()
                    dot_wrap.setStyleSheet("background: transparent;")
                    dv = QVBoxLayout(dot_wrap)
                    dv.setContentsMargins(0, 0, 0, 0)
                    dv.addStretch()
                    dot = QFrame()
                    dot.setFixedSize(6, 6)
                    dot.setStyleSheet(
                        f"background: {get_token('success')}; border-radius: 3px;"
                    )
                    dv.addWidget(dot)
                    dv.addStretch()
                    cell_h.addWidget(dot_wrap)

                if is_cost:
                    text = fmt_currency(val, currency, decimals=0, style="both")
                elif isinstance(val, int):
                    text = f"{val} yrs"
                else:
                    text = str(val)

                val_lbl = QLabel(text)
                val_lbl.setFont(_f(FS_BASE, FW_BOLD if is_total else FW_NORMAL))
                val_lbl.setStyleSheet(
                    f"color: {get_token('success') if is_best and is_cost else get_token('text')}; "
                    f"background: transparent;"
                )
                val_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
                cell_h.addWidget(val_lbl)

                if is_cost and best_pid and pid != best_pid:
                    best_val = values[best_pid]
                    if isinstance(best_val, (int, float)) and best_val > 0:
                        delta = ((val - best_val) / best_val) * 100
                        delta_lbl = QLabel(f"+{delta:.1f}%" if delta > 0 else f"{delta:.1f}%")
                        delta_lbl.setFont(_f(FS_XS, FW_MEDIUM))
                        delta_lbl.setStyleSheet(f"color: {get_token('text_secondary')}; background: transparent;")
                        cell_h.addWidget(delta_lbl)

                grid.addWidget(cell, row, col)

        grid.setColumnStretch(0, 3)
        for c in range(1, len(pids) + 1):
            grid.setColumnStretch(c, 2)


# ──────────────────────────────────────────────────────────────────────────────
# Grouped bar chart - stages × projects
# ──────────────────────────────────────────────────────────────────────────────

class _ComparisonChart(QWidget):
    """
    Grouped bar chart: x = life cycle stage, bars within group = projects.
    Each project gets a distinct color; stage groups are visually separated.
    """

    def __init__(self, ordered_pids: list[str], display_names: list[str],
                 summaries: dict[str, dict], currency: str, parent=None):
        super().__init__(parent)
        self._pids      = ordered_pids
        self._names     = display_names
        self._summaries = summaries
        self._currency  = currency
        self._visible_stages = list(_STAGE_KEYS)
        self._fig       = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self._build()
        theme_manager().theme_changed.connect(self._rebuild)

    def update_stages(self, stages: list[str]):
        """Update chart to show only selected life cycle stages."""
        self._visible_stages = stages
        self._rebuild()

    def _rebuild(self):
        if self._fig:
            plt.close(self._fig)
            self._fig = None
        while self.layout().count():
            item = self.layout().takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._build()

    def _build(self):
        text_color = get_token("text")
        bg_color   = get_token("window")
        mid_color  = get_token("surface_mid")

        # Filter stages based on interactive selection
        indices = [i for i, k in enumerate(_STAGE_KEYS) if k in self._visible_stages]
        labels  = [_STAGE_LABELS[i] for i in indices]
        n_stages = len(indices)
        
        if n_stages == 0:
            msg = QLabel("No stages selected.")
            msg.setAlignment(Qt.AlignCenter)
            msg.setStyleSheet(f"color: {get_token('text_disabled')};")
            self.layout().addWidget(msg)
            return

        n_projects = len(self._pids)
        bar_w      = 0.7 / max(1, n_projects)
        x          = np.arange(n_stages)

        fig, ax = plt.subplots(figsize=(max(5, n_stages * 2.5), 4.5))
        fig.patch.set_facecolor(bg_color)
        ax.set_facecolor(bg_color)
        self._fig = fig

        legend_patches = []
        for i, (pid, name) in enumerate(zip(self._pids, self._names)):
            sw  = self._summaries[pid]["stagewise"]
            # Extract only the visible stage values
            vals = np.array([sw.get(_STAGE_KEYS[idx], 0) / 1_000_000 for idx in indices])
            
            offset = (i - (n_projects - 1) / 2) * bar_w
            color  = _PROJECT_COLORS[i % len(_PROJECT_COLORS)]
            ax.bar(x + offset, vals, bar_w, color=color, label=name,
                   edgecolor=bg_color, linewidth=0.5)
            legend_patches.append(
                mpatches.Patch(color=color, label=name)
            )

        ax.set_xticks(x)
        ax.set_xticklabels(labels, color=text_color,
                           fontsize=8, fontfamily=FONT_FAMILY)
        ax.set_ylabel(f"Cost  (Million {self._currency})",
                      color=text_color, fontsize=8, fontfamily=FONT_FAMILY)
        ax.tick_params(colors=text_color, labelsize=8)
        for spine in ax.spines.values():
            spine.set_color(mid_color)
        ax.yaxis.set_tick_params(color=mid_color)
        ax.xaxis.set_tick_params(color=mid_color)
        ax.set_title("Life-Cycle Cost Breakdown  (NPV)",
                     color=text_color, fontsize=10, fontfamily=FONT_FAMILY, pad=10)

        ax.legend(handles=legend_patches, fontsize=8, facecolor=bg_color,
                  labelcolor=text_color, framealpha=0.85,
                  edgecolor=mid_color, loc="upper right")
        fig.tight_layout(pad=1.5)

        class _ChartToolbar(NavigationToolbar2QT):
            toolitems = [t for t in NavigationToolbar2QT.toolitems
                         if t[0] not in ("Subplots", "Customize")]
            def set_message(self, s): pass

        canvas = FigureCanvasQTAgg(fig)
        canvas.setMinimumHeight(340)
        canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        canvas.wheelEvent = lambda event: event.ignore()
        toolbar = _ChartToolbar(canvas, self)

        self.layout().addWidget(toolbar)
        self.layout().addWidget(canvas)


# ──────────────────────────────────────────────────────────────────────────────
# Standalone result window - one per confirmed comparison group
# ──────────────────────────────────────────────────────────────────────────────

class ComparisonResultWindow(QWidget):
    """
    Opened by ComparisonPickerPanel when the user confirms a group.
    Runs workers, shows KPI table + chart. No picker inside.
    """

    def __init__(self, pids: list, names: list, caches: dict,
                 override_ap: int, parent=None):
        super().__init__(parent, Qt.Window)
        label = "  ·  ".join(sorted(names))
        self.setWindowTitle(f"Comparison: {label}")
        self.setMinimumSize(980, 680)

        self._pids       = pids
        self._names      = names        # parallel to pids
        self._caches     = caches
        self._override_ap = override_ap
        self._results: dict = {}
        self._errors:  dict = {}
        self._pending: set  = set()
        self._workers: dict = {}
        self._currency = caches[pids[0]].get("currency", "INR") if pids else "INR"

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self._body = QWidget()
        self._body_layout = QVBoxLayout(self._body)
        self._body_layout.setContentsMargins(SP6, SP5, SP6, SP5)
        self._body_layout.setSpacing(SP4)
        scroll.setWidget(self._body)
        outer.addWidget(scroll)

        self._show_running()
        self._start_workers()
        theme_manager().theme_changed.connect(self._on_theme)

    # ── helpers ───────────────────────────────────────────────────────────────

    def _clear_body(self):
        while self._body_layout.count():
            item = self._body_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _section_heading(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setFont(_f(FS_LG, FW_BOLD))
        lbl.setStyleSheet(f"color: {get_token('text')};")
        return lbl

    def _banner(self, text: str, token: str) -> QWidget:
        outer = QWidget()
        h = QHBoxLayout(outer)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        strip = QFrame()
        strip.setFixedWidth(3)
        strip.setStyleSheet(f"background: {get_token(token)}; border-radius: 2px;")
        h.addWidget(strip)
        inner = QFrame()
        inner.setStyleSheet("QFrame { background: transparent; border: none; }")
        v = QVBoxLayout(inner)
        v.setContentsMargins(SP3, SP2, SP3, SP2)
        lbl = QLabel(text)
        lbl.setFont(_f(FS_BASE))
        lbl.setWordWrap(True)
        lbl.setStyleSheet(f"color: {get_token('text')}; background: transparent;")
        v.addWidget(lbl)
        h.addWidget(inner, 1)
        return outer

    def _on_theme(self):
        pass   # _ComparisonChart rebuilds itself; static labels stay readable

    # ── running state ─────────────────────────────────────────────────────────

    def _show_running(self):
        self._clear_body()
        self._progress_status: dict = {}

        hdr = QLabel("Running Analysis…")
        hdr.setFont(_f(FS_LG, FW_BOLD))
        hdr.setStyleSheet(f"color: {get_token('text')};")
        self._body_layout.addWidget(hdr)

        for pid, name in zip(self._pids, self._names):
            row = QWidget()
            row_h = QHBoxLayout(row)
            row_h.setContentsMargins(0, 0, 0, 0)
            row_h.setSpacing(SP3)

            name_lbl = QLabel(name)
            name_lbl.setFont(_f(FS_BASE, FW_MEDIUM))
            name_lbl.setFixedWidth(220)
            row_h.addWidget(name_lbl)

            bar = QProgressBar()
            bar.setRange(0, 0)
            bar.setTextVisible(False)
            bar.setFixedHeight(6)
            row_h.addWidget(bar, 1)

            status = QLabel("Running…")
            status.setFont(_f(FS_SM))
            status.setStyleSheet(f"color: {get_token('text_secondary')};")
            status.setFixedWidth(70)
            row_h.addWidget(status)

            self._progress_status[pid] = status
            self._body_layout.addWidget(row)

        self._body_layout.addStretch()

    # ── workers ───────────────────────────────────────────────────────────────

    def _start_workers(self):
        self._pending = set(self._pids)
        for pid in self._pids:
            cache = self._caches[pid]
            ap = self._override_ap if self._override_ap > 0 \
                 else cache.get("analysis_period", 50)
            worker = _ComparisonWorker(
                pid, cache.get("all_data", {}), cache.get("lcc_breakdown", {}), ap
            )
            worker.finished.connect(self._on_finished)
            worker.errored.connect(self._on_errored)
            self._workers[pid] = worker
            worker.start()

    def _on_finished(self, pid: str, results: dict):
        self._results[pid] = results
        self._pending.discard(pid)
        if pid in self._progress_status:
            self._progress_status[pid].setText("Done")
            self._progress_status[pid].setStyleSheet(f"color: {get_token('success')};")
        if not self._pending:
            self._drain_workers()
            QTimer.singleShot(0, self._show_results)

    def _on_errored(self, pid: str, error: str):
        self._errors[pid] = error
        self._pending.discard(pid)
        if pid in self._progress_status:
            self._progress_status[pid].setText("Failed")
            self._progress_status[pid].setStyleSheet(f"color: {get_token('danger')};")
        if not self._pending:
            self._drain_workers()
            QTimer.singleShot(0, self._show_results)

    def _drain_workers(self):
        """Wait for every thread to exit then drop Python references."""
        for worker in self._workers.values():
            worker.wait()   # blocks briefly - thread has already emitted its signal
        self._workers.clear()

    def _on_stage_filter_changed(self):
        visible = [k for k, cb in self._stage_checks.items() if cb.isChecked()]
        self._chart.update_stages(visible)

    def _show_results(self):
        self._clear_body()

        for pid, err in self._errors.items():
            idx = self._pids.index(pid)
            self._body_layout.addWidget(
                self._banner(f"{self._names[idx]}: {err}", "danger")
            )

        if not self._results:
            self._body_layout.addWidget(
                self._banner("All analyses failed - no results to display.", "danger")
            )
            self._body_layout.addStretch()
            return

        pids  = [p for p in self._pids if p in self._results]
        names = [self._names[self._pids.index(p)] for p in pids]

        # Period line
        if self._override_ap > 0:
            period_text = f"All projects analysed at a {self._override_ap}-year horizon."
        else:
            parts = [
                f"{n}: {self._caches[p].get('analysis_period', '?')} yrs"
                for p, n in zip(pids, names)
            ]
            period_text = "Analysis periods - " + "  ·  ".join(parts)
        period_lbl = QLabel(period_text)
        period_lbl.setFont(_f(FS_SM))
        period_lbl.setWordWrap(True)
        period_lbl.setStyleSheet(f"color: {get_token('text_secondary')};")
        self._body_layout.addWidget(period_lbl)

        summaries = {p: compute_all_summaries(self._results[p]) for p in pids}

        # KPI table
        self._body_layout.addWidget(self._section_heading("Cost Summary"))
        table_card = QFrame()
        table_card.setObjectName("compTableCard")
        table_card.setStyleSheet(
            f"#compTableCard {{ background: {get_token('surface')}; "
            f"border: 1px solid {get_token('surface_mid')}; "
            f"border-radius: {RADIUS_LG}px; }}"
        )
        tc_lay = QVBoxLayout(table_card)
        tc_lay.setContentsMargins(0, 0, 0, 0)
        tc_lay.addWidget(
            _KPITable(pids, names, summaries,
                      {p: self._caches[p] for p in pids}, self._currency)
        )
        self._body_layout.addWidget(table_card)

        # Color legend
        legend_row = QWidget()
        lr_h = QHBoxLayout(legend_row)
        lr_h.setContentsMargins(SP2, 0, 0, 0)
        lr_h.setSpacing(SP4)
        for i, name in enumerate(names):
            color = _PROJECT_COLORS[i % len(_PROJECT_COLORS)]
            dot = QFrame()
            dot.setFixedSize(10, 10)
            dot.setStyleSheet(f"background: {color}; border-radius: 5px;")
            lbl = QLabel(name)
            lbl.setFont(_f(FS_SM))
            lbl.setStyleSheet(f"color: {get_token('text_secondary')};")
            dot_wrap = QWidget()
            dw_h = QHBoxLayout(dot_wrap)
            dw_h.setContentsMargins(0, 0, 0, 0)
            dw_h.setSpacing(SP1)
            dw_h.addWidget(dot)
            dw_h.addWidget(lbl)
            lr_h.addWidget(dot_wrap)
        lr_h.addStretch()
        self._body_layout.addWidget(legend_row)

        # Interactive Chart Section
        self._body_layout.addWidget(self._section_heading("Stage Breakdown"))
        
        filter_row = QHBoxLayout()
        filter_row.setContentsMargins(SP2, 0, 0, 0)
        filter_row.setSpacing(SP6)
        
        self._stage_checks = {}
        for key, label in zip(_STAGE_KEYS, _STAGE_LABELS):
            cb = QCheckBox(label)
            cb.setChecked(True)
            cb.setFont(_f(FS_SM, FW_MEDIUM))
            cb.setStyleSheet(f"color: {get_token('text_secondary')};")
            cb.setCursor(Qt.PointingHandCursor)
            cb.stateChanged.connect(lambda: self._on_stage_filter_changed())
            filter_row.addWidget(cb)
            self._stage_checks[key] = cb
        filter_row.addStretch()
        self._body_layout.addLayout(filter_row)

        self._chart = _ComparisonChart(pids, names, summaries, self._currency)
        self._body_layout.addWidget(self._chart)
        self._body_layout.addStretch()


# ──────────────────────────────────────────────────────────────────────────────
# Embedded picker panel - lives inside the home page stack
# ──────────────────────────────────────────────────────────────────────────────

class ComparisonPickerPanel(QWidget):
    """
    Embedded in the home page (QStackedWidget page 1).
    Manages project selection, launches ComparisonResultWindows, tracks history.
    """

    def __init__(self, manager=None, parent=None):
        super().__init__(parent)
        self.manager = manager
        self._open_windows: dict[frozenset, "ComparisonResultWindow"] = {}
        self._selected_pids: set[str] = set()
        self._picker_cards: dict[str, _ProjectCard] = {}
        self._on_disk_pids: set[str] = set()

        self._build()
        theme_manager().theme_changed.connect(self._on_theme)

    # ── shell ─────────────────────────────────────────────────────────────────

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        body = QWidget()
        self._body_layout = QVBoxLayout(body)
        self._body_layout.setContentsMargins(SP6, SP5, SP6, SP5)
        self._body_layout.setSpacing(SP4)
        scroll.setWidget(body)
        outer.addWidget(scroll)

        # Main Header
        self._header = QLabel("LCCA Comparison")
        self._header.setFont(_f(FS_DISP, FW_BOLD))
        self._header.setStyleSheet(f"color: {get_token('text')};")
        self._body_layout.addWidget(self._header)

        # ── Active Picker Section ─────────────────────────────────────────────
        picker_header = QLabel("Select Projects to Compare")
        picker_header.setFont(_f(FS_LG, FW_SEMIBOLD))
        picker_header.setStyleSheet(f"color: {get_token('text_secondary')};")
        self._body_layout.addWidget(picker_header)

        self._picker_container = QWidget()
        self._picker_layout = QGridLayout(self._picker_container)
        self._picker_layout.setContentsMargins(0, 0, 0, 0)
        self._picker_layout.setSpacing(SP3)
        self._body_layout.addWidget(self._picker_container)

        # Run Button Row
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        
        self._run_btn = QPushButton("Run Comparison ↗")
        self._run_btn.setFixedHeight(BTN_LG)
        self._run_btn.setMinimumWidth(200)
        self._run_btn.setFont(_f(FS_BASE, FW_BOLD))
        self._run_btn.setEnabled(False)
        self._run_btn.setCursor(Qt.PointingHandCursor)
        self._run_btn.setStyleSheet(btn_ghost())
        self._run_btn.clicked.connect(self._run_active_comparison)
        btn_row.addWidget(self._run_btn)
        btn_row.addStretch()
        self._body_layout.addLayout(btn_row)

        # ── History Section ───────────────────────────────────────────────────
        self._hist_sep = self._hline()
        self._hist_sep.hide()
        self._body_layout.addWidget(self._hist_sep)

        hist_header_row = QHBoxLayout()
        hist_header_row.setContentsMargins(0, 0, 0, 0)

        self._hist_header = QLabel("Comparison History")
        self._hist_header.setFont(_f(FS_LG, FW_SEMIBOLD))
        self._hist_header.setStyleSheet(f"color: {get_token('text')};")
        self._hist_header.hide()
        hist_header_row.addWidget(self._hist_header)
        
        hist_header_row.addStretch()

        self._clear_all_btn = QPushButton("Clear All")
        self._clear_all_btn.setFixedHeight(24)
        self._clear_all_btn.setFont(_f(FS_SM, FW_MEDIUM))
        self._clear_all_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {get_token('danger')}; "
            f"border: 1px solid {get_token('surface_mid')}; border-radius: 12px; "
            f"padding: 0 12px; }}"
            f"QPushButton:hover {{ background: {get_token('danger')}; color: {get_token('base')}; "
            f"border-color: {get_token('danger')}; }}"
        )
        self._clear_all_btn.setCursor(Qt.PointingHandCursor)
        self._clear_all_btn.hide()
        self._clear_all_btn.clicked.connect(self._clear_all_history)
        hist_header_row.addWidget(self._clear_all_btn)

        self._body_layout.addLayout(hist_header_row)

        # Empty State
        self._empty_state = QWidget()
        ev = QVBoxLayout(self._empty_state)
        ev.setContentsMargins(0, SP10, 0, SP10)
        ev.setSpacing(SP4)
        
        empty_lbl = QLabel("No comparisons yet")
        empty_lbl.setFont(_f(FS_LG, FW_MEDIUM))
        empty_lbl.setStyleSheet(f"color: {get_token('text_disabled')};")
        empty_lbl.setAlignment(Qt.AlignCenter)
        ev.addWidget(empty_lbl)
        
        hint_lbl = QLabel("Select at least two projects above to start a side-by-side analysis.")
        hint_lbl.setFont(_f(FS_BASE))
        hint_lbl.setStyleSheet(f"color: {get_token('text_disabled')};")
        hint_lbl.setAlignment(Qt.AlignCenter)
        ev.addWidget(hint_lbl)
        
        self._body_layout.addWidget(self._empty_state)

        self._history_container = QWidget()
        self._history_layout = QVBoxLayout(self._history_container)
        self._history_layout.setContentsMargins(0, 0, 0, 0)
        self._history_layout.setSpacing(SP2)
        self._body_layout.addWidget(self._history_container)

        self._body_layout.addStretch()

        # ── Footer: Sponsors Area ──────────────────────────────────────────
        self.footer = QWidget()
        self.footer.setFixedHeight(120)
        outer.addWidget(self.footer)

        fl = QHBoxLayout(self.footer)
        fl.setContentsMargins(SP10, SP6, SP10, SP6)

        # Developed At Section
        dev_v = QVBoxLayout()
        dev_v.setSpacing(SP3)
        dev_lbl = QLabel("DEVELOPED AT")
        dev_lbl.setFont(_f(FS_XS, FW_BOLD))
        dev_v.addWidget(dev_lbl)
        self.iitb_logo = QLabel()
        dev_v.addWidget(self.iitb_logo, 0, Qt.AlignLeft | Qt.AlignVCenter)
        fl.addLayout(dev_v)

        fl.addStretch()

        # Supported By Section
        sup_v = QVBoxLayout()
        sup_v.setSpacing(SP3)
        sup_v.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        sup_lbl = QLabel("SUPPORTED BY")
        sup_lbl.setFont(_f(FS_XS, FW_BOLD))
        sup_lbl.setAlignment(Qt.AlignRight)
        sup_v.addWidget(sup_lbl)

        sup_h = QHBoxLayout()
        sup_h.setSpacing(SP8)
        sup_h.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.cs_logo = QLabel()
        self.mos_logo = QLabel()
        self.insdag_logo = QLabel()
        sup_h.addWidget(self.cs_logo)
        sup_h.addWidget(self.mos_logo)
        sup_h.addWidget(self.insdag_logo)
        sup_v.addLayout(sup_h)
        fl.addLayout(sup_v)

        self._refresh_footer()

    def _on_theme(self):
        self._header.setStyleSheet(f"color: {get_token('text')};")
        self._refresh_footer()
        self._apply_run_btn_style()

    def _apply_run_btn_style(self):
        if self._run_btn.isEnabled():
            self._run_btn.setStyleSheet(btn_primary())
        else:
            self._run_btn.setStyleSheet(btn_ghost())

    def _set_svg_logo(self, label: QLabel, path: str, height: int):
        """Helper to render a crisp SVG logo into a QLabel with no background."""
        if not os.path.exists(path):
            label.hide()
            return
        label.show()
        label.setStyleSheet("background: transparent; border: none;")
        renderer = QSvgRenderer(path)
        if not renderer.isValid():
            return
        aspect = renderer.defaultSize().width() / max(1, renderer.defaultSize().height())
        width = int(height * aspect)
        pixmap = QPixmap(width * 2, height * 2)  # High DPI
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        label.setPixmap(pixmap)
        label.setFixedSize(width, height)
        label.setScaledContents(True)

    def _set_themed_logo(self, label: QLabel, dark_path: str, light_path: str, height: int, is_dk: bool):
        """Pick dark or light SVG variant based on theme."""
        path = dark_path if is_dk else light_path
        self._set_svg_logo(label, path, height)

    def _refresh_footer(self):
        """Update theme-aware logos and dynamic QSS."""
        from three_ps_lcca_gui.gui.themes import is_dark
        is_dk = is_dark()

        # 1. Footer: Developed At (IITB)
        self._set_themed_logo(
            self.iitb_logo,
            os.path.join(_ASSETS_DIR, "logo", "special", "IITB_logo_dark.svg"),
            os.path.join(_ASSETS_DIR, "logo", "special", "IITB_logo_light.svg"),
            50, is_dk
        )

        # 2. Footer: Supported By (ConstructSteel, MOS, INSDAG)
        self._set_themed_logo(
            self.cs_logo,
            os.path.join(_ASSETS_DIR, "logo", "special", "ConstructSteel_dark.svg"),
            os.path.join(_ASSETS_DIR, "logo", "special", "ConstructSteel_light.svg"),
            20, is_dk
        )
        self._set_themed_logo(
            self.mos_logo,
            os.path.join(_ASSETS_DIR, "logo", "special", "MOS_dark.svg"),
            os.path.join(_ASSETS_DIR, "logo", "special", "MOS_light.svg"),
            40, is_dk
        )
        self._set_themed_logo(
            self.insdag_logo,
            os.path.join(_ASSETS_DIR, "logo", "special", "INSDAG_dark.svg"),
            os.path.join(_ASSETS_DIR, "logo", "special", "INSDAG_light.svg"),
            40, is_dk
        )

        # 3. Style text and background
        muted = f"color: {get_token('text_disabled')}; letter-spacing: 1px;"
        for lbl in self.footer.findChildren(QLabel):
            if lbl.text() in ("DEVELOPED AT", "SUPPORTED BY"):
                lbl.setStyleSheet(muted)

        self.footer.setStyleSheet(f"background: {get_token('surface')}; border: none;")

    @staticmethod
    def _hline() -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Plain)
        line.setStyleSheet("color: palette(mid);")
        line.setFixedHeight(1)
        return line

    # ── public API ────────────────────────────────────────────────────────────

    def refresh(self):
        """Reload both the project picker and history. Called when tab becomes visible."""
        self._render_picker()
        self._render_history()

    def soft_refresh(self):
        self.refresh()

    def is_in_active_comparison(self, pid: str) -> bool:
        """True if pid is in a currently visible ComparisonResultWindow."""
        for project_set, win in self._open_windows.items():
            if pid in project_set and win.isVisible():
                return True
        return False

    def preselect_project(self, pid: str):
        """Force-select a project in the picker (useful for shortcuts from Outputs)."""
        card = self._picker_cards.get(pid)
        if card and not card._is_locked and not card._selected:
            card._selected = True
            card._apply_style()
            self._selected_pids.add(pid)
            self._apply_run_btn_style()

    # ── active picker ─────────────────────────────────────────────────────────

    def _render_picker(self):
        """Build the grid of selectable project cards."""
        while self._picker_layout.count():
            item = self._picker_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        self._selected_pids.clear()
        self._picker_cards.clear()
        self._run_btn.setEnabled(False)
        self._apply_run_btn_style()

        # Build a live availability set from disk
        base = Path(SafeChunkEngine.get_default_base_dir())
        projects = SafeChunkEngine.list_all_projects(str(base))
        self._live_caches: dict[str, dict] = {}
        self._on_disk_pids = {proj["project_id"] for proj in projects}
        
        eligible = []
        for proj in projects:
            if not proj.get("user_meta", {}).get("fit_for_comparison"):
                continue
            cache = _read_cache_from_disk(base, proj["project_id"])
            if cache.get("is_valid"):
                self._live_caches[proj["project_id"]] = cache
                eligible.append(proj)

        if not eligible:
            empty_lbl = QLabel("No projects ready for comparison.\nComplete at least two LCCA analyses first.")
            empty_lbl.setFont(_f(FS_BASE))
            empty_lbl.setStyleSheet(f"color: {get_token('text_disabled')}; padding: {SP4}px;")
            empty_lbl.setAlignment(Qt.AlignCenter)
            self._picker_layout.addWidget(empty_lbl, 0, 0)
            return

        for i, proj in enumerate(eligible):
            pid  = proj["project_id"]
            name = proj["display_name"]
            meta = proj.get("user_meta", {})
            ap   = meta.get("analysis_period", 50)
            curr = meta.get("currency", "INR")
            
            is_open = self.manager.is_project_open(pid) if self.manager else False
            card = _ProjectCard(pid, name, ap, curr, is_locked=is_open)
            card.selection_changed.connect(self._on_picker_selection_changed)
            card.return_requested.connect(lambda pid: self.manager.open_project(project_id=pid))
            
            self._picker_cards[pid] = card
            self._picker_layout.addWidget(card, i // 3, i % 3)

    def _on_picker_selection_changed(self, pid: str, is_selected: bool):
        if is_selected:
            if self.manager and self.manager.is_project_open(pid):
                return
            self._selected_pids.add(pid)
        else:
            self._selected_pids.discard(pid)
        
        can_run = len(self._selected_pids) >= 2
        self._run_btn.setEnabled(can_run)
        self._apply_run_btn_style()

    def _run_active_comparison(self):
        if len(self._selected_pids) < 2:
            return
            
        pids  = list(self._selected_pids)
        names = [self._picker_cards[p]._name_lbl.text() for p in pids]
        
        # Determine common AP (or 0 if mixed)
        aps = [self._live_caches[p].get("analysis_period", 50) for p in pids]
        common_ap = aps[0] if len(set(aps)) == 1 else 0
        
        # Save to DB history
        label = " vs ".join(names)
        _sm.add_comparison(label, pids, names, common_ap)
        
        # Launch window
        self._rerun_comparison(pids, names, common_ap, {p: True for p in pids})
        
        # Deselect all and refresh history
        for card in self._picker_cards.values():
            if card.selected:
                card.mousePressEvent(None) # Force deselect UI
        
        self._selected_pids.clear()
        self._run_btn.setEnabled(False)
        self._apply_run_btn_style()
        self._render_history()

    # ── history ───────────────────────────────────────────────────────────────

    def _render_history(self):
        while self._history_layout.count():
            item = self._history_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Build a live availability set from disk (needed for cards)
        base = Path(SafeChunkEngine.get_default_base_dir())
        projects = SafeChunkEngine.list_all_projects(str(base))
        self._live_caches: dict[str, dict] = {}
        self._on_disk_pids = {proj["project_id"] for proj in projects}
        for proj in projects:
            if not proj.get("user_meta", {}).get("fit_for_comparison"):
                continue
            cache = _read_cache_from_disk(base, proj["project_id"])
            if cache.get("is_valid"):
                self._live_caches[proj["project_id"]] = cache

        entries = _sm.get_comparison_history()
        
        has_history = bool(entries)
        self._hist_sep.setVisible(has_history)
        self._hist_header.setVisible(has_history)
        self._clear_all_btn.setVisible(has_history)
        self._empty_state.setVisible(not has_history)

        for entry in entries:   # already newest-first from DB
            self._history_layout.addWidget(self._make_history_card(entry))

    def _make_history_card(self, entry: dict) -> QWidget:
        pids  = entry["project_ids"]
        names = entry["project_names"]
        ap    = entry["analysis_period"]
        hid   = entry["id"]

        # Determine individual project statuses: 'ok', 'not_analysed', 'missing'
        p_status = {}
        avail = {} # Parallel boolean map for the re-run worker logic
        for p in pids:
            is_open = self.manager.is_project_open(p) if self.manager else False
            if p in self._live_caches:
                if is_open:
                    p_status[p] = 'not_analysed' # Locked/Open projects treated as not ready
                    avail[p] = False
                else:
                    p_status[p] = 'ok'
                    avail[p] = True
            elif p in self._on_disk_pids:
                p_status[p] = 'not_analysed'
                avail[p] = False
            else:
                p_status[p] = 'missing'
                avail[p] = False

        avail_count = sum(1 for s in p_status.values() if s == 'ok')
        n_not_ready = sum(1 for s in p_status.values() if s == 'not_analysed')
        n_missing   = sum(1 for s in p_status.values() if s == 'missing')
        all_ok      = (avail_count == len(pids))

        # ── Card shell ────────────────────────────────────────────────────────
        card = QFrame()
        card.setObjectName("histCard")
        card.setStyleSheet(
            f"#histCard {{ background: {get_token('surface')}; "
            f"border: 1px solid {get_token('surface_mid')}; "
            f"border-radius: {RADIUS_LG}px; }}"
            f"#histCard:hover {{ border-color: {get_token('primary')}; }}"
        )
        card_h = QHBoxLayout(card)
        card_h.setContentsMargins(0, 0, 0, 0)
        card_h.setSpacing(0)


        # ── Content ───────────────────────────────────────────────────────────
        content = QWidget()
        content.setStyleSheet("background: transparent;")
        cv = QVBoxLayout(content)
        cv.setContentsMargins(SP4, SP3, SP2, SP2)
        cv.setSpacing(SP2)

        # Title row: label + date
        top_h = QHBoxLayout()
        top_h.setContentsMargins(0, 0, 0, 0)
        top_h.setSpacing(SP2)

        title_lbl = QLabel(entry["label"])
        title_lbl.setFont(_f(FS_BASE, FW_SEMIBOLD))
        title_lbl.setStyleSheet(f"color: {get_token('text')}; background: transparent;")
        title_lbl.setWordWrap(True)
        top_h.addWidget(title_lbl, 1)

        date_lbl = QLabel(_fmt_date(entry["compared_at"]))
        date_lbl.setFont(_f(FS_SM))
        date_lbl.setStyleSheet(f"color: {get_token('text_secondary')}; background: transparent;")
        date_lbl.setAlignment(Qt.AlignRight | Qt.AlignTop)
        top_h.addWidget(date_lbl)
        cv.addLayout(top_h)

        # Availability dots row
        dots_h = QHBoxLayout()
        dots_h.setContentsMargins(0, 0, 0, 0)
        dots_h.setSpacing(SP4)
        for pid, name in zip(pids, names):
            st = p_status.get(pid, 'missing')
            dw_h = QHBoxLayout()
            dw_h.setContentsMargins(0, 0, 0, 0)
            dw_h.setSpacing(SP1)
            dot = QFrame()
            dot.setFixedSize(8, 8)
            
            if st == 'ok':
                dot_color = get_token('success')
                text_color = get_token('text_secondary')
            elif st == 'not_analysed':
                dot_color = get_token('warning')
                text_color = get_token('warning')
            else:
                dot_color = get_token('danger')
                text_color = get_token('danger')

            dot.setStyleSheet(f"background: {dot_color}; border-radius: 4px;")
            dw_h.addWidget(dot)
            name_lbl = QLabel(name)
            name_lbl.setFont(_f(FS_SM))
            name_lbl.setStyleSheet(f"color: {text_color}; background: transparent;")
            dw_h.addWidget(name_lbl)
            dots_h.addLayout(dw_h)
        dots_h.addStretch()
        cv.addLayout(dots_h)

        # AP note
        ap_text = f"Analysis period: {ap} yrs" if ap > 0 else "Each project uses its own analysis period"
        ap_lbl = QLabel(ap_text)
        ap_lbl.setFont(_f(FS_SM))
        ap_lbl.setStyleSheet(f"color: {get_token('text_secondary')}; background: transparent;")
        cv.addWidget(ap_lbl)

        # Unavailability inline note
        if not all_ok:
            if n_not_ready > 0:
                note_text = "⚠  One or more projects are not analysed. Please run and make ready for comparison."
                note_color = get_token("warning")
            else:
                note_text = f"⚠  {n_missing} project{'s' if n_missing > 1 else ''} no longer available - will be excluded"
                note_color = get_token("danger")

            note = QLabel(note_text)
            note.setFont(_f(FS_SM))
            note.setWordWrap(True)
            note.setStyleSheet(f"color: {note_color}; background: transparent;")
            cv.addWidget(note)

        # Buttons row
        br_h = QHBoxLayout()
        br_h.setContentsMargins(0, SP2, 0, 0)
        br_h.setSpacing(SP2)
        br_h.addStretch()

        rerun_btn = QPushButton("Re-run ↗")
        rerun_btn.setFixedHeight(BTN_SM)
        rerun_btn.setMinimumWidth(80)
        rerun_btn.setFont(_f(FS_SM, FW_MEDIUM))
        rerun_btn.setEnabled(avail_count >= 2)
        rerun_btn.setStyleSheet(btn_primary() if avail_count >= 2 else btn_ghost())
        rerun_btn.setCursor(Qt.PointingHandCursor)
        rerun_btn.clicked.connect(
            lambda _, p=pids, n=names, a=ap, av=avail:
                self._rerun_comparison(p, n, a, av)
        )
        br_h.addWidget(rerun_btn)

        # Delete button - explicit no-padding style so the ✕ is always visible
        del_btn = QPushButton("✕")
        del_btn.setFixedSize(BTN_SM, BTN_SM)
        del_btn.setFont(_f(FS_MD, FW_BOLD))
        del_btn.setToolTip("Remove from history")
        del_btn.setCursor(Qt.PointingHandCursor)
        del_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: 1px solid {get_token('surface_mid')}; "
            f"border-radius: {BTN_SM // 2}px; color: {get_token('text_secondary')}; padding: 0; }}"
            f"QPushButton:hover {{ border-color: {get_token('danger')}; color: {get_token('danger')}; "
            f"background: transparent; }}"
        )
        del_btn.clicked.connect(lambda _, h=hid: self._remove_history(h))
        br_h.addWidget(del_btn)

        cv.addLayout(br_h)
        card_h.addWidget(content, 1)
        return card

    def _rerun_comparison(self, pids: list, names: list, ap: int, avail: dict):
        base = Path(SafeChunkEngine.get_default_base_dir())
        missing_on_disk = [names[i] for i, pid in enumerate(pids) if not (base / pid).exists()]
        
        if missing_on_disk:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self, "Projects Missing",
                "The following projects no longer exist on disk and cannot be re-run:\n\n- " +
                "\n- ".join(missing_on_disk)
            )
            self._render_history() # Refresh to update UI state
            return

        # Mutual exclusivity: cannot re-run comparison if any project is open for editing
        if self.manager:
            open_projects = [names[i] for i, pid in enumerate(pids) if self.manager.is_project_open(pid)]
            if open_projects:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.information(
                    self, "Project Open for Editing",
                    "The following projects are currently open for editing and cannot be included in a comparison re-run:\n\n- " +
                    "\n- ".join(open_projects) +
                    "\n\nPlease close these projects before re-running the comparison."
                )
                return

        avail_pids  = [p for p in pids if avail.get(p) and p in self._live_caches]
        avail_names = [names[i] for i, p in enumerate(pids)
                       if avail.get(p) and p in self._live_caches]

        if len(avail_pids) < 2:
            missing_names = [names[i] for i, p in enumerate(pids)
                             if not (avail.get(p) and p in self._live_caches)]
            from PySide6.QtWidgets import QMessageBox
            msg = "At least 2 projects with valid analyses are needed to re-run the comparison.\n\n"
            if missing_names:
                msg += "The following projects are no longer available or have been unlocked:\n- "
                msg += "\n- ".join(missing_names)
            else:
                msg += "Some projects may have been deleted or moved."
                
            QMessageBox.warning(self, "Cannot Re-run", msg)
            return

        project_set = frozenset(avail_pids)
        existing = self._open_windows.get(project_set)
        if existing and existing.isVisible():
            existing.raise_()
            existing.activateWindow()
            return

        caches = {p: self._live_caches[p] for p in avail_pids}
        win = ComparisonResultWindow(pids=avail_pids, names=avail_names,
                                     caches=caches, override_ap=ap)
        win.show()
        self._open_windows[project_set] = win

    def _remove_history(self, history_id: int):
        # Retrieve the entry to show its label in the warning
        entries = _sm.get_comparison_history()
        entry = next((e for e in entries if e["id"] == history_id), None)
        if not entry:
            return

        from PySide6.QtWidgets import QMessageBox
        res = QMessageBox.warning(
            self, "Remove History",
            f"Are you sure you want to remove '{entry['label']}' from your comparison history?\n\n"
            "This only removes the history record. Underlying project data is not affected.",
            QMessageBox.Ok | QMessageBox.Cancel, QMessageBox.Cancel
        )

        if res == QMessageBox.Ok:
            _sm.delete_comparison(history_id)
            self._render_history()

    def _clear_all_history(self):
        from PySide6.QtWidgets import QMessageBox
        res = QMessageBox.warning(
            self, "Clear All History",
            "Are you sure you want to clear your entire comparison history?\n\n"
            "This action cannot be undone. Underlying project data will not be affected.",
            QMessageBox.Ok | QMessageBox.Cancel, QMessageBox.Cancel
        )

        if res == QMessageBox.Ok:
            _sm.delete_all_comparisons()
            self._render_history()


# Keep old name available so any stale import doesn't hard-crash
ComparisonPage = ComparisonPickerPanel
