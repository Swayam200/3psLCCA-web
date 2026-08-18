"""
gui/components/api_access_prompt.py

A minimal Allow / Deny dialog shown when an external caller hits
/<project_id>/get_tokens for the first time in a session.

Message: "An external application wants to access this project using the API"
- Allow  → result_allowed = True
- Deny   → result_allowed = False
- X (close window) → result_allowed = False (treated same as Deny)
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)


class ApiAccessPrompt(QDialog):
    """Single-purpose Allow/Deny popup for API access request.

    Shown from bridge.py in response to an external HTTP call, so - unlike
    a dialog the user opens themselves - there's no guarantee this app is
    the foreground window when it appears. Windows silently denies
    SetForegroundWindow calls from processes it doesn't consider "active",
    which can leave a freshly-created window sitting behind whatever the
    user is actually looking at (e.g. a terminal). WindowStaysOnTopHint
    sidesteps that: it controls z-order, not keyboard focus, and Windows
    honors it regardless of the foreground-lock restriction - the dialog
    is guaranteed visible even on the rare chance it doesn't grab focus.
    """

    def __init__(self, project_display_name: str, parent=None):
        super().__init__(parent)
        self.result_allowed: bool = False  # default = denied (covers X button too)

        self.setWindowTitle("API Access Request")
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setMinimumWidth(400)
        self.setMaximumWidth(500)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 20)
        layout.setSpacing(16)

        msg = QLabel(
            f"An external application wants to access this project using the API:\n\n"
            f"<b>{project_display_name}</b>\n\n"
            f"Do you want to allow API communication?"
        )
        msg.setWordWrap(True)
        msg.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(msg)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch()

        btn_deny = QPushButton("Deny")
        btn_deny.setFixedWidth(95)
        btn_deny.clicked.connect(self._on_deny)

        btn_allow = QPushButton("Allow")
        btn_allow.setFixedWidth(95)
        # Deliberately no setDefault(True) here: this dialog can be shown
        # while the user isn't looking (triggered by an external HTTP call,
        # not a click of their own), so a stray/late Enter keypress landing
        # on it must never silently grant API access. Only an explicit
        # button click (or explicit Deny/close) decides the outcome.
        btn_allow.clicked.connect(self._on_allow)

        btn_row.addWidget(btn_deny)
        btn_row.addWidget(btn_allow)
        layout.addLayout(btn_row)

    def showEvent(self, event):
        super().showEvent(event)
        # Center on the screen the parent window is on (falls back to the
        # primary screen if there's no parent) so the dialog can't end up
        # off-screen or tucked in a corner behind other windows.
        screen = self.parent().screen() if self.parent() else QGuiApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            self.move(
                geo.center().x() - self.width() // 2,
                geo.center().y() - self.height() // 2,
            )
        self.raise_()
        self.activateWindow()
        # Belt-and-braces: even if Windows' foreground-lock stops
        # activateWindow() from actually stealing keyboard focus,
        # flashing the taskbar entry still reliably signals the user.
        QApplication.alert(self)

    def _on_allow(self):
        self.result_allowed = True
        self.accept()

    def _on_deny(self):
        self.result_allowed = False
        self.reject()

    def closeEvent(self, event):
        """X button → treated as Deny."""
        self.result_allowed = False
        super().closeEvent(event)
