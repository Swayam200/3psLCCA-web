# gui/components/new_project_dialog.py
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QLineEdit,
    QComboBox,
    QDialogButtonBox,
)
from PySide6.QtCore import Qt, Signal, QTimer
from three_ps_lcca_gui.gui.themes import get_token


def _set_combo_error(widget: QComboBox, error: bool):
    """Set or clear a validation error on a QComboBox via dynamic property."""
    widget.setProperty("validationState", get_token("danger") if error else "")
    widget.style().unpolish(widget)
    widget.style().polish(widget)

# 1. UPDATED IMPORT: Added COUNTRY_TO_CURRENCY
from .utils.countries_data import CURRENCIES, COUNTRIES, COUNTRY_TO_CURRENCY


_UNIT_SYSTEMS = [
    ("Metric",          "metric"),
    ("Imperial",   "imperial"),
]


class NewProjectDialog(QDialog):
    """Collect project name, country, currency, and unit system before creating a project."""

    loading_started = Signal(str, str, str, str)  # display_name, country, currency, unit_system

    _LOADING_MSGS = [
        "Preparing project…",
        "Loading modules…",
        "Setting up workspace…",
        "Configuring files…",
        "Almost ready…",
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Project")
        self.setFixedWidth(420)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(24, 24, 24, 24)

        # ── Project Name ──────────────────────────────────────────────────
        layout.addWidget(QLabel("<b>Project Name</b>"))

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g. Highway 5 Bridge Replacement")
        self.name_input.setFixedHeight(34)
        self.name_input.textChanged.connect(
            lambda: self.name_input.setStyleSheet("") if self.name_input.text().strip() else None
        )
        layout.addWidget(self.name_input)

        name_hint = QLabel("You can rename this later.")
        name_hint.setEnabled(False)
        layout.addWidget(name_hint)

        layout.addSpacing(4)

        # ── Country ───────────────────────────────────────────────────────
        layout.addWidget(QLabel("<b>Country</b>"))

        self.country_input = QComboBox()
        self.country_input.setFixedHeight(34)
        self.country_input.addItem("- Select country -", "")
        for country in COUNTRIES:
            self.country_input.addItem(country, country)
        self.country_input.currentIndexChanged.connect(
            lambda: self.country_input.setStyleSheet("") if self.country_input.currentData() else None
        )
        
        # 2. ADDED SIGNAL CONNECTION: Trigger auto-fill when country changes
        self.country_input.currentTextChanged.connect(self._auto_fill_currency)
        
        layout.addWidget(self.country_input)

        country_hint = QLabel("Cannot be changed after project creation.")
        country_hint.setEnabled(False)
        layout.addWidget(country_hint)

        layout.addSpacing(4)

        # ── Currency ──────────────────────────────────────────────────────
        layout.addWidget(QLabel("<b>Currency</b>"))

        self.currency_input = QComboBox()
        self.currency_input.setFixedHeight(34)
        self.currency_input.addItem("- Select currency -", "")
        for code in CURRENCIES:
            self.currency_input.addItem(code, code)
        self.currency_input.setEnabled(False)
        layout.addWidget(self.currency_input)

        currency_hint = QLabel("Auto-filled based on the selected country. Cannot be changed after project creation.")
        currency_hint.setWordWrap(True)
        currency_hint.setEnabled(False)
        layout.addWidget(currency_hint)

        layout.addSpacing(4)

        # ── Unit System ───────────────────────────────────────────────────
        layout.addWidget(QLabel("<b>Unit System</b>"))

        self.unit_system_input = QComboBox()
        self.unit_system_input.setFixedHeight(34)
        for label, value in _UNIT_SYSTEMS:
            self.unit_system_input.addItem(label, value)
        layout.addWidget(self.unit_system_input)

        unit_hint = QLabel("Cannot be changed after project creation.")
        unit_hint.setEnabled(False)
        layout.addWidget(unit_hint)

        layout.addSpacing(8)

        # ── Buttons ───────────────────────────────────────────────────────
        self._btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self._btn_box.accepted.connect(self._on_accept)
        self._btn_box.rejected.connect(self.reject)
        layout.addWidget(self._btn_box)

        self._ok_btn = self._btn_box.button(QDialogButtonBox.Ok)
        self._ok_btn.setText("Create") 
        self._msg_index = 0
        self._msg_timer = QTimer(self)
        self._msg_timer.setInterval(1100)
        self._msg_timer.timeout.connect(self._cycle_message)

        self.name_input.returnPressed.connect(self._on_accept)

    def _on_accept(self):
        name_ok = bool(self.name_input.text().strip())
        country_ok = bool(self.country_input.currentData())
        currency_ok = bool(self.currency_input.currentData())

        self.name_input.setStyleSheet("" if name_ok else f"border: 1.5px solid {get_token('danger')};")
        _set_combo_error(self.country_input, not country_ok)

        if name_ok and country_ok and currency_ok:
            self._lock_inputs()
            self.loading_started.emit(
                self.name_input.text().strip(),
                self.country_input.currentData(),
                self.currency_input.currentData(),
                self.unit_system_input.currentData() or "metric",
            )

    def _lock_inputs(self):
        for w in (self.name_input, self.country_input,
                  self.currency_input, self.unit_system_input):
            w.setEnabled(False)
        cancel = self._btn_box.button(QDialogButtonBox.Cancel)
        if cancel:
            cancel.setEnabled(False)
        self._ok_btn.setEnabled(False)
        self._ok_btn.setText(self._LOADING_MSGS[0])
        self._msg_index = 0
        self._msg_timer.start()

    def _cycle_message(self):
        self._msg_index = (self._msg_index + 1) % len(self._LOADING_MSGS)
        self._ok_btn.setText(self._LOADING_MSGS[self._msg_index])

    def finish_loading(self):
        """Called by project_manager when preloading is done - closes the dialog."""
        self._msg_timer.stop()
        self.accept()

    def get_name(self) -> str:
        return self.name_input.text().strip()

    def get_country(self) -> str:
        return self.country_input.currentData() or ""

    def get_currency(self) -> str:
        return self.currency_input.currentData() or ""

    def get_unit_system(self) -> str:
        return self.unit_system_input.currentData() or "metric"

    # 3. ADDED METHOD: Handle the actual auto-fill logic
    def _auto_fill_currency(self, selected_country: str):
        """Auto-fills the currency combo box based on the country selection."""
        if selected_country in COUNTRY_TO_CURRENCY:
            target_currency = COUNTRY_TO_CURRENCY[selected_country]
            
            idx = self.currency_input.findText(target_currency)
            if idx >= 0:
                self.currency_input.setCurrentIndex(idx)
        else:
            self.currency_input.setCurrentIndex(0)


