"""
three_ps_lcca_gui/gui/themes/__init__.py - Theme registry.

Directory layout
----------------
three_ps_lcca_gui/gui/themes/
    light/
        soft_light.yml  Catppuccin Latte (built-in)
        <custom>.yml    drop any .yml here to add your own light theme
        <custom>.py     legacy .py themes still work as a fallback
    dark/
        dracula.yml     Dracula          (built-in)
        <custom>.yml    drop any .yml here to add your own dark theme
        <custom>.py     legacy .py themes still work as a fallback

Each theme YAML must contain:
    name: str                        - human-readable display name
    palette: map[semantic_key, hex]  - semantic colour → hex
    state:   map[state_key, float]   - hover/pressed/focus/disabled opacity multipliers (optional)

Semantic palette keys
---------------------
    primary, brand, window, base, surface, surface_mid, surface_pressed,
    text, text_secondary, text_disabled, success, warning, danger, info

If a YAML file is missing, corrupt, or has a schema mismatch the system
silently falls back to the hardcoded defaults below - the app never crashes.

Selecting active themes
-----------------------
Change via the Settings panel in the app sidebar (persisted to user prefs).
Fallback defaults are ACTIVE_LIGHT / ACTIVE_DARK below.
"""

from __future__ import annotations

import importlib
import os
import pkgutil
from pathlib import Path

import yaml
from PySide6.QtCore import Qt, QObject, Signal
from PySide6.QtGui import QPalette, QColor
import sys


class _ThemeManager(QObject):
    """Internal singleton to manage theme change signals."""
    theme_changed = Signal()


_MANAGER = None


def theme_manager() -> _ThemeManager:
    """Return the global ThemeManager instance."""
    global _MANAGER
    if _MANAGER is None:
        _MANAGER = _ThemeManager()
    return _MANAGER

# ── Fallback defaults (used if no user pref is saved) ────────────────────
ACTIVE_LIGHT: str = "soft_light"  # built-in: "default" | "soft_light"
ACTIVE_DARK: str = "dracula"  # built-in: "default" | "dracula"
APPEARANCE_MODE: str = "auto"  # "auto" | "light" | "dark"
# ──────────────────────────────────────────────────────────────────────────

_PKG = "three_ps_lcca_gui.gui.themes"
_THEMES_DIR = Path(__file__).parent
# Absolute path - works regardless of working directory (e.g. when a project is open)
_QSS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "gui",
    "assets",
    "themes",
    "main.qss",
)
_prefs_loaded = False
_current_is_dark: bool = False  # last-known resolved is_dark; set by track_mode()
# populated by get_light/dark_theme(); read via get_token()
_active_tokens: dict[str, str] = {}
# populated by get_light/dark_theme(); read via get_state()
_active_state: dict[str, float] = {}

# ── Hardcoded fallback themes - system NEVER fails even if all YAMLs are gone ──
#
# Light fallback: brand green palette (matches three_ps_lcca_gui/gui/theme.py constants)
_FALLBACK_LIGHT: dict = {
    "name": "Soft Light",
    "palette": {
        "primary": "#0d6efd",
        "brand": "#90af13",
        "window": "#eff1f5",
        "base": "#ffffff",
        "surface": "#e6e9ef",
        "surface_mid": "#ccd0da",
        "surface_pressed": "#dce0e8",
        "text": "#4c4f69",
        "text_secondary": "#6c6f85",
        "text_disabled": "#9ca0b0",
        "success": "#22c55e",
        "warning": "#f97316",
        "danger": "#ef4444",
        "info": "#3b82f6",
    },
    "state": {"hover": 0.50, "pressed": 0.12, "focus": 0.18, "disabled": 0.38},
}

# Dark fallback: matches palette_manager.py + theme.py DARK_QSS_TOKENS
_FALLBACK_DARK: dict = {
    "name": "Dracula",
    "palette": {
        "primary": "#bd93f9",
        "brand": "#90af13",
        "window": "#282a36",
        "base": "#21222c",
        "surface": "#383a4a",
        "surface_mid": "#44475a",
        "surface_pressed": "#565869",
        "text": "#f8f8f2",
        "text_secondary": "#6272a4",
        "text_disabled": "#4d5068",
        "success": "#50fa7b",
        "warning": "#ffb86c",
        "danger": "#ff5555",
        "info": "#8be9fd",
    },
    "state": {"hover": 0.50, "pressed": 0.12, "focus": 0.18, "disabled": 0.38},
}

# Required keys for schema validation
_REQUIRED_KEYS = {"palette"}

# ── Semantic palette key → one or more QPalette roles ────────────────────
_SEMANTIC_ROLES: dict[str, list[QPalette.ColorRole]] = {
    "window":          [QPalette.Window],
    "base":            [QPalette.Base, QPalette.Button],
    "surface":         [QPalette.AlternateBase],
    "surface_mid":     [QPalette.Mid, QPalette.Midlight, QPalette.ToolTipBase],
    "surface_pressed": [QPalette.Light],
    "text":            [QPalette.Text, QPalette.WindowText, QPalette.ButtonText, QPalette.ToolTipText],
    "text_secondary":  [QPalette.PlaceholderText],
    "primary":         [QPalette.Highlight, QPalette.Accent],
}


_FALLBACK_STATE = {"hover": 0.06, "pressed": 0.12, "focus": 0.18, "disabled": 0.38}


def _ensure_tokens() -> None:
    """Bootstrap _active_tokens / _active_state from fallback if not yet loaded."""
    global _active_tokens, _active_state
    if not _active_tokens:
        data = _FALLBACK_DARK if _current_is_dark else _FALLBACK_LIGHT
        _active_tokens = {str(k): str(v) for k, v in data["palette"].items()}
        _active_state = dict(_FALLBACK_STATE)
        _active_tokens.update(_derive_compat_tokens(_active_tokens, _active_state))


_missing_token_cache: set[str] = set()

def get_token(name: str, state: str = "") -> str:
    """Return the hex colour or constant for a semantic key."""
    _ensure_tokens()
    name = name.lstrip("$")
    val = _active_tokens.get(name)

    if val is None:
        if name not in _missing_token_cache:
            _missing_token_cache.add(name)
            print(f"[THEME WARN] Missing token: {name!r}", file=sys.stderr)
        return ""

    # Don't apply state alpha to font weights or if no state requested
    if not state or name.startswith("weight-"):
        return val

    # Apply state alpha only if valid color
    c = QColor(val)
    if not c.isValid():
        return val

    alpha = _active_state.get(state, 1.0)
    aa = round(alpha * 255)
    return f"#{aa:02x}{c.red():02x}{c.green():02x}{c.blue():02x}"


def get_state(name: str, fallback: float = 0.0) -> float:
    """Return a state opacity multiplier by name ('hover', 'pressed', 'focus', 'disabled').

    Values are 0-1 floats used to blend a tint over a base surface colour.
    Example: hover = 0.06 → overlay text colour at 6 % alpha on the surface.
    """
    _ensure_tokens()
    return _active_state.get(name, fallback)


def get_active_theme() -> dict[str, str]:
    _ensure_tokens()
    return _active_tokens


def _derive_compat_tokens(raw: dict[str, str], state: dict[str, float]) -> dict[str, str]:
    """Compute specialized or state-derived tokens from the semantic palette.
    These are tokens that aren't 1:1 mappings of the base palette.
    """

    def _alpha(key: str, state_name: str) -> str:
        """Return `key` colour at `state_name` opacity as #AARRGGBB."""
        hex_color = raw.get(key, "")
        if not hex_color:
            return ""
        alpha = state.get(state_name, 0.0)
        c = QColor(hex_color)
        aa = round(alpha * 255)
        return f"#{aa:02x}{c.red():02x}{c.green():02x}{c.blue():02x}"

    # Start with the base palette
    tokens = dict(raw)
    
    # Calculate primary luminance for text-on-primary contrast
    primary_hex = raw.get("primary", "#000000")
    pc = QColor(primary_hex)
    lum = 0.299 * pc.redF() + 0.587 * pc.greenF() + 0.114 * pc.blueF()
    text_on_primary = "#ffffff" if lum < 0.5 else "#000000"

    # Add derived state tokens (alphas) and specialized UI identifiers
    from three_ps_lcca_gui.gui.components.outputs.helper_functions.lcc_colors import COLORS as LCC
    tokens.update({
        "primary-hover":       _alpha("primary", "hover"),
        "primary-active":      _alpha("primary", "pressed"),
        "border":              raw.get("text_disabled", ""),
        "border-subtle":       raw.get("surface_mid", ""),
        
        # Chart / Pillar colors
        "eco":                 LCC.get("eco_color", "#9e9eff"),
        "env":                 LCC.get("env_color", "#8ad400"),
        "soc":                 LCC.get("soc_color", "#ff5a2a"),
        "init":                LCC.get("init_color", "#CCCCCC"),
        "use":                 LCC.get("use_color", "#00C49A"),
        "end":                 LCC.get("end_color", "#EA9E9E"),

        "danger-bg":           _alpha("danger",  "hover"),
        "danger-bg-pressed":   _alpha("danger",  "pressed"),
        "sidebar-hover":       _alpha("primary", "hover"),
        "sidebar-sel":         _alpha("primary", "pressed"),
        "cell-invalid-bg":     _alpha("danger",  "pressed"),
        "cell-warn-bg":        _alpha("warning", "pressed"),
        "cell-editable-bg":    _alpha("primary", "hover"),
        "cell-warn-row-bg":    _alpha("danger",  "hover"),
        "icon-brand":          raw.get("brand", raw.get("primary", "")),
        "splash-bg":           raw.get("window", ""),
        "splash-progress":     raw.get("success", ""),
        "text-on-primary":     text_on_primary,
    })

    # Add centralized font weights
    from three_ps_lcca_gui.gui.theme import QSS_WEIGHTS
    tokens.update(QSS_WEIGHTS)
    
    # Add URL-encoded versions of all color tokens for safe use in SVG data URIs
    # e.g., $primary-url will be %23RRGGBB
    url_tokens = {}
    for k, v in tokens.items():
        if isinstance(v, str) and v.startswith("#"):
            url_tokens[f"{k}-url"] = v.replace("#", "%23")
    tokens.update(url_tokens)

    return tokens


def _build_theme(data: dict) -> tuple[QPalette, dict[str, str], dict[str, float]]:
    """Build (QPalette, semantic_palette, state) from a raw theme dict.

    Validates schema - raises ValueError on mismatch so callers can fall back.
    Returns:
      palette  - QPalette populated from semantic colour keys
      raw      - flat str→str palette map (used by get_token() and QSS substitution)
      state    - float multipliers for hover/pressed/focus/disabled
    """
    if not isinstance(data, dict):
        raise ValueError("Theme data is not a mapping")
    missing = _REQUIRED_KEYS - data.keys()
    if missing:
        raise ValueError(f"Theme missing required keys: {missing}")
    if not isinstance(data["palette"], dict):
        raise ValueError("'palette' must be a mapping")

    raw: dict[str, str] = {str(k): str(v) for k, v in data["palette"].items()}

    palette = QPalette()
    for sem_key, roles in _SEMANTIC_ROLES.items():
        hex_color = raw.get(sem_key)
        if hex_color is None:
            continue
        color = QColor(hex_color)
        for role in roles:
            palette.setColor(role, color)

    # State multipliers - fall back to defaults for any missing key
    raw_state = data.get("state", {})
    state: dict[str, float] = {**_FALLBACK_STATE, **{str(k): float(v) for k, v in raw_state.items()}}

    # Merge $-prefixed compat tokens so legacy callers keep working
    # This also populates text-on-primary based on the primary color luminance
    derived = _derive_compat_tokens(raw, state)
    raw.update(derived)

    # HighlightedText (text ON a primary/highlight background): pick white or
    # black based on primary luminance so contrast is always readable.
    palette.setColor(QPalette.HighlightedText, QColor(derived["text-on-primary"]))

    return palette, raw, state


def _fallback(variant: str) -> tuple[QPalette, dict[str, str], dict[str, float]]:
    """Return the hardcoded fallback theme - guaranteed to never fail."""
    data = _FALLBACK_DARK if variant == "dark" else _FALLBACK_LIGHT
    return _build_theme(data)


def _ensure_prefs() -> None:
    """Load persisted theme choices from user prefs (once, lazily)."""
    global ACTIVE_LIGHT, ACTIVE_DARK, APPEARANCE_MODE, _prefs_loaded
    if _prefs_loaded:
        return
    _prefs_loaded = True
    try:
        import three_ps_lcca_gui.core.start_manager as sm

        v = sm.get_pref("active_light_theme")
        if v:
            ACTIVE_LIGHT = v
        v = sm.get_pref("active_dark_theme")
        if v:
            ACTIVE_DARK = v
        v = sm.get_pref("appearance_mode")
        if v in ("auto", "light", "dark"):
            APPEARANCE_MODE = v
    except Exception:
        pass


def _load_yaml_theme(path: Path) -> tuple[QPalette, dict[str, str], dict[str, float]]:
    """Parse a .yml theme file → (QPalette, semantic_palette, state).

    Raises ValueError/yaml.YAMLError on parse or schema failure.
    """
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return _build_theme(data)


def _load(variant: str, name: str) -> tuple[QPalette, dict[str, str], dict[str, float]]:
    """Load a theme by variant ('light'|'dark') and name.

    Resolution order:
      1. <themes_dir>/<variant>/<name>.yml  - preferred declarative format
      2. three_ps_lcca_gui.gui.themes.<variant>.<name>        - legacy .py module fallback
      3. Hardcoded fallback                 - if file missing, corrupt, or schema mismatch
    """
    # 1. YAML
    yml_path = _THEMES_DIR / variant / f"{name}.yml"
    if yml_path.exists():
        try:
            return _load_yaml_theme(yml_path)
        except Exception as e:
            print(
                f"[themes] Warning: '{yml_path.name}' failed to load ({e}); using built-in fallback."
            )
            return _fallback(variant)

    # 2. Legacy .py module - no state dict; use defaults
    try:
        mod = importlib.import_module(f"{_PKG}.{variant}.{name}")
        return mod.palette, mod.QSS_TOKENS, dict(_FALLBACK_STATE)
    except Exception:
        pass

    # 3. Hardcoded fallback - YAML missing and no .py module found
    print(
        f"[themes] Warning: theme '{variant}/{name}' not found; using built-in fallback."
    )
    return _fallback(variant)


def get_light_theme() -> tuple[QPalette, dict[str, str], dict[str, float]]:
    """Return (palette, semantic_palette, state) for the active light theme."""
    global _active_tokens, _active_state
    _ensure_prefs()
    palette, tokens, state = _load("light", ACTIVE_LIGHT)
    _active_tokens = tokens
    _active_state = state
    return palette, tokens, state


def get_dark_theme() -> tuple[QPalette, dict[str, str], dict[str, float]]:
    """Return (palette, semantic_palette, state) for the active dark theme."""
    global _active_tokens, _active_state
    _ensure_prefs()
    palette, tokens, state = _load("dark", ACTIVE_DARK)
    _active_tokens = tokens
    _active_state = state
    return palette, tokens, state


def set_active_theme(variant: str, name: str) -> None:
    """Set the active theme for 'light' or 'dark' and persist to user prefs."""
    global ACTIVE_LIGHT, ACTIVE_DARK
    if variant == "light":
        ACTIVE_LIGHT = name
    else:
        ACTIVE_DARK = name
    try:
        import three_ps_lcca_gui.core.start_manager as sm

        sm.set_pref(f"active_{variant}_theme", name)
    except Exception:
        pass


def set_appearance_mode(mode: str) -> None:
    """Set appearance mode: 'auto' | 'light' | 'dark'. Persists to user prefs."""
    global APPEARANCE_MODE
    if mode not in ("auto", "light", "dark"):
        return
    APPEARANCE_MODE = mode
    try:
        import three_ps_lcca_gui.core.start_manager as sm

        sm.set_pref("appearance_mode", mode)
    except Exception:
        pass


def resolve_is_dark(os_is_dark: bool) -> bool:
    """Return True if dark theme should be used, respecting APPEARANCE_MODE."""
    _ensure_prefs()
    if APPEARANCE_MODE == "dark":
        return True
    if APPEARANCE_MODE == "light":
        return False
    return os_is_dark  # "auto"


def track_mode(is_dark: bool) -> None:
    """Record the last-resolved is_dark state. Called by main._apply_theme()
    so reapply() always has a reliable baseline instead of guessing from palette."""
    global _current_is_dark
    _current_is_dark = is_dark


def is_dark() -> bool:
    """Return True if the current active theme is a dark variant."""
    return _current_is_dark


def _detect_os_dark(app=None) -> bool:
    """Read the current OS dark/light state directly - never uses cached values.

    Resolution order:
      1. QApplication.styleHints().colorScheme()  - Qt 6.5+, most reliable
      2. Windows registry AppsUseLightTheme       - fallback on Windows
      3. False (assume light)                     - safe default
    """
    # 1. Qt colorScheme (reliable on Qt 6.5+; often Unknown on Windows/Fusion)
    if app is not None:
        try:
            scheme = app.styleHints().colorScheme()
            if scheme == Qt.ColorScheme.Dark:
                print(f"[themes] _detect_os_dark -> Dark (Qt.ColorScheme.Dark)")
                return True
            if scheme == Qt.ColorScheme.Light:
                print(f"[themes] _detect_os_dark -> Light (Qt.ColorScheme.Light)")
                return False
            print(
                f"[themes] _detect_os_dark: Qt.ColorScheme returned Unknown ({scheme}), trying registry ..."
            )
        except AttributeError:
            print(
                "[themes] _detect_os_dark: Qt.ColorScheme not available, trying registry ..."
            )

    # 2. Windows registry
    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        )
        val, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        winreg.CloseKey(key)
        result = val == 0
        print(
            f"[themes] _detect_os_dark -> {'Dark' if result else 'Light'} (registry AppsUseLightTheme={val})"
        )
        return result
    except Exception as e:
        print(
            f"[themes] _detect_os_dark: registry read failed ({e}), defaulting to Light"
        )

    return False


def _write_arrow_svgs(tokens: dict[str, str]) -> None:
    """Write theme-colored down-arrow SVG files used by QComboBox::down-arrow."""
    _assets = os.path.join(os.path.dirname(_QSS_PATH))
    # Use standard text tokens (text for normal, text_secondary for disabled)
    normal_color   = tokens.get("text", "#4c4f69")
    disabled_color = tokens.get("text_secondary", "#9ca0b0")

    def _svg(color: str) -> str:
        # Convert hex to valid SVG color (ensure # is present)
        if not color.startswith("#"):
            color = f"#{color}"
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
            f'<path fill="{color}" d="M7 10l5 5 5-5z"/>'
            f'</svg>'
        )

    try:
        with open(os.path.join(_assets, "arrow_down.svg"), "w", encoding="utf-8") as f:
            f.write(_svg(normal_color))
        with open(os.path.join(_assets, "arrow_down_disabled.svg"), "w", encoding="utf-8") as f:
            f.write(_svg(disabled_color))
    except Exception as e:
        print(f"[themes] Could not write arrow SVGs: {e}")


def reapply(app=None) -> None:
    """Re-apply the current active themes to the running QApplication."""
    from PySide6.QtWidgets import QApplication

    if app is None:
        app = QApplication.instance()
    if app is None:
        return

    # For "auto" mode always re-read the live OS state - _current_is_dark is
    # stale when the user switches FROM an explicit mode (dark/light) back to auto.
    if APPEARANCE_MODE == "auto":
        os_is_dark = _detect_os_dark(app)
    else:
        os_is_dark = _current_is_dark

    is_dark = resolve_is_dark(os_is_dark)
    print(
        f"[themes] reapply: APPEARANCE_MODE={APPEARANCE_MODE!r}, os_is_dark={os_is_dark}, resolved is_dark={is_dark}"
    )
    track_mode(is_dark)
    palette, tokens, _ = get_dark_theme() if is_dark else get_light_theme()

    app.setPalette(palette)
    _write_arrow_svgs(tokens)

    if os.path.exists(_QSS_PATH):
        try:
            with open(_QSS_PATH, encoding="utf-8") as f:
                qss = f.read()
            
            # Sort tokens by length (longest first) to avoid partial replacements
            # e.g., substituting 'primary' shouldn't break '$primary-hover'.
            # We also prepend '$' to match the syntax used in main.qss.
            sorted_tokens = sorted(tokens.items(), key=lambda x: len(x[0]), reverse=True)
            for token, value in sorted_tokens:
                qss = qss.replace(f"${token}", value)

            # Resolve arrow SVG URLs to absolute paths so styles work from any CWD.
            _arrow = os.path.join(os.path.dirname(_QSS_PATH), "arrow_down.svg").replace("\\", "/")
            _arrow_disabled = os.path.join(os.path.dirname(_QSS_PATH), "arrow_down_disabled.svg").replace("\\", "/")
            qss = qss.replace(
                "url(gui/assets/themes/arrow_down.svg)",
                f'url("{_arrow}")',
            )
            qss = qss.replace(
                "url(gui/assets/themes/arrow_down_disabled.svg)",
                f'url("{_arrow_disabled}")',
            )
                
            # Clear first - forces Qt to fully re-evaluate all style rules
            # on every existing widget, including window backgrounds.
            app.setStyleSheet("")
            app.setStyleSheet(qss)
        except Exception as e:
            print(f"[themes] Error applying stylesheet: {e}")

    # Force every top-level window (and its children) to repaint immediately.
    # Without this, palette(window) backgrounds stay stale until the next
    # resize/focus event.
    for w in app.topLevelWidgets():
        w.style().unpolish(w)
        w.style().polish(w)
        w.update()

    # Notify all subscribed listeners
    theme_manager().theme_changed.emit()


def list_themes(variant: str) -> list[str]:
    """Return names of all available themes for 'light' or 'dark'.
    Discovers both .yml files and legacy .py modules in the variant folder."""
    pkg_dir = _THEMES_DIR / variant

    yml_names = {p.stem for p in pkg_dir.glob("*.yml")}
    py_names = {
        name for _, name, is_pkg in pkgutil.iter_modules([str(pkg_dir)]) if not is_pkg
    }
    return sorted(yml_names | py_names)


def get_theme_name(variant: str, module_name: str) -> str:
    """Return the human-readable name for a theme."""
    yml_path = _THEMES_DIR / variant / f"{module_name}.yml"
    if yml_path.exists():
        try:
            with open(yml_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if isinstance(data, dict):
                return data.get("name", module_name)
        except Exception:
            pass

    # Legacy .py fallback
    try:
        mod = importlib.import_module(f"{_PKG}.{variant}.{module_name}")
        return getattr(mod, "NAME", module_name)
    except Exception:
        pass

    return module_name


