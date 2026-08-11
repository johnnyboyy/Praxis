#!/usr/bin/env bash
# praxis-payload-read-stamp.sh — PostToolUse hook on Read.
#
# The payload-read half of the frame gate, journal-backed (P2 of docs/CONDUCTOR-PLAN.md): when the
# frame payload file (<root>/.praxis/.frame-payload.md, or legacy praxis/) is Read, record that
# read on the root's OPEN journal unit (gate.py mark-payload-read → a `unit.note payload_read`
# event), so the gate lets a file/spawn-delivered unit edit. Replaces the old
# `$TMPDIR/praxis-front-door/<session>/<hash>.read` tmp stamp file with a journal note — the
# journal is the single source of truth.
#
# Fires only on the payload path, and only when there is an open unit to attach the read to
# (mark-payload-read is a no-op otherwise). Fails open (writes nothing, exits 0) on any ambiguity.

set -u

command -v jq &>/dev/null || exit 0
command -v python3 &>/dev/null || exit 0

# Source the shared hook primitives via this script's resolved real path (reached through a
# symlink). Fail open (exit 0) if the lib is missing/unreadable.
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
[ -r "$GATE_PY" ] || exit 0

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
[ -z "$FILE_PATH" ] && exit 0

# Only the frame payload file counts. Match on basename under a praxis state dir.
case "$FILE_PATH" in
  */.praxis/.frame-payload.md|*/praxis/.frame-payload.md) ;;
  *) exit 0 ;;
esac

DIR=$(cd "$(dirname "$FILE_PATH")" 2>/dev/null && pwd)
[ -z "$DIR" ] && exit 0
# The payload lives in the root's state dir; walk up from there to the governing root.
praxis_walk_to_root "$DIR" || exit 0
ROOT_PATH="$PRAXIS_ROOT_PATH"

python3 "$GATE_PY" mark-payload-read --root "$ROOT_PATH" >/dev/null 2>&1 || exit 0
exit 0
