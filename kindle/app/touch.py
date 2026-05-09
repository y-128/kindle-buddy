from __future__ import annotations

"""Touch input via evdev — reads raw EV_ABS events from /dev/input/event*.

Provides:
  - TouchReader   : background thread that reads the touch panel
  - hit_test()    : maps a (x, y) tap to a named zone

K7/K8 have no physical page-turn buttons; all interaction is touch-only.
The raw panel coordinates may be swapped or scaled differently from the
framebuffer — calibrate once on first run and persist to /tmp/touch_cal.json.

Zone constants live in layout.py; hit_test() accepts zone tuples
(x, y, w, h) in **screen** coordinates.
"""

import json
import logging
import os
import fcntl
import struct
import threading
import time
from pathlib import Path
from typing import Callable

import layout

log = logging.getLogger(__name__)

TapCallback = Callable[[int, int], None]

# ── Calibration ───────────────────────────────────────────────────────────────

CAL_FILE = Path("/tmp/touch_cal.json")

_cal = {
    "x_min": 0, "x_max": layout.W,
    "y_min": 0, "y_max": layout.H,
    "swap_xy": False,
    "flip_x": False,
    "flip_y": False,
}


def load_calibration() -> None:
    """Load persisted calibration if available."""
    if CAL_FILE.exists():
        try:
            _cal.update(json.loads(CAL_FILE.read_text()))
            log.info("[touch] calibration loaded: %s", _cal)
        except Exception as e:
            log.warning("[touch] failed to load calibration: %s", e)


def save_calibration() -> None:
    CAL_FILE.write_text(json.dumps(_cal, indent=2))


def apply_calibration(raw_x: int, raw_y: int) -> tuple[int, int]:
    """Map raw panel coordinates → screen (0..W-1, 0..H-1)."""
    if _cal["swap_xy"]:
        raw_x, raw_y = raw_y, raw_x

    x_min, x_max = _cal["x_min"], _cal["x_max"]
    y_min, y_max = _cal["y_min"], _cal["y_max"]

    sx = int((raw_x - x_min) / max(1, x_max - x_min) * layout.W)
    sy = int((raw_y - y_min) / max(1, y_max - y_min) * layout.H)

    if _cal["flip_x"]:
        sx = layout.W - 1 - sx
    if _cal["flip_y"]:
        sy = layout.H - 1 - sy

    sx = max(0, min(layout.W - 1, sx))
    sy = max(0, min(layout.H - 1, sy))
    return sx, sy


# ── Evdev reader ──────────────────────────────────────────────────────────────

# Linux input_event struct: timeval (8 bytes on 64-bit) + type + code + value
# On 32-bit ARM (Kindle) timeval is 8 bytes (2×u32). struct format: I I H H i
_EVENT_FMT   = "IIHHi"
_EVENT_BYTES = struct.calcsize(_EVENT_FMT)

EV_SYN = 0
EV_ABS = 3
ABS_X  = 0
ABS_Y  = 1
ABS_MT_POSITION_X = 53
ABS_MT_POSITION_Y = 54
SYN_REPORT = 0

# Linux input EVIOCGRAB. While grabbed, touch events are delivered only to
# Buddy and do not pass through to the Kindle home/store UI underneath.
EVIOCGRAB = 0x40044590

TAP_DEBOUNCE_SEC = 0.45


def _find_touch_device() -> str | None:
    """Return the first event device that looks like a touchscreen."""
    base = Path("/dev/input")
    for dev in sorted(base.glob("event*")):
        name_path = Path(f"/sys/class/input/{dev.name}/device/name")
        if name_path.exists():
            name = name_path.read_text().strip().lower()
            if any(k in name for k in ("touch", "elan", "cyttsp", "imx-mxc", "zforce")):
                log.info("[touch] found device: %s (%s)", dev, name)
                return str(dev)
    # fall back to event0
    candidate = str(base / "event0")
    if os.path.exists(candidate):
        log.warning("[touch] using fallback %s", candidate)
        return candidate
    return None


class TouchReader:
    """Background thread that reads touch events and fires *on_tap* callbacks.

    on_tap(screen_x, screen_y) is called once per complete touch gesture
    (finger-down then finger-up, or SYN_REPORT after ABS position).
    """

    def __init__(self, on_tap: TapCallback, device: str | None = None):
        self._on_tap = on_tap
        self._device = device
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        load_calibration()
        if self._device is None:
            self._device = _find_touch_device()
        if self._device is None:
            log.error("[touch] no input device found — touch disabled")
            return
        self._thread = threading.Thread(
            target=self._read_loop,
            args=(self._device,),
            daemon=True,
            name="touch-reader",
        )
        self._thread.start()

    def _read_loop(self, path: str) -> None:
        log.info("[touch] reading %s", path)
        raw_x = raw_y = 0
        last_tap_at = 0.0
        while True:
            try:
                with open(path, "rb") as f:
                    try:
                        fcntl.ioctl(f.fileno(), EVIOCGRAB, 1)
                        log.info("[touch] grabbed %s", path)
                    except OSError as e:
                        log.warning("[touch] grab failed on %s: %s", path, e)
                    while True:
                        buf = f.read(_EVENT_BYTES)
                        if len(buf) < _EVENT_BYTES:
                            break
                        _, _, etype, code, value = struct.unpack(_EVENT_FMT, buf)
                        if etype == EV_ABS:
                            if code in (ABS_X, ABS_MT_POSITION_X):
                                raw_x = value
                            elif code in (ABS_Y, ABS_MT_POSITION_Y):
                                raw_y = value
                        elif etype == EV_SYN and code == SYN_REPORT:
                            sx, sy = apply_calibration(raw_x, raw_y)
                            now = time.monotonic()
                            if now - last_tap_at < TAP_DEBOUNCE_SEC:
                                continue
                            last_tap_at = now
                            log.debug("[touch] tap screen=(%d,%d) raw=(%d,%d)", sx, sy, raw_x, raw_y)
                            try:
                                self._on_tap(sx, sy)
                            except Exception:
                                log.exception("[touch] on_tap raised")
            except Exception as e:
                log.warning("[touch] read error on %s: %s — retrying", path, e)
                time.sleep(2)


# ── Hit-test ──────────────────────────────────────────────────────────────────

def hit_test(sx: int, sy: int, zones: dict[str, tuple[int, int, int, int]]) -> str | None:
    """Return the first zone name whose rect contains (sx, sy), or None.

    *zones* maps a name string to a (x, y, w, h) tuple in screen pixels.
    """
    for name, (zx, zy, zw, zh) in zones.items():
        if zx <= sx < zx + zw and zy <= sy < zy + zh:
            return name
    return None


def dashboard_zones(session_count: int = 0, scroll: int = 0) -> dict[str, tuple[int, int, int, int]]:
    zones: dict[str, tuple[int, int, int, int]] = {
        "exit": layout.EXIT_ZONE,
        "settings": layout.SETTINGS_ZONE,
        "dnd": layout.DND_TOGGLE_ZONE,
    }
    if scroll > 0:
        zones["session_scroll_up"] = layout.SESSION_SCROLL_UP_ZONE
    if scroll + layout.SESSION_VISIBLE < session_count:
        zones["session_scroll_down"] = layout.SESSION_SCROLL_DOWN_ZONE
    for i, z in enumerate(layout.session_row_zones(session_count, scroll)):
        zones[f"session:{scroll + i}"] = z
    return zones


def settings_zones() -> dict[str, tuple[int, int, int, int]]:
    return {
        "back": layout.BACK_ZONE,
        "exit": layout.EXIT_ZONE,
        "dnd": layout.DND_TOGGLE_ZONE,
        "full_refresh": layout.FULL_REFRESH_ZONE,
    }


def approval_zones(option_count: int = 0) -> dict[str, tuple[int, int, int, int]]:
    zones: dict[str, tuple[int, int, int, int]] = {
        "approve": layout.APPROVE_ZONE,
        "deny":    layout.DENY_ZONE,
    }
    for i, z in enumerate(layout.question_option_zones(option_count)):
        zones[f"option:{i}"] = z
    return zones
