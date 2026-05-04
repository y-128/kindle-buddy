#!/bin/sh
# Claude Buddy process manager for Kindle (sy69jl + WinterBreak target).

set -u

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
BUDDY_DIR="${BUDDY_DIR:-/mnt/us/buddy}"
APP_DIR="$BUDDY_DIR/app"
PID_FILE="$BUDDY_DIR/buddy.pid"
LOG_FILE="$BUDDY_DIR/buddy.log"
TRANSPORT="${BUDDY_TRANSPORT:-wifi}"
TCP_PORT="${BUDDY_TCP_PORT:-9877}"
LOG_LEVEL="${BUDDY_LOG_LEVEL:-DEBUG}"

find_python() {
    for p in \
        /usr/local/bin/python3 \
        /usr/bin/python3 \
        /mnt/us/extensions/python/bin/python3
    do
        if [ -x "$p" ]; then
            echo "$p"
            return 0
        fi
    done
    if command -v python3 >/dev/null 2>&1; then
        command -v python3
        return 0
    fi
    return 1
}

is_running() {
    if [ -f "$PID_FILE" ]; then
        pid="$(cat "$PID_FILE" 2>/dev/null)"
        [ -n "${pid:-}" ] && kill -0 "$pid" 2>/dev/null
        return $?
    fi
    return 1
}

ensure_runtime_dir() {
    mkdir -p "$BUDDY_DIR"
    : > "$LOG_FILE" 2>/dev/null || true
}

preflight() {
    if [ ! -d "$APP_DIR" ]; then
        echo "app dir missing: $APP_DIR"
        return 1
    fi
    if [ ! -f "$APP_DIR/buddy.py" ]; then
        echo "entrypoint missing: $APP_DIR/buddy.py"
        return 1
    fi
    if ! PYTHON_BIN="$(find_python)"; then
        echo "python3 not found"
        return 1
    fi
    echo "python: $PYTHON_BIN"
    return 0
}

start_buddy() {
    if is_running; then
        echo "already running (pid $(cat "$PID_FILE"))"
        return 0
    fi

    ensure_runtime_dir
    if ! preflight >> "$LOG_FILE" 2>&1; then
        echo "preflight failed, see $LOG_FILE"
        return 1
    fi

    lipc-set-prop com.lab126.cmd wirelessEnable 1 >/dev/null 2>&1 || true
    lipc-set-prop com.lab126.powerd preventScreenSaver 1 >/dev/null 2>&1 || true

    (
        cd "$APP_DIR" || exit 1
        nohup "$PYTHON_BIN" "$APP_DIR/buddy.py" \
            --transport "$TRANSPORT" \
            --tcp-port "$TCP_PORT" \
            --log-level "$LOG_LEVEL" \
            >> "$LOG_FILE" 2>&1 &
        echo $! > "$PID_FILE"
    )

    sleep 2
    if is_running; then
        echo "started (pid $(cat "$PID_FILE"))"
        return 0
    fi

    echo "start failed, last log:"
    tail -n 30 "$LOG_FILE" 2>/dev/null || true
    rm -f "$PID_FILE"
    return 1
}

stop_buddy() {
    if is_running; then
        pid="$(cat "$PID_FILE")"
        kill "$pid" >/dev/null 2>&1 || true
        sleep 1
        if kill -0 "$pid" 2>/dev/null; then
            kill -9 "$pid" >/dev/null 2>&1 || true
        fi
        echo "stopped (pid $pid)"
    else
        echo "not running"
    fi
    rm -f "$PID_FILE"
    lipc-set-prop com.lab126.powerd preventScreenSaver 0 >/dev/null 2>&1 || true
}

status_buddy() {
    if is_running; then
        echo "running (pid $(cat "$PID_FILE"))"
    else
        echo "stopped"
    fi
    echo "log: $LOG_FILE"
}

case "${1:-}" in
    start)  start_buddy ;;
    stop)   stop_buddy ;;
    status) status_buddy ;;
    restart)
        stop_buddy
        start_buddy
        ;;
    *)
        echo "usage: $0 {start|stop|status|restart}"
        exit 1
        ;;
esac
