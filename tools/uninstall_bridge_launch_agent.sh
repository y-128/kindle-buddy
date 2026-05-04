#!/usr/bin/env bash
# Remove the macOS LaunchAgent for the claude-buddy bridge.

set -euo pipefail

LABELS=("com.kindle-buddy.bridge" "com.pepper-buddy.bridge" "com.claude-buddy.bridge")

for label in "${LABELS[@]}"; do
  plist="$HOME/Library/LaunchAgents/$label.plist"
  launchctl bootout "gui/$(id -u)" "$plist" >/dev/null 2>&1 || true
  rm -f "$plist"
  echo "removed: $plist"
done
