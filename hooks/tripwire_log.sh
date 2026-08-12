#!/usr/bin/env bash
# tripwire_log.sh — PreToolUse hook. The tool-log capture for the rebuild
# tripwire (spine B3b).
#
# A PreToolUse hook fires for the tool call ABOUT to run. Its stdin JSON carries
# `agent_id` (ABSENT/null for the parent orchestrator, POPULATED for a dispatched
# subagent's own calls), `tool_name`, and `tool_input`. We log ONE line per
# subagent read so `isolation.read_tool_log` can replay a single subagent's
# reads (keyed on `agent_id`) into `scan_tripwire`.
#
# We log a line only when:
#   * `agent_id` is present (a subagent, NOT the parent orchestrator), AND
#   * `tool_name` is Read / Grep / Glob / Bash.
# Line format (tab-separated): <agent_id>\t<tool_name>\t<path-or-command>
#   Read/Grep/Glob → tool_input.file_path (Grep/Glob fall back to .path/.pattern)
#   Bash           → tool_input.command
#
# Destination: $PRAXIS_TRIPWIRE_LOG, else <cwd>/.praxis/tripwire.log.
#
# A logging hook must NEVER block a tool call: this script is fail-soft and
# ALWAYS exits 0. `jq` is used when present; a tolerant grep/sed parse is the
# fallback so capture still works without jq.

set -u

INPUT=$(cat 2>/dev/null) || INPUT=""
[ -z "$INPUT" ] && exit 0

LOG="${PRAXIS_TRIPWIRE_LOG:-}"
if [ -z "$LOG" ]; then
  LOG="$(pwd)/.praxis/tripwire.log"
fi

AGENT_ID=""
TOOL_NAME=""
PAYLOAD=""

if command -v jq &>/dev/null; then
  AGENT_ID=$(printf '%s' "$INPUT" | jq -r '.agent_id // empty' 2>/dev/null)
  TOOL_NAME=$(printf '%s' "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
  case "$TOOL_NAME" in
    Bash)
      PAYLOAD=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null) ;;
    *)
      PAYLOAD=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // .tool_input.path // .tool_input.pattern // empty' 2>/dev/null) ;;
  esac
else
  # Tolerant fallback parse — best-effort scalar extraction, no nesting smarts.
  _grab() {
    printf '%s' "$INPUT" \
      | grep -oE "\"$1\"[[:space:]]*:[[:space:]]*\"([^\"\\\\]|\\\\.)*\"" \
      | head -n1 \
      | sed -E "s/^\"$1\"[[:space:]]*:[[:space:]]*\"//; s/\"$//; s/\\\\\"/\"/g"
  }
  AGENT_ID=$(_grab agent_id)
  TOOL_NAME=$(_grab tool_name)
  case "$TOOL_NAME" in
    Bash) PAYLOAD=$(_grab command) ;;
    *)    PAYLOAD=$(_grab file_path)
          [ -z "$PAYLOAD" ] && PAYLOAD=$(_grab path)
          [ -z "$PAYLOAD" ] && PAYLOAD=$(_grab pattern) ;;
  esac
fi

# Parent orchestrator (no agent_id) → nothing to capture.
[ -z "$AGENT_ID" ] || [ "$AGENT_ID" = "null" ] && exit 0

case "$TOOL_NAME" in
  Read|Grep|Glob|Bash) ;;
  *) exit 0 ;;
esac

[ -z "$PAYLOAD" ] && exit 0

# Strip tabs/newlines from the payload so one read == one line.
PAYLOAD=$(printf '%s' "$PAYLOAD" | tr '\t\n\r' '   ')

mkdir -p "$(dirname "$LOG")" 2>/dev/null || exit 0
printf '%s\t%s\t%s\n' "$AGENT_ID" "$TOOL_NAME" "$PAYLOAD" >>"$LOG" 2>/dev/null || exit 0

exit 0
