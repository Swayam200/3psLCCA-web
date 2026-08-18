"""
gui/components/maintenance/main.py
"""

from PySide6.QtWidgets import (
    QHBoxLayout,
    QPushButton,
    QWidget,
    QDoubleSpinBox,
    QSpinBox,
    QMessageBox,
)

from ..base_widget import ScrollableForm
from ..utils.form_builder.form_definitions import FieldDef, Section
from ..utils.form_builder.form_builder import build_form
from ..utils.validation_helpers import (
    clear_field_styles,
    freeze_form,
    freeze_widgets,
    validate_form,
    confirm_clear_all,
)



MAINTENANCE_FIELDS = [
    # ── Routine Maintenance ──────────────────────────────────────────────
    Section("Routine Maintenance"),
    FieldDef(
        "routine_inspection_cost",
        "Routine Inspection Cost",
        "[Cost incurred due to routine inspection, expressed as a percentage of the initial construction cost.]",
        "float",
        options=(0.0, 100.0, 3),
        unit="(% of initial construction cost)",
        required=True,
        default=0.0,
        warn=(0.01, 100.0, "Routine Inspection Cost is 0 - cost will not be included"),
        doc_slug=["Maintenance_repair", "Routine_inspection_cost"],
    ),
    FieldDef(
        "routine_inspection_freq",
        "Routine Inspection Frequency",
        "[Interval between routine inspections (expressed in years).]",
        "int",
        options=(0, 50),
        unit="(year)",
        required=True,
        default=0,
        warn=(
            1,
            50,
            "Routine Inspection Frequency seems unusual - expected between 1 and 50 years",
        ),
        doc_slug=["Maintenance_repair", "Routine_inspection_frequency"],
    ),
    # ── Periodic Maintenance ─────────────────────────────────────────────
    Section("Periodic Maintenance"),
    FieldDef(
        "periodic_maintenance_cost",
        "Periodic Maintenance Cost",
        "[Cost incurred due to periodic maintenance, expressed as a percentage of the initial construction cost.]",
        "float",
        options=(0.0, 100.0, 3),
        unit="(% of initial construction cost)",
        required=True,
        default=0.0,
        warn=(
            0.01,
            100.0,
            "Periodic Maintenance Cost is 0 - cost will not be included",
        ),
        doc_slug=["Maintenance_repair", "Periodic_maintenance_cost"],
    ),
    FieldDef(
        "periodic_maintenance_carbon_cost",
        "Periodic Maintenance Carbon Cost",
        "[Carbon emissions cost incurred due to periodic maintenance, expressed as a percentage of the initial carbon emissions cost.]",
        "float",
        options=(0.0, 100.0, 3),
        unit="(% of initial construction cost)",
        required=True,
        default=0.0,
        warn=(
            0.01,
            100.0,
            "Periodic Maintenance Carbon Cost is 0 - cost will not be included",
        ),
        doc_slug=["Maintenance_repair", "Periodic_maintenance_carbon_cost"],
    ),
    FieldDef(
        "periodic_maintenance_freq",
        "Periodic Maintenance Frequency",
        "[Interval between periodic maintenance works (expressed in years).]",
        "int",
        options=(0, 100),
        unit="(year)",
        required=True,
        default=0,
        warn=(
            1,
            100,
            "Periodic Maintenance Frequency seems unusual - expected between 1 and 100 years",
        ),
        doc_slug=["Maintenance_repair", "Periodic_maintenance_frequency"],
    ),
    # ── Major Works ──────────────────────────────────────────────────────
    Section("Major Inspection"),
    FieldDef(
        "major_inspection_cost",
        "Major Inspection Cost",
        "[Cost incurred due to major inspection, expressed as a percentage of the initial construction cost.]",
        "float",
        options=(0.0, 100.0, 3),
        unit="(% of initial construction cost)",
        required=True,
        default=0.0,
        warn=(0.01, 100.0, "Major Inspection Cost is 0 - cost will not be included"),
        doc_slug=["Maintenance_repair", "Major_inspection_cost"],
    ),
    FieldDef(
        "major_inspection_freq",
        "Major Inspection Frequency",
        "[Interval between major inspections (expressed in years).]",
        "int",
        options=(0, 100),
        unit="(year)",
        required=True,
        default=0,
        warn=(
            1,
            100,
            "Major Inspection Frequency seems unusual - expected between 1 and 100 years",
        ),
        doc_slug=["Maintenance_repair", "Major_inspection_frequency"],
    ),
    Section("Major Repair"),
    FieldDef(
        "major_repair_cost",
        "Major Repair Cost",
        "[Cost incurred due to major repairs, expressed as a percentage of the initial construction cost.]",
        "float",
        options=(0.0, 100.0, 3),
        unit="(% of initial construction cost)",
        required=True,
        default=0.0,
        warn=(0.01, 100.0, "Major Repair Cost is 0 - cost will not be included"),
        doc_slug=["Maintenance_repair", "Major_repair_cost"],
    ),
    FieldDef(
        "major_repair_carbon_cost",
        "Major Repair Carbon Cost",
        "[Carbon emissions cost incurred due to major repairs, expressed as a percentage of the initial carbon emissions cost.]",
        "float",
        options=(0.0, 100.0, 3),
        unit="(% of initial construction cost)",
        required=True,
        default=0.0,
        warn=(0.01, 100.0, "Major Repair Carbon Cost is 0 - cost will not be included"),
        doc_slug=["Maintenance_repair", "Major_repair_carbon_cost"],
    ),
    FieldDef(
        "major_repair_freq",
        "Major Repair Frequency",
        "[Interval between major repair works (expressed in years).]",
        "int",
        options=(0, 100),
        unit="(year)",
        required=True,
        default=0,
        warn=(
            1,
            100,
            "Major Repair Frequency seems unusual - expected between 1 and 100 years",
        ),
        doc_slug=["Maintenance_repair", "Major_repair_frequency"],
    ),
    FieldDef(
        "major_repair_duration",
        "Major Repair Duration",
        "[Duration of major repair works (expressed in months).]",
        "int",
        options=(0, 60),
        unit="(months)",
        required=True,
        default=0,
        warn=(
            1,
            60,
            "Major Repair Duration seems unusual - expected between 1 and 60 months",
        ),
        doc_slug=["Maintenance_repair", "Major_repair_duration"],
    ),
    # ── Bearings & Expansion Joints ──────────────────────────────────────
    Section("Bearings & Expansion Joints"),
    FieldDef(
        "bearing_exp_joint_cost",
        "Bearing & Expansion Joint Replacement Cost",
        "[Cost incurred due to replacement of bearing and expansion joint, expressed as a percentage of the superstructure cost.]",
        "float",
        options=(0.0, 100.0, 3),
        unit="(% of initial construction cost)",
        required=True,
        default=0.0,
        warn=(
            0.01,
            100.0,
            "Bearing & Expansion Joint Cost is 0 - cost will not be included",
        ),
        doc_slug=["Maintenance_repair", "Bearing_expansion_joint_replacement_cost"],
    ),
    FieldDef(
        "bearing_exp_joint_freq",
        "Bearing & Expansion Joint Replacement Frequency",
        "[Interval between bearing and expansion joint replacements (expressed in years).]",
        "int",
        options=(0, 100),
        unit="(year)",
        required=True,
        default=0,
        warn=(
            1,
            100,
            "Bearing & Expansion Joint Frequency seems unusual - expected between 1 and 100 years",
        ),
        doc_slug=["Maintenance_repair", "Bearing_expansion_joint_replacement_frequency"],
    ),
    FieldDef(
        "bearing_exp_joint_duration",
        "Bearing & Expansion Joint Replacement Duration",
        "[Duration of bearing and expansion joint replacement works (expressed in days).]",
        "int",
        options=(0, 365),
        unit="(days)",
        required=True,
        default=0,
        warn=(
            1,
            365,
            "Replacement Duration seems unusual - expected between 1 and 365 days",
        ),
        doc_slug=["Maintenance_repair", "Bearing_expansion_joint_replacement_duration"],
    ),
]


SUGGESTED_VALUES = {
    # ── Routine Maintenance ──────────────────────────────────────────────
    "routine_inspection_cost": 0.1,
    "routine_inspection_freq": 1,
    # ── Periodic Maintenance ─────────────────────────────────────────────
    "periodic_maintenance_cost": 0.55,
    "periodic_maintenance_carbon_cost": 0.55,
    "periodic_maintenance_freq": 5,
    # ── Major Works ──────────────────────────────────────────────────────
    "major_inspection_cost": 0.5,
    "major_inspection_freq": 5,
    "major_repair_cost": 10.0,
    "major_repair_carbon_cost": 0.55,
    "major_repair_freq": 20,
    "major_repair_duration": 3,
    # ── Bearings & Expansion Joints ──────────────────────────────────────
    "bearing_exp_joint_cost": 12.5,
    "bearing_exp_joint_freq": 25,
    "bearing_exp_joint_duration": 2,
    # ── End of Life ───────────────────────────────────────────────────────
    "demolition_cost": 10.0,
    "demolition_carbon_cost": 10.0,
    "demolition_duration": 1,
}


class Maintenance(ScrollableForm):

    def __init__(self, controller=None):
        super().__init__(controller=controller, chunk_name="maintenance_data")

        self.required_keys = build_form(self, MAINTENANCE_FIELDS)

        # ── Buttons row ──────────────────────────────────────────────────
        btn_row = QWidget()
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 10, 0, 10)
        btn_layout.setSpacing(10)

        self.btn_load_suggested = QPushButton("Load Suggested Values")
        self.btn_load_suggested.setMinimumHeight(35)
        self.btn_load_suggested.clicked.connect(self.load_suggested_values)

        self.btn_clear_all = QPushButton("Clear All")
        self.btn_clear_all.setMinimumHeight(35)
        self.btn_clear_all.clicked.connect(self.clear_all)

        btn_layout.addWidget(self.btn_load_suggested)
        btn_layout.addWidget(self.btn_clear_all)
        self.form.addRow(btn_row)

    # ── Suggested values ─────────────────────────────────────────────────
    def load_suggested_values(self):
        for key, val in SUGGESTED_VALUES.items():
            widget = getattr(self, key, None)
            if widget is None:
                continue
            if isinstance(widget, (QDoubleSpinBox, QSpinBox)):
                widget.setValue(val)
            elif isinstance(widget, QComboBox):
                idx = widget.findText(str(val))
                if idx >= 0:
                    widget.setCurrentIndex(idx)
            elif isinstance(widget, QLineEdit):
                widget.setText(str(val))
            widget.setStyleSheet("")

        self._on_field_changed()

        if self.controller and self.controller.engine:
            self.controller.engine._log("Maintenance: Suggested values applied.")

    # ── Clear All ────────────────────────────────────────────────────────
    def clear_all(self):
        if not confirm_clear_all(self):
            return

        for entry in MAINTENANCE_FIELDS:
            if isinstance(entry, Section):
                continue
            widget = getattr(self, entry.key, None)
            if widget is None:
                continue
            if isinstance(widget, QLineEdit):
                widget.clear()
            elif isinstance(widget, QComboBox):
                widget.setCurrentIndex(0)
            elif isinstance(widget, (QDoubleSpinBox, QSpinBox)):
                widget.setValue(widget.minimum())
            widget.setStyleSheet("")

        self._on_field_changed()

        if self.controller and self.controller.engine:
            self.controller.engine._log("Maintenance: All fields cleared.")

    # ── Validation ───────────────────────────────────────────────────────
    def freeze(self, frozen: bool = True):
        freeze_form(MAINTENANCE_FIELDS, self, frozen)
        freeze_widgets(frozen, self.btn_load_suggested, self.btn_clear_all)

    def clear_validation(self):
        clear_field_styles(MAINTENANCE_FIELDS, self)

    def validate(self) -> dict:
        return validate_form(MAINTENANCE_FIELDS, self)

    def get_data(self) -> dict:
        return {"chunk": "maintenance_data", "data": self.get_data_dict()}
