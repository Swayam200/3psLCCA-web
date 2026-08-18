from three_ps_lcca_gui.gui.themes import get_token
from PySide6.QtWidgets import (
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QSizePolicy,
    QMessageBox,
)
from PySide6.QtCore import Qt, QSize, QRect, QEvent
from PySide6.QtGui import QFont
from ...utils.definitions import UNIT_DISPLAY
from ...utils.display_format import fmt, fmt_comma
from ...utils.icons import make_icon
from ...utils.table_widgets import (
    GroupedHeaderView,
    WordWrapHeaderView,
    BaseActionDelegate,
    TooltipTableMixin,
)
from three_ps_lcca_gui.gui.theme import FS_SM, FW_SEMIBOLD


_HDR_FONT = QFont("Ubuntu", FS_SM, FW_SEMIBOLD)

_ACTION_W = 80  # fixed Action column width


def _make_msgbox(parent, icon, title, text):
    """QMessageBox styled to match the app theme background."""
    box = QMessageBox(icon, title, text, QMessageBox.Yes | QMessageBox.No, parent)
    box.setDefaultButton(QMessageBox.No)
    box.setStyleSheet(
        f"QMessageBox {{ background-color: {get_token('base')}; color: {get_token('text')}; }}"
        f"QLabel {{ color: {get_token('text')}; }}"
    )
    return box
_ROW_H = 50  # row height - 11 px clearance top + bottom around 28 px button


# ---------------------------------------------------------------------------
# Action column delegate - paints icon buttons directly, no QWidget overhead
# ---------------------------------------------------------------------------


class _ActionDelegate(BaseActionDelegate):
    """Paints circular icon buttons in the Action column and handles clicks."""

    BTN_GAP = 8

    def __init__(self, table, manager, component_name, is_trash_view):
        super().__init__(table)
        self._manager = manager
        self._component = component_name
        self._trash_view = is_trash_view

        if not is_trash_view:
            self._btns = [
                (make_icon("edit"), (46, 204, 113), "edit", "Edit"),
                (
                    make_icon("trash", color=get_token("danger")),
                    (231, 76, 60),
                    "trash",
                    "Move to trash",
                ),
            ]
        else:
            self._btns = [
                (make_icon("restore"), (46, 204, 113), "restore", "Restore"),
                (
                    make_icon("trash", color=get_token("danger")),
                    (192, 57, 43),
                    "delete",
                    "Permanently delete",
                ),
            ]

    def _get_btns_for_row(self, row) -> list[tuple]:
        return [
            (icon, hover_rgb, tooltip) for icon, hover_rgb, _, tooltip in self._btns
        ]

    def sizeHint(self, option, index):
        return QSize(_ACTION_W, _ROW_H)

    def editorEvent(self, event, model, option, index):
        if self._frozen:
            return False
        if event.type() == QEvent.MouseButtonRelease:
            original_index = index.data(Qt.UserRole)
            rects = self._btn_rects(option.rect, len(self._btns))
            for i, (_, _, action, *__) in enumerate(self._btns):
                if rects[i].contains(event.pos()):
                    if action == "edit":
                        self._manager.open_edit_dialog(self._component, original_index)
                    elif action == "trash":
                        self._confirm_trash(original_index)
                    elif action == "restore":
                        self._manager.toggle_trash_status(
                            self._component, original_index, False
                        )
                    elif action == "delete":
                        self._confirm_delete(original_index)
                    return True
        return False

    def _confirm_trash(self, original_index):
        box = _make_msgbox(self._table, QMessageBox.Warning, "Move to Trash", "Move this item to trash?")
        if box.exec() == QMessageBox.Yes:
            self._manager.toggle_trash_status(self._component, original_index, True)

    def _confirm_delete(self, original_index):
        box = _make_msgbox(self._table, QMessageBox.Critical, "Permanent Delete", "Remove this item? This cannot be undone.")
        if box.exec() == QMessageBox.Yes:
            self._manager.permanent_delete(self._component, original_index)


# ---------------------------------------------------------------------------
# Frozen Action overlay - single-column widget pinned to the right edge
# ---------------------------------------------------------------------------


class _FrozenActionTable(QTableWidget):
    """
    Overlay widget rendered on top of the right margin that StructureTableWidget
    reserves via setViewportMargins(0, 0, _ACTION_W, 0).

    Because the main table's viewport is already narrowed by _ACTION_W, no
    scrollable column ever enters this zone - the overlay just sits on top of
    the dead margin and nothing is hidden behind it.
    """

    def __init__(self, parent_table: "StructureTableWidget"):
        super().__init__(parent_table)
        self._parent_table = parent_table

        # Use WordWrapHeaderView (not the plain default QHeaderView) so this
        # header is exempt from the app-wide _TableHeaderWordWrapFilter, which
        # asynchronously (QTimer.singleShot(0, ...)) replaces the header of any
        # QTableWidget/QTableView that isn't already a GroupedHeaderView or
        # WordWrapHeaderView. That swap runs fully decoupled from reposition()/
        # resizeEvent()/showEvent(), so if it ever landed on the plain header
        # this widget used before, nothing here would know to resync afterward.
        self.setHorizontalHeader(WordWrapHeaderView(Qt.Horizontal, font=_HDR_FONT))

        self.setColumnCount(1)
        hdr_item = QTableWidgetItem("Action")
        hdr_item.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
        self.setHorizontalHeaderItem(0, hdr_item)
        self.horizontalHeader().setFont(_HDR_FONT)

        self.setFixedWidth(_ACTION_W)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setEditTriggers(QTableWidget.NoEditTriggers)
        self.setFocusPolicy(Qt.NoFocus)
        self.setSelectionMode(QTableWidget.NoSelection)
        self.setFrameShape(QTableWidget.NoFrame)
        self.setStyleSheet(
            """
            QTableWidget {
                background-color: palette(base);
                border-top-left-radius: 0px;
                border-bottom-left-radius: 0px;
                border-bottom-right-radius: 7px;
            }
        """
        )

        self.viewport().setStyleSheet(
            "border-bottom-right-radius: 7px; background-color: transparent;"
        )

        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(_ROW_H)
        self.verticalHeader().setMinimumSectionSize(_ROW_H)

        hdr = self.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.Fixed)
        self.setColumnWidth(0, _ACTION_W)

        # Sync vertical scroll with the main table
        parent_table.verticalScrollBar().valueChanged.connect(
            self.verticalScrollBar().setValue
        )

    def sync_row_heights(self):
        for r in range(self.rowCount()):
            self.setRowHeight(r, self._parent_table.rowHeight(r))

    def add_row(self, original_index: int):
        row = self.rowCount()
        self.insertRow(row)
        self.setRowHeight(row, _ROW_H)
        item = QTableWidgetItem()
        item.setData(Qt.UserRole, original_index)
        item.setFlags(Qt.ItemIsEnabled)
        self.setItem(row, 0, item)

    def reposition(self):
        """
        Sit flush against the right edge of the parent widget, aligned with
        the top of the header.  Match the grouped header height exactly so
        row 0 lines up with the main table's first data row.
        """
        p = self._parent_table
        main_hdr_h = p.horizontalHeader().height()

        # Force overlay header to same height as the two-tier grouped header
        self.horizontalHeader().setFixedHeight(main_hdr_h)

        # x: flush right edge of parent widget
        # y: top of header = viewport top minus header height
        vp = p.viewport()
        x = p.width() - _ACTION_W
        y = vp.y() - main_hdr_h
        self.move(x, y)

        # Use the summed *row* heights rather than p.viewport().height() - the
        # viewport's own geometry only catches up with a newly-grown row (e.g.
        # from word-wrap in resizeRowsToContents()) after another layout pass,
        # leaving the overlay briefly shorter than its actual header+row content
        # in the meantime. Row heights themselves are already up to date here,
        # since resizeEvent() calls resizeRowsToContents() before reposition().
        rows_h = sum(p.rowHeight(r) for r in range(p.rowCount()))
        self.setFixedHeight(rows_h + main_hdr_h)


# ---------------------------------------------------------------------------
# Structure table
# ---------------------------------------------------------------------------


class StructureTableWidget(TooltipTableMixin, QTableWidget):
    _GROUPS = []

    def __init__(self, parent_manager, component_name, is_trash_view=False):
        super().__init__()
        self.manager = parent_manager
        self.component_name = component_name
        self.is_trash_view = is_trash_view
        self._frozen = False

        self.setHorizontalHeader(GroupedHeaderView(groups=self._GROUPS, font=_HDR_FONT))

        # 6 scrollable columns (0-5) + col 6 hidden (data/delegate only).
        # The frozen overlay renders the Action UI on top of the reserved right margin.
        self.setColumnCount(8)
        _L = Qt.AlignLeft | Qt.AlignVCenter
        _headers = [
            "Work Name",   # 0
            "Quantity",    # 1
            "Unit",        # 2
            "Rate/Unit",   # 3
            "Source",      # 4
            "Total",       # 5
            "Action",      # 6  hidden - data/delegate only
            "",            # 7  placeholder - same width as overlay, keeps Total visible
        ]
        for col, label in enumerate(_headers):
            item = QTableWidgetItem(label)
            item.setTextAlignment(_L)
            self.setHorizontalHeaderItem(col, item)

        hdr = self.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.Interactive)
        hdr.setStretchLastSection(False)
        hdr.setMinimumSectionSize(60)
        hdr.setSectionResizeMode(5, QHeaderView.Stretch)  # Total fills remaining space
        self.setColumnWidth(3, 110)
        hdr.setSectionResizeMode(6, QHeaderView.Fixed)
        self.setColumnWidth(6, 0)
        self.setColumnHidden(6, True)
        hdr.setSectionResizeMode(7, QHeaderView.Fixed)
        self.setColumnWidth(7, _ACTION_W)

        # KEY: reserve _ACTION_W px on the right so the viewport (and therefore
        # all scrollable columns including Total) never extends into the overlay zone.
        self.setViewportMargins(0, 0, _ACTION_W, 0)

        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setSelectionMode(QTableWidget.SingleSelection)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.setEditTriggers(QTableWidget.NoEditTriggers)
        self.verticalHeader().setDefaultSectionSize(_ROW_H)
        self.verticalHeader().setMinimumSectionSize(_ROW_H)
        self.verticalHeader().setVisible(False)

        # Delegate on hidden col 6 (stores original_index, handles clicks)
        self._action_delegate = _ActionDelegate(
            self, parent_manager, component_name, is_trash_view
        )
        self.setItemDelegateForColumn(6, self._action_delegate)

        # Frozen overlay
        self._frozen_col = _FrozenActionTable(self)
        self._frozen_action_delegate = _ActionDelegate(
            self._frozen_col, parent_manager, component_name, is_trash_view
        )
        self._frozen_col.setItemDelegateForColumn(0, self._frozen_action_delegate)
        self._frozen_col.show()

        if not self.is_trash_view:
            self.cellDoubleClicked.connect(self._on_cell_double_clicked)

        self.update_height()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _on_cell_double_clicked(self, row, column):
        if self._frozen:
            return
        cell = self.item(row, 6)
        if cell is None:
            return
        self.manager.open_edit_dialog(self.component_name, cell.data(Qt.UserRole))

    def set_currency(self, code: str):
        suffix = f" ({code})" if code else ""
        for col, base in ((3, "Rate/Unit"), (5, "Total")):
            item = self.horizontalHeaderItem(col)
            if item:
                item.setText(base + suffix)

    def sizeHint(self):
        header_h = self.horizontalHeader().height() or 56
        rows_h = sum(self.rowHeight(r) for r in range(self.rowCount()))
        return QSize(super().sizeHint().width(), header_h + rows_h + 2)

    def minimumSizeHint(self):
        return self.sizeHint()

    def update_height(self):
        self.updateGeometry()
        if hasattr(self, "_frozen_col"):
            self._frozen_col.reposition()
            self._frozen_col.sync_row_heights()

    # ------------------------------------------------------------------
    # Row management
    # ------------------------------------------------------------------

    def add_row(self, item_data, original_index):
        self.blockSignals(True)
        row = self.rowCount()
        self.insertRow(row)
        self.setRowHeight(row, _ROW_H)

        v = item_data.get("values", {})

        self.setItem(row, 0, QTableWidgetItem(v.get("material_name", "New Item")))

        qty_item = QTableWidgetItem(fmt(v.get("quantity")))
        qty_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.setItem(row, 1, qty_item)

        unit = v.get("unit", "")
        unit = UNIT_DISPLAY.get(unit.lower(), unit) if unit else unit
        self.setItem(row, 2, QTableWidgetItem(unit))

        rate_item = QTableWidgetItem(fmt_comma(v.get("rate")))
        rate_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.setItem(row, 3, rate_item)

        self.setItem(row, 4, QTableWidgetItem(v.get("rate_source", "Manual")))

        try:
            rate = float(v.get("rate") or 0)
            qty = float(v.get("quantity") or 0)
            total = rate * qty
        except (ValueError, TypeError):
            total = 0.0

        total_item = QTableWidgetItem(fmt_comma(total))
        total_item.setFlags(total_item.flags() & ~Qt.ItemIsEditable)
        total_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.setItem(row, 5, total_item)

        # Col 6: hidden, stores original_index for delegate click handling
        action_item = QTableWidgetItem()
        action_item.setData(Qt.UserRole, original_index)
        action_item.setFlags(Qt.ItemIsEnabled)
        self.setItem(row, 6, action_item)

        # Col 7: empty placeholder - reserves space so Total is never hidden
        self.setItem(row, 7, QTableWidgetItem())

        # Mirror in frozen overlay
        self._frozen_col.add_row(original_index)

        self.blockSignals(False)
        self.update_height()

    def insert_row_at_position(self, item_data: dict, original_index: int):
        """Insert a row at the correct sorted position (by original_index)."""
        pos = self.rowCount()
        for r in range(self.rowCount()):
            cell = self.item(r, 6)
            if cell:
                idx = cell.data(Qt.UserRole)
                if isinstance(idx, int) and idx > original_index:
                    pos = r
                    break

        self.blockSignals(True)
        self.insertRow(pos)
        self.setRowHeight(pos, _ROW_H)

        v = item_data.get("values", {})

        self.setItem(pos, 0, QTableWidgetItem(v.get("material_name", "New Item")))

        qty_item = QTableWidgetItem(fmt(v.get("quantity", 0)))
        qty_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.setItem(pos, 1, qty_item)

        unit = v.get("unit", "")
        unit = UNIT_DISPLAY.get(unit.lower(), unit) if unit else unit
        self.setItem(pos, 2, QTableWidgetItem(unit))

        rate_item = QTableWidgetItem(fmt_comma(v.get("rate", 0)))
        rate_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.setItem(pos, 3, rate_item)

        self.setItem(pos, 4, QTableWidgetItem(v.get("rate_source", "Manual")))

        try:
            rate = float(v.get("rate", 0) or 0)
            qty = float(v.get("quantity", 0) or 0)
            total = rate * qty
        except (ValueError, TypeError):
            total = 0.0

        total_item = QTableWidgetItem(fmt_comma(total))
        total_item.setFlags(total_item.flags() & ~Qt.ItemIsEditable)
        total_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.setItem(pos, 5, total_item)

        action_item = QTableWidgetItem()
        action_item.setData(Qt.UserRole, original_index)
        action_item.setFlags(Qt.ItemIsEnabled)
        self.setItem(pos, 6, action_item)

        self.setItem(pos, 7, QTableWidgetItem())

        self.blockSignals(False)

        frozen_item = QTableWidgetItem()
        frozen_item.setData(Qt.UserRole, original_index)
        frozen_item.setFlags(Qt.ItemIsEnabled)
        self._frozen_col.insertRow(pos)
        self._frozen_col.setRowHeight(pos, _ROW_H)
        self._frozen_col.setItem(pos, 0, frozen_item)

        self.update_height()

    def remove_row_by_index(self, original_index: int, reindex: bool = False):
        """Remove the row whose col-6 UserRole matches original_index.

        reindex=True: decrement stored indices > original_index after removal
        (needed after permanent delete, which shifts the data array).
        """
        found = None
        for row in range(self.rowCount()):
            item = self.item(row, 6)
            if item and item.data(Qt.UserRole) == original_index:
                found = row
                break
        if found is None:
            return
        self.removeRow(found)
        self._frozen_col.removeRow(found)
        if reindex:
            for row in range(self.rowCount()):
                for tbl, col in ((self, 6), (self._frozen_col, 0)):
                    cell = tbl.item(row, col)
                    if cell:
                        idx = cell.data(Qt.UserRole)
                        if isinstance(idx, int) and idx > original_index:
                            cell.setData(Qt.UserRole, idx - 1)
        self.update_height()

    # ------------------------------------------------------------------
    # Freeze / unfreeze
    # ------------------------------------------------------------------

    def freeze(self, frozen: bool = True):
        self._frozen = frozen
        self._action_delegate.set_frozen(frozen)
        self._frozen_action_delegate.set_frozen(frozen)

    # ------------------------------------------------------------------
    # Layout / resize
    # ------------------------------------------------------------------

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # viewport() is already _ACTION_W narrower thanks to setViewportMargins.
        # Size cols 0-5 against this narrowed viewport width.
        vp_w = self.viewport().width()

        ratios = {
            0: 0.36,  # Work Name
            1: 0.10,  # Quantity
            2: 0.08,  # Unit
            3: 0.11,  # Rate/Unit
            4: 0.15,  # Source
            5: 0.20,  # Total
        }
        mins = {0: 120, 1: 90, 2: 60, 3: 60, 4: 80, 5: 90}

        col_widths = {c: max(mins[c], int(vp_w * r)) for c, r in ratios.items()}

        used = sum(col_widths.values())
        if used > vp_w:
            # Too narrow for proportional layout - scale down to mins, enable scroll
            scale = vp_w / used
            col_widths = {
                c: max(mins[c], int(w * scale)) for c, w in col_widths.items()
            }

        self.setHorizontalScrollBarPolicy(
            Qt.ScrollBarAsNeeded
            if sum(col_widths.values()) > vp_w
            else Qt.ScrollBarAlwaysOff
        )

        hdr = self.horizontalHeader()
        hdr.blockSignals(True)
        for col, width in col_widths.items():
            self.setColumnWidth(col, width)
        hdr.blockSignals(False)
        self.resizeRowsToContents()

        self._frozen_col.reposition()
        self._frozen_col.sync_row_heights()

    def showEvent(self, event):
        super().showEvent(event)
        self._frozen_col.reposition()


