from PySide6.QtWidgets import QFormLayout, QStackedWidget, QWidget

from three_ps_lcca_gui.gui._CONFIG import DEV_MODE
from ...base_widget import BaseDataWidget
from ...utils.form_builder.form_definitions import FieldDef
from ...utils.form_builder.form_builder import build_form
from ...utils.validation_helpers import freeze_form, clear_field_styles
from .scc_tabs.ricke import RickeWidget
from .scc_tabs.custom import CustomWidget

_SELECTOR_LABELS = ["K. Ricke et al. (Country-Level)", "Custom / Manual Override"]

_SELECTOR_FIELDS = [
    FieldDef("selector", "Mode", "", "combo", options=_SELECTOR_LABELS, combo_placeholder=""),
]

_KEYS = ["ricke", "custom"]


class SCCWidget(BaseDataWidget):
    def __init__(self, controller=None):
        super().__init__(controller=controller, chunk_name="social_cost_data")

        # ── selector form (header) ─────────────────────────────────────────────
        header = QWidget()
        self.form = QFormLayout(header)
        self.form.setContentsMargins(24, 12, 24, 4)
        self.form.setSpacing(8)
        build_form(self, _SELECTOR_FIELDS)

        # ── stacked content ────────────────────────────────────────────────────
        self._stack = QStackedWidget()
        self._sub_a = RickeWidget(controller=None)
        self._sub_b = CustomWidget(controller=None)
        self._stack.addWidget(self._sub_a)  # index 0
        self._stack.addWidget(self._sub_b)  # index 1

        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        self.layout.addWidget(header)
        self.layout.addWidget(self._stack)

        self._field_map["selector"].currentIndexChanged.connect(self._stack.setCurrentIndex)

        # propagate sub-widget changes up so SCCWidget autosaves the full nested chunk
        self._sub_a.data_changed.connect(self._on_field_changed)
        self._sub_b.data_changed.connect(self._on_field_changed)

    def _active(self):
        return self._stack.currentWidget()

    def freeze(self, frozen: bool = True):
        freeze_form(_SELECTOR_FIELDS, self, frozen)
        for sub in (self._sub_a, self._sub_b):
            sub.freeze(frozen)

    def validate(self) -> dict:
        result = self._active().validate()
        if isinstance(result, dict):
            return result
        return {"errors": [], "warnings": []}

    def clear_validation(self):
        clear_field_styles(_SELECTOR_FIELDS, self)
        self._sub_a.clear_validation()
        self._sub_b.clear_validation()

    def get_data_dict(self) -> dict:
        if self.controller and self.controller.engine and self.controller.engine.is_active():
            chunk = dict(self.controller.get_chunk(self.chunk_name) or {})
        else:
            chunk = {}

        idx = self._field_map["selector"].currentIndex()
        label = _SELECTOR_LABELS[idx]
        chunk["source"] = label

        if idx == 0:
            chunk["ricke"] = self._sub_a.get_ricke_data()
            chunk["result"] = self._sub_a.get_result_data(label)
        else:
            chunk["custom"] = self._sub_b.get_custom_data()
            chunk["result"] = self._sub_b.get_result_data(label)

        return chunk

    def get_data(self) -> dict:
        chunk = {"chunk": "social_cost_data", "data": self.get_data_dict()}
        if DEV_MODE:
            print(f"[SCCWidget] storing chunk: {chunk}")
        return chunk

    def load_data(self, data: dict):
        self._loading = True
        try:
            source = data.get("source") or data.get("mode", "ricke")
            if source in _SELECTOR_LABELS:
                idx = _SELECTOR_LABELS.index(source)
            elif source in _KEYS:
                idx = _KEYS.index(source)
            else:
                idx = 0
            self._field_map["selector"].setCurrentIndex(idx)
            self._sub_a.load_data_dict(data.get("ricke", {}))
            custom_data = data.get("custom", {})
            if "entered_value" in custom_data and "scc_value" not in custom_data:
                custom_data = {"scc_value": custom_data["entered_value"]}
            self._sub_b.load_data_dict(custom_data)
        finally:
            self._loading = False

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
        self._sub_a.refresh_from_engine()
        self._sub_b.refresh_from_engine()
