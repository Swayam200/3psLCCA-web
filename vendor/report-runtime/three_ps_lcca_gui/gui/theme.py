"""
gui/theme.py - Layout and typography design tokens.

Colours are no longer defined here. Use gui.themes.get_token() instead:

    from gui.themes import get_token

    color = get_token("primary")               # full opacity
    color = get_token("danger", "disabled")    # 38 % alpha

Migration reference - old constant → new get_token() call
----------------------------------------------------------
    PRIMARY           → get_token("primary")
    PRIMARY_HOVER     → get_token("primary", "hover")
    PRIMARY_ACTIVE    → get_token("primary", "pressed")
    DANGER            → get_token("danger")
    SUCCESS           → get_token("success")
    WARNING_COLOR     → get_token("warning")
    INFO              → get_token("info")
    MUTED             → get_token("text_disabled")
    PLACEHOLDER       → get_token("text_secondary")
    VALIDATION_ERROR  → get_token("danger")
    BORDER            → get_token("border")
    CARD_BG / WHITE   → get_token("base")
    BODY_BG           → get_token("window")
    BODY_COLOR        → get_token("text")
    SECONDARY         → get_token("text_secondary")
    SURFACE           → get_token("surface")
    SURFACE_ACTIVE    → get_token("surface_pressed")
    SIDEBAR_HOVER     → get_token("surface", "hover")
    SIDEBAR_SEL       → get_token("surface", "pressed")
"""

# ── Spacing (Bootstrap spacer multiples, in px) ────────────────────────────
# Base spacer = 4 px
SP1  =  4
SP2  =  8
SP3  = 12
SP4  = 16
SP5  = 20
SP6  = 24
SP8  = 32
SP10 = 40

# ── Border radius ──────────────────────────────────────────────────────────
RADIUS_SM =  4
RADIUS_MD =  6
RADIUS_LG =  8
RADIUS_XL = 12

# ── Button heights ─────────────────────────────────────────────────────────
BTN_SM = 28   # compact / icon-adjacent
BTN_MD = 36   # standard
BTN_LG = 40   # primary CTA

# ── Typography ─────────────────────────────────────────────────────────────
FONT_FAMILY = "Ubuntu"

# Point sizes
FS_XS   =  7   # badge pill, tertiary hint
FS_SM   =  8   # caption, overline label, sort buttons
FS_BASE =  9   # body text, standard buttons
FS_MD   = 10   # sidebar row name, banner label
FS_LG      = 11   # grid card title
FS_SUBHEAD = 16   # content-area section heading, group divider
FS_XL      = 15   # logo / brand mark
FS_DISP  = 18   # greeting display heading
FS_DISP_LG = 22 # prominent card values
FS_DISP_XL = 32 # extra large dashboard highlights

# Font weights (match QFont.Weight int values)
# Toned down for subtler hierarchy:
# - MEDIUM:   500 -> 450
# - SEMIBOLD: 600 -> 550
# - BOLD:     700 -> 600
FW_LIGHT    = 300
FW_NORMAL   = 400
FW_MEDIUM   = 450
FW_SEMIBOLD = 550
FW_BOLD     = 600

# Centralized weight tokens for QSS substitution
QSS_WEIGHTS = {
    "weight-medium":   str(FW_MEDIUM),
    "weight-semibold": str(FW_SEMIBOLD),
    "weight-bold":     str(FW_BOLD),
}


