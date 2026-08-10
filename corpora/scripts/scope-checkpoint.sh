#!/bin/sh
# corpora PostToolUse hook — periodic scope/integrity checkpoint nudge.
#
# Backs spawn-integrity's periodic-scope-and-integrity-checkpoint principle: a spawn noticing its
# own scope has drifted mid-task (not just attention degrading, which checkpoint-on-context-
# pressure-tell already covers) is easy to miss without an external prompt, the same way
# self-initiated checking erodes under the pressure that principle documents. This hook is that
# external prompt.
#
# Deliberately no python/jq here — this fires on every tool call for the whole session, so the
# steady-state cost (the common case: silent, no reminder due yet) has to be a few filesystem ops,
# not an interpreter startup. Only the Nth call actually emits anything.
#
# State is a per-session counter file, not a shared one — a fresh session (main agent or a spawned
# subagent, each gets its own session_id) starts counting from zero, so the interval is per spawn's
# own tool-call stream, matching the principle's own scope ("during a spawn's session").
#
# Register in ~/.claude/settings.json (user-level, so it's active for every corpora-managed
# project; the .corpora/config.md check below makes it a no-op everywhere else):
#   { "hooks": { "PostToolUse": [ { "matcher": "*", "hooks": [ { "type": "command",
#     "command": "~/.claude/skills/corpora/scripts/scope-checkpoint.sh" } ] } ] } }

[ -f .corpora/config.md ] || [ -f corpora/config.md ] || exit 0

INTERVAL=20

INPUT=$(cat)
SESSION_ID=$(printf '%s' "$INPUT" | grep -o '"session_id"[[:space:]]*:[[:space:]]*"[^"]*"' | sed -E 's/.*"([^"]+)"$/\1/')
[ -n "$SESSION_ID" ] || exit 0

STATE_DIR="${TMPDIR:-/tmp}/corpora-checkpoint"
mkdir -p "$STATE_DIR" 2>/dev/null
COUNTER_FILE="$STATE_DIR/$SESSION_ID"

COUNT=0
[ -f "$COUNTER_FILE" ] && COUNT=$(cat "$COUNTER_FILE" 2>/dev/null)
case "$COUNT" in ''|*[!0-9]*) COUNT=0 ;; esac
COUNT=$((COUNT + 1))
echo "$COUNT" > "$COUNTER_FILE"

[ $((COUNT % INTERVAL)) -eq 0 ] || exit 0

cat <<'REMINDER'
Periodic checkpoint (spawn-integrity's periodic-scope-and-integrity-checkpoint): compare your
current diff/output against this task's original stated scope. If it has grown to cover materially
different or additional concerns — not just more effort than expected — stop at the next safe
point, set status: blocked, name the divergence observed, and describe in Surfaced exactly what's
done and what remains. If scope still matches, no action needed.
REMINDER

exit 0
