from __future__ import annotations
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtWidgets import QApplication, QWidget

"""
PESTICIDE.py - Qt Layout Debugger.

API:
    paraside(mode)   - 'rainbow' | 'beast' | 'off'
    inspector(show)  - show/hide inspector panel independently

Controls (when active):
    Hover            - overlay rect + live inspector update
    Alt + click      - lock / unlock inspector to a widget
"""


def _qt():
    for pkg in ("PySide6.QtWidgets", "PyQt6.QtWidgets", "PyQt5.QtWidgets", "PySide2.QtWidgets"):
        if pkg in sys.modules: return sys.modules[pkg]
    import importlib
    return importlib.import_module("PySide6.QtWidgets")

def _qt_core():
    for pkg in ("PySide6.QtCore", "PyQt6.QtCore", "PyQt5.QtCore", "PySide2.QtCore"):
        if pkg in sys.modules: return sys.modules[pkg]
    import importlib
    return importlib.import_module("PySide6.QtCore")

def _qt_gui():
    for pkg in ("PySide6.QtGui", "PyQt6.QtGui", "PyQt5.QtGui", "PySide2.QtGui"):
        if pkg in sys.modules: return sys.modules[pkg]
    import importlib
    return importlib.import_module("PySide6.QtGui")


# ─── State ────────────────────────────────────────────────────────────────────

_ACTIVE_MODE = "off"
_LISTENER    = None
_OVERLAY     = None   # _OverlayRect instance (lazy)
_INSPECTOR   = None   # _InspectorPanel instance (lazy)
_LOCKED      = None   # widget ref when locked
_PICK_MODE   = False  # True = hover tracks widgets, click selects & exits pick


# ─── Public API ───────────────────────────────────────────────────────────────

def paraside(mode: str = "rainbow"):
    """
    'rainbow' - colored borders on every widget.
    'beast'   - borders + inspector panel visible.
    'off'     - restore standard UI.
    """
    global _ACTIVE_MODE
    _ACTIVE_MODE = mode

    app = _qt().QApplication.instance()
    if not app: return

    _uninstall_interceptor()
    app.setStyleSheet("")
    for w in app.topLevelWidgets():
        _cleanup_widget(w)

    if mode == "off":
        _hide_tools()
        from three_ps_lcca_gui.gui.themes import reapply
        reapply(app)
        return

    app.setStyleSheet(get_debug_styles(padding=4 if mode == "beast" else None))
    for w in app.topLevelWidgets():
        _force_debug_style_recursive(w)

    _install_interceptor(app)

    if mode == "beast":
        _get_inspector().show()
        _get_inspector().raise_()


def inspector(show: bool = True):
    """Show or hide the inspector panel independently of debug mode."""
    panel = _get_inspector()
    if show:
        panel.show()
        panel.raise_()
    else:
        panel.hide()


# ─── Overlay Rect ─────────────────────────────────────────────────────────────

def _get_overlay():
    global _OVERLAY
    if _OVERLAY is None:
        _OVERLAY = _create_overlay()
    return _OVERLAY


def _create_overlay():
    QtWidgets = _qt()
    QtCore    = _qt_core()
    QtGui     = _qt_gui()

    class OverlayRect(QtWidgets.QWidget):
        def __init__(self):
            super().__init__(None)
            self.setWindowFlags(
                QtCore.Qt.FramelessWindowHint |
                QtCore.Qt.WindowStaysOnTopHint |
                QtCore.Qt.Tool
            )
            self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
            self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
            self._locked = False

        def track(self, widget, locked: bool = False):
            self._locked = locked
            if not widget:
                self.hide()
                return
            try:
                tl = widget.mapToGlobal(QtCore.QPoint(0, 0))
                self.setGeometry(tl.x(), tl.y(), widget.width(), widget.height())
                self.show()
                self.raise_()
                self.update()
            except RuntimeError:
                self.hide()

        def paintEvent(self, event):
            painter = QtGui.QPainter(self)
            # Blue = hover, Orange = locked
            if self._locked:
                border = QtGui.QColor(255, 140,   0, 230)
                fill   = QtGui.QColor(255, 140,   0,  25)
            else:
                border = QtGui.QColor(  0, 120, 215, 200)
                fill   = QtGui.QColor(  0, 120, 215,  20)
            painter.setPen(QtGui.QPen(border, 2))
            painter.setBrush(fill)
            painter.drawRect(self.rect().adjusted(1, 1, -1, -1))

    return OverlayRect()


# ─── Inspector Panel ──────────────────────────────────────────────────────────

def _get_inspector():
    global _INSPECTOR
    if _INSPECTOR is None:
        _INSPECTOR = _create_inspector()
    return _INSPECTOR


def _create_inspector():
    QtWidgets = _qt()
    QtCore    = _qt_core()
    QtGui     = _qt_gui()

    PANEL_STYLE = """
        QWidget          { background: #1e1e1e; color: #d4d4d4;
                           font: 11px 'Consolas', 'Courier New', monospace; }
        QLabel#section   { color: #569cd6; font-weight: bold;
                           padding: 6px 0 2px 0; }
        QLabel#key       { color: #9cdcfe; min-width: 96px; padding-right: 8px; }
        QLabel#val       { color: #ce9178; }
        QLabel#header    { font: bold 12px 'Consolas'; color: #ffffff; }
        QScrollArea      { border: none; background: transparent; }
        QScrollBar:vertical   { background: #2d2d2d; width: 6px; }
        QScrollBar::handle:vertical { background: #555; border-radius: 3px; }
        QPushButton      { background: #2d2d2d; border: 1px solid #555;
                           color: #d4d4d4; padding: 2px 10px; border-radius: 2px; }
        QPushButton:hover   { background: #3e3e3e; }
        QPushButton:checked { background: #264f78; border-color: #4e9acf; color: #fff; }
        QTextEdit        { background: #0d0d0d; border: 1px solid #333;
                           color: #9cdcfe; font: 10px 'Consolas'; }
        QTreeWidget      { background: #1a1a1a; border: 1px solid #333;
                           color: #d4d4d4; outline: none; }
        QTreeWidget::item          { padding: 1px 0; }
        QTreeWidget::item:selected { background: #264f78; color: #fff; }
        QHeaderView::section { background: #2d2d2d; border: none;
                               color: #aaa; padding: 2px 4px; }
        QTabWidget::pane   { border: none; }
        QTabBar::tab       { background: #2d2d2d; color: #888; padding: 4px 14px;
                             border: none; border-bottom: 2px solid transparent; }
        QTabBar::tab:selected { background: #1e1e1e; color: #fff;
                                border-bottom: 2px solid #569cd6; }
        QSplitter::handle { background: #333; }
    """

    class InspectorPanel(QtWidgets.QWidget):
        def __init__(self):
            super().__init__(None)
            self.setWindowTitle("PESTICIDE Inspector")
            self.setWindowFlags(QtCore.Qt.Tool | QtCore.Qt.WindowStaysOnTopHint)
            self.resize(340, 620)
            self.setStyleSheet(PANEL_STYLE)
            self._current = None
            self._tree_map: dict[int, object] = {}
            self._build_ui()

        # ── Build UI ─────────────────────────────────────────────────────────

        def _build_ui(self):
            root = QtWidgets.QVBoxLayout(self)
            root.setContentsMargins(0, 0, 0, 0)
            root.setSpacing(0)

            # Header bar
            bar = QtWidgets.QWidget()
            bar.setStyleSheet("background:#2d2d2d; border-bottom:1px solid #444;")
            blay = QtWidgets.QHBoxLayout(bar)
            blay.setContentsMargins(8, 5, 8, 5)
            self._lbl_header = QtWidgets.QLabel("- no selection -")
            self._lbl_header.setObjectName("header")
            blay.addWidget(self._lbl_header, 1)
            self._btn_pick = QtWidgets.QCheckBox("Pick")
            self._btn_pick.setToolTip("Pick mode - hover to highlight, click to select")
            self._btn_pick.toggled.connect(self._on_pick_toggled)
            blay.addWidget(self._btn_pick)
            self._btn_lock = QtWidgets.QPushButton("🔒")
            self._btn_lock.setCheckable(True)
            self._btn_lock.setFixedWidth(32)
            self._btn_lock.setToolTip("Lock selection (Alt+click a widget)")
            self._btn_lock.toggled.connect(self._on_lock_toggled)
            blay.addWidget(self._btn_lock)
            root.addWidget(bar)

            # Tabs
            tabs = QtWidgets.QTabWidget()
            root.addWidget(tabs)

            # ── Tab: Info ──────────────────────────────────────────────────
            scroll = QtWidgets.QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
            container = QtWidgets.QWidget()
            self._info_layout = QtWidgets.QVBoxLayout(container)
            self._info_layout.setContentsMargins(8, 4, 8, 8)
            self._info_layout.setSpacing(1)
            self._info_layout.addStretch()
            scroll.setWidget(container)
            tabs.addTab(scroll, "Info")

            # ── Tab: Style ─────────────────────────────────────────────────
            self._ss_edit = QtWidgets.QTextEdit()
            self._ss_edit.setReadOnly(True)
            self._ss_edit.setPlaceholderText("(no local stylesheet on this widget)")
            tabs.addTab(self._ss_edit, "Style")

            # ── Tab: Tree ──────────────────────────────────────────────────
            tree_wrap = QtWidgets.QWidget()
            tlay = QtWidgets.QVBoxLayout(tree_wrap)
            tlay.setContentsMargins(4, 4, 4, 4)
            tlay.setSpacing(4)
            btn_refresh = QtWidgets.QPushButton("↺  Refresh Tree")
            btn_refresh.clicked.connect(self._rebuild_tree)
            tlay.addWidget(btn_refresh)
            self._tree = QtWidgets.QTreeWidget()
            self._tree.setHeaderLabels(["Type", "objectName"])
            self._tree.header().setStretchLastSection(True)
            self._tree.setColumnWidth(0, 175)
            self._tree.itemClicked.connect(self._on_tree_click)
            tlay.addWidget(self._tree)
            tabs.addTab(tree_wrap, "Tree")

        # ── Helpers ──────────────────────────────────────────────────────────

        def _section(self, title: str) -> "QLabel":
            sep = QtWidgets.QFrame()
            sep.setFrameShape(QtWidgets.QFrame.HLine)
            sep.setStyleSheet("color:#333;")
            lbl = QtWidgets.QLabel(title)
            lbl.setObjectName("section")
            wrap = QtWidgets.QWidget()
            wl = QtWidgets.QVBoxLayout(wrap)
            wl.setContentsMargins(0, 4, 0, 0)
            wl.setSpacing(0)
            wl.addWidget(sep)
            wl.addWidget(lbl)
            return wrap

        def _row(self, key: str, val: str) -> "QWidget":
            row = QtWidgets.QWidget()
            rl = QtWidgets.QHBoxLayout(row)
            rl.setContentsMargins(4, 0, 0, 0)
            rl.setSpacing(0)
            k = QtWidgets.QLabel(key)
            k.setObjectName("key")
            k.setFixedWidth(96)
            v = QtWidgets.QLabel(str(val))
            v.setObjectName("val")
            v.setWordWrap(False)
            v.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
            rl.addWidget(k)
            rl.addWidget(v, 1)
            return row

        def _clear_info(self):
            il = self._info_layout
            while il.count() > 1:
                item = il.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

        def _add(self, widget):
            self._info_layout.insertWidget(self._info_layout.count() - 1, widget)

        # ── Lock ─────────────────────────────────────────────────────────────

        def _on_pick_toggled(self, checked: bool):
            global _PICK_MODE
            _PICK_MODE = checked
            if not checked and not _LOCKED:
                _get_overlay().track(None)

        def _on_lock_toggled(self, checked: bool):
            global _LOCKED
            _LOCKED = self._current if checked else None
            if checked:
                _get_overlay().track(self._current, locked=True)
            else:
                _get_overlay().track(None)

        def set_locked(self, widget, locked: bool, exit_pick: bool = False):
            global _LOCKED, _PICK_MODE
            _LOCKED = widget if locked else None
            self._current = widget
            self._btn_lock.blockSignals(True)
            self._btn_lock.setChecked(locked)
            self._btn_lock.blockSignals(False)
            if exit_pick:
                _PICK_MODE = False
                self._btn_pick.blockSignals(True)
                self._btn_pick.setChecked(False)
                self._btn_pick.blockSignals(False)
            self.update_widget(widget)
            if locked:
                _get_overlay().track(widget, locked=True)
            else:
                _get_overlay().track(None)

        # ── Update ───────────────────────────────────────────────────────────

        def update_widget(self, widget):
            if _LOCKED and widget is not _LOCKED:
                return
            self._current = widget
            self._clear_info()

            if not widget:
                self._lbl_header.setText("- no selection -")
                self._ss_edit.setPlainText("")
                return

            try:
                self._populate(widget)
            except RuntimeError:
                self._lbl_header.setText("(widget was deleted)")

        def _populate(self, w):
            QtCore2 = _qt_core()
            QMAX = 16777215

            cls  = type(w).__name__
            name = w.objectName() or ""
            mod  = type(w).__module__ or ""
            self._lbl_header.setText(cls + (f"  #{name}" if name else ""))

            # ── Identity ──
            self._add(self._section("IDENTITY"))
            self._add(self._row("class",       cls))
            if name:
                self._add(self._row("objectName", name))
            self._add(self._row("module",      mod))

            # ── Geometry ──
            self._add(self._section("GEOMETRY"))
            local_pos  = w.pos()
            global_pos = w.mapToGlobal(QtCore2.QPoint(0, 0))
            sz   = w.size()
            hint = w.sizeHint()
            mh   = w.minimumSizeHint()
            mnsz = w.minimumSize()
            mxsz = w.maximumSize()
            self._add(self._row("pos (local)",  f"{local_pos.x()}, {local_pos.y()}"))
            self._add(self._row("pos (global)", f"{global_pos.x()}, {global_pos.y()}"))
            self._add(self._row("size",         f"{sz.width()} × {sz.height()}"))
            self._add(self._row("sizeHint",     f"{hint.width()} × {hint.height()}"))
            self._add(self._row("minSizeHint",  f"{mh.width()} × {mh.height()}"))
            self._add(self._row("minSize",      f"{mnsz.width()} × {mnsz.height()}"))
            mxw = "∞" if mxsz.width()  >= QMAX else str(mxsz.width())
            mxh = "∞" if mxsz.height() >= QMAX else str(mxsz.height())
            self._add(self._row("maxSize",      f"{mxw} × {mxh}"))

            # ── Size Policy ──
            self._add(self._section("SIZE POLICY"))
            sp = w.sizePolicy()
            self._add(self._row("horizontal", _policy_name(sp.horizontalPolicy())))
            self._add(self._row("vertical",   _policy_name(sp.verticalPolicy())))
            self._add(self._row("hStretch",   str(sp.horizontalStretch())))
            self._add(self._row("vStretch",   str(sp.verticalStretch())))

            # ── State ──
            self._add(self._section("STATE"))
            self._add(self._row("visible",    "yes" if w.isVisible() else "NO"))
            self._add(self._row("enabled",    "yes" if w.isEnabled() else "NO"))
            self._add(self._row("underMouse", "yes" if w.underMouse() else "no"))

            # ── Layout ──
            self._add(self._section("LAYOUT"))
            parent = w.parent()
            pl = None
            if parent:
                try:
                    pl = parent.layout()
                except TypeError:
                    pl = None  # .layout is an instance attr, not a method
            if pl:
                pm = pl.contentsMargins()
                self._add(self._row("parent layout", type(pl).__name__))
                self._add(self._row("margins",       f"{pm.left()},{pm.top()},{pm.right()},{pm.bottom()}"))
                self._add(self._row("spacing",       str(pl.spacing())))
                idx = pl.indexOf(w)
                if idx >= 0:
                    self._add(self._row("index",     str(idx)))
            else:
                self._add(self._row("parent layout", "none"))

            own = None
            try:
                own = w.layout()
            except TypeError:
                pass
            if own:
                om = own.contentsMargins()
                self._add(self._row("own layout",   type(own).__name__))
                self._add(self._row("own margins",  f"{om.left()},{om.top()},{om.right()},{om.bottom()}"))
                self._add(self._row("own spacing",  str(own.spacing())))
                self._add(self._row("child items",  str(own.count())))

            # ── Parent chain ──
            self._add(self._section("PARENT CHAIN"))
            chain, p = [], w.parent()
            while p:
                n  = type(p).__name__
                oid = p.objectName()
                chain.append(n + (f"#{oid}" if oid else ""))
                p = p.parent()
            chain_str = " → ".join(chain[:6]) + ("…" if len(chain) > 6 else "")
            lbl = QtWidgets.QLabel(chain_str or "(top-level)")
            lbl.setObjectName("val")
            lbl.setWordWrap(True)
            lbl.setTextInteractionFlags(QtCore2.Qt.TextSelectableByMouse)
            lbl.setContentsMargins(4, 0, 0, 0)
            self._add(lbl)

            # ── Style tab ──
            self._ss_edit.setPlainText(w.styleSheet() or "")

        # ── Tree ─────────────────────────────────────────────────────────────

        def _rebuild_tree(self):
            self._tree.clear()
            self._tree_map.clear()
            app = _qt().QApplication.instance()
            if not app: return
            for w in app.topLevelWidgets():
                if w is self or w is _OVERLAY: continue
                self._tree.addTopLevelItem(self._make_item(w))
            self._tree.expandToDepth(2)

        def _make_item(self, widget) -> "QTreeWidgetItem":
            QtWidgets2 = _qt()
            QtCore2    = _qt_core()
            cls  = type(widget).__name__
            name = widget.objectName() or ""
            item = QtWidgets2.QTreeWidgetItem([cls, name])
            item.setData(0, QtCore2.Qt.UserRole, id(widget))
            self._tree_map[id(widget)] = widget
            for child in widget.children():
                if isinstance(child, QtWidgets2.QWidget):
                    item.addChild(self._make_item(child))
            return item

        def _on_tree_click(self, item, _col):
            wid    = item.data(0, _qt_core().Qt.UserRole)
            widget = self._tree_map.get(wid)
            if not widget: return
            try:
                self.set_locked(widget, True)
            except RuntimeError:
                pass

    return InspectorPanel()


# ─── Interceptor ──────────────────────────────────────────────────────────────

class _PesticideInterceptor(_qt_core().QObject):
    def __init__(self):
        super().__init__()
        self._hovered = None

    def eventFilter(self, obj, event):
        QtCore    = _qt_core()
        QtWidgets = _qt()

        etype = event.type()

        # Inject borders + enable mouse tracking on newly polished widgets
        if etype == QtCore.QEvent.Polish:
            if isinstance(obj, QtWidgets.QWidget):
                obj.setMouseTracking(True)
                if _ACTIVE_MODE != "off":
                    _inject_pesticide_style(obj)

        # Hover → update overlay + inspector
        if etype == QtCore.QEvent.MouseMove:
            self._on_move()

        # Click handling
        if etype == QtCore.QEvent.MouseButtonPress:
            mods = event.modifiers() if hasattr(event, "modifiers") else QtCore.Qt.NoModifier
            if _PICK_MODE:
                # Pick mode: consume only if we picked an app widget
                # (lets clicks on the inspector panel itself pass through)
                if self._on_pick_click():
                    return True
            elif mods & QtCore.Qt.AltModifier:
                # Alt+click: toggle lock without pick mode
                self._on_alt_click()
                return True

        return super().eventFilter(obj, event)

    def _on_move(self):
        if not _PICK_MODE or _LOCKED:
            return
        QtWidgets = _qt()
        QtGui     = _qt_gui()
        widget    = QtWidgets.QApplication.widgetAt(QtGui.QCursor.pos())

        if widget is self._hovered:
            return
        if widget and widget.objectName().startswith("__p_"):
            return
        if widget and _INSPECTOR and widget.window() is _INSPECTOR:
            return
        if widget and _OVERLAY and widget.window() is _OVERLAY:
            return

        self._hovered = widget
        _get_overlay().track(widget, locked=False)
        if _INSPECTOR and _INSPECTOR.isVisible():
            _INSPECTOR.update_widget(widget)

    def _on_pick_click(self) -> bool:
        """Returns True if the event should be consumed (picked an app widget)."""
        QtWidgets = _qt()
        QtGui     = _qt_gui()
        widget    = QtWidgets.QApplication.widgetAt(QtGui.QCursor.pos())
        if not widget: return False
        if widget.objectName().startswith("__p_"): return False
        if _INSPECTOR and widget.window() is _INSPECTOR: return False
        if _OVERLAY   and widget.window() is _OVERLAY:   return False
        panel = _get_inspector()
        if not panel.isVisible():
            panel.show()
            panel.raise_()
        panel.set_locked(widget, True, exit_pick=True)
        return True

    def _on_alt_click(self):
        QtWidgets = _qt()
        QtGui     = _qt_gui()
        widget    = QtWidgets.QApplication.widgetAt(QtGui.QCursor.pos())
        if not widget: return
        if widget.objectName().startswith("__p_"): return
        if _INSPECTOR and widget.window() is _INSPECTOR: return
        if _OVERLAY   and widget.window() is _OVERLAY:   return

        panel    = _get_inspector()
        is_same  = (widget is _LOCKED)
        new_lock = not is_same          # toggle off if same widget, on if new

        panel.set_locked(widget if new_lock else None, new_lock)
        if not panel.isVisible():
            panel.show()
            panel.raise_()


def _install_interceptor(app):
    global _LISTENER
    if not _LISTENER:
        _LISTENER = _PesticideInterceptor()
        app.installEventFilter(_LISTENER)
        for w in app.topLevelWidgets():
            _enable_mouse_tracking(w)


def _enable_mouse_tracking(w):
    try:
        w.setMouseTracking(True)
        for child in w.findChildren(_qt().QWidget):
            child.setMouseTracking(True)
    except RuntimeError:
        pass


def _uninstall_interceptor():
    global _LISTENER, _LOCKED, _PICK_MODE
    if _LISTENER:
        app = _qt().QApplication.instance()
        if app: app.removeEventFilter(_LISTENER)
        _LISTENER = None
    _LOCKED    = None
    _PICK_MODE = False


def _hide_tools():
    if _OVERLAY   and _OVERLAY.isVisible():   _OVERLAY.hide()
    if _INSPECTOR and _INSPECTOR.isVisible(): _INSPECTOR.hide()


# ─── Style Injection ──────────────────────────────────────────────────────────

def _cleanup_widget(w):
    try:
        ss = w.styleSheet() or ""
        if "/* pesticide */" in ss:
            ss = ss.split("/* pesticide */")[0].strip()
        w.setStyleSheet(ss)
        for child in w.findChildren(_qt().QWidget):
            if child.parent() is w:
                _cleanup_widget(child)
    except RuntimeError:
        pass


def _force_debug_style_recursive(w):
    _inject_pesticide_style(w)
    for child in w.findChildren(_qt().QWidget):
        if child.parent() is w:
            _force_debug_style_recursive(child)


def _inject_pesticide_style(w):
    if not w or w.objectName().startswith("__p_"):
        return
    if _INSPECTOR and w.window() is _INSPECTOR: return
    if _OVERLAY   and w.window() is _OVERLAY:   return

    existing = (w.styleSheet() or "").strip()
    if not existing or "/* pesticide */" in existing:
        return

    cls = type(w).__name__
    if   "Label"  in cls: color = "rgba(255,   0, 255, 180)"
    elif "Button" in cls: color = "rgba(255, 165,   0, 200)"
    elif "Edit"   in cls or "Combo" in cls: color = "rgba(  0, 255, 255, 200)"
    elif "Frame"  in cls or "Group" in cls: color = "rgba(  0,   0, 255, 120)"
    elif "Scroll" in cls or "Stack" in cls: color = "rgba(255,  20, 147, 150)"
    else:                                   color = "rgba(255,   0,   0, 150)"

    pad = "padding: 4px !important;" if _ACTIVE_MODE == "beast" else ""

    if "{" in existing:
        rule = f"\n/* pesticide */ * {{ border: 1px solid {color} !important; {pad} }}"
    else:
        rule = f" /* pesticide */ border: 1px solid {color} !important; {pad}"

    try:
        w.setStyleSheet(existing + rule)
    except Exception:
        pass


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _policy_name(val) -> str:
    # PySide6 returns an enum with .name; older bindings return an int
    if hasattr(val, "name"):
        return val.name
    return {0: "Fixed", 1: "Minimum", 4: "Maximum", 5: "Preferred",
            3: "MinimumExpanding", 7: "Expanding", 13: "Ignored"}.get(int(val), f"?({val})")


# ─── Stylesheet Engine ────────────────────────────────────────────────────────

def get_debug_styles(padding=None) -> str:
    inject = f"    padding: {padding}px !important;" if padding else ""
    return DEBUG_STYLES.replace("/* inject */", inject)


DEBUG_STYLES = """
/* UNIVERSAL RESET */
* {
    border: 1px solid rgba(255, 0, 0, 150) !important;
    /* inject */
}

QFrame, QGroupBox        { border: 1px solid rgba(  0,   0, 255, 120) !important; }
QLabel                   { border: 1px solid rgba(255,   0, 255, 180) !important; }
QPushButton              { border: 2px solid rgba(255, 165,   0, 200) !important;
                           background: rgba(255, 165, 0, 10) !important; }
QLineEdit, QTextEdit,
QComboBox                { border: 2px solid rgba(  0, 255, 255, 200) !important;
                           background: rgba(0, 255, 255, 10) !important; }
QScrollArea,
QStackedWidget           { border: 3px solid rgba(255,  20, 147, 150) !important;
                           background: rgba(255, 20, 147, 5) !important; }
"""
