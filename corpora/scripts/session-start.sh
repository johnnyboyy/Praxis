#!/bin/sh
# corpora SessionStart hook — runs in a project's working directory at every
# session start. Two jobs, both deterministic:
#   1. Point work at the praxis conductor (the plan / conduct tools compose the
#      judgment and deliver it per unit; the journal-first edit gate stays closed
#      until a unit is framed — enforced by the gate, not prose).
#   2. Reconcile the counters ledger and the domain schemas against the
#      working files, surfacing anything that ran off the books at the moment
#      of peak attention. (Chunk/unit-of-work bookkeeping moved to praxis.)
# Always exits 0 — this hook informs; it never blocks a session.
#
# Register in the project's .claude/settings.json:
#   { "hooks": { "SessionStart": [ { "hooks": [ { "type": "command",
#     "command": "~/.claude/skills/corpora/scripts/session-start.sh" } ] } ] } }

# Project state lives in `.corpora/` (standard) or `corpora/` (legacy).
CORPORA_DIR=""
for C in .corpora corpora; do
  [ -f "$C/config.md" ] && CORPORA_DIR="$C" && break
done
[ -z "$CORPORA_DIR" ] && exit 0

echo "This is a corpora-managed project. Drive work through the praxis conductor:"
echo "give it a tasklist (the praxis MCP 'plan' tool) or a single unit ('conduct'); it"
echo "frames, composes the judgment, and delivers it. The edit gate stays closed until a"
echo "unit is framed — for in-context work, pull the handoff ('next_handoff') first."

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
python3 "$SCRIPT_DIR/corpus.py" --root . verify 2>&1
python3 "$SCRIPT_DIR/corpus.py" --root . lint-domains --domains-dir "$SCRIPT_DIR/../domains" 2>&1
if [ -d "$CORPORA_DIR/domains" ]; then
  python3 "$SCRIPT_DIR/corpus.py" --root . lint-domains --domains-dir "$CORPORA_DIR/domains" 2>&1
fi
python3 "$SCRIPT_DIR/corpus.py" --root . lint-deterministic-shortcut-candidates 2>&1
python3 "$SCRIPT_DIR/corpus.py" --root . deterministic-shortcut-candidates 2>&1

exit 0
