"""
Report Section Selection Dialog - Hierarchical tree for choosing PDF report sections.

Adapted from lcca_gui.py SectionTreeWidget for use as a modal dialog within
the main 3psLCCA GUI application.
"""

import sys
import os
import shutil
import tempfile
import traceback


from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QScrollArea,
    QTreeWidget,
    QTreeWidgetItem,
    QMessageBox,
    QApplication,
    QFileDialog,
    QSizePolicy,
    QWidget,
    QStyle,
)
from PySide6.QtCore import Qt, Signal, QThread, QSize, QRect, QStandardPaths, QTimer, QVariantAnimation, QEasingCurve
from PySide6.QtGui import QPainter, QColor, QPalette

from three_ps_lcca_gui.gui.themes import get_token, theme_manager
from three_ps_lcca_gui.gui.theme import (
    FS_DISP, FS_MD, FS_BASE, FS_SM,
    FW_BOLD, FW_SEMIBOLD, FW_MEDIUM, FW_NORMAL,
    SP4, RADIUS_MD, BTN_LG
)
from three_ps_lcca_gui.gui.styles import font as _f, btn_primary, btn_outline
from three_ps_lcca_gui.gui._CONFIG import ALLOW_TEX

# ─────────────────────────────────────────────────────────────────────────────
# Config keys & Schema
# ─────────────────────────────────────────────────────────────────────────────
from three_ps_lcca_gui.code_to_latex.pdf_generation_v3.lcca_report_builder import (
    REPORT_SCHEMA,
    KEY_SHOW_TITLE_PAGE,
    KEY_SHOW_LCCA_RESULTS,
)


# ==============================================================================
# CLASS: SectionTreeWidget - Interactive tree for selecting report sections
# ==============================================================================


class SectionTreeWidget(QTreeWidget):
    """
    Professional tree widget for selecting report sections.
    Uses custom drawRow for polished hover/select effects matching the sidebar.
    """

    selectionChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("tree_sections")
        self.setHeaderLabel("Report Sections")
        self.itemChanged.connect(self.on_item_changed)
        
        self.setIndentation(28)
        self.setAnimated(True)
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)
        
        # Style the header and basic properties
        self._apply_theme_style()
        theme_manager().theme_changed.connect(self._apply_theme_style)

    def _apply_theme_style(self):
        """Apply theme-consistent styling to the tree widget."""
        # Sync Base/AlternateBase so viewport background matches window
        p = self.palette()
        p.setColor(QPalette.Base, p.color(QPalette.Window))
        self.setPalette(p)

        self.setStyleSheet(f"""
            QTreeWidget {{
                background-color: transparent;
                border: none;
                font-family: 'Ubuntu';
                font-size: {FS_BASE}pt;
                color: {get_token("text")};
                outline: none;
            }}
            QTreeWidget::item {{
                padding: 6px 0;
                border: none;
                color: {get_token("text")};
            }}

            /* ── Branch arrows ───────────────────────────────────────── */
            QTreeWidget::branch {{
                background: transparent;
            }}
            QTreeWidget::branch:has-children:!has-siblings:closed,
            QTreeWidget::branch:closed:has-children:has-siblings {{
                image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath d='M8 5v14l11-7z' fill='{get_token("text_secondary").replace("#", "%23")}'/%3E%3C/svg%3E");
            }}
            QTreeWidget::branch:open:has-children:!has-siblings,
            QTreeWidget::branch:open:has-children:has-siblings {{
                image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath d='M7 10l5 5 5-5z' fill='{get_token("text_secondary").replace("#", "%23")}'/%3E%3C/svg%3E");
            }}

            /* ── Checkboxes ───────────────────────────────────────────── */
            QTreeWidget::indicator {{
                width: 16px;
                height: 16px;
                border: 1px solid {get_token("surface_mid")};
                border-radius: 4px;
                background-color: {get_token("base")};
            }}
            QTreeWidget::indicator:checked {{
                background-color: {get_token("primary")};
                border-color: {get_token("primary")};
                image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath d='M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z' fill='white'/%3E%3C/svg%3E");
            }}
            QTreeWidget::indicator:indeterminate {{
                background-color: {get_token("primary")};
                border-color: {get_token("primary")};
                image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Crect x='4' y='11' width='16' height='2' fill='white'/%3E%3C/svg%3E");
            }}
            QTreeWidget::indicator:unchecked:hover {{
                border-color: {get_token("primary")};
            }}

            /* ── Header ──────────────────────────────────────────────── */
            QHeaderView::section {{
                background-color: {get_token("surface")};
                color: {get_token("text")};
                font-weight: {FW_SEMIBOLD};
                padding: 8px 12px;
                border: none;
                border-bottom: 2px solid {get_token("surface_mid")};
                font-size: 11px;
                text-transform: uppercase;
            }}
        """)

    def _row_state(self, index):
        """Return (is_selected, is_hovered) for a model index."""
        item = self.itemFromIndex(index)
        is_sel = item in self.selectedItems()
        is_hovered = index == self.indexAt(
            self.viewport().mapFromGlobal(self.cursor().pos())
        )
        return is_sel, is_hovered

    def drawRow(self, painter: QPainter, option, index):
        """Pre-paint full-width background for professional hover/selection."""
        is_sel, is_hovered = self._row_state(index)
        full = option.rect

        painter.save()
        painter.setPen(Qt.NoPen)
        # Background fill
        painter.setBrush(self.palette().window())
        painter.drawRect(full)
        
        # Hover tint
        if is_hovered and not is_sel:
            tint = QColor(get_token("primary")); tint.setAlpha(11)
            painter.setBrush(tint); painter.drawRect(full)
        
        # Selection tint
        if is_sel:
            tint = QColor(get_token("primary")); tint.setAlpha(22)
            painter.setBrush(tint); painter.drawRect(full)
        
        painter.restore()

        # Strip standard selection states so Qt doesn't paint its own (often harsh) highlight
        option.state &= ~(QStyle.State_Selected | QStyle.State_MouseOver | QStyle.State_HasFocus)
        super().drawRow(painter, option, index)

    def build_from_sections(self):
        """Populate tree widget directly from the data-driven REPORT_SCHEMA."""
        self.clear()

        from PySide6.QtGui import QFont as _QFont, QColor as _QColor
        font_section = _QFont("Ubuntu", FS_BASE); font_section.setWeight(_QFont.Weight.DemiBold)
        font_sub    = _QFont("Ubuntu", FS_BASE)
        font_table  = _QFont("Ubuntu", FS_SM)
        col_section = _QColor(get_token("text"))
        col_sub     = _QColor(get_token("text"))
        col_table   = _QColor(get_token("text_secondary"))
        col_disabled = _QColor(get_token("text_secondary"))

        try:
            from three_ps_lcca_gui.gui.components.utils.common_requested_data import get_traffic_and_road_data
            _is_global = get_traffic_and_road_data().get("mode") == "GLOBAL"
        except Exception:
            _is_global = False

        def _add_item(schema_item, parent_widget):
            india_only = schema_item.get("india_only", False)
            disabled = _is_global and india_only

            label = schema_item["title"]
            if disabled:
                label = f"{label}  (India mode only)"
            tree_item = QTreeWidgetItem(parent_widget, [label])

            if disabled:
                tree_item.setFlags(Qt.ItemIsEnabled)  # visible but not checkable
                tree_item.setCheckState(0, Qt.Unchecked)
                tree_item.setForeground(0, col_disabled)
                font_dis = _QFont("Ubuntu", FS_SM)
                tree_item.setFont(0, font_dis)
            else:
                tree_item.setFlags(tree_item.flags() | Qt.ItemIsUserCheckable)
                tree_item.setCheckState(0, Qt.Checked)

                # Formatting based on depth
                if isinstance(parent_widget, QTreeWidget):
                    tree_item.setFont(0, font_section)
                    tree_item.setForeground(0, col_section)
                elif parent_widget.parent() and isinstance(parent_widget.parent(), QTreeWidget):
                    tree_item.setFont(0, font_sub)
                    tree_item.setForeground(0, col_sub)
                else:
                    tree_item.setFont(0, font_table)
                    tree_item.setForeground(0, col_table)

            # Map the config key
            key = schema_item.get("key")
            if key:
                tree_item.setData(0, Qt.UserRole, key)

            # Recursively add children
            if "children" in schema_item:
                for child in schema_item["children"]:
                    _add_item(child, tree_item)

        for top_item in REPORT_SCHEMA:
            _add_item(top_item, self)

        self.expandAll()

    def on_item_changed(self, item, column):
        """Handle checkbox changes with parent-child propagation."""
        if column == 0:
            self.blockSignals(True)
            state = item.checkState(0)
            self._set_children_state(item, state)
            self.update_parent_state(item)
            self.blockSignals(False)
            self.selectionChanged.emit()

    def _set_children_state(self, item, state):
        """Recursively set check state on all descendants."""
        for i in range(item.childCount()):
            child = item.child(i)
            child.setCheckState(0, state)
            self._set_children_state(child, state)

    def update_parent_state(self, item):
        """Update parent checkbox state based on children states."""
        parent = item.parent()
        if parent is None:
            return

        total_children = parent.childCount()
        checked_children = sum(
            1
            for i in range(total_children)
            if parent.child(i).checkState(0) == Qt.Checked
        )

        if checked_children == total_children:
            parent.setCheckState(0, Qt.Checked)
        elif checked_children == 0:
            parent.setCheckState(0, Qt.Unchecked)
        else:
            parent.setCheckState(0, Qt.PartiallyChecked)

        self.update_parent_state(parent)

    def get_config(self):
        """Build config dict from current tree selection state."""
        config = {}
        self._collect_config(self.invisibleRootItem(), config)
        config.setdefault(KEY_SHOW_TITLE_PAGE, True)
        config.setdefault(KEY_SHOW_LCCA_RESULTS, True)
        return config

    def _collect_config(self, item, config):
        """Recursively collect config flags from tree items."""
        for i in range(item.childCount()):
            child = item.child(i)
            config_key = child.data(0, Qt.UserRole)
            if config_key:
                config[config_key] = child.checkState(0) == Qt.Checked
            self._collect_config(child, config)


# ==============================================================================
# CLASS: _PdfGenWorker - Background thread for PDF generation
# ==============================================================================


class _PdfGenWorker(QThread):
    """Runs PDF generation on a background thread to avoid freezing the UI."""

    finished = Signal(str)        # emitted with final PDF path on success
    errored = Signal(str, str)    # (error_msg, tex_path_or_empty)- work dir kept alive when tex_path set

    def __init__(self, export_dict, config, output_dir, filename="LCCA_Report", mode="lcca_v3", controller=None):
        super().__init__()
        self._export_dict = export_dict
        self._config = config
        self._output_dir = output_dir
        self._filename = filename
        self._mode = mode
        self._controller = controller

    def run(self):
        work_dir = tempfile.mkdtemp(prefix="3psLCCA_")
        try:
            stem = self._filename
            work_stem = os.path.join(work_dir, stem)

            if self._mode == "lcca_v3":
                from three_ps_lcca_gui.code_to_latex.pdf_generation_v3.lcca_report_builder import (
                    compile_lcca_report_pdf,
                )

                _, final_pdf = compile_lcca_report_pdf(
                    self._controller,
                    output_dir=self._output_dir,
                    filename=stem,
                    config=self._config,
                )
                shutil.rmtree(work_dir, ignore_errors=True)
                self.finished.emit(str(final_pdf))
                return

            work_pdf = work_stem + ".pdf"
            if os.path.exists(work_pdf):
                final_pdf = os.path.join(self._output_dir, stem + ".pdf")
                shutil.copy2(work_pdf, final_pdf)
                
                shutil.rmtree(work_dir, ignore_errors=True)
                self.finished.emit(final_pdf)
            else:
                tex_path = work_stem + ".tex"
                if os.path.exists(tex_path) and ALLOW_TEX:
                    # Keep work_dir alive- dialog cleans it up after export/close
                    self.errored.emit(
                        f"PDF compilation failed- LaTeX could not produce a PDF.\n"
                        f"You can export the .tex file and compile it manually:\n"
                        f"  pdflatex \"{stem}.tex\"",
                        tex_path,
                    )
                else:
                    shutil.rmtree(work_dir, ignore_errors=True)
                    err_msg = "Report generation completed but no output file was found."
                    if os.path.exists(tex_path):
                        err_msg = "PDF compilation failed- LaTeX could not produce a PDF."
                    self.errored.emit(err_msg, "")

        except Exception as e:
            shutil.rmtree(work_dir, ignore_errors=True)
            self.errored.emit(f"{type(e).__name__}: {e}", "")


# ==============================================================================
# CLASS: ReportSectionDialog - Modal dialog for section selection + generation
# ==============================================================================


class ReportSectionDialog(QDialog):
    """
    Modal dialog that lets the user select which sections/tables to include
    in the PDF report, then generates it via generate_report().
    """


    def __init__(self, export_dict: dict, mode="lcca_v3", controller=None, parent=None):
        super().__init__(parent)
        self._mode = mode
        self._controller = controller
        title_text = (
            "LCCA V3 Report Customization"
            if mode == "lcca_v3"
            else "Data Provenance Report V2"
        )
        self.setWindowTitle(title_text)
        self.setObjectName("report_section_dialog")
        self.resize(600, 700)
        self._export_dict = export_dict
        self._worker = None
        self._dot_timer = QTimer(self)
        self._dot_timer.setInterval(450)
        self._dot_timer.timeout.connect(self._tick_dots)
        self._dot_count = 0

        self._animating = False
        self._bg_anim = QVariantAnimation(self)
        self._bg_anim.setStartValue(QColor(get_token("primary")))
        self._bg_anim.setEndValue(QColor(get_token("primary")).lighter(160))
        self._bg_anim.setDuration(900)
        self._bg_anim.setEasingCurve(QEasingCurve.InOutSine)
        self._bg_anim.setLoopCount(1)
        self._bg_anim.valueChanged.connect(self._on_btn_anim)
        self._bg_anim.finished.connect(self._ping_pong_anim)

        self._init_ui()

    def _init_ui(self):
        """Build the user interface."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(32, 32, 32, 32)
        main_layout.setSpacing(16)

        # Title
        title_text = (
            "LCCA Report Customization"
            if self._mode == "lcca_v3"
            else "Data Provenance Report V2"
        )
        self.lbl_title = QLabel(title_text)
        self.lbl_title.setFont(_f(FS_DISP, FW_BOLD))
        self.lbl_title.setStyleSheet(f"color: {get_token('primary')};")
        self.lbl_title.setAlignment(Qt.AlignLeft)
        main_layout.addWidget(self.lbl_title)

        self.lbl_subtitle = QLabel(
            "Select the sections and data tables to include in your final modular LCCA PDF report."
        )
        self.lbl_subtitle.setFont(_f(FS_BASE, FW_NORMAL))
        self.lbl_subtitle.setStyleSheet(f"color: {get_token('text_secondary')};")
        self.lbl_subtitle.setWordWrap(True)
        main_layout.addWidget(self.lbl_subtitle)

        # Separator-like gap
        main_layout.addSpacing(8)

        # Tree widget container
        tree_container = QWidget()
        tree_container.setObjectName("tree_container")
        tree_container.setStyleSheet(f"""
            QWidget#tree_container {{
                background-color: {get_token("base")};
                border: 1px solid {get_token("surface_mid")};
                border-radius: {RADIUS_MD}px;
            }}
        """)
        tree_layout = QVBoxLayout(tree_container)
        tree_layout.setContentsMargins(0, 0, 0, 0)

        # Tree widget
        self.tree_sections = SectionTreeWidget()
        self.tree_sections.build_from_sections()
        self.tree_sections.selectionChanged.connect(self.on_selection_changed)
        tree_layout.addWidget(self.tree_sections)

        main_layout.addWidget(tree_container, stretch=1)

        # Status and Buttons bottom area
        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(0, 8, 0, 0)
        
        # Status label
        self.lbl_status = QLabel("")
        self.lbl_status.setFont(_f(FS_SM, FW_MEDIUM))
        self.lbl_status.setStyleSheet(f"color: {get_token('text_secondary')};")
        bottom_layout.addWidget(self.lbl_status)
        
        bottom_layout.addStretch()

        # Buttons
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setFixedWidth(110)
        self.btn_cancel.setMinimumHeight(BTN_LG)
        self.btn_cancel.setStyleSheet(btn_outline())
        self.btn_cancel.clicked.connect(self.reject)
        bottom_layout.addWidget(self.btn_cancel)

        self.btn_save_as = QPushButton("Generate PDF")
        self.btn_save_as.setFixedWidth(170)
        self.btn_save_as.setMinimumHeight(BTN_LG)
        self.btn_save_as.setStyleSheet(btn_primary())
        self.btn_save_as.clicked.connect(self.generate_report_with_path)
        bottom_layout.addWidget(self.btn_save_as)

        main_layout.addLayout(bottom_layout)
        
        self.on_selection_changed()

    def on_selection_changed(self):
        """Update status label when tree selection changes."""
        config = self.tree_sections.get_config()
        selected_count = sum(1 for v in config.values() if v)
        total_count = len(config)
        self.lbl_status.setText(f"{selected_count} of {total_count} sections selected")

    def _tick_dots(self):
        self._dot_count = (self._dot_count + 1) % 4
        self.lbl_status.setText("Generating" + "." * self._dot_count)

    def _ping_pong_anim(self):
        if not self._animating:
            return
        from PySide6.QtCore import QAbstractAnimation
        self._bg_anim.setDirection(
            QAbstractAnimation.Backward
            if self._bg_anim.direction() == QAbstractAnimation.Forward
            else QAbstractAnimation.Forward
        )
        self._bg_anim.start()

    def _on_btn_anim(self, color: QColor):
        self.btn_save_as.setStyleSheet(
            f"QPushButton {{ background-color: {color.name()}; color: white; border: none; }}"
        )

    def _set_ui_enabled(self, enabled):
        """Enable/disable UI controls during generation."""
        self.btn_save_as.setEnabled(enabled)
        self.btn_cancel.setEnabled(enabled)
        self.tree_sections.setEnabled(enabled)
        if enabled:
            self.btn_save_as.setText("Generate PDF")
        else:
            self.btn_save_as.setText("Generating...")

    def generate_report_with_path(self):
        """Ask user for save location, then generate PDF."""
        default_name = self._export_dict.get("project_name", "LCCA_Report")
        # Sanitize filename (remove characters like / \ : * ? " < > |)
        for char in '<>:"/\\|?*':
            default_name = default_name.replace(char, "_")

        # Set default directory to Documents
        default_dir = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)
        default_path = os.path.join(default_dir, f"{default_name}.pdf")

        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save PDF Report",
            default_path,
            "PDF Files (*.pdf)",
        )
        if not save_path:
            return

        # Ensure .pdf extension
        if not save_path.lower().endswith(".pdf"):
            save_path += ".pdf"

        self._generate_pdf(os.path.dirname(save_path), os.path.splitext(os.path.basename(save_path))[0])

    def _generate_pdf(self, output_dir, filename):
        """Launch background PDF generation."""
        import three_ps_lcca_gui.gui.components.utils.common_requested_data as crd
        crd.get_all_data()

        config = self.tree_sections.get_config()
        export = self._export_dict

        self._set_ui_enabled(False)
        self._dot_count = 0
        self.lbl_status.setText("Generating.")
        self._dot_timer.start()
        self._animating = True
        self.btn_save_as.setFixedSize(self.btn_save_as.size())
        self._bg_anim.setDirection(QVariantAnimation.Forward)
        self._bg_anim.start()
        QApplication.processEvents()

        self._worker = _PdfGenWorker(
            export,
            config,
            output_dir,
            filename=filename,
            mode=self._mode,
            controller=self._controller,
        )
        self._worker.finished.connect(self._on_pdf_success)
        self._worker.errored.connect(self._on_pdf_error)
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.errored.connect(self._worker.deleteLater)
        self._worker.start()

    def _stop_anim(self):
        self._animating = False
        self._dot_timer.stop()
        self._bg_anim.stop()
        self.btn_save_as.setStyleSheet(btn_primary())
        self.lbl_status.setText("")

    def _on_pdf_success(self, pdf_path):
        """Handle successful PDF generation."""
        self._stop_anim()
        self._set_ui_enabled(True)
        QMessageBox.information(
            self,
            "Report Saved",
            f"Report saved to:\n{pdf_path}",
        )
        # Attempt to open the PDF
        if os.path.exists(pdf_path):
            os.startfile(pdf_path)
        self.accept()

    def _on_pdf_error(self, error_msg: str, tex_path: str):
        """Handle PDF generation error- offer .tex export when available."""
        self._stop_anim()
        self._set_ui_enabled(True)

        if not tex_path:
            QMessageBox.critical(self, "PDF Generation Failed", error_msg)
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("PDF Compilation Failed")
        dlg.setMinimumWidth(460)
        lay = QVBoxLayout(dlg)
        lay.setSpacing(12)
        lay.setContentsMargins(20, 20, 20, 20)

        lbl = QLabel(error_msg)
        lbl.setWordWrap(True)
        lbl.setFont(_f(FS_BASE))
        lay.addWidget(lbl)

        note = QLabel(
            "The .tex source file is ready. Export it, then run:\n"
            "  <b>pdflatex LCCA_Report.tex</b>"
        )
        note.setTextFormat(Qt.RichText)
        note.setWordWrap(True)
        note.setFont(_f(FS_SM))
        note.setStyleSheet(f"color: {get_token('text_secondary')};")
        lay.addWidget(note)

        btns = QDialogButtonBox()
        export_btn = btns.addButton("Export .tex File…", QDialogButtonBox.AcceptRole)
        btns.addButton("Close", QDialogButtonBox.RejectRole)
        lay.addWidget(btns)

        work_dir = os.path.dirname(tex_path)

        def _cleanup():
            shutil.rmtree(work_dir, ignore_errors=True)

        def _export():
            # Set default directory to Documents
            default_dir = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)
            default_path = os.path.join(default_dir, "LCCA_Report.tex")

            dest, _ = QFileDialog.getSaveFileName(
                dlg, "Save .tex File", default_path, "LaTeX Files (*.tex)"
            )
            if dest:
                if not dest.lower().endswith(".tex"):
                    dest += ".tex"
                try:
                    shutil.copy2(tex_path, dest)
                    QMessageBox.information(
                        dlg, "Saved",
                        f"Saved to:\n{dest}\n\nCompile with:\n  pdflatex \"{dest}\""
                    )
                    dlg.accept()
                except Exception as e:
                    QMessageBox.critical(dlg, "Export Failed", str(e))

        export_btn.clicked.connect(_export)
        btns.rejected.connect(dlg.reject)
        dlg.finished.connect(lambda _: _cleanup())
        dlg.exec()
