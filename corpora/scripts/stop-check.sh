#!/bin/sh
# corpora Stop hook. Chunk-composition reconciliation (what this hook used to run as
# `corpus.py verify-chunks`) moved to praxis's `chunk_ledger.py verify` along with the rest of
# chunk/unit-of-work bookkeeping — that check now runs praxis-side, where the project root's
# registered engine slot is actually resolvable. Nothing left for this hook to check today; it
# exists as the registration point if a corpora-side Stop check is ever needed again.
#
# Register in the project's .claude/settings.json:
#   { "hooks": { "Stop": [ { "hooks": [ { "type": "command",
#     "command": "~/.claude/skills/corpora/scripts/stop-check.sh" } ] } ] } }

exit 0
