"""
gui/components/outputs/lcc_plot.py

Creates an interactive matplotlib chart from LCC analysis results.
Use LCCChartWidget(results) to get a QWidget ready to embed in Qt.
"""

import matplotlib
matplotlib.use("QtAgg")

from three_ps_lcca_gui.gui.themes import get_token, theme_manager
from three_ps_lcca_gui.gui.theme import (
    FONT_FAMILY,
    FS_XS, FS_SM, FS_BASE, FS_MD, FS_LG, FS_XL,
    FW_NORMAL, FW_MEDIUM, FW_SEMIBOLD, FW_BOLD, SP4, SP2
)
from three_ps_lcca_gui.gui.components.utils.display_format import fmt_currency
from three_ps_lcca_gui.gui.components.utils.table_widgets import round_table_viewport, contrast_color
from .plots_helper.Pie import COLORS
from .helper_functions.lcc_colors import COLORS as LCC_PALETTE
from .lcc_data import (
    _get,
    build_chart_data,
    STAGE_DEFS, stage_totals,
    BREAKDOWN_STAGES,
    CATEGORY_COLORS,
)
from .plots_helper.bar_chart import create_bar_chart

matplotlib.rcParams["font.family"] = FONT_FAMILY

from PySide6.QtCore import QEvent, QObject, QRect, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QFontMetrics
from PySide6.QtWidgets import (
    QApplication, QHeaderView, QLabel, QScrollArea, QFrame,
    QSizePolicy, QStyledItemDelegate, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget, QToolTip, QHBoxLayout
)

try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
except ImportError:
    from matplotlib.backends.backend_qt import FigureCanvasQTAgg

from .plots_helper.plot_utils import ChartToolbar, WheelForwarder as _ScrollForwarder



class HeatmapDelegate(QStyledItemDelegate):
    """Native Qt delegate for rendering heatmap cells."""
    def __init__(self, col_maxima, currency, parent=None):
        super().__init__(parent)
        self.col_maxima = col_maxima
        self.currency = currency

    def _std_heat_color(self, intensity: float) -> QColor:
        t = max(0.0, min(1.0, intensity))
        # Light Pale Yellow (255, 255, 200) -> Deep Forest Green (34, 139, 34)
        r = 255 + int((34 - 255) * t)
        g = 255 + int((139 - 255) * t)
        b = 200 + int((34 - 200) * t)
        return QColor(r, g, b)

    def _text_on(self, bg: QColor) -> QColor:
        return contrast_color(bg)

    def paint(self, painter, option, index):
        # Index breakdown:
        # Col 0: Stage Name (slight tint)
        # Col 1-3: Economic, Environmental, Social (Heatmap)
        # Col 4: Stage Total (Neutral)
        # Last Row: Grand Total (Neutral Highlight)
        
        row_count = index.model().rowCount()
        is_total_row = (index.row() == row_count - 1)
        is_heatmap_col = (1 <= index.column() <= 3)
        is_stage_col = (index.column() == 0)
        
        # Determine background color
        if is_heatmap_col and not is_total_row:
            # Main Heatmap Area
            val = index.data(Qt.UserRole)
            col_idx = index.column() - 1
            max_val = self.col_maxima[col_idx]
            intensity = val / max_val if max_val > 0 else 0
            bg_color = self._std_heat_color(intensity)
        elif is_total_row:
            # Bottom Total Row
            bg_color = QColor(get_token("surface_mid"))
        elif is_stage_col:
            bg_data = index.data(Qt.BackgroundRole)
            if hasattr(bg_data, 'color'):
                bg_color = bg_data.color()
            elif isinstance(bg_data, QColor) and bg_data.isValid():
                bg_color = bg_data
            else:
                bg_color = QColor(get_token("window"))
        else:
            # Right Total Column (index 4)
            bg_color = QColor(get_token("surface"))

        fg_color = self._text_on(bg_color)

        painter.save()
        painter.fillRect(option.rect, bg_color)
        
        painter.setFont(option.font)
        painter.setPen(fg_color)
        
        # Draw text
        display_text = index.data(Qt.DisplayRole)
        if display_text is None:
            val = index.data(Qt.UserRole)
            if val is not None:
                display_text = fmt_currency(val, self.currency, decimals=2)
        
        if display_text:
            padding = 8
            rect = option.rect.adjusted(padding, 0, -padding, 0)
            align = Qt.AlignLeft if is_stage_col else Qt.AlignRight
            painter.drawText(rect, align | Qt.AlignVCenter, display_text)
            
        painter.restore()

    def helpEvent(self, event, view, option, index):
        if not index.isValid():
            return False

        val = index.data(Qt.UserRole)
        if val is not None:
            actual_val = val * 1_000_000
            QToolTip.showText(
                event.globalPos(),
                f"Actual Value: {self.currency} {fmt_currency(actual_val, self.currency, decimals=0, style='both')}",
            )
            return True
        else:
            txt = index.data(Qt.DisplayRole)
            if txt:
                QToolTip.showText(event.globalPos(), str(txt))
                return True
                
        return super().helpEvent(event, view, option, index)


class _StageLabelDelegate(QStyledItemDelegate):
    """Paints col-0 stage cells with explicit background and centered text."""

    def paint(self, painter, option, index):
        bg = index.data(Qt.BackgroundRole)
        bg_color = bg.color() if hasattr(bg, 'color') else None
        painter.save()
        if bg_color and bg_color.isValid():
            painter.fillRect(option.rect, bg_color)
            painter.setPen(contrast_color(bg_color))
        else:
            painter.fillRect(option.rect, option.palette.base())
        font = index.data(Qt.FontRole)
        if font:
            painter.setFont(font)
        text = index.data(Qt.DisplayRole) or ""
        painter.drawText(option.rect.adjusted(6, 0, -6, 0),
                         Qt.AlignCenter | Qt.TextWordWrap, str(text))
        painter.restore()


class LCCDetailsTable(QWidget):
    """Stage × pillar cost summary table."""

    def __init__(self, results: dict, currency: str = "INR", parent=None):
        super().__init__(parent)
        self._currency = currency

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self.table = QTableWidget()
        round_table_viewport(self.table)
        self.table.setItemDelegateForColumn(0, _StageLabelDelegate(self.table))
        self.table.setColumnCount(5)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        self.table.setShowGrid(True)
        self.table.setAlternatingRowColors(False)

        headers = [
            "Stage",
            f"Economic\n({currency})",
            f"Environmental\n({currency})",
            f"Social\n({currency})",
            f"Stage Total\n({currency})"
        ]
        self.table.setHorizontalHeaderLabels(headers)
        _hdr_bg = [None, LCC_PALETTE["eco_color"], LCC_PALETTE["env_color"], LCC_PALETTE["soc_color"], None]
        for col, hex_color in enumerate(_hdr_bg):
            if hex_color:
                item = self.table.horizontalHeaderItem(col)
                if item:
                    item.setBackground(QColor(hex_color))
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
        self.table.horizontalHeader().setMinimumSectionSize(120)
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignCenter)
        self.table.setWordWrap(True)

        self._build_data(results)
        self.table.resizeRowsToContents()

        lay.addWidget(self.table)

        # Compute height from actual row heights after word-wrap
        header_h = self.table.horizontalHeader().sizeHint().height()
        total_row_h = sum(self.table.rowHeight(r) for r in range(self.table.rowCount()))
        table_h = header_h + total_row_h + 2
        self.table.setFixedHeight(table_h)
        self.setFixedHeight(table_h)

    def _build_data(self, results: dict):
        rows = []
        grand = [0.0] * 4
        _recon_vals = None

        for stage_label, result_key, cat_keys in STAGE_DEFS:
            totals = stage_totals(results, result_key, cat_keys)
            if not totals:
                continue

            vals = [
                totals.get("Economic", 0.0),
                totals.get("Environmental", 0.0),
                totals.get("Social", 0.0),
            ]
            vals.append(sum(vals))

            if result_key == "reconstruction":
                _recon_vals = vals
                continue

            if result_key == "end_of_life" and _recon_vals is not None:
                vals = [vals[i] + _recon_vals[i] for i in range(4)]

            rows.append((stage_label, result_key, vals))
            for i, v in enumerate(vals):
                grand[i] += v

        self.table.setRowCount(len(rows) + 1)

        f_base = QFont(FONT_FAMILY, FS_BASE, FW_SEMIBOLD)
        f_bold = QFont(FONT_FAMILY, FS_BASE, FW_BOLD)

        _stage_bg = {
            "initial_stage": LCC_PALETTE["init_color"],
            "use_stage":     LCC_PALETTE["use_color"],
            "end_of_life":   LCC_PALETTE["end_color"],
        }

        for r_idx, (label, key, vals) in enumerate(rows):
            item = QTableWidgetItem(label)
            item.setFont(f_base)
            if key in _stage_bg:
                item.setBackground(QColor(_stage_bg[key]))
            self.table.setItem(r_idx, 0, item)

            for c_idx, v in enumerate(vals):
                it = QTableWidgetItem(fmt_currency(v, self._currency, decimals=2))
                it.setFont(f_base)
                it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter | Qt.TextWordWrap)
                self.table.setItem(r_idx, c_idx + 1, it)

        # Grand Total Row
        tr_idx = len(rows)
        gt_item = QTableWidgetItem("Total")
        gt_item.setFont(f_bold)
        gt_item.setBackground(QColor(get_token("surface_mid")))
        self.table.setItem(tr_idx, 0, gt_item)

        for c_idx, v in enumerate(grand):
            it = QTableWidgetItem(fmt_currency(v, self._currency, decimals=2))
            it.setFont(f_bold)
            it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter | Qt.TextWordWrap)
            it.setBackground(QColor(get_token("surface_mid")))
            self.table.setItem(tr_idx, c_idx + 1, it)


# ---------------------------------------------------------------------------
# Detailed breakdown table
# ---------------------------------------------------------------------------

class _VerticalTextDelegate(QStyledItemDelegate):
    """Renders cell text rotated 90° counter-clockwise for the stage column."""

    def paint(self, painter, option, index):
        painter.save()
        bg = index.data(Qt.BackgroundRole)
        if bg:
            c = bg.color() if hasattr(bg, "color") else QColor(bg)
            painter.fillRect(option.rect, c)

        painter.translate(
            option.rect.x() + option.rect.width() / 2,
            option.rect.y() + option.rect.height() / 2,
        )
        painter.rotate(-90)

        text_rect = QRect(
            -option.rect.height() // 2,
            -option.rect.width() // 2,
            option.rect.height(),
            option.rect.width(),
        )
        text = (index.data(Qt.DisplayRole) or "").replace("\n", " ")
        font = index.data(Qt.FontRole)
        if font:
            painter.setFont(font)
        fg = index.data(Qt.ForegroundRole)
        painter.setPen(fg.color() if fg and hasattr(fg, "color") else option.palette.text().color())
        painter.drawText(text_rect, Qt.AlignCenter, text)
        painter.restore()

    def sizeHint(self, option, index):
        return QSize(64, 80)



class _ColorDelegate(QStyledItemDelegate):
    """Paints cell background from BackgroundRole brush, ignoring QSS overrides.
    This is the only reliable way to force per-item colors in a dark-themed Qt app."""

    def paint(self, painter, option, index):
        painter.save()
        # Fill background from the item's BackgroundRole brush
        bg = index.data(Qt.BackgroundRole)
        if bg:
            color = bg.color() if hasattr(bg, 'color') else QColor(bg)
            painter.fillRect(option.rect, color)
        else:
            painter.fillRect(option.rect, option.palette.base())

        # Draw text with ForegroundRole color
        fg = index.data(Qt.ForegroundRole)
        text_color = fg.color() if fg and hasattr(fg, 'color') else QColor(get_token("text"))
        painter.setPen(text_color)

        text = index.data(Qt.DisplayRole) or ""
        align = index.data(Qt.TextAlignmentRole)
        if align is None:
            align = Qt.AlignLeft | Qt.AlignVCenter

        padding = 6
        text_rect = option.rect.adjusted(padding, 0, -padding, 0)
        painter.drawText(text_rect, int(align), text)
        painter.restore()

    def sizeHint(self, option, index):
        base = super().sizeHint(option, index)
        return base


class LCCBreakdownTable(QWidget):
    """Detailed row-by-row LCC cost breakdown- pure QPainter widget.

    Columns: Stage (fixed) | Cost Item (draggable) | Value (draggable) | Relative Cost (draggable)

    Column dividers can be dragged to resize. Hover over Cost Item or Value cells
    shows the full text as a tooltip. Long labels wrap within their cell.
    """

    _STAGE_W   = 64    # fixed- stage column never resizes
    _PAD_X     = 6
    _VAL_PAD_X = 8   # horizontal padding for the Value column (col 3)
    _VAL_PAD_Y = 10  # vertical padding for the Value column (col 3)
    _ITEM_PAD_Y = 8  # vertical padding for the Cost Item column (col 2)
    _LEGEND_H  = 28    # height reserved for legend at top
    _PAD_TOP   = 32    # legend (28) + 4px gap before header
    _MIN_ROW_H = 40
    _DRAG_HIT  = 5     # px tolerance for divider hit-test

    # column ratio/width defaults  (flex_w = W - _STAGE_W)
    _DEF_ITEM_RATIO = 0.25   # Cost Item - 25 %
    _DEF_BAR_RATIO  = 0.55   # Relative Cost bar- 55 % (highest priority)
    # Value gets the remainder: 20 %

    # Colors from lcc_colors.py (single source of truth for this widget)
    _PILLAR_COLORS = {
        "economic":      LCC_PALETTE["eco_color"],
        "environmental": LCC_PALETTE["env_color"],
        "social":        LCC_PALETTE["soc_color"],
    }
    _STAGE_COLORS = {
        "initial_stage":   LCC_PALETTE["init_color"],
        "use_stage":       LCC_PALETTE["use_color"],
        "end_of_life":     LCC_PALETTE["end_color"],
        "reconstruction":  LCC_PALETTE.get("recon_color", "#B0BEC5"),
    }

    def __init__(self, results: dict, currency: str = "INR",
                 stage_labels: dict | None = None,
                 row_labels: dict | None = None,
                 parent=None):
        super().__init__(parent)
        self._currency = currency
        self._stage_labels = stage_labels or {}  # result_key → custom stage name
        self._row_labels   = row_labels   or {}  # cost key   → custom row label
        self._rows = []          # list of (pillar, label, value)
        self._stage_blocks = []  # list of [label, color_hex, start, end, sy, sh]
        self._row_layouts = []   # list of (y, h) per row
        self._total_content_h = 0
        self._max_val = 1.0

        # Column layout state- ratios of the flexible zone (W - _STAGE_W)
        self._item_ratio = self._DEF_ITEM_RATIO   # Cost Item / flex_w
        self._bar_ratio  = self._DEF_BAR_RATIO    # Relative Cost / flex_w
        # Value column gets the rest: flex_w * (1 - item - bar)

        # Drag state
        self._drag_col = None   # "bar" | "val" | None
        self._drag_start_x = 0
        self._drag_start_item = 0.0
        self._drag_start_bar  = 0.0

        self._build(results)
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding)
        theme_manager().theme_changed.connect(self.update)

    def minimumSizeHint(self) -> QSize:
        """Allow the widget to shrink horizontally below its painted width."""
        return QSize(100, 400)

    # ── data ──────────────────────────────────────────────────────────────────

    def _build(self, results: dict):
        row_idx = 0
        _pillar_order = {"economic": 0, "environmental": 1, "social": 2}
        _buffered_recon = None  # buffer reconstruction rows to fold into end_of_life

        for stage_def in BREAKDOWN_STAGES:
            result_key = stage_def["result_key"]
            stage_data = results.get(result_key, {})

            if stage_def.get("optional") and not isinstance(stage_data.get("economic"), dict):
                continue

            stage_rows = []
            for cat, key, label in stage_def["rows"]:
                val = stage_data.get(cat, {}).get(key)
                if val is not None:
                    # Scrap value is stored as a positive cost, so negate it for display/totaling as a credit
                    if key == "total_scrap_value":
                        val = -float(val)
                    stage_rows.append((cat, label, float(val)))
            if not stage_rows:
                continue
            if stage_def.get("optional") and all(v == 0.0 for _, _, v in stage_rows):
                continue

            stage_rows.sort(key=lambda r: _pillar_order.get(r[0], 9))
            stage_color = self._STAGE_COLORS.get(result_key, stage_def["stage_color"])

            if result_key == "reconstruction":
                # Buffer to fold into end_of_life block as a sub-section
                _buffered_recon = stage_rows
            elif result_key == "end_of_life":
                start = row_idx
                if _buffered_recon is not None:
                    for cat, label, value in _buffered_recon:
                        self._rows.append((cat, f"Reconstruction | {label}", value, stage_color))
                        row_idx += 1
                for cat, label, value in stage_rows:
                    self._rows.append((cat, label, value, stage_color))
                    row_idx += 1
                self._stage_blocks.append([
                    self._stage_labels.get(result_key,
                                           stage_def["label"].replace("\n", " ")),
                    stage_color,
                    start,
                    row_idx - 1,
                    0, 0,  # sy, sh- filled by _calculate_layout
                ])
            else:
                start = row_idx
                for cat, label, value in stage_rows:
                    self._rows.append((cat, label, value, stage_color))
                    row_idx += 1
                self._stage_blocks.append([
                    self._stage_labels.get(result_key,
                                           stage_def["label"].replace("\n", " ")),
                    stage_color,
                    start,
                    row_idx - 1,
                    0, 0,  # sy, sh- filled by _calculate_layout
                ])

        if self._rows:
            self._max_val = max(
                abs(r[2]) for r in self._rows if r[0] != "_subheader"
            ) or 1.0

    # ── layout ────────────────────────────────────────────────────────────────

    def _col_x(self, W: int) -> tuple[int, int, int]:
        """Return (x_val, x_bar, bar_w) for the current column state.

        Column order: Stage | Cost Item | Value | Relative Cost
          x_val = divider between Cost Item and Value
          x_bar = divider between Value and Relative Cost
          bar_w = width of the Relative Cost bar column
        """
        flex_w = W - self._STAGE_W
        x_val = self._STAGE_W + int(flex_w * self._item_ratio)
        val_w  = int(flex_w * (1.0 - self._item_ratio - self._bar_ratio))
        x_bar  = x_val + val_w
        # clamp so bar column is never off-screen
        x_bar = min(x_bar, W - 60)
        return x_val, x_bar, W - x_bar

    def _calculate_layout(self):
        W = self.width()
        if W <= 0:
            return

        x_val, x_bar, _ = self._col_x(W)
        item_w = x_val - self._STAGE_W - self._PAD_X * 2
        item_w = max(item_w, 1)

        fm = QFontMetrics(QFont(FONT_FAMILY, FS_BASE, FW_NORMAL))
        curr_y = self._PAD_TOP + self._MIN_ROW_H  # header height
        self._row_layouts = []

        for cat, label, *_ in self._rows:
            if cat == "_subheader":
                h = 22
            else:
                text_rect = fm.boundingRect(0, 0, item_w, 2000,
                                            Qt.TextWordWrap | Qt.AlignLeft, label)
                h = max(self._MIN_ROW_H, text_rect.height() + self._ITEM_PAD_Y * 2)
            self._row_layouts.append((curr_y, h))
            curr_y += h

        self._total_content_h = curr_y + 8
        self.setFixedHeight(self._total_content_h)

        for block in self._stage_blocks:
            s, e = block[2], block[3]
            sy = self._row_layouts[s][0]
            ey = self._row_layouts[e][0] + self._row_layouts[e][1]
            block[4] = sy
            block[5] = ey - sy

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._calculate_layout()

    # ── tooltip ───────────────────────────────────────────────────────────────

    def event(self, event: QEvent):
        if event.type() == QEvent.ToolTip:
            W = self.width()
            x_val, x_bar, bar_w = self._col_x(W)
            pos = event.pos()

            for idx, (y, h) in enumerate(self._row_layouts):
                if not (y <= pos.y() < y + h):
                    continue
                cat, label, value, _stage_color = self._rows[idx]
                if cat == "_subheader":
                    continue

                # Cost Item column → show full label when clipped
                if self._STAGE_W <= pos.x() < x_val:
                    fm = QFontMetrics(QFont(FONT_FAMILY, FS_BASE, FW_NORMAL))
                    item_w = x_val - self._STAGE_W - self._PAD_X * 2
                    elided = fm.elidedText(label, Qt.ElideRight, item_w)
                    tip = label if elided != label or "\n" in label else ""
                    if tip:
                        QToolTip.showText(event.globalPos(), tip)
                        return True

                # Value column → show full precision
                if x_val <= pos.x() < x_bar:
                    QToolTip.showText(
                        event.globalPos(),
                        f"{fmt_currency(value, self._currency, decimals=4)} {self._currency}",
                    )
                    return True

                # Relative Cost bar column → show rounded value
                if x_bar <= pos.x() < W:
                    QToolTip.showText(
                        event.globalPos(),
                        f"{fmt_currency(value, self._currency, decimals=2)} {self._currency}",
                    )
                    return True

            QToolTip.hideText()
        return super().event(event)

    # ── column drag resize ────────────────────────────────────────────────────

    def _divider_at(self, x: int) -> str | None:
        """Return which divider is within _DRAG_HIT of x.

        'val' = Cost Item / Value boundary (x_val)
        'bar' = Value / Relative Cost boundary (x_bar)
        """
        W = self.width()
        x_val, x_bar, _ = self._col_x(W)
        if abs(x - x_val) <= self._DRAG_HIT:
            return "val"
        if abs(x - x_bar) <= self._DRAG_HIT:
            return "bar"
        return None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            div = self._divider_at(event.pos().x())
            if div:
                self._drag_col = div
                self._drag_start_x = event.pos().x()
                self._drag_start_item = self._item_ratio
                self._drag_start_bar  = self._bar_ratio
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        W = self.width()
        flex_w = W - self._STAGE_W

        if self._drag_col and flex_w > 0:
            dx = event.pos().x() - self._drag_start_x

            if self._drag_col == "val":
                # Moving x_val (Cost Item / Value boundary): adjusts item_ratio
                new_item = self._drag_start_item + dx / flex_w
                new_item = max(0.15, min(new_item, 1.0 - self._bar_ratio - 0.10))
                self._item_ratio = new_item

            elif self._drag_col == "bar":
                # Moving x_bar (Value / Relative Cost boundary): adjusts bar_ratio.
                # Moving right (dx > 0) widens Value → bar_ratio shrinks.
                new_bar = self._drag_start_bar - dx / flex_w
                new_bar = max(0.10, min(new_bar, 1.0 - self._item_ratio - 0.10))
                self._bar_ratio = new_bar

            self._calculate_layout()
            self.update()
            event.accept()
            return

        # Cursor hint
        div = self._divider_at(event.pos().x())
        if div:
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        else:
            self.unsetCursor()

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._drag_col:
            self._drag_col = None
            event.accept()
            return
        super().mouseReleaseEvent(event)

    # ── paint ─────────────────────────────────────────────────────────────────

    def paintEvent(self, event):
        if not self._row_layouts:
            self._calculate_layout()

        p = QPainter(self)
        # Fill whole background to avoid gaps between rows
        p.fillRect(self.rect(), QColor(get_token("window")))
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        color_text      = QColor(get_token("text"))
        color_header_bg = QColor(get_token("surface_mid"))
        color_success   = QColor(get_token("success"))
        color_row_sep   = QColor(get_token("border", "pressed"))

        pillar_colors = {k: QColor(v) for k, v in self._PILLAR_COLORS.items()}

        W = self.width()
        x_val, x_bar, bar_w = self._col_x(W)
        item_w = x_val - self._STAGE_W
        _bar_pad  = 3
        bar_w_max = int(bar_w * 0.95)

        # ── legend (top) ──────────────────────────────────────────────────────
        legend_y = (self._LEGEND_H - 16) // 2   # vertically center in legend band
        lx = self._STAGE_W + self._PAD_X
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setFont(QFont(FONT_FAMILY, FS_BASE, FW_NORMAL))
        for pillar, color in pillar_colors.items():
            p.fillRect(lx, legend_y, 16, 16, QColor(color))
            p.setPen(color_text)
            p.drawText(lx + 20, legend_y - 1, 120, 18,
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                       pillar.capitalize())
            lx += 130
        p.restore()

        # ── header ────────────────────────────────────────────────────────────
        hdr_y = self._PAD_TOP
        p.fillRect(0, hdr_y, W, self._MIN_ROW_H, color_header_bg)
        p.setFont(QFont(FONT_FAMILY, FS_BASE, FW_SEMIBOLD))
        p.setPen(color_text)
        p.drawText(QRect(self._PAD_X, hdr_y, self._STAGE_W - self._PAD_X * 2, self._MIN_ROW_H),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "Stage")
        p.drawText(QRect(self._STAGE_W + self._PAD_X, hdr_y + self._ITEM_PAD_Y,
                         item_w - self._PAD_X * 2, self._MIN_ROW_H - self._ITEM_PAD_Y * 2),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "Cost Item")
        p.drawText(QRect(x_val + self._VAL_PAD_X, hdr_y + self._VAL_PAD_Y,
                         x_bar - x_val - self._VAL_PAD_X * 2, self._MIN_ROW_H - self._VAL_PAD_Y * 2),
                   Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                   f"Value ({self._currency})")
        p.drawText(QRect(x_bar + self._PAD_X, hdr_y,
                         bar_w - self._PAD_X * 2, self._MIN_ROW_H),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "")

        # ── data rows ─────────────────────────────────────────────────────────
        row_font = QFont(FONT_FAMILY, FS_BASE, FW_NORMAL)

        for idx, (cat, label, value, stage_color_hex) in enumerate(self._rows):
            ry, rh = self._row_layouts[idx]

            # ── sub-header (Reconstruction label band) ────────────────────────
            if cat == "_subheader":
                sc = QColor(stage_color_hex)
                band = QColor(
                    min(255, sc.red()   * 40 // 100 + 153),
                    min(255, sc.green() * 40 // 100 + 153),
                    min(255, sc.blue()  * 40 // 100 + 153),
                )
                p.fillRect(self._STAGE_W, ry, W - self._STAGE_W, rh, band)
                p.setFont(QFont(FONT_FAMILY, FS_BASE, FW_SEMIBOLD))
                p.setPen(QColor("#1a1a1a"))
                p.drawText(
                    QRect(self._STAGE_W + self._PAD_X, ry,
                          W - self._STAGE_W - self._PAD_X * 2, rh),
                    Qt.AlignmentFlag.AlignCenter,
                    label,
                )
                continue

            pillar_color = pillar_colors.get(cat, QColor("#888888"))

            # Row background- same light shade across Cost Item, Bar, and Value columns
            # Merged into one fill to avoid vertical gaps at x_bar/x_val
            tint = QColor(
                min(255, pillar_color.red()   * 25 // 100 + 191),
                min(255, pillar_color.green() * 25 // 100 + 191),
                min(255, pillar_color.blue()  * 25 // 100 + 191),
            )
            p.fillRect(self._STAGE_W, ry, W - self._STAGE_W, rh, tint)

            # Cost Item label (word-wrap)- dark text, bg is always light
            p.setFont(row_font)
            p.setPen(QColor("#1a1a1a"))
            p.drawText(
                QRect(self._STAGE_W + self._PAD_X, ry + self._ITEM_PAD_Y,
                      item_w - self._PAD_X * 2, rh - self._ITEM_PAD_Y * 2),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter | Qt.TextWordWrap,
                label,
            )

            # Value & bar - diverging at x_bar.
            # Positive: value text left of x_bar, bar grows RIGHT from x_bar.
            # Negative: bar grows LEFT from x_bar, value text right of x_bar.
            val_text = fmt_currency(value, self._currency, decimals=2)
            bar_h = rh - _bar_pad * 2
            filled = int((abs(value) / self._max_val) * bar_w_max)
            if value != 0:
                filled = max(filled, 1)

            p.setFont(QFont(FONT_FAMILY, FS_BASE, FW_SEMIBOLD))
            if value < 0:
                # Bar grows left from x_bar - same width scale as positive bars
                p.fillRect(
                    x_bar - filled, ry + _bar_pad,
                    filled, bar_h,
                    QColor(pillar_color),
                )
                # Value text in the right (Relative Cost) column
                p.setPen(QColor("#1a1a1a"))
                p.drawText(
                    QRect(x_bar + self._VAL_PAD_X, ry + self._VAL_PAD_Y,
                          bar_w - self._VAL_PAD_X * 2, rh - self._VAL_PAD_Y * 2),
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                    val_text,
                )
            else:
                # Bar grows right - original behaviour
                p.fillRect(
                    x_bar + _bar_pad, ry + _bar_pad,
                    filled, bar_h,
                    QColor(pillar_color),
                )
                # Value text in the left (Value) column - original behaviour
                p.setPen(QColor("#1a1a1a"))
                p.drawText(
                    QRect(x_val + self._VAL_PAD_X, ry + self._VAL_PAD_Y,
                          x_bar - x_val - self._VAL_PAD_X * 2, rh - self._VAL_PAD_Y * 2),
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                    val_text,
                )
            p.setFont(row_font)

            # row separator
            p.setPen(color_row_sep)
            p.drawLine(self._STAGE_W, ry + rh - 1, W, ry + rh - 1)

        # ── stage blocks ──────────────────────────────────────────────────────
        p.setFont(QFont(FONT_FAMILY, FS_MD, FW_BOLD))
        for stage_label, stage_color_hex, _, _, sy, sh in self._stage_blocks:
            sc = QColor(stage_color_hex)
            stage_tint = QColor(
                min(255, sc.red()   * 25 // 100 + 191),
                min(255, sc.green() * 25 // 100 + 191),
                min(255, sc.blue()  * 25 // 100 + 191),
            )
            p.fillRect(0, sy, self._STAGE_W, sh, stage_tint)
            p.save()
            p.translate(self._STAGE_W / 2, sy + sh / 2)
            p.rotate(-90)
            p.setPen(QColor("#1a1a1a"))
            p.drawText(QRect(-sh // 2, -self._STAGE_W // 2, sh, self._STAGE_W),
                       Qt.AlignmentFlag.AlignCenter, stage_label)
            p.restore()

        # ── stage boundary lines ──────────────────────────────────────────────
        # Draw a full-width separator after each stage except the last one so the
        # three life cycle phases (Initial / Use / End-of-Life) are clearly delimited.
        sep_color = QColor(get_token("surface_mid"))
        sep_color.setAlpha(220)
        p.setPen(QPen(sep_color, 2))
        for i, (_, _, _, _, sy, sh) in enumerate(self._stage_blocks):
            if i < len(self._stage_blocks) - 1:
                sep_y = sy + sh
                p.drawLine(0, sep_y, W, sep_y)

        # ── outer border ──────────────────────────────────────────────────────
        total_h = self._total_content_h - 8
        border_color = QColor(get_token("surface_mid"))
        # Using full opacity for outer border to avoid blending issues
        p.setPen(QPen(border_color, 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(0, self._PAD_TOP, W - 1, total_h - self._PAD_TOP)

        p.end()

    @classmethod
    def in_scroll(cls, results: dict, currency: str = "INR",
                  stage_labels: dict | None = None,
                  row_labels: dict | None = None,
                  parent=None) -> QScrollArea:
        chart = cls(results, currency, stage_labels=stage_labels, row_labels=row_labels)
        scroll = QScrollArea(parent)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidgetResizable(True)
        scroll.setWidget(chart)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # Don't let the inner scroll area force the outer page wider
        scroll.setMinimumWidth(0)
        scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        return scroll


# ---------------------------------------------------------------------------
# Public widget
# ---------------------------------------------------------------------------

class _ScrollForwarder(QObject):
    """Forward wheel events from the canvas to the nearest parent QScrollArea."""

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Wheel:
            parent = obj.parent()
            while parent is not None:
                if isinstance(parent, QScrollArea):
                    QApplication.sendEvent(parent.verticalScrollBar(), event)
                    return True
                parent = parent.parent()
        return False


class LCCChartWidget(QWidget):
    """
    Interactive LCC bar chart widget.
    Includes a navigation toolbar (zoom / pan / save) and hover tooltips.
    """

    def __init__(self, results: dict, currency: str = "INR", parent=None):
        super().__init__(parent)
        self._currency = currency

        # Use theme colors for the graph
        text_color = get_token("text")
        bg_color   = get_token("window")

        self._values, self._labels, stage_info = build_chart_data(results)
        fig, self._bars = create_bar_chart(
            self._values, self._labels, stage_info, text_color, bg_color, currency=currency
        )

        self._canvas = FigureCanvasQTAgg(fig)
        self._canvas.setMinimumHeight(480)
        self._canvas.setMaximumHeight(600)
        self._canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._scroll_forwarder = _ScrollForwarder(self)
        self._canvas.installEventFilter(self._scroll_forwarder)
        toolbar = _ChartToolbar(self._canvas, self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(toolbar)
        layout.addWidget(self._canvas)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        # ── Hover annotation ──────────────────────────────────────────────
        ax = fig.axes[0]
        self._annot = ax.annotate(
            "",
            xy=(0, 0),
            xytext=(14, 14),
            textcoords="offset points",
            bbox=dict(
                boxstyle="round,pad=0.5",
                fc=bg_color,
                ec="#aaaaaa",
                alpha=0.95,
                linewidth=1,
            ),
            fontsize=FS_SM,
            fontfamily=FONT_FAMILY,
            color=text_color,
            zorder=10,
        )
        self._annot.set_visible(False)

        self._canvas.mpl_connect("motion_notify_event", self._on_hover)
        self._canvas.mpl_connect("axes_leave_event",    self._on_leave)

    def sizeHint(self):
        # toolbar ≈ 36px + canvas minimum 480px
        return QSize(super().sizeHint().width(), 520)

    # ── Hover handlers ────────────────────────────────────────────────────

    def _on_hover(self, event):
        if event.inaxes is None:
            self._set_annot_visible(False)
            return

        for bar, label, val in zip(self._bars, self._labels, self._values):
            if bar.contains(event)[0]:
                x = bar.get_x() + bar.get_width() / 2
                self._annot.xy = (x, val)
                inr_val = val * 1_000_000
                sign = "−" if val < 0 else ""
                self._annot.set_text(
                    f"{label}\n"
                    f"{self._currency} {sign}{fmt_currency(abs(inr_val), self._currency, decimals=0, style='both')}\n"
                    f"({sign}{fmt_currency(abs(val), self._currency, decimals=4)} Million {self._currency})"
                )
                self._set_annot_visible(True)
                return

        self._set_annot_visible(False)

    def _on_leave(self, event):
        self._set_annot_visible(False)

    def _set_annot_visible(self, visible: bool):
        if self._annot.get_visible() != visible:
            self._annot.set_visible(visible)
            self._canvas.draw_idle()


# Keep backward-compatible alias for any existing call sites
def create_lcc_figure(results: dict):
    palette = QApplication.instance().palette()
    text_color = palette.windowText().color().name()
    bg_color   = palette.window().color().name()
    values, labels, stage_info = build_chart_data(results)
    fig, _ = create_bar_chart(values, labels, stage_info, text_color, bg_color)
    return fig
