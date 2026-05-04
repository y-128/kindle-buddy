#!/usr/bin/env bash
# Start the Kindle Buddy bridge daemon in the background.
#
# Config via env vars:
#   BUDDY_TRANSPORT   auto|serial|tcp  (default: auto)
#   BUDDY_BUDGET      daily token budget (default: 200000; 0 = hide)
#   BUDDY_OWNER       override $USER as displayed owner name
#   BUDDY_HTTP_PORT   HTTP listener port (default: 9876)
#   KINDLE_IP         Kindle WiFi IP (default: 192.168.15.244)
#   KINDLE_PORT       Kindle TCP port (default: 9877)

set -euo pipefail
SELF_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
# shellcheck source=common.sh
source "$SELF_DIR/common.sh"

if is_running; then
  echo "daemon already running (pid $(cat "$PID_FILE"))"
  exit 0
fi

need_python

TRANSPORT="${BUDDY_TRANSPORT:-auto}"
BUDGET="${BUDDY_BUDGET:-200000}"
OWNER="${BUDDY_OWNER:-$USER}"
HTTP_PORT="${BUDDY_HTTP_PORT:-9876}"
KINDLE_IP="${KINDLE_IP:-192.168.15.244}"
KINDLE_PORT="${KINDLE_PORT:-9877}"

nohup "$PY" "$DAEMON" \
  --transport    "$TRANSPORT" \
  --budget       "$BUDGET" \
  --owner        "$OWNER" \
  --http-port    "$HTTP_PORT" \
  --kindle-ip    "$KINDLE_IP" \
  --kindle-port  "$KINDLE_PORT" \
  >> "$LOG_FILE" 2>&1 &
echo $! > "$PID_FILE"

sleep 0.5
if is_running; then
  echo "daemon started (pid $(cat "$PID_FILE"))  transport=$TRANSPORT  kindle=$KINDLE_IP:$KINDLE_PORT"
  echo "log: $LOG_FILE"
else
  echo "daemon failed to start — check $LOG_FILE"
  tail -n 20 "$LOG_FILE" || true
  exit 1
fi
