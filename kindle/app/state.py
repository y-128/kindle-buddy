from __future__ import annotations

"""KindleState — Python equivalent of data_paper.h's TamaState.

Parses the JSON line-protocol sent by claude_code_bridge.py (unchanged from
the M5Paper protocol) and stores it in a plain dataclass so display.py can
read it without locks.  All mutation happens inside update_from_json() which
is called from transport.py's reader thread while holding _LOCK.
"""

import json
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

_LOCK = threading.Lock()


@dataclass
class SessionRow:
    sid:     str = ""
    full:    str = ""
    project: str = ""
    branch:  str = ""
    dirty:   int = 0
    running: bool = False
    waiting: bool = False
    focused: bool = False


@dataclass
class PendingTab:
    id:      str = ""
    tool:    str = ""
    project: str = ""


@dataclass
class KindleState:
    sessions_total:    int  = 0
    sessions_running:  int  = 0
    sessions_waiting:  int  = 0
    recently_completed: bool = False
    tokens_today:      int  = 0
    last_updated:      float = 0.0
    msg:               str  = ""
    connected:         bool = False
    owner:             str  = ""
    approved_count:    int  = 0
    denied_count:      int  = 0

    lines:     list[str]  = field(default_factory=list)   # up to 8 transcript lines
    line_gen:  int        = 0

    prompt_id:      str = ""
    prompt_tool:    str = ""
    prompt_hint:    str = ""
    prompt_kind:    str = ""   # "permission" | "question"
    prompt_body:    str = ""
    prompt_options: list[str] = field(default_factory=list)
    prompt_project: str = ""
    prompt_sid:     str = ""

    project:       str  = ""
    branch:        str  = ""
    dirty:         int  = 0
    budget_limit:  int  = 0
    model_name:    str  = ""
    assistant_msg: str  = ""
    assistant_gen: int  = 0

    session_rows:  list[SessionRow]  = field(default_factory=list)
    session_count: int               = 0
    session_gen:   int               = 0

    pending_tabs:  list[PendingTab]  = field(default_factory=list)
    pending_count: int               = 0

    # Internal: timestamp of last JSON frame received from daemon
    _last_live: float = field(default=0.0, repr=False)


# Module-level singleton shared between transport thread and display thread.
STATE = KindleState()


def update_from_json(line: str) -> None:
    """Parse a JSON line from the bridge daemon and update STATE in place.

    Called from the transport reader thread; acquires _LOCK for the write.
    """
    try:
        doc = json.loads(line)
    except json.JSONDecodeError:
        return

    with _LOCK:
        s = STATE
        s._last_live = time.monotonic()
        s.connected  = True

        if doc.get("cmd") == "owner":
            s.owner = str(doc.get("name", ""))[:32]
            s.last_updated = time.time()
            return

        s.sessions_total     = doc.get("total",     s.sessions_total)
        s.sessions_running   = doc.get("running",   s.sessions_running)
        s.sessions_waiting   = doc.get("waiting",   s.sessions_waiting)
        s.approved_count     = int(doc.get("approved", s.approved_count))
        s.denied_count       = int(doc.get("denied",   s.denied_count))
        s.recently_completed = doc.get("completed", False)
        if "tokens_today" in doc:
            s.tokens_today = doc["tokens_today"]
        if "msg" in doc:
            s.msg = doc["msg"][:80]

        entries = doc.get("entries")
        if entries is not None:
            new_lines = [str(e)[:91] for e in entries[:8]]
            if new_lines != s.lines:
                s.line_gen += 1
                s.lines = new_lines

        prompt = doc.get("prompt")
        if prompt is not None:
            s.prompt_id      = prompt.get("id",   "")
            s.prompt_tool    = prompt.get("tool", "")
            s.prompt_hint    = prompt.get("hint", "")
            s.prompt_body    = prompt.get("body", "")
            s.prompt_kind    = prompt.get("kind", "permission")
            opts = prompt.get("options") or []
            s.prompt_options = [str(o)[:48] for o in opts[:4]]
            s.prompt_project = prompt.get("project", "")
            s.prompt_sid     = prompt.get("sid",     "")
        else:
            s.prompt_id = s.prompt_tool = s.prompt_hint = ""
            s.prompt_body = s.prompt_kind = ""
            s.prompt_options = []
            s.prompt_project = s.prompt_sid = ""

        pending = doc.get("pending")
        if pending is not None:
            s.pending_tabs = [
                PendingTab(
                    id=p.get("id",""),
                    tool=p.get("tool",""),
                    project=p.get("project",""),
                )
                for p in pending[:4]
            ]
            s.pending_count = len(s.pending_tabs)

        if "project" in doc:
            s.project = doc["project"]
        if "branch" in doc:
            s.branch = doc["branch"]
        if "dirty" in doc:
            s.dirty = int(doc["dirty"])
        if "budget" in doc:
            s.budget_limit = int(doc["budget"])
        if "model" in doc:
            s.model_name = str(doc["model"])[:32]
        if "assistant_msg" in doc:
            new_am = str(doc["assistant_msg"])[:240]
            if new_am != s.assistant_msg:
                s.assistant_msg = new_am
                s.assistant_gen += 1

        sessions = doc.get("sessions")
        if sessions is not None:
            rows = []
            for r in sessions[:5]:
                rows.append(SessionRow(
                    sid     = r.get("sid",     ""),
                    full    = r.get("full",    ""),
                    project = r.get("project") or r.get("proj", ""),
                    branch  = r.get("branch",  ""),
                    dirty   = int(r.get("dirty", 0)),
                    running = bool(r.get("running", False)),
                    waiting = bool(r.get("waiting", False)),
                    focused = bool(r.get("focused", False)),
                ))
            if rows != s.session_rows:
                s.session_gen += 1
            s.session_rows  = rows
            s.session_count = len(rows)

        s.last_updated = time.time()


def is_connected() -> bool:
    """Return True if a JSON frame has been received within the last 30 s."""
    with _LOCK:
        return STATE._last_live > 0 and (time.monotonic() - STATE._last_live) <= 30.0


def snapshot() -> KindleState:
    """Return a shallow copy of STATE so display.py can read without a lock."""
    with _LOCK:
        import copy
        return copy.copy(STATE)
