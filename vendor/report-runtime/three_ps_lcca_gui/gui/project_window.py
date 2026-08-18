import os

from PySide6.QtCore import Qt, QRect, QSize, QEvent, QPoint, QTimer, QStandardPaths
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QInputDialog,
    QFileDialog,
    QLabel,
    QMainWindow,
    QMenu,
    QMenuBar,
    QMessageBox,
    QPushButton,
    QSplitter,
    QSplitterHandle,
    QStackedWidget,
    QStatusBar,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPalette

from three_ps_lcca_gui.gui.components.utils.icons import make_icon, make_icon_btn
from three_ps_lcca_gui.gui.theme import (
    FS_SM, FS_BASE, FS_MD,
    FW_NORMAL, FW_MEDIUM, FW_SEMIBOLD,
    SP4,
)
from three_ps_lcca_gui.gui.styles import font as _f
from PySide6.QtWidgets import QToolTip
from three_ps_lcca_gui.gui.version import VERSION
from three_ps_lcca_gui.gui.devmode import setup_dev_menu
from three_ps_lcca_gui.gui.project_controller import ProjectController
from three_ps_lcca_gui.gui.themes import get_token, theme_manager
from three_ps_lcca_gui.gui.components.home_page import HomePage
from three_ps_lcca_gui.gui.components.save_status_bar import SaveStatusBar
from three_ps_lcca_gui.gui.components.logs import Logs
from three_ps_lcca_gui.gui.components.outputs.outputs_page import OutputsPage
from three_ps_lcca_gui.gui.components.global_info.main import GeneralInfo
from three_ps_lcca_gui.gui.components.bridge_data.main import BridgeData
from three_ps_lcca_gui.gui.components.structure.main import StructureTabView
from three_ps_lcca_gui.gui.components.traffic_data.main import TrafficData
from three_ps_lcca_gui.gui.components.financial_data.main import FinancialData
from three_ps_lcca_gui.gui.components.carbon_emission.main import CarbonEmissionTabView
from three_ps_lcca_gui.gui.components.maintenance.main import Maintenance
from three_ps_lcca_gui.gui.components.recycling.main import Recycling
from three_ps_lcca_gui.gui.components.demolition.main import Demolition
from three_ps_lcca_gui.gui.components.utils.validation_helpers import set_lock_tooltip_target
from three_ps_lcca_gui.gui.components.utils.definitions import set_active_unit_system
from three_ps_lcca_gui.gui.components.utils.doc_handler import open_glossary
from three_ps_lcca_gui.core.safechunk_engine import SafeChunkEngine
from PySide6.QtWidgets import QDialog, QFormLayout, QVBoxLayout, QLabel, QPushButton
from three_ps_lcca_gui.gui.components.rollback_dialog import RollbackDialog
from three_ps_lcca_gui.gui.components.blob_manager import BlobManagerDialog
from three_ps_lcca_gui.gui._CONFIG import DEV_MODE, FLUSH_MODE
try:
    from three_ps_lcca_gui.gui._CONFIG import COMPARISON_MODE
except ImportError:
    COMPARISON_MODE = True
if FLUSH_MODE:
    from three_ps_lcca_gui.gui.flush import flush_project_window
if DEV_MODE:
    from three_ps_lcca_gui.gui.sys_tracker import SysTracker
import shutil
import logging

log = logging.getLogger("project_window")

_GUI_DIR = os.path.abspath(os.path.dirname(__file__))
_ASSETS_DIR = os.path.join(_GUI_DIR, "assets")


# ── Sidebar tree definition ───────────────────────────────────────────────────

SIDEBAR_TREE = {
    "General Information": {},
    "Bridge Data": {},
    "Input Parameters": {
        "Construction Works Data": [
            "Foundation",
            "Sub-Structure",
            "Super-Structure",
            "Miscellaneous",
        ],
        "Traffic Data": [],
        "Financial Data": [],
        "Carbon Emissions Data": [
            "Social Cost of Carbon",
            "Material Emissions",
            "Transportation Emissions",
            "Machinery/Equipment Emissions",
            "Traffic Rerouting Emissions",
        ],
        "Maintenance and Repair": [],
        "Recycling": [],
        "Demolition": [],
    },
    "Results": {},
}


# ── Sidebar tree ──────────────────────────────────────────────────────────────

_V_PAD = 1   # vertical padding per side
_H_PAD = 10  # left text indent
_ACCENT_W = 3   # width of the left accent bar in px
_ICON_SIZE = 16
_ICON_GAP = 6

# Material icon name for each sidebar item (top-level and section-level only)
_SIDEBAR_ICONS: dict[str, str] = {
    "General Information":    "info",
    "Bridge Data":            "layers",
    "Input Parameters":       "folder",
    "Construction Works Data": "build",
    "Traffic Data":           "truck",
    "Financial Data":         "cash",
    "Carbon Emissions Data":   "cloud",
    "Maintenance and Repair": "settings",
    "Recycling":              "autorenew",
    "Demolition":             "delete",
    "Results":                "bar-chart",
}


class _SidebarDelegate(QStyledItemDelegate):
    """Owns text-column painting: padding, text color. Background is handled
    by _SidebarTree.drawRow so we only need to paint text here."""

    def sizeHint(self, option, index):
        base = super().sizeHint(option, index)
        depth = 0
        p = index.parent()
        while p.isValid():
            depth += 1
            p = p.parent()
        pad = _V_PAD if depth < 2 else _V_PAD + 3
        return QSize(base.width(), base.height() + pad * 2)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        # Query tree directly - option.state may be stripped by drawRow
        tree = self.parent()
        item = tree.itemFromIndex(index) if tree else None
        is_sel = bool(item and item in tree.selectedItems())

        option.state &= ~(
            QStyle.State_Selected | QStyle.State_MouseOver | QStyle.State_HasFocus
        )

        painter.save()

        depth = 0
        p = index.parent()
        while p.isValid():
            depth += 1
            p = p.parent()

        # Font by depth - size stays at FS_MD; weight carries the hierarchy
        # Bump weight if selected
        if depth == 0:
            painter.setFont(_f(FS_MD, FW_SEMIBOLD if is_sel else FW_MEDIUM))
        elif depth == 1:
            painter.setFont(_f(FS_MD, FW_SEMIBOLD if is_sel else FW_MEDIUM))
        else:
            painter.setFont(_f(FS_BASE, FW_MEDIUM if is_sel else FW_NORMAL))

        # Text colour - PRIMARY on selected, normal otherwise
        text_col = QColor(get_token("primary")
                          ) if is_sel else option.palette.windowText().color()
        painter.setPen(text_col)

        extra = 28 if depth >= 2 else 0
        x = option.rect.left() + _H_PAD + extra + (_ACCENT_W if is_sel else 0)

        # Icon
        icon: QIcon = index.data(Qt.DecorationRole)
        if icon and not icon.isNull():
            iy = option.rect.top() + (option.rect.height() - _ICON_SIZE) // 2
            icon.paint(painter, QRect(
                x, iy, _ICON_SIZE, _ICON_SIZE), Qt.AlignCenter)
            x += _ICON_SIZE + _ICON_GAP

        # Text
        text = index.data(Qt.DisplayRole)
        if text:
            text_rect = QRect(x, option.rect.top() + _V_PAD,
                              option.rect.right() - x - SP4,
                              option.rect.height() - _V_PAD * 2)
            painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, text)

        painter.restore()


class _SidebarTree(QTreeWidget):
    """
    QTreeWidget subclass that overrides drawRow() and drawBranches() -
    the only two methods that own the full row width including the
    indentation/branch zone. The delegate only handles text after we've
    painted the correct background across the entire row.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)
        self.setItemDelegate(_SidebarDelegate(self))
        self.setRootIsDecorated(True)
        self.setIndentation(16)
        self._refresh_theme()
        theme_manager().theme_changed.connect(self._refresh_theme)

    def _refresh_theme(self):
        # Sync Base/AlternateBase → Window so the viewport background matches
        p = self.palette()
        p.setColor(QPalette.Base, p.color(QPalette.Window))
        p.setColor(QPalette.AlternateBase, p.color(QPalette.Window))
        # Keep Highlight neutral - we paint selection ourselves
        p.setColor(QPalette.Highlight, p.color(QPalette.Window))
        p.setColor(QPalette.HighlightedText, p.color(QPalette.WindowText))
        self.setPalette(p)
        self.viewport().update()

    def _row_state(self, index):
        """Return (is_selected, is_hovered) for a model index."""
        item = self.itemFromIndex(index)
        is_sel = item in self.selectedItems()
        is_hovered = index == self.indexAt(
            self.viewport().mapFromGlobal(self.cursor().pos())
        )
        return is_sel, is_hovered

    def drawRow(self, painter: QPainter, option, index):
        """Pre-paint full-width background, strip Qt states, then let Qt draw
        content on top. Accent bar is drawn last so it's never overwritten."""
        is_sel, is_hovered = self._row_state(index)
        full = option.rect

        painter.save()
        painter.setPen(Qt.NoPen)
        painter.setBrush(self.palette().window())
        painter.drawRect(full)
        if is_hovered and not is_sel:
            tint = QColor(get_token("primary"))
            tint.setAlpha(11)
            painter.setBrush(tint)
            painter.drawRect(full)
        if is_sel:
            tint = QColor(get_token("primary"))
            tint.setAlpha(22)
            painter.setBrush(tint)
            painter.drawRect(full)
        painter.restore()

        # Strip selection/hover so Qt doesn't repaint with its own highlight
        option.state &= ~(QStyle.State_Selected |
                          QStyle.State_MouseOver | QStyle.State_HasFocus)
        super().drawRow(painter, option, index)

        if is_sel:
            painter.save()
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(get_token("primary")))
            painter.drawRect(full.left(), full.top(), _ACCENT_W, full.height())
            painter.restore()

    def drawBranches(self, painter: QPainter, rect: QRect, index):
        """Background already painted by drawRow; just draw the expand arrows."""
        super().drawBranches(painter, rect, index)


# ── Hover-highlight splitter ──────────────────────────────────────────────────


class _HoverHandle(QSplitterHandle):
    """
    Splitter handle that draws a 2px green accent line on hover/drag -
    identical visual language to VS Code's panel resize handles.
    """

    def __init__(self, orientation, parent):
        super().__init__(orientation, parent)
        self.setMouseTracking(True)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._hovered = False

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        r = self.rect()

        painter.fillRect(r, self.palette().window())
        painter.setPen(Qt.NoPen)
        if self._hovered:
            painter.setBrush(QColor(get_token("primary")))
        else:
            painter.setBrush(QColor(get_token("primary", "pressed")))

        if self.orientation() == Qt.Horizontal:
            painter.drawRect((r.width() - 2) // 2, 0, 2, r.height())
        else:
            painter.drawRect(0, (r.height() - 2) // 2, r.width(), 2)

        painter.end()


class _HoverSplitter(QSplitter):
    """QSplitter that uses _HoverHandle for all its handles."""

    def createHandle(self):
        return _HoverHandle(self.orientation(), self)


# ── Main window ───────────────────────────────────────────────────────────────


class ProjectWindow(QMainWindow):
    def __init__(self, manager, controller=None):
        super().__init__()
        self.manager = manager

        if controller is not None:
            self.controller = controller
        else:
            self.controller = ProjectController()

        self.project_id = None
        self._needs_initial_landing = False

        if FLUSH_MODE:
            self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowTitle("3psLCCA - Home")
        _icon_path = os.path.join(_ASSETS_DIR, "logo", "logo-3psLCCA.ico")
        if os.path.exists(_icon_path):
            self.setWindowIcon(QIcon(_icon_path))
        self.resize(1100, 750)

        self.main_stack = QStackedWidget()
        self.setCentralWidget(self.main_stack)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # Add version to the right of the status bar
        self.version_lbl = QLabel(VERSION)
        self.version_lbl.setStyleSheet(
            f"color: {get_token('text_disabled')}; margin-right: 10px;")
        self.status_bar.addPermanentWidget(self.version_lbl)

        self._project_ui_ready = False
        self._setup_home_ui()  # index 0
        # _setup_project_ui() deferred to first show_project_view()

        # ── Controller signals ────────────────────────────────────────────
        self.controller.fault_occurred.connect(self._on_fault)
        self.controller.project_loaded.connect(self._on_project_loaded)
        self.controller.sync_completed.connect(
            lambda: self.status_bar.showMessage("All changes saved.", 3000)
        )
        self.controller.dirty_changed.connect(
            lambda d: self.status_bar.showMessage(
                "Unsaved changes...") if d else None
        )

        theme_manager().theme_changed.connect(self._refresh_lock_btn)

        self.show_home()

    # ── Home screen ───────────────────────────────────────────────────────────

    def _setup_home_ui(self):
        self.home_widget = HomePage(manager=self.manager)
        self.main_stack.addWidget(self.home_widget)  # index 0

    # ── Project view ──────────────────────────────────────────────────────────

    def _setup_project_ui(self):

        self.project_widget = QWidget()
        master_layout = QVBoxLayout(self.project_widget)
        master_layout.setContentsMargins(0, 0, 0, 0)
        master_layout.setSpacing(0)

        # ── Top bar ───────────────────────────────────────────────────────
        top_bar = QWidget()
        top_bar_layout = QHBoxLayout(top_bar)
        top_bar_layout.setContentsMargins(8, 4, 8, 4)
        top_bar_layout.setSpacing(8)
        top_bar.setObjectName("top_bar")

        self.menubar = QMenuBar()

        # ── File menu ─────────────────────────────────────────────────────
        self.menuFile = QMenu("&File", self.menubar)

        action_new = QAction("New Project", self)
        action_new.triggered.connect(
            lambda: self.manager.open_project(is_new=True))
        self.menuFile.addAction(action_new)

        action_open = QAction("Open Project", self)
        action_open.triggered.connect(self.show_home)
        self.menuFile.addAction(action_open)

        self.menuFile.addSeparator()

        self.actionSave = QAction("Save", self)
        self.actionSave.triggered.connect(self._save_now)
        self.menuFile.addAction(self.actionSave)

        self.menuFile.addSeparator()

        # ── Export submenu ────────────────────────────────────────────────
        self.menuExport = QMenu("Export", self.menuFile)
        self.menuExport.setStyleSheet(
            f"QMenu::item:disabled {{ color: {get_token('text_disabled')}; }}"
        )

        self.actionExportInputsJSON = QAction("Export Inputs as JSON", self)
        self.actionExportInputsJSON.triggered.connect(self._export_inputs_json)
        self.menuExport.addAction(self.actionExportInputsJSON)

        self.actionExportResultsJSON = QAction("Export Results as JSON", self)
        self.actionExportResultsJSON.setEnabled(False)
        self.actionExportResultsJSON.triggered.connect(
            self._export_results_json)
        self.menuExport.addAction(self.actionExportResultsJSON)

        self.actionExportAllDataJSON = QAction("Export All Data as JSON", self)
        self.actionExportAllDataJSON.setEnabled(False)
        self.actionExportAllDataJSON.triggered.connect(
            self._export_all_data_json)
        self.menuExport.addAction(self.actionExportAllDataJSON)

        self.menuFile.addMenu(self.menuExport)

        self.menuFile.addSeparator()

        action_rename = QAction("Rename", self)
        action_rename.triggered.connect(self._rename_project)
        self.menuFile.addAction(action_rename)

        action_export = QAction("Share", self)
        action_export.triggered.connect(self._export_project)
        self.menuFile.addAction(action_export)

        self.menuFile.addSeparator()

        self.actionVersionHistory = QAction("Version History", self)
        self.actionVersionHistory.triggered.connect(self._open_rollback_dialog)
        self.menuFile.addAction(self.actionVersionHistory)

        self.actionBlobManager = QAction("Blob Manager", self)
        self.actionBlobManager.triggered.connect(self._open_blob_manager)
        self.menuFile.addAction(self.actionBlobManager)

        self.menuFile.addSeparator()

        action_info = QAction("Info", self)
        action_info.triggered.connect(self._show_project_info)
        self.menuFile.addAction(action_info)

        from three_ps_lcca_gui.gui._CONFIG import LOCAL_API_ENABLED
        if LOCAL_API_ENABLED:
            action_api_access = QAction("API Access", self)
            action_api_access.triggered.connect(self._show_api_access)
            self.menuFile.addAction(action_api_access)

        self.menuFile.addSeparator()

        action_close = QAction("Close Project", self)
        action_close.triggered.connect(self._close_project)
        self.menuFile.addAction(action_close)

        # ── Help menu ─────────────────────────────────────────────────────
        self.menuHelp = QMenu("&Help", self.menubar)

        action_glossary = QAction("Glossary", self)
        action_glossary.triggered.connect(lambda: open_glossary(parent=self))
        self.menuHelp.addAction(action_glossary)

        self.menuHelp.addSeparator()

        action_contact = QAction("Contact Us", self)
        action_contact.triggered.connect(
            lambda: QMessageBox.information(
                self, "Contact Us",
                "For support or enquiries, please email:\nsupport@3pslcca.com"
            )
        )
        self.menuHelp.addAction(action_contact)

        action_feedback = QAction("Feedback", self)
        action_feedback.triggered.connect(
            lambda: QMessageBox.information(
                self, "Feedback",
                "We'd love to hear from you!\nSend feedback to:\nfeedback@3pslcca.com"
            )
        )
        self.menuHelp.addAction(action_feedback)

        # ── Dev menu ──────────────────────────────────────────────────────
        self.menuDev = setup_dev_menu(self, self.menubar)

        # ── Menubar ───────────────────────────────────────────────────────
        home_action = QAction("Home", self)
        home_action.setIcon(make_icon("home"))
        home_action.triggered.connect(self.show_home)

        self.log_action = QAction("&Logs", self)

        self.menubar.addAction(home_action)
        self.menubar.addMenu(self.menuFile)
        self.menubar.addAction(self.log_action)
        self.menubar.addMenu(self.menuHelp)
        if self.menuDev:
            self.menubar.addMenu(self.menuDev)

        top_bar_layout.addWidget(
            self.menubar, alignment=Qt.AlignmentFlag.AlignCenter)
        top_bar_layout.addStretch()
        self.save_status_bar = SaveStatusBar(controller=self.controller)
        top_bar_layout.addWidget(self.save_status_bar)

        self.btn_calculate = QPushButton("Calculate")
        self.btn_calculate.clicked.connect(self._run_calculate)
        top_bar_layout.addWidget(self.btn_calculate)

        self._frozen = False
        self._lock_tooltip = "Click to lock this project and prevent accidental edits."
        self.btn_lock = make_icon_btn(
            "lock-open", tooltip=self._lock_tooltip, size=30)
        self.btn_lock.setIcon(make_icon("lock-open", color=get_token("text")))
        self.btn_lock.setFixedSize(30, 30)
        _r = "border-radius:15px; min-width:30px; min-height:30px; padding:0px; border:none;"
        self.btn_lock.setStyleSheet(
            f"QPushButton               {{ {_r} background:transparent; }}"
            f"QPushButton:hover         {{ {_r} background:palette(midlight); }}"
            f"QPushButton:pressed       {{ {_r} background:palette(mid); }}"
            f"QPushButton:checked       {{ {_r} background:{get_token('primary')}; }}"
            f"QPushButton:checked:hover {{ {_r} background:{get_token('primary')}; }}"
        )
        self.btn_lock.setCheckable(True)
        self.btn_lock.installEventFilter(self)
        self.btn_lock.clicked.connect(self._on_lock_toggled)
        top_bar_layout.addWidget(self.btn_lock)

        master_layout.setMenuBar(top_bar)

        # ── Sidebar ───────────────────────────────────────────────────────
        self.sidebar = _SidebarTree()
        self.sidebar.setMinimumWidth(80)

        for header, subheaders in SIDEBAR_TREE.items():
            top_item = QTreeWidgetItem(self.sidebar)
            top_item.setText(0, header)
            if header in _SIDEBAR_ICONS:
                top_item.setIcon(0, make_icon(_SIDEBAR_ICONS[header]))
            for subheader, subitems in subheaders.items():
                sub_item = QTreeWidgetItem(top_item)
                sub_item.setText(0, subheader)
                if subheader in _SIDEBAR_ICONS:
                    sub_item.setIcon(0, make_icon(_SIDEBAR_ICONS[subheader]))
                for subitem in subitems:
                    leaf = QTreeWidgetItem(sub_item)
                    leaf.setText(0, subitem)
                    if subitem in _SIDEBAR_ICONS:
                        leaf.setIcon(0, make_icon(_SIDEBAR_ICONS[subitem]))

        self.sidebar.expandAll()

        # Find out the minimum width of the sidebar
        self.sidebar.resizeColumnToContents(0)
        self.sidebar.header().setStretchLastSection(False)

        min_width = int(
            (self.sidebar.header().sectionSize(0) + _H_PAD + _ACCENT_W) * 0.9)
        self.sidebar.header().setStretchLastSection(True)
        self.sidebar.setMinimumWidth(min_width)

        self.sidebar.itemPressed.connect(self._select_sidebar)

        # ── Content stack ─────────────────────────────────────────────────
        self.content_stack = QStackedWidget()

        self.metadata_page = QLabel()
        self.metadata_page.setAlignment(Qt.AlignCenter)

        self.logs_page = Logs(controller=self.controller)

        self.outputs_page = OutputsPage(controller=self.controller)
        self.outputs_page.navigate_requested.connect(self._navigate_to_page)
        self.outputs_page.calculation_completed.connect(
            self._on_calculation_done)
        self.outputs_page.validate_requested.connect(self._run_calculate)
        if COMPARISON_MODE:
            self.outputs_page.compare_requested.connect(self._on_compare_requested)

        # Page widgets are built lazily on first sidebar click via _get_or_create_widget
        self.widget_map = {"Results": self.outputs_page}
        self._page_names = [
            "General Information", "Bridge Data", "Construction Works Data",
            "Traffic Data", "Financial Data", "Carbon Emissions Data",
            "Maintenance and Repair", "Recycling", "Demolition",
        ]

        self.content_stack.addWidget(self.outputs_page)
        self.content_stack.addWidget(self.logs_page)

        self.log_action.triggered.connect(
            lambda: self.content_stack.setCurrentWidget(self.logs_page)
        )

        # ── Splitter ──────────────────────────────────────────────────────
        self.splitter = _HoverSplitter(Qt.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.addWidget(self.sidebar)
        self.splitter.setHandleWidth(8)
        self.splitter.addWidget(self.content_stack)
        self.splitter.setSizes([min_width, 880])

        master_layout.addWidget(self.splitter, stretch=1)
        self.main_stack.addWidget(self.project_widget)  # index 1

    def _get_or_create_widget(self, name: str):
        """Return the page widget for *name*, creating it on first access."""
        if name in self.widget_map:
            return self.widget_map[name]
        if name not in self._page_names:
            return None

        if name == "General Information":
            widget = GeneralInfo(controller=self.controller)
        elif name == "Bridge Data":
            widget = BridgeData(controller=self.controller)
        elif name == "Construction Works Data":
            widget = StructureTabView(controller=self.controller)
        elif name == "Traffic Data":
            widget = TrafficData(controller=self.controller)
        elif name == "Financial Data":
            widget = FinancialData(controller=self.controller)
        elif name == "Carbon Emissions Data":
            widget = CarbonEmissionTabView(controller=self.controller)
        elif name == "Maintenance and Repair":
            widget = Maintenance(controller=self.controller)
        elif name == "Recycling":
            widget = Recycling(controller=self.controller)
        elif name == "Demolition":
            widget = Demolition(controller=self.controller)
        else:
            return None

        self.widget_map[name] = widget
        self.content_stack.addWidget(widget)

        if name == "Construction Works Data":
            widget.tab_changed.connect(self._sync_sidebar_from_tab)
        elif name == "Carbon Emissions Data":
            widget.tab_changed.connect(self._sync_sidebar_from_tab)

        if self._frozen and hasattr(widget, "freeze"):
            widget.freeze(True)

        return widget

    def _select_sidebar(self, item: QTreeWidgetItem):
        header = item.text(0)
        parent = item.parent()

        # Direct page item - show it
        widget = self._get_or_create_widget(header)
        if widget:
            # If we are navigating AWAY from Construction Works Data or TO it directly,
            # ensure Trash view is reset.
            for w in self.widget_map.values():
                if isinstance(w, StructureTabView):
                    w.reset_view()

            self.content_stack.setCurrentWidget(widget)
            return

        # Leaf item under a tabbed page - show parent page and select tab
        if parent is not None:
            parent_name = parent.text(0)
            w = self._get_or_create_widget(parent_name)
            if w and hasattr(w, "select_tab"):
                # If this is Structure, reset the trash view before showing the tab
                if isinstance(w, StructureTabView):
                    w.reset_view()

                self.content_stack.setCurrentWidget(w)
                w.select_tab(header)

    # ── View switching ────────────────────────────────────────────────────────

    def show_home(self, tab: str = None, project_select: str = None):
        self.setWindowTitle("3psLCCA - Home")
        self.home_widget.set_active_project(
            self.project_id if self.has_project_loaded() else None
        )
        self.home_widget.refresh_project_list()
        self.main_stack.setCurrentWidget(self.home_widget)
        self.manager.refresh_all_home_screens()
        if tab == "compare":
            QTimer.singleShot(0, lambda: self.home_widget.switch_to_compare(
                preselect_pid=project_select))

    def show_project_view(self):
        if not self.has_project_loaded():
            return
        if not self._project_ui_ready:
            self._setup_project_ui()
            self._project_ui_ready = True

        display = self.controller.active_display_name or self.project_id
        self.setWindowTitle(f"3psLCCA - {display}")
        self.main_stack.setCurrentWidget(self.project_widget)

        # ── Auto-Results Logic ──────────────────────────────────────────
        # If project was previously analyzed and locked (fit for comparison),
        # land directly on the Outputs page and compile results in real-time.
        # This only runs on the INITIAL load, not when returning from Home tab.
        if self._needs_initial_landing:
            self._needs_initial_landing = False
            is_locked_on_disk = False
            try:
                info = SafeChunkEngine.get_project_info(self.project_id)
                if COMPARISON_MODE and info and info.get("user_meta", {}).get("fit_for_comparison"):
                    is_locked_on_disk = True
            except:
                pass

            if is_locked_on_disk:
                self.btn_lock.setChecked(True)
                self._on_lock_toggled(True)
                for name in self._page_names:
                    self._get_or_create_widget(name)
                self.outputs_page.register_pages(self.widget_map)
                self.content_stack.setCurrentWidget(self.outputs_page)
                self.outputs_page.run_calculation(save_cache=False)
                items = self.sidebar.findItems("Results", Qt.MatchExactly)
                if items:
                    self.sidebar.setCurrentItem(items[0])
            else:
                self.content_stack.setCurrentWidget(
                    self._get_or_create_widget("General Information"))
                items = self.sidebar.findItems(
                    "General Information", Qt.MatchExactly)
                if items:
                    self.sidebar.setCurrentItem(items[0])

    def preload_all(self, on_complete):
        """Setup project UI if needed, then build every page widget one per
        event-loop tick (non-blocking), then call on_complete."""
        if not self._project_ui_ready:
            self._setup_project_ui()
            self._project_ui_ready = True
        _order = [
            "General Information",
            "Construction Works Data", "Carbon Emissions Data",
            "Bridge Data", "Traffic Data", "Financial Data",
            "Maintenance and Repair", "Recycling", "Demolition",
        ]
        QTimer.singleShot(0, lambda: self._do_preload(_order, 0, on_complete))

    def _do_preload(self, order, index, on_complete):
        """Build one unbuilt widget, yield to event loop, then continue."""
        while index < len(order):
            name = order[index]
            index += 1
            if name not in self.widget_map:
                self._get_or_create_widget(name)
                QTimer.singleShot(
                    0, lambda i=index: self._do_preload(order, i, on_complete))
                return
        on_complete()

    def has_project_loaded(self):
        return self.project_id is not None

    # ── Calculate ─────────────────────────────────────────────────────────────

    def eventFilter(self, obj, event):
        if obj is self.btn_lock:
            if event.type() == QEvent.Type.Enter:
                pos = self.btn_lock.mapToGlobal(
                    QPoint(self.btn_lock.width() // 2,
                           self.btn_lock.height() + 4)
                )
                QToolTip.showText(pos, self._lock_tooltip, None, QRect(), 3000)
            elif event.type() == QEvent.Type.Leave:
                QToolTip.hideText()
        return super().eventFilter(obj, event)

    def _on_calculation_done(self):
        """Auto-lock the project after a successful calculation."""
        self.btn_lock.setChecked(True)
        self._on_lock_toggled(True)
        self.actionExportResultsJSON.setEnabled(True)
        self.actionExportAllDataJSON.setEnabled(True)

    def _refresh_lock_btn(self):
        if not self._project_ui_ready:
            return
        _r = "border-radius:15px; min-width:30px; min-height:30px; padding:0px; border:none;"
        self.btn_lock.setStyleSheet(
            f"QPushButton               {{ {_r} background:transparent; }}"
            f"QPushButton:hover         {{ {_r} background:palette(midlight); }}"
            f"QPushButton:pressed       {{ {_r} background:palette(mid); }}"
            f"QPushButton:checked       {{ {_r} background:{get_token('primary')}; }}"
            f"QPushButton:checked:hover {{ {_r} background:{get_token('primary')}; }}"
        )
        self.btn_lock.setIcon(
            make_icon("lock", color=get_token("base")) if self._frozen
            else make_icon("lock-open", color=get_token("text"))
        )

    def _on_lock_toggled(self, checked: bool):
        if not checked and self.outputs_page._has_results:
            reply = QMessageBox.warning(
                self,
                "Unlock Project",
                "Unlocking will clear the current results and reset all inputs.\n\nContinue?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                self.btn_lock.blockSignals(True)
                self.btn_lock.setChecked(True)
                self.btn_lock.blockSignals(False)
                return
        self.apply_lock_state(checked)

    def apply_lock_state(self, checked: bool):
        """Actually applies the locked/unlocked state - clearing cached
        results on unlock, freezing/unfreezing every page widget, and
        syncing the lock button's checked state/icon/tooltip. Split out of
        _on_lock_toggled() so ApiBridge._unlock() (POST /{project_id}/unlock)
        can apply the same state change without that method's confirmation
        dialog - a deliberate API call to a dedicated unlock endpoint is
        itself the confirmation, same as a human clicking "Yes"."""
        if not checked and self.outputs_page._has_results:
            self.outputs_page.reset_for_edit()
            self.actionExportResultsJSON.setEnabled(False)
            self.actionExportAllDataJSON.setEnabled(False)

        self._frozen = checked
        self.btn_lock.blockSignals(True)
        self.btn_lock.setChecked(checked)
        self.btn_lock.blockSignals(False)
        self.btn_lock.setIcon(
            make_icon("lock", color=get_token("base")) if checked
            else make_icon("lock-open", color=get_token("text"))
        )
        self._lock_tooltip = (
            "This project is locked.\nClick here to unlock and enable editing."
            if checked else
            "Click to lock this project and prevent accidental edits."
        )
        set_lock_tooltip_target(self.btn_lock if checked else None)
        for page in self.widget_map.values():
            if hasattr(page, "freeze"):
                page.freeze(checked)

    def _run_calculate(self):
        # Ensure all pages exist - needed for full validation and calculation
        for name in self._page_names:
            self._get_or_create_widget(name)
        self.outputs_page.register_pages(self.widget_map)
        self.outputs_page.run_validation()
        self.content_stack.setCurrentWidget(self.outputs_page)
        items = self.sidebar.findItems("Results", Qt.MatchExactly)
        if items:
            self.sidebar.setCurrentItem(items[0])

    def _sync_sidebar_from_tab(self, tab_name: str):
        """Highlight the sidebar item matching the active tab (no content switch)."""
        items = self.sidebar.findItems(
            tab_name, Qt.MatchExactly | Qt.MatchRecursive)
        if items:
            self.sidebar.setCurrentItem(items[0])

    def _navigate_to_page(self, page_name: str):
        """Navigate sidebar + content stack to a named page."""
        widget = self._get_or_create_widget(page_name)
        if widget:
            self.content_stack.setCurrentWidget(widget)
        items = self.sidebar.findItems(
            page_name, Qt.MatchExactly | Qt.MatchRecursive)
        if items:
            self.sidebar.setCurrentItem(items[0])

    def _on_compare_requested(self, project_id: str):
        if not COMPARISON_MODE:
            return
        if self.controller.engine and self.controller.engine.is_active():
            self.controller.close_project()
        self.project_id = None

        new_win = self.manager._create_window()
        new_win.show_home(tab="compare", project_select=project_id)
        new_win.show()
        new_win.activateWindow()
        self.close()

    # ── Controller signals ────────────────────────────────────────────────────

    def _on_project_loaded(self):
        if not self.controller.active_project_id:
            return
        self.project_id = self.controller.active_project_id
        self._needs_initial_landing = True
        display = self.controller.active_display_name or self.project_id
        self.setWindowTitle(f"3psLCCA - {display}")
        self.status_bar.showMessage(f"Project: {display}")

        # Apply project's unit system to the unit dropdowns
        try:
            info = self.controller.engine.fetch_chunk("general_info") or {}
            unit_system = info.get("unit_system", "metric")
            set_active_unit_system(unit_system)
        except Exception:
            pass

    def _on_fault(self, error_message: str):
        QMessageBox.critical(
            self,
            "Engine Error - Data may not be saved",
            f"Storage error:\n\n{error_message}\n\nSave a checkpoint now if possible, then restart.",
        )

    def _close_project(self):
        if FLUSH_MODE:
            if DEV_MODE:
                SysTracker.instance().snapshot(
                    f"_close_project [{self.project_id}]")
            flush_project_window(self)
        else:
            if self.controller.engine and self.controller.engine.is_active():
                self.controller.close_project()
        if self.project_id:
            from three_ps_lcca_gui.gui.api import tokens
            tokens.clear_token(self.project_id)
        self.project_id = None

        new_win = self.manager._create_window()
        new_win.show_home()
        new_win.show()
        new_win.activateWindow()
        self.close()

    def _save_now(self):
        if self.controller.engine and self.controller.engine.is_active():
            self.controller.engine.force_sync()
            self.status_bar.showMessage("Saved.", 3000)

    def _rename_project(self):
        if not self.controller.engine or not self.controller.engine.is_active():
            return
        current = self.controller.active_display_name or self.project_id
        new_name, ok = QInputDialog.getText(
            self, "Rename Project", "New name:", text=current
        )
        new_name = new_name.strip()
        if not ok or not new_name or new_name == current:
            return
        self.controller.engine.rename(new_name)
        self.controller.active_display_name = new_name
        self.setWindowTitle(f"3psLCCA - {new_name}")
        self.manager.refresh_all_home_screens()

    def _export_project(self):
        if not self.controller.engine or not self.controller.engine.is_active():
            return
        display = self.controller.active_display_name or self.project_id

        # Set default directory to Documents
        default_dir = QStandardPaths.writableLocation(
            QStandardPaths.DocumentsLocation)
        default_path = os.path.join(default_dir, f"{display}.3ps")

        dest, _ = QFileDialog.getSaveFileName(
            self, "Export Project", default_path, "3ps Archive (*.3ps)"
        )
        if not dest:
            return
        zip_name = self.controller.engine.create_checkpoint(
            label="export", notes="Exported from 3psLCCA", include_blobs=True
        )
        if not zip_name:
            QMessageBox.warning(self, "Export Failed",
                                "Could not create export archive.")
            return
        src = self.controller.engine.checkpoint_manual / zip_name
        try:
            shutil.copy2(str(src), dest)
            QMessageBox.information(
                self, "Export Complete", f"Project exported to:\n{dest}")
        except Exception as e:
            QMessageBox.warning(self, "Export Failed", str(e))

    def _export_inputs_json(self):
        for name in self._page_names:
            self._get_or_create_widget(name)
        display = self.controller.active_display_name or self.project_id or "project"
        default_dir = QStandardPaths.writableLocation(
            QStandardPaths.DocumentsLocation)
        default_path = os.path.join(default_dir, f"{display}_inputs.json")
        dest, _ = QFileDialog.getSaveFileName(
            self, "Export Inputs as JSON", default_path, "JSON Files (*.json)"
        )
        if not dest:
            return
        try:
            from three_ps_lcca_gui.gui.components.utils.export import export_inputs_json
            count = export_inputs_json(
                self.widget_map, dest, project_name=display)
            QMessageBox.information(
                self, "Export Complete",
                f"Exported {count} input section(s) to:\n{dest}",
            )
        except Exception as e:
            QMessageBox.warning(self, "Export Failed", str(e))

    def _export_results_json(self):
        export_data = self.outputs_page.get_export_data()
        if not export_data:
            QMessageBox.warning(self, "No Results", "Run the analysis first.")
            return
        display = self.controller.active_display_name or self.project_id or "project"
        default_dir = QStandardPaths.writableLocation(
            QStandardPaths.DocumentsLocation)
        default_path = os.path.join(default_dir, f"{display}_results.json")
        dest, _ = QFileDialog.getSaveFileName(
            self, "Export Results as JSON", default_path, "JSON Files (*.json)"
        )
        if not dest:
            return
        try:
            from three_ps_lcca_gui.gui.components.utils.export import export_results_json
            export_results_json(export_data, dest, project_name=display)
            QMessageBox.information(
                self, "Export Complete", f"Results exported to:\n{dest}"
            )
        except Exception as e:
            QMessageBox.warning(self, "Export Failed", str(e))

    def _export_all_data_json(self):
        export_data = self.outputs_page.get_export_data()
        if not export_data:
            QMessageBox.warning(self, "No Results", "Run the analysis first.")
            return
        display = self.controller.active_display_name or self.project_id or "project"
        default_dir = QStandardPaths.writableLocation(
            QStandardPaths.DocumentsLocation)
        default_path = os.path.join(default_dir, f"{display}_all_data.json")
        dest, _ = QFileDialog.getSaveFileName(
            self, "Export All Data as JSON", default_path, "JSON Files (*.json)"
        )
        if not dest:
            return
        try:
            from three_ps_lcca_gui.gui.components.utils.export import export_all_data_json
            export_all_data_json(export_data, dest, project_name=display)
            QMessageBox.information(
                self, "Export Complete", f"All data exported to:\n{dest}"
            )
        except Exception as e:
            QMessageBox.warning(self, "Export Failed", str(e))

    def _show_project_info(self):
        if not self.project_id:
            return
        info = SafeChunkEngine.get_project_info(self.project_id)
        if not info:
            return
        # Overlay live data from running engine
        report = self.controller.get_health_report()
        if report:
            info["pending_syncs"] = report.get("pending_syncs", 0)
            info["wal_exists"] = report.get("wal_exists", False)

        dlg = QDialog(self)
        dlg.setWindowTitle(
            f"Project Info - {info.get('display_name', self.project_id)}")
        dlg.setMinimumWidth(450)
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        rows = [
            ("Project ID",       info.get("project_id", "")),
            ("Display Name",     info.get("display_name", "")),
            ("Status",           info.get("status", "").capitalize()),
            ("Created",          info.get("created_at", "-")),
            ("Last Modified",    info.get("last_modified", "-")),
            ("Chunks",           str(info.get("chunk_count", 0))),
            ("Checkpoints",      str(info.get("checkpoint_count", 0))),
            ("Last Checkpoint",  info.get("last_checkpoint_date") or "-"),
            ("Size",             f"{info.get('size_kb', 0)} KB"),
            ("Engine Version",   info.get("engine_version", "-")),
            ("Pending Syncs",    str(info.get("pending_syncs", 0))),
            ("WAL Active",       "Yes" if info.get("wal_exists") else "No"),
        ]
        for label, value in rows:
            lbl = QLabel(value)
            lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
            form.addRow(f"{label}:", lbl)

        # Storage Path (last row, multi-line)
        project_path = info.get("project_path", "-")
        path_lbl = QLabel(project_path)
        path_lbl.setWordWrap(True)
        path_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        form.addRow("Storage Location:", path_lbl)

        layout.addLayout(form)

        btn_box = QHBoxLayout()
        btn_box.addStretch()

        def copy_all_info():
            try:
                text = f"Project Info: {info.get('display_name', self.project_id)}\n"
                text += "=" * 40 + "\n"
                for label, value in rows:
                    text += f"{label}: {value}\n"
                text += f"Storage Location: {project_path}\n"
                QApplication.clipboard().setText(text)
                copy_btn.setText("Copied!")
            except Exception:
                copy_btn.setText("Failed!")

            # Reset text after 2 seconds
            QTimer.singleShot(2000, lambda: copy_btn.setText("Copy All"))

        copy_btn = QPushButton("Copy All")
        copy_btn.setMinimumWidth(80)
        copy_btn.clicked.connect(copy_all_info)
        btn_box.addWidget(copy_btn)

        close_btn = QPushButton("Close")
        close_btn.setMinimumWidth(80)
        close_btn.clicked.connect(dlg.accept)
        btn_box.addWidget(close_btn)
        layout.addLayout(btn_box)

        dlg.exec()

    def _show_api_access(self):
        if not self.project_id:
            return
        from three_ps_lcca_gui.gui.components.api_access_dialog import ApiAccessDialog
        dlg = ApiAccessDialog(self.project_id, parent=self)
        dlg.exec()

    def _open_rollback_dialog(self):
        if not self.controller.engine or not self.controller.engine.is_active():
            return
        dlg = RollbackDialog(self.controller, parent=self)
        dlg.exec()

    def _open_blob_manager(self):
        if not self.controller.engine or not self.controller.engine.is_active():
            return
        dlg = BlobManagerDialog(self.controller, parent=self)
        dlg.exec()

    # ── Focus ─────────────────────────────────────────────────────────────────

    def changeEvent(self, event):
        """Re-asserts this window's controller as common_requested_data's
        active one whenever this window becomes the OS-active window
        (click, alt-tab, or ProjectManager.open_project()'s
        activateWindow() call on an already-open project) - that module
        backs get_currency()/get_project_iso3()/etc. with a single
        process-wide global, set only once per window at creation
        (ProjectManager._create_window()) and otherwise never updated, so
        with 2+ project windows open those helpers could silently return a
        DIFFERENT (whichever was created most recently) project's data
        instead of this window's own - confirmed live via manual testing.
        gui/api/bridge.py's _find_window() has the equivalent fix for
        API-triggered reads; this is the GUI-side half, for when a human
        just clicks between windows with no API involved."""
        super().changeEvent(event)
        if event.type() == QEvent.ActivationChange and self.isActiveWindow() and self.controller:
            from three_ps_lcca_gui.gui.components.utils.common_requested_data import set_controller
            set_controller(self.controller)

    # ── Close ─────────────────────────────────────────────────────────────────

    def closeEvent(self, event):
        if FLUSH_MODE:
            if DEV_MODE:
                SysTracker.instance().snapshot(
                    f"closeEvent [{self.project_id}]")
            flush_project_window(self)
        else:
            if self.controller.engine:
                self.controller.close_project()
        if self.project_id:
            from three_ps_lcca_gui.gui.api import tokens
            tokens.clear_token(self.project_id)
        self.project_id = None
        self.manager.remove_window(self)
        self.manager.refresh_all_home_screens()
        event.accept()
