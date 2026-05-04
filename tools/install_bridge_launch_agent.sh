#!/usr/bin/env bash
# Install a macOS LaunchAgent that starts the claude-buddy bridge on login.
#
# Usage:
#   tools/install_bridge_launch_agent.sh 192.168.179.56
#   tools/install_bridge_launch_agent.sh 192.168.179.56 9876

set -euo pipefail

KINDLE_IP="${1:-${KINDLE_IP:-}}"
HTTP_PORT="${2:-${BUDDY_HTTP_PORT:-9876}}"
KINDLE_PORT="${KINDLE_PORT:-9877}"

if [ -z "$KINDLE_IP" ]; then
  echo "usage: $0 KINDLE_IP [HTTP_PORT]" >&2
  exit 2
fi

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REPO_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
STATE_DIR="$HOME/.claude-buddy"
PLIST_DIR="$HOME/Library/LaunchAgents"
LABEL="com.kindle-buddy.bridge"
OLD_LABELS=("com.pepper-buddy.bridge" "com.claude-buddy.bridge")
PLIST="$PLIST_DIR/$LABEL.plist"
mkdir -p "$STATE_DIR" "$PLIST_DIR"

cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LABEL</string>
  <key>WorkingDirectory</key>
  <string>$REPO_ROOT</string>
  <key>ProgramArguments</key>
  <array>
    <string>$REPO_ROOT/tools/run_bridge_named.sh</string>
    <string>$REPO_ROOT/tools/claude_code_bridge.py</string>
    <string>--transport</string>
    <string>tcp</string>
    <string>--kindle-ip</string>
    <string>$KINDLE_IP</string>
    <string>--kindle-port</string>
    <string>$KINDLE_PORT</string>
    <string>--http-port</string>
    <string>$HTTP_PORT</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>$STATE_DIR/launchd.out.log</string>
  <key>StandardErrorPath</key>
  <string>$STATE_DIR/launchd.err.log</string>
</dict>
</plist>
PLIST

for old in "${OLD_LABELS[@]}"; do
  old_plist="$PLIST_DIR/$old.plist"
  launchctl bootout "gui/$(id -u)" "$old_plist" >/dev/null 2>&1 || true
  rm -f "$old_plist"
done
launchctl bootout "gui/$(id -u)" "$PLIST" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
launchctl kickstart -k "gui/$(id -u)/$LABEL"

echo "installed: $PLIST"
echo "bridge: tcp -> $KINDLE_IP:$KINDLE_PORT, http -> 127.0.0.1:$HTTP_PORT"
echo "logs: $STATE_DIR/launchd.err.log"
