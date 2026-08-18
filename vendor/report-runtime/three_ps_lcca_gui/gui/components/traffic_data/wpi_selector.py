"""
gui/components/traffic_data/wpi_selector.py

_WPISelector - profile selector bar for WPI adjustment ratio profiles.

Layout:
    [Profile: ▾ combo] [✅/⚠/❌] [+ New] [✎ Save As] [🗑 Delete]

Signals:
    profile_selected(WPIProfile)   - user picked a profile from combo
    profile_saved(WPIProfile)      - user saved a custom profile
    profile_deleted(str)           - user deleted a profile (id)
    edit_requested()               - user wants to edit current profile
"""

from __future__ import annotations

from typing import Optional

from three_ps_lcca_gui.gui.themes import get_token, theme_manager
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QScreen
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QCheckBox,
    QScrollArea,
)
from ..utils.wpi_manager import (
    WPIManager, WPIProfile, IntegrityState, empty_data,
    save_to_user_library, delete_from_user_library,
)
import datetime
import json

# ── Dev mode ──────────────────────────────────────────────────────────────────

DEV = False # Set to True to print JSON data on add/edit

# ── Integrity badge ───────────────────────────────────────────────────────────
# Store token keys, not resolved colors- colors are fetched live in _update_badge

_BADGE = {
    IntegrityState.OK:       ("✅", "success", "Integrity verified"),
    IntegrityState.MISMATCH: ("⚠",  "danger",  "Hash mismatch - data may be tampered"),
    IntegrityState.MISSING:  ("❓", "warning", "No hash - unverified profile"),
}


# ── WPI Editor Dialog ─────────────────────────────────────────────────────────

class _WPIEditorDialog(QDialog):
    """
    Unified dialog for creating/cloning or editing profiles.
    Contains metadata fields and an integrated _WPITable.
    """

    def __init__(self, manager: WPIManager, profile: Optional[WPIProfile] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("WPI Profile Editor")
        self.setMinimumWidth(900)

        from PySide6.QtWidgets import QApplication
        screen = QApplication.primaryScreen().availableGeometry()
        max_h = int(screen.height() * 0.90)
        self.setMaximumHeight(max_h)
        self.resize(900, min(780, max_h))
        
        self._manager = manager
        self._is_new = profile is None
        self._result_profile: Optional[WPIProfile] = None

        if self._is_new:
            # Default for adding new
            self._profile = WPIProfile(
                id="", name=self._manager.suggest_custom_name("custom"),
                year=datetime.datetime.now().year, is_custom=True,
                remark="", hash="", data=empty_data(), is_shared=True
            )
        else:
            # Edit a copy
            import json as _json
            self._profile = WPIProfile(
                id=profile.id, name=profile.name, year=profile.year,
                is_custom=True, remark=profile.remark, hash=profile.hash,
                data=_json.loads(_json.dumps(profile.data)),
                is_shared=profile.is_shared
            )

        self._build_ui()
        self._load_meta()

        if self._is_new:
            self._on_template_changed() # load initial scratch
        else:
            self._table.load_from_data(self._profile.data)

    def _build_ui(self):
        from .wpi_table import _WPITable
        layout = QVBoxLayout(self)

        # ── Header: Metadata ──────────────────────────────────────────────────
        meta_group = QWidget()
        meta_layout = QFormLayout(meta_group)
        meta_layout.setContentsMargins(0, 0, 0, 10)

        if self._is_new:
            self._template = QComboBox()
            self._template.addItem("Scratch (all 1.0)", userData="scratch")
            for p in self._manager.all_listed():
                self._template.addItem(f"Clone: {p.name}", userData=p.id)
            self._template.currentIndexChanged.connect(self._on_template_changed)
            meta_layout.addRow("Based on Template:", self._template)

        self._name = QLineEdit()
        meta_layout.addRow("Profile Name:", self._name)

        self._year = QSpinBox()
        self._year.setRange(1900, 2200)
        meta_layout.addRow("Year (metadata):", self._year)

        self._remark = QLineEdit()
        self._remark.setPlaceholderText("Optional remarks...")
        meta_layout.addRow("Remark:", self._remark)

        self._shared = QCheckBox("Save for later projects (global library)")
        meta_layout.addRow("", self._shared)

        layout.addWidget(meta_group)

        # ── Body: Table ───────────────────────────────────────────────────────
        layout.addWidget(QLabel("<b>Adjust WPI Ratios:</b>"))
        self._table = _WPITable()
        self._table.set_editable(True)
        # Allow vertical scrolling so the dialog doesn't overflow the screen
        self._table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self._table, 1)

        # ── Footer: Actions ───────────────────────────────────────────────────
        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._on_save)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _load_meta(self):
        self._name.setText(self._profile.name)
        self._year.setValue(self._profile.year)
        self._remark.setText(self._profile.remark)
        self._shared.setChecked(self._profile.is_shared)

    def _on_template_changed(self):
        tid = self._template.currentData()
        if tid == "scratch":
            data = empty_data()
        else:
            tpl = self._manager.get_by_id(tid)
            import json as _json
            data = _json.loads(_json.dumps(tpl.data)) if tpl else empty_data()
        self._table.load_from_data(data)

    def _on_save(self):
        name = self._name.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation", "Profile name is required.")
            return
        
        # Only check name clashes if creating new or changing the name
        if self._is_new or name.lower() != self._profile.name.lower():
            if self._manager.is_name_taken(name):
                QMessageBox.warning(self, "Taken", f"A profile named '{name}' already exists.")
                return

        self._profile.name = name
        self._profile.year = self._year.value()
        self._profile.remark = self._remark.text().strip()
        self._profile.is_shared = self._shared.isChecked()
        self._profile.data = self._table.collect_to_data()
        self._profile.stamp_hash()

        if self._is_new:
            import uuid as _uuid
            self._profile.id = f"wpi_custom_{_uuid.uuid4().hex[:8]}"
        
        self._result_profile = self._profile
        self.accept()

    @property
    def result_profile(self) -> Optional[WPIProfile]:
        return self._result_profile


# ── _WPISelector ──────────────────────────────────────────────────────────────


class _WPISelector(QWidget):
    profile_selected = Signal(object)   # WPIProfile
    profile_saved    = Signal(object)   # WPIProfile
    profile_deleted  = Signal(str)      # profile id
    edit_requested   = Signal()

    def __init__(self, manager: WPIManager, parent=None):
        super().__init__(parent)
        self._manager = manager
        self._current: Optional[WPIProfile] = None
        self._build_ui()
        self._populate_combo()
        self._select_first()
        theme_manager().theme_changed.connect(self._refresh_styles)

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        lbl = QLabel("WPI Profile:")
        lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        layout.addWidget(lbl)

        self._combo = QComboBox()
        self._combo.setMinimumWidth(180)
        self._combo.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self._combo.currentIndexChanged.connect(self._on_combo_changed)
        layout.addWidget(self._combo)

        self._badge = QLabel("-")
        self._badge.setFixedWidth(24)
        self._badge.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._badge)

        layout.addStretch()

        self._btn_add    = QPushButton("+ Add New")
        self._btn_edit   = QPushButton("✎ Edit")
        self._btn_delete = QPushButton("🗑 Delete")

        for btn in (self._btn_add, self._btn_edit, self._btn_delete):
            btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            layout.addWidget(btn)

        self._btn_add.clicked.connect(self._on_add)
        self._btn_edit.clicked.connect(self._on_edit_current)
        self._btn_delete.clicked.connect(self._on_delete_current)

    # ── Combo management ──────────────────────────────────────────────────────

    def freeze(self, frozen: bool = True):
        self._combo.setEnabled(not frozen)
        self._btn_add.setEnabled(not frozen)
        self._btn_edit.setEnabled(not frozen and (self._current.is_custom if self._current else False))
        self._btn_delete.setEnabled(not frozen and (self._current.is_custom if self._current else False))

    def _populate_combo(self, select_id: Optional[str] = None):
        self._combo.blockSignals(True)
        self._combo.clear()
        bold = QFont()
        bold.setBold(True)
        for profile in self._manager.all_listed():
            label = profile.name if not profile.is_custom else f"★ {profile.name}"
            self._combo.addItem(label, userData=profile.id)
            idx = self._combo.count() - 1
            if not profile.is_custom:
                self._combo.setItemData(idx, bold, Qt.FontRole)
        self._combo.blockSignals(False)
        if select_id:
            for i in range(self._combo.count()):
                if self._combo.itemData(i) == select_id:
                    self._combo.setCurrentIndex(i)
                    break
        elif self._combo.count() > 0:
            self._combo.setCurrentIndex(0)

    def _on_combo_changed(self, idx: int):
        profile_id = self._combo.itemData(idx)
        if not profile_id: return
        profile = self._manager.get_by_id(profile_id)
        if profile:
            self._current = profile
            self._update_badge(profile)
            # Edit and Delete are only enabled for custom profiles
            self._btn_edit.setEnabled(profile.is_custom)
            self._btn_delete.setEnabled(profile.is_custom)
            self.profile_selected.emit(profile)

    def _select_first(self):
        if self._combo.count() > 0:
            self._combo.setCurrentIndex(0)
            self._on_combo_changed(0)

    def _update_badge(self, profile: WPIProfile):
        icon, token_key, tip = _BADGE[profile.integrity]
        self._badge.setText(icon)
        self._badge.setToolTip(f"{tip}\n({'DB' if not profile.is_custom else 'Custom'})")
        self._badge.setStyleSheet(f"color: {get_token(token_key)}; font-size: 14px;")

    # ── Slot handlers ─────────────────────────────────────────────────────────

    def _on_add(self):
        dlg = _WPIEditorDialog(self._manager, parent=self)
        if dlg.exec() == QDialog.Accepted and dlg.result_profile:
            p = dlg.result_profile
            self._manager.add_custom(p)
            if p.is_shared:
                save_to_user_library(p)
            
            if DEV:
                print("\n[DEV] Added New WPI Profile:")
                print(json.dumps(p.to_dict(), indent=2))
                
            self.refresh(select_id=p.id)
            self.profile_saved.emit(p)

    def _on_edit_current(self):
        if not self._current:
            return
        
        # If current is DB, we open the editor in "Add" mode but pre-cloned 
        # from this DB. If custom, we open in "Edit" mode.
        is_db = not self._current.is_custom
        dlg = _WPIEditorDialog(self._manager, profile=(None if is_db else self._current), parent=self)
        
        if is_db:
            # Manually set template and trigger clone in the "Add" dialog
            dlg._template.setCurrentIndex(dlg._template.findData(self._current.id))
        
        if dlg.exec() == QDialog.Accepted and dlg.result_profile:
            new_p = dlg.result_profile
            if is_db:
                self._manager.add_custom(new_p)
            else:
                self._manager.save_custom(new_p)
                
            if new_p.is_shared:
                save_to_user_library(new_p)
            
            if DEV:
                print(f"\n[DEV] {'Added (via Edit DB)' if is_db else 'Edited'} WPI Profile:")
                print(json.dumps(new_p.to_dict(), indent=2))
                
            self.refresh(select_id=new_p.id)
            self.profile_saved.emit(new_p)

    def _on_delete_current(self):
        if not self._current or not self._current.is_custom:
            return

        reply = QMessageBox.question(
            self,
            "Delete Profile",
            f"Delete custom profile '{self._current.name}'?\nThis cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        deleted_id = self._current.id
        self._manager.delete_custom(deleted_id)
        if self._current.is_shared:
            delete_from_user_library(deleted_id)
            
        self._current = None
        self._populate_combo()
        self._select_first()
        self.profile_deleted.emit(deleted_id)

    # ── Theme refresh ─────────────────────────────────────────────────────────

    def _refresh_styles(self):
        if self._current:
            self._update_badge(self._current)

    # ── Public API ────────────────────────────────────────────────────────────

    def current_profile(self) -> Optional[WPIProfile]:
        return self._current

    def current_is_custom(self) -> bool:
        return self._current is not None and self._current.is_custom

    def refresh(self, select_id: Optional[str] = None):
        self._populate_combo(select_id=select_id or (self._current.id if self._current else None))

    def select_by_id(self, profile_id: str):
        for i in range(self._combo.count()):
            if self._combo.itemData(i) == profile_id:
                self._combo.setCurrentIndex(i)
                return


