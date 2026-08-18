"""
gui/components/utils/validation_helpers.py

Shared helpers for form validation across all data-entry pages.

Usage pattern
-------------
Simple page (only build_form() fields):
    def validate(self):
        return validate_form(MY_FIELDS, self)

Page with warning thresholds:
    def validate(self):
        return validate_form(MY_FIELDS, self, warn_rules=WARNING_RULES)

Page with extra validation (tables, custom widgets, etc.):
    def validate(self):
        result = validate_form(MY_FIELDS, self)
        extra_errors = self._validate_my_table()
        if extra_errors:
            result["errors"].extend(extra_errors)
        return result

Caller checks success as:
    result = page.validate()
    if not result["errors"] and not result["warnings"]:
        # all good

Standard validation flow
------------------------
1. Clear styles       - reset all visual state before re-validating
2. Required checks    - is the field filled at all?         → result["errors"]
3. Range/warn checks  - is the value plausible?             → result["warnings"]
                        (skips fields already in errors)
                        (skips optional fields with no value)
4. Cross-field checks - handled externally by the caller via the extra-validation pattern
5. Return             - {"errors": [...], "warnings": [...]}

Each layer only runs on fields that passed the previous layer:
    required=True,  empty        → error   (stops here, warn skipped)
    required=False, empty        → skip    (neither error nor warning)
    required=any,   value present, in range  → ok
    required=any,   value present, out of range → warning
"""

from PySide6.QtCore import QEvent, QObject, QPoint, QRect, Qt, QTimer
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QApplication,
    QAbstractButton,
    QAbstractSpinBox,
    QComboBox,
    QLineEdit,
    QMessageBox,
    QTextEdit,
    QToolTip,
    QWidget,
)

from .form_builder.form_definitions import FieldDef
from three_ps_lcca_gui.gui.themes import get_token


# ── Style helpers ─────────────────────────────────────────────────────────────


def _apply_border_style(widget, color: str):
    """
    Apply a coloured validation border without clobbering the app QSS.

    QComboBox / QAbstractSpinBox: widget-level stylesheets (even scoped ones)
    override the entire app QSS block for that widget, losing complex styling
    (drop-down buttons, up/down arrows). Instead we set a dynamic property
    and let main.qss handle the border via a ``[validationState="..."]`` selector.

    All other widgets: a bare ``border:`` inline rule only overrides the border
    property and leaves the rest of the app QSS intact.
    """
    state = ""
    if color == get_token("danger"):
        state = "error"
    elif color == get_token("warning"):
        state = "warning"

    if isinstance(widget, (QComboBox, QAbstractSpinBox)):
        widget.setProperty("validationState", state)
        widget.style().unpolish(widget)
        widget.style().polish(widget)
    else:
        widget.setStyleSheet(f"border: 1px solid {color};")


def _clear_border_style(widget):
    """Clear a validation border set by ``_apply_border_style``."""
    if isinstance(widget, (QComboBox, QAbstractSpinBox)):
        widget.setProperty("validationState", "")
        widget.style().unpolish(widget)
        widget.style().polish(widget)
    else:
        widget.setStyleSheet("")


# ── Field helpers ─────────────────────────────────────────────────────────────


def field_title(key: str, fields: list) -> str:
    """Return the human-readable title for a field key, falling back to the key."""
    return next(
        (f.title for f in fields if isinstance(f, FieldDef) and f.key == key),
        key,
    )


def _is_required(key: str, fields: list) -> bool:
    """Return True if the field with this key is marked required."""
    return any(
        isinstance(f, FieldDef) and f.key == key and f.required
        for f in fields
    )


def clear_field_styles(fields: list, widget_owner, skip_keys: set = None):
    """Clear validation border styles from all FieldDef widgets."""
    skip = skip_keys or set()
    for f in fields:
        if not isinstance(f, FieldDef) or f.key in skip:
            continue
        widget = getattr(widget_owner, f.key, None)
        if widget:
            _clear_border_style(widget)


def confirm_clear_all(parent: QWidget) -> bool:
    """Show a standardized confirmation dialog for 'Clear All' actions.
    Returns True if the user confirmed, False otherwise.
    """
    reply = QMessageBox.question(
        parent,
        "Clear All Data",
        "This will reset all fields on this page to their default values. "
        "This action cannot be undone.\n\nContinue?",
        QMessageBox.Yes | QMessageBox.No,
        QMessageBox.No,
    )
    return reply == QMessageBox.Yes


# ── Centralised form validation ───────────────────────────────────────────────


def validate_form(
    fields: list,
    widget_owner,
    warn_rules: dict = None,
    skip_keys: set = None,
) -> dict:
    """
    Standard validation for fields generated by build_form().

    Returns
    -------
    {"errors": [str, ...], "warnings": [str, ...]}
        Both lists empty → validation passed.
        Caller checks: if not result["errors"] and not result["warnings"]
    """
    # ── Step 1: Clear styles ──────────────────────────────────────────────────
    clear_field_styles(fields, widget_owner, skip_keys=skip_keys)
    skip = skip_keys or set()

    # ── Step 2: Required checks ───────────────────────────────────────────────
    errors: list[str] = []
    error_keys: set[str] = set()

    for f in fields:
        if not isinstance(f, FieldDef) or not f.required or f.key in skip:
            continue
        widget = getattr(widget_owner, f.key, None)
        if widget is None:
            errors.append(f"'{f.title}' is required but the input field was not found")
            error_keys.add(f.key)
            continue
        if isinstance(widget, QLineEdit) and not widget.text().strip():
            _apply_border_style(widget, get_token("danger"))
            errors.append(f"'{f.title}' is required - the field cannot be left empty")
            error_keys.add(f.key)
        elif (isinstance(widget, QAbstractSpinBox)
              and f.default is not None
              and widget.value() == widget.minimum()):
            # Spinbox with an explicit default uses the minimum as the "blank" sentinel.
            # If still at minimum it has never been filled - treat as a required error.
            _apply_border_style(widget, get_token("danger"))
            errors.append(f"'{f.title}' is required - enter a value above the minimum")
            error_keys.add(f.key)
        elif isinstance(widget, QComboBox):
            placeholder = f.combo_placeholder if f.combo_placeholder is not None else "-- select --"
            if widget.currentText() == placeholder:
                _apply_border_style(widget, get_token("danger"))
                errors.append(f"'{f.title}' is required - please select an option")
                error_keys.add(f.key)
        # QSpinBox/QDoubleSpinBox without default: 0 is a valid value - use warn_rules
        # QComboBox: always has a selection - no check needed

    # ── Step 3: Range/warn checks ─────────────────────────────────────────────
    # Behaviour by case:
    #   required=True,  failed → in error_keys → skip (keep red)
    #   required=False, empty  → val == 0, not required → skip (no style)
    #   any,            value present → evaluate range normally
    warnings: list[str] = []

    # Merge warn rules: FieldDef.warn takes base, explicit warn_rules override
    effective_warn: dict = {
        f.key: f.warn
        for f in fields
        if isinstance(f, FieldDef) and f.warn is not None
    }
    effective_warn.update(warn_rules or {})

    for key, rule in effective_warn.items():
        low, high = rule[0], rule[1]
        low_msg  = rule[2] if len(rule) > 2 else None
        high_msg = rule[3] if len(rule) > 3 else low_msg  # fall back to low_msg if only one given

        if key in error_keys:
            # Required check already failed - keep red, do not overwrite with orange
            continue
        widget = getattr(widget_owner, key, None)
        if not widget:
            continue
        if not isinstance(widget, QAbstractSpinBox):
            # warn_rules are range checks - only valid for numeric widgets.
            # Skip silently to avoid AttributeError on .value()
            continue
        val = widget.value()

        too_low  = low  is not None and val < low
        too_high = high is not None and val > high

        if too_low:
            label = low_msg if low_msg else f"{field_title(key, fields)} has an unusual value of {val} - please verify"
            warnings.append(label)
            _apply_border_style(widget, get_token("warning"))
        elif too_high:
            label = high_msg if high_msg else f"{field_title(key, fields)} has an unusual value of {val} - please verify"
            warnings.append(label)
            _apply_border_style(widget, get_token("warning"))
        else:
            _clear_border_style(widget)  # passed both checks - clear any stale style

    # ── Step 4 (caller's responsibility): cross-field checks ──────────────────
    # See module docstring for the extra-validation pattern.
    res = {"errors": errors, "warnings": warnings}
    # print(res)
    return res


# ── Form freeze / unfreeze ────────────────────────────────────────────────────


LOCK_TOOLTIP = "Project is locked - click Unlock in the toolbar to edit."


class _LockEventFilter(QObject):
    """Blocks input events on frozen widgets and shows a native tooltip on the Lock button."""

    _TRIGGER = {
        QEvent.Type.MouseButtonPress,
        QEvent.Type.MouseButtonDblClick,
        QEvent.Type.Wheel,
        QEvent.Type.KeyPress,
        QEvent.Type.Enter,
        QEvent.Type.Leave,
    }
    _TOOLTIP_TRIGGER = {
        QEvent.Type.MouseButtonPress,
        QEvent.Type.MouseButtonDblClick,
        QEvent.Type.KeyPress,
        QEvent.Type.Enter,
    }
    _TOOLTIP_MS  = 1200  # how long the tooltip stays visible
    _THROTTLE_MS = 1200  # min gap between successive shows

    def __init__(self, parent=None):
        super().__init__(parent)
        self.target_widget = None

        # 200 ms delay ensures MouseButtonRelease and all related Qt events
        # are fully processed before showText fires, so nothing hides it.
        self._show_timer = QTimer(self)
        self._show_timer.setSingleShot(True)
        self._show_timer.setInterval(200)
        self._show_timer.timeout.connect(self._show_tooltip)

        # Throttle gate: starts after tooltip is shown; suppresses re-shows
        # while it is still visible.
        self._throttle = QTimer(self)
        self._throttle.setSingleShot(True)

    def _show_tooltip(self):
        if self.target_widget is None:
            return
        w = self.target_widget
        pos = w.mapToGlobal(QPoint(w.width() // 2, w.height() + 4))
        QToolTip.showText(pos, "This project is locked.\nClick here to unlock and enable editing.",
                          None, QRect(), self._TOOLTIP_MS)
        self._throttle.start(self._THROTTLE_MS)

    def eventFilter(self, obj, event):
        if event.type() not in self._TRIGGER:
            return super().eventFilter(obj, event)

        # Wheel: only block on value-changing widgets so page scrolling works.
        if event.type() == QEvent.Type.Wheel:
            if not isinstance(obj, (QAbstractSpinBox, QComboBox)):
                return super().eventFilter(obj, event)

        if (
            self.target_widget is not None
            and event.type() in self._TOOLTIP_TRIGGER
            and not self._throttle.isActive()
        ):
            # Debounce: rapid clicks restart the timer, collapsing into one show.
            self._show_timer.start()

        # Enter: set override cursor so Qt's internal IBeam/Arrow can't override it.
        if event.type() == QEvent.Type.Enter:
            QApplication.setOverrideCursor(QCursor(Qt.CursorShape.ForbiddenCursor))
            return super().eventFilter(obj, event)

        # Leave: restore cursor.
        if event.type() == QEvent.Type.Leave:
            QApplication.restoreOverrideCursor()
            return super().eventFilter(obj, event)

        return True  # consume - prevent any accidental change


# Module-level singleton - one filter object serves every frozen widget.
_lock_filter = _LockEventFilter()


def set_lock_tooltip_target(widget) -> None:
    """
    Register the Lock button so the filter can point users to it.
    Call with the button when locking, None when unlocking.
    """
    _lock_filter.target_widget = widget


def freeze_form(
    fields: list,
    widget_owner,
    frozen: bool = True,
    skip_keys: set = None,
) -> None:
    """
    Make all FieldDef widgets in *fields* non-editable (frozen=True) or
    restore them to editable (frozen=False).

    Widget behaviour:
        QLineEdit / QTextEdit      → setReadOnly  (value stays visible)
        QAbstractSpinBox           → setReadOnly  (value stays visible)
        QComboBox                  → setEnabled   (no readOnly equivalent)

    All affected widgets receive the lock tooltip and event filter when frozen
    so the tooltip fires immediately on any interaction attempt.
    """
    skip = skip_keys or set()
    for f in fields:
        if not isinstance(f, FieldDef) or f.key in skip:
            continue
        widget = getattr(widget_owner, f.key, None)
        if widget is None:
            continue
        if frozen:
            widget.setToolTip(LOCK_TOOLTIP)
            widget.installEventFilter(_lock_filter)
            widget.setProperty("frozen", "true")
            widget.style().unpolish(widget)
            widget.style().polish(widget)
        else:
            widget.removeEventFilter(_lock_filter)
            widget.setToolTip("")
            widget.setProperty("frozen", "")
            widget.style().unpolish(widget)
            widget.style().polish(widget)
        if isinstance(widget, (QLineEdit, QTextEdit)):
            widget.setReadOnly(frozen)
        elif isinstance(widget, QAbstractSpinBox):
            widget.setReadOnly(frozen)


def freeze_widgets(frozen: bool, *widgets) -> None:
    """Freeze/unfreeze arbitrary non-FieldDef widgets (buttons, tables, etc.).

    Buttons (QAbstractButton) stay enabled when frozen so mouse events reach
    the event filter, which consumes the click and shows the lock tooltip.
    All other widgets are disabled as before.

        def freeze(self, frozen: bool = True):
            freeze_form(MY_FIELDS, self, frozen)
            freeze_widgets(frozen, self.btn_clear_all, self.btn_load_suggested)
    """
    for w in widgets:
        if w is None:
            continue
        if frozen:
            w.setToolTip(LOCK_TOOLTIP)
            w.installEventFilter(_lock_filter)
            if isinstance(w, QAbstractButton):
                # Keep enabled - disabled buttons don't receive mouse events
                # so the filter can't show the tooltip. Use a forbidden cursor
                # as the visual "locked" cue instead.
                w.setCursor(QCursor(Qt.CursorShape.ForbiddenCursor))
            else:
                w.setEnabled(False)
        else:
            w.setToolTip("")
            w.removeEventFilter(_lock_filter)
            if isinstance(w, QAbstractButton):
                w.unsetCursor()
            else:
                w.setEnabled(True)


