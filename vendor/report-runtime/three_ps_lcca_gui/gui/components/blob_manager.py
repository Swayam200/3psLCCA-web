"""
gui/components/blob_manager.py

Blob Manager dialog - browse, upload, download, and delete binary files
(images, PDFs, ZIPs, etc.) stored in the project's blob storage.
"""

import os
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
    QFrame,
    QMessageBox,
    QFileDialog,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor
from three_ps_lcca_gui.gui.themes import get_token
from three_ps_lcca_gui.gui.components.utils.table_widgets import round_table_viewport


class BlobManagerDialog(QDialog):
    """
    Lists all blobs stored in the project.
    Supports upload (store_blob), download (fetch_blob + save), and delete.
    """

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller

        self.setWindowTitle("Blob Manager")
        self.setMinimumSize(620, 420)
        self.setModal(True)

        self._build_ui()
        self._load_blobs()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header
        header = QLabel("Blob Manager")
        f = QFont()
        f.setPointSize(12)
        f.setBold(True)
        header.setFont(f)
        layout.addWidget(header)

        desc = QLabel(
            "Binary files (images, PDFs, ZIPs, etc.) attached to this project. "
            "Blobs are stored separately from chunk data and written directly to disk."
        )
        desc.setWordWrap(True)
        desc.setEnabled(False)
        layout.addWidget(desc)

        layout.addWidget(self._divider())

        # Table
        self.table = QTableWidget()
        round_table_viewport(self.table)
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Name", "Size", "Saved At"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.selectionModel().selectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self.table)

        layout.addWidget(self._divider())

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        upload_btn = QPushButton("Upload File...")
        upload_btn.setFixedHeight(34)
        upload_btn.clicked.connect(self._upload)
        btn_row.addWidget(upload_btn)

        btn_row.addStretch()

        self.download_btn = QPushButton("Download...")
        self.download_btn.setFixedHeight(34)
        self.download_btn.setEnabled(False)
        self.download_btn.clicked.connect(self._download)
        btn_row.addWidget(self.download_btn)

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setFixedHeight(34)
        self.delete_btn.setEnabled(False)
        self.delete_btn.setStyleSheet(
            f"QPushButton:enabled {{ color: {get_token('danger')}; border-color: {get_token('danger')}; }}"
            f"QPushButton:enabled:hover {{ background-color: {get_token('danger')}; color: {get_token('base')}; }}"
        )
        self.delete_btn.clicked.connect(self._delete)
        btn_row.addWidget(self.delete_btn)

        close_btn = QPushButton("Close")
        close_btn.setFixedHeight(34)
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)

        layout.addLayout(btn_row)

    # ── Data ──────────────────────────────────────────────────────────────────

    def _load_blobs(self):
        self.table.setRowCount(0)
        blobs = self.controller.engine.list_blobs() if self.controller.engine else []

        if not blobs:
            self.table.setRowCount(1)
            placeholder = QTableWidgetItem("No blobs stored. Click 'Upload File...' to add one.")
            placeholder.setForeground(QColor(get_token("text_secondary")))
            self.table.setItem(0, 0, placeholder)
            self.table.setSpan(0, 0, 1, 3)
            return

        self.table.setRowCount(len(blobs))
        for row, blob in enumerate(blobs):
            self.table.setItem(row, 0, QTableWidgetItem(blob["blob_name"]))
            self.table.setItem(row, 1, QTableWidgetItem(f"{blob['size_kb']} KB"))
            self.table.setItem(row, 2, QTableWidgetItem(blob["saved_at"]))

    def _on_selection_changed(self):
        has = bool(self.table.selectedItems()) and self.table.rowCount() > 0
        # Only enable if real data row (not placeholder span)
        has = has and self.table.columnSpan(self.table.currentRow(), 0) == 1
        self.download_btn.setEnabled(has)
        self.delete_btn.setEnabled(has)

    def _selected_blob_name(self) -> str | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if not item or self.table.columnSpan(row, 0) > 1:
            return None
        return item.text()

    # ── Actions ───────────────────────────────────────────────────────────────

    def _upload(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Upload Files",
            "",
            "All Files (*)",
        )
        if not paths:
            return

        uploaded = []
        failed = []
        for path in paths:
            name = self.controller.engine.store_blob(path)
            if name:
                uploaded.append(name)
            else:
                failed.append(os.path.basename(path))

        self._load_blobs()

        if failed:
            QMessageBox.warning(
                self,
                "Upload Partial",
                f"Uploaded {len(uploaded)} file(s).\n\nFailed: {', '.join(failed)}",
            )
        elif uploaded:
            QMessageBox.information(
                self,
                "Upload Complete",
                f"Uploaded {len(uploaded)} file(s):\n" + "\n".join(uploaded),
            )

    def _download(self):
        blob_name = self._selected_blob_name()
        if not blob_name:
            return

        dest, _ = QFileDialog.getSaveFileName(
            self,
            "Save File",
            blob_name,
            "All Files (*)",
        )
        if not dest:
            return

        data = self.controller.engine.fetch_blob(blob_name)
        if data is None:
            QMessageBox.critical(self, "Download Failed", f"Could not read '{blob_name}'.")
            return

        try:
            with open(dest, "wb") as f:
                f.write(data)
            QMessageBox.information(self, "Download Complete", f"Saved to:\n{dest}")
        except Exception as e:
            QMessageBox.critical(self, "Download Failed", f"Could not write file:\n{e}")

    def _delete(self):
        blob_name = self._selected_blob_name()
        if not blob_name:
            return

        result = QMessageBox.warning(
            self,
            "Delete Blob",
            f"Delete '{blob_name}'?\nThis cannot be undone.",
            QMessageBox.Ok | QMessageBox.Cancel,
            QMessageBox.Cancel,
        )
        if result != QMessageBox.Ok:
            return

        if self.controller.engine.delete_blob(blob_name):
            self._load_blobs()
        else:
            QMessageBox.critical(self, "Delete Failed", f"Could not delete '{blob_name}'.")

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _divider() -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        return line


