# Praxis design — phases, typed edges, and workflows

**Snapshot as of 2026-08-11.** This is a point-in-time description; changes committed after this
date may make it stale — check `git log` against this date.

Praxis runs a **unit of work through a workflow** — a graph of **phases** — rather than a single
dispatch. This document is both the conceptual model (the part that does not fall out of the code)
and a map of what is actually wired today, with `file:line` anchors.

---

## Conceptual model

### Primitives

**Phase** — one atomic move an agent (or a deterministic step) makes.
```
Phase = { name, stance, intent, produces, delivery, run }
  stance   : divergent | convergent | neutral   # secondary to the edge for context decisions
  produces : the result contract — what "done" looks like
  delivery : inline | spawn | deterministic
  run      : a Callable, used only when delivery == "deterministic"
```

**Workflow** — a graph of phases with typed, possibly-conditional edges.
```
Workflow = { name, phases[], edges[(from,to,when,edge_type[,predicate])], expand }
  when : pass | fail | always | agent-choice | feeds | fact
```

There is deliberately **no phase-intrinsic `gate` field** — the preservation gate is a property of
the incoming edge, not the phase (see below). The `expand` slot (phase → sub-workflow) exists on the
dataclass but is not yet driven.

### The context boundary is a property of the EDGE, not the phase

Firmest seam in the system. An artifact in context is an **attractor**: instructions cannot reliably
override it. So the edge into a phase is typed by what that phase does to the prior artifact, and the
edge type — not the phase — selects the preservation gate:

| edge    | did to the original | what's in context               | preservation gate | question        |
|---------|---------------------|---------------------------------|-------------------|-----------------|
| create  | none existed        | the spec (prescriptive spec)      | `does-it`         | *does it?*      |
| carry   | perturbs it         | the original (it should anchor) | `regression`      | *didn't break?* |
| extract | rebuilds it         | the spec only (original dropped)  | `coverage-diff`   | *covered it?*   |

**Every edge carries a preservation gate; its form is a function of what the edge did to the
original.** Coverage-diff is not generic — it is the compensating control specific to the `extract`
edge, the price of having dropped the original to escape its pull.

### The rebuild triple (the `extract` edge, expanded)

A hard seam is never one phase:
```
extract       original IN — inventory / classify / define-interface → produces the spec (no synthesis)
  ── drop the original ──
synthesize    spec ONLY     — rebuild to the interface, free of the attractor
coverage-diff both IN     — TWO directions: losslessness (spec covered?) + completeness (spec met?)
```
Who may hold the original is decided by what the phase emits: **restructures it → no; analyzes it →
yes; compares it → both.** `plan` is itself an extraction (request → units/edges = the spec), so
planning and re-architecture are the same move at different altitudes. `coverage-diff` is
two-input — it consumes *both* `extract`'s spec and `synthesize`'s artifact; the linear single-slot
carry cannot feed it, which is why the runner threads a named-output map (below).

### Two altitudes

**Orchestration** (across units) — verification is DEFERRED to a single barrier:
```
plan → fan-out (units run isolated, in parallel) → ┃BARRIER┃ → verify(full suite, once)
                                                              ├ fail → fix units → re-verify
                                                              └ pass → close
```
**Unit** (within a unit) — a phase-walked workflow, e.g. TDD:
```
write-tests → implement → refactor → test-cleanup
```
Two verification scopes: **local** (a unit's own new tests, fast, inside the unit workflow) and
**global** (the full suite, once, at the barrier).

### Discovery over stone

Every phase exit reports `phase_fit` (clean|loose|none) + `suggested` (what the agent would call
what it actually did) — the same mechanism as task-kind fit, lifted to process. `loose`/`none`
writes a `phase.gap`; recurring gaps promote (via `accretion`) into new vocabulary. Seed the phase
set small; grow it from where real work strains.

---

## Current state (verified against code)

### Phase / workflow data model — `workflow.py`

- `EdgeType` = create / carry / extract (`workflow.py:8`); `GATES` maps each to its gate name
  `does-it` / `regression` / `coverage-diff` (`workflow.py:14`).
- `WHENS = (pass, fail, always, agent-choice, feeds, fact)` (`workflow.py:20`);
  `STANCES` (`:21`), `DELIVERIES` (inline/spawn/deterministic, `:22`).
- `Phase` dataclass carries `run` (a Callable for deterministic delivery); there is **no `gate`
  field** (`workflow.py:25`). `Workflow` has `phases`, `edges`, optional `expand` (`:36`).
- `edge_parts` normalizes 4-tuples (predicate padded `None`) and 5-tuples (`fact`,predicate)
  interchangeably (`workflow.py:52`) — full backward compatibility.
- Seed phases: `plan, write-tests, implement, refactor, test-cleanup, verify, fix, close, extract,
  synthesize, coverage-diff` (`workflow.py:68-94`). `verify` and `coverage-diff` are
  `delivery="deterministic"`.
- Seed workflows (`workflow.py:97-130`): **tdd-unit** (write-tests→implement→refactor→test-cleanup,
  all carry), **rebuild-triple** (extract→synthesize via *extract* edge; synthesize→coverage-diff
  carry; extract→coverage-diff via **feeds**, wiring the two-input phase), **build-verify**
  (implement→verify→close pass, verify→fix on **fail**, fix→verify — a bounded fix-loop).

### The phase-walking runner — `workflow_run.py`

`run_workflow` (`workflow_run.py:86`) walks phases from `start` (or `workflow.first`):

- **Per-phase gather.** Each phase copies the unit `Situation`, sets `situation.phase` to the
  stance (divergent/convergent, else "none") and `situation.phase_name` to the phase name, then
  `gather`s contributors — passing `root` only on the first phase so the task-kind gap surfaces
  **once**, not per phase (`workflow_run.py:112-116`).
- **Delivery.** `delivery=="deterministic"` with a callable `run` executes in-process and builds a
  `Receipt` from its evidence (`passed` → result/stall) (`:129-144`); otherwise `executor.run(unit,
  composed)` (`:146`).
- **Edge-derived gate + verifier.** The gate is `GATES[edge_in]` (create for the entry phase);
  the matching verifier from `verifiers` runs, defaulting `verified=True` when none is supplied
  (`:148-150`).
- **Advance rule.** `passed = evidence["passed"]` (default: receipt outcome == result);
  `advance = passed AND verified` — a failed preservation gate forces the non-advance path
  (`:172-173`).
- **`_choose_edge` routing** (`workflow_run.py:48`), in order: (1) if not advancing, the first
  `fail`/`always` edge wins (failure short-circuits; forward branches are not consulted); (2)
  advancing — `fact` predicate edges are tried in **declaration order**, first truthy predicate
  wins (a raising predicate is fail-soft no-match); (3) `agent-choice` matching `evidence["next"]`;
  (4) default `pass`/`always`.
- **Named-output threading.** `outputs[phase]` records each phase's `produces`; a phase's `inputs`
  are assembled from **all** incoming edges (`_incoming`, `:81`) — this is what lets `coverage-diff`
  read both predecessors. `carry`/`ir` are also injected into `composed` by edge type
  (carry→`composed["carry"]`, extract→`composed["ir"]`) (`:117-123`).
- **`max_phase_loops` guard** (default 3): re-entering a phase beyond the budget emits
  `phase.stalled` and halts (`:106-110`).
- **Unmatched-route guard.** When a phase emits `evidence["next"]` that no outgoing agent-choice
  edge targets, `run_workflow` always journals `phase.route_unmatched` with `kind` classified as
  `unknown` (not in `resolve_phases` — a bug) vs `unwired` (registered but no edge here); a
  facts-only phase where all predicates/default miss journals `kind="no-match"`. The opt-in
  core-scope flag `stall-on-unmatched-route` (`_stall_on_unmatched`, `:21`; string case-insensitive
  `"true"`) converts the fall-through into a `phase.stalled` halt (`:180-205`).
- **`unit-close` hook** fires once at the end with the aggregated final receipt (`:220-222`); the
  return carries `phases` walked, `phase_fits`, `gaps`, and `final`/`receipt`.

### Orchestration altitude — `orchestrate.py`

`run_orchestrated` (`orchestrate.py:44`):

- **Fan-out** via `schedule.run_dag` (`:49`) — waves by dependency, `ThreadPoolExecutor` at
  `concurrency`, `resume=True` skips already done/stalled units.
- **Single barrier full-verify** (`:64-71`): a `() -> Verdict` callable, retried across
  `fix_rounds`; `verdict.verified` → `orchestration.closed`, status `complete`.
- **Bounded fix-loop** (`:72-84`): each barrier defect spawns a targeted **fix-unit** (a `change`
  Situation from `defect_owner`, default `fix: <defect>`), run inline via `run_unit`; fix-units
  patch in place (carry semantics).
- **Three escalation triggers**, all `orchestration.escalated` + `status="escalated"`, never
  auto-replanned: (1) a fan-out unit **stalled** — barrier skipped (`:51-56`); (2) a fix-unit
  reports **structural misfit** (stall or `phase_fit` loose/none) (`:79-84`); (3) the fix-loop
  **exhausts** `fix_rounds` (`:86-88`). Escalations carry `failing_subdag` (transitive dependents
  of the failing seeds, `failing_subdag` at `:21`).
- **`replan`** (`orchestrate.py:91`) is **caller-driven, not automatic**: it splices a
  caller-supplied replacement into the surviving units and re-runs with `resume=True`. The engine
  never picks the replacement — that is the caller's judgment.

### Registry — `registry.py`

`resolve_phases` / `resolve_workflows` (`registry.py:91`, `:114`) start from `SEED_PHASES` /
`SEED_WORKFLOWS` and merge contributor-supplied objects from optional `phases()` / `workflows()`
providers. Collision policy: **seed always wins**; plugin-vs-plugin **first loaded wins**; invalid
objects / colliding names / a raising provider are skipped fail-soft (validation:
`validate_phase` `:30`, `validate_workflow` `:43`, which also checks `fact` edges carry a callable).

### Unit dispatch — `run.py`

- `Receipt` (`run.py:16`): outcome ∈ {result, stall}, plus status, surfaced, evidence, cost,
  tool_calls.
- `run_unit` (`run.py:160`) frames the unit (`gather` + `surface_for`), then **routes on
  `situation.workflow`**: if set and resolvable, it delegates to `run_workflow` (the workflow path,
  `:171-176`); otherwise **single-dispatch** — an executor loop with up to `max_retries` retries,
  a verifier gate, defect feedback threaded back into the next attempt, and a `unit-close` hook on
  finish (`:181-236`).

### Situation — `situation.py`

`Situation` (`situation.py:19`) splits **stance** (`phase` ∈ divergent/convergent/none, `:27`) from
**identity** (`phase_name`, the phase's own name, `:28`). `project_shape` is **gone** as a
concept/field (confirmed: `grep project_shape` finds nothing in the code), and
`Situation`/`TaskSpec` no longer carry the old language/framework/has-ui shape fields.

### Contributors — `contributors.py`

The `Contributor` contract is duck-typed: required `source` + `contribute(situation)`; optional
`hooks()`, `surface()`, `phases()`, `workflows()` (`validate_contributor` `:72`). `gather`
(`:113`) composes contributions (priority-sorted) plus routing metadata and surfaces the task-kind
gap once. `fire` (`:48`) dispatches a `HookContext` to each contributor's `hooks()[step]` — the
**`unit-close`** step is fired from both `run.py:189` (single-dispatch) and `workflow_run.py:220`
(workflow path). `contributors_for` (`:90`) loads `module:factory` specs from the config
`contributors` scope, fail-soft.

### Config — `config.py`

A JSON store at `.praxis/config.json` (`config.py:15`), namespaced: the unnamed scope is
praxis-core, each named scope is a plugin. `read`/`write` operate per scope (`:22`, `:26`);
`ensure` (`:35`) creates an empty `{}` and returns whether it was created. **Existence, not
contents, is the root marker** — a clean root is `{}`.

### Entry points — `conduct.py` + `mcp_server.py`

The MCP server (`mcp_server.py`) is registered under the surface name **`px`** (`.mcp.json`); tools
appear as `mcp__plugin_praxis_px__*`. Two paths:

- **ORCHESTRATOR** — `plan` (`mcp_server.py:93`) → `conduct.run_tasklist_detached` → a **detached**
  cascade (`cascade.launch_detached`) that spawns a **single** worker process which then runs the
  whole unit graph itself (`schedule.run_dag` — a ThreadPoolExecutor over dependency waves) with per-unit
  isolation and resumability; returns
  `running`, poll `plan_status`. `dry_run=True` (the default) previews without spawning.
- **INLINE** — `register_plan` (`:138`, records the unit graph, no spawn/gather) → `next_handoff` (`:157`,
  pulls the next ready unit, frames it, opens the edit gate) → `close_unit` / `record_receipt`.
  `close_unit` (`conduct.py:221`) journals `unit.done` (result only) for the open/named unit so an
  inline unit graph advances past its dependencies; `record_receipt(outcome="stall")` (`conduct.py:239`)
  journals `unit.stalled` for the abandoned/blocked inline close (dependents stay waiting).

`conduct` (single unit, `mcp_server.py:58`) and `init` (`:50`) round out the surface;
`conductor_status` / `conductor_gaps` / `conductor_mint` expose the journal fold, promotable gaps,
and the operator mint gate.

### Support modules

`journal.py` (append-only event log + `fold`), `accretion.py` (gap counting + `mint`/`is_known`),
`handoff.py` (`assemble` overlay/brief, `next_ready`, `pull`), `policy.py` (per-root
`max_retries`/`concurrency`/`verify_required`), `schedule.py` (`run_dag` wave scheduler with cycle
detection and resume) back the two altitudes above.
