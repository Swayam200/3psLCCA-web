from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QWidget,
)

from ....base_widget import ScrollableForm
from ....utils.form_builder.form_definitions import FieldDef, Section
from ....utils.form_builder.form_builder import build_form
from ....utils.display_format import DECIMAL_PLACES
from ....utils.validation_helpers import freeze_form, validate_form, clear_field_styles, confirm_clear_all
from ....utils.common_requested_data import get_currency

CUSTOM_FIELDS: list[FieldDef | Section] = [
    FieldDef(
        "scc_value",
        "Social Cost of Carbon (SCC)",
        "The financial cost attributed to 1 kg of CO₂e emissions.",
        "float",
        options=(0.0, 1e6, DECIMAL_PLACES),
        unit="(Currency/kgCO₂e)",
        warn=(
            0.0001,
            None,
            "Social Cost of Carbon is 0 - no carbon pricing will be applied to emissions; enter a positive custom SCC value in the field above",
        ),
    ),
    FieldDef("source", "Source", "Reference or basis for this SCC value (e.g. government report, paper, agency guideline).", "text"),
    FieldDef("comments", "Comments", "Any additional notes or justification for the chosen SCC value.", "textarea"),
]


class CustomWidget(ScrollableForm):
    def __init__(self, controller=None):
        super().__init__(controller=controller, chunk_name=None)
        build_form(self, CUSTOM_FIELDS)
        self._update_currency_suffix()

        btn_row = QWidget()
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 10, 0, 10)
        self._btn_clear = QPushButton("Clear All")
        self._btn_clear.setMinimumHeight(35)
        self._btn_clear.clicked.connect(self._clear_all)
        btn_layout.addWidget(self._btn_clear)
        self.form.addRow(btn_row)

    def _update_currency_suffix(self):
        widget = self._field_map.get("scc_value")
        if isinstance(widget, QDoubleSpinBox):
            currency = get_currency()
            widget.setSuffix(f" {currency}/kgCO₂e")

    def _clear_all(self):
        if not confirm_clear_all(self):
            return
        for widget in self._field_map.values():
            if isinstance(widget, QComboBox):
                widget.setCurrentIndex(0)
            elif isinstance(widget, QDoubleSpinBox):
                widget.setValue(widget.minimum())
            elif isinstance(widget, QSpinBox):
                widget.setValue(widget.minimum())
            elif isinstance(widget, (QLineEdit, QTextEdit)):
                widget.clear()
            elif isinstance(widget, QCheckBox):
                widget.setChecked(False)

    def freeze(self, frozen: bool = True):
        freeze_form(CUSTOM_FIELDS, self, frozen)
        self._btn_clear.setEnabled(not frozen)

    def validate(self):
        return validate_form(CUSTOM_FIELDS, self)

    def clear_validation(self):
        clear_field_styles(CUSTOM_FIELDS, self)

    def refresh_from_engine(self):
        self._update_currency_suffix()

    def get_cost(self) -> float | None:
        return self._field_map["scc_value"].value() if "scc_value" in self._field_map else None

    def get_custom_data(self) -> dict:
        value = self._field_map["scc_value"].value() if "scc_value" in self._field_map else 0.0
        currency = get_currency()
        return {
            "entered_value": value,
            "currency": currency,
            "unit": f"{currency}/kgCO₂e",
            "source": self._field_map["source"].text() if "source" in self._field_map else "",
            "comments": self._field_map["comments"].toPlainText() if "comments" in self._field_map else "",
        }

    def get_result_data(self, selected_mode: str) -> dict:
        cost = self.get_cost()
        currency = get_currency()
        return {
            "selected_mode": selected_mode,
            "cost_of_carbon_local": cost if cost is not None else 0.0,
            "currency": currency,
            "unit": f"{currency}/kgCO₂e",
        }
