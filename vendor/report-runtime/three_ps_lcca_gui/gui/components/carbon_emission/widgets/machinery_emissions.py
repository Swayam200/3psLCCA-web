"""
gui/components/carbon_emission/widgets/machinery_emissions.py

Chunk: machinery_emissions_data

Two modes toggled by radio buttons:
  - Detailed Equipment List  (table with per-row calculation)
  - Lump Sum                 (electricity + fuel - built via build_form)

Grand total shown at top and bottom.
Currency label pulled from general_info chunk.
"""

from three_ps_lcca_gui.gui.themes import get_token
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt, QEvent, QRect, QSize
from PySide6.QtGui import QFont

from ...base_widget import ScrollableForm
from ...utils.form_builder.form_definitions import FieldDef, Section
from ...utils.form_builder.form_builder import build_form
from ...utils.remarks_editor import RemarksEditor
from ...utils.display_format import fmt, fmt_comma, DECIMAL_PLACES
from ...utils.icons import make_icon
from ...utils.table_widgets import BaseActionDelegate, TooltipTableMixin
from ...utils.validation_helpers import freeze_widgets, confirm_clear_all

CHUNK = "machinery_emissions_data"
_ACTION_W = 80   # frozen action-column width (edit + delete)

ENERGY_SOURCES = [
    "Diesel",
    "Electricity (Grid)",
    "Electricity (Solar/Renewable)",
    "Other",
]

EF_DEFAULTS = {
    "Diesel": 2.69,
    "Electricity (Grid)": 0.71,
    "Electricity (Solar/Renewable)": 0.0,
    "Other": 0.0,
}

RATE_SUFFIX = {
    "Diesel": " l/hr",
    "Electricity (Grid)": " kW",
    "Electricity (Solar/Renewable)": " kW",
    "Other": " units/hr",
}

CONSUMPTION_UNIT = {
    "Diesel": "litres",
    "Electricity (Grid)": "kWh",
    "Electricity (Solar/Renewable)": "kWh",
    "Other": "units",
}

DEFAULT_MACHINERY_DATA = [
    {"name": "Backhoe loader (JCB)", "source": "Diesel", "rate": 5.0, "ef": 2.69},
    {
        "name": "Bar bending machine",
        "source": "Electricity (Grid)",
        "rate": 3.0,
        "ef": 0.71,
    },
    {
        "name": "Bar cutting machine",
        "source": "Electricity (Grid)",
        "rate": 4.0,
        "ef": 0.71,
    },
    {"name": "Bitumen boiler", "source": "Diesel", "rate": 1.0, "ef": 2.69},
    {"name": "Bitumen sprayer", "source": "Diesel", "rate": 5.0, "ef": 2.69},
    {"name": "Concrete pump", "source": "Diesel", "rate": 12.0, "ef": 2.69},
    {"name": "Crane (crawler)", "source": "Diesel", "rate": 12.0, "ef": 2.69},
    {"name": "Crane (mobile)", "source": "Diesel", "rate": 8.0, "ef": 2.69},
    {"name": "Dewatering pump", "source": "Diesel", "rate": 2.0, "ef": 2.69},
    {"name": "DG set", "source": "Diesel", "rate": 4.0, "ef": 2.69},
    {"name": "Grouting mixer", "source": "Electricity (Grid)", "rate": 1.0, "ef": 0.71},
    {"name": "Grouting pump", "source": "Electricity (Grid)", "rate": 5.0, "ef": 0.71},
    {"name": "Hydraulic excavator", "source": "Diesel", "rate": 14.0, "ef": 2.69},
    {
        "name": "Hydraulic stressing jack",
        "source": "Electricity (Grid)",
        "rate": 3.0,
        "ef": 0.71,
    },
    {
        "name": "Needle Vibrator",
        "source": "Electricity (Grid)",
        "rate": 1.0,
        "ef": 0.71,
    },
    {"name": "Paver finisher", "source": "Diesel", "rate": 7.0, "ef": 2.69},
    {"name": "Road roller", "source": "Diesel", "rate": 4.0, "ef": 2.69},
    {
        "name": "Rotary piling rig/Hydraulic piling rig",
        "source": "Diesel",
        "rate": 15.0,
        "ef": 2.69,
    },
    {
        "name": "Site office (If Grid electricity is used)",
        "source": "Electricity (Grid)",
        "rate": 4.0,
        "ef": 0.71,
    },
    {
        "name": "Welding machine",
        "source": "Electricity (Grid)",
        "rate": 4.0,
        "ef": 0.71,
    },
]

# ── Field definitions - passed to build_form ──────────────────────────────────

LUMPSUM_ELEC_FIELDS = [
    Section("Electricity Consumption"),
    FieldDef(
        "elec_consumption_per_day",
        "Electricity Consumption per Day",
        "Total electricity consumed per working day across all equipment.",
        "float",
        options=(0.0, 1e12, DECIMAL_PLACES),
        unit="(kWh/day)",
    ),
    FieldDef(
        "elec_days",
        "Number of Days",
        "Total number of working days for electricity consumption.",
        "int",
        options=(0, 9999),
        unit="(days)",
    ),
    FieldDef(
        "elec_ef",
        "Emission Factor",
        "Grid electricity emission factor (kg CO₂e per kWh).",
        "float",
        options=(0.0, 999.0, DECIMAL_PLACES),
        unit="(kg CO₂e/kWh)",
    ),
]

LUMPSUM_FUEL_FIELDS = [
    Section("Fuel Consumption"),
    FieldDef(
        "fuel_consumption_per_day",
        "Fuel Consumption per Day",
        "Total fuel consumed per working day across all equipment.",
        "float",
        options=(0.0, 1e12, DECIMAL_PLACES),
        unit="(litres/day)",
    ),
    FieldDef(
        "fuel_days",
        "Number of Days",
        "Total number of working days for fuel consumption.",
        "int",
        options=(0, 9999),
        unit="(days)",
    ),
    FieldDef(
        "fuel_ef",
        "Emission Factor",
        "Emission factor (kg CO₂e per litre).",
        "float",
        options=(0.0, 999.0, DECIMAL_PLACES),
        unit="(kg CO₂e/litre)",
    ),
]

_LUMPSUM_KEYS = [
    ("elec_consumption_per_day", 0.0),
    ("elec_days", 0),
    ("elec_ef", 0.0),
    ("fuel_consumption_per_day", 0.0),
    ("fuel_days", 0),
    ("fuel_ef", 0.0),
]



# ── Action delegate - paints edit + delete icon buttons ───────────────────────


class _ActionDelegate(BaseActionDelegate):
    """Paints circular Edit and Delete buttons in the frozen action column."""

    BTN_GAP = 8

    def __init__(self, table, detail_table):
        super().__init__(table)
        self._detail_table = detail_table
        self._btns = [
            (make_icon("edit"), (46, 204, 113), "edit", "Edit"),
            (make_icon("trash", color=get_token("danger")), (231, 76, 60), "delete", "Remove row"),
        ]
        # Also watch the frozen table widget itself so Leave clears hover
        # even when the cursor exits via the frame/header rather than the viewport.
        table.setMouseTracking(True)
        table.installEventFilter(self)

    def eventFilter(self, obj, event):
        # Clear hover when the mouse leaves the entire frozen column widget.
        try:
            vp = self._table.viewport()
        except RuntimeError:
            return False
        if obj is self._table and event.type() == QEvent.Leave:
            self._set_hovered(-1, -1)
            return False
        # Delegate standard viewport hover tracking to the base class.
        return super().eventFilter(obj, event)

    def _get_btns_for_row(self, row) -> list[tuple]:
        return [(icon, hover_rgb, tooltip) for icon, hover_rgb, _, tooltip in self._btns]

    def _btn_rects(self, cell_rect, n):
        """Center all buttons horizontally within the cell."""
        total_w = n * self.BTN_SIZE + (n - 1) * self.BTN_GAP
        x0 = cell_rect.x() + (cell_rect.width() - total_w) // 2
        y = cell_rect.y() + (cell_rect.height() - self.BTN_SIZE) // 2
        return [
            QRect(x0 + i * (self.BTN_SIZE + self.BTN_GAP), y, self.BTN_SIZE, self.BTN_SIZE)
            for i in range(n)
        ]

    def sizeHint(self, option, index):
        return QSize(_ACTION_W, _DetailedTable._ROW_H)

    def editorEvent(self, event, model, option, index):
        if self._frozen:
            return False
        if event.type() == QEvent.MouseButtonRelease:
            rects = self._btn_rects(option.rect, len(self._btns))
            for i, (_, _, action, *__) in enumerate(self._btns):
                if rects[i].contains(event.pos()):
                    if action == "edit":
                        self._detail_table._open_edit_dialog(index.row())
                    elif action == "delete":
                        self._detail_table._delete_row(index.row())
                    return True
        return False


# ── Edit row dialog ────────────────────────────────────────────────────────────


class _EditRowDialog(QDialog):
    """Dialog for editing a single equipment row's fields."""

    def __init__(self, row_data: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Equipment")
        self.setMinimumWidth(400)

        layout = QFormLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        self._name = QLineEdit(row_data.get("name", ""))

        self._source = QComboBox()
        self._source.addItems(ENERGY_SOURCES)
        src = row_data.get("source", ENERGY_SOURCES[0])
        self._source.setCurrentIndex(max(0, self._source.findText(src)))

        self._rate = QDoubleSpinBox()
        self._rate.setRange(0.0, 1e9)
        self._rate.setDecimals(DECIMAL_PLACES)
        self._rate.setValue(row_data.get("rate", 0.0))
        self._rate.setSuffix(RATE_SUFFIX.get(src, " units/hr"))

        self._hrs = QDoubleSpinBox()
        self._hrs.setRange(0.0, 24.0)
        self._hrs.setDecimals(DECIMAL_PLACES)
        self._hrs.setValue(row_data.get("hrs", 0.0))
        self._hrs.setSuffix(" hrs/day")

        self._days = QSpinBox()
        self._days.setRange(0, 9999)
        self._days.setValue(row_data.get("days", 0))
        self._days.setSuffix(" days")

        self._ef = QDoubleSpinBox()
        self._ef.setRange(0.0, 999.0)
        self._ef.setDecimals(DECIMAL_PLACES)
        self._ef.setValue(row_data.get("ef", 0.0))
        self._ef.setSuffix(" kg CO₂e/unit")

        layout.addRow("Equipment Name:", self._name)
        layout.addRow("Energy Source:", self._source)
        layout.addRow("Fuel / Power Rating:", self._rate)
        layout.addRow("Avg Hrs/Day:", self._hrs)
        layout.addRow("No. of Days:", self._days)
        layout.addRow("EF:", self._ef)

        self._source.currentTextChanged.connect(self._on_source_changed)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _on_source_changed(self, src: str):
        self._rate.setSuffix(RATE_SUFFIX.get(src, " units/hr"))
        self._ef.setValue(EF_DEFAULTS.get(src, 0.0))

    def get_values(self) -> dict:
        return {
            "name": self._name.text().strip(),
            "source": self._source.currentText(),
            "rate": self._rate.value(),
            "hrs": self._hrs.value(),
            "days": self._days.value(),
            "ef": self._ef.value(),
        }


# ── Frozen delete-button column overlay ───────────────────────────────────────


class _FrozenActionCol(QTableWidget):
    """Delete-button column pinned to the right edge of the table, never scrolls."""

    def __init__(self, parent_table: QTableWidget, row_h: int):
        super().__init__(parent_table)
        self._parent_table = parent_table
        self._row_h = row_h

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
        self.setMouseTracking(True)
        self.setStyleSheet(
            "QTableWidget { background-color: palette(base); border-top-left-radius: 0px;"
            " border-bottom-left-radius: 0px; border-bottom-right-radius: 7px; }"
        )
        self.viewport().setStyleSheet("border-bottom-right-radius: 7px;")
        self.viewport().setMouseTracking(True)

        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(row_h)
        self.verticalHeader().setMinimumSectionSize(row_h)

        hdr = self.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.Fixed)
        self.setColumnWidth(0, _ACTION_W)

        parent_table.verticalScrollBar().valueChanged.connect(
            self.verticalScrollBar().setValue
        )

    def sync_row_heights(self):
        for r in range(self.rowCount()):
            self.setRowHeight(r, self._parent_table.rowHeight(r))

    def add_row(self):
        row = self.rowCount()
        self.insertRow(row)
        self.setRowHeight(row, self._row_h)
        item = QTableWidgetItem()
        item.setData(Qt.UserRole, row)
        item.setFlags(Qt.ItemIsEnabled)
        self.setItem(row, 0, item)

    def reposition(self):
        p = self._parent_table
        hdr_h = p.horizontalHeader().height()
        self.horizontalHeader().setFixedHeight(hdr_h)
        vp = p.viewport()
        
        # Position at absolute right edge of the table widget
        x = p.width() - _ACTION_W
        y = vp.y() - hdr_h
        
        self.move(x, y)
        self.setFixedHeight(vp.height() + hdr_h)
        self.raise_()


# ── Detailed equipment table ──────────────────────────────────────────────────


class _MachineryTable(TooltipTableMixin, QTableWidget):
    """Equipment table that reports its full content height as its size hint.

    With a Fixed vertical size policy (set by the owner), the surrounding layout
    reserves exactly header + all rows, so every row is shown without the table's
    own scrollbar and the subtotal/button rows below are never overlapped; the
    page's scroll area does the scrolling. This hint is the single source of
    truth for the table's height - no manual pinning or deferred geometry passes.
    """

    def _content_height(self) -> int:
        hh = self.horizontalHeader()
        h = (hh.height() or hh.sizeHint().height()) + 2 * self.frameWidth()
        for r in range(self.rowCount()):
            h += self.rowHeight(r)
        return h

    def sizeHint(self) -> QSize:
        return QSize(super().sizeHint().width(), self._content_height())

    def minimumSizeHint(self) -> QSize:
        return QSize(super().minimumSizeHint().width(), self._content_height())


class _DetailedTable(QWidget):
    # Header labels are left-aligned even for numeric (right-aligned data)
    # columns: when a column is too narrow for its full heading, Qt anchors
    # visible text to the alignment edge - right-aligned text would show the
    # *tail* of the label (e.g. "ssion") instead of its start ("Emiss").
    # Left alignment keeps the beginning of the label visible regardless of
    # column width. Data-cell alignment (set per-item in _add_blank_row) is
    # unaffected by this and stays right-aligned for numbers.
    HEADERS = [
        ("Equipment Name",      Qt.AlignLeft   | Qt.AlignVCenter),  # 0
        ("Energy Source",       Qt.AlignLeft   | Qt.AlignVCenter),  # 1
        ("Fuel / Power Rating", Qt.AlignLeft   | Qt.AlignVCenter),  # 2
        ("Avg Hrs/Day",         Qt.AlignLeft   | Qt.AlignVCenter),  # 3
        ("No. of Days",         Qt.AlignLeft   | Qt.AlignVCenter),  # 4
        ("EF (kg CO₂e/unit)",   Qt.AlignLeft   | Qt.AlignVCenter),  # 5
        ("Consumption",         Qt.AlignLeft   | Qt.AlignVCenter),  # 6
        ("Emissions (kg CO₂e)", Qt.AlignLeft   | Qt.AlignVCenter),  # 7
        ("Action",              Qt.AlignCenter | Qt.AlignVCenter),  # 8 hidden - frozen overlay
        ("",                    Qt.AlignCenter | Qt.AlignVCenter),  # 9 placeholder - reserves _ACTION_W
    ]
    _ROW_H = 36

    def __init__(self, on_change, parent=None):
        super().__init__(parent)
        self._on_change = on_change
        self._cached_total: float = 0.0  # updated by _recalculate, read by get_total

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Table - no fixed height; grows/shrinks via sizeHint override
        self._table = _MachineryTable(0, len(self.HEADERS))
        for col, (label, align) in enumerate(self.HEADERS):
            item = QTableWidgetItem(label)
            item.setTextAlignment(align)
            self._table.setHorizontalHeaderItem(col, item)
        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.Interactive)
        hh.setStretchLastSection(False)
        hh.setMinimumSectionSize(60)
        # Equipment Name absorbs all remaining width automatically (same
        # pattern as material_emissions.py's "Material" column) so the row of
        # real columns always fills exactly 100% of the viewport - manual
        # ratio math elsewhere can under-fill by a few px from int() rounding,
        # leaving a gap short of the frozen action-column overlay instead of
        # extending fully underneath it.
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        hh.setSectionResizeMode(8, QHeaderView.Fixed)
        self._table.setColumnWidth(8, 0)
        self._table.setColumnHidden(8, True)
        hh.setSectionResizeMode(9, QHeaderView.Fixed)
        self._table.setColumnWidth(9, _ACTION_W)
        self._table.setViewportMargins(0, 0, _ACTION_W, 0)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setSelectionMode(QTableWidget.SingleSelection)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.verticalHeader().setDefaultSectionSize(self._ROW_H)
        self._table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self._table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._table.cellChanged.connect(self._on_cell_changed)
        self._table.cellDoubleClicked.connect(self._open_edit_dialog)
        self._table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._table.setMinimumWidth(0)
        self._table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        layout.addWidget(self._table)

        self._frozen_col = _FrozenActionCol(self._table, self._ROW_H)
        self._action_delegate = _ActionDelegate(self._frozen_col, self)
        self._frozen_col.setItemDelegateForColumn(0, self._action_delegate)
        self._frozen_col.show()
        self._frozen_col.raise_()

        # Subtotals
        sub_layout = QHBoxLayout()
        self._lbl_diesel_sub = QLabel(f"Diesel: {fmt(0.0)} kg CO₂e")
        self._lbl_elec_sub = QLabel(f"Electricity: {fmt(0.0)} kg CO₂e")
        self._lbl_detail_total = QLabel(f"Subtotal: {fmt(0.0)} kg CO₂e")
        bold = QFont()
        bold.setBold(True)
        self._lbl_detail_total.setFont(bold)
        sub_layout.addWidget(self._lbl_diesel_sub)
        sub_layout.addSpacing(20)
        sub_layout.addWidget(self._lbl_elec_sub)
        sub_layout.addStretch()
        sub_layout.addWidget(self._lbl_detail_total)
        layout.addLayout(sub_layout)

        # Buttons
        btn_layout = QHBoxLayout()
        self.btn_add = QPushButton("＋ Add Equipment")
        self.btn_add.setMinimumHeight(35)
        self.btn_add.clicked.connect(self._add_blank_row)
        self.btn_defaults = QPushButton("Load Defaults")
        self.btn_defaults.setMinimumHeight(35)
        self.btn_defaults.clicked.connect(self._load_defaults)
        self.btn_clear = QPushButton("Clear All")
        self.btn_clear.setMinimumHeight(35)
        self.btn_clear.clicked.connect(self._clear_all)
        # self.btn_apply = QPushButton("Apply Days to All Rows")
        # self.btn_apply.setMinimumHeight(35)
        # self.btn_apply.clicked.connect(self._apply_default_days)
        btn_layout.addWidget(self.btn_add)
        btn_layout.addWidget(self.btn_defaults)
        btn_layout.addWidget(self.btn_clear)
        # btn_layout.addWidget(self.btn_apply)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        self._frozen = False

        # Report the initial (header-only) content height to the layout.
        self._refresh_table_height()

    # ── Height management ─────────────────────────────────────────────────

    def _refresh_table_height(self):
        """Row count changed: let the table re-report its content height so the
        layout re-fits it, then move the frozen action-column overlay to match."""
        self._table.updateGeometry()
        self.updateGeometry()
        if hasattr(self, "_frozen_col"):
            self._frozen_col.reposition()
            self._frozen_col.sync_row_heights()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not hasattr(self, "_frozen_col"):
            return
        vp_w = self._table.viewport().width()
        if vp_w <= 0:
            return
        # Cols 1-7 share the viewport minus the col-9 placeholder (_ACTION_W);
        # col 0 (Equipment Name) is QHeaderView.Stretch and absorbs whatever's
        # left automatically, so the row always fills exactly 100% of the
        # viewport - it's excluded here rather than folded into a ratio that
        # would have to sum to 1.0 (fragile under per-column int() rounding).
        # Col 9 is a fixed placeholder that reserves space for the frozen overlay.
        avail = max(1, vp_w - _ACTION_W)
        ratios = {1: 0.14, 2: 0.12, 3: 0.10, 4: 0.10, 5: 0.12, 6: 0.10, 7: 0.16}
        mins   = {1: 120,  2: 110,  3: 90,   4: 90,   5: 140,  6: 100,  7: 100}
        col_widths = {c: max(mins[c], int(avail * r)) for c, r in ratios.items()}
        used = sum(col_widths.values())
        if used > avail:
            # Scale down proportionally so columns never overflow
            scale = avail / used
            col_widths = {c: max(mins[c], int(w * scale)) for c, w in col_widths.items()}
        hh = self._table.horizontalHeader()
        hh.blockSignals(True)
        for col, width in col_widths.items():
            self._table.setColumnWidth(col, width)
        hh.blockSignals(False)
        self._frozen_col.reposition()
        self._frozen_col.sync_row_heights()

    def showEvent(self, event):
        super().showEvent(event)
        if hasattr(self, "_frozen_col"):
            self._frozen_col.reposition()

    # ── Row management ────────────────────────────────────────────────────

    # ── Cell helpers ──────────────────────────────────────────────────────

    def _cell_text(self, row, col, default="") -> str:
        item = self._table.item(row, col)
        return item.text().strip() if item else default

    def _cell_float(self, row, col, default=0.0) -> float:
        try:
            return float(self._cell_text(row, col, str(default)).replace(",", ""))
        except (ValueError, TypeError):
            return default

    def _cell_int(self, row, col, default=0) -> int:
        try:
            return int(float(self._cell_text(row, col, str(default)).replace(",", "")))
        except (ValueError, TypeError):
            return default

    def _make_item(self, text, align, editable=True) -> QTableWidgetItem:
        it = QTableWidgetItem(str(text))
        it.setTextAlignment(align)
        if not editable:
            it.setFlags(Qt.ItemIsEnabled)
        elif self._frozen:
            it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        return it

    # ── Row management ────────────────────────────────────────────────────

    # def _apply_default_days(self):
    #     days_val = str(self._default_days.value())
    #     self._table.blockSignals(True)
    #     for row in range(self._table.rowCount()):
    #         item = self._table.item(row, 4)
    #         if item:
    #             item.setText(days_val)
    #     self._table.blockSignals(False)
    #     self._recalculate()

    def _add_blank_row(self, d: dict | None = None):
        self._table.blockSignals(True)
        row_idx = self._table.rowCount()
        self._table.insertRow(row_idx)
        self._table.setRowHeight(row_idx, self._ROW_H)

        src  = d.get("source", ENERGY_SOURCES[0]) if d else ENERGY_SOURCES[0]
        _L   = Qt.AlignLeft  | Qt.AlignVCenter
        _R   = Qt.AlignRight | Qt.AlignVCenter

        self._table.setItem(row_idx, 0, self._make_item(d.get("name", "") if d else "", _L))
        self._table.setItem(row_idx, 1, self._make_item(src, _L))
        self._table.setItem(row_idx, 2, self._make_item(d.get("rate", 0.0) if d else 0.0, _R))
        self._table.setItem(row_idx, 3, self._make_item(d.get("hrs",  0.0) if d else 0.0, _R))
        self._table.setItem(row_idx, 4, self._make_item(d.get("days", 0)   if d else 0,   _R))
        self._table.setItem(row_idx, 5, self._make_item(d.get("ef", EF_DEFAULTS.get(src, 0.0)) if d else EF_DEFAULTS.get(src, 0.0), _R))
        self._table.setItem(row_idx, 6, self._make_item("", _R, editable=False))
        self._table.setItem(row_idx, 7, self._make_item("", _R, editable=False))

        action_item = QTableWidgetItem()
        action_item.setData(Qt.UserRole, row_idx)
        action_item.setFlags(Qt.ItemIsEnabled)
        self._table.setItem(row_idx, 8, action_item)
        self._table.setItem(row_idx, 9, QTableWidgetItem())

        self._table.blockSignals(False)
        self._frozen_col.add_row()
        self._refresh_table_height()
        self._recalculate()

    def _open_edit_dialog(self, row: int, _col: int = 0):
        if self._frozen:
            return
        if not (0 <= row < self._table.rowCount()):
            return
        row_data = {
            "name":   self._cell_text(row, 0),
            "source": self._cell_text(row, 1, ENERGY_SOURCES[0]),
            "rate":   self._cell_float(row, 2),
            "hrs":    self._cell_float(row, 3),
            "days":   self._cell_int(row, 4),
            "ef":     self._cell_float(row, 5),
        }
        dlg = _EditRowDialog(row_data, parent=self)
        if dlg.exec() != QDialog.Accepted:
            return
        v = dlg.get_values()
        self._table.blockSignals(True)
        for col, text in (
            (0, v["name"]),
            (1, v["source"]),
            (2, fmt(v["rate"])),
            (3, fmt(v["hrs"])),
            (4, str(v["days"])),
            (5, fmt(v["ef"])),
        ):
            item = self._table.item(row, col)
            if item:
                item.setText(text)
        self._table.blockSignals(False)
        if v != row_data:
            self._recalculate()

    def _delete_row(self, row_idx: int):
        if not (0 <= row_idx < self._table.rowCount()):
            return
        self._table.removeRow(row_idx)
        self._frozen_col.removeRow(row_idx)
        self._refresh_table_height()
        self._recalculate()

    def _load_defaults(self):
        if self._table.rowCount() > 0:
            reply = QMessageBox.question(
                self,
                "Load Defaults",
                "This will replace all current rows with the default equipment list.\nContinue?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return
        self._clear_all(confirm=False)
        for d in DEFAULT_MACHINERY_DATA:
            self._add_blank_row(d)

    def _clear_all(self, confirm=True):
        if confirm and self._table.rowCount() > 0:
            if not confirm_clear_all(self):
                return
        self._table.setRowCount(0)
        self._frozen_col.setRowCount(0)
        self._cached_total = 0.0
        self._refresh_table_height()
        self._recalculate()

    # ── Calculation ───────────────────────────────────────────────────────

    def _on_cell_changed(self, row, col):
        if col == 1:  # Energy Source changed - auto-update EF
            src = self._cell_text(row, 1, ENERGY_SOURCES[0])
            if src in EF_DEFAULTS:
                self._table.blockSignals(True)
                ef_item = self._table.item(row, 5)
                if ef_item:
                    ef_item.setText(str(EF_DEFAULTS[src]))
                self._table.blockSignals(False)
        self._recalculate()

    def _recalculate(self):
        diesel_total = elec_total = 0.0
        self._table.blockSignals(True)
        for row in range(self._table.rowCount()):
            rate = self._cell_float(row, 2)
            hrs  = self._cell_float(row, 3)
            days = self._cell_int(row, 4)
            ef   = self._cell_float(row, 5)
            src  = self._cell_text(row, 1, ENERGY_SOURCES[0])

            consumption = rate * hrs * days
            emissions   = consumption * ef
            unit = CONSUMPTION_UNIT.get(src, "units")

            c_item = self._table.item(row, 6)
            e_item = self._table.item(row, 7)
            if c_item:
                c_item.setText(f"{fmt_comma(consumption)} {unit}")
            if e_item:
                e_item.setText(fmt_comma(emissions))

            if src == "Diesel":
                diesel_total += emissions
            else:
                elec_total += emissions
        self._table.blockSignals(False)

        self._cached_total = diesel_total + elec_total
        self._lbl_diesel_sub.setText(f"Diesel: {fmt_comma(diesel_total)} kg CO₂e")
        self._lbl_elec_sub.setText(f"Electricity: {fmt_comma(elec_total)} kg CO₂e")
        self._lbl_detail_total.setText(f"Subtotal: {fmt_comma(self._cached_total)} kg CO₂e")
        self._on_change()

    def freeze(self, frozen: bool = True):
        self._frozen = frozen
        freeze_widgets(frozen, self.btn_add, self.btn_defaults, self.btn_clear)
        # freeze_widgets(frozen, ..., self.btn_apply)
        flags_editable = Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable
        flags_frozen   = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        for row in range(self._table.rowCount()):
            for col in range(6):  # cols 0-5 are user-editable
                item = self._table.item(row, col)
                if item:
                    item.setFlags(flags_frozen if frozen else flags_editable)
        self._action_delegate.set_frozen(frozen)

    def get_total(self) -> float:
        """Return last recalculated total - avoids redundant row traversal."""
        return self._cached_total

    # ── Data I/O ──────────────────────────────────────────────────────────

    def collect(self) -> dict:
        rows = []
        for row in range(self._table.rowCount()):
            rows.append({
                "name":   self._cell_text(row, 0),
                "source": self._cell_text(row, 1, ENERGY_SOURCES[0]),
                "rate":   self._cell_float(row, 2),
                "hrs":    self._cell_float(row, 3),
                "days":   self._cell_int(row, 4),
                "ef":     self._cell_float(row, 5),
            })
        return {"rows": rows}

    def load(self, data: dict):
        self._clear_all(confirm=False)
        for d in data.get("rows", []):
            self._add_blank_row(d)


# ── Main page ─────────────────────────────────────────────────────────────────


class MachineryEmissions(ScrollableForm):
    def __init__(self, controller=None):
        super().__init__(controller=controller, chunk_name=CHUNK)
        self._loading = False
        self._build_ui()
        self._loading = True
        self._detailed_table._load_defaults()
        self._loading = False
        self._on_totals_changed()
        if self.controller and hasattr(self.controller, "chunk_updated"):
            self.controller.chunk_updated.connect(self._on_chunk_updated)

    def _get_currency(self) -> str:
        if self.controller and self.controller.engine:
            info = self.controller.engine.fetch_chunk("general_info") or {}
            return str(info.get("currency", ""))
        return ""

    def _build_ui(self):
        f = self.form
        bold = QFont()
        bold.setBold(True)
        bold.setPointSize(11)

        # ── Grand total banner (top) ───────────────────────────────────────
        banner = QGroupBox()
        banner_layout = QHBoxLayout(banner)
        banner_layout.setContentsMargins(12, 8, 12, 8)
        self._lbl_grand_total = QLabel("Total Machinery/Equipment Emissions: - kg CO₂e")
        self._lbl_grand_total.setFont(bold)
        # note = QLabel(
        #     "  ⓘ  Fill either Detailed Equipment List or Lump Sum - not both."
        # )
        # note.setStyleSheet("color: gray; font-style: italic;")
        banner_layout.addWidget(self._lbl_grand_total)
        # banner_layout.addWidget(note)
        banner_layout.addStretch()
        f.addRow(banner)

        # ── Toggle ────────────────────────────────────────────────────────
        toggle_widget = QWidget()
        toggle_layout = QHBoxLayout(toggle_widget)
        toggle_layout.setContentsMargins(0, 4, 0, 4)
        self._radio_detailed = QRadioButton("Detailed Equipment List")
        self._radio_lumpsum = QRadioButton("Lump Sum")
        self._radio_detailed.setChecked(True)
        self._toggle_group = QButtonGroup(self)
        self._toggle_group.addButton(self._radio_detailed, 0)
        self._toggle_group.addButton(self._radio_lumpsum, 1)
        self._toggle_group.idToggled.connect(self._on_mode_toggled)
        toggle_layout.addWidget(QLabel("Input Method:"))
        toggle_layout.addSpacing(8)
        toggle_layout.addWidget(self._radio_detailed)
        toggle_layout.addSpacing(16)
        toggle_layout.addWidget(self._radio_lumpsum)
        toggle_layout.addStretch()
        f.addRow(toggle_widget)

        # ── Stack ─────────────────────────────────────────────────────────
        self._stack = QStackedWidget()
        self._stack.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        # Index 0 - Detailed table
        detailed_widget = QWidget()
        detailed_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        detailed_vbox = QVBoxLayout(detailed_widget)
        detailed_vbox.setContentsMargins(0, 0, 0, 0)
        detailed_vbox.setSpacing(4)

        self._detailed_table = _DetailedTable(
            on_change=self._on_totals_changed,
        )
        detailed_vbox.addWidget(self._detailed_table)
        self._stack.addWidget(detailed_widget)

        # Index 1 - Lump Sum via build_form temp-swap
        lumpsum_widget = QWidget()
        lumpsum_layout = QFormLayout(lumpsum_widget)
        lumpsum_layout.setContentsMargins(0, 0, 0, 0)
        lumpsum_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        lumpsum_layout.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        lumpsum_layout.setFormAlignment(Qt.AlignTop | Qt.AlignLeft)
        lumpsum_layout.setVerticalSpacing(8)

        _saved = self.form
        self.form = lumpsum_layout
        build_form(self, LUMPSUM_ELEC_FIELDS)
        build_form(self, LUMPSUM_FUEL_FIELDS)
        self.form = _saved

        # Pop from _field_map - we save manually via collect_data
        # Wire valueChanged -> _on_totals_changed for live total update
        for key, default in _LUMPSUM_KEYS:
            self._field_map.pop(key, None)
            w = getattr(self, key, None)
            if w is not None:
                w.valueChanged.connect(self._on_totals_changed)

        # Set default EF values

        # Lump sum subtotal
        ls_total_row = QWidget()
        ls_total_layout = QHBoxLayout(ls_total_row)
        ls_total_layout.setContentsMargins(0, 8, 0, 4)
        self._lbl_lumpsum_total = QLabel(f"Lump Sum Subtotal: {fmt(0.0)} kg CO₂e")
        bold2 = QFont()
        bold2.setBold(True)
        self._lbl_lumpsum_total.setFont(bold2)
        ls_total_layout.addStretch()
        ls_total_layout.addWidget(self._lbl_lumpsum_total)
        lumpsum_layout.addRow(ls_total_row)

        self._stack.addWidget(lumpsum_widget)
        f.addRow(self._stack)
        self._shrink_stack_to_current()

        # ── Grand total (bottom) ───────────────────────────────────────────
        bottom_banner = QGroupBox()
        bottom_layout = QHBoxLayout(bottom_banner)
        bottom_layout.setContentsMargins(12, 8, 12, 8)
        self._lbl_grand_total_bottom = QLabel("Total Machinery/Equipment Emissions: - kg CO₂e")
        self._lbl_grand_total_bottom.setFont(bold)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self._lbl_grand_total_bottom)
        f.addRow(bottom_banner)

        # ── Remarks ───────────────────────────────────────────────────────
        self._remarks = RemarksEditor(
            title="Notes",
            on_change=self._on_field_changed,
        )
        f.addRow(self._remarks)

    # ── Helpers ───────────────────────────────────────────────────────────

    def _lumpsum_elec_total(self) -> float:
        c = getattr(self, "elec_consumption_per_day", None)
        d = getattr(self, "elec_days", None)
        e = getattr(self, "elec_ef", None)
        return c.value() * d.value() * e.value() if c and d and e else 0.0

    def _lumpsum_fuel_total(self) -> float:
        c = getattr(self, "fuel_consumption_per_day", None)
        d = getattr(self, "fuel_days", None)
        e = getattr(self, "fuel_ef", None)
        return c.value() * d.value() * e.value() if c and d and e else 0.0

    def _current_mode(self) -> str:
        return "detailed" if self._radio_detailed.isChecked() else "lumpsum"

    # ── Slots ─────────────────────────────────────────────────────────────

    def _shrink_stack_to_current(self):
        idx = self._stack.currentIndex()
        for i in range(self._stack.count()):
            w = self._stack.widget(i)
            if i == idx:
                w.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
                w.adjustSize()
            else:
                w.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)

        # Cap the stack to the sizeHint of the current panel in BOTH modes.
        # The detailed panel's sizeHint is now reliable because _refresh_table_height
        # pins the inner QTableWidget's min/max on every row change.
        hint = self._stack.currentWidget().sizeHint().height()
        self._stack.setMaximumHeight(max(hint, 0))

        self._stack.adjustSize()
        self._stack.updateGeometry()

    def _on_mode_toggled(self, btn_id: int, checked: bool):
        if checked:
            self._stack.setCurrentIndex(btn_id)
            self._shrink_stack_to_current()
            self._on_totals_changed()

    def _on_totals_changed(self):
        if self._loading:
            return
        # Guard: may fire during build_form before all labels are created
        if not hasattr(self, "_lbl_grand_total_bottom"):
            return
        mode = self._current_mode()
        if mode == "detailed":
            total = self._detailed_table.get_total()
            # Only re-fit the stack when row count changes; skipping it on plain
            # value edits prevents a spurious resizeEvent → column-width recalc.
            new_count = self._detailed_table._table.rowCount()
            if new_count != getattr(self, "_last_row_count", -1):
                self._last_row_count = new_count
                self._shrink_stack_to_current()
        else:
            total = self._lumpsum_elec_total() + self._lumpsum_fuel_total()
            self._lbl_lumpsum_total.setText(f"Lump Sum Subtotal: {fmt_comma(total)} kg CO₂e")

        text = f"Total Machinery/Equipment Emissions: {fmt_comma(total)} kg CO₂e"
        self._lbl_grand_total.setText(text)
        self._lbl_grand_total_bottom.setText(text)
        self._on_field_changed()

    # ── Currency ──────────────────────────────────────────────────────────

    def _apply_currency(self):
        currency = self._get_currency()
        note = f" (Currency: {currency})" if currency else ""
        self._lbl_grand_total.setToolTip(f"Total CO₂e emissions from machinery{note}")
        self._lbl_grand_total_bottom.setToolTip(
            f"Total CO₂e emissions from machinery{note}"
        )

    def _on_chunk_updated(self, chunk_name: str):
        if chunk_name == "general_info":
            self._apply_currency()

    # ── Data I/O ──────────────────────────────────────────────────────────

    def collect_data(self) -> dict:
        lumpsum = {}
        for key, default in _LUMPSUM_KEYS:
            w = getattr(self, key, None)
            if w is not None:
                lumpsum[key] = (
                    int(w.value()) if isinstance(w, QSpinBox) else float(w.value())
                )
            else:
                lumpsum[key] = default


        return {
            "mode": self._current_mode(),
            "default_days": (
                int(self.default_days.value()) if hasattr(self, "default_days") else 0
            ),
            "detailed": self._detailed_table.collect(),
            "lumpsum": lumpsum,
            "remarks": self._remarks.to_html() if hasattr(self, "_remarks") else "",
            "total_kgCO2e": round(
                (
                    self._detailed_table.get_total()
                    if self._current_mode() == "detailed"
                    else self._lumpsum_elec_total() + self._lumpsum_fuel_total()
                ),
                DECIMAL_PLACES,
            ),
        }

    def load_data(self, data: dict):
        if not data:
            return
        self._loading = True
        try:
            mode = data.get("mode", "detailed")
            self._radio_lumpsum.setChecked(mode == "lumpsum")
            self._radio_detailed.setChecked(mode != "lumpsum")
            self._stack.setCurrentIndex(1 if mode == "lumpsum" else 0)

            self._detailed_table.load(data.get("detailed", {}))

            if hasattr(self, "default_days"):
                self.default_days.blockSignals(True)
                self.default_days.setValue(int(data.get("default_days", 0)))
                self.default_days.blockSignals(False)

            ls = data.get("lumpsum", {})
            for key, default in _LUMPSUM_KEYS:
                w = getattr(self, key, None)
                if w is not None:
                    w.blockSignals(True)
                    val = ls.get(key, default)
                    w.setValue(int(val) if isinstance(w, QSpinBox) else float(val))
                    w.blockSignals(False)

            self._remarks.from_html(data.get("remarks", ""))
        finally:
            self._loading = False
        # Shrink/expand stack AFTER all rows are loaded so sizeHint is correct
        self._shrink_stack_to_current()
        self._on_totals_changed()

    # ── Base overrides ────────────────────────────────────────────────────

    def showEvent(self, event):
        super().showEvent(event)
        # _shrink_stack_to_current() was last run in _build_ui(), before this
        # widget was ever shown/polished - the detailed table's sizeHint() can
        # be wrong at that point (e.g. an unpolished header height), capping
        # the stack too short and cramping the banners/margins around it until
        # something else (like a row-count change) reruns it. Rerun once here
        # too so the layout is correct from the very first paint, not only
        # after the user first interacts with the table.
        self._shrink_stack_to_current()

    def _on_field_changed(self):
        if self._loading:
            return
        if self.controller and self.controller.engine and self.chunk_name:
            self.controller.engine.stage_update(
                chunk_name=self.chunk_name, data=self.collect_data()
            )
        self.data_changed.emit()

    def get_data_dict(self) -> dict:
        return self.collect_data()

    def load_data_dict(self, data: dict):
        self.load_data(data)

    def refresh_from_engine(self):
        if not self.controller or not self.controller.engine:
            return
        if not self.controller.engine.is_active() or not self.chunk_name:
            return
        data = self.controller.get_chunk(self.chunk_name)
        if not data or data == self._loaded_data:
            return
        self._loaded_data = data
        self.load_data(data)
        self._apply_currency()

    def on_refresh(self):
        if not self.controller or not getattr(self.controller, "engine", None):
            return
        data = self.controller.get_chunk(CHUNK) or {}
        self.load_data(data)
        self._apply_currency()

    def validate(self) -> dict:
        data = self.collect_data()
        warnings = []
        total = data.get("total_kgCO2e", 0.0)
        if total == 0.0:
            mode = data.get("mode", "")
            if mode == "detailed":
                warnings.append(
                    "Total machinery/equipment emissions is 0 kgCO₂e - "
                    "no equipment rows have been added, or fuel consumption and operating hours are zero for all entries; add equipment details or check existing entries"
                )
            else:
                warnings.append(
                    "Total machinery/equipment emissions is 0 kgCO₂e - "
                    "both lumpsum fuel consumption and electricity consumption are zero; enter at least one positive value to calculate machinery emissions"
                )
        return {"errors": [], "warnings": warnings}

    def freeze(self, frozen: bool = True):
        self._radio_detailed.setEnabled(not frozen)
        self._radio_lumpsum.setEnabled(not frozen)
        self._detailed_table.freeze(frozen)
        for key, _ in _LUMPSUM_KEYS:
            w = getattr(self, key, None)
            if w is not None:
                w.setEnabled(not frozen)
        if hasattr(self, "default_days"):
            self.default_days.setEnabled(not frozen)
        self._remarks.freeze(frozen)

    def get_data(self) -> dict:
        return {"chunk": CHUNK, "data": self.get_data_dict()}


