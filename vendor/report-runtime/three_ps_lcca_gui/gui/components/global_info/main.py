# """
# gui\components\global_info\main.py
# """

from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QWidget,
)
from PySide6.QtCore import Signal
from PySide6.QtGui import QPixmap

from ..base_widget import ScrollableForm
from ..utils.form_builder.form_definitions import FieldDef, Section
from ..utils.form_builder.form_builder import build_form, _IMG_PREVIEWS_ATTR, freeze_img_uploads
from ..utils.validation_helpers import clear_field_styles, freeze_form, freeze_widgets, validate_form, confirm_clear_all
from ..utils.countries_data import CURRENCIES, COUNTRIES


GENERAL_FIELDS = []

PROJECT_INFO_FIELDS = [
    # ── Project Information ──────────────────────────────────────────────
    Section("Project Information"),
    FieldDef(
        "project_name",
        "Project Name",
        "",
        "text",
        required=True,
    ),
    FieldDef(
        "project_code",
        "Project Code",
        "",
        "text",
    ),
    FieldDef(
        "project_description",
        "Project Description",
        "",
        "textarea",
        placeholder_text="A free-text summary of the project scope, objectives, and context."
        
    ),
    FieldDef(
        "remarks",
        "Remarks",
        "",
        "textarea",
        placeholder_text="Additional notes or observations. Does not affect any calculations."
    ),
]

AGENCY_FIELDS = [
    Section("Assessing Organisation"),
    FieldDef(
        "contact_person",
        "Assessor's Name",
        "",
        "text",
    ),
    FieldDef(
        "agency_logo",
        "Organisation's Logo",
        "[Appears on the report cover page. Must be a JPG or PNG image.]",
        "upload_img",
        options="default",
    ),
    FieldDef(
        "agency_name",
        "Organisation's Name",
        "",
        "text",
        # required=True,
    ),
    FieldDef(
        "agency_address",
        "Organisation's Address",
        "[Appears in the report footer.]",
        "text",
    ),
    FieldDef(
        "agency_country",
        "Country",
        "[Country where the evaluating agency is based. Used for report localisation.]",
        "combo",
        options=COUNTRIES,
    ),
    FieldDef(
        "agency_email",
        "Email",
        "",
        "text",
    ),
    FieldDef(
        "agency_phone",
        "Phone",
        "",
        "phone",
    ),
]

REVIEWER_FIELDS = [
    Section("Reviewer"),
    FieldDef(
        "reviewer_name",
        "Reviewer's Name",
        "",
        "text",
    ),
    FieldDef(
        "reviewer_organization",
        "Reviewer's Organisation",
        "",
        "text",
    ),
    FieldDef(
        "reviewer_address",
        "Reviewer's Address",
        "",
        "text",
    ),
    FieldDef(
        "agency_country",
        "Country",
        "Country where the reviewing agency is located.",
        "combo",
        options=COUNTRIES,
    ),
    FieldDef(
        "reviewer_email",
        "Email",
        "",
        "text",
    ),
    FieldDef(
        "reviewer_phone",
        "Phone",
        "",
        "phone",
    ),
]

GENERAL_FIELDS = PROJECT_INFO_FIELDS + AGENCY_FIELDS + REVIEWER_FIELDS + [
    # ── Project Settings ─────────────────────────────────────────────────
    Section("Project Settings"),
    FieldDef(
        "project_country",
        "Country",
        "Country where the bridge project is located. Set at project creation.",
        "text",
    ),
    FieldDef(
        "project_currency",
        "Currency",
        "Currency used for all cost inputs and outputs. Set at project creation.",
        "text",
    ),
    FieldDef(
        "unit_system",
        "Unit System",
        "Measurement system for all dimensional inputs (Metric or Imperial). Set at project creation.",
        "text",
        doc_slug=["general", "unit-system"],
    ),
    FieldDef(
        "sor_database",
        "Material Suggestions",
        "Schedule of Rates database used to auto-suggest material names and rates in the Material Dialog.",
        "combo",
        options=[],
        doc_slug=["general", "sor-database"],
    ),
]


class GeneralInfo(ScrollableForm):

    created = Signal()

    _LOCKED = {"project_country", "project_currency", "unit_system"}
    # sor_database is editable but should not be wiped by Clear All
    _SKIP_CLEAR = _LOCKED | {"sor_database"}

    def __init__(self, controller=None):
        super().__init__(controller=controller, chunk_name="general_info")

        self.required_keys = build_form(self, GENERAL_FIELDS)

        # Lock country and currency - disable widget so user can't edit,
        # but keep in _field_map so get_data_dict() saves them normally
        self.required_keys = [
            k for k in self.required_keys if k not in self._LOCKED]
        for key in self._LOCKED:
            w = getattr(self, key, None)
            if w is not None:
                w.setEnabled(False)

        # ── Clear All button ─────────────────────────────────────────────
        btn_row = QWidget()
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 10, 0, 10)

        self.btn_clear_all = QPushButton("Clear All")
        self.btn_clear_all.setMinimumHeight(35)
        self.btn_clear_all.clicked.connect(self.clear_all)

        btn_layout.addWidget(self.btn_clear_all)
        self.form.addRow(btn_row)

        # ── Load Profile button inline with Assessing Organization header ──
        self.btn_load_profile = QPushButton("Load Agency Profile")
        self.btn_load_profile.setMinimumHeight(28)
        self.btn_load_profile.clicked.connect(self._load_agency_profile_dialog)

        from PySide6.QtWidgets import QFormLayout
        for i in range(self.form.rowCount()):
            item = self.form.itemAt(i, QFormLayout.SpanningRole)
            if item and item.widget():
                w = item.widget()
                if isinstance(w, QLabel) and "Assessing Organisation" in w.text():
                    self.form.takeRow(i)
                    header_row = QWidget()
                    lay = QHBoxLayout(header_row)
                    lay.setContentsMargins(0, 0, 0, 0)
                    lay.setSpacing(8)
                    lay.addWidget(w)
                    lay.addStretch()
                    lay.addWidget(self.btn_load_profile)
                    self.form.insertRow(i, header_row)
                    break

    def _load_agency_profile_dialog(self):
        import os
        import json
        from PySide6.QtWidgets import QInputDialog, QMessageBox

        dir_path = os.path.join("data", "user_db")
        file_path = os.path.join(dir_path, "profile.json")

        profiles = {}
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    if content.strip():
                        profiles = json.loads(content)
            except Exception:
                pass

        if not profiles:
            QMessageBox.information(
                self, "No Profiles", "No saved agency profiles found.")
            return

        profile_names = list(profiles.keys())
        item, ok = QInputDialog.getItem(
            self, "Load Profile", "Select a profile to load:", profile_names, 0, False
        )
        if ok and item:
            data = profiles[item]
            # Preserve current form data for non-agency fields
            current_data = self.get_data_dict()
            current_data.update(data)
            self.load_data_dict(current_data)

    # ── Clear All ────────────────────────────────────────────────────────
    def clear_all(self):
        if not confirm_clear_all(self):
            return

        for entry in GENERAL_FIELDS:
            if isinstance(entry, Section):
                continue
            if entry.key in self._SKIP_CLEAR:
                continue  # never clear locked or settings fields

            widget = getattr(self, entry.key, None)
            if widget is None:
                continue

            if isinstance(widget, QLineEdit):
                widget.clear()
            elif isinstance(widget, QTextEdit):
                widget.clear()
            elif isinstance(widget, QComboBox):
                widget.setCurrentIndex(0)
            elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                widget.setValue(widget.minimum())

        # Reset all upload_img previews
        for key, preview in getattr(self, _IMG_PREVIEWS_ATTR, {}).items():
            preview.setPixmap(QPixmap())
            preview.setText("No image selected")

        self._on_field_changed()

    # ── Validation ───────────────────────────────────────────────────────
    def freeze(self, frozen: bool = True):
        freeze_form(GENERAL_FIELDS, self, frozen)
        freeze_img_uploads(self, GENERAL_FIELDS, frozen)
        freeze_widgets(frozen, self.btn_clear_all, self.btn_load_profile)

    def clear_validation(self):
        clear_field_styles(GENERAL_FIELDS, self)

    def validate(self):
        return validate_form(GENERAL_FIELDS, self)

    _UNIT_SYSTEM_LABELS = {
        "metric":   "Metric",
        "imperial": "Imperial",
    }

    def load_data_dict(self, data: dict):
        raw = data.get("unit_system", "metric")
        display = self._UNIT_SYSTEM_LABELS.get(raw, raw)
        data = {**data, "unit_system": display}
        super().load_data_dict(data)

        # Populate SOR combo based on project country (country is now loaded)
        country = data.get("project_country", "")
        saved_key = data.get("sor_database", "")
        self._populate_sor_combo(country, saved_key)

    def _populate_sor_combo(self, country: str, saved_key: str = "") -> None:
        """Fill the Material Suggestions combo from the registry for *country*."""
        try:
            from ..structure.widgets.material_dialog import _list_sor_options
            options = _list_sor_options(country)
        except Exception:
            options = []

        cb = getattr(self, "sor_database", None)
        if cb is None:
            return

        cb.blockSignals(True)
        cb.clear()
        for opt in options:
            cb.addItem(opt["label"], opt["db_key"])
        cb.addItem("- No suggestions -", "")

        idx = cb.findData(saved_key) if saved_key else -1
        # default → "- No suggestions -"
        cb.setCurrentIndex(idx if idx >= 0 else cb.count() - 1)

        cb.setEnabled(bool(options))
        cb.blockSignals(False)

    def get_data_dict(self) -> dict:
        data = super().get_data_dict()
        cb = getattr(self, "sor_database", None)
        if cb is not None:
            data["sor_database"] = cb.currentData() or ""
        return data

    def get_data(self) -> dict:
        return {"chunk": "general_info", "data": self.get_data_dict()}

    def _on_field_changed(self):
        super()._on_field_changed()
        self.created.emit()
