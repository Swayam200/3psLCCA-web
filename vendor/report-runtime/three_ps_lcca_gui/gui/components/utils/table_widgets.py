"""
Reusable table widgets shared across the application.

Exports:
    GroupedHeaderView       - two-tier grouped horizontal header
    WordWrapHeaderView      - single-tier header with word wrap (installed globally)
    BaseActionDelegate      - base for painted action-column delegates
    TooltipTableMixin       - mixin that shows cell tooltip on overflow
    TableDoubleSpinBox      - QDoubleSpinBox styled for table cells
    TableSpinBox            - QSpinBox styled for table cells
    TableLineEdit           - QLineEdit styled for table cells
    mark_editable_column    - tints a column to indicate it is editable
"""
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QHeaderView,
    QLineEdit,
    QSpinBox,
    QStyledItemDelegate,
    QStyleOptionHeader,
    QStyleOptionViewItem,
    QStyle,
    QTableView,
    QAbstractItemView,
    QToolTip,
)
from PySide6.QtCore import Qt, QSize, QRect, QPoint, QEvent
from PySide6.QtGui import QPainter, QBrush, QColor, QPalette
from three_ps_lcca_gui.gui.themes import get_token


# ---------------------------------------------------------------------------
# Two-tier grouped header
# ---------------------------------------------------------------------------

class GroupedHeaderView(QHeaderView):
    """Horizontal header with spanning group labels on the top tier and
    individual column labels on the bottom tier.

    Args:
        groups: list of (start_col, span, label)
        font:   optional QFont applied to all header text
    Columns NOT in any group span the full height with their label centred.
    """

    def __init__(self, groups=(), font=None, parent=None):
        super().__init__(Qt.Horizontal, parent)
        self._groups    = list(groups)
        self._font      = font
        self._col_group: dict[int, tuple] = {}
        for start, span, label in self._groups:
            for c in range(start, start + span):
                self._col_group[c] = (start, span, label)

    def sizeHint(self):
        s = super().sizeHint()
        if self._groups:
            return QSize(s.width(), s.height() * 2)
        return QSize(s.width(), max(s.height(), 44))

    def paintSection(self, painter, rect, logical_index):
        if self._font:
            painter.setFont(self._font)
        if self._groups and logical_index in self._col_group:
            h2     = rect.height() // 2
            bottom = QRect(rect.x(), rect.y() + h2, rect.width(), h2)
            painter.save()
            painter.setClipRect(bottom)
            super().paintSection(painter, bottom, logical_index)
            painter.restore()
            return
        # Non-grouped column: spans full height — delegate to Qt's C++ pipeline.
        # super().paintSection() is Fusion-safe: it calls drawControl(CE_Header)
        # with opt.text set correctly, so the pen is always valid.
        painter.save()
        painter.setClipRect(rect)
        super().paintSection(painter, rect, logical_index)
        painter.restore()

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self._groups:
            return
        painter = QPainter(self.viewport())
        if self._font:
            painter.setFont(self._font)
        h2 = self.height() // 2
        for start, span, label in self._groups:
            x       = self.sectionViewportPosition(start)
            total_w = sum(self.sectionSize(start + i) for i in range(span))
            group_rect = QRect(x, 0, total_w, h2)
            opt = QStyleOptionHeader()
            self.initStyleOption(opt)
            opt.rect             = group_rect
            opt.section          = start
            opt.text             = label
            opt.textAlignment    = Qt.AlignCenter | Qt.AlignVCenter
            opt.position         = QStyleOptionHeader.Middle
            opt.selectedPosition = QStyleOptionHeader.NotAdjacent
            self.style().drawControl(
                self.style().ControlElement.CE_Header, opt, painter, self
            )
        painter.end()


# ---------------------------------------------------------------------------
# Word-wrap header (no groups) - installed globally on plain QTableWidget/View
# ---------------------------------------------------------------------------

def contrast_color(bg: QColor) -> QColor:
    """Return black or white for readable text on the given background color."""
    lum = (0.299 * bg.red() + 0.587 * bg.green() + 0.114 * bg.blue()) / 255
    return QColor("#000000") if lum > 0.55 else QColor("#ffffff")


class WordWrapHeaderView(QHeaderView):
    """Horizontal header that paints column labels with word wrap and left alignment."""

    _MIN_HEIGHT = 44

    def __init__(self, orientation=Qt.Horizontal, font=None, parent=None):
        super().__init__(orientation, parent)
        self._font = font

    def sizeHint(self):
        s = super().sizeHint()
        return QSize(s.width(), max(s.height(), self._MIN_HEIGHT))

    def paintSection(self, painter, rect, logical_index):
        bg = self.model().headerData(logical_index, self.orientation(), Qt.BackgroundRole)
        bg_color = bg.color() if isinstance(bg, QBrush) else (bg if isinstance(bg, QColor) else None)
        if bg_color and bg_color.isValid() and bg_color.alpha() > 0:
            # Draw standard section first (Fusion-safe), then overlay tint + text with contrast pen.
            painter.save()
            super().paintSection(painter, rect, logical_index)
            painter.restore()
            painter.save()
            painter.fillRect(rect.adjusted(0, 0, 0, -2), bg_color)
            painter.setFont(self._font if self._font else self.font())
            painter.setPen(contrast_color(bg_color))
            text = self.model().headerData(logical_index, self.orientation(), Qt.DisplayRole) or ""
            painter.drawText(rect.adjusted(6, 4, -6, -4), self.defaultAlignment() | Qt.TextWordWrap, str(text))
            painter.restore()
        else:
            # Normal path: delegate entirely to Qt's C++ rendering pipeline.
            # super().paintSection() is Fusion-safe — same proven approach as GroupedHeaderView.
            if self._font:
                painter.setFont(self._font)
            painter.save()
            super().paintSection(painter, rect, logical_index)
            painter.restore()


# ---------------------------------------------------------------------------
# Base action delegate
# ---------------------------------------------------------------------------

class BaseActionDelegate(QStyledItemDelegate):
    """Paints circular icon buttons in a table's last (action) column.
    No QWidget/QHBoxLayout - eliminates jitter and background bleed.

    Subclasses must implement:
        _get_btns_for_row(row) → list of (QIcon, hover_rgb_tuple)

    Class attributes to override per subclass:
        BTN_SIZE  - button diameter in px  (default 28)
        BTN_GAP   - gap between buttons px (default 6)
    """

    BTN_SIZE = 28
    BTN_GAP  = 6

    def __init__(self, table):
        super().__init__(table)
        self._table     = table
        self._frozen    = False
        self._hovered   = (-1, -1)   # (row, btn_index)
        self._icon_size = int(self.BTN_SIZE * 0.8)
        table.viewport().setMouseTracking(True)
        table.viewport().installEventFilter(self)

    # ------------------------------------------------------------------
    # Subclass contract
    # ------------------------------------------------------------------

    def _get_btns_for_row(self, row) -> list[tuple]:
        """Return list of (QIcon, hover_rgb) for buttons in this row."""
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _action_col(self) -> int:
        return self._table.columnCount() - 1

    def _btn_rects(self, cell_rect: QRect, n: int) -> list[QRect]:
        """Return n QRects left-aligned inside cell_rect."""
        x = cell_rect.x() + 6
        y = cell_rect.y() + (cell_rect.height() - self.BTN_SIZE) // 2
        return [
            QRect(x + i * (self.BTN_SIZE + self.BTN_GAP), y, self.BTN_SIZE, self.BTN_SIZE)
            for i in range(n)
        ]

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------

    def paint(self, painter, option, index):
        painter.save()
        is_alt = self._table.alternatingRowColors() and (index.row() % 2 != 0)

        if option.state & QStyle.State_Selected:
            bg = QColor(get_token("surface_pressed"))
        elif option.state & QStyle.State_MouseOver:
            bg = QColor(get_token("surface"))
        else:
            role = QPalette.AlternateBase if is_alt else QPalette.Base
            bg = option.palette.color(role)

        painter.fillRect(option.rect, bg)
        painter.restore()

        # We don't call super().paint() to ensure QSS hover rules are ignored.
        btns = self._get_btns_for_row(index.row())
        if not btns:
            return
        painter.save()
        if self._frozen:
            painter.setOpacity(0.35)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)

        row       = index.row()
        btn_rects = self._btn_rects(option.rect, len(btns))
        icon_size = self._icon_size

        for i, (icon, hover_rgb, *_) in enumerate(btns):
            br = btn_rects[i]
            if not self._frozen and self._hovered == (row, i):
                painter.setBrush(QColor(*hover_rgb, 40))
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(br)
            offset    = (br.width() - icon_size) // 2
            icon_rect = QRect(br.x() + offset, br.y() + offset, icon_size, icon_size)
            icon.paint(painter, icon_rect, Qt.AlignCenter)

        painter.restore()

    # ------------------------------------------------------------------
    # Mouse events - hover tracking
    # ------------------------------------------------------------------

    def eventFilter(self, obj, event):
        try:
            vp = self._table.viewport()
        except RuntimeError:
            return False
        if obj is not vp:
            return False

        action_col = self._action_col()
        if event.type() == QEvent.MouseMove:
            pos   = event.pos()
            index = self._table.indexAt(pos)
            if index.isValid() and index.column() == action_col:
                btns = self._get_btns_for_row(index.row())
                for i, br in enumerate(
                    self._btn_rects(self._table.visualRect(index), len(btns))
                ):
                    if br.contains(pos):
                        self._set_hovered(index.row(), i)
                        tooltip = btns[i][2] if len(btns[i]) > 2 else ""
                        if tooltip:
                            QToolTip.showText(event.globalPos(), tooltip)
                        else:
                            QToolTip.hideText()
                        return False
            self._set_hovered(-1, -1)
            QToolTip.hideText()
        elif event.type() == QEvent.Leave:
            self._set_hovered(-1, -1)
            QToolTip.hideText()

        return False

    def _set_hovered(self, row, btn):
        new = (row, btn)
        if self._hovered == new:
            return
        old, self._hovered = self._hovered, new
        vp         = self._table.viewport()
        action_col = self._action_col()
        for r, _ in (old, new):
            if r >= 0:
                vp.update(self._table.visualRect(
                    self._table.model().index(r, action_col)
                ))

    def set_frozen(self, frozen: bool):
        self._frozen = frozen
        self._table.viewport().update()


# ---------------------------------------------------------------------------
# Tooltip mixin for QTableWidget subclasses
# ---------------------------------------------------------------------------

def round_table_viewport(table) -> None:
    """Clip the viewport background to the table's rounded border corners."""
    table.viewport().setStyleSheet(
        "border-bottom-left-radius: 7px; border-bottom-right-radius: 7px;"
        " background-color: transparent;"
    )


class TooltipTableMixin:
    """Mixin for QTableWidget: always shows a tooltip with the full cell text,
    and enables word wrap + ElideNone so text is never silently cut off.
    The last column (action column) is always skipped.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setWordWrap(True)
        self.setTextElideMode(Qt.ElideNone)
        round_table_viewport(self)

    def viewportEvent(self, event):
        if event.type() == QEvent.ToolTip:
            index      = self.indexAt(event.pos())
            action_col = self.columnCount() - 1
            if index.isValid() and index.column() != action_col:
                item = self.item(index.row(), index.column())
                if item and item.text():
                    QToolTip.showText(event.globalPos(), item.text())
                    return True
            QToolTip.hideText()
        return super().viewportEvent(event)


# ---------------------------------------------------------------------------
# Editable-column tint
# ---------------------------------------------------------------------------

class _EditableColumnDelegate(QStyledItemDelegate):
    """Paints a distinct background behind every cell in an editable column.
    Only highlights cells that are actually interactive (have a cell widget
    or the ItemIsEditable flag set).
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        from three_ps_lcca_gui.gui.themes import theme_manager
        theme_manager().theme_changed.connect(self._on_theme_changed)

    def _on_theme_changed(self):
        parent = self.parent()
        if parent and hasattr(parent, "viewport"):
            parent.viewport().update()

    def paint(self, painter, option, index):
        # Check if the cell is actually editable:
        # 1. Does it have a custom widget set (e.g. TableSpinBox)?
        # 2. Or is its model-level flag set to ItemIsEditable?
        table = self.parent()
        is_widget = False
        if isinstance(table, QTableView):
            is_widget = table.indexWidget(index) is not None

        is_flag = bool(index.flags() & Qt.ItemIsEditable)

        if is_widget or is_flag:
            painter.save()
            bg = QColor(get_token("cell-editable-bg"))
            if bg.isValid():
                painter.fillRect(option.rect, bg)
            painter.restore()

        super().paint(painter, option, index)


def mark_editable_column(table, col: int) -> None:
    """Register the editable-column tint delegate on *col* of *table*."""
    table.setItemDelegateForColumn(col, _EditableColumnDelegate(table))


# ---------------------------------------------------------------------------
# Compact spin boxes for use inside QTableWidget cells
# ---------------------------------------------------------------------------

# Base inline style to include whenever setStyleSheet is called on these widgets.
# Required because a widget-level stylesheet overrides the app QSS entirely for
# that widget - any properties omitted fall back to platform defaults, not main.qss.
TABLE_SPINBOX_BASE_QSS = (
    "background-color: transparent; border: none; border-radius: 0;"
    " margin: 0; padding: 0 4px; min-height: 0;"
)


class TableDoubleSpinBox(QDoubleSpinBox):
    """QDoubleSpinBox subclass for table cells.
    Named differently so main.qss compact rules apply instead of the
    standard form-control padding/min-height rules.
    """


class TableSpinBox(QSpinBox):
    """QSpinBox subclass for table cells. Same rationale as TableDoubleSpinBox."""


class TableLineEdit(QLineEdit):
    """QLineEdit subclass for table cells. Same rationale as TableDoubleSpinBox."""


