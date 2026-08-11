#!/usr/bin/env bash
# praxis-frame-gate.sh — PreToolUse hook (Edit/Write/MultiEdit): blocks a code edit in a
# praxis-managed root unless an OPEN unit of work in the conductor journal authorizes it.
#
# P2 of docs/CONDUCTOR-PLAN.md: the gate now reads the conductor journal
# (conductor/journal.open_unit) as the single source of truth — is there an open unit for this
# root, and does it authorize THIS edit? — replacing the tmp session-stamp files + freshness
# windows. The decision itself lives in praxis/scripts/gate.py (a pure function of the journal
# fold); this hook is the thin surface that resolves the root and relays the verdict:
#   - allow    ⇒ exit 0.
#   - deny     ⇒ an open unit exists but does not authorize this edit (out of lease surface, or its
#                payload has not been read yet) — deny with the reason gate.py gives.
#   - no_unit  ⇒ no open unit for this root — deny with the begin_work pointer.
#
# Fails OPEN on any ambiguity or error (missing jq/python3, path not resolvable, gate.py errors) —
# this hook must never be the reason a legitimate edit can't proceed. Set PRAXIS_HOOK_BYPASS=1 to
# disable outright.

set -u

if [ -n "${PRAXIS_HOOK_BYPASS:-}" ]; then
  exit 0
fi

if ! command -v jq &>/dev/null; then
  exit 0
fi
if ! command -v python3 &>/dev/null; then
  exit 0
fi

# Source the shared hook primitives. This file is reached through a symlink (~/.claude/hooks/…),
# so resolve BASH_SOURCE to the real repo copy before dirname or the sibling lib is invisible.
# Fail open (exit 0 ⇒ allow) if the lib is missing/unreadable — never hard-fail a legit edit.
_praxis_self="${BASH_SOURCE[0]}"
while [ -L "$_praxis_self" ]; do
  _praxis_link=$(readlink "$_praxis_self")
  case "$_praxis_link" in
    /*) _praxis_self="$_praxis_link" ;;
    *) _praxis_self="$(dirname "$_praxis_self")/$_praxis_link" ;;
  esac
done
_praxis_libdir=$(cd "$(dirname "$_praxis_self")" 2>/dev/null && pwd)
if [ -z "$_praxis_libdir" ] || [ ! -r "$_praxis_libdir/praxis-hooks-lib.sh" ]; then
  exit 0
fi
. "$_praxis_libdir/praxis-hooks-lib.sh"

GATE_PY="$_praxis_libdir/../scripts/gate.py"
if [ ! -r "$GATE_PY" ]; then
  exit 0
fi

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null)

if [ -z "$FILE_PATH" ]; then
  exit 0
fi

# Walk upward from the file's own directory to the nearest praxis marker — the rule of record is
# root_tree.governing_root_above (nearest ancestor carrying `.praxis/config.md`, then legacy
# `praxis/config.md`; `.praxis` wins), which praxis_walk_to_root transcribes.
DIR=$(cd "$(dirname "$FILE_PATH")" 2>/dev/null && pwd)
if [ -z "$DIR" ]; then
  exit 0
fi
ABS_FILE="$DIR/$(basename "$FILE_PATH")"
if ! praxis_walk_to_root "$DIR"; then
  exit 0
fi
ROOT_PATH="$PRAXIS_ROOT_PATH"

deny() {
  jq -n --arg reason "$1" \
    '{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": $reason}}'
  exit 0
}

# The journal-backed decision. gate.py always exits 0 with a {verdict, reason} JSON object, and is
# itself fail-open (any internal error resolves to "no_unit"); a hard failure here (unparseable
# output, non-zero exit) falls open too.
DECISION=$(python3 "$GATE_PY" check --root "$ROOT_PATH" --file "$ABS_FILE" 2>/dev/null) || exit 0
VERDICT=$(echo "$DECISION" | jq -r '.verdict // empty' 2>/dev/null)
REASON=$(echo "$DECISION" | jq -r '.reason // empty' 2>/dev/null)

case "$VERDICT" in
  allow)
    exit 0
    ;;
  deny)
    [ -n "$REASON" ] || REASON="This edit is not authorized by the open unit of work for this root ($ROOT_PATH) — call begin_work for the unit whose work this edit is."
    deny "$REASON"
    ;;
  no_unit)
    deny "No open unit of work in the journal for this root ($ROOT_PATH) — drive this work through the conductor first (the plan / next_handoff tools, or conduct for a single unit) so a unit is framed before editing."
    ;;
  *)
    # Unrecognized verdict ⇒ fail open, never the reason a legit edit is blocked.
    exit 0
    ;;
esac
