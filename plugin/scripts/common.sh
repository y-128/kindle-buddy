#!/usr/bin/env bash
# Shared helpers for the Kindle Buddy plugin scripts.

set -euo pipefail

PLUGIN_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
REPO_ROOT="$( cd "$PLUGIN_DIR/.." && pwd )"
STATE_DIR="$HOME/.claude-buddy"
PID_FILE="$STATE_DIR/daemon.pid"
LOG_FILE="$STATE_DIR/daemon.log"
DAEMON="$REPO_ROOT/tools/claude_code_bridge.py"

mkdir -p "$STATE_DIR"

pick_python() {
  if [ -n "${BUDDY_PYTHON:-}" ] && [ -x "${BUDDY_PYTHON}" ]; then
    echo "$BUDDY_PYTHON"; return
  fi
  # PlatformIO embedded Python (has pyserial)
  for p in /opt/homebrew/Cellar/platformio/*/libexec/bin/python \
            /home/linuxbrew/.linuxbrew/Cellar/platformio/*/libexec/bin/python; do
    if [ -x "$p" ]; then echo "$p"; return; fi
  done
  if command -v python3 >/dev/null 2>&1; then echo "$(command -v python3)"; return; fi
  echo ""; return 1
}

PY="$(pick_python || true)"

need_python() {
  if [ -z "$PY" ]; then
    echo "error: no suitable Python found." >&2
    echo "install PlatformIO (brew install platformio) or set BUDDY_PYTHON." >&2
    exit 1
  fi
}

is_running() {
  [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null
}

find_serial() {
  ls /dev/cu.usbserial-* /dev/ttyUSB* 2>/dev/null | head -n1 || true
}
