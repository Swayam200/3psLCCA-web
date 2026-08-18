from PySide6.QtWidgets import (
    QTabWidget,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QStackedWidget,
    QFileDialog,
    QMessageBox,
)
from PySide6.QtCore import QThread, Signal, QSize
from PySide6.QtGui import QPalette, QColor
from ..utils.icons import make_icon
from three_ps_lcca_gui.gui.themes import get_token
from ..utils.validation_helpers import LOCK_TOOLTIP, freeze_widgets
from .excel_importer import parse_excel, verify_schema, ImportPreviewWindow
from .excel_exporter import EXPORT_FORMATS, format_available, export_all_chunks, count_active_all
from .widgets.foundation import FoundationWidget
from .widgets.super_structure import SuperStructureWidget
from .widgets.substructure import SubStructureWidget
from .widgets.misc_widget import MiscWidget
from .widgets.trash_tab import TrashTabWidget


_PAGES = [
    ("Foundation", "str_foundation"),
    ("Sub-Structure", "str_sub_structure"),
    ("Super-Structure", "str_super_structure"),
    ("Miscellaneous", "str_misc"),
]


class _ExcelParseWorker(QThread):
    """Runs parse_excel + verify_schema off the main thread."""

    finished = Signal(dict)  # emits verified parsed data
    error = Signal(str)  # emits error message string

    def __init__(self, path: str, parent=None):
        super().__init__(parent)
        self._path = path

    def run(self):
        try:
            result = parse_excel(self._path)
            if not result["materials"]:
                self.error.emit("empty")
                return
            result["materials"] = verify_schema(result["materials"])
            self.finished.emit(result)
        except Exception as exc:
            self.error.emit(str(exc))


class StructureTabView(QWidget):
    tab_changed = Signal(str)  # emits the tab name when user clicks a tab

    def __init__(self, controller=None):
        super().__init__()
        self.setObjectName("StructureTabView")  # For identification in Manager
        self.controller = controller
        self._loaded = False
        if controller and hasattr(controller, "project_loaded"):
            controller.project_loaded.connect(self._on_project_reloaded)

        self.main_layout = QVBoxLayout(self)

        # --- TOP AREA ---
        top_area = QWidget()
        top_layout = QHBoxLayout(top_area)

        region_info = QVBoxLayout()
        region_info.addWidget(QLabel("<b>Construction Works Data</b>"))
        region_info.addWidget(QLabel("Project: Active Analysis"))
        top_layout.addLayout(region_info)

        top_layout.addStretch()

        # Action Buttons
        self.excel_btn = QPushButton("  Import Excel")
        self.excel_btn.setIcon(make_icon("download"))
        self.excel_btn.setIconSize(QSize(18, 18))

        self.download_btn = QPushButton("  Export Excel")
        self.download_btn.setIcon(make_icon("upload"))
        self.download_btn.setIconSize(QSize(18, 18))
        self.trash_btn = QPushButton("🗑️")

        top_layout.addWidget(self.excel_btn)
        top_layout.addWidget(self.download_btn)
        top_layout.addWidget(self.trash_btn)

        self.main_layout.addWidget(top_area)

        # --- CONTENT AREA (Tabs + Trash View) ---
        self.content_stack = QStackedWidget()

        # 1. Active Tabs
        self.tab_view = QTabWidget()

        # QTabWidget's content pane paints using Base palette role, which differs
        # from Window in dark mode. Copy Window → Base so both are identical.
        palette = self.tab_view.palette()
        palette.setColor(QPalette.Base, palette.color(QPalette.Window))
        self.tab_view.setPalette(palette)

        self.foundation_tab = FoundationWidget(controller=controller)
        self.substructure_tab = SubStructureWidget(controller=controller)
        self.superstructure_tab = SuperStructureWidget(controller=controller)
        self.misc_tab = MiscWidget(controller=controller)

        self.tab_view.addTab(self.foundation_tab, "Foundation")
        self.tab_view.addTab(self.substructure_tab, "Sub-Structure")
        self.tab_view.addTab(self.superstructure_tab, "Super-Structure")
        self.tab_view.addTab(self.misc_tab, "Miscellaneous")

        # 2. Trash View
        self.trash_view = TrashTabWidget(controller=controller)

        self.content_stack.addWidget(self.tab_view)  # Index 0
        self.content_stack.addWidget(self.trash_view)  # Index 1

        self.main_layout.addWidget(self.content_stack)

        # --- CONNECTIONS ---
        for tab in (self.foundation_tab, self.substructure_tab, self.superstructure_tab, self.misc_tab):
            tab.total_changed.connect(self._save_str_summary)

        self.excel_btn.clicked.connect(self._open_excel_import)
        self.download_btn.clicked.connect(self._download_excel)
        self.trash_btn.clicked.connect(self.toggle_trash_view)
        self.tab_view.currentChanged.connect(self._on_tab_changed)

    def _save_str_summary(self):
        if not self.controller or not self.controller.engine:
            return

        def _tab_data(tab) -> dict:
            return {
                "total":      getattr(tab, "_computed_total",      0.0),
                "items":      getattr(tab, "_computed_count",       0),
                "components": getattr(tab, "_computed_components",  0),
            }

        foundation    = _tab_data(self.foundation_tab)
        substructure  = _tab_data(self.substructure_tab)
        super_str     = _tab_data(self.superstructure_tab)
        misc          = _tab_data(self.misc_tab)

        self.controller.engine.stage_update(chunk_name="str_summary", data={
            "foundation":      foundation,
            "substructure":    substructure,
            "super_structure": super_str,
            "misc":            misc,
            "grand_total":     foundation["total"] + substructure["total"] + super_str["total"] + misc["total"],
            "total_items":     foundation["items"] + substructure["items"] + super_str["items"] + misc["items"],
        })

    def on_refresh(self):
        """Refreshes all active tabs and updates the global trash count."""
        # SAFETY GUARD: Ensure controller and engine are ready before fetching
        if (
            not self.controller
            or not hasattr(self.controller, "engine")
            or not self.controller.engine
        ):
            return

        # Refresh all nested managers (this triggers their fetch_chunk calls)
        self.foundation_tab.on_refresh()
        self.substructure_tab.on_refresh()
        self.superstructure_tab.on_refresh()
        self.misc_tab.on_refresh()

        # Update the counter whenever the main view refreshes
        self.update_trash_count()

        # If we are looking at the trash stack, refresh that too
        if self.content_stack.currentIndex() == 1:
            self.trash_view.on_refresh()

    def refresh_trash_only(self):
        """Lightweight refresh for trash operations."""
        if self.content_stack.currentIndex() == 1:
            self.trash_view.on_refresh()
        self.update_trash_count()

    def refresh_tab_by_chunk(self, chunk_id: str):
        """Refreshes only the tab associated with a specific chunk ID."""
        mapping = {
            "str_foundation": self.foundation_tab,
            "str_sub_structure": self.substructure_tab,
            "str_super_structure": self.superstructure_tab,
            "str_misc": self.misc_tab,
        }
        tab = mapping.get(chunk_id)
        if tab:
            tab.on_refresh()
        self.update_trash_count()

    def showEvent(self, event):
        """Qt event triggered when the widget is shown."""
        super().showEvent(event)
        if not self._loaded:
            self.on_refresh()
            self._loaded = True

    def _on_project_reloaded(self):
        self._loaded = False
        if self.isVisible():
            self.on_refresh()
            self._loaded = True

    def toggle_trash_view(self):
        """Swaps between normal tabs and the Trash list."""
        if self.content_stack.currentIndex() == 0:
            self.trash_view.on_refresh()
            self.content_stack.setCurrentIndex(1)
            self.excel_btn.setVisible(False)
            self.download_btn.setVisible(False)
        else:
            self.content_stack.setCurrentIndex(0)
            self.excel_btn.setVisible(True)
            self.download_btn.setVisible(True)

        self.update_trash_count()

    def update_trash_count(self):
        """Calculates total trashed items and updates the button text."""
        if not self.controller or not self.controller.engine:
            return

        # Change button text if we are currently inside the trash view
        if self.content_stack.currentIndex() == 1:
            self.trash_btn.setText("Back to Work")
            self.trash_btn.setStyleSheet(f"color: {get_token('success')};")
            return
        
        self.trash_btn.setStyleSheet("")

        total_count = 0
        chunks = [
            "str_foundation",
            "str_sub_structure",
            "str_super_structure",
            "str_misc",
        ]

        for chunk_id in chunks:
            data = self.controller.engine.fetch_chunk(chunk_id) or {}
            for group_name, items in data.items():
                for item in items:
                    if item.get("state", {}).get("in_trash"):
                        total_count += 1

        if total_count > 0:
            self.trash_btn.setText(f"🗑️ ({total_count})")
        else:
            self.trash_btn.setText("🗑️")

    def _open_excel_import(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select File",
            "",
            "All Supported (*.xlsx *.xls *.ods);;Excel Files (*.xlsx *.xls);;OpenDocument Spreadsheet (*.ods)",
        )
        if not path:
            return

        self.excel_btn.setEnabled(False)
        self.excel_btn.setText("Parsing…")

        self._excel_worker = _ExcelParseWorker(path, parent=self)
        self._excel_worker.finished.connect(self._on_excel_parsed)
        self._excel_worker.error.connect(self._on_excel_error)
        self._excel_worker.start()

    def _on_excel_parsed(self, result: dict):
        self.excel_btn.setEnabled(True)
        self.excel_btn.setText("  Import Excel")

        materials = result["materials"]
        metadata = result.get("metadata", [])

        # Warn about sheets routed to Misc
        fallback_sheets = [
            s
            for s, rows in materials.items()
            if rows and rows[0].get("_is_fallback_chunk")
        ]
        if fallback_sheets:
            names = ", ".join(f'"{s}"' for s in fallback_sheets)
            QMessageBox.information(
                self,
                "Unrecognised Sheet(s)",
                f"These sheets didn't match a known category and will be added to <b>Misc</b>:<br><br>{names}",
            )

        preview = ImportPreviewWindow(materials, manager=self.foundation_tab, metadata=metadata, parent=self)
        preview.showMaximized()
        if preview.exec():
            self.on_refresh()

    def _on_excel_error(self, msg: str):
        self.excel_btn.setEnabled(True)
        self.excel_btn.setText("  Import Excel")
        if msg == "empty":
            QMessageBox.warning(
                self, "Empty File", "No data found in the selected file."
            )
        else:
            QMessageBox.critical(self, "Parse Error", msg)

    def _download_excel(self):
        if not self.controller or not self.controller.engine:
            QMessageBox.warning(self, "No Project", "Open a project before exporting.")
            return

        if count_active_all(self.controller.engine) == 0:
            QMessageBox.information(
                self,
                "Nothing to Export",
                "No active materials found.\nAdd materials first, or restore items from Trash.",
            )
            return

        available_fmts = [f for f in EXPORT_FORMATS if format_available(f)[0]]
        file_filter = ";;".join(f["filter"] for f in available_fmts)

        import datetime as _dt, re
        gi = self.controller.engine.fetch_chunk("general_info") or {}
        _proj = gi.get("project_name", "").strip()
        _safe = re.sub(r'[\\/:*?"<>|]+', "_", _proj) if _proj else "construction_works"
        _default_name = f"{_safe}_{_dt.date.today().isoformat()}"

        path, selected_filter = QFileDialog.getSaveFileName(
            self, "Save Construction Works Data", _default_name, file_filter
        )
        if not path:
            return

        fmt = next((f for f in available_fmts if f["filter"] == selected_filter), available_fmts[0])
        if not path.endswith(fmt["ext"]):
            path += fmt["ext"]

        self.download_btn.setEnabled(False)
        self.download_btn.setText("Exporting…")
        try:
            total, sheets = export_all_chunks(self.controller.engine, path, fmt)
            self.download_btn.setEnabled(True)
            self.download_btn.setText("  Export Excel")
            QMessageBox.information(
                self,
                "Export Complete",
                f"{total} row(s) exported across {len(sheets)} sheet(s).\n\nFile saved to:\n{path}",
            )
        except Exception as exc:
            self.download_btn.setEnabled(True)
            self.download_btn.setText("  Export Excel")
            QMessageBox.critical(self, "Export Error", str(exc))

    def freeze(self, frozen: bool = True):
        freeze_widgets(frozen, self.excel_btn)
        for tab in (
            self.foundation_tab,
            self.substructure_tab,
            self.superstructure_tab,
            self.misc_tab,
        ):
            if hasattr(tab, "freeze"):
                tab.freeze(frozen)

    def validate(self) -> dict:
        """
        Called by OutputsPage when Validate is clicked.

        Collects all structure data, computes component-wise and page-wise
        totals, then returns warnings when:
          - the grand total is zero (nothing entered / all trashed), or
          - items are sitting in Trash (excluded from calculations).
        """
        if not self.controller or not self.controller.engine:
            return {"errors": [], "warnings": []}

        page_totals: dict[str, float] = {}
        grand_total = 0.0
        trash_count = 0

        for page_name, chunk_id in _PAGES:
            chunk_data = self.controller.engine.fetch_chunk(chunk_id) or {}
            page_total = 0.0

            for comp_name, items in chunk_data.items():
                comp_total = 0.0
                for item in items:
                    if item.get("state", {}).get("in_trash", False):
                        trash_count += 1
                        continue
                    v = item.get("values", {})
                    qty = float(v.get("quantity") or 0)
                    rate = float(v.get("rate") or 0)
                    comp_total += qty * rate
                page_total += comp_total

            page_totals[page_name] = page_total
            grand_total += page_total

        warnings = []

        if grand_total == 0.0:
            breakdown = "  |  ".join(f"{name}: 0" for name, _ in _PAGES)
            warnings.append(
                f"Total construction cost is 0 - no material quantities or rates have been entered, "
                f"or all items are in the Trash and excluded from the analysis. Tab breakdown: {breakdown}"
            )
        else:
            # Show page-wise breakdown only when total is suspicious (any page is zero)
            zero_pages = [name for name, total in page_totals.items() if total == 0.0]
            if zero_pages:
                warnings.append(
                    "No materials entered in the following structure tabs (cost is 0): "
                    + ", ".join(zero_pages)
                    + " - add items or check if entries are in the Trash"
                )

        if trash_count > 0:
            warnings.append(
                f"{trash_count} item{'s' if trash_count != 1 else ''} "
                f"in the Trash - excluded from all cost calculations. "
                f"Open the Trash view to review and restore them if needed."
            )

        return {"errors": [], "warnings": warnings}

    def get_data(self) -> dict:
        """
        Called by OutputsPage when Proceed with Calculation is clicked.

        Returns a single dict with raw items per tab, component-wise totals,
        page-wise totals, and the overall grand total.
        """

        pages_data = {}
        grand_total = 0.0

        if self.controller and self.controller.engine:
            for page_name, chunk_id in _PAGES:
                chunk_data = self.controller.engine.fetch_chunk(chunk_id) or {}
                page_total = 0.0
                components = {}

                for comp_name, items in chunk_data.items():
                    comp_total = 0.0
                    active_items = []
                    for item in items:
                        if item.get("state", {}).get("in_trash", False):
                            continue
                        v = item.get("values", {})
                        qty = float(v.get("quantity", 0) or 0)
                        rate = float(v.get("rate", 0) or 0)
                        item_total = qty * rate
                        comp_total += item_total
                        active_items.append({**item, "total": item_total})
                    components[comp_name] = {
                        "items": active_items,
                        "total": comp_total,
                    }
                    page_total += comp_total

                pages_data[page_name] = {
                    "components": components,
                    "total": page_total,
                }
                grand_total += page_total

        return {
            "chunk": "construction_work_data",
            "data": {
                **pages_data,
                "grand_total": grand_total,
            },
        }

    def _on_tab_changed(self, index: int):
        name = self.tab_view.tabText(index)
        self.tab_changed.emit(name)

    def reset_view(self):
        """Resets the view to normal tabs (exits Trash view)."""
        if self.content_stack.currentIndex() == 1:
            self.content_stack.setCurrentIndex(0)
            self.trash_btn.setStyleSheet("")
            self.update_trash_count()

    def select_tab(self, name: str):
        """External helper to switch tabs (e.g., from a Sidebar)."""
        mapping = {
            "Foundation": 0,
            "Sub-Structure": 1,
            "Super-Structure": 2,
            "Miscellaneous": 3,
        }
        idx = mapping.get(name)
        if idx is not None:
            self.content_stack.setCurrentIndex(0)
            self.tab_view.setCurrentIndex(idx)


