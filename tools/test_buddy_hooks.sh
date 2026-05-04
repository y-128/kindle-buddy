#!/usr/bin/env bash
# Send synthetic Claude Code hook events to the local claude-buddy bridge.
#
# Usage:
#   bash tools/test_buddy_hooks.sh dashboard
#   bash tools/test_buddy_hooks.sh approval
#   bash tools/test_buddy_hooks.sh question
#
# Env:
#   BUDDY_HTTP_PORT=9878

set -euo pipefail

MODE="${1:-dashboard}"
PORT="${BUDDY_HTTP_PORT:-9878}"
URL="http://127.0.0.1:${PORT}/"
SID="test-session-$(date +%s)"
CWD="$(pwd)"

post() {
  curl -fsS -X POST "$URL" \
    -H 'Content-Type: application/json' \
    --data-binary @-
  printf '\n'
}

session_start() {
  post <<JSON
{
  "hook_event_name": "SessionStart",
  "session_id": "$SID",
  "cwd": "$CWD"
}
JSON
}

user_prompt() {
  post <<JSON
{
  "hook_event_name": "UserPromptSubmit",
  "session_id": "$SID",
  "cwd": "$CWD",
  "prompt": "Synthetic claude-buddy test: show activity on Kindle"
}
JSON
}

post_tool() {
  post <<JSON
{
  "hook_event_name": "PostToolUse",
  "session_id": "$SID",
  "cwd": "$CWD",
  "tool_name": "Read"
}
JSON
}

approval_prompt() {
  post <<JSON
{
  "hook_event_name": "PreToolUse",
  "session_id": "$SID",
  "cwd": "$CWD",
  "tool_name": "Bash",
  "tool_input": {
    "command": "echo claude-buddy approval test",
    "description": "Synthetic permission card test"
  }
}
JSON
}

question_prompt() {
  post <<JSON
{
  "hook_event_name": "PreToolUse",
  "session_id": "$SID",
  "cwd": "$CWD",
  "tool_name": "AskUserQuestion",
  "tool_input": {
    "questions": [
      {
        "question": "Which test path should claude-buddy show?",
        "options": [
          {"label": "Dashboard"},
          {"label": "Approval"},
          {"label": "Question"}
        ]
      }
    ]
  }
}
JSON
}

echo "Posting synthetic hooks to $URL"

case "$MODE" in
  dashboard)
    session_start
    user_prompt
    post_tool
    echo "Dashboard test sent."
    ;;
  approval)
    session_start
    user_prompt
    echo "Approval card sent. Tap Approve or Deny on Kindle, or wait 30s for timeout."
    approval_prompt
    ;;
  question)
    session_start
    user_prompt
    echo "Question card sent. Tap an option on Kindle, or wait 30s for timeout."
    question_prompt
    ;;
  *)
    echo "usage: bash tools/test_buddy_hooks.sh {dashboard|approval|question}" >&2
    exit 2
    ;;
esac
