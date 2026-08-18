import sys
import os
import platform
import ctypes

# ── Global App Configuration ──────────────────────────────────────────────────
# This MUST happen before any other project imports to ensure paths are set correctly
from three_ps_lcca_gui.gui.version import APP_NAME, APP_AUTHOR, APP_DATA_NAME
from three_ps_lcca_gui.core.safechunk_engine import SafeChunkEngine
SafeChunkEngine.APP_NAME = APP_NAME
SafeChunkEngine.APP_AUTHOR = APP_AUTHOR
SafeChunkEngine.APP_DATA_NAME = APP_DATA_NAME

# Conda-forge's PySide6 build ships no Wayland platform plugin, so on a Wayland
# session Qt prints a "Could not find the Qt platform plugin wayland" warning
# before falling back to xcb (via XWayland) and working normally anyway. Skip
# straight to xcb to silence the noise; no-op if the user set their own
# QT_QPA_PLATFORM. See devtools/dev_notes_log/3psLCCA_wayland_plugin_warning.md.
if platform.system() == "Linux" and "QT_QPA_PLATFORM" not in os.environ:
    os.environ["QT_QPA_PLATFORM"] = "xcb"

from PySide6.QtWidgets import (
    QApplication,
    QSpinBox,
    QDoubleSpinBox,
    QComboBox,
    QLineEdit,
    QProxyStyle,
    QStyle,
    QTableView,
    QTableWidget,
)
from three_ps_lcca_gui.gui.components.utils.table_widgets import (
    GroupedHeaderView,
    WordWrapHeaderView,
)
from PySide6.QtCore import QObject, QEvent, Qt, QTimer, QCoreApplication
from PySide6.QtGui import QFont, QFontDatabase, QIcon

# Custom UI Components and Managers
from three_ps_lcca_gui.gui.components.splash_screen import SplashScreen
from three_ps_lcca_gui.gui.project_manager import ProjectManager
from three_ps_lcca_gui.gui.themes import reapply as _reapply
from three_ps_lcca_gui.gui.components.utils.unit_resolver import load_custom_units
from three_ps_lcca_gui.gui.version import VERSION


_GUI_DIR = os.path.abspath(os.path.dirname(__file__))
_ASSETS_DIR = os.path.join(_GUI_DIR, "assets")

# ── Global UI Behavior Overrides ──────────────────────────────────────────────


class _ComboItemStyle(QProxyStyle):
    """Enforces minimum item height in combo popups and removes the harsh OS drop shadow."""

    _MIN_H = 36

    def sizeFromContents(self, ct, opt, sz, widget=None):
        size = super().sizeFromContents(ct, opt, sz, widget)
        if ct == QStyle.ContentsType.CT_ItemViewItem and size.height() < self._MIN_H:
            size.setHeight(self._MIN_H)
        return size

    def styleHint(self, hint, opt=None, widget=None, returnData=None):
        if hint == QStyle.SH_ComboBox_Popup:
            return 0  # keep combobox-popup: 0 behaviour
        return super().styleHint(hint, opt, widget, returnData)

    def drawComplexControl(self, cc, opt, p, widget=None):
        super().drawComplexControl(cc, opt, p, widget)
        # Remove OS drop shadow from the popup view after it is shown
        if cc == QStyle.CC_ComboBox and widget is not None:
            view = getattr(widget, "view", None)
            if callable(view):
                v = view()
                if v and v.window():
                    w = v.window()
                    flags = w.windowFlags()
                    if not (flags & Qt.NoDropShadowWindowHint):
                        w.setWindowFlags(flags | Qt.NoDropShadowWindowHint)
                        w.show()


class _TableRowSelectFilter(QObject):
    """Enforces row selection and hover tracking on all TableViews."""

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Polish and isinstance(obj, QTableView):
            obj.setSelectionMode(QTableView.SingleSelection)
            obj.setSelectionBehavior(QTableView.SelectRows)
            obj.setMouseTracking(True)
        return super().eventFilter(obj, event)



class _TableHeaderWordWrapFilter(QObject):
    """Installs WordWrapHeaderView on every QTableWidget/QTableView that does not
    already use GroupedHeaderView (which handles word wrap itself)."""

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Polish and isinstance(obj, (QTableWidget, QTableView)):
            hdr = obj.horizontalHeader()
            if not isinstance(hdr, (GroupedHeaderView, WordWrapHeaderView)):
                # Defer header swap: calling setHorizontalHeader() synchronously
                # during Polish (which fires mid-reparent inside addWidget) causes
                # a segfault because the widget tree is in an inconsistent state.
                QTimer.singleShot(0, lambda o=obj: self._install_word_wrap_header(o))
        return super().eventFilter(obj, event)

    @staticmethod
    def _install_word_wrap_header(obj):
        try:
            hdr = obj.horizontalHeader()
        except RuntimeError:
            return
        if isinstance(hdr, (GroupedHeaderView, WordWrapHeaderView)):
            return
        count = hdr.count()
        modes        = [hdr.sectionResizeMode(i) for i in range(count)]
        sizes        = [hdr.sectionSize(i) for i in range(count)]
        hidden       = [hdr.isSectionHidden(i) for i in range(count)]
        stretch_last = hdr.stretchLastSection()
        min_size     = hdr.minimumSectionSize()
        new_hdr = WordWrapHeaderView(Qt.Horizontal, parent=obj)
        obj.setHorizontalHeader(new_hdr)
        new_hdr.setStretchLastSection(stretch_last)
        new_hdr.setMinimumSectionSize(min_size)
        for i in range(count):
            new_hdr.setSectionResizeMode(i, modes[i])
            new_hdr.resizeSection(i, sizes[i])
            if hidden[i]:
                new_hdr.hideSection(i)


class DisableSpinBoxScroll(QObject):
    """Prevents mouse wheel from changing values in SpinBoxes/Combos."""

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Wheel:
            if isinstance(obj, (QSpinBox, QDoubleSpinBox, QComboBox)):
                if obj.parent():
                    QApplication.instance().sendEvent(obj.parent(), event)
                return True
        return super().eventFilter(obj, event)


class SelectTextOnFocus(QObject):
    """Selects all text when a QLineEdit is clicked."""

    watching = None

    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseButtonRelease and isinstance(obj, QLineEdit):
            if self.watching != obj and obj.isEnabled():
                self.watching = obj
                obj.selectAll()
        return super().eventFilter(obj, event)


# ── Main Entry Point ──────────────────────────────────────────────────────────


def _setup_logging():
    import logging
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s  %(levelname)-7s  %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )
    # Quieten noisy third-party loggers
    for noisy in ("PIL", "matplotlib", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def main():
    from three_ps_lcca_gui.gui._CONFIG import DEV_MODE, ATTACH_LOGGER
    if not DEV_MODE:
        import builtins, warnings
        builtins.print = lambda *a, **k: None
        warnings.filterwarnings("ignore")
    if ATTACH_LOGGER:
        _setup_logging()

    # Windows: set AppUserModelID before QApplication so Task Manager
    # shows the app icon instead of the Python interpreter icon.
    if platform.system() == "Windows":
        try:
            # Format: Organization.AppName
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                f"{APP_AUTHOR}.{APP_NAME}"
            )
        except Exception:
            pass

    # Configure High DPI and Scaling
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
    os.environ["QT_SCALE_FACTOR"] = "1"
    QCoreApplication.setAttribute(
        Qt.ApplicationAttribute.AA_DontUseNativeMenuBar)

    app = QApplication(sys.argv)
    app.setApplicationName("OS Bridge LCCA")
    app.setOrganizationName("OSBridge")

    # Set Window Icon
    _ICON_PATH = os.path.join(_ASSETS_DIR, "logo", "logo-3psLCCA.ico")
    if os.path.exists(_ICON_PATH):
        app.setWindowIcon(QIcon(_ICON_PATH))

    # Linux: link to .desktop file so taskbar/task-manager uses the app icon
    if platform.system() == "Linux":
        app.setDesktopFileName("3psLCCA")

    # Initialize Style and Theme before showing Splash
    app.setStyle(_ComboItemStyle("Fusion"))
    _reapply(app)

    # Show Custom Splash Screen
    splash = SplashScreen()
    splash.show()
    app.processEvents()

    # Load Bundled Fonts
    _font_dir = os.path.join(_ASSETS_DIR, "themes", "Ubuntu_font")
    if os.path.exists(_font_dir):
        for _ttf in [
            "Ubuntu-Light.ttf",
            "Ubuntu-LightItalic.ttf",
            "Ubuntu-Regular.ttf",
            "Ubuntu-Italic.ttf",
            "Ubuntu-Medium.ttf",
            "Ubuntu-MediumItalic.ttf",
            "Ubuntu-Bold.ttf",
            "Ubuntu-BoldItalic.ttf",
        ]:
            QFontDatabase.addApplicationFont(os.path.join(_font_dir, _ttf))

    # Set app-level default font- body size, normal weight.
    # With font-size removed from the global QSS * rule, this becomes the
    # fallback for any widget that does not call setFont() explicitly.
    # Widgets that do call setFont(_f(...)) will use their own size correctly.
    app.setFont(QFont("Ubuntu", 9))

    # Load Custom Units (deferred to start of event loop)
    def _load_custom_units():
        try:

            load_custom_units()
        except Exception as _e:
            print(f"Warning: Could not load custom units: {_e}")

    QTimer.singleShot(0, _load_custom_units)

    # Install Global Event Filters
    # NOTE: named references required - Python GC will collect anonymous instances
    wheel_filter      = DisableSpinBoxScroll()
    table_filter      = _TableRowSelectFilter()
    focus_filter      = SelectTextOnFocus()
    hdr_wrap_filter   = _TableHeaderWordWrapFilter()
    app.installEventFilter(wheel_filter)
    app.installEventFilter(table_filter)
    app.installEventFilter(focus_filter)
    app.installEventFilter(hdr_wrap_filter)

    # Runtime Theme Switching (Qt 6.5+)
    try:
        app.styleHints().colorSchemeChanged.connect(lambda s: _reapply(app))
    except AttributeError:
        pass

    # Handle First Launch Dialog
    import three_ps_lcca_gui.core.start_manager as sm

    if sm.is_first_launch():
        from three_ps_lcca_gui.gui.components.first_launch_dialog import FirstLaunchDialog

        splash.hide()
        dlg = FirstLaunchDialog()
        if dlg.exec() == FirstLaunchDialog.Accepted:
            sm.set_name(dlg.get_name())
        else:
            sm.set_name("")  # Mark as seen

    # Start resource tracker (dev mode + logger only)
    from three_ps_lcca_gui.gui._CONFIG import DEV_MODE, ATTACH_LOGGER, LOCAL_API_ENABLED
    if DEV_MODE and ATTACH_LOGGER:
        from three_ps_lcca_gui.gui.sys_tracker import SysTracker
        SysTracker.instance().start()

    # Initialize Project Manager and Close Splash
    manager = ProjectManager()

    # Local HTTP API - lets external tools read/update an open project's GUI.
    # LOCAL_API_ENABLED is a hard kill switch (off by default, not yet ready
    # for release); the settings toggle only matters once it's True. Failure
    # to bind must never block startup.
    if LOCAL_API_ENABLED and sm.get_pref("api_enabled", "true") == "true":
        from three_ps_lcca_gui.gui.api.server import start_api_server

        api_handle = start_api_server(manager)
        if api_handle:
            app.aboutToQuit.connect(api_handle.shutdown)

    # Heavy work first - splash stays visible during entire load
    manager.open_project()

    # Pass main window so Qt waits until it's visible AND MIN_DISPLAY_MS has elapsed
    main_win = manager.windows[0] if manager.windows else None
    splash.finish(main_win)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
