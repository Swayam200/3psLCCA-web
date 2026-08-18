"""
gui/components/rollback_dialog.py

Per-chunk rollback dialog.
Lists all chunks, shows the 3 available copies (current / previous / earlier),
and lets the user restore any one of them.
"""

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QFrame,
    QMessageBox,
    QAbstractItemView,
    QSplitter,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor
from three_ps_lcca_gui.gui.themes import get_token


class RollbackDialog(QDialog):
    """
    Two-panel dialog:
      Left  - list of all chunks in the project
      Right - available rollback copies for the selected chunk
    """

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self._options = []  # rollback options for currently selected chunk

        self.setWindowTitle("Version Rollback")
        self.setMinimumSize(600, 380)
        self.setModal(True)

        self._build_ui()
        self._load_chunks()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header
        header = QLabel("Version Rollback")
        f = QFont()
        f.setPointSize(12)
        f.setBold(True)
        header.setFont(f)
        layout.addWidget(header)

        desc = QLabel(
            "Select a chunk on the left, then choose which saved version to restore on the right.\n"
            "Only the selected chunk is affected - all other data stays unchanged."
        )
        desc.setWordWrap(True)
        desc.setEnabled(False)
        layout.addWidget(desc)

        layout.addWidget(self._divider())

        # Two-panel splitter
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)

        # Left: chunk list
        left = QFrame()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)
        left_layout.addWidget(self._section_label("Chunks"))
        self.chunk_list = QListWidget()
        self.chunk_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.chunk_list.currentItemChanged.connect(self._on_chunk_selected)
        left_layout.addWidget(self.chunk_list)
        splitter.addWidget(left)

        # Right: versions for selected chunk
        right = QFrame()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(4)
        right_layout.addWidget(self._section_label("Available Versions"))
        self.version_list = QListWidget()
        self.version_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.version_list.currentItemChanged.connect(self._on_version_selected)
        right_layout.addWidget(self.version_list)
        splitter.addWidget(right)

        splitter.setSizes([200, 380])
        layout.addWidget(splitter, stretch=1)

        layout.addWidget(self._divider())

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.rollback_btn = QPushButton("↩  Roll Back to Selected Version")
        self.rollback_btn.setFixedHeight(36)
        self.rollback_btn.setEnabled(False)
        self.rollback_btn.clicked.connect(self._do_rollback)
        btn_row.addWidget(self.rollback_btn)

        btn_row.addStretch()

        close_btn = QPushButton("Close")
        close_btn.setFixedHeight(36)
        close_btn.clicked.connect(self.reject)
        btn_row.addWidget(close_btn)

        layout.addLayout(btn_row)

    # ── Data ──────────────────────────────────────────────────────────────────

    def _load_chunks(self):
        self.chunk_list.clear()
        chunks = sorted(self.controller.list_chunks())
        if not chunks:
            placeholder = QListWidgetItem("No chunks found.")
            placeholder.setFlags(placeholder.flags() & ~Qt.ItemIsSelectable)
            placeholder.setForeground(QColor(get_token("text_secondary")))
            self.chunk_list.addItem(placeholder)
            return
        for name in chunks:
            self.chunk_list.addItem(QListWidgetItem(name))

    def _on_chunk_selected(self, current, _previous):
        self.version_list.clear()
        self.rollback_btn.setEnabled(False)
        self._options = []

        if not current:
            return

        chunk_name = current.text()
        options = self.controller.get_rollback_options(chunk_name)
        self._options = options

        for opt in options:
            text = f"{opt['label']}  -  {opt['saved_at']}"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, opt)
            # Grey out "Current" slightly to indicate it's already active
            if opt["label"] == "Current":
                item.setForeground(QColor(get_token("text_secondary")))
            self.version_list.addItem(item)

    def _on_version_selected(self, current, _previous):
        if not current:
            self.rollback_btn.setEnabled(False)
            return
        opt = current.data(Qt.UserRole)
        # Can't "roll back" to current - it's already the current state
        is_current = opt and opt.get("label") == "Current"
        self.rollback_btn.setEnabled(not is_current)

    def _do_rollback(self):
        chunk_item = self.chunk_list.currentItem()
        version_item = self.version_list.currentItem()
        if not chunk_item or not version_item:
            return

        chunk_name = chunk_item.text()
        opt = version_item.data(Qt.UserRole)
        if not opt:
            return

        result = QMessageBox.warning(
            self,
            "Confirm Rollback",
            f"Roll back '{chunk_name}' to '{opt['label']}' ({opt['saved_at']})?\n\nThis replaces the current version. Other chunks are not affected.",
            QMessageBox.Ok | QMessageBox.Cancel,
            QMessageBox.Cancel,
        )
        if result != QMessageBox.Ok:
            return

        success = self.controller.rollback_chunk(chunk_name, opt["path"])
        if success:
            QMessageBox.information(
                self,
                "Rollback Complete",
                f"'{chunk_name}' rolled back to '{opt['label']}'.",
            )
            # Refresh version list to reflect new state
            self._load_chunks()
            self.version_list.clear()
            self.rollback_btn.setEnabled(False)
        else:
            QMessageBox.critical(
                self,
                "Rollback Failed",
                "Could not roll back this chunk.",
            )

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _section_label(text: str) -> QLabel:
        lbl = QLabel(text.upper())
        f = QFont()
        f.setPointSize(8)
        f.setBold(True)
        lbl.setFont(f)
        lbl.setEnabled(False)
        return lbl

    @staticmethod
    def _divider() -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        return line


