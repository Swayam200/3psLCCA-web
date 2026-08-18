"""
gui/components/save_status_bar.py

Status bar showing autosave state + Save Checkpoint / Checkpoints buttons.
"""

from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton
from PySide6.QtCore import QTimer

from three_ps_lcca_gui.gui.components.checkpoint_dialog import SaveCheckpointDialog, CheckpointManagerDialog


class SaveStatusBar(QWidget):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(10)

        self.status_label = QLabel("No project open")
        self.status_label.setWordWrap(True)  # Enable text wrapping
        self.status_label.setStyleSheet("background: transparent;")
        layout.addWidget(self.status_label)

        layout.addStretch()

        self.checkpoint_btn = QPushButton("Save Checkpoint")
        self.checkpoint_btn.clicked.connect(self._open_save_dialog)
        layout.addWidget(self.checkpoint_btn)

        self.manager_btn = QPushButton("Checkpoints")
        self.manager_btn.clicked.connect(self._open_manager_dialog)
        layout.addWidget(self.manager_btn)

        self.set_active(False)
        self._connect_signals()

    def _connect_signals(self):
        if self.controller:
            self.controller.project_loaded.connect(lambda: self.set_active(True))
            self.controller.sync_completed.connect(self._on_saved)
            self.controller.dirty_changed.connect(self._on_dirty_changed)
            self.controller.status_message.connect(self._on_status_message)
            self.controller.fault_occurred.connect(self._on_fault)
            # If the project was already loaded before this widget was created
            # (e.g. created mid-preload), sync state immediately so the label
            # never shows "No project open" when a project is actually active.
            if self.controller.active_project_id:
                self.set_active(True)
                if self.controller.is_dirty():
                    self.status_label.setText("Unsaved changes...")
                else:
                    self.status_label.setText("All changes saved")

    def _on_saved(self):
        self.status_label.setText("All changes saved")

    def _on_dirty_changed(self, is_dirty: bool):
        self.status_label.setText("Unsaved changes..." if is_dirty else "All changes saved")

    def _on_status_message(self, message: str):
        if "Checkpoint saved" in message or "Restored" in message:
            self.status_label.setText(message)
            QTimer.singleShot(4000, lambda: self.status_label.setText("All changes saved"))

    def _on_fault(self, error_message: str):
        self.status_label.setText(f"Error: {error_message}")

    def _open_save_dialog(self):
        SaveCheckpointDialog(self.controller, parent=self).exec()

    def _open_manager_dialog(self):
        CheckpointManagerDialog(self.controller, parent=self).exec()

    def set_active(self, active: bool):
        self.checkpoint_btn.setEnabled(active)
        self.manager_btn.setEnabled(active)
        if not active:
            self.status_label.setText("No project open")


