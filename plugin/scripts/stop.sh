#!/usr/bin/env bash
# Stop the bridge daemon.

set -euo pipefail
SELF_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source "$SELF_DIR/common.sh"

if ! is_running; then
  echo "daemon is not running"
  rm -f "$PID_FILE"
  exit 0
fi

PID=$(cat "$PID_FILE")
kill "$PID"
rm -f "$PID_FILE"
echo "daemon stopped (pid $PID)"
