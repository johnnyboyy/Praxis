---
name: praxis
description: "Praxis — the process/orchestration engine and the front door for any task. Every task enters through framing (which root governs it, how big it is, what assumptions are being made), then routing (the unit of work, the stance, and whether to run inline / resume / isolate), then a spawn and a single handoff. Praxis owns the workflow — routing, spawning, relay, the chunk ledger, and the hard rule that one unit of work = one spawn = one handoff. It drives corpora, the judgment engine of this fork: corpora registers into praxis's plugin slots, and praxis invokes it generically for composition. Enter here first; with no engine registered praxis still reports the deterministic facts and degrades rather than failing."
---

# Praxis

The **process / orchestration engine** — and the **front door**. Anything you are about to act on
enters here first. Praxis owns *how work moves*: framing it, routing it, spawning it, and carrying one
handoff per unit of work.

Praxis holds no judgment of its own — that lives in the engine. In this fork the engine is
**corpora**: it *registers* into praxis's plugin slots, and the same generic code drives whatever is
registered. The full contract is `BOUNDARY.md`; this file is the operational entry.

## The front door — every task passes through, proportionally

The front door is one tool call: **`begin_work`** (the praxis-front-door MCP server). It frames the
task (governing root; span → **decompose**, N units one per root, never one straddling agent; size
floor; the assumptions list), routes it (execution-shape signals — spans → isolate, ledgered
workstream → resume, else new; the *decision* is yours, the signals are facts), composes judgment
through the registered engine, and **delivers** it: spawn work carries the bodies in the Agent
prompt via `compose_spawn` (the payload read is the prompt-assembly step, and the gate requires it,
and the prompt is assembled **invariants first**: the payload — stance, domains, schema — at the
top, the task-specific brief at the bottom, so every spawn of the same composition shares a
byte-identical prefix and a multi-spawn batch hits the provider's prompt cache instead of paying
the full payload cold each time);
inline work reads the payload file the envelope names (the edit gate stays closed until that read is
recorded). **Spawn is the default** — undeclared execution routes to a spawn, because a spawn's
death is the unit's structural close-out: its context cannot carry one phase's judgment into the
next. Inline is the explicit exception (`execution="inline"`), for work the operator asked to run
inline or that framing sized trivial — and two mechanical gates bound it beyond declaration:
**cross-root inline is rejected** (a seat root holds the judgment between roots and never works
inside another root — begin_work refuses inline when the work's governing root differs from the
declared seat, because "I already have the context loaded" is available as a rationalization on
every call; declaring `search_base=<that root>` is the deliberate re-seating act that re-enables
operator-directed inline there), and a unit whose lease declares `execution: spawn` is
**spawn-only by root policy**. State the envelope's assumptions before acting — redirect
happens before they're realized. `close_work` ends the unit; the next edit requires a fresh frame —
and a frame that merely went stale without `close_work` is surfaced as **close-ceremony debt** at
the next `begin_work` (unit, age, dirty-tree state), to be settled or explicitly abandoned, never
silently buried.

Each unit of work carries a **lease** where `<root>/.praxis/units.md` declares one: the unit's
**edit surface** (the paths that kind of work may write — the gate denies edits outside it, so the
first source-file edit under a design frame bounces instead of drifting), its **output** (the
deliverable whose delivery ends the unit — call `close_work` then, not when the clock runs out),
and optionally `execution: spawn` (the root's standing answer that this unit is never trivial
enough for inline). An undeclared unit restricts nothing; the lease narrows known units, it never
blocks new vocabulary.

The output *scales to the task*: a one-line change earns one line; a vague goal earns a full
disambiguation. An unknown unit-of-work composes universal domains only — the envelope warns loudly
and lists the known units and the root's phases. Fit the task to a known unit, or treat the misfit
as a vocabulary gap: surface it and author the unit/phase through `phases/plugin-authoring.md`
rather than proceeding judgment-free.

One unit of work = one spawn = one handoff: `scripts/handoff.py` templates, validates, and closes
the handoff from the registered plugins' schema contributions; `scripts/chunk_ledger.py` enforces
chunk-done-before-close. `scripts/unit_close.py` is the one-shot form of the close ceremony —
validate → chunk-close → frame-marker-close, chained in one invocation with a clear stop at the
first failure, instead of three separate calls with error gaps between them. Interop between roots
(a task that legitimately spans two) goes through `phases/interop.md` and a bidirectional handoff,
not a straddling agent.

Engine room (what `begin_work` drives; each runnable by hand, and the CLI path still opens the gate):
`scripts/route.py --ask "…"` for a raw natural-language ask (or with `--target`/`--files` for a
targeted frame), `scripts/frame.py` for the root+span+composition facts alone — with
`phases/framing.md` and `phases/routing.md` holding the judgment the scripts don't decide. The engine slot auto-resolves from the governing root (its `.praxis/config.md`
may declare `engine-plugins:`, else the `<root>/.praxis/engine/plugins` convention; legacy bare
`praxis/` dirs remain recognized).

Multiple units queued for the same root — a tasklist, a plan's task files, a workstream with `next`
pointers — run through `phases/session.md`: the loop conductor that iterates the front door one unit
at a time and halts loudly on `blocked` / `questions-pending` / `tradeoffs-pending` or a
scope-changing `Surfaced` item, rather than answering for the operator.

## The plugin-slot model — how an engine (and concerns) plug in

Praxis ships with **empty** slots and discovers whatever is registered:

- **`engine/plugins/`** — a judgment engine's capabilities manifest (`capability → verb + cli`).
  `scripts/engine.py` resolves a capability name against it and invokes the declared CLI. `compose` is
  the one framing/routing needs.
- **`handoff/plugins/`** — the handoff fields an engine expects; `handoff.py` composes the schema from
  `handoff/base.json` + every registered plugin and enforces their required fields.
- **`phases/`** — praxis-core carries only the universal phases (`framing`, `routing`, `interop`,
  `session`, `plugin-authoring`); an engine or a concern contributes its own alongside.

**Moving an engine or a concern in** = `scripts/plugin_import.py import --contribution <dir> --root
<project>` snapshot-imports its contribution into the project's own slots (praxis face → the slots
above; a judgment face → staged through the engine's ratify gate). `scripts/plugin_scaffold.py` and
`scripts/praxis_init.py` author new plugins and new roots; provenance lands in
`<root>/.praxis/plugins.lock.json`.

## The hard rules

- **One unit of work = one spawn = one handoff.** The ledger enforces the chunk-done-before-close gate.
- **Verification stays with the orchestrator.** An implementer spawn's report is a claim, not the
  evidence: the orchestrator (or its verification pass, after the implementation units) re-runs the
  suites and drives the behavior itself. Defects route to a fresh spawn, never back into the
  finished implementer's context.
- **A single agent never straddles two roots.** Spanning work decomposes, one unit per root.
- **Frame before acting; relay assumptions before acting.** The floor of every task, however small.
- **Deterministic-first.** Whatever can be a script is a script (root facts, span, sizing signals,
  ledger, handoff); the engine is invoked only where genuine judgment remains. See `BOUNDARY.md`.
- **Standing permission to spawn.** The user has granted praxis blanket authorization to use the Agent
  tool for the spawn step without asking first, each time a unit of work reaches spawn. This
  is scoped to praxis's own spawn-and-handoff step — it is not a general license to spawn agents outside
  of praxis's routing.

## Components

`scripts/`: `root_tree`, `frame`, `route`, `frame_store`, `engine`, `handoff`,
`interop_handoff`, `chunk_ledger`, `churn`, `excerpt`, `plugin_import`, `plugin_scaffold`, `praxis_init`. `phases/`: `framing`, `routing`, `interop`,
`session`, `plugin-authoring`. Full suite: `python3 -m unittest discover -s tests`. Contract:
`BOUNDARY.md`.
