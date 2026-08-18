"""
gui/components/logs.py

A real-time log viewer panel that reads from the engine's log_history
via the ProjectController. Replaces the placeholder stub.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QLabel
)
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QFont, QColor, QTextCharFormat, QTextCursor
from .utils.validation_helpers import confirm_clear_all


class Logs(QWidget):
    """
    Live log viewer panel. Polls the engine log history every 2 seconds
    and displays entries with colour-coded severity.
    """

    def __init__(self, controller=None):
        super().__init__()
        self.controller = controller
        self._last_log_count = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Header row
        header_row = QHBoxLayout()
        title = QLabel("Engine Logs")
        font = QFont()
        font.setPointSize(11)
        font.setBold(True)
        title.setFont(font)
        header_row.addWidget(title)
        header_row.addStretch()

        self.health_label = QLabel("")
        # self.health_label.setStyleSheet("color: #555; font-size: 11px;")
        header_row.addWidget(self.health_label)

        clear_btn = QPushButton("Clear")
        clear_btn.setFixedWidth(60)
        clear_btn.clicked.connect(self._clear_display)
        header_row.addWidget(clear_btn)

        layout.addLayout(header_row)

        # Log display
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setFont(QFont("Courier New", 10))
        # self.log_view.setStyleSheet(
        #     "QTextEdit { background-color: #1e1e1e; color: #d4d4d4; "
        #     "border: 1px solid #444; border-radius: 4px; padding: 6px; }"
        # )
        layout.addWidget(self.log_view)

        # Auto-refresh timer (polls every 2 seconds)
        self._timer = QTimer(self)
        self._timer.setInterval(2000)
        self._timer.timeout.connect(self.refresh_logs)
        self._timer.start()

        self.refresh_logs()

    def refresh_logs(self):
        """Fetches latest log entries from the controller and appends new ones."""
        if not self.controller:
            return

        logs = self.controller.get_engine_logs()

        # Only append new entries since last refresh
        new_entries = logs[self._last_log_count:]
        if new_entries:
            cursor = self.log_view.textCursor()
            cursor.movePosition(QTextCursor.End)

            for entry in new_entries:
                fmt = QTextCharFormat()

                # Colour-code by severity
                from three_ps_lcca_gui.gui.themes import get_token
                if "CRITICAL" in entry or "FAULT" in entry or "FAILED" in entry:
                    fmt.setForeground(QColor(get_token("danger")))
                elif "ERROR" in entry or "corrupt" in entry or "loss" in entry:
                    fmt.setForeground(QColor(get_token("danger")))
                elif "WARN" in entry or "stale" in entry or "DENIED" in entry:
                    fmt.setForeground(QColor(get_token("warning")))
                elif "Checkpoint" in entry or "Restored" in entry or "saved" in entry.lower():
                    fmt.setForeground(QColor(get_token("info")))
                elif "attached" in entry or "SUCCESS" in entry:
                    fmt.setForeground(QColor(get_token("success")))
                else:
                    fmt.setForeground(QColor(get_token("text_secondary")))

                cursor.setCharFormat(fmt)
                cursor.insertText(entry + "\n")

            self._last_log_count = len(logs)

            # Auto-scroll to bottom
            self.log_view.setTextCursor(cursor)
            self.log_view.ensureCursorVisible()

        # Update health badge
        report = self.controller.get_health_report()
        if report:
            chunks = report.get("chunk_count", 0)
            checkpoints = report.get("checkpoint_count", 0)
            pending = report.get("pending_syncs", 0)
            wal = "WAL" if report.get("wal_exists") else ""
            parts = [f"Chunks: {chunks}", f"Checkpoints: {checkpoints}", f"Pending: {pending}"]
            if wal:
                parts.append(wal)
            self.health_label.setText("  |  ".join(parts))

    def _clear_display(self):
        """Clears the display (does not clear the engine's log_history)."""
        if not confirm_clear_all(self):
            return
        self.log_view.clear()
        self._last_log_count = 0
        if self.controller:
            # Reset to current length so we don't re-display old entries
            logs = self.controller.get_engine_logs()
            self._last_log_count = len(logs)


