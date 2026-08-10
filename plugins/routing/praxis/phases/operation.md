# Phase: operation

The session and per-unit-of-work loop — how praxis drives work from session entry to close. It is the
routing plugin's praxis face: praxis-core carries the *primitives* (framing, routing, the spawn-prompt
skeleton, the handoff and chunk ledgers); this phase is the *conductor* that sequences them together
with the registered engine's judgment (the ratify gate) and the installed plugins' phases (design
review, library sync, retrospective, architecture scan).

It names each collaborator **by role**, not by identity: "the engine's ratify gate," "the design
plugin's decision-review phase." A project with no engine registered runs the deterministic spine
alone (framing/routing on root facts, spawn skeleton, handoff) and skips the judgment steps; a project
without the design plugin skips design review. Nothing here hard-codes an engine or breaks when one is
absent — the same degradation praxis-core practises, one level up.

**This process is meant to change.** It is a plugin phase, deliberately outside praxis-core, so the
loop can grow, shrink, and re-shape as the right form becomes clear with use. Treat the sequence below
as the current best structure, not a fixed contract.

**Entry condition:** every session, and every unit of work within it. **Stance:** convergent
(orchestration is matching-a-standard work). Not generative.

---

## Session entry (once per session)

1. **Resolve the governing root** for what the session touches — `route.py --from <dir> --target
   <file>` (or `root_tree`). A task whose files span two roots is **decompose**: two units of work,
   one per root, never one spawn straddling both (framing surfaces this as a hard fact).
2. **Is the root bootstrapped?** If the engine needs project state that is absent (for corpora, a
   `.corpora/config.md`), run the engine's **bootstrap** first and do not proceed until it exists — the
   one fallback, no other "if missing" logic. Bootstrap is the engine's own (corpora: the
   `engine-bootstrap` phase / `corpus.py init`), then route what follows per the bootstrap phase's own
   fork (a concrete feature request accompanying bootstrap goes to planning; otherwise run the
   applicable setup phases directly).
3. **Load the conductor's own judgment.** When an engine is registered, this loop composes the routing
   plugin's domains (routing, spawn-integrity, planning) for its own routing decisions — the
   orchestrator is a spawn like any other and does not skip the load-before-work rule it enforces on
   everyone else. With no engine, the loop runs on deterministic facts alone.
4. **Ledger check.** If a chunk ledger exists for the root, verify it before routing new work; surface
   any discrepancy to the operator and never silently re-baseline it.

## Per unit of work

**Route** (`phases/routing.md` + `route.py`). Decide `stance`, `unit-of-work`, and the execution
shape — inline / resume an existing agent / isolate a new spawn — off the deterministic signals
(span, ledger resume-candidate, composition availability). Frame what the spawn must answer before
spawning; if framing reveals ambiguity, ask one clarifying question first. One unit of work = one
spawn = one handoff.

**Compose + spawn** (`spawn_prompt.py`). The engine composes the domain set for the unit of work (its
`compose` hook); `spawn_prompt.py` assembles the prompt skeleton from the parts the engine injects
(`spawn-parts`) — stance frame, domain bodies byte-for-byte, handoff-read schema — plus the task.
Print it, read it yourself, and paste its content into the spawn; never point the spawn at a file to
read (a spawn told to read a file it thinks it knows may shortcut the read). Inline work loads the
same composition into the current session instead of spawning. For a batch of spawns over the same
codebase, run discovery once and paste the findings into each — orchestrator procedure, not gated
judgment.

**Execute.** The composed spawn does the work under its stance and domains. A spawn may create
scope-bounded workers; their results return to the parent, but questions/tradeoffs/proposals/
violations/routing-requests belong to the orchestrator — relayed verbatim, never filtered or silently
resolved. Before writing its handoff the spawn re-reads its output against the composed domains and
revises any violation (tools catch hard errors, not soft principles). Runtime-observable work also
takes the engine's **runtime-verification** phase — drive the real surface, don't just re-run static
checks. The spawn's terminal output is the handoff artifact: one file per spawn, a path + one-line
status only.

**Relay** (the handoff lifecycle, a praxis primitive). Relay the handoff's `Surfaced` section to the
operator **verbatim**, read from the file the spawn wrote. Then branch on the handoff:
- `stance: divergent`, or an `Artifact` targeting a design library → the design plugin's
  **design-decision-review** phase (accept / revise / reject) before continuing.
- `status: questions-pending` → relay questions, collect answers, **continue the same agent** (working
  context survives) — back to Execute, not to Route.
- a `tradeoffs` block → relay for implement-as-specced / accept-alternative / send-back.
- `status: blocked` with scope divergence → re-decompose via planning, or refile the remaining scope
  as fresh narrow tasks; never resume the same spawn on the full original scope.

**Ratify gate** (the engine's judgment — invoked, never re-implemented here). Runs after each spawn by
default: the engine audits the output against its ratified principles, presents proposals **one at a
time** for the operator's ratify/reject/edit, assigns each ratified principle a home, and writes it
back (the engine's write-back / kill-log procedures). Close the unit's **chunk before closing the
handoff** — this ordering is load-bearing (the chunk ledger is a praxis primitive; `handoff.py`
closes, archiving under `debug:`). A unit whose inline session produced no handoff stays unchunked.
With no engine, there is nothing to ratify — the spawn's output stands on its own and the loop closes
the chunk directly.

**Loop** back to Route for the next unit of work.

## Post-gate maintenance (triggered from the gate)

When the design plugin is installed and its drift signals fire, the gate may open a sync workstream —
the design plugin's **library-sync** phase (an edge back to Route, not a continuation of the gate).
Mechanical screenshot sync rides the same trigger point. Each is its own phase; this loop is only the
shared trigger.

## Periodic, operator-invoked (never mechanically routed)

**Retrospective** and **architecture scan** are the engine's own standalone phases — operator
commands, run on their own triggers, never something the per-unit loop routes into automatically.
