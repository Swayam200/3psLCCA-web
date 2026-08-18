from three_ps_lcca_gui.gui.themes import get_token
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QFrame,
    QSizePolicy,
    QScrollArea,
    QToolTip,
)
from PySide6.QtCore import Qt, QSize, QTimer, QRect, QEvent

import time
import datetime

from ..utils.definitions import UNIT_DISPLAY
from ..utils.display_format import fmt, fmt_comma, DECIMAL_PLACES
from ..utils.icons import make_icon
from ..utils.table_widgets import (
    GroupedHeaderView,
    BaseActionDelegate,
    TooltipTableMixin,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CHUNKS = [
    ("str_foundation", "Foundation"),
    ("str_sub_structure", "Sub-Structure"),
    ("str_super_structure", "Super-Structure"),
    ("str_misc", "Misc"),
]

_ACTION_W = 80  # fixed action column width

REASON_INCOMPLETE = "Incomplete Data"
REASON_EXCLUDED   = "Manually Excluded"


# ---------------------------------------------------------------------------
# Validity check
# ---------------------------------------------------------------------------


def _fmt_unit(code: str) -> str:
    return UNIT_DISPLAY.get(code.lower(), code) if code else code


def _recycle_pct(v: dict) -> float:
    """Read recyclability % - checks both field names for backward compat."""
    return float(
        v.get("post_demolition_recovery_percentage")
        or v.get("recyclability_percentage")
        or 0
    )


def is_recyclable_valid(item: dict) -> bool:
    v = item.get("values", {})
    try:
        return all(
            [
                _recycle_pct(v) > 0,
                float(v.get("scrap_rate") or 0) > 0,
                float(v.get("quantity") or 0) > 0,
            ]
        )
    except (TypeError, ValueError):
        return False


def calc_recyclable_qty(item: dict) -> float:
    """Recyclable Quantity = quantity × (recyclability% / 100)"""
    v = item.get("values", {})
    try:
        return float(v.get("quantity", 0) or 0) * (_recycle_pct(v) / 100)
    except (TypeError, ValueError):
        return 0.0


def calc_recovered_value(item: dict) -> float:
    """Recovered Value = Recyclable Qty × scrap_rate"""
    v = item.get("values", {})
    try:
        return calc_recyclable_qty(item) * float(v.get("scrap_rate") or 0)
    except (TypeError, ValueError):
        return 0.0


# ---------------------------------------------------------------------------
# Action column delegate
# ---------------------------------------------------------------------------


class _RecyclingActionDelegate(BaseActionDelegate):
    """Paints circular icon buttons in the recycling table action column.

    Per-row data stored in the action item's Qt.UserRole as a dict:
        {"btns": ["edit", "exclude"], "chunk_id": ..., "comp_name": ...,
         "idx": ..., "item": ...}
    """

    _ICON_CFG = {
        "edit": (None, (46, 204, 113), "Edit"),
        "exclude": (get_token("danger"), (231, 76, 60), "Exclude from calculation"),
        "include": (get_token("success"), (46, 204, 113), "Include in calculation"),
    }

    def __init__(self, table, handler):
        super().__init__(table)
        self._handler = handler
        self._icons = {
            key: (make_icon(key, color=color), hover_rgb, tooltip)
            for key, (color, hover_rgb, tooltip) in self._ICON_CFG.items()
        }

    def _raw_row_data(self, row) -> dict | None:
        item = self._table.item(row, 0)
        return item.data(Qt.UserRole) if item else None

    def _get_btns_for_row(self, row) -> list[tuple]:
        data = self._raw_row_data(row)
        if not data:
            return []
        return [self._icons[key] for key in data.get("btns", [])]

    def sizeHint(self, option, index):
        return QSize(_ACTION_W, self.BTN_SIZE + 14)

    def editorEvent(self, event, model, option, index):
        if self._frozen:
            return False
        if event.type() == QEvent.MouseButtonRelease:
            data = self._raw_row_data(index.row())
            if not data:
                return False
            btn_keys = data.get("btns", [])
            rects = self._btn_rects(option.rect, len(btn_keys))
            for i, key in enumerate(btn_keys):
                if rects[i].contains(event.pos()):
                    ci, cn, idx, it = (
                        data["chunk_id"],
                        data["comp_name"],
                        data["idx"],
                        data["item"],
                    )
                    if key == "edit":
                        self._handler._open_recyclability_edit(ci, cn, idx, it)
                    elif key == "exclude":
                        self._handler._toggle_inclusion(ci, cn, idx, False)
                    elif key == "include":
                        self._handler._toggle_inclusion(ci, cn, idx, True)
                    return True
        return False


# ---------------------------------------------------------------------------
# Frozen Action overlay - single-column widget pinned to the right edge
# ---------------------------------------------------------------------------


class _FrozenActionTable(QTableWidget):
    """Overlay pinned to the right edge; main table reserves space via setViewportMargins."""

    def __init__(self, parent_table):
        super().__init__(parent_table)
        self._parent_table = parent_table

        self.setColumnCount(1)
        hdr_item = QTableWidgetItem("Action")
        hdr_item.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
        self.setHorizontalHeaderItem(0, hdr_item)

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
        self.verticalHeader().setDefaultSectionSize(35)
        self.verticalHeader().setMinimumSectionSize(35)

        hdr = self.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.Fixed)
        self.setColumnWidth(0, _ACTION_W)

        parent_table.verticalScrollBar().valueChanged.connect(
            self.verticalScrollBar().setValue
        )

    def sync_row_heights(self):
        for r in range(self.rowCount()):
            self.setRowHeight(r, self._parent_table.rowHeight(r))

    def add_row(self, row_data):
        row = self.rowCount()
        self.insertRow(row)
        self.setRowHeight(row, self._parent_table.rowHeight(row))
        item = QTableWidgetItem()
        item.setData(Qt.UserRole, row_data)
        item.setFlags(Qt.ItemIsEnabled)
        self.setItem(row, 0, item)

    def clear_rows(self):
        self.setRowCount(0)

    def reposition(self):
        p = self._parent_table
        main_hdr_h = p.horizontalHeader().height()
        self.horizontalHeader().setFixedHeight(main_hdr_h)
        vp = p.viewport()
        x = p.width() - _ACTION_W
        y = vp.y() - main_hdr_h
        self.move(x, y)
        self.setFixedHeight(vp.height() + main_hdr_h)


# ---------------------------------------------------------------------------
# Recycling Table
# ---------------------------------------------------------------------------


class RecyclingTable(TooltipTableMixin, QTableWidget):
    _L = Qt.AlignLeft | Qt.AlignVCenter
    _R = Qt.AlignRight | Qt.AlignVCenter
    _C = Qt.AlignCenter

    # Cols 2-3 → "Quantity" group (Value + Unit)
    _GROUPS = [(2, 2, "Quantity")]

    INCLUDED_HEADERS = [
        ("Category", _L),  # 0
        ("Component", _L),  # 1
        ("Value", _C),  # 2  ┐ Quantity group
        ("Unit", _C),  # 3  ┘
        ("Recyclability %", _R),  # 4
        ("Recyclable Quantity", _R),  # 5
        ("Scrap Rate", _R),  # 6
        ("Recovered Value", _R),  # 7
        ("Warning", _L),  # 8
        ("Action", _C),  # 9
        ("", _C),  # 10 placeholder
    ]

    EXCLUDED_HEADERS = [
        ("Category", _L),  # 0
        ("Component", _L),  # 1
        ("Value", _C),  # 2  ┐ Quantity group
        ("Unit", _C),  # 3  ┘
        ("Recyclability %", _R),  # 4
        ("Scrap Rate", _R),  # 5
        ("Reason", _L),  # 6
        ("Action", _C),  # 7
        ("", _C),  # 8 placeholder
    ]

    def __init__(self, is_included: bool, parent=None):
        super().__init__(parent)
        self.is_included = is_included

        self.setHorizontalHeader(GroupedHeaderView(groups=self._GROUPS))

        headers = self.INCLUDED_HEADERS if is_included else self.EXCLUDED_HEADERS
        self.setColumnCount(len(headers))
        for col, (label, align) in enumerate(headers):
            item = QTableWidgetItem(label)
            item.setTextAlignment(align)
            self.setHorizontalHeaderItem(col, item)

        h = self.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.Interactive)
        h.setStretchLastSection(False)
        h.setMinimumSectionSize(60)

        self.setEditTriggers(QTableWidget.NoEditTriggers)
        self.setSelectionMode(QTableWidget.NoSelection)
        self.setWordWrap(True)
        self.setTextElideMode(Qt.ElideNone)
        self.verticalHeader().setDefaultSectionSize(35)
        self.verticalHeader().setMinimumSectionSize(35)
        self.verticalHeader().setVisible(False)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        # Hide real action col; placeholder reserves overlay space
        action_col = len(headers) - 2
        placeholder_col = len(headers) - 1
        h.setSectionResizeMode(action_col, QHeaderView.Fixed)
        self.setColumnWidth(action_col, 0)
        self.setColumnHidden(action_col, True)
        h.setSectionResizeMode(placeholder_col, QHeaderView.Fixed)
        self.setColumnWidth(placeholder_col, _ACTION_W)

        self.setViewportMargins(0, 0, _ACTION_W, 0)

        self._frozen_overlay = _FrozenActionTable(self)
        self._frozen_overlay.show()

    def viewportEvent(self, event):
        if event.type() == QEvent.ToolTip:
            index = self.indexAt(event.pos())
            action_col = self.columnCount() - 1
            if index.isValid() and index.column() != action_col:
                item = self.item(index.row(), index.column())
                if item and item.text():
                    QToolTip.showText(event.globalPos(), item.text())
                    return True
            QToolTip.hideText()
        return super().viewportEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        rest = max(1, self.viewport().width())
        qty_sub = max(40, int(rest * 0.06))

        if self.is_included:
            widths = {
                0: max(120, int(rest * 0.09)),  # Category
                1: max(100, int(rest * 0.21)),  # Material
                2: qty_sub,  # Quantity › Value
                3: qty_sub,  # Quantity › Unit
                4: max(55, int(rest * 0.08)),  # Recyclability %
                5: max(70, int(rest * 0.11)),  # Recyclable Quantity
                6: max(55, int(rest * 0.08)),  # Scrap Rate
                7: max(80, int(rest * 0.12)),  # Recovered Value
                8: max(80, int(rest * 0.19)),  # Warning
            }
        else:
            widths = {
                0: max(120, int(rest * 0.10)),  # Category
                1: max(100, int(rest * 0.22)),  # Material
                2: qty_sub,  # Quantity › Value
                3: qty_sub,  # Quantity › Unit
                4: max(55, int(rest * 0.08)),  # Recyclability %
                5: max(55, int(rest * 0.08)),  # Scrap Rate
                6: max(100, int(rest * 0.40)),  # Reason
            }

        for col, width in widths.items():
            self.setColumnWidth(col, width)
        self.resizeRowsToContents()

        self._frozen_overlay.reposition()
        self._frozen_overlay.sync_row_heights()

    def sizeHint(self):
        header_h = self.horizontalHeader().height() or 35
        rows_h = sum(self.rowHeight(r) for r in range(self.rowCount()))
        return QSize(super().sizeHint().width(), max(60, header_h + rows_h + 10))

    def minimumSizeHint(self):
        return self.sizeHint()

    def update_height(self):
        self.resizeRowsToContents()
        self.updateGeometry()
        if hasattr(self, "_frozen_overlay"):
            self._frozen_overlay.reposition()
            self._frozen_overlay.sync_row_heights()

    def clear_rows(self):
        self.setRowCount(0)
        self._frozen_overlay.clear_rows()
        self.update_height()

    def showEvent(self, event):
        super().showEvent(event)
        self._frozen_overlay.reposition()


# ---------------------------------------------------------------------------
# RecyclingWidget - main tab
# ---------------------------------------------------------------------------


class Recycling(QWidget):
    def __init__(self, controller=None):
        super().__init__()
        self.controller = controller
        self.setObjectName("RecyclingWidget")

        self._details_visible = False
        self._frozen = False
        self._loaded = False
        if controller and hasattr(controller, "project_loaded"):
            controller.project_loaded.connect(self._on_project_reloaded)
        if controller and hasattr(controller, "chunk_updated"):
            _STRUCTURE_CHUNKS = {"str_foundation", "str_sub_structure", "str_super_structure", "str_misc"}
            controller.chunk_updated.connect(
                lambda name: QTimer.singleShot(0, self.on_refresh) if name in _STRUCTURE_CHUNKS else None
            )

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        container = QWidget()
        main_layout = QVBoxLayout(container)
        main_layout.setSpacing(8)

        # ── Summary Bar ──────────────────────────────────────────────────
        self.summary_bar = QWidget()
        summary_layout = QHBoxLayout(self.summary_bar)
        summary_layout.setContentsMargins(8, 8, 8, 8)

        self.total_lbl = QLabel("Total Recovered Value: -")
        self.count_lbl = QLabel("Included: - of - items")
        self.details_btn = QPushButton("Show Details ▼")
        self.details_btn.setFlat(True)
        self.details_btn.setCursor(Qt.PointingHandCursor)
        self.details_btn.clicked.connect(self._toggle_details)

        summary_layout.addWidget(self.total_lbl)
        summary_layout.addWidget(self._vline())
        summary_layout.addWidget(self.count_lbl)
        summary_layout.addStretch()
        summary_layout.addWidget(self.details_btn)
        main_layout.addWidget(self.summary_bar)

        # ── Details Row (hidden by default) ──────────────────────────────
        self.details_widget = QWidget()
        details_layout = QHBoxLayout(self.details_widget)
        details_layout.setContentsMargins(8, 0, 8, 8)

        self.foundation_lbl = QLabel("Foundation: -")
        self.sub_lbl = QLabel("Sub-Structure: -")
        self.super_lbl = QLabel("Super-Structure: -")
        self.misc_lbl = QLabel("Misc: -")

        for lbl in [self.foundation_lbl, self.sub_lbl, self.super_lbl, self.misc_lbl]:
            details_layout.addWidget(lbl)
            details_layout.addWidget(self._vline())

        details_layout.addStretch()
        self.details_widget.setVisible(False)
        main_layout.addWidget(self.details_widget)
        main_layout.addWidget(self._hline())

        # ── Included Section ─────────────────────────────────────────────
        main_layout.addWidget(self._section_label("Included in Recyclability"))

        self.included_table = RecyclingTable(is_included=True)
        self._included_action = _RecyclingActionDelegate(
            self.included_table._frozen_overlay, self
        )
        self.included_table._frozen_overlay.setItemDelegateForColumn(
            0, self._included_action
        )
        main_layout.addWidget(self.included_table)
        main_layout.addWidget(self._hline())

        # ── Excluded Section ─────────────────────────────────────────────
        main_layout.addWidget(self._section_label("Excluded from Recyclability"))

        self.excluded_table = RecyclingTable(is_included=False)
        self._excluded_action = _RecyclingActionDelegate(
            self.excluded_table._frozen_overlay, self
        )
        self.excluded_table._frozen_overlay.setItemDelegateForColumn(
            0, self._excluded_action
        )
        main_layout.addWidget(self.excluded_table)
        main_layout.addStretch()

        scroll.setWidget(container)
        outer_layout.addWidget(scroll)

    # ── UI Helpers ───────────────────────────────────────────────────────

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(f"<b>{text}</b>")
        lbl.setStyleSheet("font-size: 13px;")
        return lbl

    def _hline(self) -> QFrame:
        f = QFrame()
        f.setFrameShape(QFrame.HLine)
        f.setFrameShadow(QFrame.Sunken)
        return f

    def _vline(self) -> QFrame:
        f = QFrame()
        f.setFrameShape(QFrame.VLine)
        f.setFrameShadow(QFrame.Sunken)
        return f

    def _toggle_details(self):
        self._details_visible = not self._details_visible
        self.details_widget.setVisible(self._details_visible)
        self.details_btn.setText(
            "Hide Details ▲" if self._details_visible else "Show Details ▼"
        )

    def _get_currency(self) -> str:
        try:
            data = self.controller.engine.fetch_chunk("general_info") or {}
            return data.get("project_currency", "")
        except Exception:
            return ""

    # ── Data Loading ─────────────────────────────────────────────────────

    def on_refresh(self):
        if not self.controller or not getattr(self.controller, "engine", None):
            return

        result = self._compute()

        included_with_warn = [
            (
                cat,
                chunk_id,
                comp,
                idx,
                item,
                value,
                (
                    "! Zero Quantity"
                    if float(item.get("values", {}).get("quantity", 0) or 0) == 0
                    else ""
                ),
            )
            for cat, chunk_id, comp, idx, item, value in result["included_items"]
        ]

        self._update_currency_headers(result["currency"])
        self._populate_included(included_with_warn, result["currency"])
        self._populate_excluded(result["excluded_items"])
        self._update_summary(
            result["total_recovered_value"],
            result["included_count"],
            result["total_count"],
            result["cat_totals"],
            result["currency"],
        )

    def _update_currency_headers(self, currency: str):
        cu = currency or ""
        def _hdr(text):
            it = QTableWidgetItem(text)
            it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            return it
        # Included table: col 6 = Scrap Rate, col 7 = Recovered Value
        self.included_table.setHorizontalHeaderItem(
            6, _hdr(f"Scrap Rate ({cu}/unit)" if cu else "Scrap Rate (per unit)")
        )
        self.included_table.setHorizontalHeaderItem(
            7, _hdr(f"Recovered Value ({cu})" if cu else "Recovered Value")
        )
        # Excluded table: col 5 = Scrap Rate
        self.excluded_table.setHorizontalHeaderItem(
            5, _hdr(f"Scrap Rate ({cu}/unit)" if cu else "Scrap Rate (per unit)")
        )

    def _populate_included(self, items, currency: str):
        t = self.included_table
        t.clear_rows()

        for category, chunk_id, comp_name, idx, item, value, warn in items:
            v = item.get("values", {})
            row = t.rowCount()
            t.insertRow(row)

            unit = _fmt_unit(v.get("unit", ""))
            recyclable_qty = f"{fmt(calc_recyclable_qty(item))} {unit}".strip()
            value_str = fmt_comma(value)

            def _ri(text):
                it = QTableWidgetItem(text)
                it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                return it

            t.setItem(row, 0, QTableWidgetItem(category))
            t.setItem(row, 1, QTableWidgetItem(v.get("material_name", "")))
            t.setItem(row, 2, _ri(fmt(v.get("quantity"))))
            t.setItem(row, 3, QTableWidgetItem(unit))
            t.setItem(row, 4, _ri(
                f"{_recycle_pct(v):.{DECIMAL_PLACES}f}%"
                if v.get("post_demolition_recovery_percentage") is not None
                else "-"
            ))
            t.setItem(row, 5, _ri(recyclable_qty))
            t.setItem(row, 6, _ri(fmt(v.get("scrap_rate"))))
            val_item = QTableWidgetItem(value_str)
            val_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            t.setItem(row, 7, val_item)
            warn_item = QTableWidgetItem(warn)
            warn_item.setTextAlignment(Qt.AlignCenter)
            t.setItem(row, 8, warn_item)

            action_item = QTableWidgetItem()
            action_item.setData(
                Qt.UserRole,
                {
                    "btns": ["edit", "exclude"],
                    "chunk_id": chunk_id,
                    "comp_name": comp_name,
                    "idx": idx,
                    "item": item,
                },
            )
            action_item.setFlags(Qt.ItemIsEnabled)
            t.setItem(row, 9, action_item)
            t.setItem(row, 10, QTableWidgetItem())  # placeholder
            t._frozen_overlay.add_row(
                {
                    "btns": ["edit", "exclude"],
                    "chunk_id": chunk_id,
                    "comp_name": comp_name,
                    "idx": idx,
                    "item": item,
                }
            )

        t.update_height()

    def _populate_excluded(self, items, currency: str = ""):
        t = self.excluded_table
        t.clear_rows()

        for category, chunk_id, comp_name, idx, item, reason in items:
            v = item.get("values", {})
            row = t.rowCount()
            t.insertRow(row)

            unit = _fmt_unit(v.get("unit", ""))

            def _ri(text):
                it = QTableWidgetItem(text)
                it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                return it

            t.setItem(row, 0, QTableWidgetItem(category))
            t.setItem(row, 1, QTableWidgetItem(v.get("material_name", "")))
            t.setItem(row, 2, _ri(fmt(v.get("quantity"))))
            t.setItem(row, 3, QTableWidgetItem(unit))
            t.setItem(row, 4, _ri(
                f"{_recycle_pct(v):.{DECIMAL_PLACES}f}%"
                if v.get("post_demolition_recovery_percentage") is not None
                else "-"
            ))
            t.setItem(row, 5, _ri(fmt(v.get("scrap_rate"))))
            t.setItem(row, 6, QTableWidgetItem(reason))

            btn_keys = ["edit"] if reason == REASON_INCOMPLETE else ["edit", "include"]
            action_item = QTableWidgetItem()
            action_item.setData(
                Qt.UserRole,
                {
                    "btns": btn_keys,
                    "chunk_id": chunk_id,
                    "comp_name": comp_name,
                    "idx": idx,
                    "item": item,
                },
            )
            action_item.setFlags(Qt.ItemIsEnabled)
            t.setItem(row, 7, action_item)
            t.setItem(row, 8, QTableWidgetItem())  # placeholder
            t._frozen_overlay.add_row(
                {
                    "btns": btn_keys,
                    "chunk_id": chunk_id,
                    "comp_name": comp_name,
                    "idx": idx,
                    "item": item,
                }
            )

        t.update_height()

    def _update_summary(
        self,
        total: float,
        included: int,
        total_count: int,
        cat_totals: dict,
        currency: str,
    ):
        self.total_lbl.setText(
            f"Total Recovered Value: {currency} {fmt_comma(total)}".strip()
        )
        self.count_lbl.setText(f"Included: {included} of {total_count} items")
        self.foundation_lbl.setText(
            f"Foundation: {currency} {fmt_comma(cat_totals.get('Foundation', 0))}".strip()
        )
        self.sub_lbl.setText(
            f"Sub-Structure: {currency} {fmt_comma(cat_totals.get('Sub-Structure', 0))}".strip()
        )
        self.super_lbl.setText(
            f"Super-Structure: {currency} {fmt_comma(cat_totals.get('Super-Structure', 0))}".strip()
        )
        self.misc_lbl.setText(
            f"Misc: {currency} {fmt_comma(cat_totals.get('Misc', 0))}".strip()
        )

    # ── Actions ──────────────────────────────────────────────────────────

    def _toggle_inclusion(
        self, chunk_id: str, comp_name: str, data_index: int, include: bool
    ):
        data = self.controller.engine.fetch_chunk(chunk_id) or {}
        if comp_name in data and data_index < len(data[comp_name]):
            target = data[comp_name][data_index]
            target["state"]["included_in_recyclability"] = include
            target["values"].setdefault("exclusion_reason", {})["recycling"] = "" if include else REASON_EXCLUDED
            self.controller.engine.stage_update(chunk_name=chunk_id, data=data)
            self._mark_dirty()
            QTimer.singleShot(0, self.on_refresh)

    def _open_recyclability_edit(
        self, chunk_id: str, comp_name: str, data_index: int, item: dict
    ):
        from ..structure.widgets.material_dialog import MaterialDialog

        dialog = MaterialDialog(
            comp_name, parent=self, data=item, recyclability_only=True
        )
        if dialog.exec():
            vals = dialog.get_values()
            v_vals = vals.get("values", {})
            data = self.controller.engine.fetch_chunk(chunk_id) or {}
            if comp_name in data and data_index < len(data[comp_name]):
                target = data[comp_name][data_index]
                target["values"]["post_demolition_recovery_percentage"] = v_vals.get(
                    "post_demolition_recovery_percentage"
                )
                target["values"]["scrap_rate"] = v_vals.get("scrap_rate")
                target["values"].setdefault("exclusion_reason", {})["recycling"] = ""
                target["state"]["included_in_recyclability"] = vals.get("state", {}).get(
                    "included_in_recyclability", False
                )
                target["meta"]["modified_on"] = datetime.datetime.now().isoformat()
                self.controller.engine.stage_update(chunk_name=chunk_id, data=data)
                self._mark_dirty()
                QTimer.singleShot(0, self.on_refresh)

    def _mark_dirty(self):
        if self.controller and self.controller.engine:
            eng = self.controller.engine
            eng._last_keystroke_time = time.time()
            eng._has_unsaved_changes = True
            try:
                eng.on_dirty(True)
            except Exception:
                pass

    def _compute(self) -> dict:
        cat_totals = {label: 0.0 for _, label in CHUNKS}
        included_items = []
        excluded_items = []
        total_value = 0.0
        total_count = 0
        included_count = 0

        if not self.controller or not getattr(self.controller, "engine", None):
            return {
                "total_recovered_value": 0.0,
                "cat_totals": cat_totals,
                "included_count": 0,
                "total_count": 0,
                "included_items": [],
                "excluded_items": [],
                "currency": "",
            }

        currency = self._get_currency()

        for chunk_id, category in CHUNKS:
            data = self.controller.engine.fetch_chunk(chunk_id) or {}
            for comp_name, items in data.items():
                for idx, item in enumerate(items):
                    if item.get("state", {}).get("in_trash", False):
                        continue

                    total_count += 1
                    valid = is_recyclable_valid(item)
                    included = item.get("state", {}).get(
                        "included_in_recyclability", True
                    )

                    v = item.get("values", {})
                    if valid and included:
                        included_count += 1
                        value = calc_recovered_value(item)
                        total_value += value
                        cat_totals[category] += value
                        v.setdefault("exclusion_reason", {})["recycling"] = ""
                        included_items.append(
                            (category, chunk_id, comp_name, idx, item, value)
                        )
                    else:
                        reason = REASON_INCOMPLETE if not valid else REASON_EXCLUDED
                        v.setdefault("exclusion_reason", {})["recycling"] = reason
                        excluded_items.append(
                            (category, chunk_id, comp_name, idx, item, reason)
                        )
                    self.controller.engine.stage_update(chunk_name=chunk_id, data=data)

        return {
            "total_recovered_value": total_value,
            "cat_totals": cat_totals,
            "included_count": included_count,
            "total_count": total_count,
            "included_items": included_items,
            "excluded_items": excluded_items,
            "currency": currency,
        }

    def freeze(self, frozen: bool = True):
        self._frozen = frozen
        self._included_action.set_frozen(frozen)
        self._excluded_action.set_frozen(frozen)

    def validate(self) -> dict:
        result = self._compute()
        warnings = []

        if result["total_count"] == 0:
            warnings.append(
                "No materials are available for recycling calculations - add material entries in the Construction Works Data section first"
            )
        elif result["total_recovered_value"] == 0.0:
            warnings.append(
                f"Total recovered (salvage) value is 0 - "
                f"{result['included_count']} of {result['total_count']} materials are included but none yield a positive recycled value; check recyclability percentage and scrap rate entries"
            )

        missing = sum(
            1 for *_, reason in result["excluded_items"] if reason == REASON_INCOMPLETE
        )
        if missing:
            warnings.append(
                f"{missing} material item{'s' if missing != 1 else ''} excluded from recycling calculations - "
                f"recyclability percentage or scrap rate data is missing; complete these fields in the Construction Works Data section"
            )

        return {"errors": [], "warnings": warnings}

    def get_data(self) -> dict:
        result = self._compute()
        return {
            "chunk": "recycling_data",
            "data": {
                "total_recovered_value": result["total_recovered_value"],
                "included_count": result["included_count"],
                "total_count": result["total_count"],
                "cat_totals": result["cat_totals"],
                "currency": result["currency"],
            },
        }

    def showEvent(self, event):
        super().showEvent(event)
        if not self._loaded:
            self.on_refresh()
            self._loaded = True

    def hideEvent(self, event):
        super().hideEvent(event)
        self._loaded = False

    def _on_project_reloaded(self):
        self._loaded = False
        if self.isVisible():
            self.on_refresh()
            self._loaded = True