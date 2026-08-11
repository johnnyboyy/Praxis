# Praxis Workflows

Praxis runs a **unit of work through a workflow** — a graph of **phases** — instead of a single
dispatch. Praxis owns the process; *what to think* (coding judgment, UI inventories, legal checklists)
rides in as **contributors** (see `contributors.py`). This document is the spec the implementation
synthesizes from.

## Primitives

**Phase** — one atomic move an agent (or a deterministic step) makes.
```
Phase = { name, stance, intent, produces, delivery, gate }
  stance   : divergent | convergent | neutral        # secondary to the edge for context decisions
  produces : the result contract — what "done" looks like
  delivery : inline | spawn | deterministic
  gate     : the preservation check to advance (see below)
```

**Workflow** — a graph of phases with typed, possibly-conditional edges; a phase may expand into a
sub-workflow.
```
Workflow = { name, phases[], edges[(from,to,when)], expand{phase: sub-workflow} }
  when : pass | fail | always | agent-choice
```

**Unit** already carries `workflow` and `phase_index` in the journal schema (dormant until now). A
phase run is a journal record like a unit run: `phase.entered` / `phase.exited` with `phase`,
`phase_index`, `phase_fit`.

## The context boundary is a property of the EDGE, not the phase

Firmest seam in the system. An artifact in context is an **attractor**: instructions cannot reliably
override it. So the edge into a phase is typed by what that phase does to the prior artifact:

| edge     | did to the original | what's in context           | preservation gate      | question        |
|----------|---------------------|-----------------------------|------------------------|-----------------|
| create   | none existed        | the IR (prescriptive spec)  | new-behavior check     | *does it?*      |
| carry    | perturbs it         | the original (it should anchor) | regression / suite | *didn't break?* |
| extract  | rebuilds it         | the IR only (original dropped)  | coverage-diff       | *covered it?*   |

**Every edge carries a preservation gate; its form is a function of what the edge did to the original.**
Coverage-diff is not generic — it is the compensating control specific to the `extract` edge, the price
of having dropped the original to escape its pull.

## The rebuild triple (the `extract` edge, expanded)

A hard seam is never one phase:
```
extract      original IN   — inventory / classify / define-interface → produces the IR (no synthesis)
  ── drop the original ──
synthesize   IR ONLY       — rebuild to the interface, free of the attractor
coverage-diff both IN      — TWO directions: losslessness (IR covered?) + completeness (target spec met?)
```
Who may hold the original is decided by what the phase emits: **restructures it → no; analyzes it →
yes; compares it → both.** `plan` is itself an extraction (request → units/edges = the IR), so
planning and re-architecture are the same move at different altitudes.

## Two altitudes

**Orchestration** (across units) — where verification is DEFERRED to a barrier:
```
plan → fan-out (units run isolated, in parallel) → ┃BARRIER┃ → verify(full suite, once)
                                                              ├ fail → fix units → re-verify
                                                              └ pass → close
```
**Unit** (within a unit) — e.g. TDD:
```
write-tests → implement → refactor → test-cleanup
```
Two verification scopes: **local** (a unit's own new tests, fast, inside the unit workflow — what
`implement` passes against) and **global** (the full suite, once, at the barrier).

## Contributions per phase

`gather` runs at each phase with the phase in the `Situation`; contributors return phase-appropriate
sections. `uiux → plan` (reusable components, so the planner designs for reuse); `conventions →
implement`; `law-checklist → extract`. Domain knowledge is a contributor — praxis stays neutral.

## Discovery over stone

Every phase exit reports `phase_fit` (clean|loose|none) + `suggested` (what the agent would call what
it actually did) — the same mechanism as task-kind fit, lifted to process. `loose`/`none` writes a
`phase.gap`; recurring gaps promote (via `accretion`) into new phases or edges. A mis-typed edge
surfaces as attractor-pull friction (an agent in a `synthesize` phase reaching for the original) — a
`phase.gap` with a specific diagnosis. Seed the phase set small; grow it from where real work strains.

## Definitions

- **Planning** = extraction of an open request into structure (units, edges, per-unit workflow). Output
  is an IR, not code. Where reuse is discovered.
- **Implementation** = a *workflow*, not a phase. TDD is one; others (spike-first, code-first) compose
  differently.
- **Testing** = plural: `write-tests` (author intent), `verify` (run — local or global), `test-cleanup`
  (editorial pruning). "Testing" as one word is itself a gap the fit-signal surfaces.

## Seed phase library

`plan`, `write-tests`, `implement`, `refactor`, `test-cleanup`, `verify`, `fix`, `close`; and the
rebuild triple `extract`, `synthesize`, `coverage-diff`.

## Build status

Implemented (first cut): phase/workflow data model; a phase-walking runner recording `phase_fit`;
per-edge preservation-gate dispatch; per-phase `gather`; `phase.gap` recording via accretion.

Discovered-next (grown, not pre-built): the deferred barrier-verify + fix-loop at the orchestration
altitude; TDD as a wired unit workflow; agent-choice edges; and unit-completion for inline conductor
runs (see the discovery log below).

## Discovery log

- 2026-08-10: the inline conductor path (`register_plan` + `next_handoff`) has no unit-completion
  event, so a multi-unit inline DAG stalls at the first dependency (`next_ready` unlocks a unit only
  when its deps are `done`, and nothing marks an inline unit `done`). Surfaced by trying to enact this
  very build as a multi-unit inline plan. Needs an inline "phase/unit complete" close.

Surfaced by *building* the runner (the model discovering its own gaps — the thesis proving itself):

- **`coverage-diff` is a two-input phase the single-slot boundary can't feed** (highest priority). The
  runner threads one `carry`/`ir` value between phases, but coverage-diff needs BOTH the original IR and
  the newly-synthesized artifact ("both IN"). Fix: thread a small map of named phase outputs, not one
  slot, so a phase can consume several prior outputs. This is the rebuild triple straining against the
  linear model — exactly the kind of misfit the system is meant to catch.
- **`gather` re-surfaces the task-kind gap at every phase.** With a loose/none unit fit, each phase
  re-emits a `conductor.gap`. The task-kind gap should surface once (at the first phase), not per phase.
- **The phase-level `gate` field is unused** — gates are edge-derived (`GATES[edge_in]`). Either drop
  the field or give it a distinct meaning (a phase-intrinsic check independent of its incoming edge).
- **Traversal is linear** — only `pass`/`always` edges are walked; `fail`/`agent-choice` edges (the
  fix-loop, dynamic routing) are defined-but-not-yet-driven. Expected for this cut.
- **Starting mid-graph treats the first phase as `create`** — no incoming edge is honored on resume.

- 2026-08-10 (later): **resolved discoveries 1–3.** `run_workflow` now threads a named-output map and
  assembles each phase's `inputs` from ALL its incoming edges, with a new `feeds` (input-only) edge
  type; `coverage-diff` now receives both `extract`'s IR and `synthesize`'s artifact end-to-end (the
  rebuild triple is whole). The task-kind gap surfaces once (first phase only). The unused
  `Phase.gate` field is dropped (gates are edge-derived). Still open: conditional-edge traversal
  (`fail`/`agent-choice` — the fix-loop) and the orchestration altitude (fan-out → barrier → fix →
  close), plus inline unit-completion.

- 2026-08-10 (later still): **conditional-edge traversal done.** The runner routes on a phase outcome
  (`evidence["passed"]`, defaulting to receipt success) rather than blindly following `pass`: a `fail`
  edge routes to a repair phase, so `verify --fail--> fix --pass--> verify` forms a bounded fix-loop
  (`max_loops` guard emits `phase.stalled` and halts). `agent-choice` edges follow `evidence["next"]`.
  The composed dict now carries `phase` so executors are phase-aware. New `build-verify` seed workflow.
  Note (new discovery): routing outcome (receipt/`passed`) is deliberately DECOUPLED from the
  preservation gate (`verified`, recorded but not routing); unifying them — a failed gate forcing a
  fail-route — is a future call. Still open: the orchestration altitude across units (fan-out →
  barrier full-verify → fix units) and inline unit-completion.

- 2026-08-10 (orchestration altitude, first cut): `orchestrate.run_orchestrated` — fan-out via
  `run_dag`, then a single **barrier full-verify** (a `() -> Verdict` callable), then a bounded
  fix-loop that spawns targeted **fix-units** per defect (carry edge, patch in place) and re-verifies.
  **Escalation to re-plan is triggered, not defaulted**, on three signals: a fan-out unit `stalled`
  (barrier skipped — nothing to verify), the fix-loop exhausting `max_loops`, or a fix-unit reporting
  structural misfit (stall or `phase_fit` loose/none — a perturbation that was secretly a rebuild).
  The hook only records `orchestration.escalated` + returns `status="escalated"`; **re-plan machinery
  is deliberately deferred** until a real run trips a trigger (grow it when the failure tells us its
  shape). Rationale (agreed): fix-units are the standard because they're non-destructive (preserve the
  passing units); re-plan is the expensive re-extraction reserved for structural failure.
  Process note: this unit was built by SPAWN + verify (the model's default), correcting two prior
  units done inline — inline is now a *declared* carry-edge exception, not a silent convenience.
