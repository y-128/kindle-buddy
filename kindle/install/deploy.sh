#!/usr/bin/env bash
# Deploy Kindle app + KUAL extension over WiFi SSH.
#
# Usage:
#   bash kindle/install/deploy.sh
#   KINDLE_HOST=root@<Kindle WiFi IP> bash kindle/install/deploy.sh
#
# Prerequisites on the Kindle:
#   - USBNetwork WiFi SSH enabled
#   - Python 3 + Pillow + pyfbink installed
#   - /mnt/us writable

set -euo pipefail

KINDLE_HOST="${KINDLE_HOST:-kindle-buddy}"
REMOTE_DIR="${REMOTE_DIR:-/mnt/us/buddy}"

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
APP_DIR="$SCRIPT_DIR/../app"
KUAL_DIR="$SCRIPT_DIR/../kual-extension"

# KUAL extension install dir on Kindle
KUAL_EXT_PARENT="/mnt/us/extensions"
KUAL_EXT_NAME="ClaudeBuddy"
KUAL_EXT_DIR="$KUAL_EXT_PARENT/$KUAL_EXT_NAME"

echo "Deploying to $KINDLE_HOST"

# Create remote directories
ssh "$KINDLE_HOST" "mkdir -p '$REMOTE_DIR/app' '$REMOTE_DIR/kual-extension' '$KUAL_EXT_DIR'"

# Copy app/
scp -r "$APP_DIR"/. "$KINDLE_HOST:$REMOTE_DIR/app/"

# Copy KUAL extension into buddy backup dir and the directory KUAL scans.
scp -r "$KUAL_DIR"/. "$KINDLE_HOST:$REMOTE_DIR/kual-extension/"
scp -r "$KUAL_DIR"/. "$KINDLE_HOST:$KUAL_EXT_DIR/"

ssh "$KINDLE_HOST" "chmod +x '$REMOTE_DIR/app/buddy.py' '$REMOTE_DIR/kual-extension/start.sh' '$REMOTE_DIR/kual-extension/stop.sh' '$REMOTE_DIR/kual-extension/buddyctl.sh' '$KUAL_EXT_DIR/start.sh' '$KUAL_EXT_DIR/stop.sh' '$KUAL_EXT_DIR/buddyctl.sh'"

echo ""
echo "Deploy complete."
echo ""
echo "On Kindle: KUAL → Claude Buddy → Start Buddy"
echo "Or via SSH: sh $REMOTE_DIR/kual-extension/start.sh"
echo ""
echo "Tail log: ssh $KINDLE_HOST 'tail -f $REMOTE_DIR/buddy.log'"
