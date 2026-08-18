"""
gui/components/agency_profile_dialog.py
"""

import os
import json
from PySide6.QtWidgets import QDialog, QVBoxLayout, QDialogButtonBox, QInputDialog, QMessageBox, QLineEdit
from three_ps_lcca_gui.core import start_manager as sm

from three_ps_lcca_gui.gui.components.base_widget import ScrollableForm
from three_ps_lcca_gui.gui.components.global_info.main import AGENCY_FIELDS
from three_ps_lcca_gui.gui.components.utils.form_builder.form_builder import build_form
from three_ps_lcca_gui.gui.components.utils.form_builder.form_definitions import Section


class AgencyProfileForm(ScrollableForm):
    """
    A standalone form for the Agency evaluating fields that
    saves profiles into data/user_db/profile.json to support multiple profiles.
    """
    def __init__(self):
        super().__init__(controller=None, chunk_name="agency_profile")

        # Exclude the section header and agency_logo - logo is handled by the
        # avatar widget in SettingsDialog, not a separate Browse field here.
        fields_no_logo = [
            f for f in AGENCY_FIELDS
            if not isinstance(f, Section) and getattr(f, "key", None) != "agency_logo"
        ]
        self.required_keys = build_form(self, fields_no_logo)

        # Register a hidden QLineEdit for agency_logo so get_data_dict() / load_data_dict()
        # still round-trip the logo data without showing a duplicate Browse button.
        self._logo_input = QLineEdit(self._content)  # parented so Qt owns it
        self._logo_input.setObjectName("agency_logo")
        self._logo_input.setMaxLength(10_000_000)
        self._logo_input.setReadOnly(True)
        self._logo_input.hide()
        self.register_field("agency_logo", self._logo_input)

    def save_to_json(self, profile_name: str, manual_data: dict = None):
        data = manual_data if manual_data is not None else self.get_data_dict()
        
        dir_path = os.path.join("data", "user_db")
        os.makedirs(dir_path, exist_ok=True)
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
        
        profiles[profile_name] = data
        
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(profiles, f, indent=4)
            
        # Also store the latest one as default for auto-populating new projects
        sm.set_pref("agency_profile", json.dumps(data))

    def get_available_profiles(self) -> dict:
        file_path = os.path.join("data", "user_db", "profile.json")
        if not os.path.exists(file_path):
            return {}
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                if content.strip():
                    return json.loads(content)
        except Exception:
            pass
        return {}

    def delete_from_json(self, profile_name: str) -> bool:
        profiles = self.get_available_profiles()
        if profile_name in profiles:
            del profiles[profile_name]
            file_path = os.path.join("data", "user_db", "profile.json")
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(profiles, f, indent=4)
                return True
            except Exception:
                pass
        return False


class AgencyProfileDialog(QDialog):
    """
    Popup dialog to let users save an Agency Profile.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Save Agency Profile")
        self.setFixedWidth(500)
        self.setFixedHeight(650)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        self.profile_form = AgencyProfileForm()
        layout.addWidget(self.profile_form)

        btn_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btn_box.accepted.connect(self.save_and_accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def save_and_accept(self):
        profile_name, ok = QInputDialog.getText(
            self, "Profile Name", "Enter a name for this profile:"
        )
        if ok and profile_name.strip():
            self.profile_form.save_to_json(profile_name.strip())
            self.accept()
        elif ok:
            QMessageBox.warning(self, "Invalid Name", "Profile name cannot be empty.")




