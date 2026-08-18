DECIMAL_PLACES_FOR_LATEX       = 2
DECIMAL_PLACES_FOR_LATEX_RATIO = 4

# LaTeX font size declaration applied to the whole devmode document.
# Valid values: \tiny \scriptsize \footnotesize \small \normalsize \large \Large \LARGE \huge \Huge
LATEX_FONT_SIZE = r"\small"

# ─────────────────────────────────────────────────────────────────────────────
# LaTeX Packages (Single Source of Truth)
# ─────────────────────────────────────────────────────────────────────────────
# Key: package name, Value: list of options or None
REQUIRED_LATEX_PACKAGES = {
    "inputenc":   ["utf8"],       # base LaTeX
    "fontenc":    ["T1"],         # base LaTeX
    "mathptmx":   None,           # psnfss
    "microtype":  ["protrusion=true", "expansion=false"],
    "geometry":   ["a4paper", "top=2.5cm", "bottom=2.5cm", "left=2.5cm", "right=2.5cm"],
    "setspace":   None,
    "booktabs":   None,
    "array":      None,           # tools
    "longtable":  None,           # tools
    "tabularx":   None,           # tools
    "multirow":   None,
    "makecell":   None,
    "graphicx":   None,           # graphics
    "float":      None,
    "pdflscape":  None,
    "adjustbox":  None,
    "caption":    None,
    "amsmath":    None,
    "xcolor":     None,
    "colortbl":   None,
    "enumitem":   None,
    "fancyhdr":   None,
    "lastpage":   None,
    "titlesec":   None,
    "etoolbox":   None,
    "hyperref":   ["hidelinks", "hypertexnames=false"],
    "bookmark":   None,
    "tikz":       None,
    "tcolorbox":  ["many"],        # NOT "most": that also pulls in the "listingsutf8"
                                   # library, which \RequirePackage{listingsutf8} — a
                                   # separate CTAN package not in the LaTeX bundle and
                                   # never actually used (no lstlisting/tcblisting here).
                                   # "many" = raster,skins,breakable,hooks,theorems,fitting
                                   # — covers the `enhanced` (skins) usage in title_page.py.
}

# ─────────────────────────────────────────────────────────────────────────────
# Known MISSING from bundle (do not add to REQUIRED_LATEX_PACKAGES):
#   tocloft
# Use verify_packages() / list_bundle_packages() at runtime for ground truth.
# ─────────────────────────────────────────────────────────────────────────────


def _find_texmf_latex():
    """Return the texmf-dist/tex/latex Path inside the active env, or None."""
    import sys
    from pathlib import Path
    candidates = [
        Path(sys.prefix) / "Library" / "share" / "osdag_latex_env" / "texmf-dist" / "tex" / "latex",
        Path(sys.prefix) / "share"   / "osdag_latex_env" / "texmf-dist" / "tex" / "latex",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def list_bundle_packages() -> list:
    """
    Scan the bundled osdag_latex_env and return every .sty stem found.
    Returns an empty list if the bundle is not present.
    """
    texmf = _find_texmf_latex()
    if texmf is None:
        return []
    return sorted({sty.stem for sty in texmf.rglob("*.sty")})


def verify_packages() -> dict:
    """
    Check REQUIRED_LATEX_PACKAGES against the bundle by scanning all .sty files.
    Returns:
      {
        "bundle_path":     Path or None,
        "bundle_packages": sorted list of all .sty stems in the bundle,
        "available":       required packages found in the bundle,
        "missing":         required packages NOT found in the bundle,
      }
    Does not run pdflatex — purely a filesystem check.
    """
    texmf = _find_texmf_latex()
    bundle_set = set(list_bundle_packages())

    available, missing = [], []
    for pkg in REQUIRED_LATEX_PACKAGES:
        (available if pkg in bundle_set else missing).append(pkg)

    return {
        "bundle_path":     texmf,
        "bundle_packages": sorted(bundle_set),
        "available":       available,
        "missing":         missing,
    }


# Optional light column backgrounds for generated tables.
LATEX_TABLE_COLUMN_BG_ENABLED = False
LATEX_TABLE_COLUMN_BG_COLORS = ("gray!4", "blue!3")

LATEX_TABLE_LAYOUTS = {
    "field_table": r">{\raggedright\arraybackslash}p{0.40\linewidth}>{\raggedleft\arraybackslash}p{0.40\linewidth}",
    "structure_work": r">{\raggedright\arraybackslash}p{0.34\linewidth}>{\raggedleft\arraybackslash}p{0.09\linewidth}>{\centering\arraybackslash}p{0.09\linewidth}>{\raggedleft\arraybackslash}p{0.10\linewidth}>{\centering\arraybackslash}p{0.14\linewidth}>{\raggedleft\arraybackslash}p{0.10\linewidth}",
    "material_emissions": r">{\raggedright\arraybackslash}p{0.23\linewidth}>{\raggedleft\arraybackslash}p{0.09\linewidth}>{\centering\arraybackslash}p{0.07\linewidth}>{\raggedleft\arraybackslash}p{0.12\linewidth}>{\raggedleft\arraybackslash}p{0.12\linewidth}>{\centering\arraybackslash}p{0.11\linewidth}>{\raggedleft\arraybackslash}p{0.10\linewidth}",
    "material_emissions_excluded": r">{\raggedright\arraybackslash}p{0.47\linewidth}>{\raggedleft\arraybackslash}p{0.47\linewidth}",
    "recycling_included": r">{\raggedright\arraybackslash}p{0.25\linewidth}>{\raggedleft\arraybackslash}p{0.12\linewidth}>{\raggedleft\arraybackslash}p{0.14\linewidth}>{\centering\arraybackslash}p{0.08\linewidth}>{\raggedleft\arraybackslash}p{0.13\linewidth}>{\raggedleft\arraybackslash}p{0.13\linewidth}",
    "recycling_excluded": r">{\raggedright\arraybackslash}p{0.47\linewidth}>{\raggedleft\arraybackslash}p{0.47\linewidth}",
    "transport_summary": r">{\raggedright\arraybackslash}p{0.09\linewidth}>{\raggedright\arraybackslash}p{0.11\linewidth}>{\raggedright\arraybackslash}p{0.10\linewidth}>{\raggedleft\arraybackslash}p{0.10\linewidth}>{\raggedleft\arraybackslash}p{0.09\linewidth}>{\raggedleft\arraybackslash}p{0.09\linewidth}>{\raggedleft\arraybackslash}p{0.06\linewidth}>{\raggedleft\arraybackslash}p{0.14\linewidth}",
    "transport_emissions": r">{\raggedright\arraybackslash}p{0.27\linewidth}>{\raggedright\arraybackslash}p{0.12\linewidth}>{\raggedleft\arraybackslash}p{0.13\linewidth}>{\raggedleft\arraybackslash}p{0.12\linewidth}>{\raggedleft\arraybackslash}p{0.07\linewidth}>{\raggedleft\arraybackslash}p{0.14\linewidth}",
    "machinery_emissions": r"p{0.22\linewidth}p{0.14\linewidth}p{0.12\linewidth}p{0.10\linewidth}p{0.10\linewidth}p{0.14\linewidth}p{0.10\linewidth}p{0.12\linewidth}",
}
