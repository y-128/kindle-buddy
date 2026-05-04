"""ASCII buddy art — single representative frame per state.

Ported from src/paper/buddy_frames.h.  Each value is a tuple of 5 strings
(rows), all 12 chars wide so the block is monospace-symmetric.
"""

from dataclasses import dataclass
from typing import Tuple

Frame = Tuple[str, ...]   # 5-line block

# ── Cat frames ────────────────────────────────────────────────────────────────

SLEEP = (
    "            ",
    "            ",
    "   .-..-.   ",
    "  ( -.- )   ",
    "  `------`~ ",
)

IDLE = (
    "            ",
    "   /\\_/\\    ",
    "  ( o   o ) ",
    "  (  w   )  ",
    "  (\")_(\")   ",
)

BUSY = (
    "      .     ",
    "   /\\_/\\    ",
    "  ( o   o ) ",
    "  (  w   )/ ",
    "  (\")_(\")   ",
)

ATTENTION = (
    "            ",
    "   /^_^\\    ",
    "  ( O   O ) ",
    "  (  v   )  ",
    "  (\")_(\")   ",
)

CELEBRATE = (
    "    \\o/     ",
    "   /\\_/\\    ",
    "  ( ^   ^ ) ",
    " /(  W   )\\ ",
    "  (\")_(\")   ",
)

DND = (
    "            ",
    "   /\\_/\\    ",
    "  ( -   - ) ",
    "  (  w   )  ",
    "  (\")_(\")   ",
)


def pick(running: int, waiting: int, recently_completed: bool,
         connected: bool, celebrate: bool, dnd: bool) -> Frame:
    """Select the appropriate frame for the current daemon state."""
    if dnd:
        return DND
    if celebrate:
        return CELEBRATE
    if not connected:
        return SLEEP
    if waiting > 0:
        return ATTENTION
    if running > 0:
        return BUSY
    if recently_completed:
        return CELEBRATE
    if running == 0 and waiting == 0:
        return IDLE
    return IDLE
