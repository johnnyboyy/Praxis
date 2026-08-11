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
  into a unit DAG and run it as a detached cascade (spawn per unit, barrier
  full-verify, fix-loop, escalation). For work you want to hand off and walk away
  from.
- `/praxis:inline <task-or-question>` — do one small thing or answer a question in
  the current conversation: frame a single unit, work in-context, close it.

Both are explicit-only (they will not be auto-invoked by the model).

## Requirements

- Python 3 on `PATH` (the bundled MCP server runs as `python3`).
- The `mcp` package installed (the FastMCP server dependency): `pip install mcp`.

## Design

See [`docs/design.md`](docs/design.md) for the phase/workflow model, typed edges, and
the phase-walking runner.
