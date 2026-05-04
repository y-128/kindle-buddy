#!/usr/bin/env bash
# Start the bridge with a readable process title for Activity Monitor/ps.

set -euo pipefail

PYTHON_BIN="${BUDDY_PYTHON:-$(command -v python3)}"
exec -a "Pepper Buddy Bridge" "$PYTHON_BIN" "$@"
