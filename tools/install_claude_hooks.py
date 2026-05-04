#!/usr/bin/env python3
"""Merge claude-buddy hook commands into Claude Code settings."""

from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path


def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    src = repo / "plugin" / "settings" / "hooks.json"
    dst = Path.home() / ".claude" / "settings.json"

    payload = json.loads(src.read_text())
    hooks = payload.get("hooks")
    if not isinstance(hooks, dict):
        print(f"hooks missing in {src}", file=sys.stderr)
        return 2

    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        settings = json.loads(dst.read_text() or "{}")
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = dst.with_suffix(f".json.bak-{stamp}")
        shutil.copy2(dst, backup)
        print(f"backup: {backup}")
    else:
        settings = {}

    existing = settings.get("hooks")
    if existing is not None and not isinstance(existing, dict):
        print("settings.hooks exists but is not an object", file=sys.stderr)
        return 2

    settings["hooks"] = hooks
    dst.write_text(json.dumps(settings, indent=2, ensure_ascii=False) + "\n")
    print(f"installed hooks: {dst}")
    print("restart Claude Code sessions for hooks to take effect")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
