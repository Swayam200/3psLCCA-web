"""
gui/components/checkpoint_dialog.py

Two dialogs for the checkpoint system:

  SaveCheckpointDialog    - prompts for a label + notes, then saves
  CheckpointManagerDialog - lists all checkpoints; restore or delete
"""

from datetime import datetime

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QTextEdit, QPushButton,
    QDialogButtonBox,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QAbstractItemView,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from three_ps_lcca_gui.gui.theme import (
    FS_LG, FS_BASE, FS_SM,
    FW_SEMIBOLD, FW_NORMAL,
    BTN_MD, BTN_SM,
    SP2, SP3, SP4, SP8, SP10,
)
from three_ps_lcca_gui.gui.themes import get_token
from three_ps_lcca_gui.gui.components.utils.table_widgets import round_table_viewport
from three_ps_lcca_gui.gui.styles import font as _f


# ── Save Checkpoint Dialog ─────────────────────────────────────────────────────


class SaveCheckpointDialog(QDialog):
    """Modal dialog - collect label + notes before saving a checkpoint."""

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("Save Checkpoint")
        self.setFixedWidth(420)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(24, 24, 24, 24)

        # Header
        header = QLabel("Save Checkpoint")
        header.setFont(_f(FS_LG, FW_SEMIBOLD))
        layout.addWidget(header)

        desc = QLabel(
            "A checkpoint is a full snapshot of your current project data. "
            "You can restore a saved checkpoint at any time from the \"Checkpoint Manager\"."
        )
        desc.setWordWrap(True)
        desc.setFont(_f(FS_SM))
        desc.setEnabled(False)
        layout.addWidget(desc)

        layout.addSpacing(4)

        # Form
        form = QFormLayout()
        form.setSpacing(8)

        self.label_edit = QLineEdit()
        self.label_edit.setPlaceholderText("e.g. before client review, v2 cost update")
        self.label_edit.setMaxLength(30)
        self.label_edit.setFixedHeight(34)
        form.addRow("<b>Label</b>", self.label_edit)

        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText("Optional notes about this snapshot…")
        self.notes_edit.setFixedHeight(80)
        form.addRow("<b>Notes</b>", self.notes_edit)

        layout.addLayout(form)
        layout.addSpacing(8)

        # Buttons
        self._btn_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self._btn_box.rejected.connect(self.reject)
        self._save_btn = self._btn_box.button(QDialogButtonBox.Save)
        self._save_btn.clicked.connect(self._on_save)
        layout.addWidget(self._btn_box)

    def _on_save(self):
        label = self.label_edit.text().strip() or "manual"
        notes = self.notes_edit.toPlainText().strip()

        self._save_btn.setEnabled(False)
        self._save_btn.setText("Saving…")

        zip_name = self.controller.save_checkpoint(label=label, notes=notes)

        if zip_name:
            QMessageBox.information(
                self, "Checkpoint Saved",
                f"Checkpoint '{label}' saved.\nFile: {zip_name}",
            )
            self.accept()
        else:
            QMessageBox.critical(
                self, "Save Failed",
                "Could not save the checkpoint.",
            )
            self._save_btn.setEnabled(True)
            self._save_btn.setText("Save")


# ── Checkpoint Manager Dialog ──────────────────────────────────────────────────


class CheckpointManagerDialog(QDialog):
    """Full checkpoint browser - list, restore, delete."""

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self._checkpoints: list = []
        self.setWindowTitle("Checkpoint Manager")
        self.setMinimumSize(700, 440)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(24, 24, 24, 24)

        # Header
        header = QLabel("Checkpoint Manager")
        header.setFont(_f(FS_LG, FW_SEMIBOLD))
        layout.addWidget(header)

        desc = QLabel(
            "Select a checkpoint to restore or delete it. "
            "Restoring will replace all current project data with the snapshot."
        )
        desc.setWordWrap(True)
        desc.setFont(_f(FS_SM))
        desc.setEnabled(False)
        layout.addWidget(desc)

        layout.addSpacing(4)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Label", "Date & Time", "Notes", "File"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)
        # Apply rounded viewport and connect selection signal after the table is
        # parented via addWidget; doing so before causes a segfault when Qt
        # traverses the transparent-background chain on an unparented viewport.
        round_table_viewport(self.table)
        self.table.selectionModel().selectionChanged.connect(self._on_selection_changed)

        layout.addSpacing(4)

        # Action row - New on left, Delete + Restore on right
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.new_btn = QPushButton("+ New Checkpoint")
        self.new_btn.setFixedHeight(BTN_SM)
        self.new_btn.clicked.connect(self._on_new_checkpoint)
        btn_row.addWidget(self.new_btn)

        btn_row.addStretch()

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setFixedHeight(BTN_SM)
        self.delete_btn.setEnabled(False)
        self.delete_btn.clicked.connect(self._on_delete)
        btn_row.addWidget(self.delete_btn)

        self.restore_btn = QPushButton("Restore")
        self.restore_btn.setFixedHeight(BTN_SM)
        self.restore_btn.setEnabled(False)
        self.restore_btn.setDefault(True)
        self.restore_btn.clicked.connect(self._on_restore)
        btn_row.addWidget(self.restore_btn)

        layout.addLayout(btn_row)

        self._populate_table()

    def _populate_table(self):
        checkpoints = self.controller.list_checkpoints()
        self._checkpoints = checkpoints
        self.table.setRowCount(len(checkpoints))

        for row, cp in enumerate(checkpoints):
            raw_date = cp.get("date", "")
            try:
                ts = raw_date.rsplit("_", 1)[0] if raw_date.count("_") == 2 else raw_date
                dt = datetime.strptime(ts, "%Y%m%d_%H%M%S")
                formatted_date = dt.strftime("%d %b %Y, %I:%M %p")
            except Exception:
                formatted_date = raw_date

            _ro = Qt.ItemIsEnabled | Qt.ItemIsSelectable

            label_item = QTableWidgetItem(cp.get("label", ""))
            label_item.setFont(_f(FS_BASE, FW_SEMIBOLD))
            label_item.setFlags(_ro)

            date_item = QTableWidgetItem(formatted_date)
            date_item.setFlags(_ro)

            notes_item = QTableWidgetItem(cp.get("notes", ""))
            notes_item.setFlags(_ro)

            file_item = QTableWidgetItem(cp.get("filename", ""))
            file_item.setFont(_f(FS_SM))
            file_item.setFlags(_ro)

            self.table.setItem(row, 0, label_item)
            self.table.setItem(row, 1, date_item)
            self.table.setItem(row, 2, notes_item)
            self.table.setItem(row, 3, file_item)

        if not checkpoints:
            self.table.setRowCount(1)
            empty_item = QTableWidgetItem(
                "No checkpoints yet. Use '+ New Checkpoint' to create one."
            )
            empty_item.setForeground(QColor(get_token("text_disabled")))
            empty_item.setFlags(Qt.ItemIsEnabled)
            self.table.setItem(0, 0, empty_item)
            self.table.setSpan(0, 0, 1, 4)

    def _on_selection_changed(self):
        has = bool(self.table.selectedItems()) and bool(self._checkpoints)
        self.restore_btn.setEnabled(has)
        self.delete_btn.setEnabled(has)

    def _selected_checkpoint(self):
        row = self.table.currentRow()
        if 0 <= row < len(self._checkpoints):
            return self._checkpoints[row]
        return None

    def _on_new_checkpoint(self):
        dlg = SaveCheckpointDialog(self.controller, parent=self)
        if dlg.exec() == QDialog.Accepted:
            self._populate_table()

    def _on_restore(self):
        cp = self._selected_checkpoint()
        if not cp:
            return
        result = QMessageBox.warning(
            self, "Confirm Restore",
            f"Restore '{cp['label']}' from {cp['date']}?\n\nAll current data will be replaced. Unsaved changes will be lost.",
            QMessageBox.Ok | QMessageBox.Cancel,
            QMessageBox.Cancel,
        )
        if result == QMessageBox.Ok:
            success = self.controller.load_checkpoint(cp["filename"])
            if success:
                QMessageBox.information(
                    self, "Restore Complete",
                    f"Restored from '{cp['label']}'.",
                )
                self.accept()
            else:
                QMessageBox.critical(
                    self, "Restore Failed",
                    "Could not restore the checkpoint.",
                )

    def _on_delete(self):
        cp = self._selected_checkpoint()
        if not cp:
            return
        result = QMessageBox.warning(
            self, "Confirm Delete",
            f"Delete checkpoint '{cp['label']}'?\nThis cannot be undone.",
            QMessageBox.Ok | QMessageBox.Cancel,
            QMessageBox.Cancel,
        )
        if result == QMessageBox.Ok:
            success = self.controller.delete_checkpoint(cp["filename"])
            if success:
                self._populate_table()
            else:
                QMessageBox.critical(
                    self, "Delete Failed", "Could not delete the checkpoint file.",
                )


