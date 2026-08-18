"""
gui/styles.py - Component-level style helpers (single source of truth).

All functions read from gui/theme.py tokens - change a token there and
every widget that calls these helpers picks it up automatically.

Font helper
-----------
    from gui.styles import font
    widget.setFont(font(FS_LG, FW_SEMIBOLD))

Button QSS builders
-------------------
    from gui.styles import btn_primary, btn_outline, ...
    button.setStyleSheet(btn_primary())
"""

from PySide6.QtGui import QFont

from three_ps_lcca_gui.gui.theme import (
    FONT_FAMILY,
    RADIUS_MD,
    FW_NORMAL,
)

from three_ps_lcca_gui.gui.themes import get_token


# ── Font helper ────────────────────────────────────────────────────────────────

def font(size: int, weight: int = FW_NORMAL, italic: bool = False) -> QFont:
    """Return a QFont using the app font family with the given size/weight/style."""
    f = QFont(FONT_FAMILY)
    f.setPointSize(size)
    f.setWeight(QFont.Weight(weight))
    f.setItalic(italic)
    return f


# ── Button QSS builders ────────────────────────────────────────────────────────
#
# Each function returns a complete QSS string for QPushButton.
# Pass `radius` to override the default border-radius per instance.

def btn_primary(radius: int = RADIUS_MD) -> str:
    """Filled PRIMARY button - main CTA."""
    return (
        f"QPushButton {{ background: {get_token('primary')}; color: {get_token('base')}; border: none;"
        f"  border-radius: {radius}px; padding: 0 16px; font-weight: {get_token('weight-semibold')}; }}"
        f"QPushButton:hover   {{ background: {get_token('primary', 'hover')}; }}"
        f"QPushButton:pressed {{ background: {get_token('primary', 'pressed')}; }}"
    )


def btn_outline(radius: int = RADIUS_MD) -> str:
    """Neutral outlined button - secondary action."""
    return (
        f"QPushButton {{ background: transparent; border: 1px solid palette(mid);"
        f"  border-radius: {radius}px; padding: 0 16px; color: palette(windowText); }}"
        f"QPushButton:hover   {{ border-color: {get_token('primary')}; color: {get_token('primary')}; }}"
        f"QPushButton:pressed {{ background: palette(midlight); }}"
    )


def btn_outline_primary(radius: int = RADIUS_MD) -> str:
    """Outlined PRIMARY button - confirmatory action (Open, etc.)."""
    return (
        f"QPushButton {{ border: 1px solid {get_token('primary')}; color: {get_token('primary')};"
        f"  border-radius: {radius}px; padding: 0 20px; background: transparent; }}"
        f"QPushButton:hover   {{ background: {get_token('primary')}; color: {get_token('base')}; }}"
        f"QPushButton:pressed {{ background: {get_token('primary', 'pressed')}; color: {get_token('base')};"
        f"  border-color: {get_token('primary', 'pressed')}; }}"
    )


def btn_danger(radius: int = RADIUS_MD) -> str:
    """Filled danger button - destructive action (Delete, etc.)."""
    return (
        f"QPushButton {{ background: {get_token('danger')}; color: {get_token('base')}; border: none;"
        f"  border-radius: {radius}px; padding-left: 16px; padding-right: 16px;"
        f"  font-weight: {get_token('weight-semibold')}; }}"
        f"QPushButton:hover   {{ background: {get_token('danger', 'hover')}; }}"
        f"QPushButton:pressed {{ background: {get_token('danger', 'pressed')}; }}"
        f"QPushButton:disabled {{ background: {get_token('danger', 'disabled')}; }}"
    )


def btn_outline_danger(radius: int = RADIUS_MD) -> str:
    """Outlined danger button - destructive action (Delete, etc.)."""
    return (
        f"QPushButton {{ border: 1px solid {get_token('danger')}; color: {get_token('danger')};"
        f"  border-radius: {radius}px; padding: 0 20px; background: transparent; }}"
        f"QPushButton:hover   {{ background: {get_token('danger', 'hover')}; }}"
        f"QPushButton:pressed {{ background: {get_token('danger', 'pressed')}; }}"
    )


def btn_text_primary(radius: int = RADIUS_MD) -> str:
    """Text-only PRIMARY button, left-aligned - nav/return links."""
    return (
        f"QPushButton {{ color: {get_token('primary')}; border: none; background: transparent;"
        f"  text-align: left; padding-left: 16px; border-radius: {radius}px; }}"
        f"QPushButton:hover {{ background: palette(midlight); }}"
    )


def btn_ghost(radius: int = RADIUS_MD) -> str:
    """Subtle outlined button - toolbar/secondary small actions (Refresh, sort tabs)."""
    return (
        f"QPushButton {{ border: 1px solid palette(mid); border-radius: {radius}px;"
        f"  padding: 0 12px; background: transparent; color: palette(windowText); }}"
        f"QPushButton:hover {{ border-color: {get_token('primary')}; color: {get_token('primary')}; }}"
    )


def btn_ghost_checkable(radius: int = RADIUS_MD) -> str:
    """Ghost button that can be checked - sort/filter toggle tabs."""
    return (
        f"QPushButton {{ border: 1px solid palette(mid); border-radius: {radius}px;"
        f"  padding: 0 10px; background: transparent; color: palette(windowText); }}"
        f"QPushButton:hover   {{ border-color: {get_token('primary')}; color: {get_token('primary')}; }}"
        f"QPushButton:checked {{ background: transparent; color: {get_token('primary')};"
        f"  border: 1.5px solid {get_token('primary')}; font-weight: {get_token('weight-semibold')}; }}"
    )


def btn_banner(radius: int = RADIUS_MD) -> str:
    """White-outlined button for use on a PRIMARY-coloured banner."""
    return (
        f"QPushButton {{ color: white; border: 1px solid rgba(255,255,255,0.6);"
        f"  border-radius: {radius}px; padding: 0 14px; background: transparent; }}"
        f"QPushButton:hover   {{ background: rgba(255,255,255,0.15); }}"
        f"QPushButton:pressed {{ background: rgba(255,255,255,0.25); }}"
    )


