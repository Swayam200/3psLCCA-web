# gui/components/recovery_dialog.py

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QTextEdit,
    QProgressBar,
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont, QColor
from three_ps_lcca_gui.gui.themes import get_token


class RecoveryWorker(QThread):
    """Runs the recovery chain in a background thread."""

    finished = Signal(dict)

    def __init__(self, engine):
        super().__init__()
        self.engine = engine

    def run(self):
        result = self.engine.run_recovery_chain()
        self.finished.emit(result)


class RecoveryDialog(QDialog):
    """
    Shown when a project needs recovery on open.
    Displays health issues, runs recovery chain, shows result.
    """

    def __init__(self, engine, health: dict, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.health = health
        self.result = None
        self._worker = None

        self.setWindowTitle("Project Recovery")
        self.setFixedWidth(480)
        self.setModal(True)
        self.setWindowFlag(Qt.WindowCloseButtonHint, False)

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # ── Title ─────────────────────────────────────────────────────────────
        title = QLabel("⚠  Project Needs Recovery")
        f = QFont()
        f.setPointSize(12)
        f.setBold(True)
        title.setFont(f)
        layout.addWidget(title)

        # ── Issue summary ─────────────────────────────────────────────────────
        issues_text = "\n".join(f"• {i}" for i in self.health.get("issues", []))
        if not issues_text:
            issues_text = "• Unknown integrity issue detected."

        issues_label = QLabel(issues_text)
        issues_label.setWordWrap(True)
        issues_label.setStyleSheet(f"color: {get_token('danger')};")
        layout.addWidget(issues_label)

        layout.addWidget(self._divider())

        # ── Info ──────────────────────────────────────────────────────────────
        info = QLabel(
            "A backup (.ebak) of the current project state has been created "
            "automatically before any changes are made.\n\n"
            "Click 'Recover' to attempt automatic recovery."
        )
        info.setWordWrap(True)
        info.setEnabled(False)
        layout.addWidget(info)

        # ── Progress bar (hidden until recovery starts) ───────────────────────
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)  # indeterminate
        self.progress.hide()
        layout.addWidget(self.progress)

        # ── Result area (hidden until recovery finishes) ──────────────────────
        self.result_label = QLabel()
        self.result_label.setWordWrap(True)
        self.result_label.hide()
        layout.addWidget(self.result_label)

        layout.addWidget(self._divider())

        # ── Buttons ───────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.btn_recover = QPushButton("Recover")
        self.btn_recover.setFixedHeight(36)
        self.btn_recover.setDefault(True)
        self.btn_recover.clicked.connect(self._start_recovery)
        btn_row.addWidget(self.btn_recover)

        self.btn_skip = QPushButton("Open Anyway")
        self.btn_skip.setFixedHeight(36)
        self.btn_skip.setToolTip(
            "Open the project without recovery. Data may be incomplete."
        )
        self.btn_skip.clicked.connect(self._skip)
        btn_row.addWidget(self.btn_skip)

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setFixedHeight(36)
        self.btn_cancel.clicked.connect(self._cancel)
        btn_row.addWidget(self.btn_cancel)

        self.btn_close = QPushButton("Close")
        self.btn_close.setFixedHeight(36)
        self.btn_close.hide()
        self.btn_close.clicked.connect(self.accept)
        btn_row.addWidget(self.btn_close)

        layout.addLayout(btn_row)

    @staticmethod
    def _divider() -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        return line

    def _start_recovery(self):
        self.btn_recover.setEnabled(False)
        self.btn_skip.setEnabled(False)
        self.btn_cancel.setEnabled(False)
        self.progress.show()
        self.result_label.hide()

        self._worker = RecoveryWorker(self.engine)
        self._worker.finished.connect(self._on_recovery_done)
        self._worker.start()

    def _on_recovery_done(self, result: dict):
        self.result = result
        self.progress.hide()

        level = result.get("level", 0)
        success = result.get("success", False)
        description = result.get("description", "")
        data_loss = result.get("data_loss", False)
        missing = result.get("missing_chunks", [])

        LEVEL_LABELS = {
            1: "WAL replay",
            2: "Manifest ring buffer",
            3: "Auto-save checkpoint",
            4: "Manual checkpoint",
            5: "Object store rebuild",
            6: "Partial recovery",
            7: "Unrecoverable",
        }

        if success:
            level_name = LEVEL_LABELS.get(level, f"Level {level}")
            msg = f"✅  Recovery successful via {level_name}.\n\n{description}"
            if data_loss:
                msg += "\n\n⚠  Some recent changes may not have been recovered."
            if missing:
                msg += f"\n\nMissing sections: {', '.join(missing)}"
            self.result_label.setStyleSheet(f"color: {get_token('success')};")
        else:
            msg = f"❌  Recovery failed.\n\n{description}\n\nYour .ebak backup is preserved in the project's backups/ folder."
            self.result_label.setStyleSheet(f"color: {get_token('danger')};")

        self.result_label.setText(msg)
        self.result_label.show()

        self.btn_close.show()
        if not success:
            # Re-enable open anyway as last resort
            self.btn_skip.setEnabled(True)
            self.btn_skip.setText("Open Anyway (Unsafe)")

    def _skip(self):
        self.result = {
            "success": True,
            "level": 0,
            "description": "Opened without recovery.",
            "data_loss": True,
        }
        self.reject()

    def _cancel(self):
        self.result = None
        self.reject()

    def was_cancelled(self) -> bool:
        return self.result is None

    def was_skipped(self) -> bool:
        return self.result is not None and self.result.get("level") == 0


