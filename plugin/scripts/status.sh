#!/usr/bin/env bash
# Show daemon status.

set -euo pipefail
SELF_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source "$SELF_DIR/common.sh"

if is_running; then
  echo "daemon running (pid $(cat "$PID_FILE"))"
  echo "log: $LOG_FILE"
  echo ""
  tail -n 10 "$LOG_FILE" 2>/dev/null || true
else
  echo "daemon is not running"
fi
