"""
Material Design Icons - Apache 2.0 License - https://fonts.google.com/icons
Inline SVG icon renderer for PySide6.  No external files required.

Icons are rendered via a QIconEngine subclass, so they:
  - Paint at whatever pixel size Qt requests  →  always crisp / HiDPI-safe
  - Read QApplication.palette() at paint time  →  work on both light and dark themes

Usage:
    from gui.components.utils.icons import make_icon
    btn.setIcon(make_icon("bolt"))
    btn.setIconSize(QSize(18, 18))
"""
from PySide6.QtCore import QByteArray, QEvent, QRectF, QRect, QPoint, QSize, Qt
from PySide6.QtGui import QIcon, QIconEngine, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication, QGraphicsOpacityEffect, QPushButton

# ---------------------------------------------------------------------------
# Filled SVG body fragments - viewBox="0 0 24 24", fill-based
# Source: Material Design Icons (Apache 2.0) - https://fonts.google.com/icons
# Custom: "bridge" (original)
# ---------------------------------------------------------------------------

_ICONS: dict[str, str] = {
    # ── Navigation / UI ──────────────────────────────────────────────────────
    "home": (
        '<path d="M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z"/>'
    ),
    "list": (
        '<path d="M3 13h2v-2H3v2zm0 4h2v-2H3v2zm0-8h2V7H3v2zm4 4h14v-2H7v2zm0'
        ' 4h14v-2H7v2zM7 7v2h14V7H7z"/>'
    ),
    "folder": (
        '<path d="M10 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0'
        ' 2-.9 2-2V8c0-1.1-.9-2-2-2h-8l-2-2z"/>'
    ),
    "layers": (
        '<path d="M11.99 18.54l-7.37-5.73L3 14.07l9 7 9-7-1.63-1.27-7.38'
        ' 5.74zm.01-2.81l7.36-5.73L21 8.5l-9-7-9 7 1.63 1.27L12 15.73z"/>'
    ),

    # ── Info / status ────────────────────────────────────────────────────────
    "info": (
        '<path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52'
        ' 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z"/>'
    ),
    "bar-chart": (
        '<path d="M5 9.2h3V19H5V9.2zM10.6 5h2.8v14h-2.8V5zm5.6 8H19v6h-2.8v-6z"/>'
    ),

    # ── Actions ──────────────────────────────────────────────────────────────
    "bolt": (
        '<path d="M7 2v11h3v9l7-12h-4l4-8z"/>'
    ),
    "edit": (
        '<path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25z"/>'
        '<path d="M20.71 7.04c.39-.39.39-1.02 0-1.41l-2.34-2.34c-.39-.39'
        '-1.02-.39-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/>'
    ),
    "trash": (
        '<path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1'
        '-1h-5l-1 1H5v2h14V4z"/>'
    ),
    "exclude": (
        '<polygon points="12,19 2,5 22,5"/>'
    ),
    "include": (
        '<polygon points="12,5 2,19 22,19"/>'
    ),
    "restore": (
        '<path d="M12 5V1L7 6l5 5V7c3.31 0 6 2.69 6 6s-2.69 6-6 6-6-2.69-6'
        '-6H4c0 4.42 3.58 8 8 8s8-3.58 8-8-3.58-8-8-8z"/>'
    ),
    "lock": (
        '<path d="M18 8h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6v2H6c-1.1 0-2 .9-2'
        ' 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2zm-6 9c-1.1'
        ' 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2zm3.1-9H8.9V6c0-1.71'
        ' 1.39-3.1 3.1-3.1 1.71 0 3.1 1.39 3.1 3.1v2z"/>'
    ),
    "lock-open": (
        '<path d="M18 8h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6h2c0-1.66 1.34-3 3-3'
        's3 1.34 3 3v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2'
        'V10c0-1.1-.9-2-2-2zm0 12H6v-10h12v10zm-6-3c1.1 0 2-.9 2-2s-.9-2-2-2'
        '-2 .9-2 2 .9 2 2 2z"/>'
    ),

    # ── Section icons ────────────────────────────────────────────────────────
    "build": (
        '<path d="M22.7 19l-9.1-9.1c.9-2.3.4-5-1.5-6.9-2-2-5-2.4-7.4-1.3L9'
        ' 6 6 9 1.6 4.7C.4 7.1.9 10.1 2.9 12.1c1.9 1.9 4.6 2.4 6.9 1.5l9.1'
        ' 9.1c.4.4 1 .4 1.4 0l2.3-2.3c.5-.4.5-1.1.1-1.4z"/>'
    ),
    "truck": (
        '<path d="M20 8h-3V4H3c-1.1 0-2 .9-2 2v11h2c0 1.66 1.34 3 3 3s3-1.34'
        ' 3-3h6c0 1.66 1.34 3 3 3s3-1.34 3-3h2v-5l-3-4zm-.5 1.5l1.96 2.5H17V9'
        'h2.5zM6 18.5c-.83 0-1.5-.67-1.5-1.5s.67-1.5 1.5-1.5 1.5.67 1.5'
        ' 1.5-.67 1.5-1.5 1.5zm11 0c-.83 0-1.5-.67-1.5-1.5s.67-1.5 1.5-1.5'
        ' 1.5.67 1.5 1.5-.67 1.5-1.5 1.5z"/>'
    ),
    "cash": (
        '<path d="M11 17h2v-1h1c.55 0 1-.45 1-1v-3c0-.55-.45-1-1-1h-3v-1h4V8'
        'h-2V7h-2v1h-1c-.55 0-1 .45-1 1v3c0 .55.45 1 1 1h3v1H9v2h2v1z"/>'
        '<path d="M20 4H4c-1.11 0-1.99.89-1.99 2L2 18c0 1.11.89 2 2 2h16'
        'c1.11 0 2-.89 2-2V6c0-1.11-.89-2-2-2zm0 14H4V6h16v12z"/>'
    ),
    "cloud": (
        '<path d="M19.35 10.04C18.67 6.59 15.64 4 12 4 9.11 4 6.6 5.64 5.35'
        ' 8.04 2.34 8.36 0 10.91 0 14c0 3.31 2.69 6 6 6h13c2.76 0 5-2.24'
        ' 5-5 0-2.64-2.05-4.78-4.65-4.96z"/>'
    ),
    "settings": (
        '<path d="M19.14 12.94c.04-.3.06-.61.06-.94 0-.32-.02-.64-.07-.94l2.03'
        '-1.58c.18-.14.23-.41.12-.61l-1.92-3.32c-.12-.22-.37-.29-.59-.22l-2.39'
        '.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54c-.04-.24-.24-.41-.48-.41h-3.84'
        'c-.24 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96c-.22'
        '-.08-.47 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.05.3-.09'
        '.63-.09.94s.02.64.07.94l-2.03 1.58c-.18.14-.23.41-.12.61l1.92 3.32c.12'
        '.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41'
        '.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.57'
        ' 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12'
        '-.61l-2.01-1.58zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3.6 3.6-3.6'
        ' 3.6 1.62 3.6 3.6-1.62 3.6-3.6 3.6z"/>'
    ),
    "autorenew": (
        '<path d="M12 6v3l4-4-4-4v3c-4.42 0-8 3.58-8 8 0 1.57.46 3.03 1.24'
        ' 4.26L6.7 14.8c-.45-.83-.7-1.79-.7-2.8 0-3.31 2.69-6 6-6zm6.76'
        ' 1.74L17.3 9.2c.44.84.7 1.79.7 2.8 0 3.31-2.69 6-6 6v-3l-4 4 4 4v-3'
        'c4.42 0 8-3.58 8-8 0-1.57-.46-3.03-1.24-4.26z"/>'
    ),
    "delete": (
        '<path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1'
        '-1h-5l-1 1H5v2h14V4z"/>'
    ),
    "upload": (
        '<path d="M9 16h6v-6h4l-7-7-7 7h4v6zm-4 2h14v2H5v-2z"/>'
    ),
    "download": (
        '<path d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z"/>'
    ),
}

# ---------------------------------------------------------------------------
# SVG wrapper - filled style
# ---------------------------------------------------------------------------

_TEMPLATE = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"'
    ' fill="{color}">'
    "{body}"
    "</svg>"
)


# ---------------------------------------------------------------------------
# Theme-aware icon engine
# ---------------------------------------------------------------------------

class _SvgIconEngine(QIconEngine):
    """Renders an SVG icon at whatever size Qt requests and in the current
    palette's foreground color - crisp on HiDPI, works on light and dark themes.

    Pixmaps are cached by (body, color, w, h) so each unique combination is
    rendered only once.  The cache is cleared on QApplication.paletteChanged
    so theme switches re-render cleanly without flooding the event loop.
    """

    # Cache keyed by (body, color, w, h) - dark and light entries coexist,
    # so theme switches are instant after the first render of each color.
    _cache: dict = {}

    def __init__(self, body: str):
        super().__init__()
        self._body = body

    def _fg_color(self, mode: QIcon.Mode) -> str:
        app = QApplication.instance()
        if mode == QIcon.Mode.Disabled:
            from three_ps_lcca_gui.gui.themes import get_token
            return app.palette().placeholderText().color().name() if app else get_token("icon-muted")
        from three_ps_lcca_gui.gui.themes import get_token
        return app.palette().windowText().color().name() if app else get_token("text")

    @classmethod
    def _render(cls, body: str, color: str, w: int, h: int) -> QPixmap:
        key = (body, color, w, h)
        if key not in cls._cache:
            svg = _TEMPLATE.format(color=color, body=body).encode()
            renderer = QSvgRenderer(QByteArray(svg))
            pix = QPixmap(w, h)
            pix.fill(Qt.GlobalColor.transparent)
            p = QPainter(pix)
            renderer.render(p, QRectF(0, 0, w, h))
            p.end()
            cls._cache[key] = pix
        return cls._cache[key]

    def paint(self, painter: QPainter, rect: QRect, mode: QIcon.Mode, state: QIcon.State):
        dpr = painter.device().devicePixelRatioF() if painter.device() else 1.0
        w = max(1, round(rect.width() * dpr))
        h = max(1, round(rect.height() * dpr))
        pix = self._render(self._body, self._fg_color(mode), w, h)
        pix.setDevicePixelRatio(dpr)
        painter.drawPixmap(rect.topLeft(), pix)

    def pixmap(self, size, mode: QIcon.Mode, state: QIcon.State) -> QPixmap:
        return self._render(self._body, self._fg_color(mode), size.width(), size.height())

    def clone(self) -> "_SvgIconEngine":
        return _SvgIconEngine(self._body)


# ---------------------------------------------------------------------------
# Auto-fading icon button
# ---------------------------------------------------------------------------

class _IconBtn(QPushButton):
    """QPushButton that automatically fades to ~35% opacity when disabled."""

    def changeEvent(self, e: QEvent) -> None:
        super().changeEvent(e)
        if e.type() == QEvent.Type.EnabledChange:
            if not self.isEnabled():
                eff = QGraphicsOpacityEffect(self)
                eff.setOpacity(0.35)
                self.setGraphicsEffect(eff)
            else:
                self.setGraphicsEffect(None)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def make_icon_btn(
    name: str,
    tooltip: str = "",
    size: int = 28,
    icon_color: str | None = None,
    hover_color: str = "46, 204, 113",
):
    """Return a compact circular QPushButton with a centred icon.

    Args:
        name:        Icon name from _ICONS.
        tooltip:     Tooltip text.
        size:        Button diameter in pixels (also sets border-radius = size/2).
        icon_color:  Fixed hex colour for the icon. When None the icon adapts
                     to the current palette (light/dark theme safe).
        hover_color: RGB triplet string used for the hover/pressed circle tint,
                     e.g. ``"231, 76, 60"`` for red.  Defaults to app green.
    """
    r = size // 2
    icon_px = size - 10
    btn = _IconBtn()
    btn.setIcon(make_icon(name, color=icon_color))
    btn.setIconSize(QSize(icon_px, icon_px))
    btn.setFixedSize(QSize(size, size))
    btn.setToolTip(tooltip)
    btn.setStyleSheet(
        f"QPushButton {{"
        f"  border-radius: {r}px; padding: 0px;"
        f"  border: none; background: transparent;"
        f"}}"
        f"QPushButton:hover {{"
        f"  border-radius: {r}px; padding: 0px;"
        f"  background: rgba({hover_color}, 40);"
        f"}}"
        f"QPushButton:pressed {{"
        f"  border-radius: {r}px; padding: 0px;"
        f"  background: rgba({hover_color}, 80);"
        f"}}"
    )
    return btn


def make_icon(name: str, color: str | None = None, size: int = 64) -> QIcon:
    """Return a QIcon for the named icon.

    When *color* is None (default) the icon adapts to the current palette
    (light / dark theme safe, always sharp).

    Pass an explicit *color* + *size* only for special cases like the app
    window icon where a fixed brand colour is required.
    """
    body = _ICONS.get(name, "")
    if color is None:
        return QIcon(_SvgIconEngine(body))

    # Fixed-colour rendering (e.g. branded window icon)
    svg = _TEMPLATE.format(color=color, body=body).encode()
    renderer = QSvgRenderer(QByteArray(svg))
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    renderer.render(painter)
    painter.end()
    return QIcon(pix)


