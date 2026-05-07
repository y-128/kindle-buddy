from __future__ import annotations

"""Display engine — Pillow → FBInk framebuffer rendering for Kindle K7/K8.

Public API
----------
    renderer = Renderer()
    renderer.draw_dashboard(state)
    renderer.draw_approval_card(state)
    renderer.full_refresh()

On the Mac (for development), FBInk is not available.  Import is guarded so
``python3 display.py`` writes a ``preview.png`` instead.

Layout reference: layout.py.  All pixel coordinates are for 600×800.
"""

import logging
import os
import textwrap
import time
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image, ImageDraw, ImageFont

import layout
import frames as buddy_frames
from state import KindleState

log = logging.getLogger(__name__)

# ── FBInk import (Kindle only) ────────────────────────────────────────────────
# On Kindle, NiLuJe's snapshot provides _fbink (CFFI). Wrap it to match the
# call sites below.

_FBINK_AVAILABLE = False
_fbink_lib = None
_fbink_ffi = None

try:
    import _fbink as _fbink_raw  # type: ignore[import]
    _fbink_lib = _fbink_raw.lib
    _fbink_ffi = _fbink_raw.ffi
    _FBINK_AVAILABLE = True
except ImportError:
    pass

# ── Font cache ────────────────────────────────────────────────────────────────

_font_cache: dict[tuple[tuple[str, ...], int], ImageFont.FreeTypeFont] = {}
_font_path_cache: dict[tuple[str, ...], str | None] = {}


def _font(paths: str | tuple[str, ...], size: int) -> ImageFont.FreeTypeFont:
    if isinstance(paths, str):
        candidates = (paths,)
    else:
        candidates = paths

    key = (candidates, size)
    if key not in _font_cache:
        font_path = _font_path_cache.get(candidates)
        if candidates not in _font_path_cache:
            font_path = next((path for path in candidates if os.path.exists(path)), None)
            _font_path_cache[candidates] = font_path
            if font_path:
                log.info("[display] using font: %s", font_path)
            else:
                log.warning("[display] no configured fonts found; using Pillow default")

        if font_path:
            try:
                _font_cache[key] = ImageFont.truetype(font_path, size)
            except Exception as e:
                log.warning("[display] failed to load font %s: %s", font_path, e)
                _font_cache[key] = ImageFont.load_default()
        else:
            _font_cache[key] = ImageFont.load_default()
    return _font_cache[key]


def _sans(size: int) -> ImageFont.FreeTypeFont:
    return _font(layout.FONT_SANS_CANDIDATES, size)


def _mono(size: int) -> ImageFont.FreeTypeFont:
    return _font(layout.FONT_MONO_CANDIDATES, size)


def _emoji(size: int) -> ImageFont.FreeTypeFont:
    return _font(layout.FONT_EMOJI_CANDIDATES, size)


def _is_emoji(ch: str) -> bool:
    cp = ord(ch)
    return (
        0x1F000 <= cp <= 0x1FFFF or
        0x2600 <= cp <= 0x27BF or
        0x2B00 <= cp <= 0x2BFF
    )


def _text_segments(text: str) -> list[tuple[str, bool]]:
    """Split text into (chunk, is_emoji) segments, skipping invisible emoji modifiers."""
    _SKIP = {0x200D, 0xFE0E, 0xFE0F}
    segments: list[tuple[str, bool]] = []
    current = ""
    current_emoji: bool | None = None
    for ch in text:
        if ord(ch) in _SKIP:
            continue
        em = _is_emoji(ch)
        if current_emoji is None:
            current_emoji = em
        if em != current_emoji:
            if current:
                segments.append((current, current_emoji))
            current = ch
            current_emoji = em
        else:
            current += ch
    if current:
        segments.append((current, current_emoji if current_emoji is not None else False))
    return segments


# ── Renderer ──────────────────────────────────────────────────────────────────

class Renderer:
    """Manages one PIL Image and pushes it to the Kindle framebuffer."""

    def __init__(self):
        self._img  = Image.new("L", (layout.W, layout.H), layout.PAPER)
        self._draw = ImageDraw.Draw(self._img)
        self._last_full_refresh = 0.0
        self._full_refresh_interval = 120  # seconds

        if _FBINK_AVAILABLE:
            self._fbink_cfg = _fbink_ffi.new("FBInkConfig *")
            _fbink_lib.fbink_init(_fbink_lib.FBFD_AUTO, self._fbink_cfg)
        else:
            log.warning("[display] FBInk not available — preview mode (PNG output)")

    # ── low-level helpers ─────────────────────────────────────────────────────

    def _clear(self) -> None:
        self._draw.rectangle([0, 0, layout.W - 1, layout.H - 1], fill=layout.PAPER)

    def _rule(self, y: int, inset: int = 0) -> None:
        x0 = inset
        x1 = layout.W - 1 - inset
        for dy in range(layout.RULE_THICK):
            self._draw.line([(x0, y + dy), (x1, y + dy)], fill=layout.INK)

    def _seg_width(self, seg: str, is_em: bool, font: ImageFont.FreeTypeFont) -> int:
        f = _emoji(font.size) if is_em else font
        bb = f.getbbox(seg)
        return bb[2] - bb[0]

    def _text(self, text: str, x: int, y: int, font: ImageFont.FreeTypeFont,
              fill: int = layout.INK, anchor: str = "la") -> None:
        segs = _text_segments(text)
        if not segs or not any(is_em for _, is_em in segs):
            self._draw.text((x, y), text, font=font, fill=fill, anchor=anchor)
            return
        total_w = sum(self._seg_width(s, e, font) for s, e in segs)
        h_anchor = anchor[0] if anchor else "l"
        if h_anchor == "r":
            cx = x - total_w
        elif h_anchor == "m":
            cx = x - total_w // 2
        else:
            cx = x
        v_anchor = anchor[1] if len(anchor) > 1 else "a"
        for seg, is_em in segs:
            f = _emoji(font.size) if is_em else font
            self._draw.text((cx, y), seg, font=f, fill=fill, anchor="l" + v_anchor)
            cx += self._seg_width(seg, is_em, font)

    def _text_width(self, text: str, font: ImageFont.FreeTypeFont) -> int:
        segs = _text_segments(text)
        if not segs or not any(is_em for _, is_em in segs):
            bb = font.getbbox(text)
            return bb[2] - bb[0]
        return sum(self._seg_width(s, e, font) for s, e in segs)

    def _rect(self, x: int, y: int, w: int, h: int,
              fill: int | None = None, outline: int | None = None) -> None:
        self._draw.rectangle([x, y, x + w - 1, y + h - 1], fill=fill, outline=outline)

    def _wrap_lines(self, text: str, font: ImageFont.FreeTypeFont,
                    max_width: int) -> list[str]:
        """Word-wrap *text* to fit within *max_width* pixels."""
        if not text:
            return [""]
        if " " not in text:
            return self._wrap_chars(text, font, max_width)
        words = text.split()
        lines: list[str] = []
        current = ""
        for word in words:
            probe = (current + " " + word).strip()
            if self._text_width(probe, font) <= max_width:
                current = probe
            else:
                if current:
                    lines.append(current)
                if self._text_width(word, font) <= max_width:
                    current = word
                else:
                    lines.extend(self._wrap_chars(word, font, max_width))
                    current = ""
        if current:
            lines.append(current)
        return lines or [""]

    def _wrap_chars(self, text: str, font: ImageFont.FreeTypeFont,
                    max_width: int) -> list[str]:
        lines: list[str] = []
        current = ""
        for ch in text:
            probe = current + ch
            if self._text_width(probe, font) <= max_width:
                current = probe
            else:
                if current:
                    lines.append(current)
                current = ch
        if current:
            lines.append(current)
        return lines or [""]

    def _fit_text(self, text: str, font: ImageFont.FreeTypeFont,
                  max_width: int) -> str:
        if self._text_width(text, font) <= max_width:
            return text
        ell = "..."
        out = ""
        for ch in text:
            if self._text_width(out + ch + ell, font) > max_width:
                break
            out += ch
        return out + ell if out else ell

    # ── framebuffer output ────────────────────────────────────────────────────

    def _push(self, full: bool = False) -> None:
        now = time.monotonic()
        # Periodic forced full refresh to clear ghosting
        if now - self._last_full_refresh >= self._full_refresh_interval:
            full = True

        if not _FBINK_AVAILABLE:
            self._img.save("preview.png")
            log.info("[display] preview.png written")
            return

        # fb(col, row) maps directly to display(col, row) in portrait.
        # fbink_print_raw_data applies an unwanted rotation=3 transform, so we
        # write the image directly to /dev/fb0 and use FBInk only for the refresh.
        raw = self._img.tobytes()
        _FB_LINE = 608  # physical line_length (600px + 8 padding bytes)
        W, H = layout.W, layout.H
        try:
            with open("/dev/fb0", "r+b") as _fb:
                for row in range(layout.SAFE_TOP, H):
                    _fb.seek(row * _FB_LINE)
                    _fb.write(raw[row * W: row * W + W])
        except OSError as e:
            log.warning("[display] fb0 write error: %s", e)
            return

        cfg = _fbink_ffi.new("FBInkConfig *")
        cfg.wfm_mode = _fbink_lib.WFM_GC16 if full else _fbink_lib.WFM_GL16
        _fbink_lib.fbink_refresh(_fbink_lib.FBFD_AUTO, 0, 0, 0, 0, cfg)
        if full:
            self._last_full_refresh = now

    def full_refresh(self) -> None:
        """Force a GC16 full refresh (clears ghosting)."""
        self._last_full_refresh = 0.0
        self._push(full=True)

    def white_flash(self) -> None:
        """Clear the Buddy drawing area to white before redrawing content."""
        self._clear()
        self._last_full_refresh = 0.0
        self._push(full=True)

    def black_white_flash(self) -> None:
        """Drive e-ink particles through black, then white, before redraw."""
        self._draw.rectangle([0, 0, layout.W - 1, layout.H - 1], fill=layout.INK)
        self._last_full_refresh = 0.0
        self._push(full=True)
        time.sleep(0.18)
        self._clear()
        self._last_full_refresh = 0.0
        self._push(full=True)

    # ── dashboard view ────────────────────────────────────────────────────────

    def draw_dashboard(self, s: KindleState,
                       celebrate: bool = False,
                       dnd: bool = False) -> None:
        self._clear()
        P = layout.PAD
        Y = layout.SAFE_TOP
        label_font = _sans(layout.TS_SM)
        body_font = _sans(layout.TS_MD)

        # Header
        self._text("Kindle Buddy", P, Y + 8, _sans(layout.TS_LG))
        owner = (s.owner or "claude-buddy")
        self._text(self._fit_text(owner, label_font, 260), P, Y + 40, label_font)
        self._text("EXIT", layout.W - P, Y + 8, label_font, anchor="ra")
        self._text("SETTINGS", layout.W - P, Y + 40, label_font, anchor="ra")
        self._rule(Y + 68)

        # Sessions / model pane
        pane_top, pane_bottom = Y + 70, Y + 222
        mid_x = 290
        self._draw.line([(mid_x, pane_top + 8), (mid_x, pane_bottom - 4)], fill=layout.INK, width=1)
        self._text("SESSIONS", P, pane_top + 10, label_font, fill=layout.INK_DIM)

        rows = s.session_rows[:4]
        if not rows:
            rows = []
        row_y = pane_top + 34
        for i, row in enumerate(rows):
            y = row_y + i * 24
            focused = row.focused or row.waiting
            if focused:
                self._rect(P - 2, y - 2, mid_x - P - 8, 22, fill=layout.INK)
            marker = "*" if row.running else ("!" if row.waiting else "-")
            project = row.project or row.sid[:8] or "(unknown)"
            suffix = row.branch or ("waiting" if row.waiting else "")
            text = self._fit_text(f"{marker} {project}", body_font, 168)
            self._text(text, P, y, body_font, fill=layout.PAPER if focused else layout.INK)
            if suffix:
                self._text(self._fit_text(suffix, label_font, 72), mid_x - 12, y + 3,
                           label_font, fill=layout.PAPER if focused else layout.INK, anchor="ra")
        if not rows:
            self._text("* (unknown)", P, row_y, body_font)

        model_x = mid_x + 16
        self._text("MODEL", model_x, pane_top + 10, label_font, fill=layout.INK_DIM)
        model = s.model_name or "Claude"
        self._text(self._fit_text(model, _sans(layout.TS_LG), layout.W - model_x - P),
                   model_x, pane_top + 34, _sans(layout.TS_LG))
        self._text("CONTEXT", model_x, pane_top + 86, label_font, fill=layout.INK_DIM)
        if s.budget_limit:
            ratio = min(1.0, s.tokens_today / s.budget_limit)
            ctx = f"{s.tokens_today / 1000:.1f}K / {s.budget_limit / 1000:.0f}K  {ratio * 100:.0f}%"
        else:
            ratio = 0.0
            ctx = f"{s.sessions_running} running / {s.sessions_total} total"
        self._text(ctx, model_x, pane_top + 108, body_font)
        bar_x, bar_y, bar_w, bar_h = model_x, pane_top + 136, layout.W - model_x - P, 12
        self._rect(bar_x, bar_y, bar_w, bar_h, outline=layout.INK_DIM)
        if s.budget_limit and ratio > 0:
            filled = int((bar_w - 2) * ratio)
            if filled > 0:
                self._rect(bar_x + 1, bar_y + 1, filled, bar_h - 2, fill=layout.INK)
        self._rule(pane_bottom)

        # Stats
        stat_y = pane_bottom + 14
        stat_w = layout.W // 3
        stats = [
            ("LEVEL", str(max(1, int(s.tokens_today / 1000))) if s.tokens_today else str(s.sessions_total)),
            ("APPROVED", str(s.approved_count)),
            ("DENIED", str(s.denied_count)),
        ]
        for i, (name, value) in enumerate(stats):
            x = P + i * stat_w
            self._text(name, x, stat_y, label_font, fill=layout.INK_DIM)
            self._text(value, x, stat_y + 24, _sans(layout.TS_LG))
        self._rule(Y + 304)

        # Latest reply
        self._text("LATEST REPLY", P, Y + 318, label_font, fill=layout.INK_DIM)
        reply = s.assistant_msg or s.msg or "Waiting for Claude Code..."
        reply_font = _sans(layout.TS_SM + 2)
        reply_lines = self._wrap_lines(reply, reply_font, layout.W - 2 * P)
        for i, line in enumerate(reply_lines[:4]):
            self._text(line, P, Y + 342 + i * 22, reply_font)
        self._rule(Y + 426)

        # Activity
        self._text("ACTIVITY", P, Y + 440, label_font, fill=layout.INK_DIM)
        log_lines: list[str] = []
        for entry in s.lines:
            log_lines.extend(self._wrap_lines(entry, body_font, layout.W - 2 * P))
        for i, entry in enumerate(log_lines[:7]):
            self._text(entry, P, Y + 468 + i * 24, body_font, fill=layout.INK_DIM)
        self._rule(Y + 640)

        # Footer
        frame = buddy_frames.pick(
            running=s.sessions_running,
            waiting=s.sessions_waiting,
            recently_completed=s.recently_completed,
            connected=s.sessions_total > 0 or s.assistant_msg != "",
            celebrate=celebrate,
            dnd=dnd,
        )
        art_font = _mono(layout.TS_SM)
        art_line_h = layout.TS_SM + 1
        for i, art_line in enumerate(frame):
            self._text(art_line, P + 50, Y + 668 + i * art_line_h, art_font)
        footer_x = 330
        self._text("WiFi TCP", footer_x, Y + 660, label_font, fill=layout.INK_DIM)
        self._text("DND: tap lower right", footer_x, Y + 684, label_font)
        self._text("Approve / Deny on cards", footer_x, Y + 708, label_font)
        if dnd:
            self._rect(footer_x, Y + 730, 92, 22, fill=layout.INK)
            self._text("DND ON", footer_x + 8, Y + 733, label_font, fill=layout.PAPER)

        self._push()

    def draw_settings(self, s: KindleState, dnd: bool = False,
                      notice: str = "", full: bool = False) -> None:
        self._clear()
        P = layout.PAD
        Y = layout.SAFE_TOP
        label_font = _sans(layout.TS_SM)
        body_font = _sans(layout.TS_MD)
        title_font = _sans(layout.TS_LG)

        self._text("BACK", P, Y + 8, label_font)
        self._text("EXIT", layout.W - P, Y + 8, label_font, anchor="ra")
        self._text("Settings", layout.W // 2, Y + 44, title_font, anchor="ma")
        self._rule(Y + 76)

        self._text("DND", P, Y + 106, label_font, fill=layout.INK_DIM)
        self._text("Auto-approve approval cards while active", P, Y + 128, body_font)
        bx, by, bw, bh = layout.DND_BUTTON_ZONE
        self._rect(bx, by, bw, bh, fill=layout.INK if dnd else None, outline=layout.INK)
        dnd_label = "DND ON" if dnd else "DND OFF"
        self._text(dnd_label, bx + bw // 2, by + 13, body_font,
                   fill=layout.PAPER if dnd else layout.INK, anchor="ma")

        fx, fy, fw, fh = layout.FULL_REFRESH_ZONE
        self._rect(fx, fy, fw, fh, outline=layout.INK)
        self._text("Full refresh", fx + 18, fy + 10, body_font)
        self._text("Clear e-ink ghosting", fx + 18, fy + 34, label_font, fill=layout.INK_DIM)

        self._rule(Y + 350)
        self._text("Connection", P, Y + 374, label_font, fill=layout.INK_DIM)
        connected = "connected" if s.connected else "waiting"
        self._text(f"Bridge: {connected}", P, Y + 398, body_font)
        self._text(f"Sessions: {s.sessions_running} running / {s.sessions_total} total",
                   P, Y + 426, body_font)
        if notice:
            self._rect(P, Y + 448, layout.W - 2 * P, 32, fill=layout.INK)
            self._text(notice, layout.W // 2, Y + 454, body_font,
                       fill=layout.PAPER, anchor="ma")
        self._text("Recommended later: log viewer, IP display, contrast/theme,",
                   P, Y + 486, label_font, fill=layout.INK_DIM)
        self._text("touch calibration, and auto-start toggle.",
                   P, Y + 506, label_font, fill=layout.INK_DIM)

        self._push(full=full)

    def draw_exit_screen(self) -> None:
        self._clear()
        Y = layout.SAFE_TOP
        self._text("Claude Buddy stopped", layout.W // 2, Y + 260,
                   _sans(layout.TS_LG), anchor="ma")
        self._text("Return to KUAL or Kindle Home.", layout.W // 2, Y + 300,
                   _sans(layout.TS_MD), fill=layout.INK_DIM, anchor="ma")
        self._push(full=True)

    # ── approval / question card ──────────────────────────────────────────────

    def draw_approval_card(self, s: KindleState, elapsed_s: float = 0) -> None:
        self._clear()
        P = layout.PAD
        Y = layout.SAFE_TOP

        is_question = s.prompt_kind == "question"
        title = "Question" if is_question else "Permission Request"
        self._text(title, layout.W // 2, Y + layout.CARD_TITLE_Y, _sans(layout.TS_SM),
                    fill=layout.INK_DIM, anchor="ma")

        # Tool name
        tool = s.prompt_tool or "Unknown"
        tool_font = _sans(layout.TS_XL)
        self._text(self._fit_text(tool, tool_font, layout.W - 2 * P),
                   layout.W // 2, Y + layout.CARD_TOOL_Y, tool_font, anchor="ma")

        # Hint / one-liner
        if s.prompt_hint:
            hint_lines = self._wrap_lines(s.prompt_hint, _sans(layout.TS_MD), layout.W - 2 * P)
            for i, hl in enumerate(hint_lines[:2]):
                self._text(hl, P, Y + layout.CARD_HINT_Y + i * (layout.TS_MD + 2), _sans(layout.TS_MD))

        body_rule_y = Y + layout.CARD_HINT_Y + layout.TS_MD * 2 + 8
        self._rule(body_rule_y)

        # Body (diff / command)
        if s.prompt_body:
            body_font = _mono(layout.TS_SM)
            body_line_h = layout.TS_SM + 2
            max_body_lines = layout.CARD_BODY_H // body_line_h
            raw_lines = s.prompt_body.splitlines()
            body_lines: list[str] = []
            for raw in raw_lines:
                body_lines.extend(self._wrap_lines(raw, body_font, layout.W - 2 * P))
            for i, bl in enumerate(body_lines[:max_body_lines]):
                self._text(bl, P, body_rule_y + 14 + i * body_line_h, body_font)

        # Pending tabs
        if s.pending_count > 1:
            tab_w = (layout.W - 2 * P) // min(s.pending_count, 4)
            for i, tab in enumerate(s.pending_tabs[:4]):
                tx = P + i * tab_w
                label = f"{tab.tool[:8]}\n{tab.project[:10]}"
                self._text(label, tx + 4, Y + layout.CARD_TABS_Y, _sans(layout.TS_SM))

        self._rule(layout.CARD_BTN_Y - 6)

        # Approve / deny buttons
        if is_question and s.prompt_options:
            for i, (bx, by, bw, bh) in enumerate(layout.question_option_zones(len(s.prompt_options))):
                self._rect(bx, by, bw, bh, outline=layout.INK)
                label = self._fit_text(s.prompt_options[i], _sans(layout.TS_SM), bw - 12)
                lw = self._text_width(label, _sans(layout.TS_SM))
                self._text(label, bx + (bw - lw) // 2, by + (bh - layout.TS_SM) // 2,
                            _sans(layout.TS_SM))
        else:
            # Approve button
            ax, ay, aw, ah = layout.APPROVE_ZONE
            self._rect(ax, ay, aw, ah, fill=layout.INK)
            lbl = "Approve"
            lw = self._text_width(lbl, _sans(layout.TS_MD))
            self._text(lbl, ax + (aw - lw) // 2, ay + (ah - layout.TS_MD) // 2,
                        _sans(layout.TS_MD), fill=layout.PAPER)

            # Deny button
            dx, dy, dw, dh = layout.DENY_ZONE
            self._rect(dx, dy, dw, dh, outline=layout.INK)
            lbl = "Deny"
            lw = self._text_width(lbl, _sans(layout.TS_MD))
            self._text(lbl, dx + (dw - lw) // 2, dy + (dh - layout.TS_MD) // 2,
                        _sans(layout.TS_MD), fill=layout.INK)

        # Countdown timer (top-right, darkens below 10s)
        remaining = max(0, 30 - int(elapsed_s))
        timer_fill = layout.INK if remaining <= 10 else layout.INK_DIM
        self._text(f"{remaining}s", layout.W - P, Y + layout.CARD_TITLE_Y,
                   _sans(layout.TS_LG), fill=timer_fill, anchor="ra")

        self._push()


# ── Development preview entrypoint ───────────────────────────────────────────

if __name__ == "__main__":
    import state as st

    demo = st.KindleState(
        sessions_total=3,
        sessions_running=2,
        sessions_waiting=1,
        project="claude-buddy",
        branch="main",
        dirty=2,
        model_name="Claude Sonnet 4.6",
        budget_limit=200000,
        tokens_today=45000,
        assistant_msg="I'll refactor the transport layer to support both TCP and serial simultaneously.",
        lines=[
            "12:01 Read file src/transport.py",
            "12:02 Edit file src/transport.py",
            "12:03 Bash: python3 -m pytest tests/",
            "12:04 All tests passed (14 passed)",
        ],
    )

    r = Renderer()
    r.draw_dashboard(demo)
    if not _FBINK_AVAILABLE:
        import shutil
        shutil.copy("preview.png", "preview_dashboard.png")
    print("Dashboard → preview_dashboard.png")

    demo.prompt_tool = "Bash"
    demo.prompt_kind = "permission"
    demo.prompt_hint = "rm -rf /tmp/build && make clean"
    demo.prompt_body = "$ rm -rf /tmp/build\n$ make clean\nremoving 1234 files…"
    r.draw_approval_card(demo, elapsed_s=8)
    if not _FBINK_AVAILABLE:
        import shutil
        shutil.copy("preview.png", "preview_card.png")
    print("Approval card → preview_card.png")
