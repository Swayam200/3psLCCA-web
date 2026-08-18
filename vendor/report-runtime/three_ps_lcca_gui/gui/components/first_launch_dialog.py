"""
gui/components/first_launch_dialog.py

First-launch welcome dialog - same settings form as the sidebar Settings dialog,
wrapped in a welcome header with "Skip" / "Get Started" buttons.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)
from three_ps_lcca_gui.gui.styles import font, btn_primary, btn_outline
from three_ps_lcca_gui.gui.theme import (
    SP2, SP4, SP6, SP8, SP10,
    BTN_MD,
    FS_BASE, FS_DISP,
    FW_BOLD, FW_MEDIUM,
)
from three_ps_lcca_gui.gui.themes import get_token
from three_ps_lcca_gui.gui.components.settings_dialog import SettingsPanel


class FirstLaunchDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Welcome to 3psLCCA")
        self.setMinimumWidth(420)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SP10, SP10, SP10, SP8)
        layout.setSpacing(0)

        # Brand accent bar
        accent = QFrame()
        accent.setFixedHeight(4)
        accent.setStyleSheet(f"background: {get_token('primary')}; border-radius: 2px;")
        layout.addWidget(accent)
        layout.addSpacing(SP8 - SP2)

        # Title
        title = QLabel("Welcome to 3psLCCA")
        title.setFont(font(FS_DISP - 2, FW_BOLD))
        layout.addWidget(title)
        layout.addSpacing(SP2)

        # Subtitle
        sub = QLabel("Life Cycle Cost Analysis for bridge projects.")
        sub.setFont(font(FS_BASE))
        sub.setEnabled(False)
        layout.addWidget(sub)
        layout.addSpacing(SP8)

        # ── Shared settings panel ──────────────────────────────────────────
        self._panel = SettingsPanel(self)
        layout.addWidget(self._panel)
        layout.addSpacing(SP8)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(SP2)
        btn_row.addStretch()

        btn_skip = QPushButton("Skip")
        btn_skip.setFixedHeight(BTN_MD)
        btn_skip.setFont(font(FS_BASE))
        btn_skip.setStyleSheet(btn_outline())
        btn_skip.clicked.connect(self.reject)
        btn_row.addWidget(btn_skip)

        btn_ok = QPushButton("Get Started")
        btn_ok.setFixedHeight(BTN_MD)
        btn_ok.setFont(font(FS_BASE, FW_MEDIUM))
        btn_ok.setDefault(True)
        btn_ok.setStyleSheet(btn_primary())
        btn_ok.clicked.connect(self._accept)
        btn_row.addWidget(btn_ok)

        layout.addLayout(btn_row)

    def _accept(self):
        self._panel.save()
        self.accept()

    def get_name(self) -> str:
        return self._panel.get_name()


