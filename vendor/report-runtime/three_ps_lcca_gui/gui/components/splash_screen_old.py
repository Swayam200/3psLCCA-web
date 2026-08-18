"""
gui/components/splash_screen.py
────────────────────────────────────────────────────────────────────────────────
Theme-aware Splash Screen - lightweight & smooth.
"""

from __future__ import annotations
import time, os

from PySide6.QtCore import Property, QEasingCurve, QPropertyAnimation, QRect, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QWidget

from three_ps_lcca_gui.gui.themes import get_token
from three_ps_lcca_gui.gui.theme import SP4, SP8, SP10, FS_DISP, FS_BASE, FW_BOLD
from three_ps_lcca_gui.gui.styles import font

MIN_DISPLAY_MS = 1_500
SPLASH_W, SPLASH_H = 520, 300
_ICON_PATH = os.path.join("gui", "assets", "logo", "logo-3psLCCA.svg")


class _Bar(QWidget):
    """Slim progress bar - reads live theme tokens."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self._v: float = 0.0
        self.setFixedHeight(3)

    def _get(self) -> float:
        return self._v

    def _set(self, v: float) -> None:
        self._v = max(0.0, min(1.0, v))
        self.update()

    progress = Property(float, fget=_get, fset=_set)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setPen(Qt.NoPen)
        # Track
        p.setOpacity(0.12)
        p.setBrush(QColor(get_token("window")))
        p.drawRect(self.rect())
        # Fill
        if self._v > 0:
            p.setOpacity(1.0)
            p.setBrush(QColor(get_token("primary")))
            p.drawRect(0, 0, int(self.width() * self._v), self.height())
        p.end()


class SplashScreen(QWidget):
    def __init__(self) -> None:
        super().__init__(
            None, Qt.SplashScreen | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(SPLASH_W, SPLASH_H)
        self._center()

        # Cache pixmap once - never re-read disk on repaint
        self._logo: QPixmap | None = None
        if os.path.exists(_ICON_PATH):
            self._logo = QPixmap(_ICON_PATH).scaled(
                64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )

        self._bar = _Bar(self)
        self._bar.setGeometry(0, SPLASH_H - 3, SPLASH_W, 3)

        # Main animation: 0 → 0.85 over display duration
        self._anim = QPropertyAnimation(self._bar, b"progress", self)
        self._anim.setDuration(MIN_DISPLAY_MS)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(0.85)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

        # Close animation: 0.85 → 1.0 quick snap before hide
        self._close_anim = QPropertyAnimation(self._bar, b"progress", self)
        self._close_anim.setDuration(150)
        self._close_anim.setEndValue(1.0)
        self._close_anim.setEasingCurve(QEasingCurve.OutQuad)
        self._close_anim.finished.connect(self.close)

        self._show_ts = 0.0

    def show(self) -> None:
        self._show_ts = time.monotonic()
        super().show()
        self._anim.start()

    def finish(self, _widget=None) -> None:
        elapsed_ms = (time.monotonic() - self._show_ts) * 1000
        delay = max(0, int(MIN_DISPLAY_MS - elapsed_ms))
        QTimer.singleShot(delay, self._do_close)

    def _do_close(self) -> None:
        self._anim.stop()
        self._close_anim.setStartValue(self._bar.progress)
        self._close_anim.start()

    def _center(self) -> None:
        geo = QApplication.primaryScreen().availableGeometry()
        self.move(geo.center() - self.rect().center())

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)

        # Background
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(get_token("window")))
        p.drawRoundedRect(self.rect(), 12, 12)

        # Top accent strip
        p.setBrush(QColor(get_token("primary")))
        p.drawRoundedRect(QRect(0, 0, SPLASH_W, 4), 2, 2)

        margin, logo_size = SP10, 64

        # Logo (pre-cached)
        if self._logo:
            p.drawPixmap(margin, margin + SP8, self._logo)

        # App name
        p.setPen(QColor(get_token("text")))
        p.setFont(font(FS_DISP, FW_BOLD))
        p.drawText(
            QRect(margin + logo_size + SP4, margin + SP8, 300, logo_size),
            Qt.AlignVCenter,
            "3psLCCA",
        )

        # Subtitle
        p.setPen(QColor(get_token("text_secondary")))
        p.setFont(font(FS_BASE))
        p.drawText(
            margin,
            margin + logo_size + SP8 + SP4,
            SPLASH_W - (2 * margin),
            30,
            Qt.AlignLeft,
            "Life Cycle Cost Analysis · Bridge Infrastructure",
        )

        p.end()


