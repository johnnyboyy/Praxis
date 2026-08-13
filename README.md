# praxis

A process/orchestration engine, packaged as a Claude Code plugin. Praxis frames a
unit of work, composes context per phase, drives it through typed-edge workflows
(or spawns it isolated), verifies at a barrier, and gates edits until a unit is
framed.

## Install

From a marketplace:

```
/plugin marketplace add johnzdanis/skills-pi
/plugin install praxis@jdev-praxis
```

(You can also point the marketplace at a local checkout: `/plugin marketplace add ./`.)

To test without installing, run Claude Code with the plugin dir directly:

```
claude --plugin-dir ./praxis
```

## Entry points

- `/praxis:orchestrate <task>` — drive a whole task autonomously: decompose it
  into a unit graph and run it as a detached cascade (spawn per unit, barrier
  full-verify, fix-loop, escalation). For work you want to hand off and walk away
  from.
- `/praxis:inline <task-or-question>` — do one small thing or answer a question in
  the current conversation: frame a single unit, work in-context, close it.
- `/praxis:report [subcommand] [flags]` — view this repo's praxis journal, gap
  candidates, and metrics/analytics inside Claude Code. It is a deterministic read
  (a bundled `scripts/report.py` renders the append-only journal; no inference).
  Subcommands: `summary` (default — a one-screen overview), `journal` (recent
  entries; `--limit N`, `--unit UID`, `--event TYPE`), `gaps` (recurring vocabulary
  gap candidates), `metrics` (per-phase / per-workflow runs, result/stall,
  pass-rate). Every subcommand also takes `--json`.

All are explicit-only (they will not be auto-invoked by the model).

## Requirements

- Python 3 on `PATH` (the bundled MCP server runs as `python3`).
- The `mcp` package installed (the FastMCP server dependency): `pip install mcp`.

## Design

See [`docs/design.md`](docs/design.md) for the phase/workflow model and typed edges,
[`docs/plugins.md`](docs/plugins.md) for the Contributor contract, and
[`docs/glossary.md`](docs/glossary.md) for the vocabulary.
