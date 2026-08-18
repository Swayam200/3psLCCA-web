import os
import sys
import yaml
from collections import defaultdict


# ─────────────────────────────────────────────────────────────
# REQUIRED TOKEN CONTRACT (single source of truth)
# ─────────────────────────────────────────────────────────────

REQUIRED_TOKENS = {
    # Core
    "primary", "primary-hover", "primary-active",
    "border", "border-subtle",
    "surface", "surface-active",
    "body-bg", "body-color",
    "secondary", "muted",
    "white", "card-bg",

    # Semantic
    "danger", "danger-bg", "danger-bg-pressed",
    "success", "warning", "info",
    "validation-error",
    "placeholder", "placeholder-text",

    # Sidebar
    "sidebar-hover", "sidebar-sel",

    # Splash
    "splash-progress", "splash-bg",

    # Icons
    "icon-brand", "icon-success", "icon-danger", "icon-muted",

    # Logs
    "log-success", "log-default", "log-warning",
    "log-error", "log-info",

    # Table
    "cell-editable-bg", "cell-warn-row-bg", "cell-disabled-bg",
    "cell-invalid-bg", "cell-warn-bg", "cell-warn-fg",

    # Integrity
    "integrity-mismatch", "integrity-missing", "integrity-ok",

    # Charts
    "chart-initial-tick", "chart-initial-bg",
    "chart-use-tick", "chart-use-bg",
    "chart-recon-tick", "chart-recon-bg",
    "chart-eol-tick", "chart-eol-bg",
    "chart-bar-positive", "chart-bar-negative",
}


# Core semantic keys that MUST be in 'palette'
REQUIRED_PALETTE = {
    "primary", "brand", "window", "base", "surface", 
    "surface_mid", "surface_pressed", "text", 
    "text_secondary", "text_disabled", "success", 
    "warning", "danger", "info"
}

# ─────────────────────────────────────────────────────────────
# YAML LOADING
# ─────────────────────────────────────────────────────────────

def load_yaml(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def extract_palette(theme_data):
    """Extract palette keys safely."""
    return set((theme_data.get("palette") or {}).keys())


# ─────────────────────────────────────────────────────────────
# VALIDATION
# ─────────────────────────────────────────────────────────────

def validate_theme(file_path):
    data = load_yaml(file_path)

    if not data:
        print(f"[ERROR] Empty or invalid YAML: {file_path}")
        return False

    palette_keys = extract_palette(data)

    missing = REQUIRED_PALETTE - palette_keys
    extra = palette_keys - REQUIRED_PALETTE

    ok = True

    print(f"\n==============================")
    print(f"Theme: {data.get('name', os.path.basename(file_path))}")
    print(f"File : {file_path}")
    print(f"==============================")

    if missing:
        ok = False
        print("\n❌ Missing tokens:")
        for t in sorted(missing):
            print(f"  - {t}")

    if extra:
        print("\n⚠️ Extra tokens (not in contract):")
        for t in sorted(extra):
            print(f"  - {t}")

    if not missing and not extra:
        print("\n✅ Theme fully compliant")

    return ok


# ─────────────────────────────────────────────────────────────
# PROJECT SCAN
# ─────────────────────────────────────────────────────────────

def find_themes(root_dir):
    themes = []
    for dirpath, _, filenames in os.walk(root_dir):
        for f in filenames:
            if f.endswith(".yml") or f.endswith(".yaml"):
                themes.append(os.path.join(dirpath, f))
    return themes


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Usage: python theme_checker.py <themes_root_dir>")
        sys.exit(1)

    root_dir = sys.argv[1]
    theme_files = find_themes(root_dir)

    if not theme_files:
        print("No theme files found.")
        sys.exit(1)

    all_ok = True

    for theme_file in theme_files:
        try:
            ok = validate_theme(theme_file)
            all_ok = all_ok and ok
        except Exception as e:
            all_ok = False
            print(f"\n[ERROR] Failed to parse {theme_file}")
            print(e)

    print("\n==============================")
    if all_ok:
        print("✅ ALL THEMES PASS VALIDATION")
    else:
        print("❌ SOME THEMES HAVE ISSUES")
    print("==============================\n")

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()


