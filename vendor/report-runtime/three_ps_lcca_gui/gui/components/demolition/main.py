from PySide6.QtWidgets import (
    QHBoxLayout,
    QPushButton,
    QWidget,
    QComboBox,
    QDoubleSpinBox,
    QSpinBox,
    QSpacerItem,
    QSizePolicy,
)
from PySide6.QtCore import Qt, Signal
from ..base_widget import ScrollableForm
from ..utils.form_builder.form_definitions import FieldDef, Section
from ..utils.form_builder.form_builder import build_form
from ..utils.validation_helpers import clear_field_styles, freeze_form, freeze_widgets, validate_form, confirm_clear_all


SUGGESTED_VALUES = {
    "demolition_cost_pct": 10.0,
    "demolition_carbon_cost_pct": 10.0,
    "demolition_duration": 1,
}

DEMOLITION_FIELDS = [
    Section("End of Life"),
    FieldDef(
        "demolition_cost_pct",
        "Demolition & Disposal Costs (%)",
        "Costs of demoilition expressed as percentage of initial construction cost.",
        "float",
        (0.0, 100.0, 1),
        unit="(%)",
        required=True,
        default=0.0,
        doc_slug=["Demolition", "Demolition_disposal_cost"],
    ),
    FieldDef(
        "demolition_carbon_cost_pct",
        "Demolition & Disposal Carbon Cost (%)",
        "Carbon emission cost of demolition expressed as a percentage of inital carbon emission cost.",
        "float",
        (0.0, 100.0, 1),
        unit="(%)",
        required=True,
        default=0.0,
        doc_slug=["Demolition", "Demolition_disposal_carbon_cost"],
    ),
    FieldDef(
        "demolition_duration",
        "Demolition & Disposal Duration",
        "Time taken for demolition work in months",
        "int",
        (0, 60),
        unit="(months)",
        required=True,
        default=0,
        doc_slug=["Demolition", "Demolition_disposal_duration"],
    ),
]


DEMOLITION_WARN_RULES = {
    "demolition_cost_pct": (0.1, 50.0,
                            "Demolition & Disposal Cost is 0% - if end-of-life demolition costs apply, enter a percentage of the initial construction cost",
                            "Demolition & Disposal Cost exceeds 50% of construction cost - this is unusually high; confirm the value is correct"),
    "demolition_carbon_cost_pct": (0.1, 50.0,
                                   "Demolition & Disposal Carbon Cost is 0% - if carbon costs apply at end of life, enter a percentage of the initial carbon emission cost",
                                   "Demolition & Disposal Carbon Cost exceeds 50% - this is unusually high; confirm this is the correct proportion of the initial carbon cost"),
    "demolition_duration": (1, 24,
                            "Demolition & Disposal Duration is 0 months - enter the expected time to complete demolition and disposal work",
                            "Demolition & Disposal Duration exceeds 24 months - this is a long demolition period; confirm the value is in months, not years"),
}


class Demolition(ScrollableForm):
    created = Signal()

    def __init__(self, controller=None):
        super().__init__(controller=controller, chunk_name="demolition_data")
        self.required_keys = build_form(self, DEMOLITION_FIELDS)

        # ── Buttons row (Maintenance Style) ──────────────────────────────────
        btn_row = QWidget()
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 10, 0, 10)

        self.btn_load_suggested = QPushButton("Load Suggested Values")
        self.btn_load_suggested.setMinimumHeight(35)
        self.btn_load_suggested.clicked.connect(self.load_suggested_values)

        self.btn_clear_all = QPushButton("Clear All")
        self.btn_clear_all.setMinimumHeight(35)
        self.btn_clear_all.clicked.connect(self.clear_all)

        btn_layout.addWidget(self.btn_load_suggested)
        btn_layout.addWidget(self.btn_clear_all)

        # Maintenance usually adds the row directly to the form
        self.form.addRow(btn_row)

        # Vertical Spacer to prevent the AttributeError from earlier
        spacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)
        self.form.addItem(spacer)

    def load_suggested_values(self):
        for key, val in SUGGESTED_VALUES.items():
            widget = getattr(self, key, None)
            if widget:
                widget.setValue(val)
                widget.setStyleSheet("")
        self._on_field_changed()

    def clear_all(self):
        if not confirm_clear_all(self):
            return

        for entry in DEMOLITION_FIELDS:
            if isinstance(entry, Section):
                continue
            widget = getattr(self, entry.key, None)
            if not widget:
                continue
            if isinstance(widget, (QDoubleSpinBox, QSpinBox)):
                widget.setValue(widget.minimum())
            elif isinstance(widget, QComboBox):
                widget.setCurrentIndex(0)
            elif hasattr(widget, "clear"):
                widget.clear()
            widget.setStyleSheet("")
        self._on_field_changed()

    def freeze(self, frozen: bool = True):
        freeze_form(DEMOLITION_FIELDS, self, frozen)
        freeze_widgets(frozen, self.btn_load_suggested, self.btn_clear_all)

    def validate(self):
        return validate_form(DEMOLITION_FIELDS, self, warn_rules=DEMOLITION_WARN_RULES)

    def clear_validation(self):
        clear_field_styles(DEMOLITION_FIELDS, self)

    def get_data(self):
        return {"chunk": "demolition_data", "data": self.get_data_dict()}

    def _on_field_changed(self):
        super()._on_field_changed()
        self.created.emit()


