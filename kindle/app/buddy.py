#!/usr/bin/env python3
from __future__ import annotations
"""buddy.py — main event loop for the Kindle Claude Code companion.

Equivalent to src/paper/main.cpp.

Architecture
------------
  transport thread  → state.update_from_json() → STATE
  touch thread      → on_tap() → action (send ack JSON / toggle DND)
  main loop         → polls STATE, calls display.draw_*() when something changed

Startup
-------
  /usr/local/bin/python3 /mnt/us/buddy/app/buddy.py [options]

Options
-------
  --transport   auto|wifi|serial|both  (default: auto)
  --tcp-port    9877
  --serial-path /dev/ttyGS0
  --touch-dev   /dev/input/event1
  --log-level   DEBUG|INFO|WARNING
"""

import argparse
import json
import logging
import sys
import time
import threading

import state
import transport as transport_mod
import display as display_mod
import touch
import layout


# ─── globals ──────────────────────────────────────────────────────────────────

TRANSPORT: transport_mod.Transport | None = None
RENDERER:  display_mod.Renderer | None = None

DND_MODE     = False
SETTINGS_MODE = False
EXIT_REQUESTED = False
FULL_REFRESH_REQUESTED = False
SETTINGS_NOTICE_UNTIL: float = 0.0
CELEBRATE_UNTIL: float = 0.0

FULL_REFRESH_INTERVAL = 120  # seconds between forced GC16 refresh

# track render triggers
_last_line_gen      = -1
_last_assistant_gen = -1
_last_session_gen   = -1
_last_prompt_id     = ""
_last_connected     = False
_last_dnd_mode      = False
_last_settings_mode = False
_last_settings_notice = False

log = logging.getLogger("buddy")
_last_rx_summary = ""
_last_render_summary = ""


# ─── send helpers ─────────────────────────────────────────────────────────────

def _send(obj: dict) -> None:
    if TRANSPORT and TRANSPORT.connected():
        TRANSPORT.write((json.dumps(obj) + "\n").encode())


def _ack(prompt_id: str, decision: str) -> None:
    """Send a permission/question decision back to the Mac bridge."""
    _send({"cmd": "permission", "id": prompt_id, "ack": prompt_id, "decision": decision})
    log.info("[ack] %s -> %s", prompt_id, decision)


# ─── touch handler ────────────────────────────────────────────────────────────

def on_tap(sx: int, sy: int) -> None:
    global DND_MODE, SETTINGS_MODE, EXIT_REQUESTED, FULL_REFRESH_REQUESTED, SETTINGS_NOTICE_UNTIL, CELEBRATE_UNTIL

    s = state.snapshot()

    if s.prompt_id and SETTINGS_MODE:
        SETTINGS_MODE = False
        log.info("[settings] closed by prompt")

    if SETTINGS_MODE:
        action = touch.hit_test(sx, sy, touch.settings_zones())
        log.debug("[settings] tap action=%s at %d,%d", action, sx, sy)
        if action == "back":
            SETTINGS_MODE = False
            log.info("[settings] back")
        elif action == "exit":
            EXIT_REQUESTED = True
            log.info("[exit] requested from settings")
        elif action == "dnd":
            DND_MODE = not DND_MODE
            log.info("[dnd] mode=%s", DND_MODE)
        elif action == "full_refresh":
            FULL_REFRESH_REQUESTED = True
            log.info("[display] full refresh requested")
        _request_redraw()
        return

    if s.prompt_id:
        # We are on the approval/question card
        zones = touch.approval_zones(len(s.prompt_options))
        action = touch.hit_test(sx, sy, zones)
        if action == "approve":
            _ack(s.prompt_id, "once")
            CELEBRATE_UNTIL = time.monotonic() + 1.5
        elif action == "deny":
            _ack(s.prompt_id, "deny")
            CELEBRATE_UNTIL = time.monotonic() + 1.5
        elif action and action.startswith("option:"):
            _ack(s.prompt_id, action)
            CELEBRATE_UNTIL = time.monotonic() + 1.5
    else:
        # Dashboard touch
        zones = touch.dashboard_zones(len(s.session_rows))
        action = touch.hit_test(sx, sy, zones)
        if action == "settings":
            SETTINGS_MODE = True
            log.info("[settings] open")
        elif action == "exit":
            EXIT_REQUESTED = True
            log.info("[exit] requested from dashboard")
        elif action == "dnd":
            DND_MODE = not DND_MODE
            log.info("[dnd] mode=%s", DND_MODE)
            if DND_MODE and s.prompt_id:
                _ack(s.prompt_id, "once")
        elif action and action.startswith("session:"):
            idx = int(action.split(":", 1)[1])
            if 0 <= idx < len(s.session_rows):
                row = s.session_rows[idx]
                sid = row.full or row.sid
                _send({"cmd": "focus_session", "sid": sid})
                log.info("[session] focus %s", row.sid)

    _request_redraw()


# ─── redraw signalling ────────────────────────────────────────────────────────

_redraw_event = threading.Event()


def _request_redraw() -> None:
    _redraw_event.set()


# ─── render loop ──────────────────────────────────────────────────────────────

def render_loop() -> None:
    global _last_line_gen, _last_assistant_gen, _last_session_gen, _last_prompt_id, _last_connected, _last_dnd_mode, _last_settings_mode, _last_settings_notice, _last_render_summary, FULL_REFRESH_REQUESTED

    last_full = time.monotonic()

    while True:
        if EXIT_REQUESTED:
            if RENDERER:
                RENDERER.draw_exit_screen()
            log.info("[exit] bye")
            return

        # Tight polling during approval card for countdown timer
        _redraw_event.wait(timeout=1.0 if _last_prompt_id else 2.0)
        _redraw_event.clear()

        if EXIT_REQUESTED:
            continue

        s = state.snapshot()
        now = time.monotonic()
        notice_active = now < SETTINGS_NOTICE_UNTIL

        # Detect changes
        changed = (
            s.line_gen      != _last_line_gen
            or s.assistant_gen != _last_assistant_gen
            or s.session_gen   != _last_session_gen
            or s.prompt_id     != _last_prompt_id
            or state.is_connected() != _last_connected
            or DND_MODE        != _last_dnd_mode
            or SETTINGS_MODE   != _last_settings_mode
            or notice_active   != _last_settings_notice
            or FULL_REFRESH_REQUESTED
        )

        force_full = (now - last_full) >= FULL_REFRESH_INTERVAL
        # Always redraw during approval card so countdown timer ticks
        force_redraw = bool(s.prompt_id)

        if not changed and not force_full and not force_redraw:
            continue

        _last_line_gen      = s.line_gen
        _last_assistant_gen = s.assistant_gen
        _last_session_gen   = s.session_gen
        _last_prompt_id     = s.prompt_id
        _last_connected     = state.is_connected()
        _last_dnd_mode      = DND_MODE
        _last_settings_mode = SETTINGS_MODE
        _last_settings_notice = notice_active

        if force_full:
            last_full = now

        celebrate = time.monotonic() < CELEBRATE_UNTIL

        try:
            if SETTINGS_MODE:
                log.debug("[render] settings dnd=%s", DND_MODE)
                notice = "Refreshing..." if notice_active else ""
                if FULL_REFRESH_REQUESTED:
                    RENDERER.black_white_flash()
                    time.sleep(0.25)
                RENDERER.draw_settings(s, dnd=DND_MODE, notice=notice, full=FULL_REFRESH_REQUESTED)
                FULL_REFRESH_REQUESTED = False
            elif s.prompt_id:
                elapsed = time.monotonic() - _prompt_arrived.get(s.prompt_id, now)
                log.debug("[render] approval prompt=%s tool=%s", s.prompt_id, s.prompt_tool)
                RENDERER.draw_approval_card(s, elapsed_s=elapsed)
                if DND_MODE:
                    # Auto-approve in DND after short delay
                    threading.Timer(0.6, lambda pid=s.prompt_id: _ack(pid, "once")).start()
            else:
                render_summary = (
                    f"dashboard total={s.sessions_total} running={s.sessions_running} "
                    f"waiting={s.sessions_waiting} lines={len(s.lines)} dnd={DND_MODE}"
                )
                if render_summary != _last_render_summary:
                    log.info("[render] %s", render_summary)
                    _last_render_summary = render_summary
                log.debug(
                    "[render] dashboard total=%d running=%d waiting=%d lines=%d dnd=%s",
                    s.sessions_total,
                    s.sessions_running,
                    s.sessions_waiting,
                    len(s.lines),
                    DND_MODE,
                )
                RENDERER.draw_dashboard(s, celebrate=celebrate, dnd=DND_MODE)
        except Exception:
            log.exception("[render] draw raised")


_prompt_arrived: dict[str, float] = {}


def on_line(line: str) -> None:
    """Called by the transport reader thread on each JSON line."""
    global SETTINGS_MODE, _last_rx_summary
    log.debug("[rx] %s", line[:500])
    state.update_from_json(line)
    s = state.snapshot()
    rx_summary = (
        f"total={s.sessions_total} running={s.sessions_running} "
        f"waiting={s.sessions_waiting} lines={len(s.lines)} prompt={bool(s.prompt_id)}"
    )
    if rx_summary != _last_rx_summary:
        log.info("[rx] %s", rx_summary)
        _last_rx_summary = rx_summary
    if s.prompt_id and SETTINGS_MODE:
        SETTINGS_MODE = False
        log.info("[settings] closed by incoming prompt")
    # Track when the current prompt first arrived
    if s.prompt_id and s.prompt_id not in _prompt_arrived:
        _prompt_arrived[s.prompt_id] = time.monotonic()
        # Prune stale entries
        for old in list(_prompt_arrived):
            if old != s.prompt_id:
                _prompt_arrived.pop(old, None)
    _request_redraw()


# ─── main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    global TRANSPORT, RENDERER

    ap = argparse.ArgumentParser(description="Kindle Claude Code companion")
    ap.add_argument("--transport",   default="auto",
                    choices=("auto", "wifi", "serial", "both"))
    ap.add_argument("--tcp-port",    type=int, default=9877)
    ap.add_argument("--serial-path", default="/dev/ttyGS0")
    ap.add_argument("--touch-dev",   default=None, help="evdev path (auto-detect if omitted)")
    ap.add_argument("--log-level",   default="INFO",
                    choices=("DEBUG", "INFO", "WARNING", "ERROR"))
    args = ap.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )

    log.info("buddy starting — transport=%s tcp-port=%d", args.transport, args.tcp_port)

    # Display
    RENDERER = display_mod.Renderer()

    # Transport
    TRANSPORT = transport_mod.build_transport(
        mode=args.transport,
        serial_path=args.serial_path,
        tcp_port=args.tcp_port,
    )
    TRANSPORT.start(on_line=on_line)

    # Touch
    reader = touch.TouchReader(on_tap=on_tap, device=args.touch_dev)
    reader.start()

    # Render loop on main thread
    log.info("buddy ready")
    _request_redraw()
    render_loop()


if __name__ == "__main__":
    main()
