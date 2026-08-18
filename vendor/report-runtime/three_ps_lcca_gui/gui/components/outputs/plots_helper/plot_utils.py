"""
gui/components/outputs/plots_helper/plot_utils.py

Shared utilities for matplotlib-based chart widgets.
"""

import os
from matplotlib import font_manager as _fm
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT
from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QApplication, QScrollArea
from three_ps_lcca_gui.gui.theme import FONT_FAMILY

def register_ubuntu_fonts():
    """Register Ubuntu TTF fonts with Matplotlib."""
    font_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "assets", "themes", "Ubuntu_font")
    )
    for ttf in ["Ubuntu-Light.ttf", "Ubuntu-Regular.ttf", "Ubuntu-Medium.ttf", "Ubuntu-Bold.ttf"]:
        path = os.path.join(font_dir, ttf)
        if os.path.exists(path):
            _fm.fontManager.addfont(path)

class WheelForwarder(QObject):
    """Forwards wheel events from a child widget to the nearest parent QScrollArea."""
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Wheel:
            parent = obj.parent()
            while parent is not None:
                if isinstance(parent, QScrollArea):
                    QApplication.sendEvent(parent.verticalScrollBar(), event)
                    return True
                parent = parent.parent()
        return False

class ChartToolbar(NavigationToolbar2QT):
    """Custom Matplotlib toolbar with fewer items and silenced messages."""
    toolitems = [t for t in NavigationToolbar2QT.toolitems
                 if t[0] not in ("Subplots", "Customize")]
    def set_message(self, s): pass

def currency_note(currency: str) -> str:
    """Standard note for currency units."""
    return f"All values in {currency}"
