"""
gui/components/settings_dialog.py

SettingsPanel  - reusable form widget (name + theme pickers).
                 Embedded by both SettingsDialog and FirstLaunchDialog.

SettingsDialog - sidebar gear-button dialog (Save / Cancel).
"""

import three_ps_lcca_gui.core.start_manager as sm
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QTabWidget,
    QMessageBox,
    QScrollArea,
    QGroupBox,
    QInputDialog,
)
import os
import json
from PySide6.QtGui import QPalette, QColor, QPainter, QFont, QPixmap, QPainterPath
from three_ps_lcca_gui.gui.themes import (
    list_themes,
    get_theme_name,
    set_active_theme,
    set_appearance_mode,
    reapply,
)
import three_ps_lcca_gui.gui.themes as _themes
from three_ps_lcca_gui.gui.styles import btn_outline, font
from three_ps_lcca_gui.gui.theme import FS_SM, FW_MEDIUM
from three_ps_lcca_gui.gui.components.agency_profile_dialog import AgencyProfileForm
from three_ps_lcca_gui.gui.themes import get_token


# ── Shared form panel ─────────────────────────────────────────────────────────


class SettingsPanel(QWidget):
    """
    The shared settings form - display name + light/dark theme pickers.
    Contains no buttons or title; embed this inside any dialog.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # ── Display Name ──────────────────────────────────────────────────
        layout.addWidget(QLabel("<b>Display Name</b>"))
        # name_hint = QLabel("Shown in reports and exports.")
        # name_hint.setEnabled(False)
        # name_hint.setFont(font(FS_SM))
        # layout.addWidget(name_hint)

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("Enter your name…")
        self._name_edit.setFixedHeight(34)
        # Restore loading the saved name so it's visible if already set
        current_name = sm.get_profile().get("display_name", "")
        self._name_edit.setText(current_name)
        self._name_edit.textChanged.connect(
            lambda: (
                self._name_edit.setStyleSheet("")
                if self._name_edit.text().strip()
                else None
            )
        )
        layout.addWidget(self._name_edit)

        layout.addSpacing(8)

        # ── Appearance Mode ───────────────────────────────────────────────
        layout.addWidget(QLabel("<b>Appearance Mode</b>"))
        mode_hint = QLabel("Switch between light and dark mode. 'Auto' follows your OS setting.")
        mode_hint.setEnabled(False)
        mode_hint.setFont(font(FS_SM))
        mode_hint.setWordWrap(True)
        layout.addWidget(mode_hint)

        self._mode_combo = QComboBox()
        self._mode_combo.setFixedHeight(34)
        for value, label in [
            ("auto", "Auto (follow OS)"),
            ("light", "Light"),
            ("dark", "Dark"),
        ]:
            self._mode_combo.addItem(label, userData=value)
            if value == _themes.APPEARANCE_MODE:
                self._mode_combo.setCurrentIndex(self._mode_combo.count() - 1)
        layout.addWidget(self._mode_combo)

        layout.addSpacing(8)

        # ── Light Theme ───────────────────────────────────────────────────
        layout.addWidget(QLabel("<b>Light Theme</b>"))
        light_hint = QLabel("Colour scheme used in light mode.")
        light_hint.setEnabled(False)
        light_hint.setFont(font(FS_SM))
        layout.addWidget(light_hint)

        self._light_combo = self._theme_combo("light", _themes.ACTIVE_LIGHT)
        layout.addWidget(self._light_combo)

        layout.addSpacing(8)

        # ── Dark Theme ────────────────────────────────────────────────────
        layout.addWidget(QLabel("<b>Dark Theme</b>"))
        dark_hint = QLabel("Colour scheme used in dark mode.")
        dark_hint.setEnabled(False)
        dark_hint.setFont(font(FS_SM))
        layout.addWidget(dark_hint)

        self._dark_combo = self._theme_combo("dark", _themes.ACTIVE_DARK)
        layout.addWidget(self._dark_combo)

        theme_hint = QLabel("Theme changes apply immediately on save.")
        theme_hint.setEnabled(False)
        theme_hint.setFont(font(FS_SM))
        layout.addWidget(theme_hint)

        layout.addSpacing(8)

        # ── Local API ─────────────────────────────────────────────────────
        layout.addWidget(QLabel("<b>Local API</b>"))

        self._api_checkbox = QCheckBox("Enable local API server")
        self._api_checkbox.setChecked(sm.get_pref("api_enabled", "true") == "true")
        layout.addWidget(self._api_checkbox)

        api_hint = QLabel(
            "Lets external tools read/update an open project over a local HTTP "
            "API (File → API Access). Change takes effect after restart."
        )
        api_hint.setEnabled(False)
        api_hint.setFont(font(FS_SM))
        api_hint.setWordWrap(True)
        layout.addWidget(api_hint)

        # Actual bound URL - the port is picked automatically at startup (the
        # default may be busy, e.g. a second app instance), so it's shown here
        # rather than configured here.
        from three_ps_lcca_gui.gui.api.server import get_active_port
        port = get_active_port()
        if port:
            api_url_label = QLabel(f"Running at:  http://127.0.0.1:{port}")
            api_url_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        else:
            api_url_label = QLabel("Server not running.")
            api_url_label.setEnabled(False)
        api_url_label.setFont(font(FS_SM))
        layout.addWidget(api_url_label)

        layout.addStretch()

    # ── Public API ────────────────────────────────────────────────────────────

    def get_name(self) -> str:
        return self._name_edit.text().strip()

    def save(self) -> None:
        """Persist name + theme choices; re-applies theme live if anything changed."""
        sm.set_name(self.get_name())

        mode = self._mode_combo.currentData()
        light_mod = self._light_combo.currentData()
        dark_mod = self._dark_combo.currentData()

        changed = (
            mode != _themes.APPEARANCE_MODE
            or light_mod != _themes.ACTIVE_LIGHT
            or dark_mod != _themes.ACTIVE_DARK
        )

        set_appearance_mode(mode)
        set_active_theme("light", light_mod)
        set_active_theme("dark", dark_mod)
        sm.set_pref("api_enabled", "true" if self._api_checkbox.isChecked() else "false")

        if changed:
            reapply()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _theme_combo(self, variant: str, current: str) -> QComboBox:
        combo = QComboBox()
        combo.setFixedHeight(34)
        for module_name in list_themes(variant):
            combo.addItem(get_theme_name(variant, module_name), userData=module_name)
            if module_name == current:
                combo.setCurrentIndex(combo.count() - 1)
        return combo


# ── Settings dialog (sidebar gear button) ─────────────────────────────────────


class _CircularAvatar(QWidget):
    """Interactive circular avatar showing company logo or profile initial."""
    clicked = Signal()

    def __init__(self, size=80, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._letter = "＋"
        self._color = get_token("surface_mid")
        self._pixmap = None
        self._hovered = False
        self.setCursor(Qt.PointingHandCursor)

    def enterEvent(self, event):
        self._hovered = True
        self.update()

    def leaveEvent(self, event):
        self._hovered = False
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()

    def set_profile(self, name: str, logo_data: str = None):
        """Set avatar state. logo_data can be base64 string or file path."""
        if not name:
            self._letter = "＋"
            self._color = get_token("surface_mid")
            self._pixmap = None
            self.update()
            return

        self._letter = name[0].upper()
        # Generate stable color from theme tokens
        colors = ["primary", "info", "success", "warning"]
        token_name = colors[sum(ord(c) for c in name) % len(colors)]
        self._color = get_token(token_name)
        
        self._pixmap = None
        if logo_data:
            import base64 as _b64
            pm = QPixmap()
            if logo_data.startswith("data:image"):
                try:
                    raw = _b64.b64decode(logo_data.split(",")[1])
                    pm.loadFromData(raw)
                except Exception:
                    pass
            elif os.path.exists(logo_data):
                pm.load(logo_data)
            else:
                # Try treating as plain base64
                try:
                    raw = _b64.b64decode(logo_data)
                    pm.loadFromData(raw)
                except Exception:
                    pass

            if not pm.isNull():
                self._pixmap = pm.scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self.rect().adjusted(2, 2, -2, -2)
        
        # Draw Circle Background
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(self._color))
        p.drawEllipse(r)
        
        if self._pixmap:
            path = QPainterPath()
            path.addEllipse(r)
            p.setClipPath(path)
            px = (self.width() - self._pixmap.width()) // 2
            py = (self.height() - self._pixmap.height()) // 2
            p.drawPixmap(px, py, self._pixmap)
        else:
            c = QColor(self._color)
            lum = 0.299 * c.redF() + 0.587 * c.greenF() + 0.114 * c.blueF()
            p.setPen(QColor("#000000") if lum > 0.5 else QColor("#ffffff"))
            f = p.font()
            f.setPixelSize(self.width() // 3)
            f.setWeight(QFont.Weight.Bold)
            p.setFont(f)
            p.drawText(r, Qt.AlignCenter, self._letter)

        if self._hovered:
            p.setClipPath(QPainterPath()) # reset clip
            overlay = QPainterPath()
            overlay.addEllipse(r)
            p.setClipPath(overlay)
            p.setBrush(QColor(0, 0, 0, 120))
            p.drawEllipse(r)
            p.setPen(QColor("white"))
            f = p.font()
            f.setPixelSize(10)
            f.setBold(True)
            p.setFont(f)
            p.drawText(r, Qt.AlignCenter, "CHANGE")


class SettingsDialog(QDialog):
    """
    Settings dialog with a multi-tab system.
    Tab 1: General (Name, Themes)
    Tab 2: Profiles (Chrome-like Management)
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setFixedWidth(520)
        self.setFixedHeight(720)
        self.setModal(True)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        self.tabs = QTabWidget()
        
        # ── Tab 1: General ──────────────────────────────────────────────
        self.gen_tab = QWidget()
        gen_layout = QVBoxLayout(self.gen_tab)
        gen_layout.setContentsMargins(24, 24, 24, 24)
        
        self._panel = SettingsPanel(self)
        gen_scroll = QScrollArea()
        gen_scroll.setWidgetResizable(True)
        gen_scroll.setFrameShape(QFrame.NoFrame)
        gen_scroll.setWidget(self._panel)
        gen_layout.addWidget(gen_scroll)
        self.tabs.addTab(self.gen_tab, "General")

        # ── Tab 2: Profiles ─────────────────────────────────────────────
        self.prof_tab = QWidget()
        prof_layout = QVBoxLayout(self.prof_tab)
        prof_layout.setContentsMargins(24, 16, 24, 16)
        prof_layout.setSpacing(12)

        # Explanation
        prof_desc = QLabel(
            "Profiles store your agency details - name, logo, and contact information. "
            "The active profile is used in generated reports and exports."
        )
        prof_desc.setWordWrap(True)
        prof_desc.setEnabled(False)
        prof_desc.setFont(font(FS_SM))
        prof_layout.addWidget(prof_desc)

        # Avatar
        self.avatar = _CircularAvatar(size=80)
        self.avatar.clicked.connect(self._on_avatar_clicked)
        prof_layout.addWidget(self.avatar, 0, Qt.AlignHCenter)

        # Profile selector row
        selector_row = QHBoxLayout()
        selector_row.setSpacing(8)

        self.prof_combo = QComboBox()
        self.prof_combo.setFixedHeight(34)
        selector_row.addWidget(self.prof_combo, stretch=1)

        self.btn_delete = QPushButton("Delete Profile")
        self.btn_delete.setFixedHeight(34)
        self.btn_delete.setStyleSheet(f"color: {get_token('danger')};")
        self.btn_delete.clicked.connect(self._on_delete_profile)
        selector_row.addWidget(self.btn_delete)

        prof_layout.addLayout(selector_row)

        # Form fills remaining height; ScrollableForm handles its own scrolling
        self.prof_form = AgencyProfileForm()
        prof_layout.addWidget(self.prof_form, stretch=1)

        self.tabs.addTab(self.prof_tab, "Profiles")
        
        layout.addWidget(self.tabs, stretch=1)

        # ── Action Buttons ────────────────────────────────────────────────
        btn_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btn_box.button(QDialogButtonBox.Save).setStyleSheet(f"color: {get_token('base')};")
        btn_box.button(QDialogButtonBox.Cancel).setStyleSheet(f"color: {get_token('text')};")
        btn_box.accepted.connect(self._on_accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

        # ── Initialize ────────────────────────────────────────────────────
        self._populate_profiles()
        self.prof_combo.currentIndexChanged.connect(self._on_profile_selected)

    def _populate_profiles(self):
        self.prof_combo.blockSignals(True)
        self.prof_combo.clear()
        
        profiles = self.prof_form.get_available_profiles()
        for name in sorted(profiles.keys()):
            self.prof_combo.addItem(name)
            
        self.prof_combo.insertSeparator(self.prof_combo.count())
        self.prof_combo.addItem("+ New Profile", userData="new")

        # Default to the last-used profile, if any
        try:
            saved = json.loads(sm.get_pref("agency_profile") or "{}")
            active_name = saved.get("profile_name", "")
        except Exception:
            active_name = ""
        idx = self.prof_combo.findText(active_name) if active_name else -1
        self.prof_combo.setCurrentIndex(idx if idx >= 0 else self.prof_combo.count() - 1)

        self.prof_combo.blockSignals(False)
        self._on_profile_selected(self.prof_combo.currentIndex())

    def _on_profile_selected(self, index):
        if index < 0: return
        
        # If "+ New" is selected, clear form and show neutral avatar
        if self.prof_combo.currentData() == "new":
            self.prof_form.load_data_dict({})
            self.avatar.set_profile("")
            self.btn_delete.setVisible(False)
            return

        name = self.prof_combo.itemText(index)
        profiles = self.prof_form.get_available_profiles()
        
        logo = None
        if name in profiles:
            data = profiles[name]
            self.prof_form.load_data_dict(data)
            logo = data.get("agency_logo")
            self.btn_delete.setVisible(True)
        else:
            self.btn_delete.setVisible(False)

        self.avatar.set_profile(name, logo)

    def _on_avatar_clicked(self):
        """Open a file picker and update the profile logo."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Logo", "", "Images (*.png *.jpg *.jpeg)"
        )
        if not file_path:
            return

        import base64
        try:
            with open(file_path, "rb") as f:
                raw = f.read()
            encoded = base64.b64encode(raw).decode("utf-8")
            # Write plain base64 into the form's hidden logo QLineEdit
            logo_input = self.prof_form.findChild(QLineEdit, "agency_logo")
            if logo_input:
                logo_input.setText(encoded)
            self.avatar.set_profile(self.prof_combo.currentText(), encoded)
        except Exception as e:
            QMessageBox.warning(self, "Logo Upload Failed", f"Could not load image:\n{e}")

    def _on_delete_profile(self):
        name = self.prof_combo.currentText()
        if not name or self.prof_combo.currentData() == "new": return
        
        if QMessageBox.question(self, "Delete Profile",
                               f"Delete '{name}'?\nThis cannot be undone.",
                               QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.prof_form.delete_from_json(name)
            self._populate_profiles()

    def _on_accept(self):
        self._panel.save()

        # Only save profile data when the Profiles tab is active
        if self.tabs.currentWidget() is self.prof_tab:
            if self.prof_combo.currentData() == "new":
                name, ok = QInputDialog.getText(self, "New Profile", "Name for this profile:")
                if not ok:
                    return
                profile_name = name.strip()
                if not profile_name:
                    QMessageBox.warning(self, "Invalid Name", "Profile name cannot be empty.")
                    return
                profiles = self.prof_form.get_available_profiles()
                if profile_name in profiles:
                    QMessageBox.warning(self, "Duplicate Name", f"Profile '{profile_name}' already exists.")
                    return
                self.prof_form.save_to_json(profile_name)
                data = self.prof_form.get_data_dict()
                data["profile_name"] = profile_name
                sm.set_pref("agency_profile", json.dumps(data))
            else:
                profile_name = self.prof_combo.currentText()
                if profile_name:
                    self.prof_form.save_to_json(profile_name)
                    data = self.prof_form.get_data_dict()
                    data["profile_name"] = profile_name
                    sm.set_pref("agency_profile", json.dumps(data))

        self.accept()


