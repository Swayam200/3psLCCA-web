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
from PySide6.QtGui import QColor
import datetime

from ...utils.unit_resolver import analyze_conversion_sympy
from ...utils.definitions import UNIT_DISPLAY
from ...utils.display_format import fmt, fmt_comma
from ...utils.icons import make_icon
from ...utils.table_widgets import (
    GroupedHeaderView,
    BaseActionDelegate,
    TooltipTableMixin,
)


def _fmt_unit(code: str) -> str:
    """Convert raw unit code to display symbol."""
    return UNIT_DISPLAY.get(code.lower(), code) if code else code


def _fmt_carbon_unit(carbon_unit: str) -> str:
    """Normalize stored carbon_unit: fix CO2e subscript and unit symbols."""
    if not carbon_unit:
        return ""
    unit = carbon_unit.replace("CO2e", "CO₂e")
    if "/" in unit:
        prefix, denom = unit.rsplit("/", 1)
        return f"{prefix}/{_fmt_unit(denom.strip())}"
    return unit


# Cache for unit analysis - keyed by (unit, carbon_denom, conv_factor)
_analysis_cache: dict = {}


def _cached_analysis(unit: str, carbon_denom: str, conv_factor) -> dict:
    key = (unit, carbon_denom, str(conv_factor))
    if key not in _analysis_cache:
        _analysis_cache[key] = analyze_conversion_sympy(unit, carbon_denom, conv_factor)
    return _analysis_cache[key]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CHUNKS = [
    ("str_foundation", "Foundation"),
    ("str_sub_structure", "Sub-Structure"),
    ("str_super_structure", "Super-Structure"),
    ("str_misc", "Misc"),
]

# Row background states - sourced from active theme; fallback keeps original colour
BG_INVALID    = get_token("danger")
BG_SUSPICIOUS = get_token("warning")
BG_DISABLED   = get_token("surface")
TEXT_DARK     = get_token("text")

REASON_INCOMPLETE  = "Incomplete Data"
REASON_SUSPICIOUS  = "Suspicious Data"
REASON_EXCLUDED    = "Manually Excluded"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_NA = {None, ""}


def _cf_value(v: dict) -> float:
    """Return the conversion factor, defaulting to 1.0 when not explicitly set."""
    raw = v.get("conversion_factor")
    if raw in _NA:
        return 1.0
    try:
        val = float(raw)
        return val if val > 0 else 1.0
    except (TypeError, ValueError):
        return 1.0


def is_carbon_valid(item) -> bool:
    """Valid when carbon_emission is non-zero and CF (if explicitly set) is positive."""
    v = item.get("values", {})
    # Explicitly stored CF of 0 or negative is invalid (not just suspicious)
    cf_raw = v.get("conversion_factor")
    if cf_raw not in _NA:
        try:
            if float(cf_raw) <= 0:
                return False
        except (TypeError, ValueError):
            pass  # unparseable CF treated as not_available → default 1.0
    try:
        emission_raw = v.get("carbon_emission")
        if emission_raw in _NA:
            return False
        return float(emission_raw) != 0
    except (TypeError, ValueError):
        return False


def calc_carbon(item: dict) -> float:
    """Carbon = quantity × conversion_factor × carbon_emission"""
    v = item.get("values", {})
    try:
        return (
            float(v.get("quantity") or 0)
            * _cf_value(v)
            * float(v.get("carbon_emission") or 0)
        )
    except (TypeError, ValueError):
        return 0.0


# ---------------------------------------------------------------------------
# Action column constants
# ---------------------------------------------------------------------------

_ACTION_W = 80  # fixed action column width (used in resizeEvent + sizeHint)


# ---------------------------------------------------------------------------
# Action column delegate
# ---------------------------------------------------------------------------


class _CarbonActionDelegate(BaseActionDelegate):
    """Paints circular icon buttons in the carbon table action column.

    Per-row data is stored in the action item's Qt.UserRole as a dict:
        {"btns": ["edit", "exclude"], "chunk_id": ..., "comp_name": ...,
         "idx": ..., "item": ...}
    """

    _ICON_CFG = {
        "edit": (None, (46, 204, 113), "Edit emission factor"),
        "exclude": (get_token("danger"), (231, 76, 60), "Exclude from calculation"),
        "include": (get_token("success"), (46, 204, 113), "Include in calculation"),
    }

    def __init__(self, table, handler):
        super().__init__(table)
        self._handler = handler  # MaterialEmissions instance
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
                        self._handler._open_emission_edit(ci, cn, idx, it)
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
            }
        """
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

    def set_row_style(self, row: int, color_hex: str):
        bg = QColor(color_hex)
        it = self.item(row, 0)
        if it:
            it.setBackground(bg)

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
# Carbon Table Widget
# ---------------------------------------------------------------------------


class CarbonTable(TooltipTableMixin, QTableWidget):
    _L = Qt.AlignLeft | Qt.AlignVCenter
    _R = Qt.AlignRight | Qt.AlignVCenter

    # Cols 2-3 → "Quantity" group;  cols 5-6 → "Emission" group
    _GROUPS = [(2, 2, "Quantity"), (5, 2, "Emission")]

    _C = Qt.AlignCenter | Qt.AlignVCenter

    INCLUDED_HEADERS = [
        ("Category", _L),  # 0
        ("Material", _L),  # 1
        ("Value", _C),  # 2  ┐ Quantity group (sub-col → center)
        ("Unit", _C),  # 3  ┘
        ("Conversion Factor", _R),  # 4
        ("Value", _C),  # 5  ┐ Emission group (sub-col → center)
        ("Unit", _C),  # 6  ┘
        ("Total Emissions \n (kgCO₂e)", _R),  # 7
        # ("Warning", _L),  # 8
        ("Action", _C),  # 9
        ("", _C),  # 10 placeholder - reserves space for frozen overlay
    ]
    EXCLUDED_HEADERS = [
        ("Category", _L),  # 0
        ("Material", _L),  # 1
        ("Value", _C),  # 2  ┐ Quantity group (sub-col → center)
        ("Unit", _C),  # 3  ┘
        ("Conversion Factor", _R),  # 4
        ("Value", _C),  # 5  ┐ Emission group (sub-col → center)
        ("Unit", _C),  # 6  ┘
        ("Reason", _L),  # 7
        ("Action", _C),  # 8
        ("", _C),  # 9 placeholder - reserves space for frozen overlay
    ]

    def __init__(self, is_included: bool, parent=None):
        super().__init__(parent)
        self.is_included = is_included

        # Install grouped header before setting column count
        self.setHorizontalHeader(GroupedHeaderView(groups=self._GROUPS))

        headers = self.INCLUDED_HEADERS if is_included else self.EXCLUDED_HEADERS
        self.setColumnCount(len(headers))
        for col, (label, align) in enumerate(headers):
            item = QTableWidgetItem(label)
            item.setTextAlignment(align)
            self.setHorizontalHeaderItem(col, item)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.horizontalHeader().setStretchLastSection(False)
        self.horizontalHeader().setMinimumSectionSize(60)
        self.setEditTriggers(QTableWidget.NoEditTriggers)
        self.setSelectionMode(QTableWidget.NoSelection)
        self.setWordWrap(True)
        self.setTextElideMode(Qt.ElideNone)
        self.verticalHeader().setDefaultSectionSize(35)
        self.verticalHeader().setVisible(False)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # Hide the real action col - frozen overlay renders it
        action_col = len(headers) - 2  # second-to-last (last is placeholder)
        self.horizontalHeader().setSectionResizeMode(action_col, QHeaderView.Fixed)
        self.setColumnWidth(action_col, 0)
        self.setColumnHidden(action_col, True)

        # Placeholder col fixed at _ACTION_W
        placeholder_col = len(headers) - 1
        self.horizontalHeader().setSectionResizeMode(placeholder_col, QHeaderView.Fixed)
        self.setColumnWidth(placeholder_col, _ACTION_W)

        # Material column stretches to fill remaining space
        if is_included:
            self.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)

        # Reserve right margin so scrollable content never enters the overlay zone
        self.setViewportMargins(0, 0, _ACTION_W, 0)

        # Frozen overlay
        self._frozen_overlay = _FrozenActionTable(self)
        self._frozen_overlay.show()

        self._set_column_widths()

    def _set_column_widths(self):
        # Initial defaults at ~800px viewport (rest ≈ 720px)
        # Sub-column pairs are equal: qty=43px each, emission=65px each
        if self.is_included:
            for col, w in enumerate([75, 164, 60, 60, 70, 85, 85, 114, 80]):
                self.setColumnWidth(col, w)
        else:
            for col, w in enumerate([72, 158, 43, 43, 50, 65, 65, 216, 80]):
                self.setColumnWidth(col, w)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # viewport() is already _ACTION_W narrower due to setViewportMargins
        rest = max(1, self.viewport().width())

        # Sub-columns in each group are EQUAL width so the spanning label is centred.
        qty_sub = max(45, int(rest * 0.06))
        em_sub = max(80, int(rest * 0.09))

        if self.is_included:
            widths = {
                0: max(120, int(rest * 0.09)),  # Category
                # col 1 Material is QHeaderView.Stretch - Qt fills remaining width
                2: qty_sub,                     # Quantity › Value
                3: qty_sub,                     # Quantity › Unit
                4: max(120, int(rest * 0.09)),  # Conv. Factor
                5: em_sub,                      # Emission › Value
                6: em_sub,                      # Emission › Unit
                7: max(70, int(rest * 0.09)),   # Total kgCO₂e
            }
        else:
            widths = {
                0: max(120, int(rest * 0.10)),  # Category
                1: max(100, int(rest * 0.22)),  # Material
                2: qty_sub,  # Quantity › Value
                3: qty_sub,  # Quantity › Unit
                4: max(120, int(rest * 0.09)),  # Conv. Factor
                5: em_sub,  # Emission › Value
                6: em_sub,  # Emission › Unit
                7: max(100, int(rest * 0.29)),  # Reason
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

    def update_height(self):
        self.resizeRowsToContents()
        self.updateGeometry()
        if hasattr(self, "_frozen_overlay"):
            self._frozen_overlay.reposition()
            self._frozen_overlay.sync_row_heights()

    def set_row_style(self, row: int, color_hex: str):
        bg = QColor(color_hex)
        is_highlighted = color_hex in [BG_INVALID, BG_SUSPICIOUS, BG_DISABLED]
        fg = QColor(TEXT_DARK if is_highlighted else "black")

        for col in range(self.columnCount()):
            it = self.item(row, col)
            if it:
                it.setBackground(bg)
                it.setForeground(fg)
            w = self.cellWidget(row, col)
            if w:
                w.setStyleSheet(
                    f"background-color: {color_hex}; color: {TEXT_DARK if is_highlighted else 'black'};"
                )
        self._frozen_overlay.set_row_style(row, color_hex)

    def showEvent(self, event):
        super().showEvent(event)
        self._frozen_overlay.reposition()

    def clear_rows(self):
        self.setRowCount(0)
        self._frozen_overlay.clear_rows()
        self.update_height()


# ---------------------------------------------------------------------------
# MaterialEmissions
# ---------------------------------------------------------------------------


class MaterialEmissions(QWidget):
    def __init__(self, controller=None):
        super().__init__()
        self.controller = controller
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

        # Outer layout holds only the scroll area, so growing tables never
        # overlap sibling widgets - the scroll area absorbs all extra height.
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        container = QWidget()
        main_layout = QVBoxLayout(container)
        main_layout.setSpacing(8)

        # Summary Bar
        self.summary_bar = QWidget()
        summary_layout = QHBoxLayout(self.summary_bar)
        self.total_lbl = QLabel("Total: - kgCO₂e")
        self.count_lbl = QLabel("Included: - of - items")
        self.details_btn = QPushButton("Show Details ▼")
        self.details_btn.setFlat(True)
        self.details_btn.clicked.connect(self._toggle_details)
        summary_layout.addWidget(self.total_lbl)
        summary_layout.addWidget(self._vline())
        summary_layout.addWidget(self.count_lbl)
        summary_layout.addStretch()
        summary_layout.addWidget(self.details_btn)
        main_layout.addWidget(self.summary_bar)

        # Details Row
        self.details_widget = QWidget()
        details_layout = QHBoxLayout(self.details_widget)
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

        main_layout.addWidget(self._section_label("Included in Carbon Emissions Calculation"))
        self.included_table = CarbonTable(is_included=True)
        self._included_action = _CarbonActionDelegate(
            self.included_table._frozen_overlay, self
        )
        self.included_table._frozen_overlay.setItemDelegateForColumn(
            0, self._included_action
        )
        main_layout.addWidget(self.included_table)
        main_layout.addWidget(self._hline())

        main_layout.addWidget(self._section_label("Excluded from Carbon Emissions Calculation"))
        self.excluded_table = CarbonTable(is_included=False)
        self._excluded_action = _CarbonActionDelegate(
            self.excluded_table._frozen_overlay, self
        )
        self.excluded_table._frozen_overlay.setItemDelegateForColumn(
            0, self._excluded_action
        )
        main_layout.addWidget(self.excluded_table)
        main_layout.addStretch()

        scroll.setWidget(container)
        outer_layout.addWidget(scroll)

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

    def on_refresh(self):
        if not self.controller or not getattr(self.controller, "engine", None):
            return

        included_items = []
        excluded_items = []
        cat_totals = {label: 0.0 for _, label in CHUNKS}
        total_carbon = 0.0
        total_count = 0
        included_count = 0

        for chunk_id, category in CHUNKS:
            data = self.controller.engine.fetch_chunk(chunk_id) or {}
            for comp_name, items in data.items():
                for idx, item in enumerate(items):
                    if item.get("state", {}).get("in_trash", False):
                        continue

                    total_count += 1
                    v = item.get("values", {})
                    state = item.get("state", {})

                    # Target denominator for carbon is usually the unit after the slash
                    carbon_unit = v.get("carbon_unit", "")
                    carbon_denom = (
                        carbon_unit.split("/")[-1] if carbon_unit and "/" in carbon_unit else ""
                    )

                    # Unit resolver analysis (cached - same inputs always yield same result)
                    analysis = _cached_analysis(
                        v.get("unit", ""), carbon_denom, _cf_value(v)
                    )

                    valid = is_carbon_valid(item)
                    is_included_flag = state.get("included_in_carbon_emission") is True
                    is_confirmed = state.get("carbon_conversion_confirmed", False)
                    suspicious = analysis["is_suspicious"] and not is_confirmed

                    if suspicious and is_included_flag:
                        state["included_in_carbon_emission"] = False
                        is_included_flag = False
                        self.controller.engine.stage_update(chunk_name=chunk_id, data=data)

                    if valid and is_included_flag and not suspicious:
                        included_count += 1
                        carbon = calc_carbon(item)
                        total_carbon += carbon
                        cat_totals[category] += carbon
                        v.setdefault("exclusion_reason", {})["carbon"] = ""
                        included_items.append(
                            (category, chunk_id, comp_name, idx, item, carbon, analysis)
                        )
                    else:
                        reason = (
                            REASON_INCOMPLETE
                            if not valid
                            else (REASON_SUSPICIOUS if suspicious else REASON_EXCLUDED)
                        )
                        v.setdefault("exclusion_reason", {})["carbon"] = reason
                        excluded_items.append(
                            (category, chunk_id, comp_name, idx, item, reason, analysis)
                        )
                    self.controller.engine.stage_update(chunk_name=chunk_id, data=data)

        self._populate_included(included_items)
        self._populate_excluded(excluded_items)
        self._update_summary(total_carbon, included_count, total_count, cat_totals)

    def _populate_included(self, items):
        t = self.included_table
        t.setUpdatesEnabled(False)
        t.clear_rows()
        for category, chunk_id, comp_name, idx, item, carbon, analysis in items:
            v = item.get("values", {})
            row = t.rowCount()
            t.insertRow(row)

            def _ri(text):
                it = QTableWidgetItem(text)
                it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                return it

            t.setItem(row, 0, QTableWidgetItem(category))
            t.setItem(row, 1, QTableWidgetItem(v.get("material_name", "")))
            t.setItem(row, 2, _ri(fmt(v.get("quantity", 0))))
            t.setItem(row, 3, QTableWidgetItem(_fmt_unit(v.get("unit", ""))))
            _cf_raw = v.get("conversion_factor")
            t.setItem(row, 4, _ri(fmt(_cf_raw) if _cf_raw not in _NA else "-"))
            t.setItem(row, 5, _ri(fmt(v.get("carbon_emission"))))
            t.setItem(
                row, 6, QTableWidgetItem(_fmt_carbon_unit(v.get("carbon_unit")))
            )

            carbon_item = QTableWidgetItem(fmt(carbon))
            carbon_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            t.setItem(row, 7, carbon_item)

            # Persistent Warnings: Check for zero qty or if the confirmed factor is still suspicious
            warnings = []
            if float(v.get("quantity", 0) or 0) == 0:
                warnings.append("Zero Quantity")
            if analysis["is_suspicious"]:
                warnings.append("⚠️ Conversion Factor seems incorrect.")

            t.setItem(row, 8, QTableWidgetItem(", ".join(warnings)))

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
        t.setUpdatesEnabled(True)

    def _populate_excluded(self, items):
        t = self.excluded_table
        t.setUpdatesEnabled(False)
        t.clear_rows()
        for category, chunk_id, comp_name, idx, item, reason, analysis in items:
            v = item.get("values", {})
            row = t.rowCount()
            t.insertRow(row)

            def _ri(text):
                it = QTableWidgetItem(text)
                it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                return it

            t.setItem(row, 0, QTableWidgetItem(category))
            t.setItem(row, 1, QTableWidgetItem(v.get("material_name", "")))
            t.setItem(row, 2, _ri(fmt(v.get("quantity", 0))))
            t.setItem(row, 3, QTableWidgetItem(_fmt_unit(v.get("unit", ""))))
            _cf_raw = v.get("conversion_factor")
            t.setItem(row, 4, _ri(fmt(_cf_raw) if _cf_raw not in _NA else "-"))
            t.setItem(row, 5, _ri(fmt(v.get("carbon_emission"))))
            t.setItem(
                row, 6, QTableWidgetItem(_fmt_carbon_unit(v.get("carbon_unit")))
            )
            t.setItem(row, 7, QTableWidgetItem(reason))

            if reason in [REASON_INCOMPLETE, REASON_SUSPICIOUS]:
                t.set_row_style(
                    row, BG_INVALID if reason == REASON_INCOMPLETE else BG_SUSPICIOUS
                )
                btn_keys = ["edit"]
            else:
                btn_keys = ["edit", "include"]

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
            t.setItem(row, 8, action_item)
            t.setItem(row, 9, QTableWidgetItem())  # placeholder
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
        t.setUpdatesEnabled(True)

    def _update_summary(
        self, total: float, included: int, total_count: int, cat_totals: dict
    ):
        self.total_lbl.setText(f"Total: {fmt_comma(total)} kgCO₂e")
        self.count_lbl.setText(f"Included: {included} of {total_count} items")
        self.foundation_lbl.setText(
            f"Foundation: {fmt_comma(cat_totals.get('Foundation', 0))}"
        )
        self.sub_lbl.setText(
            f"Sub-Structure: {fmt_comma(cat_totals.get('Sub-Structure', 0))}"
        )
        self.super_lbl.setText(
            f"Super-Structure: {fmt_comma(cat_totals.get('Super-Structure', 0))}"
        )
        self.misc_lbl.setText(f"Misc: {fmt_comma(cat_totals.get('Misc', 0))}")

    def _find_row_in_overlay(self, overlay, chunk_id, comp_name, idx) -> int:
        for row in range(overlay.rowCount()):
            cell = overlay.item(row, 0)
            if cell:
                d = cell.data(Qt.UserRole)
                if (d and d.get("chunk_id") == chunk_id
                        and d.get("comp_name") == comp_name
                        and d.get("idx") == idx):
                    return row
        return -1

    def _refresh_summary_only(self):
        result = self._compute()
        self._update_summary(
            result["total_carbon"],
            result["included_count"],
            result["total_count"],
            result["cat_totals"],
        )

    def _do_move_row(self, src_row: int, include: bool, item_data: dict,
                     category: str, chunk_id: str, comp_name: str, idx: int):
        """Move one row between tables. include=True: excluded→included."""

        def _ri(text):
            it = QTableWidgetItem(text)
            it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            return it

        src = self.excluded_table if include else self.included_table
        src.removeRow(src_row)
        src._frozen_overlay.removeRow(src_row)
        src.update_height()

        v = item_data.get("values", {})
        _cu = v.get("carbon_unit") or ""
        carbon_denom = _cu.split("/")[-1] if "/" in _cu else ""
        analysis = _cached_analysis(v.get("unit", ""), carbon_denom, _cf_value(v))
        _cf_raw = v.get("conversion_factor")

        if include:
            # Block re-inclusion of a suspicious unconfirmed item
            is_confirmed = item_data.get("state", {}).get("carbon_conversion_confirmed", False)
            if analysis["is_suspicious"] and not is_confirmed:
                # Leave it in excluded; ensure flag and reason are correct in data
                data = self.controller.engine.fetch_chunk(chunk_id) or {}
                if comp_name in data and idx < len(data[comp_name]):
                    data[comp_name][idx]["state"]["included_in_carbon_emission"] = False
                    data[comp_name][idx]["values"].setdefault("exclusion_reason", {})["carbon"] = "Suspicious Data"
                    self.controller.engine.stage_update(chunk_name=chunk_id, data=data)
                QTimer.singleShot(0, self.on_refresh)
                return

            # Clear reason when successfully moving to included
            live_data = self.controller.engine.fetch_chunk(chunk_id) or {}
            if comp_name in live_data and idx < len(live_data[comp_name]):
                live_data[comp_name][idx]["values"].setdefault("exclusion_reason", {})["carbon"] = ""
                self.controller.engine.stage_update(chunk_name=chunk_id, data=live_data)

            t = self.included_table
            carbon = calc_carbon(item_data)
            row = t.rowCount()
            t.insertRow(row)
            t.setItem(row, 0, QTableWidgetItem(category))
            t.setItem(row, 1, QTableWidgetItem(v.get("material_name", "")))
            t.setItem(row, 2, _ri(fmt(v.get("quantity", 0))))
            t.setItem(row, 3, QTableWidgetItem(_fmt_unit(v.get("unit", ""))))
            t.setItem(row, 4, _ri(fmt(_cf_raw) if _cf_raw not in _NA else "-"))
            t.setItem(row, 5, _ri(fmt(v.get("carbon_emission"))))
            t.setItem(row, 6, QTableWidgetItem(_fmt_carbon_unit(v.get("carbon_unit"))))
            carbon_item = QTableWidgetItem(fmt(carbon))
            carbon_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            t.setItem(row, 7, carbon_item)
            warnings = []
            if float(v.get("quantity", 0) or 0) == 0:
                warnings.append("Zero Quantity")
            if analysis["is_suspicious"]:
                warnings.append("⚠️ Conversion Factor seems incorrect.")
            t.setItem(row, 8, QTableWidgetItem(", ".join(warnings)))
            row_data = {"btns": ["edit", "exclude"], "chunk_id": chunk_id,
                        "comp_name": comp_name, "idx": idx, "item": item_data}
            action_item = QTableWidgetItem()
            action_item.setData(Qt.UserRole, row_data)
            action_item.setFlags(Qt.ItemIsEnabled)
            t.setItem(row, 9, action_item)
            t.setItem(row, 10, QTableWidgetItem())
            t._frozen_overlay.add_row(row_data)
        else:
            # Write reason when moving to excluded
            live_data = self.controller.engine.fetch_chunk(chunk_id) or {}
            if comp_name in live_data and idx < len(live_data[comp_name]):
                live_data[comp_name][idx]["values"].setdefault("exclusion_reason", {})["carbon"] = "User Excluded"
                self.controller.engine.stage_update(chunk_name=chunk_id, data=live_data)

            t = self.excluded_table
            row = t.rowCount()
            t.insertRow(row)
            t.setItem(row, 0, QTableWidgetItem(category))
            t.setItem(row, 1, QTableWidgetItem(v.get("material_name", "")))
            t.setItem(row, 2, _ri(fmt(v.get("quantity", 0))))
            t.setItem(row, 3, QTableWidgetItem(_fmt_unit(v.get("unit", ""))))
            t.setItem(row, 4, _ri(fmt(_cf_raw) if _cf_raw not in _NA else "-"))
            t.setItem(row, 5, _ri(fmt(v.get("carbon_emission"))))
            t.setItem(row, 6, QTableWidgetItem(_fmt_carbon_unit(v.get("carbon_unit"))))
            t.setItem(row, 7, QTableWidgetItem("User Excluded"))
            row_data = {"btns": ["edit", "include"], "chunk_id": chunk_id,
                        "comp_name": comp_name, "idx": idx, "item": item_data}
            action_item = QTableWidgetItem()
            action_item.setData(Qt.UserRole, row_data)
            action_item.setFlags(Qt.ItemIsEnabled)
            t.setItem(row, 8, action_item)
            t.setItem(row, 9, QTableWidgetItem())
            t._frozen_overlay.add_row(row_data)

        t.update_height()
        self._refresh_summary_only()

    def _toggle_inclusion(
        self, chunk_id: str, comp_name: str, data_index: int, include: bool
    ):
        data = self.controller.engine.fetch_chunk(chunk_id) or {}
        if comp_name in data and data_index < len(data[comp_name]):
            target = data[comp_name][data_index]
            target["state"]["included_in_carbon_emission"] = include
            target["values"].setdefault("exclusion_reason", {})["carbon"] = "" if include else "User Excluded"
            self.controller.engine.stage_update(chunk_name=chunk_id, data=data)
            self._mark_dirty()

            src_overlay = (
                self.included_table._frozen_overlay if not include
                else self.excluded_table._frozen_overlay
            )
            src_row = self._find_row_in_overlay(
                src_overlay, chunk_id, comp_name, data_index
            )

            if src_row >= 0:
                src_main = self.included_table if not include else self.excluded_table
                category = (src_main.item(src_row, 0).text()
                            if src_main.item(src_row, 0) else "")
                item_snap = src_overlay.item(src_row, 0).data(Qt.UserRole)["item"]

                def _do(r=src_row, inc=include, idata=item_snap, cat=category,
                        ci=chunk_id, cn=comp_name, di=data_index):
                    self._do_move_row(r, inc, idata, cat, ci, cn, di)

                QTimer.singleShot(0, _do)
            else:
                QTimer.singleShot(0, self.on_refresh)

    def _open_emission_edit(
        self, chunk_id: str, comp_name: str, data_index: int, item: dict
    ):
        from ...structure.widgets.material_dialog import MaterialDialog

        dialog = MaterialDialog(comp_name, parent=self, data=item, emissions_only=True)
        if dialog.exec():
            vals = dialog.get_values()
            v_vals = vals.get("values", {})
            data = self.controller.engine.fetch_chunk(chunk_id) or {}
            if comp_name in data and data_index < len(data[comp_name]):
                target = data[comp_name][data_index]
                target["values"]["carbon_emission"] = v_vals.get("carbon_emission", 0.0)
                target["values"]["carbon_unit"] = v_vals.get("carbon_unit", "")
                target["values"]["conversion_factor"] = v_vals.get("conversion_factor", 1.0)
                target["values"].setdefault("exclusion_reason", {})["carbon"] = ""
                target["state"]["included_in_carbon_emission"] = vals.get("state", {}).get(
                    "included_in_carbon_emission", True
                )
                target["state"]["carbon_conversion_confirmed"] = True
                target["meta"]["modified_on"] = datetime.datetime.now().isoformat()
                self.controller.engine.stage_update(chunk_name=chunk_id, data=data)
                self._mark_dirty()
                QTimer.singleShot(0, self.on_refresh)

    def _mark_dirty(self):
        if self.controller and self.controller.engine:
            import time

            eng = self.controller.engine
            eng._last_keystroke_time = time.time()
            eng._has_unsaved_changes = True
            try:
                eng.on_dirty(True)
            except:
                pass

    def _compute(self) -> dict:
        """
        Core calculation logic shared by on_refresh(), validate(), and get_data().
        Returns raw computed data without touching any UI.
        """
        cat_totals = {label: 0.0 for _, label in CHUNKS}
        included_items = []
        excluded_items = []
        total_carbon = 0.0
        total_count = 0
        included_count = 0

        if not self.controller or not getattr(self.controller, "engine", None):
            return {
                "total_carbon": 0.0,
                "cat_totals": cat_totals,
                "included_count": 0,
                "total_count": 0,
                "included_items": [],
                "excluded_items": [],
            }

        for chunk_id, category in CHUNKS:
            data = self.controller.engine.fetch_chunk(chunk_id) or {}
            for comp_name, items in data.items():
                for idx, item in enumerate(items):
                    if item.get("state", {}).get("in_trash", False):
                        continue
                    total_count += 1
                    v = item.get("values", {})
                    state = item.get("state", {})
                    carbon_unit = v.get("carbon_unit", "")
                    carbon_denom = (
                        carbon_unit.split("/")[-1] if carbon_unit and "/" in carbon_unit else ""
                    )
                    analysis = _cached_analysis(
                        v.get("unit", ""), carbon_denom, _cf_value(v)
                    )
                    valid = is_carbon_valid(item)
                    is_included_flag = state.get("included_in_carbon_emission") is True
                    is_confirmed = state.get("carbon_conversion_confirmed", False)
                    suspicious = analysis["is_suspicious"] and not is_confirmed

                    if suspicious and is_included_flag:
                        state["included_in_carbon_emission"] = False
                        is_included_flag = False
                        self.controller.engine.stage_update(chunk_name=chunk_id, data=data)

                    if valid and is_included_flag and not suspicious:
                        included_count += 1
                        carbon = calc_carbon(item)
                        total_carbon += carbon
                        cat_totals[category] += carbon
                        v.setdefault("exclusion_reason", {})["carbon"] = ""
                        included_items.append(
                            (category, chunk_id, comp_name, idx, item, carbon, analysis)
                        )
                    else:
                        reason = (
                            REASON_INCOMPLETE
                            if not valid
                            else (REASON_SUSPICIOUS if suspicious else REASON_EXCLUDED)
                        )
                        v.setdefault("exclusion_reason", {})["carbon"] = reason
                        excluded_items.append(
                            (category, chunk_id, comp_name, idx, item, reason, analysis)
                        )
                    self.controller.engine.stage_update(chunk_name=chunk_id, data=data)

        return {
            "total_carbon": total_carbon,
            "cat_totals": cat_totals,
            "included_count": included_count,
            "total_count": total_count,
            "included_items": included_items,
            "excluded_items": excluded_items,
        }

    def validate(self) -> dict:
        result = self._compute()
        warnings = []

        if result["total_count"] == 0:
            warnings.append(
                "No materials are available for emission calculations \u2014 add material entries in the Construction Works Data section first"
            )
        elif result["total_carbon"] == 0.0:
            warnings.append(
                f"Total material carbon emission is 0 kgCO\u2082e \u2014 "
                f"{result['included_count']} of {result['total_count']} materials are included but no positive carbon values were found; check emission factors and material quantities"
            )

        missing = sum(
            1 for *_, reason, _ in result["excluded_items"] if reason == REASON_INCOMPLETE
        )
        suspicious = sum(
            1
            for *_, reason, _ in result["excluded_items"]
            if reason == REASON_SUSPICIOUS
        )
        if missing:
            warnings.append(
                f"{missing} material item{'s' if missing != 1 else ''} excluded from carbon calculations - "
                f"emission factor data is missing or not assigned; set the emission factor in the Construction Works Data section"
            )
        if suspicious:
            warnings.append(
                f"{suspicious} material item{'s' if suspicious != 1 else ''} excluded - "
                f"the unit conversion factor is flagged as suspicious and has not been confirmed; review and confirm the conversion factor in the material entry"
            )

        return {"errors": [], "warnings": warnings}


    def get_data(self) -> dict:
        result = self._compute()
        return {
            "chunk": "material_emissions_data",
            "data": {
                "total_kgCO2e": result["total_carbon"],
                "included_count": result["included_count"],
                "total_count": result["total_count"],
                "cat_totals": result["cat_totals"],
            },
        }

    def freeze(self, frozen: bool = True):
        self._frozen = frozen
        self._included_action.set_frozen(frozen)
        self._excluded_action.set_frozen(frozen)

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