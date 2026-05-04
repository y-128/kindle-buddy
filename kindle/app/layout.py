"""Layout constants for Kindle 600×800 e-ink display (K7/K8 Pearl, 167 PPI)."""

# Screen dimensions
W = 600
H = 800

# Leave the Kindle status/clock strip untouched.
SAFE_TOP = 36

# Text sizes (px) — scaled from M5Paper 540×960 originals
TS_SM   = 14   # labels
TS_MD   = 20   # body text
TS_LG   = 26   # emphasis
TS_XL   = 34   # tool name / option labels
TS_XXL  = 46   # big headline
TS_HUGE = 60   # passkey / splash

# Colours (0=black, 255=white for PIL 'L' mode)
INK     = 0
INK_DIM = 40
PAPER   = 255

# Rule thickness
RULE_THICK = 2

# ─── Section Y positions (portrait, top→bottom) ──────────────────────────────
TOP_BAND_H   = 56   # project / sessions  |  model / budget
RULE1_Y      = TOP_BAND_H
MSG_Y        = TOP_BAND_H + 8
MSG_H        = 90   # "Claude says" area
RULE2_Y      = MSG_Y + MSG_H
LOG_Y        = RULE2_Y + 6
LOG_H        = 340  # recent activity log
RULE3_Y      = LOG_Y + LOG_H
BUDDY_Y      = RULE3_Y + 8
BUDDY_H      = 100  # ASCII art + status hints
RULE4_Y      = BUDDY_Y + BUDDY_H
FOOTER_Y     = RULE4_Y + 4   # button-hint footer

# ─── Approval / question card (full-screen overlay) ───────────────────────────
CARD_TITLE_Y  = 30
CARD_TOOL_Y   = 70
CARD_HINT_Y   = 110
CARD_BODY_Y   = 150
CARD_BODY_H   = 460   # scrollable body area
CARD_TABS_Y   = 620
CARD_BTN_Y    = 660

# ─── Touch zones  (x, y, w, h) — portrait ────────────────────────────────────
APPROVE_ZONE     = (8,   718, 284,  64)   # left half — approve
DENY_ZONE        = (308, 718, 284,  64)   # right half — deny
DND_BUTTON_ZONE  = (420, 728, 156, 48)
SETTINGS_ZONE    = (440, SAFE_TOP + 36, 148, 32)
EXIT_ZONE        = (440, SAFE_TOP + 4,  148, 30)
BACK_ZONE        = (12,  SAFE_TOP + 4,  120, 30)
FULL_REFRESH_ZONE = (48, SAFE_TOP + 254, 504, 58)
DND_TOGGLE_ZONE  = DND_BUTTON_ZONE        # dashboard DND button

# Session rows (left pane of dashboard)
_SESSION_PANE_TOP = SAFE_TOP + 70 + 34   # first row top = 140
_SESSION_ROW_STEP = 24
_SESSION_ROW_H    = 22
_SESSION_ROW_W    = 278                  # mid_x(290) - PAD(12)

def session_row_zones(n: int) -> list[tuple[int, int, int, int]]:
    """Return touch zones for the first n session rows (max 4)."""
    return [
        (PAD, _SESSION_PANE_TOP + i * _SESSION_ROW_STEP, _SESSION_ROW_W, _SESSION_ROW_H)
        for i in range(min(n, 4))
    ]

def question_option_zones(n: int) -> list[tuple[int, int, int, int]]:
    """Return up to *n* touch zones for AskUserQuestion options.

    Up to 4 options are arranged in a 2×2 grid above the deny/approve row.
    """
    cols = 2
    btn_w = (W - 16) // cols
    btn_h = 56
    zones = []
    for i in range(min(n, 4)):
        col = i % cols
        row = i // cols
        x = 8 + col * (btn_w + 0)
        y = 600 + row * (btn_h + 8)
        zones.append((x, y, btn_w, btn_h))
    return zones

# ─── Padding / margin ─────────────────────────────────────────────────────────
PAD = 12

# ─── Font paths (relative to this file's directory) ──────────────────────────
import os as _os
_HERE = _os.path.dirname(_os.path.abspath(__file__))
_FONTS = _os.path.join(_HERE, "fonts")

# DejaVu does not include Japanese glyphs.  Prefer a bundled CJK font when
# present, then fall back to the old DejaVu files so the app still starts.
FONT_SANS_CANDIDATES = (
    _os.path.join(_FONTS, "NotoSansCJKjp-Regular.otf"),
    _os.path.join(_FONTS, "NotoSansJP-Regular.ttf"),
    _os.path.join(_FONTS, "SourceHanSansJP-Regular.otf"),
    _os.path.join(_FONTS, "BIZUDGothic-Regular.ttf"),
    _os.path.join(_FONTS, "DejaVuSans.ttf"),
)

FONT_MONO_CANDIDATES = (
    _os.path.join(_FONTS, "NotoSansMonoCJKjp-Regular.otf"),
    _os.path.join(_FONTS, "NotoSansMonoCJKjp-Regular.ttf"),
    _os.path.join(_FONTS, "NotoSansCJKjp-Regular.otf"),
    _os.path.join(_FONTS, "NotoSansJP-Regular.ttf"),
    _os.path.join(_FONTS, "SourceHanSansJP-Regular.otf"),
    _os.path.join(_FONTS, "BIZUDGothic-Regular.ttf"),
    _os.path.join(_FONTS, "DejaVuSansMono.ttf"),
)

FONT_SANS = FONT_SANS_CANDIDATES[0]
FONT_MONO = FONT_MONO_CANDIDATES[0]
