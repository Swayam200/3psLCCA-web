"""
gui/components/traffic_data/main.py
"""

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)
from PySide6.QtCore import Qt, QSize, QTimer
from three_ps_lcca_gui.gui.themes import get_token, theme_manager
from ..utils.common_requested_data import get_currency

from ..base_widget import ScrollableForm
from ..utils.form_builder.form_definitions import FieldDef, Section, ValidationStatus
from ..utils.form_builder.form_builder import build_form
from ..utils.validation_helpers import clear_field_styles, freeze_form, freeze_widgets, validate_form, confirm_clear_all
from ..utils.remarks_editor import RemarksEditor
from ..utils.wpi_manager import WPIManager, WPIProfile
from .wpi_table import _WPITable
from .wpi_selector import _WPISelector
from ..utils.table_widgets import TableDoubleSpinBox, TableSpinBox, TABLE_SPINBOX_BASE_QSS, mark_editable_column, TooltipTableMixin
from three_ps_lcca_gui.gui.themes import get_token

# ── Dev mode ──────────────────────────────────────────────────────────────────

DEV = False

# ── WPI DB path ───────────────────────────────────────────────────────────────

_WPI_DB_PATH = Path(__file__).parent.parent.parent.parent / "data" / "wpi_db.json"

# ── Lane types ────────────────────────────────────────────────────────────────

LANE_TYPES = [
    {
        "code": "SL",
        "name": "Single Lane",
        "width": 3.75,
        "capacity": 435,
        "velocity_class": "SL",
    },
    {
        "code": "IL",
        "name": "Intermediate Lane",
        "width": 5.5,
        "capacity": 1158,
        "velocity_class": "IL",
    },
    {
        "code": "2L",
        "name": "Two Lane",
        # "name": "Two Lane (Two Way)",
        "width": 7.0,
        "capacity": 1200,
        "velocity_class": "2L",
    },
    # {
    #     "code": "2L_1W",
    #     "name": "Two Lane (One Way)",
    #     "width": 7.0,
    #     "capacity": 2700,
    #     "velocity_class": "4L",
    # },
    # {
    #     "code": "3L_1W",
    #     "name": "Three Lane (One Way)",
    #     "width": 10.5,
    #     "capacity": 4200,
    #     "velocity_class": "6L",
    # },
    {
        "code": "4L",
        "name": "Four Lane",
        # "name": "Four Lane (Two Way)",
        "width": 14.0,
        "capacity": 2900,
        "velocity_class": "4L",
    },
    {
        "code": "6L",
        "name": "Six Lane",
        # "name": "Six Lane (Two Way)",
        "width": 21.00,
        "capacity": 4300,
        "velocity_class": "6L",
    },
    {
        "code": "8L",
        "name": "Eight Lane",
        # "name": "Eight Lane (Two Way)",
        "width": 28.0,
        "capacity": 7200,
        "velocity_class": "8L",
    },
    # {
    #     "code": "EW4",
    #     "name": "4 Lane Expressway (Two Way)",
    #     "width": None,
    #     "capacity": 5000,
    #     "velocity_class": "EW",
    # },
    # {
    #     "code": "EW6",
    #     "name": "6 Lane Expressway (Two Way)",
    #     "width": None,
    #     "capacity": 7500,
    #     "velocity_class": "EW",
    # },
    {
        "code": "EW8",
        "name": "Expressway",
        # "name": "8 Lane Expressway (Two Way)",
        "width": None,
        "capacity": 9200,
        "velocity_class": "EW",
    },
]

_NONE_LANE = "- Select -"
_BY_NAME = {lt["name"]: lt for lt in LANE_TYPES}
_BY_CODE = {lt["code"]: lt["name"] for lt in LANE_TYPES}
_LANE_NAMES = [_NONE_LANE] + [lt["name"] for lt in LANE_TYPES]

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
_HAS_PWR = {"hcv", "mcv"}
_DEFAULT_PWR = {"hcv": 7.22, "mcv": 8.0}

GEN_CHUNK = "general_info"
CHUNK = "traffic_and_road_data"

# ── Field definitions ─────────────────────────────────────────────────────────

TRAFFIC_FIELDS = [
    Section("Rerouting Road Configuration"),
    FieldDef(
        "alternate_road_carriageway",
        "Rerouting Road Configuration",
        "Lane configuration (auto-fills capacity and width).",
        "combo",
        options=_LANE_NAMES,
        required=True,
        default=_NONE_LANE,
        combo_placeholder=""
    ),
    FieldDef(
        "carriage_width_in_m",
        "Carriageway Width",
        "",
        "float",
        (0.0, 999.0, 2),
        unit="(m)",
        required=True,
        doc_slug=["Traffic_data", "Carriageway_width"],
    ),
    FieldDef(
        "hourly_capacity",
        "Road Hourly Capacity",
        "",
        "int",
        (0, 99999),
        unit="(PCU/hr)",
        required=True,
        doc_slug=["Traffic_data", "Hourly_capacity"],
    ),
    Section("Accident Severity Distribution"),
    FieldDef(
        "severity_minor",
        "Minor Injury",
        "Percentage of accidents resulting in minor injury",
        "float",
        (0.0, 100.0, 2),
        unit="(%)",
        doc_slug=["Traffic_data", "Minor_injury"],
    ),
    FieldDef(
        "severity_major",
        "Major Injury",
        "Percentage of accidents resulting in major injury",
        "float",
        (0.0, 100.0, 2),
        unit="(%)",
        doc_slug=["Traffic_data", "Major_injury"],
    ),
    FieldDef(
        "severity_fatal",
        "Fatal Accident",
        "Percentage of accidents resulting in fatal injury",
        "float",
        (0.0, 100.0, 2),
        unit="(%)",
        doc_slug=["Traffic_data", "Fatal_accidents"],
    ),
    Section("Road Parameters"),
    FieldDef(
        "road_roughness_mm_per_km",
        "Road Roughness",
        "Indicates the smoothness of the road surface; lower values mean smoother ride quality, higher values mean more unevenness measured in mm/km",
        "float",
        (2000, 1_00_000.0, 0),
        unit="(mm/km)",
        required=True,
        doc_slug=["Traffic_data", "Road_roughness"],
    ),
    FieldDef(
        "road_rise_m_per_km",
        "Road Rise",
        "Upward gradient of the road, expressed as vertical increase in meters per kilometer (m/km).",
        "float",
        (0.0, 9_999.0, 3),
        unit="(m/km)",
        required=True,
        warn=(
            0.01,
            9_999.0,
            "Road Rise is 0 or unusually high - please verify the value",
        ),
        doc_slug=["Traffic_data", "Road_rise_fall"],
    ),
    FieldDef(
        "road_fall_m_per_km",
        "Road Fall",
        "Downward gradient of the road, expressed as vertical decrease in meters per kilometer (m/km).",
        "float",
        (0.0, 9_999.0, 3),
        unit="(m/km)",
        required=True,
        warn=(
            0.01,
            9_999.0,
            "Road Fall is 0 or unusually high - please verify the value",
        ),
        doc_slug=["Traffic_data", "Road_rise_fall"],
    ),
    FieldDef(
        "additional_reroute_distance_km",
        "Rerouting Distance",
        "Distance travel by the road users due to rerouting during construction.",
        "float",
        (0.0, 9_999.0, 3),
        unit="(km)",
        warn=(
            0.01,
            1000,
            "Additional Reroute Distance is 0 or unusually high - please verify the value",
        ),
        doc_slug=["Traffic_data", "Additional_reroute_distance"],
    ),
    FieldDef(
        "additional_travel_time_min",
        "Rerouting Time",
        "Travel time incurred by road users due to rerouting during construction.",
        "float",
        (0.0, 9_999.0, 3),
        unit="(min)",
        warn=(
            0.01,
            1000,
            "Additional Travel Time is 0 or unusually high - please verify the value",
        ),
        doc_slug=["Traffic_data", "Additional_travel_time"],
    ),
    FieldDef(
        "crash_rate_accidents_per_million_km",
        "Crash Rate along Rerouting Route",
        "Number of accidents per million kilometers of road length per day.",
        "float",
        (0.0, 999_999.0, 2),
        unit="(acc / M km)",
        required=True,
        warn=(
            0.01,
            10000,
            "Crash Rate is 0 or unusually high - please verify the value",
        ),
        doc_slug=["Traffic_data", "Crash_rate"],
    ),
    FieldDef(
        "work_zone_multiplier",
        "Work Zone Multiplier",
        "Multiplier applied to reflect higher accident risk or delays due to construction work zone conditions.",
        "float",
        (0.0, 1.0, 4),
        required=True,
        default=1,
        warn=(
            0.001,
            1.0,
            "Work Zone Multiplier is 0 - work zone accident scaling will be disabled",
        ),
        doc_slug=["Traffic_data", "Workzone_multiplier"],
    ),
    Section("Traffic Flow"),
    FieldDef(
        "num_peak_hours",
        "Number of Peak Hours",
        "Total hours per day with peak traffic conditions.",
        "int",
        (0, 24),
        required=True,
        warn=(1, 24, "Number of Peak Hours must be between 1 and 24"),
        doc_slug=["Traffic_data", "Number_of_peak_hours"],
    ),
]


OUTSIDE_INDIA_FIELDS = [
    FieldDef(
        "road_user_cost_per_day",
        "Road User Cost per Day",
        "",
        "float",
        (0.0, 1e15, 2),
        unit="(Currency / day)",
    ),
    FieldDef(
        "source",
        "Source",
        "Reference or basis for this Road User Cost value (e.g. project report, government guideline, study, or agency publication).",
        "text",
    ),
    FieldDef(
        "comments",
        "Comments",
        "Any additional notes, assumptions, or justification for the selected Road User Cost value.",
        "textarea",
    ),
]

PROJECT_MODE_FIELDS = [
    FieldDef("mode", "Calculation Mode", "", "combo", options=["INDIA", "GLOBAL"], combo_placeholder=""),
]


# ── Vehicle Table ─────────────────────────────────────────────────────────────


class _VehicleTrafficTable(TooltipTableMixin, QTableWidget):
    def __init__(self, on_change, parent=None):
        super().__init__(len(_VEHICLES), 4, parent)
        self.on_change = on_change
        self.setHorizontalHeaderLabels(
            ["Vehicle Type", "Vehicles / Day", "Accident (% of vehicles)", "Power to weight ratio (PWR)"]
        )
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(36)
        self.setEditTriggers(QTableWidget.NoEditTriggers)
        self.setSelectionMode(QTableWidget.NoSelection)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        mark_editable_column(self, 1)
        mark_editable_column(self, 2)
        mark_editable_column(self, 3)

        self._vpd, self._acc, self._pwr = {}, {}, {}
        for row, (key, label) in enumerate(_VEHICLES):
            item = QTableWidgetItem(label)
            item.setFlags(Qt.ItemIsEnabled)
            self.setItem(row, 0, item)

            vpd = TableSpinBox()
            vpd.setRange(0, 9_999_999)
            vpd.setButtonSymbols(TableSpinBox.NoButtons)
            vpd.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            vpd.valueChanged.connect(self.on_change)
            self.setCellWidget(row, 1, vpd)
            self._vpd[key] = vpd

            acc = TableDoubleSpinBox()
            acc.setRange(0.0, 100.0)
            acc.setDecimals(2)
            acc.setButtonSymbols(TableDoubleSpinBox.NoButtons)
            acc.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            acc.valueChanged.connect(self.on_change)
            self.setCellWidget(row, 2, acc)
            self._acc[key] = acc

            if key in _HAS_PWR:
                pwr = TableDoubleSpinBox()
                pwr.setRange(0.0, 999.9)
                pwr.setDecimals(2)
                pwr.setValue(_DEFAULT_PWR.get(key, 7.0))
                pwr.setButtonSymbols(TableDoubleSpinBox.NoButtons)
                pwr.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
                pwr.valueChanged.connect(self.on_change)
                self.setCellWidget(row, 3, pwr)
                self._pwr[key] = pwr
            else:
                na = QTableWidgetItem("-")
                na.setFlags(Qt.ItemIsEnabled)
                na.setTextAlignment(Qt.AlignCenter)
                self.setItem(row, 3, na)

        self.updateGeometry()

    def set_validation_state(self, state: str):
        self.setProperty("validationState", state)
        self.style().unpolish(self)
        self.style().polish(self)
        self.viewport().update()

    def sizeHint(self):
        header_h = self.horizontalHeader().height() or 35
        rows_h = self.rowCount() * self.verticalHeader().defaultSectionSize()
        return QSize(super().sizeHint().width(), header_h + rows_h + 10)

    def minimumSizeHint(self):
        return self.sizeHint()

    def update_height(self):
        self.updateGeometry()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        w = self.viewport().width()
        self.setColumnWidth(0, int(w * 0.35))
        self.setColumnWidth(1, int(w * 0.25))
        self.setColumnWidth(2, int(w * 0.20))
        self.setColumnWidth(3, int(w * 0.20))

    def collect_to_dict(self) -> dict:
        return {
            key: {
                "vehicles_per_day": int(self._vpd[key].value()),
                "accident_percentage": float(self._acc[key].value()),
                "pwr": float(self._pwr[key].value()) if key in _HAS_PWR else 0.0,
            }
            for key, _ in _VEHICLES
        }

    def load_from_dict(self, data: dict):
        self.blockSignals(True)
        for key, _ in _VEHICLES:
            v = data.get(key, {})
            self._vpd[key].setValue(int(v.get("vehicles_per_day", 0)))
            self._acc[key].setValue(float(v.get("accident_percentage", 0.0)))
            if key in _HAS_PWR:
                self._pwr[key].setValue(float(v.get("pwr", _DEFAULT_PWR.get(key, 7.0))))
        self.blockSignals(False)


# ── Peak Hours Table ──────────────────────────────────────────────────────────


class _PeakHoursTable(TooltipTableMixin, QTableWidget):
    def __init__(self, on_change, parent=None):
        super().__init__(0, 2, parent)
        self.setHorizontalHeaderLabels(["Hour Category", "Traffic Proportion (%)"])
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(36)
        self.setEditTriggers(QTableWidget.NoEditTriggers)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        mark_editable_column(self, 1)

        self._on_change = on_change
        self._spinboxes = []
        self._other_label = None
        self._rebuilding = False

    def resizeEvent(self, event):
        super().resizeEvent(event)
        w = self.viewport().width()
        self.setColumnWidth(0, int(w * 0.60))
        self.setColumnWidth(1, int(w * 0.40))

    def rebuild(self, n: int):
        self._rebuilding = True
        old_vals = [sb.value() for sb in self._spinboxes]
        self.setRowCount(n + 1)
        self._spinboxes.clear()

        for i in range(n):
            self.setItem(i, 0, QTableWidgetItem(f"Peak Hour {i + 1}"))
            sb = TableDoubleSpinBox()
            sb.setRange(0.0, 100.0)
            sb.setDecimals(2)
            sb.setSuffix(" %")
            sb.setButtonSymbols(TableDoubleSpinBox.NoButtons)
            sb.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            sb.setValue(old_vals[i] if i < len(old_vals) else 4.0)
            sb.valueChanged.connect(self._on_value_changed)
            self.setCellWidget(i, 1, sb)
            self._spinboxes.append(sb)

        self.setItem(n, 0, QTableWidgetItem("Other Hours (Average)"))
        self._other_label = QLabel("-")
        self._other_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._other_label.setStyleSheet("padding-right: 10px; font-weight: bold;")
        self.setCellWidget(n, 1, self._other_label)

        self._rebuilding = False
        self._recalculate()
        self.update_height()

    def sizeHint(self):
        header_h = self.horizontalHeader().height() or 35
        rows_h = self.rowCount() * self.verticalHeader().defaultSectionSize()
        return QSize(super().sizeHint().width(), header_h + rows_h + 10)

    def minimumSizeHint(self):
        return self.sizeHint()

    def update_height(self):
        self.updateGeometry()

    def _on_value_changed(self):
        if not self._rebuilding:
            self._recalculate()
            self._on_change()

    def _recalculate(self):
        if self._rebuilding:
            return
        total = sum(sb.value() for sb in self._spinboxes)
        for sb in self._spinboxes:
            others = total - sb.value()
            sb.blockSignals(True)
            sb.setMaximum(max(0.0, 100.0 - others))
            sb.blockSignals(False)
        remaining_hours = 24 - len(self._spinboxes)
        remaining_percent = max(0.0, 100.0 - total)
        avg = remaining_percent / remaining_hours if remaining_hours > 0 else 0.0
        if self._other_label:
            self._other_label.setText(f"{avg:.2f} %")

    def freeze(self, frozen: bool = True):
        for sb in self._spinboxes:
            sb.setReadOnly(frozen)
            # Use dynamic property so QSS can handle the theme-aware color
            sb.setProperty("frozen", frozen)
            sb.style().unpolish(sb)
            sb.style().polish(sb)

    def collect_to_dict(self) -> dict:
        return {
            f"peak_hour_{i+1}": float(sb.value() / 100.0)
            for i, sb in enumerate(self._spinboxes)
        }

    def load_from_dict(self, data: dict):
        self._rebuilding = True
        for i, sb in enumerate(self._spinboxes):
            key = f"peak_hour_{i+1}"
            if key in data:
                sb.setValue(float(data[key]) * 100.0)
        self._rebuilding = False
        self._recalculate()


# ── Main Class ────────────────────────────────────────────────────────────────


def _compute_wpi_ratio(selected: dict, base: dict) -> dict:
    """Recursively compute element-wise ratio: selected / base."""
    result = {}
    for key, val in selected.items():
        if isinstance(val, dict):
            result[key] = _compute_wpi_ratio(val, base.get(key, {}))
        else:
            base_val = base.get(key, 1.0) if isinstance(base, dict) else 1.0
            result[key] = val / base_val if base_val else 1.0
    return result


class TrafficData(ScrollableForm):
    def __init__(self, controller=None):
        super().__init__(controller=controller, chunk_name=CHUNK)
        self._suppress_lane_signal = False
        self._last_validate_result: dict | None = None  # stored for theme re-render
        # Load WPI manager - DB profiles loaded once at startup
        self._wpi_manager = WPIManager(_WPI_DB_PATH)
        self._build_ui()
        theme_manager().theme_changed.connect(self._refresh_styles)

    def showEvent(self, event):
        super().showEvent(event)
        self._sync_mode_from_country()
        self._sync_currency_suffix()

    def _sync_currency_suffix(self):
        if hasattr(self, "road_user_cost_per_day"):
            currency = get_currency()
            self.road_user_cost_per_day.setSuffix(f" ({currency} / day)")

    # ── Severity auto-adjust ──────────────────────────────────────────────────

    def _on_severity_changed(self):
        sender = self.sender()
        minor = self.severity_minor
        major = self.severity_major
        fatal = self.severity_fatal

        if sender == minor:
            remaining = max(0.0, 100.0 - minor.value())
            if major.value() <= remaining:
                fatal.blockSignals(True)
                fatal.setValue(remaining - major.value())
                fatal.blockSignals(False)
            else:
                fatal.blockSignals(True)
                fatal.setValue(0.0)
                fatal.blockSignals(False)
                major.blockSignals(True)
                major.setValue(remaining)
                major.blockSignals(False)

        elif sender == major:
            total_fixed = minor.value() + major.value()
            if total_fixed > 100.0:
                sender.blockSignals(True)
                sender.setValue(100.0 - minor.value())
                sender.blockSignals(False)
            fatal.blockSignals(True)
            fatal.setValue(max(0.0, 100.0 - minor.value() - major.value()))
            fatal.blockSignals(False)

        elif sender == fatal:
            total_fixed = minor.value() + fatal.value()
            if total_fixed > 100.0:
                sender.blockSignals(True)
                sender.setValue(100.0 - minor.value())
                sender.blockSignals(False)
            major.blockSignals(True)
            major.setValue(max(0.0, 100.0 - minor.value() - fatal.value()))
            major.blockSignals(False)

        self._on_field_changed()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        main_form = self.form

        # ── Mode selector ─────────────────────────────────────────────────────
        _temp_form = self.form
        self.form = main_form
        build_form(self, PROJECT_MODE_FIELDS)
        self.form = _temp_form

        self.mode.setFixedWidth(220)
        self.mode.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        if self.mode.parentWidget():
            self.mode.parentWidget().setSizePolicy(
                QSizePolicy.Expanding, QSizePolicy.Fixed
            )
        self.mode.currentIndexChanged.connect(self._on_mode_changed)

        self._stack = QStackedWidget()
        # self._stack.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)

        # ── Panel 0: INDIA ────────────────────────────────────────────────────
        india_widget = QWidget()
        india_layout = QFormLayout(india_widget)
        india_layout.setContentsMargins(0, 0, 0, 0)
        india_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        india_layout.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        india_layout.setFormAlignment(Qt.AlignTop | Qt.AlignLeft)
        india_layout.setVerticalSpacing(8)

        india_layout.addRow(QLabel("<b>Vehicle Traffic Data</b>"))
        self._vehicle_table = _VehicleTrafficTable(on_change=self._on_field_changed)
        india_layout.addRow(self._vehicle_table)

        self._force_free_flow = QCheckBox("Force free-flow conditions off-peak")
        self._force_free_flow.setChecked(True)
        self._force_free_flow.stateChanged.connect(self._on_field_changed)
        # india_layout.addRow(self._force_free_flow)

        _temp_form = self.form
        self.form = india_layout
        build_form(self, TRAFFIC_FIELDS)
        self.form = _temp_form

        self.severity_minor.valueChanged.connect(self._on_severity_changed)
        self.severity_major.valueChanged.connect(self._on_severity_changed)
        self.severity_fatal.valueChanged.connect(self._on_severity_changed)

        india_layout.addRow(QLabel("<b>Peak Hour Distribution</b>"))
        self._peak_table = _PeakHoursTable(on_change=self._on_field_changed)
        india_layout.addRow(self._peak_table)

        if hasattr(self, "alternate_road_carriageway"):
            self.alternate_road_carriageway.currentIndexChanged.connect(
                self._on_lane_changed
            )
        if hasattr(self, "num_peak_hours"):
            self.num_peak_hours.valueChanged.connect(self._on_peak_count_changed)
            self._peak_table.rebuild(self.num_peak_hours.value())

        # ── WPI section (India only) ──────────────────────────────────────────
        india_layout.addRow(QLabel("<b>Wholesale Price Index (WPI) Adjustment Factors</b>"))

        # Unlisted warning (shown if any DB entries failed integrity on load)
        self._wpi_warning = QLabel()
        self._wpi_warning.setStyleSheet(f"color: {get_token('danger')};")
        self._wpi_warning.setWordWrap(True)
        self._wpi_warning.setVisible(False)
        india_layout.addRow(self._wpi_warning)
        warn = (
            self._wpi_manager.unlisted_warning()
            if hasattr(self._wpi_manager, "unlisted_warning")
            else None
        )
        if not warn and self._wpi_manager.unlisted:
            names = ", ".join(p.name for p in self._wpi_manager.unlisted)
            warn = f"⚠ WPI profiles failed integrity check and were unlisted: {names}"
        if warn:
            self._wpi_warning.setText(warn)
            self._wpi_warning.setVisible(True)

        # Selector bar
        self._wpi_selector = _WPISelector(self._wpi_manager)
        self._wpi_selector.profile_selected.connect(self._on_wpi_profile_selected)
        self._wpi_selector.profile_saved.connect(self._on_wpi_profile_saved)
        self._wpi_selector.profile_deleted.connect(self._on_wpi_profile_deleted)
        self._wpi_selector.edit_requested.connect(self._on_wpi_edit_requested)
        india_layout.addRow(self._wpi_selector)

        # Table
        self._wpi_table = _WPITable(strict_read_only=True)
        self._wpi_table.data_changed.connect(self._on_field_changed)
        self._wpi_table.verticalHeader().sectionResized.connect(self._shrink_stack_to_current)
        india_layout.addRow(self._wpi_table)

        if DEV:
            _print_btn = QPushButton("Print WPI Data")
            _print_btn.clicked.connect(self._print_wpi_data)
            india_layout.addRow(_print_btn)

        # Load first profile into table
        first = self._wpi_selector.current_profile()
        if first:
            self._wpi_table.load_from_data(first.data)
            self._wpi_table.set_editable(False)

        self._stack.addWidget(india_widget)  # index 0

        # ── Panel 1: GLOBAL ───────────────────────────────────────────────────
        outside_widget = QWidget()
        outside_layout = QFormLayout(outside_widget)
        outside_layout.setContentsMargins(0, 0, 0, 0)
        outside_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        outside_layout.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        outside_layout.setFormAlignment(Qt.AlignTop | Qt.AlignLeft)
        outside_layout.setVerticalSpacing(8)

        _temp_form = self.form
        self.form = outside_layout
        build_form(self, OUTSIDE_INDIA_FIELDS)
        self.form = _temp_form

        self._stack.addWidget(outside_widget)
        self._shrink_stack_to_current()

        # ── Shared bottom ─────────────────────────────────────────────────────
        main_form.addRow(self._stack)

        self._remarks = RemarksEditor(
            title="Notes", on_change=self._on_field_changed
        )
        main_form.addRow(self._remarks)

        btn_row = QHBoxLayout()
        btn_clear = QPushButton("Clear All")
        btn_clear.setMinimumHeight(35)
        btn_clear.clicked.connect(self.clear_all)
        btn_row.addWidget(btn_clear)

        btn_validate = QPushButton("Validate this page")
        btn_validate.setMinimumHeight(35)
        btn_validate.setFixedWidth(160)
        btn_validate.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        btn_validate.clicked.connect(self._on_validate_clicked)
        btn_row.addWidget(btn_validate)

        btn_widget = QWidget()
        btn_widget.setLayout(btn_row)
        btn_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        main_form.addRow(btn_widget)

        self._val_result_label = QLabel()
        self._val_result_label.setWordWrap(True)
        self._val_result_label.setVisible(False)
        self._val_result_label.setContentsMargins(0, 4, 0, 4)
        main_form.addRow(self._val_result_label)

    # ── Theme refresh ─────────────────────────────────────────────────────────

    def _refresh_styles(self):
        """Reapply all token-based styles. Called on every theme change."""
        self._wpi_warning.setStyleSheet(f"color: {get_token('danger')};")
        if self._val_result_label.isVisible():
            self._on_validate_clicked()
        
        # Ensure form labels and other elements repaint with the new palette
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    # ── Slot handlers ─────────────────────────────────────────────────────────

    def _on_mode_changed(self, idx: int):
        self._stack.setCurrentIndex(idx)
        self._shrink_stack_to_current()
        self._on_field_changed()

    def _apply_carriageway_enabled(self):
        """Sync carriage_width_in_m enabled state to the current lane selection."""
        if not hasattr(self, "alternate_road_carriageway") or not hasattr(self, "carriage_width_in_m"):
            return
        text = self.alternate_road_carriageway.currentText()
        if text == _NONE_LANE:
            self.carriage_width_in_m.setEnabled(False)
            return
        lane = _BY_NAME.get(text)
        if lane:
            self.carriage_width_in_m.setEnabled(lane.get("width") is None)

    def _on_lane_changed(self, _idx: int):
        if self._suppress_lane_signal:
            return
        text = self.alternate_road_carriageway.currentText()
        if text == _NONE_LANE:
            self.carriage_width_in_m.setValue(0.0)
            self.carriage_width_in_m.setEnabled(False)
            self.hourly_capacity.setValue(0)
            self._on_field_changed()
            return
        lane = _BY_NAME.get(text)
        if not lane:
            return
        w = lane.get("width")
        if w is not None:
            self.carriage_width_in_m.setValue(float(w))
            self.carriage_width_in_m.setEnabled(False)
        else:
            self.carriage_width_in_m.setValue(0.0)
            self.carriage_width_in_m.setEnabled(True)
        self.hourly_capacity.setValue(int(lane.get("capacity", 0)))
        self._on_field_changed()

    def _on_peak_count_changed(self, n: int):
        self._peak_table.rebuild(n)
        self._on_field_changed()

    def _sync_mode_from_country(self):
        if not self.controller or not self.controller.engine:
            return
        bridge = self.controller.engine.fetch_chunk(GEN_CHUNK) or {}
        # print(bridge)
        country = bridge.get("project_country", "GLOBAL")
        is_india = country.strip().upper() == "INDIA"

        self.mode.setEnabled(is_india)

        if not is_india:
            idx = self.mode.findText("GLOBAL")
            if idx >= 0:
                self.mode.blockSignals(True)
                self.mode.setCurrentIndex(idx)
                self.mode.blockSignals(False)
                self._stack.setCurrentIndex(idx)
        else:
            self._stack.setCurrentIndex(self.mode.currentIndex())
        self._shrink_stack_to_current()

    def _shrink_stack_to_current(self):
        """
        Hide all panels except current so the stack shrinks to fit.
        This works inside QScrollArea unlike setFixedHeight.
        """
        if not self._stack.currentWidget():
            return

        for i in range(self._stack.count()):
            w = self._stack.widget(i)
            if i == self._stack.currentIndex():
                w.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
            else:
                w.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)

        # Use a zero-timer to ensure child layouts (like the WPI table) 
        # have finished their size calculation before we snap the stack height.
        QTimer.singleShot(0, self._perform_shrink)

    def _perform_shrink(self):
        current = self._stack.currentWidget()
        if not current:
            return
        
        # Trigger layout recalculation on the container
        current.adjustSize()
        h = current.sizeHint().height()
        self._stack.setMaximumHeight(h)
        self._stack.updateGeometry()
        
        # Finally, tell the scroll area content to grow/shrink
        if hasattr(self, "_content"):
            self._content.adjustSize()
            self._content.updateGeometry()

    # ── WPI slot handlers ─────────────────────────────────────────────────────

    def _on_wpi_profile_selected(self, profile: WPIProfile):
        """Load selected profile into table. Main page table is ALWAYS read-only."""
        self._wpi_table.load_from_data(profile.data)
        self._wpi_table.set_editable(False)
        self._on_field_changed()

    def _on_wpi_profile_saved(self, profile: WPIProfile):
        """After manager adds/saves - reload and ensure read-only."""
        self._wpi_table.load_from_data(profile.data)
        self._wpi_table.set_editable(False)
        self._on_field_changed()

    def _on_wpi_profile_deleted(self, profile_id: str):
        """After delete - save chunk."""
        self._on_field_changed()

    def _on_wpi_edit_requested(self):
        """Redundant in this mode, manager handles its own edits."""
        pass

    def _print_wpi_data(self):
        print(self._wpi_table.collect_to_data())

    # ── Data collection ───────────────────────────────────────────────────────

    def collect_data(self) -> dict:
        data = super().get_data_dict()

        # Map alternate_road_carriageway display name back to IRC code
        alternate_road_carriageway = data.get("alternate_road_carriageway")
        if alternate_road_carriageway and alternate_road_carriageway != _NONE_LANE:
            for dic in LANE_TYPES:
                if dic.get("name") == alternate_road_carriageway:
                    data["alternate_road_carriageway"] = dic.get("code")
                    break
        else:
            data["alternate_road_carriageway"] = ""

        data["mode"] = self.mode.currentText()
        data["remarks"] = self._remarks.to_html()
        data["force_free_flow_off_peak"] = bool(self._force_free_flow.isChecked())

        # Vehicle table - merge to preserve extra keys
        existing_veh = {}
        if self.controller and self.controller.engine:
            existing_veh = (self.controller.engine.fetch_chunk(CHUNK) or {}).get(
                "vehicle_data", {}
            )
        veh_table_dict = self._vehicle_table.collect_to_dict()
        merged_veh = {}
        for key, _ in _VEHICLES:
            base = dict(existing_veh.get(key, {}))
            base.update(veh_table_dict.get(key, {}))
            merged_veh[key] = base
        data["vehicle_data"] = merged_veh

        data["peak_hour_distribution"] = self._peak_table.collect_to_dict()

        data["global_entry"] = {
            "road_user_cost_per_day": data.pop("road_user_cost_per_day", 0.0),
            "source": data.pop("source", ""),
            "comments": data.pop("comments", ""),
        }

        # WPI - store selected profile id + snapshot of data + custom profiles
        current_profile = self._wpi_selector.current_profile()
        selected_data = self._wpi_table.collect_to_data()

        # Base is always 2019; ratio = selected / base element-wise
        base_profile = self._wpi_manager.get_by_id("wpi_2019")
        base_data = base_profile.data if base_profile else selected_data
        ratio_data = _compute_wpi_ratio(selected_data, base_data)

        data["wpi"] = {
            "selected_profile_id": current_profile.id if current_profile else None,
            "selected_profile_name": current_profile.name if current_profile else None,
            "selected_profile_year": current_profile.year if current_profile else None,
            "profile_type": (
                "custom" if (current_profile and current_profile.is_custom) else "db"
            ),
            "data_snapshot": {
                "base": base_data,
                "selected": selected_data,
                "ratio": ratio_data,
            },
            "common_state": self._wpi_table.common_state(),
            "custom_profiles": self._wpi_manager.dump_custom_profiles(),
        }

        return data

    # ── Data loading ──────────────────────────────────────────────────────────

    def load_data(self, data: dict):
        if not data:
            return
        # Safety: load_data can be called by controller before _build_ui finishes.
        if not hasattr(self, "_remarks") or not hasattr(self, "_vehicle_table"):
            return

        self.blockSignals(True)
        self._suppress_lane_signal = True
        try:
            self._remarks.from_html(data.get("remarks", ""))
            self._force_free_flow.setChecked(
                bool(data.get("force_free_flow_off_peak", True))
            )

            # Translate stored IRC code back to display name for the combo
            load_data = dict(data)
            code = load_data.get("alternate_road_carriageway", "")
            load_data["alternate_road_carriageway"] = _BY_CODE.get(code, _NONE_LANE)

            # Flatten global_entry so super().load_data_dict can populate widgets
            global_entry = data.get("global_entry", {})
            load_data.update({
                "road_user_cost_per_day": global_entry.get("road_user_cost_per_day", 0.0),
                "source": global_entry.get("source", ""),
                "comments": global_entry.get("comments", ""),
            })

            self.mode.blockSignals(True)
            super().load_data_dict(load_data)
            self.mode.blockSignals(False)
            self._stack.setCurrentIndex(self.mode.currentIndex())

            self._vehicle_table.load_from_dict(data.get("vehicle_data", {}))

            n_peak = int(data.get("num_peak_hours", 1))
            if hasattr(self, "num_peak_hours"):
                self.num_peak_hours.blockSignals(True)
                self.num_peak_hours.setValue(n_peak)
                self.num_peak_hours.blockSignals(False)
            self._peak_table.rebuild(n_peak)
            self._peak_table.load_from_dict(data.get("peak_hour_distribution", {}))

            # WPI
            wpi = data.get("wpi", {})
            if wpi:
                self._load_wpi(wpi)

        finally:
            self.blockSignals(False)
            self._suppress_lane_signal = False
            self._vehicle_table.update_height()
            self._peak_table.update_height()
            self._shrink_stack_to_current()
            self._apply_carriageway_enabled()

    def _load_wpi(self, wpi: dict):
        """Restore WPI state from saved chunk data."""
        # 1. Reload custom profiles into manager
        custom_raw = wpi.get("custom_profiles", [])
        self._wpi_manager.load_custom_profiles(custom_raw)

        # 2. Refresh selector combo
        selected_id = wpi.get("selected_profile_id")
        self._wpi_selector.refresh(select_id=selected_id)

        # 3. Load data snapshot into table
        snapshot = wpi.get("data_snapshot")
        if snapshot:
            # data_snapshot may be the new three-part dict or legacy flat dict
            selected_snapshot = (
                snapshot.get("selected", snapshot)
                if isinstance(snapshot, dict) and "selected" in snapshot
                else snapshot
            )
            self._wpi_table.load_from_data(selected_snapshot)

        # 4. Restore common-to-all checkbox states
        common_state = wpi.get("common_state", {})
        if common_state:
            # Keys are stored as strings in JSON - convert back to int
            self._wpi_table.load_common_state(
                {int(k): v for k, v in common_state.items()}
            )

        # 5. Set editability based on resolved profile
        profile = self._wpi_manager.get_by_id(selected_id) if selected_id else None
        if not profile:
            profile = self._wpi_selector.current_profile()
        if profile:
            self._wpi_table.set_editable(False)

    # ── Clear all ─────────────────────────────────────────────────────────────

    def clear_all(self):
        reply = QMessageBox.question(
            self,
            "Clear All Data",
            "This will reset all fields on this page to their default values. "
            "This action cannot be undone.\n\nContinue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        self.blockSignals(True)
        self._vehicle_table.load_from_dict({})
        self._peak_table.rebuild(1)
        self._remarks.clear_content()
        for f in PROJECT_MODE_FIELDS + TRAFFIC_FIELDS + OUTSIDE_INDIA_FIELDS:
            if isinstance(f, FieldDef):
                attr = getattr(self, f.key, None)
                if isinstance(attr, (QSpinBox, QDoubleSpinBox)):
                    attr.setValue(attr.minimum())
                elif hasattr(attr, "clear"):
                    attr.clear()
        if hasattr(self, "alternate_road_carriageway"):
            self._suppress_lane_signal = True
            idx = self.alternate_road_carriageway.findText(_NONE_LANE)
            if idx >= 0:
                self.alternate_road_carriageway.setCurrentIndex(idx)
            self._suppress_lane_signal = False
        # Reset WPI to first DB profile
        self._wpi_selector.refresh()
        first = self._wpi_selector.current_profile()
        if first:
            self._wpi_table.load_from_data(first.data)
            self._wpi_table.set_editable(False)
        self.blockSignals(False)
        self._val_result_label.setVisible(False)
        self._on_field_changed()

    # ── Validation / data export ──────────────────────────────────────────────

    def freeze(self, frozen: bool = True):
        freeze_form(TRAFFIC_FIELDS, self, frozen)
        freeze_form(OUTSIDE_INDIA_FIELDS, self, frozen)
        freeze_widgets(frozen, self._vehicle_table, self.mode, self._force_free_flow)
        self._peak_table.freeze(frozen)
        self._wpi_selector.freeze(frozen)
        self._wpi_table.freeze(frozen)
        # freeze_form uses setReadOnly for spinboxes; carriage_width_in_m also
        # uses setEnabled to reflect lane selection - reapply after any freeze change.
        if not frozen:
            self._apply_carriageway_enabled()

    def clear_validation(self):
        clear_field_styles(TRAFFIC_FIELDS, self)
        clear_field_styles(OUTSIDE_INDIA_FIELDS, self)

    def validate(self) -> dict:
        mode = self.mode.currentText()

        if mode == "INDIA":
            result = validate_form(TRAFFIC_FIELDS, self)
            errors = result["errors"]
            warnings = result["warnings"]

            # Carriageway must be selected
            if hasattr(self, "alternate_road_carriageway"):
                if self.alternate_road_carriageway.currentText() == _NONE_LANE:
                    errors.append("Alternate Road Carriageway type is not selected - choose the carriageway configuration available for traffic diversion during construction")
                    self.alternate_road_carriageway.setProperty("validationState", "error")
                else:
                    self.alternate_road_carriageway.setProperty("validationState", "")
                
                self.alternate_road_carriageway.style().unpolish(self.alternate_road_carriageway)
                self.alternate_road_carriageway.style().polish(self.alternate_road_carriageway)

                if hasattr(self, "carriage_width_in_m") and self.carriage_width_in_m.value() == 0.0:
                    errors.append("Carriageway Width of the Alternate Road cannot be 0 - enter the usable width of the diversion road in metres")
                    self.carriage_width_in_m.setProperty("validationState", "error")
                else:
                    self.carriage_width_in_m.setProperty("validationState", "")
                
                self.carriage_width_in_m.style().unpolish(self.carriage_width_in_m)
                self.carriage_width_in_m.style().polish(self.carriage_width_in_m)

            vehicle_data = self._vehicle_table.collect_to_dict()
            total_vpd = sum(v["vehicles_per_day"] for v in vehicle_data.values())

            if total_vpd == 0:
                # ADT = 0 - user opts out of road user cost; skip all transport checks
                warnings.append(
                    "All Vehicles per Day values are 0 - road user cost calculations will be skipped; enter vehicle counts if road user costs should be included in the analysis"
                )
                self._vehicle_table.set_validation_state("")
            else:
                # Per-vehicle accident % must sum to 100 (±0.1)
                total_acc = sum(v["accident_percentage"] for v in vehicle_data.values())
                if abs(total_acc - 100.0) > 0.1:
                    errors.append(
                        f"Vehicle accident percentages must sum to 100% - current total is {total_acc:.1f}%; adjust the per-vehicle percentages so all rows together add up to 100%"
                    )
                    self._vehicle_table.set_validation_state("error")
                else:
                    self._vehicle_table.set_validation_state("")

                # Accident severity distribution must sum to 100%
                total_sev = (
                    self.severity_minor.value()
                    + self.severity_major.value()
                    + self.severity_fatal.value()
                )
                if abs(total_sev - 100.0) > 1e-4:
                    errors.append(
                        f"Accident severity proportions (Minor + Major + Fatal) must sum to 100% - current total is {total_sev:.1f}%; adjust the three severity fields to add up to exactly 100%"
                    )

                # PWR must be > 0 for hcv/mcv when their VPD > 0
                _veh_label = dict(_VEHICLES)
                for key in _HAS_PWR:
                    veh = vehicle_data.get(key, {})
                    if veh.get("vehicles_per_day", 0) > 0 and veh.get("pwr", 0.0) <= 0:
                        errors.append(
                            f"Passenger Weight Ratio (PWR) for {_veh_label.get(key, key)} must be greater than 0 when that vehicle type has traffic - enter a valid PWR value or set its Vehicles per Day to 0"
                        )

                # Road Hourly Capacity must be > 0
                if hasattr(self, "hourly_capacity") and self.hourly_capacity.value() == 0:
                    errors.append("Hourly Road Capacity cannot be 0 - enter the maximum number of vehicles the road can carry per hour")
                    self.hourly_capacity.setProperty("validationState", "error")
                else:
                    self.hourly_capacity.setProperty("validationState", "")
                
                self.hourly_capacity.style().unpolish(self.hourly_capacity)
                self.hourly_capacity.style().polish(self.hourly_capacity)

                # Peak hour validation
                n_peak = self.num_peak_hours.value() if hasattr(self, "num_peak_hours") else 0
                if n_peak > 0:
                    peak_data = self._peak_table.collect_to_dict()
                    peak_fractions = list(peak_data.values())
                    zero_peaks = [i + 1 for i, v in enumerate(peak_fractions) if v == 0.0]
                    if zero_peaks:
                        hrs = ", ".join(f"Peak Hour {h}" for h in zero_peaks)
                        errors.append(f"Peak hour traffic proportion cannot be 0 for: {hrs} - enter the fraction of daily traffic that occurs during each peak hour")
                    total_peak = sum(peak_fractions)
                    if total_peak > 1.0 + 1e-6:
                        errors.append(
                            f"Peak hour proportions total {total_peak * 100:.1f}%, which exceeds 100% \u2014 reduce the peak hour values so their combined share does not exceed 100% of daily traffic"
                        )

            # WPI values must not be zero (checked regardless of ADT)
            errors.extend(self._wpi_table.validate())

        else:  # GLOBAL
            result = validate_form(OUTSIDE_INDIA_FIELDS, self)
            errors = result["errors"]
            warnings = result["warnings"]

            if self.road_user_cost_per_day.value() <= 0:
                warnings.append(
                    "Road User Cost per Day is 0 - road user costs will not be included in the LCCA output; enter a positive value if road users bear costs during construction"
                )
                self.road_user_cost_per_day.setProperty("validationState", "warning")
            else:
                self.road_user_cost_per_day.setProperty("validationState", "")
            
            self.road_user_cost_per_day.style().unpolish(self.road_user_cost_per_day)
            self.road_user_cost_per_day.style().polish(self.road_user_cost_per_day)

        return {"errors": errors, "warnings": warnings}

    def _on_validate_clicked(self):
        result = self.validate()
        errors = result.get("errors", [])
        warnings = result.get("warnings", [])

        if not errors and not warnings:
            html = f'<span style="color:{get_token("success")}; font-weight:bold;">&#10004; All checks passed</span>'
        else:
            lines = []
            for e in errors:
                lines.append(f'<span style="color:{get_token("danger")};">&#10006; {e}</span>')
            for w in warnings:
                lines.append(f'<span style="color:{get_token("warning")};">&#9888; {w}</span>')
            html = "<br>".join(lines)

        self._val_result_label.setText(html)
        self._val_result_label.setVisible(True)

    def get_data(self) -> dict:
        return {"chunk": CHUNK, "data": self.collect_data()}

    # ── Base overrides ────────────────────────────────────────────────────────

    def get_data_dict(self) -> dict:
        return self.collect_data()

    def load_data_dict(self, data: dict):
        self.load_data(data)

    def refresh_from_engine(self):
        if not self.controller or not self.controller.engine:
            return
        if not self.controller.engine.is_active() or not self.chunk_name:
            return
        data = self.controller.engine.fetch_chunk(self.chunk_name)
        if data:
            self.load_data(data)


