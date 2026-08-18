"""
gui/components/base_widget.py

Centralized base for all data-entry panels in the LCCA app.
Handles: field registration, autosave, load-from-engine, signal wiring.
"""

from PySide6.QtWidgets import (
    QWidget,
    QLineEdit,
    QComboBox,
    QDoubleSpinBox,
    QSpinBox,
    QCheckBox,
    QTextEdit,
    QFormLayout,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
)
from PySide6.QtCore import Signal, Qt, QTimer


class BaseDataWidget(QWidget):
    """
    Base class for all data-entry widgets.

    Subclasses only need to:
      1. Call super().__init__(controller=..., chunk_name="...")
      2. Use self.field(key, widget, **options) to create + register each input
      3. Build their layout normally
    """

    data_changed = Signal()

    def __init__(self, controller=None, chunk_name: str = None):
        super().__init__()
        self.controller = controller
        self.chunk_name = chunk_name
        self._field_map = {}  # key -> widget
        self._loading = False
        self._loaded_data: dict = {}  # last data loaded into widgets

        # UI Layout setup.
        # NOTE: self.form is intentionally NOT created here.
        # Subclasses (e.g. ScrollableForm) are responsible for creating self.form
        # on the correct parent widget. Creating it here would produce an orphaned
        # QFormLayout that gets added to the outer VBoxLayout alongside (and hidden
        # behind) the scroll area that ScrollableForm later inserts.
        self.layout = QVBoxLayout(self)
        self.form = None  # set by subclass

        if self.controller:
            # 1. Connect for future project opens - reset loaded state so fresh data is pulled
            if hasattr(self.controller, "project_loaded"):
                self.controller.project_loaded.connect(self._on_project_reloaded)

            # 2. THE FIX: Immediate check for already active projects.
            # This handles widgets inside tabs that are created after the project is loaded.
            if hasattr(self.controller, "engine") and self.controller.engine:
                if self.controller.engine.is_active():
                    # We use a singleShot timer to ensure the UI is fully built
                    # before the first data-population occurs.
                    QTimer.singleShot(0, self.refresh_from_engine)

    # ── PUBLIC API ────────────────────────────────────────────────────────────

    def field(
        self,
        key: str,
        widget: QWidget,
        *,
        default=None,
        placeholder: str = None,
        suffix: str = None,
        decimals: int = None,
        min_val=None,
        max_val=None,
        items: list = None,
    ) -> QWidget:
        """Configure, register, and return a field widget in one call."""
        if placeholder and isinstance(widget, (QLineEdit, QTextEdit)):
            widget.setPlaceholderText(placeholder)

        if suffix and isinstance(widget, (QDoubleSpinBox, QSpinBox)):
            widget.setSuffix(f" {suffix}")

        if decimals is not None and isinstance(widget, QDoubleSpinBox):
            widget.setDecimals(decimals)

        if min_val is not None and isinstance(widget, (QDoubleSpinBox, QSpinBox)):
            widget.setMinimum(min_val)

        if max_val is not None and isinstance(widget, (QDoubleSpinBox, QSpinBox)):
            widget.setMaximum(max_val)

        if items and isinstance(widget, QComboBox):
            widget.addItems(items)

        if default is not None:
            self._apply_value(widget, default)

        # Register
        self._field_map[key] = widget
        self._connect_widget(widget)

        return widget

    def register_field(self, key: str, widget: QWidget) -> QWidget:
        """Back-compat alias for field() without options."""
        self._field_map[key] = widget
        self._connect_widget(widget)
        return widget

    def refresh_from_engine(self):
        """Loads stored data from the engine into widgets - skips if data unchanged."""
        if not self.controller or not self.controller.engine:
            return
        if not self.controller.engine.is_active() or not self.chunk_name:
            return

        data = self.controller.get_chunk(self.chunk_name) or {}
        if data == self._loaded_data:
            return

        self._loaded_data = data
        self.load_data_dict(data)

    def _on_project_reloaded(self):
        """Clear widgets and reload from the new project's engine."""
        self._loaded_data = {}
        self.load_data_dict({})
        self.refresh_from_engine()

    def get_data_dict(self) -> dict:
        """Extracts current widget values into a plain dict for saving."""
        data = {}
        for key, widget in self._field_map.items():
            if isinstance(widget, QLineEdit):
                data[key] = widget.text()
            elif isinstance(widget, QTextEdit):
                data[key] = widget.toPlainText()
            elif isinstance(widget, (QDoubleSpinBox, QSpinBox)):
                data[key] = widget.value()
            elif isinstance(widget, QComboBox):
                data[key] = widget.currentText()
            elif isinstance(widget, QCheckBox):
                data[key] = widget.isChecked()
        return data

    def load_data_dict(self, data: dict):
        """
        Populates widgets from a dict.
        Passing an empty dict clears all fields.
        Blocks all change signals during load to prevent feedback-loop autosaves.
        """
        self._loading = True
        try:
            for key, widget in self._field_map.items():
                widget.blockSignals(True)
                try:
                    self._apply_value(widget, data.get(key, ""))
                finally:
                    widget.blockSignals(False)
        finally:
            self._loading = False

    # ── INTERNALS ─────────────────────────────────────────────────────────────

    def _connect_widget(self, widget: QWidget):
        if isinstance(widget, QLineEdit):
            widget.textChanged.connect(self._on_field_changed)
        elif isinstance(widget, (QDoubleSpinBox, QSpinBox)):
            widget.valueChanged.connect(self._on_field_changed)
        elif isinstance(widget, QComboBox):
            widget.currentIndexChanged.connect(self._on_field_changed)
        elif isinstance(widget, QCheckBox):
            widget.stateChanged.connect(self._on_field_changed)
        elif isinstance(widget, QTextEdit):
            widget.textChanged.connect(self._on_field_changed)

    def _on_field_changed(self):
        """Triggers autosave via the controller when the user edits a field."""
        if self._loading:
            return
        self.data_changed.emit()
        if self.controller and self.chunk_name:
            data = self.get_data_dict()
            self._loaded_data = data
            self.controller.save_chunk_data(self.chunk_name, data)

    @staticmethod
    def _apply_value(widget: QWidget, val):
        """Write a value to any supported widget type."""
        try:
            if isinstance(widget, QLineEdit):
                widget.setText(str(val))
            elif isinstance(widget, QTextEdit):
                widget.setPlainText(str(val))
            elif isinstance(widget, (QDoubleSpinBox, QSpinBox)):
                widget.setValue(float(val))
            elif isinstance(widget, QComboBox):
                idx = widget.findText(str(val))
                if idx >= 0:
                    widget.setCurrentIndex(idx)
            elif isinstance(widget, QCheckBox):
                widget.setChecked(bool(val))
        except (ValueError, TypeError):
            pass  # Handle incompatible data types gracefully


# ── SCROLLABLE FORM ───────────────────────────────────────────────────────────


class ScrollableForm(BaseDataWidget):
    """
    A BaseDataWidget that wraps its content in a QScrollArea and exposes
    a QFormLayout (self.form) for adding labelled rows.
    """

    def __init__(self, controller=None, chunk_name: str = None):
        super().__init__(controller=controller, chunk_name=chunk_name)

        self._content = QWidget()
        # Fixed vertical policy: _content never grows beyond its sizeHint.
        # Preferred/Minimum still allow the scroll area to push extra height
        # into the QFormLayout rows, producing visible gaps between fields.
        # Ignored horizontal policy: qSmartMinSize() skips minimumSizeHint() for
        # the horizontal axis entirely, so no child's minimum width can force the
        # scroll area to make _content wider than the viewport.
        self._content.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)

        self.form = QFormLayout(self._content)
        self.form.setContentsMargins(24, 20, 24, 20)
        self.form.setSpacing(12)
        self.form.setLabelAlignment(Qt.AlignRight)
        # Stop QFormLayout distributing leftover vertical space into rows.
        # build_form() wraps every field in a single-column QWidget row -
        # without this, those rows absorb extra height as padding gaps.
        self.form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.form.setRowWrapPolicy(QFormLayout.DontWrapRows)

        # Wrap in scroll area.
        # No QSS - use palette propagation instead.
        # Setting WA_TranslucentBackground + autoFillBackground=False on both
        # the content widget and the scroll viewport tells Qt to skip painting
        # any background of their own and let the parent's Window colour show
        # through uniformly in both light and dark themes.
        scroll = QScrollArea()
        scroll.setWidget(self._content)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        for w in (scroll, scroll.viewport(), self._content):
            w.setAutoFillBackground(False)
            w.setAttribute(Qt.WA_TranslucentBackground)

        # self.layout is always created by BaseDataWidget.__init__.
        # We simply add the scroll area to it - no orphan QFormLayout exists
        # anymore because BaseDataWidget no longer creates one.
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.addWidget(scroll)


