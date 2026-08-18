"""
gui/components/api_access_dialog.py

Shows the local API URL + bearer token for the currently open project, with
controls to generate/regenerate/revoke that project's token.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from three_ps_lcca_gui.gui.api import tokens
from three_ps_lcca_gui.gui.api.registry import CHUNK_PAGE_MAP
from three_ps_lcca_gui.gui.api.server import get_active_port


class ApiAccessDialog(QDialog):
    def __init__(self, project_id: str, parent=None):
        super().__init__(parent)
        self.project_id = project_id
        self.setWindowTitle("API Access")
        self.setMinimumWidth(480)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        self._port = get_active_port()

        if self._port is None:
            layout.addWidget(QLabel(
                "The local API server is not running.\n"
                "It may be disabled in Settings, or failed to start."
            ))
            btn_close = QPushButton("Close")
            btn_close.clicked.connect(self.reject)
            layout.addWidget(btn_close)
            return

        # ── Active-token block (URL, token, usage hint) ─────────────────────
        self._active_block = QWidget()
        active_layout = QVBoxLayout(self._active_block)
        active_layout.setContentsMargins(0, 0, 0, 0)
        active_layout.setSpacing(12)

        self._hint = QLabel(
            "Append a page name below to the base URL to GET/POST it, e.g. "
            "<code>&lt;base URL&gt;/bridge_data</code>. Every request must "
            "include the token below as an <b>X-API-Token</b> header."
        )
        self._hint.setWordWrap(True)
        active_layout.addWidget(self._hint)

        form = QFormLayout()
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self._url_edit = self._readonly_row("", form, "Base URL")
        self._token_edit = self._readonly_row("", form, "Token")
        active_layout.addLayout(form)

        self._pages_label = QLabel()
        self._pages_label.setWordWrap(True)
        active_layout.addWidget(self._pages_label)

        layout.addWidget(self._active_block)

        # ── Revoked-state message ────────────────────────────────────────
        self._revoked_label = QLabel(
            "API access for this project is currently revoked. All requests "
            "will be rejected with 401 until you generate a new token."
        )
        self._revoked_label.setWordWrap(True)
        layout.addWidget(self._revoked_label)

        # ── Buttons ──────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        self._btn_generate = QPushButton("Generate Token")
        self._btn_generate.clicked.connect(self._on_generate)
        self._btn_regen = QPushButton("Regenerate Token")
        self._btn_regen.clicked.connect(self._on_regenerate)
        self._btn_revoke = QPushButton("Revoke Token")
        self._btn_revoke.clicked.connect(self._on_revoke)
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)

        btn_row.addWidget(self._btn_generate)
        btn_row.addWidget(self._btn_regen)
        btn_row.addWidget(self._btn_revoke)
        btn_row.addStretch()
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)

        self._refresh()

    def _readonly_row(self, value: str, form: QFormLayout, label: str) -> QLineEdit:
        row = QHBoxLayout()
        edit = QLineEdit(value)
        edit.setReadOnly(True)
        btn_copy = QPushButton("Copy")
        btn_copy.setFixedWidth(60)
        btn_copy.clicked.connect(lambda: QApplication.clipboard().setText(edit.text()))
        row.addWidget(edit)
        row.addWidget(btn_copy)
        form.addRow(label, row)
        return edit

    def _refresh(self):
        """Redraws the dialog for the current token state - active (URL +
        token + regenerate/revoke) or revoked (message + generate only)."""
        token = tokens.get_token(self.project_id)
        active = token is not None

        self._active_block.setVisible(active)
        self._revoked_label.setVisible(not active)
        self._btn_generate.setVisible(not active)
        self._btn_regen.setVisible(active)
        self._btn_revoke.setVisible(active)

        if active:
            base_url = f"http://127.0.0.1:{self._port}/{self.project_id}"
            self._url_edit.setText(base_url)
            self._token_edit.setText(token)
            pages = ", ".join(sorted(CHUNK_PAGE_MAP.keys())) or "(none registered)"
            self._pages_label.setText(f"<b>Available pages:</b> {pages}")

    def _on_generate(self):
        tokens.ensure_token(self.project_id)
        self._refresh()

    def _on_regenerate(self):
        tokens.regenerate(self.project_id)
        self._refresh()

    def _on_revoke(self):
        tokens.clear_token(self.project_id)
        self._refresh()
