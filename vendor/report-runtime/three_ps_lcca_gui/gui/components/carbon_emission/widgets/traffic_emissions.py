from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QBrush, QColor
from three_ps_lcca_gui.gui.themes import get_token, theme_manager

from ...base_widget import ScrollableForm
from ...utils.form_builder.form_definitions import FieldDef
from ...utils.form_builder.form_builder import build_form
from ...utils.remarks_editor import RemarksEditor
from ...utils.display_format import fmt
from ...utils.table_widgets import TableDoubleSpinBox, TABLE_SPINBOX_BASE_QSS, mark_editable_column, TooltipTableMixin

from ...utils.validation_helpers import confirm_clear_all
from PySide6.QtWidgets import QStyledItemDelegate

# ── Constants ─────────────────────────────────────────────────────────────────

DECIMAL_PLACES_CUSTOM = 3
CHUNK = "diversion_emissions"
GEN_CHUNK = "general_info"
TRAFFIC_CHUNK = "traffic_and_road_data"

_VEHICLES = [
    ("small_cars", "Small Car"),
    ("big_cars", "Big Car"),
    ("two_wheelers", "Two Wheeler"),
    ("o_buses", "Ordinary Buses"),
    ("d_buses", "Deluxe Buses"),
    ("lcv", "LCV"),
    ("hcv", "HCV"),
    ("mcv", "MCV"),
]

DEFAULT_FACTORS: dict[str, float] = {
    "small_cars": 0.1030,
    "big_cars": 0.2690,
    "two_wheelers": 0.0351,
    "o_buses": 0.4548,
    "d_buses": 0.6064,
    "lcv": 0.3070,
    "hcv": 0.5928,
    "mcv": 0.7375,
}

_MODES = ["Calculate by Vehicle", "Enter Directly"]

DIRECT_FIELDS = [
    FieldDef(
        "total_direct_emissions",
        "Total Diversion Emissions",
        "Enter the total carbon emissions from traffic diversion per day of construction.",
        "float",
        (0.0, 1e12, DECIMAL_PLACES_CUSTOM),
        unit="(kgCO₂e/day)",
    ),
    FieldDef(
        "source",
        "Source",
        "Reference or basis used to determine the diversion emissions value (e.g. emissions study, project report, government guideline, or agency publication).",
        "text",
    ),
    FieldDef(
        "comments",
        "Comments",
        "Any additional notes, assumptions, calculations, or justification supporting the selected diversion emissions value.",
        "textarea",
    ),
]

# ── Emissions Table ───────────────────────────────────────────────────────────

_COL_VEHICLE = 0
_COL_VEH_DAY = 1
_COL_FACTOR = 2
_COL_EMISSIONS = 3

_ROW_ZERO_ROLE = Qt.UserRole + 1

class _EmissionsRowDelegate(QStyledItemDelegate):
    """Paints a full-cell background if the item has the zero-row role set."""
    def paint(self, painter, option, index):
        is_zero = index.data(_ROW_ZERO_ROLE)
        if is_zero:
            painter.save()
            bg = QColor(get_token("cell-warn-bg"))
            if bg.isValid():
                painter.fillRect(option.rect, bg)
            painter.restore()
        super().paint(painter, option, index)

class _EmissionsTable(TooltipTableMixin, QTableWidget):
    def __init__(self, on_change, on_total_changed=None, parent=None):
        super().__init__(len(_VEHICLES), 4, parent)
        self._on_change = on_change
        self._on_total_changed = on_total_changed
        self._reroute_km: float = 0.0
        self._factors: dict[str, TableDoubleSpinBox] = {}
        self._vpd_items: dict[str, QTableWidgetItem] = {}
        self._emission_items: dict[str, QTableWidgetItem] = {}

        self._zero_state: dict[str, bool] = {}
        self.setItemDelegate(_EmissionsRowDelegate(self))
        theme_manager().theme_changed.connect(self._refresh_theme)

        _L = Qt.AlignLeft  | Qt.AlignVCenter
        _R = Qt.AlignRight | Qt.AlignVCenter
        for col, (label, align) in enumerate([
            ("Vehicle Type",                         _L),
            ("Vehicles / Day",                       _R),
            ("Emission Factor\n(kgCO₂e/veh-km/day)", _R),
            ("Emissions\n(kgCO₂e/day)",              _R),
        ]):
            item = QTableWidgetItem(label)
            item.setTextAlignment(align)
            self.setHorizontalHeaderItem(col, item)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(36)
        self.setEditTriggers(QTableWidget.NoEditTriggers)
        self.setSelectionMode(QTableWidget.NoSelection)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        mark_editable_column(self, _COL_FACTOR)

        for row, (key, label) in enumerate(_VEHICLES):
            lbl_item = QTableWidgetItem(label)
            lbl_item.setFlags(Qt.ItemIsEnabled)
            self.setItem(row, _COL_VEHICLE, lbl_item)

            vpd_item = QTableWidgetItem("0")
            vpd_item.setFlags(Qt.ItemIsEnabled)
            vpd_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.setItem(row, _COL_VEH_DAY, vpd_item)
            self._vpd_items[key] = vpd_item

            sb = TableDoubleSpinBox()
            sb.setRange(0.0, 9_999.0)
            sb.setDecimals(DECIMAL_PLACES_CUSTOM)
            sb.setButtonSymbols(TableDoubleSpinBox.NoButtons)
            sb.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            sb.valueChanged.connect(self._on_factor_changed)
            self.setCellWidget(row, _COL_FACTOR, sb)
            self._factors[key] = sb

            em_item = QTableWidgetItem(fmt(0.0))
            em_item.setFlags(Qt.ItemIsEnabled)
            em_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.setItem(row, _COL_EMISSIONS, em_item)
            self._emission_items[key] = em_item

    def _refresh_theme(self):
        """Re-apply zero-state colors with fresh tokens, repaint cell widgets."""
        for row, (key, _) in enumerate(_VEHICLES):
            self._set_row_zero_state(row, key, self._zero_state.get(key, False))
        for sb in self._factors.values():
            sb.style().unpolish(sb)
            sb.style().polish(sb)
            sb.update()
        self.viewport().update()

    def sizeHint(self):
        header_h = self.horizontalHeader().height() or 36
        rows_h = self.rowCount() * self.verticalHeader().defaultSectionSize()
        return QSize(super().sizeHint().width(), max(60, header_h + rows_h + 10))

    def minimumSizeHint(self):
        return self.sizeHint()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        w = self.viewport().width()
        self.setColumnWidth(_COL_VEHICLE, int(w * 0.28))
        self.setColumnWidth(_COL_VEH_DAY, int(w * 0.18))
        self.setColumnWidth(_COL_FACTOR, int(w * 0.27))
        self.setColumnWidth(_COL_EMISSIONS, int(w * 0.27))

    def _on_factor_changed(self):
        self._recalculate()
        if self._on_total_changed:
            self._on_total_changed()
        self._on_change()

    def set_reroute_distance(self, km: float):
        self._reroute_km = km
        self._recalculate()
        if self._on_total_changed:
            self._on_total_changed()

    def load_vehicles_from_traffic(self, vehicle_data: dict):
        for row, (key, _) in enumerate(_VEHICLES):
            vpd = int((vehicle_data.get(key) or {}).get("vehicles_per_day", 0))
            self._vpd_items[key].setText(str(vpd))
            self._set_row_zero_state(row, key, vpd == 0)
        self._recalculate()
        if self._on_total_changed:
            self._on_total_changed()

    def load_defaults(self):
        for key, sb in self._factors.items():
            sb.blockSignals(True)
            sb.setValue(DEFAULT_FACTORS.get(key, 0.0))
            sb.blockSignals(False)
        self._recalculate()
        self._on_change()

    def collect_factors(self) -> dict:
        return {key: sb.value() for key, sb in self._factors.items()}

    def load_factors(self, data: dict):
        for key, sb in self._factors.items():
            sb.blockSignals(True)
            sb.setValue(float(data.get(key, 0.0)))
            sb.blockSignals(False)
        self._recalculate()

    def total_emissions(self) -> float:
        total = 0.0
        for key, _ in _VEHICLES:
            vpd = int(self._vpd_items[key].text() or "0")
            factor = self._factors[key].value()
            total += vpd * factor * self._reroute_km
        return total

    def _recalculate(self):
        for key, _ in _VEHICLES:
            vpd = int(self._vpd_items[key].text() or "0")
            factor = self._factors[key].value()
            em = vpd * factor * self._reroute_km
            self._emission_items[key].setText(fmt(em))

    def freeze(self, frozen: bool = True):
        for sb in self._factors.values():
            sb.setEnabled(not frozen)

    def _set_row_zero_state(self, row: int, key: str, is_zero: bool):
        self._zero_state[key] = is_zero

        item = self._vpd_items[key]
        item.setData(_ROW_ZERO_ROLE, is_zero)
        item.setForeground(
            QBrush(QColor(get_token("warning"))) if is_zero else QBrush()
        )

        # Ensure other cells in row don't have warning background if they share role
        # but in this case _vpd_items[key] is a specific QTableWidgetItem.
        # So we are already targeting just one cell.


# ── Main Widget ───────────────────────────────────────────────────────────────


class TrafficEmissions(ScrollableForm):
    def __init__(self, controller=None):
        super().__init__(controller=controller, chunk_name=CHUNK)
        self._suppress_mode_signal = False
        self._build_ui()

        # Re-run mode check whenever bridge_data or traffic_data changes
        if self.controller and hasattr(self.controller, "chunk_updated"):
            self.controller.chunk_updated.connect(self._on_chunk_updated)
        
        theme_manager().theme_changed.connect(self._refresh_theme)

    def _refresh_theme(self):
        self._warning_label.setStyleSheet(f"color: {get_token('danger')};")
        self.update()

    def _on_chunk_updated(self, chunk_name: str):
        if chunk_name in ("bridge_data", "traffic_and_road_data"):
            self._load_traffic_context()

    def showEvent(self, event):
        super().showEvent(event)
        self._load_traffic_context()

    # ── UI Construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        main_form = self.form

        # Build mode combo via form_builder (gives us setattr + field wrapper),
        # then immediately pop it from _field_map so the base _on_field_changed
        # never fires for it and never writes a partial dict to the chunk.
        build_form(
            self,
            [FieldDef("mode", "Calculation Mode", "", "combo", options=_MODES, combo_placeholder="")],
        )
        self._field_map.pop("mode", None)  # ← prevent base save loop from firing

        self.mode.setFixedWidth(220)
        self.mode.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        if self.mode.parentWidget():
            self.mode.parentWidget().setSizePolicy(
                QSizePolicy.Expanding, QSizePolicy.Fixed
            )
        self.mode.currentIndexChanged.connect(self._on_mode_changed)
        self.mode.setEnabled(False)  # driven by traffic data, not user

        # Warning label
        self._warning_label = QLabel()
        self._warning_label.setStyleSheet(f"color: {get_token('danger')};")
        self._warning_label.setVisible(False)
        self._warning_label.setWordWrap(True)
        main_form.addRow(self._warning_label)

        # Stack
        self._stack = QStackedWidget()
        # self._stack.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)

        # ── Panel 0: Calculate by Vehicle ─────────────────────────────────────
        calc_widget = QWidget()
        calc_layout = QFormLayout(calc_widget)
        calc_layout.setContentsMargins(0, 0, 0, 0)
        calc_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        calc_layout.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        calc_layout.setFormAlignment(Qt.AlignTop | Qt.AlignLeft)
        calc_layout.setVerticalSpacing(8)

        self._reroute_label = QLabel("-")
        calc_layout.addRow("Reroute Distance (from Traffic Data):", self._reroute_label)
        calc_layout.addRow(QLabel("<b>Vehicle Emission Factors</b>"))

        self._emissions_table = _EmissionsTable(
            on_change=self._on_field_changed,
            on_total_changed=self._refresh_total,
        )

        table_container = QWidget()
        table_layout = QHBoxLayout(table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.addWidget(self._emissions_table)

        calc_layout.addRow(table_container)

        self._total_label = QLabel("0.0000")
        calc_layout.addRow("<b>Total Daily Emissions (kgCO₂e/day):</b>", self._total_label)

        self.btn_defaults = QPushButton("Load Default Factors")
        self.btn_defaults.setFixedWidth(160)
        self.btn_defaults.setMinimumHeight(30)
        self.btn_defaults.clicked.connect(self._on_load_defaults)
        self.btn_defaults.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        calc_layout.addRow(self.btn_defaults)

        self._stack.addWidget(calc_widget)  # index 0

        # ── Panel 1: Enter Directly ───────────────────────────────────────────
        direct_widget = QWidget()
        direct_layout = QFormLayout(direct_widget)
        direct_layout.setContentsMargins(0, 0, 0, 0)
        direct_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        direct_layout.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        direct_layout.setFormAlignment(Qt.AlignTop | Qt.AlignLeft)
        direct_layout.setVerticalSpacing(8)

        _temp = self.form
        self.form = direct_layout
        build_form(self, DIRECT_FIELDS)
        for _k in ("total_direct_emissions", "source", "comments"):
            self._field_map.pop(_k, None)  # handled in collect_data
        self.form = _temp

        self._stack.addWidget(direct_widget)  # index 1
        main_form.addRow(self._stack)
        self._shrink_stack_to_current()

        # Remarks
        self._remarks = RemarksEditor(
            title="Notes", on_change=self._on_field_changed
        )
        main_form.addRow(self._remarks)

        # Clear All
        self.btn_clear = QPushButton("Clear All")
        btn_clear = self.btn_clear
        btn_clear.setMinimumHeight(35)
        btn_clear.clicked.connect(self.clear_all)

        btn_row = QHBoxLayout()
        btn_row.addWidget(btn_clear)
        btn_widget = QWidget()
        btn_widget.setLayout(btn_row)
        btn_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        main_form.addRow(btn_widget)

    # ── Slot Handlers ─────────────────────────────────────────────────────────

    def _on_field_changed(self):
        """Override base - saves full collect_data() dict, not just _field_map."""
        if self._loading:
            return
        if self.controller and self.controller.engine and self.chunk_name:
            self.controller.engine.stage_update(
                chunk_name=self.chunk_name, data=self.collect_data()
            )
        self.data_changed.emit()

    def _shrink_stack_to_current(self):
        self._stack.setCurrentIndex(self.mode.currentIndex())

    def _on_mode_changed(self, idx: int):
        if self._suppress_mode_signal:
            return
        self._stack.setCurrentIndex(idx)
        self._shrink_stack_to_current()
        self._on_field_changed()

    def _on_load_defaults(self):
        self._emissions_table.load_defaults()
        self._refresh_total()

    def _refresh_total(self):
        self._total_label.setText(fmt(self._emissions_table.total_emissions()))




    def _load_traffic_context(self):
        if not (self.controller and self.controller.engine):
            return

        # ── Load data ─────────────────────────────────────────────────────
        traffic = self.controller.engine.fetch_chunk(TRAFFIC_CHUNK) or {}

        # ── Extract + normalize values ─────────────────────────────────────
        raw_mode = traffic.get("mode")
        traffic_mode = str(raw_mode or "").strip().upper()
        
        # Fallback if traffic_mode is empty: check bridge_data for India
        if not traffic_mode:
            print("going for bridge data")
            bridge = self.controller.engine.fetch_chunk("bridge_data") or {}
            project_country = str(bridge.get("project_country") or "").strip().upper()
            if project_country == "INDIA":
                traffic_mode = "INDIA"
        
        print(f"checking mode : mode is {traffic_mode}")
        reroute = float(traffic.get("additional_reroute_distance_km", 0.0))

        can_calculate = traffic_mode == "INDIA"

        # ── Mode Handling ──────────────────────────────────────────────────
        self._suppress_mode_signal = True

        if can_calculate:
            idx = self.mode.findText("Calculate by Vehicle")
        else:
            idx = self.mode.findText("Enter Directly")

        if idx >= 0:
            self.mode.setCurrentIndex(idx)
            self._stack.setCurrentIndex(idx)

        self._suppress_mode_signal = False

        # Always locked - mode is determined automatically
        self.mode.setEnabled(False)

        # ── Load reroute + vehicle data ────────────────────────────────────
        self._emissions_table.set_reroute_distance(reroute)
        self._reroute_label.setText(f"{fmt(reroute)} km")
        self._emissions_table.load_vehicles_from_traffic(
            traffic.get("vehicle_data", {})
        )

        # ── Warning Logic ───────────────────────────────────────────────────
        show_warning = (
            can_calculate
            and self.mode.currentText() == "Calculate by Vehicle"
            and reroute == 0.0
        )

        if show_warning:
            self._warning_label.setText(
                "⚠ Reroute distance is 0 km. Please fill in the Traffic Data tab first."
            )
            self._warning_label.setVisible(True)
        else:
            self._warning_label.setVisible(False)

        # ── Final refresh ───────────────────────────────────────────────────
        self._refresh_total()
        self._shrink_stack_to_current()





    # ── Data Collection ───────────────────────────────────────────────────────

    def collect_data(self) -> dict:
        return {
            "mode": self.mode.currentText(),
            "emission_factors": self._emissions_table.collect_factors(),
            "total_calculated_emissions": self._emissions_table.total_emissions(),
            "direct_entry": {
                "total_direct_emissions": (
                    self.total_direct_emissions.value()
                    if hasattr(self, "total_direct_emissions")
                    else 0.0
                ),
                "source": self.source.text().strip() if hasattr(self, "source") else "",
                "comments": self.comments.toPlainText().strip() if hasattr(self, "comments") else "",
            },
            "remarks": self._remarks.to_html(),
        }

    # ── Base Overrides ────────────────────────────────────────────────────────

    def get_data_dict(self) -> dict:
        return self.collect_data()

    def load_data_dict(self, data: dict):
        self._load_own_data(data)
        self._load_traffic_context()

    def refresh_from_engine(self):
        if not self.controller or not self.controller.engine:
            return
        if not self.controller.engine.is_active() or not self.chunk_name:
            return
        data = self.controller.get_chunk(self.chunk_name)
        if not data or data == self._loaded_data:
            self._load_traffic_context()
            return
        self._loaded_data = data
        self._load_own_data(data)
        self._load_traffic_context()

    # ── Data Loading ──────────────────────────────────────────────────────────

    def _load_own_data(self, data: dict):
        if not data:
            return
        self._suppress_mode_signal = True
        try:
            self.mode.blockSignals(True)
            idx = self.mode.findText(data.get("mode", _MODES[0]))
            self.mode.setCurrentIndex(idx if idx >= 0 else 0)
            self.mode.blockSignals(False)
            self._stack.setCurrentIndex(self.mode.currentIndex())

            self._emissions_table.load_factors(data.get("emission_factors", {}))

            direct = data.get("direct_entry", {})

            if hasattr(self, "total_direct_emissions"):
                self.total_direct_emissions.blockSignals(True)
                self.total_direct_emissions.setValue(
                    float(direct.get("total_direct_emissions", 0.0))
                )
                self.total_direct_emissions.blockSignals(False)

            if hasattr(self, "source"):
                self.source.blockSignals(True)
                self.source.setText(direct.get("source", ""))
                self.source.blockSignals(False)

            if hasattr(self, "comments"):
                self.comments.blockSignals(True)
                self.comments.setPlainText(direct.get("comments", ""))
                self.comments.blockSignals(False)

            self._remarks.from_html(data.get("remarks", ""))
        finally:
            self._suppress_mode_signal = False

    def validate(self) -> dict:
        data = self.collect_data()
        warnings = []
        mode = data.get("mode", "")
        if mode == "Calculate by Vehicle":
            if data.get("total_calculated_emissions", 0.0) == 0.0:
                warnings.append(
                    "Total traffic diversion emissions is 0 kgCO₂e/day - "
                    "the reroute distance or vehicle counts may be zero; check the detour distance and vehicle data in the Traffic Data section"
                )
        else:
            if data.get("direct_entry", {}).get("total_direct_emissions", 0.0) == 0.0:
                warnings.append(
                    "Total direct diversion emissions is 0 kgCO₂e/day - "
                    "enter the estimated per-day carbon emission for traffic rerouting in the field above"
                )
        return {"errors": [], "warnings": warnings}

    def freeze(self, frozen: bool = True):
        self.btn_defaults.setEnabled(not frozen)
        self.btn_clear.setEnabled(not frozen)
        self._emissions_table.freeze(frozen)
        if hasattr(self, "total_direct_emissions"):
            self.total_direct_emissions.setEnabled(not frozen)
        self._remarks.freeze(frozen)

    def get_data(self) -> dict:
        return {"chunk": CHUNK, "data": self.collect_data()}

    # ── Clear All ─────────────────────────────────────────────────────────────

    def clear_all(self):
        if not confirm_clear_all(self):
            return

        self._emissions_table.load_factors({})
        if hasattr(self, "total_direct_emissions"):
            self.total_direct_emissions.blockSignals(True)
            self.total_direct_emissions.setValue(0.0)
            self.total_direct_emissions.blockSignals(False)
        self._remarks.clear_content()
        self._refresh_total()
        self._on_field_changed()


