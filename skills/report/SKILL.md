---
description: Show this repo's praxis journal, gap candidates, and metrics inside Claude Code — a deterministic read of the append-only log.
disable-model-invocation: true
---

The optional subcommand/flags are: $ARGUMENTS

Resolve the git root with `git rev-parse --show-toplevel` (fall back to the current directory outside a repo). Then run the bundled report script from the plugin directory against that root:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/report.py" summary --root <git-root>
```

- Default (no `$ARGUMENTS`): run `summary`. Show the script's output to the user verbatim — it is an already-rendered one-screen report, so surface it, do not re-summarize it in prose.
- If `$ARGUMENTS` is given, pass it through as the subcommand and flags. Supported subcommands: `summary`, `journal`, `gaps`, `metrics`. Every subcommand also accepts `--json` and `--root`; `journal` additionally accepts `--limit N`, `--unit UID`, and `--event TYPE`. Always append `--root <git-root>` yourself. Do not invent other flags.
- If the repo is not a praxis root yet (no `.praxis/config.json` and no `.praxis/journal.jsonl`), the script prints a friendly "no journal yet" note. In that case tell the user to run `/praxis:init` first to start managing this repo.
