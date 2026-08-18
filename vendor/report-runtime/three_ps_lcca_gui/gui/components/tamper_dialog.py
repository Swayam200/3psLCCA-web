# gui/components/tamper_dialog.py

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QTreeWidget,
    QTreeWidgetItem,
    QTabWidget,
    QWidget,
    QTextEdit,
    QFileDialog,
    QMessageBox,
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont, QColor
from three_ps_lcca_gui.gui.themes import get_token


class VerifyWorker(QThread):
    """Runs full verification in background thread."""

    finished = Signal(dict)

    def __init__(self, engine):
        super().__init__()
        self.engine = engine

    def run(self):
        result = self.engine.verify_full()
        self.finished.emit(result)


class TamperDialog(QDialog):
    """
    Project integrity and tamper detection dialog.
    Accessible from File menu → Verify Integrity.
    Shows:
      - Full verification results
      - Tamper log
      - Key export/import
    """

    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self._worker = None

        self.setWindowTitle("Project Integrity")
        self.setMinimumWidth(560)
        self.setMinimumHeight(480)
        self.setModal(True)

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Title
        title = QLabel(f"Project Integrity - {self.engine.display_name}")
        f = QFont()
        f.setPointSize(11)
        f.setBold(True)
        title.setFont(f)
        layout.addWidget(title)

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.addTab(self._make_verify_tab(), "Verification")
        self.tabs.addTab(self._make_tamper_log_tab(), "Tamper Log")
        self.tabs.addTab(self._make_key_tab(), "Key Management")
        layout.addWidget(self.tabs)

        # Close button
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setFixedHeight(34)
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    # ── Verification tab ──────────────────────────────────────────────────────

    def _make_verify_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(10)

        info = QLabel(
            "Runs a full integrity check on all project files, "
            "objects, and checkpoints."
        )
        info.setWordWrap(True)
        info.setEnabled(False)
        layout.addWidget(info)

        self.verify_btn = QPushButton("▶  Run Full Verification")
        self.verify_btn.setFixedHeight(36)
        self.verify_btn.clicked.connect(self._run_verify)
        layout.addWidget(self.verify_btn)

        layout.addWidget(self._divider())

        # Results tree
        self.result_tree = QTreeWidget()
        self.result_tree.setHeaderHidden(True)
        self.result_tree.setMinimumHeight(220)
        layout.addWidget(self.result_tree)

        return w

    def _run_verify(self):
        self.verify_btn.setEnabled(False)
        self.verify_btn.setText("Running...")
        self.result_tree.clear()

        self._worker = VerifyWorker(self.engine)
        self._worker.finished.connect(self._on_verify_done)
        self._worker.start()

    def _on_verify_done(self, report: dict):
        self.verify_btn.setEnabled(True)
        self.verify_btn.setText("▶  Run Full Verification")
        self.result_tree.clear()

        passed = report.get("passed", False)

        # Overall status
        status_item = QTreeWidgetItem(self.result_tree)
        status_item.setText(
            0, "✅  All checks passed" if passed else "❌  Issues found"
        )
        f = QFont()
        f.setBold(True)
        status_item.setFont(0, f)
        status_item.setForeground(0, QColor(get_token("success")) if passed else QColor(get_token("danger")))

        # Manifest
        mf_item = QTreeWidgetItem(self.result_tree)
        mf_item.setText(0, "Manifest")
        self._add_check(
            mf_item, "manifest.json readable", report.get("manifest_ok", False)
        )
        self._add_check(
            mf_item, "Signature valid", report.get("manifest_signed", False)
        )
        self._add_check(
            mf_item, "Not tampered", not report.get("manifest_tampered", False)
        )

        # Objects
        obj_item = QTreeWidgetItem(self.result_tree)
        obj_item.setText(0, "Object Store")
        self._add_check(
            obj_item, "All objects present", report.get("objects_ok", False)
        )

        missing = report.get("missing_chunks", [])
        tampered = report.get("tampered_objects", [])
        if missing:
            for c in missing:
                m = QTreeWidgetItem(obj_item)
                m.setText(0, f"  ⚠ Missing: {c}")
                m.setForeground(0, QColor(get_token("warning")))
        if tampered:
            for c in tampered:
                t = QTreeWidgetItem(obj_item)
                t.setText(0, f"  ❌ Tampered: {c}")
                t.setForeground(0, QColor(get_token("danger")))

        # Checkpoints
        cp_item = QTreeWidgetItem(self.result_tree)
        cp_item.setText(0, "Checkpoints")
        ok = report.get("checkpoints_ok", 0)
        bad = report.get("checkpoints_tampered", 0)
        uns = report.get("checkpoints_unsigned", 0)
        self._add_child(cp_item, f"Verified: {ok}")
        if bad:
            b = QTreeWidgetItem(cp_item)
            b.setText(0, f"  ❌ Tampered: {bad}")
            b.setForeground(0, QColor(get_token("danger")))
        if uns:
            self._add_child(cp_item, f"  ℹ Unsigned (legacy): {uns}")

        # Tamper log
        tl_item = QTreeWidgetItem(self.result_tree)
        tl_item.setText(
            0, f"Tamper Log - {report.get('tamper_log_entries', 0)} entries"
        )

        self.result_tree.expandAll()

        # Refresh tamper log tab
        self._load_tamper_log()

    def _add_check(self, parent: QTreeWidgetItem, label: str, ok: bool):
        item = QTreeWidgetItem(parent)
        item.setText(0, f"{'✅' if ok else '❌'}  {label}")
        item.setForeground(0, QColor(get_token("success")) if ok else QColor(get_token("danger")))

    def _add_child(self, parent: QTreeWidgetItem, text: str):
        item = QTreeWidgetItem(parent)
        item.setText(0, text)

    # ── Tamper log tab ────────────────────────────────────────────────────────

    def _make_tamper_log_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(8)

        info = QLabel("Append-only record of all detected integrity violations.")
        info.setEnabled(False)
        layout.addWidget(info)

        self.tamper_log_tree = QTreeWidget()
        self.tamper_log_tree.setHeaderLabels(["Timestamp", "Event", "Details"])
        self.tamper_log_tree.setColumnWidth(0, 140)
        self.tamper_log_tree.setColumnWidth(1, 160)
        layout.addWidget(self.tamper_log_tree)

        refresh_btn = QPushButton("↻  Refresh")
        refresh_btn.setFixedHeight(30)
        refresh_btn.clicked.connect(self._load_tamper_log)
        layout.addWidget(refresh_btn)

        self._load_tamper_log()
        return w

    def _load_tamper_log(self):
        self.tamper_log_tree.clear()
        entries = self.engine.read_tamper_log()
        if not entries:
            placeholder = QTreeWidgetItem(self.tamper_log_tree)
            placeholder.setText(0, "No tamper events recorded.")
            placeholder.setForeground(0, QColor(get_token("text_secondary")))
            return

        for entry in entries:
            item = QTreeWidgetItem(self.tamper_log_tree)
            item.setText(0, entry.get("timestamp", ""))
            item.setText(1, entry.get("reason", ""))
            item.setText(2, entry.get("details", ""))
            item.setForeground(1, QColor(get_token("danger")))

    # ── Key management tab ────────────────────────────────────────────────────

    def _make_key_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(12)
        layout.setContentsMargins(8, 12, 8, 8)

        info = QLabel(
            "The project key is used to verify that project files have not been "
            "modified outside this application.\n\n"
            "If you move this project to another machine, export the key and "
            "import it on the destination machine."
        )
        info.setWordWrap(True)
        info.setEnabled(False)
        layout.addWidget(info)

        layout.addWidget(self._divider())

        # Key status
        key_exists = self.engine.key_file.exists()
        status_lbl = QLabel(
            f"{'✅  Project key present.' if key_exists else '⚠  No key found - signatures disabled.'}"
        )
        status_lbl.setForeground = lambda c: None
        layout.addWidget(status_lbl)

        layout.addSpacing(8)

        # Export button
        export_btn = QPushButton("Export Key...")
        export_btn.setFixedHeight(34)
        export_btn.setEnabled(key_exists)
        export_btn.clicked.connect(self._export_key)
        layout.addWidget(export_btn)

        # Import button
        import_btn = QPushButton("Import Key...")
        import_btn.setFixedHeight(34)
        import_btn.clicked.connect(self._import_key)
        layout.addWidget(import_btn)

        # Re-sign button
        resign_btn = QPushButton("Re-sign All (use after key import)")
        resign_btn.setFixedHeight(34)
        resign_btn.clicked.connect(self._resign_all)
        layout.addWidget(resign_btn)

        layout.addStretch()
        return w

    def _export_key(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Project Key",
            f"{self.engine.project_id}_key.json",
            "Key Files (*.json)",
        )
        if path:
            if self.engine.export_key(path):
                QMessageBox.information(
                    self,
                    "Key Exported",
                    f"Key saved to:\n{path}\n\nKeep this file secure.",
                )
            else:
                QMessageBox.warning(
                    self, "Export Failed", "Could not export key."
                )

    def _import_key(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Project Key", "", "Key Files (*.json)"
        )
        if path:
            if self.engine.import_key(path):
                QMessageBox.information(
                    self,
                    "Key Imported",
                    "Key imported. Use 'Re-sign All' to update file signatures.",
                )
            else:
                QMessageBox.warning(
                    self, "Import Failed", "Could not import key - file may be invalid."
                )

    def _resign_all(self):
        reply = QMessageBox.question(
            self,
            "Re-sign All Files",
            "Re-sign the manifest and all checkpoints with the current key?\n\nContinue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            try:
                # Re-sign manifest
                manifest = json.loads(self.engine.manifest_path.read_text())
                self.engine._sign_manifest(manifest)

                # Re-sign all checkpoints
                resigned = 0
                for cp in self.engine.checkpoint_path.glob("*.zip"):
                    import hashlib, hmac as _hmac

                    key = self.engine._load_or_create_key()
                    zip_data = cp.read_bytes()
                    sig = _hmac.new(key, zip_data, hashlib.sha256).hexdigest()
                    (self.engine.checkpoint_path / f"{cp.name}.sig").write_text(sig)
                    resigned += 1

                QMessageBox.information(
                    self,
                    "Re-signed",
                    f"Manifest and {resigned} checkpoint(s) re-signed.",
                )
            except Exception as e:
                QMessageBox.warning(self, "Re-sign Failed", str(e))

    @staticmethod
    def _divider() -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        return line


