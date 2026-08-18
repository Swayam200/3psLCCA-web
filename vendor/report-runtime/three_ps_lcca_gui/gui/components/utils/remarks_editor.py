"""
gui/components/utils/input_fields/remarks_editor.py

Reusable rich-text remarks / notes widget.
Saves content as HTML into the engine chunk under the key "remarks".
"""

from PySide6.QtWidgets import (
    QGroupBox,
    QInputDialog,
    QSizePolicy,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
)
from PySide6.QtGui import (
    QAction,
    QFont,
    QTextBlockFormat,
    QTextCharFormat,
    QTextCursor,
    QTextLength,
    QTextListFormat,
    QTextTableFormat,
)
from three_ps_lcca_gui.gui.theme import FW_BOLD
from PySide6.QtCore import Qt
from .validation_helpers import confirm_clear_all


class RemarksEditor(QGroupBox):
    """
    Full-featured rich-text editor.
    Toolbar: Bold · Italic · Underline · Strikethrough ·
             Align L/C/R/J · Bullet · Numbered · Table · Clear
    """

    def __init__(self, title: str = "Notes", on_change=None, parent=None):
        super().__init__(title, parent)
        self._on_change = on_change

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(4)

        # ── Toolbar ───────────────────────────────────────────────────────
        self._toolbar = QToolBar()
        self._toolbar.setMovable(False)
        self._toolbar.setFloatable(False)
        self._toolbar.setStyleSheet("QToolBar { spacing: 2px; }")
        toolbar = self._toolbar

        # # Bold
        # self._act_bold = QAction("B", self)
        # self._act_bold.setCheckable(True)
        # self._act_bold.setToolTip("Bold (Ctrl+B)")
        # f = QFont()
        # f.setWeight(QFont.Weight(FW_BOLD))
        # self._act_bold.setFont(f)
        # self._act_bold.triggered.connect(self._toggle_bold)
        # toolbar.addAction(self._act_bold)

        # # Italic
        # self._act_italic = QAction("I", self)
        # self._act_italic.setCheckable(True)
        # self._act_italic.setToolTip("Italic (Ctrl+I)")
        # f = QFont()
        # f.setItalic(True)
        # self._act_italic.setFont(f)
        # self._act_italic.triggered.connect(self._toggle_italic)
        # toolbar.addAction(self._act_italic)

        # # Underline
        # self._act_underline = QAction("U", self)
        # self._act_underline.setCheckable(True)
        # self._act_underline.setToolTip("Underline (Ctrl+U)")
        # f = QFont()
        # f.setUnderline(True)
        # self._act_underline.setFont(f)
        # self._act_underline.triggered.connect(self._toggle_underline)
        # toolbar.addAction(self._act_underline)

        # # Strikethrough
        # self._act_strike = QAction("S", self)
        # self._act_strike.setCheckable(True)
        # self._act_strike.setToolTip("Strikethrough")
        # f = QFont()
        # f.setStrikeOut(True)
        # self._act_strike.setFont(f)
        # self._act_strike.triggered.connect(self._toggle_strikethrough)
        # toolbar.addAction(self._act_strike)

        # # Alignment
        # self._act_align_left = QAction("Left", self)
        # self._act_align_left.setCheckable(True)
        # self._act_align_left.setToolTip("Align Left")
        # self._act_align_left.triggered.connect(lambda: self._set_alignment(Qt.AlignLeft))
        # toolbar.addAction(self._act_align_left)
        # self._act_align_center = QAction("Center", self)
        # self._act_align_center.setCheckable(True)
        # self._act_align_center.setToolTip("Align Center")
        # self._act_align_center.triggered.connect(lambda: self._set_alignment(Qt.AlignCenter))
        # toolbar.addAction(self._act_align_center)
        # self._act_align_right = QAction("Right", self)
        # self._act_align_right.setCheckable(True)
        # self._act_align_right.setToolTip("Align Right")
        # self._act_align_right.triggered.connect(lambda: self._set_alignment(Qt.AlignRight))
        # toolbar.addAction(self._act_align_right)
        # self._act_align_justify = QAction("Justify", self)
        # self._act_align_justify.setCheckable(True)
        # self._act_align_justify.setToolTip("Justify")
        # self._act_align_justify.triggered.connect(lambda: self._set_alignment(Qt.AlignJustify))
        # toolbar.addAction(self._act_align_justify)
        # self._align_actions = [
        #     (self._act_align_left, Qt.AlignLeft),
        #     (self._act_align_center, Qt.AlignCenter),
        #     (self._act_align_right, Qt.AlignRight),
        #     (self._act_align_justify, Qt.AlignJustify),
        # ]

        # Bullet list
        act_bullet = QAction("• List", self)
        act_bullet.setToolTip("Toggle bullet list")
        act_bullet.triggered.connect(self._toggle_bullet)
        toolbar.addAction(act_bullet)

        # Numbered list
        act_numbered = QAction("1. List", self)
        act_numbered.setToolTip("Toggle numbered list")
        act_numbered.triggered.connect(self._toggle_numbered)
        toolbar.addAction(act_numbered)

        toolbar.addSeparator()

        # # Insert table
        # act_table = QAction("+ Table", self)
        # act_table.setToolTip("Insert table (prompts for rows/cols)")
        # act_table.triggered.connect(self._insert_table)
        # toolbar.addAction(act_table)
        # # Add row
        # act_add_row = QAction("+ Row", self)
        # act_add_row.setToolTip("Add row to current table")
        # act_add_row.triggered.connect(self._add_table_row)
        # toolbar.addAction(act_add_row)
        # # Add column
        # act_add_col = QAction("+ Col", self)
        # act_add_col.setToolTip("Add column to current table")
        # act_add_col.triggered.connect(self._add_table_col)
        # toolbar.addAction(act_add_col)

        toolbar.addSeparator()

        # Clear
        act_clear = QAction("Clear", self)
        act_clear.setToolTip("Clear all content")
        act_clear.triggered.connect(self._clear)
        toolbar.addAction(act_clear)

        root.addWidget(toolbar)

        # ── Editor ────────────────────────────────────────────────────────
        self._editor = QTextEdit()
        self._editor.setMinimumHeight(150)
        self._editor.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._editor.setPlaceholderText(
            "Add notes or remarks here. These will appear in the LCCA report."
        )
        self._editor.textChanged.connect(self._on_text_changed)
        self._editor.cursorPositionChanged.connect(self._sync_toolbar)
        root.addWidget(self._editor)

    # ── Text style ────────────────────────────────────────────────────────

    def _toggle_bold(self, checked: bool):
        fmt = QTextCharFormat()
        fmt.setFontWeight(FW_BOLD if checked else QFont.Normal)
        self._apply_char_fmt(fmt)

    def _toggle_italic(self, checked: bool):
        fmt = QTextCharFormat()
        fmt.setFontItalic(checked)
        self._apply_char_fmt(fmt)

    def _toggle_underline(self, checked: bool):
        fmt = QTextCharFormat()
        fmt.setFontUnderline(checked)
        self._apply_char_fmt(fmt)

    def _toggle_strikethrough(self, checked: bool):
        fmt = QTextCharFormat()
        fmt.setFontStrikeOut(checked)
        self._apply_char_fmt(fmt)

    def _apply_char_fmt(self, fmt: QTextCharFormat):
        cursor = self._editor.textCursor()
        if not cursor.hasSelection():
            cursor.select(QTextCursor.WordUnderCursor)
        cursor.mergeCharFormat(fmt)
        self._editor.mergeCurrentCharFormat(fmt)

    # ── Alignment ─────────────────────────────────────────────────────────

    def _set_alignment(self, alignment):
        self._editor.setAlignment(alignment)
        self._sync_toolbar()

    # ── Lists ─────────────────────────────────────────────────────────────

    def _toggle_bullet(self):
        self._toggle_list(QTextListFormat.ListDisc)

    def _toggle_numbered(self):
        self._toggle_list(QTextListFormat.ListDecimal)

    def _toggle_list(self, style):
        cursor = self._editor.textCursor()
        current_list = cursor.currentList()
        if current_list and current_list.format().style() == style:
            fmt = QTextBlockFormat()
            fmt.setIndent(0)
            cursor.setBlockFormat(fmt)
            cursor.createList(QTextListFormat())
        else:
            fmt = QTextListFormat()
            fmt.setStyle(style)
            cursor.createList(fmt)

    # ── Table ─────────────────────────────────────────────────────────────

    def _insert_table(self):
        rows, ok1 = QInputDialog.getInt(self, "Insert Table", "Rows:", 2, 1, 20)
        if not ok1:
            return
        cols, ok2 = QInputDialog.getInt(self, "Insert Table", "Columns:", 2, 1, 20)
        if not ok2:
            return

        cursor = self._editor.textCursor()
        fmt = QTextTableFormat()
        fmt.setBorder(1)
        fmt.setBorderStyle(QTextTableFormat.BorderStyle_Solid)
        fmt.setCellPadding(4)
        fmt.setCellSpacing(0)
        fmt.setWidth(QTextLength(QTextLength.PercentageLength, 100))
        cursor.insertTable(rows, cols, fmt)

    def _add_table_row(self):
        cursor = self._editor.textCursor()
        table = cursor.currentTable()
        if table:
            table.appendRows(1)

    def _add_table_col(self):
        cursor = self._editor.textCursor()
        table = cursor.currentTable()
        if table:
            table.appendColumns(1)

    # ── Clear ─────────────────────────────────────────────────────────────

    def _clear(self):
        if confirm_clear_all(self):
            self._editor.clear()

    # ── Toolbar sync ──────────────────────────────────────────────────────

    def _sync_toolbar(self):
        pass

    def _on_text_changed(self):
        if self._on_change:
            self._on_change()

    # ── Public API ────────────────────────────────────────────────────────

    def to_html(self) -> str:
        return self._editor.toHtml()

    def to_plain(self) -> str:
        return self._editor.toPlainText()

    def from_html(self, html: str):
        self._editor.blockSignals(True)
        self._editor.setHtml(html or "")
        self._editor.blockSignals(False)

    def clear_content(self):
        if confirm_clear_all(self):
            self._editor.clear()

    def freeze(self, frozen: bool = True):
        """Freeze/unfreeze the editor. Read-only keeps content visible; toolbar is disabled."""
        from .validation_helpers import _lock_filter, LOCK_TOOLTIP

        self._editor.setReadOnly(frozen)
        self._toolbar.setEnabled(not frozen)

        if frozen:
            self._editor.setToolTip(LOCK_TOOLTIP)
            self._editor.installEventFilter(_lock_filter)
        else:
            self._editor.removeEventFilter(_lock_filter)
            self._editor.setToolTip("")


