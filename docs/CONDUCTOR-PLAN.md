# The conductor plan — toward the independent ideal

The north star for reshaping this repo into two genuinely independent systems that meet at a clean
seam. I (the agent) execute this in small, testable phases; this file is both the roadmap and the
running progress ledger. Steer by editing the "Target contracts" or reordering phases.

## Start here (cold-boot briefing for a fresh session)

You are continuing an in-progress reshape of this repo (`~/jdev/skills-pi`, the Pi-dedicated fork of
a praxis+corpora system) toward the ideal below. Read this whole file first; the contracts and the
progress ledger are authoritative — do not re-derive them.

- **Layout:** `conductor/` (the new judgment-agnostic core being built — start here), `corpora/` (the
  judgment engine, becomes a provider), `praxis/` (legacy process scripts, retired phase by phase),
  `pi-extension/praxis/` (the Pi extension — the stable outer shell; swap its guts conductor-ward),
  `.praxis/` (per-root state: journal.jsonl, config, phases, workflow.json).
- **Run tests:** `cd conductor && python3 -m unittest discover -s tests` (and likewise in `praxis/`,
  `corpora/`). Keep all green.
- **Working rule:** nothing old is removed before its replacement passes tests (see Migration). Small
  phases; checkpoint after each; update the progress ledger at the bottom.
- **State now:** P1–P6 done. P1 = `conductor/journal.py` (the event-log source of truth + gap
  substrate). P2 = the edit gate now reads the journal fold (`journal.open_unit`) via
  `praxis/scripts/gate.py`, begin_work/close_work bridge `unit.framed`/`unit.closed` into the
  journal, and the tmp session-stamp files + freshness windows are retired on both surfaces. P3 =
  the provider seam: `conductor/situation.py` (the feature object + gap-surfacing hook) and
  `conductor/providers.py` (the `Provider` protocol, `NullProvider` degrade, and `CorporaProvider`
  wrapping corpora behind `compose`); the conductor consults `providers.consult`, not a hardcoded
  engine call. P4 = the linear conductor core `conductor/run.py`: a plan of units iterated through
  proposed→framed→dispatched→running→receipt→done/stalled, consulting the provider before executing
  and dispatching through an `Executor` (inline / subprocess), every transition a journal event.
  P5 = the recorded verification gate in the same loop: a `Verifier` gates each receipt
  (`unit.verified` on pass), defects loop back with feedback up to `max_retries`, then the unit is
  surfaced as a blocked stall. P6 = `conductor/schedule.py` (`run_dag`): `depends_on` waves run in
  parallel up to a concurrency cap, a stalled dependency blocks its dependents (cascading), cycles
  are rejected up front, and `reflexive_route` consults the provider about the conductor's OWN
  routing move (same hook, same gap detector). Contracts settled through the gap-harvest refinement.
  **Next: P7.**
- **Prioritize** the spine P1–P5 (event log → gate → provider seam → conductor → verification gate);
  P6–P9 are refinements as budget allows.
- **Style:** execute-and-verify with minimal discussion.
- **Harness-agnostic:** the conductor CORE is plain Python (event log, provider/executor
  abstractions) — build and test P2–P8 from any harness (Claude Code or Pi); it's just Python +
  `unittest`. Only the SURFACE (how tools + the edit-gate reach the agent) is harness-specific: a Pi
  extension (`pi-extension/praxis/`) or Claude Code MCP + hooks (already scaffolded in the sibling
  repo `~/jdev/skills`). Keep the core transport-free (the `front_door_core` ← `cli`/`server` split is
  the pattern) so each surface is a thin wrapper. Prefer whichever harness is cheapest for you to run.

## The point (why this exists)

The conductor is a **process-discovery engine**, not a fixed process. Its vocabulary — the task
kinds, phases, and workflows — is *emergent*: it grows per domain (coding, prose, devops, marketing,
accounting, …) through use, the same way corpora's judgment accretes and the same way Pi improves
through use. The system does not need to be complete or correct from the start; its value is in
**surfacing where it doesn't fit and discovering better process through practice** (this is what
"praxis" means). So gap-surfacing is not a feature bolted on — it is the core mechanism, symmetric to
corpora's ratify gate: corpora accretes *judgment* from real work; the conductor accretes *process
vocabulary* from real work.

**The prime directive:** the model *likes verbs* — so harvest its suggestion instead of begging it to
opt out. On every task, collect two things it answers naturally: **what it would freely call this**
(`suggested_kind`) and **how well the closest existing verb fits** (`fit`). Work proceeds under a known
verb (composition needs one), but the **divergence between its free suggestion and the verb it ran
under is the always-on gap detector — and the suggestion is the candidate new verb**. This detects the
junk drawer *from the inside*: even when everything jams into one catch-all, the suggestions beneath
it reveal the hidden diversity (the `implement-feature`-as-catch-all failure). `unclassified` is no
longer a value the model must pick — it is derived (`fit == none`). Applies to every closed vocabulary
(task_kind, subject, phase, workflow, unit).

## The ideal (established with the operator)

- **Conductor** — a *judgment-agnostic* process engine:
  - an **event log is the single source of truth**; current state is a fold over it (retires the
    scattered frame-marker / session-stamp / chunk-ledger / runtime-audit / trace files).
  - **units of work** with an explicit lifecycle and a terminal **receipt** (outcome + evidence).
  - a **plan as a DAG** (dependencies), scheduled up to a concurrency cap (parallel-then-verify).
  - an **executor abstraction** (inline / isolated subprocess / remote) — the conductor doesn't care
    *how* a unit runs, only that it returns a receipt.
  - a **verification gate** as a *recorded* transition (not prose): defect → feedback loop-back,
    bounded retries, then surface.
  - **provider hooks** — before executing a unit, and before its own routing decisions, the conductor
    consults registered **providers** and folds in what they return.
  - **guardrails as editable policy data**, not hardcoded.
- **Judgment provider (corpora)** — orchestrator-agnostic:
  - `compose / ratify / retrospect` over a **feature-based situation schema** (not another system's
    unit-of-work nouns), returning **placement-agnostic artifacts**.
  - housekeeping (ratify, retrospect) exposed as **capabilities the conductor triggers**, not phases
    corpora must contain a process engine to run.
- **The seam** — one pattern: the conductor consults the judgment provider at lifecycle points,
  *including reflexively about its own routing decisions*. This dissolves the two current
  cross-contaminations (praxis's self-routing corpora domain; corpora's praxis phases) into a single
  hook applied even to the conductor's own moves. Neither system contains the other.

## Target contracts (the shapes everything builds toward)

**Event (journal line)** — append-only at `<root>/.praxis/journal.jsonl`:
```
{ "ts": <epoch>, "seq": <n>, "event": "<type>", "unit": "<unit-id>", ...payload }
```
State-advancing event types → lifecycle state:
`unit.proposed→proposed`, `unit.framed→framed`, `unit.dispatched→dispatched`,
`unit.running→running`, `unit.receipt→verifying`, `unit.verified→verified`,
`unit.done→done`, `unit.stalled→stalled`, `unit.closed→closed`.
Non-advancing (edges/annotations): `unit.depends_on`, `unit.defect_of`, `unit.spawned_because`,
`unit.note`, `unit.runtime`.

**Situation (feature object)** — what a provider composes against. Closed vocabularies start MINIMAL
and grow by discovery; each carries `unclassified` as its honored fallout:
```
{ "task_kind": "create|change|explore",   // the CHOSEN seed verb the work RUNS under (composition
                                           //   needs a known one); fix/refactor/verify/… are discovered
  "suggested_kind": <free-text>,  // ALWAYS collected — what the model would freely call this task.
                                  //   The gap DETECTOR and the candidate new verb in one.
  "fit": "clean|loose|none",      // the model's honest rating of how well task_kind fits its own
                                  //   suggestion — rating a mapping (natural), not sacrificing a verb.
  "intent":    <free-text>,       // what the work is trying to do
  "subject":   "coding|design|process|prose",
  "phase":     "divergent|convergent|none",
  "project_shape": { "language":…, "framework":…, "has_ui":…, "styling":…, "package_manager":… },
  "root": <path>, "targets": [<path>…],
  "workflow": <id|null>, "label": <str|null> }   // label = a conductor's own noun, bridge only
// `unclassified` is DERIVED (fit == none), not a value the model must pick.
```

**Gap (surfaced, and the seed of new vocabulary)** — journal event `conductor.gap`, emitted whenever
`fit` is `loose`/`none` (work still ran under `chosen`):
```
{ "vocabulary": "task_kind|subject|phase|workflow|unit",
  "chosen":  <the seed verb work ran under>,
  "suggested": <the model's free name — THE candidate>,
  "fit": "loose|none", "intent": <free-text>, "situation": <situation>, "note": <why> }
```
Recorded and surfaced. **Recurrence of `suggested` across gaps is the mint signal** (a corpora-counter
analogue): when the same suggestion accumulates, the accretion phase promotes it into a real verb /
phase / workflow — the conductor's ratify gate. `journal.gap_candidates(root)` tallies them.

**Provider protocol** — a provider (corpora is one) exposes:
```
compose(situation)  -> { artifacts:[{slot, body, provenance}], stance, note }
ratify(proposal)    -> { verdict, domain, ... }
retrospect(scope)   -> { signals }
capabilities()      -> [<name>…]
```

**Receipt** — the terminal `unit.receipt` event payload:
```
{ outcome:"result|stall", status:"complete|blocked|questions-pending|tradeoffs-pending",
  surfaced:[<proposal>…], evidence:<verification…|null>, cost:{tokens,usd}|null, tool_calls:int }
```

## Phases (small, testable; each enables the next)

- **P1 — Event log as source of truth.** `conductor/journal.py`: append + fold-to-state + summary +
  `open_unit`. The keystone; everything reads state from here. *(tests)*
- **P2 — Gate reads the log.** Rewrite the edit gate to consult the journal fold; retire the
  tmp session-stamp files + freshness windows (vestigial in the Pi fork). *(tests + live)*
- **P3 — Provider seam + situation schema.** `conductor/situation.py` + `conductor/providers.py`;
  wrap corpora as a provider behind `compose`. The conductor consults the hook, not a hardcoded
  engine call. Degrades with a null provider. *(tests)*
- **P4 — Conductor core (linear).** `conductor/run.py`: iterate a plan's units, consult the provider,
  dispatch via an **executor** (inline / spawn), write receipts as events. *(tests + live)*
- **P5 — Verification gate.** Recorded verify transition; defect → feedback loop-back, bounded
  retries, then surface. Fixes the unenforced-verification hole; hardens `test-scaffold`'s loop-back.
- **P6 — DAG + concurrency + reflexive routing.** `depends_on` scheduling, concurrency cap
  (parallel-then-verify enforced); the conductor consults judgment about its *own* routing.
- **P7 — Fold in receipts/handoff/cost; retire redundant primitives.** Handoff/chunk-ledger become
  views over the journal; cost/tokens captured from the child run.
- **P8 — Corpora decoupling.** Migrate corpora selection from `units-of-work` strings to feature
  predicates; the provider maps situation features → domains natively.
- **PG — Gap-surfacing & vocabulary accretion (cross-cutting; the conductor's ratify gate).** The
  *surfacing hook* lands early in **P3** (the provider reports `fit`; a forced/weak match emits
  `conductor.gap` and routes to `unclassified` instead of composing the junk drawer). The *promotion
  loop* — operator reviews surfaced gaps and mints a new verb/phase/workflow — is its own step, built
  once real gaps have accumulated (first-attempt-is-first-draft, applied to the vocabulary itself).
- **P9 — Guardrails as policy + final de-cruft.** Operator guards become editable policy; collapse
  the engine-plugin hop to a direct provider call.

## Migration approach
The Pi extension (`pi-extension/praxis/`) is the stable outer shell; its guts swap from the legacy
praxis CLI to `conductor/` one phase at a time, tests green at each step. Legacy praxis scripts stay
until a phase subsumes them, then are retired. Nothing is removed before its replacement passes.

## Progress ledger
- **P1 — DONE.** `conductor/journal.py` + `conductor/tests/` (8 tests, green). Append-only event log;
  pure fold → per-unit state, `open_unit` (the gate's future query), and the deliver-vs-stall summary
  (subsumes the trace view). Tolerant of unknown event types and corrupt lines. Reserved envelope
  keys documented.
- **Contracts reshaped (operator steer).** `task_kind` → minimal seed (`create|change|explore`);
  always-present `intent`; gap-surfacing made the core mechanism (the prime directive).
- **Gap detection sharpened (operator steer).** Harvest the model's own `suggested_kind` + `fit`
  rating rather than hoping it picks `unclassified` (now derived, `fit==none`). The divergence between
  suggestion and the verb work ran under is the always-on detector; the suggestion is the candidate.
  Detects the junk drawer from the inside. **Recurrence = the mint signal**: `journal.gap_candidates`
  tallies suggestions (corpora-counter analogue). `journal.gaps` exposes the raw surfaced gaps. 10
  tests green (incl. a domain-neutral devops `provision-infra` recurrence case).
- **P2 — DONE.** The edit gate reads the journal fold as the single source of truth.
  - **Gate logic** (`praxis/scripts/gate.py`) — a pure function of `journal.open_unit(root)`:
    `no_unit` / `allow` / `deny` (out-of-surface via `units.surface_allows`, or payload-unread for
    file/spawn delivery). Fail-open: any internal error → `no_unit`. Also exposes
    `mark-payload-read` (a `unit.note payload_read` event, replacing the `.read` tmp stamp).
  - **Bridge** (`front_door_core.begin_work`/`close_work`) — writes `unit.framed` (with the frame's
    unit_of_work / composition / delivery / surface / payload…) and `unit.closed` to the journal, so
    the fold has state. Additive alongside the still-written `.last-frame-at` marker (which the
    cosmetic status footer and `_unclosed_prior` still read). NB: a long-running MCP server picks up
    the bridge only on restart; the CLI transport (Pi surface) is a fresh process each call, so it's
    live immediately.
  - **Both surfaces repointed.** Claude Code hook `praxis-frame-gate.sh` and the Pi extension
    (`pi-extension/praxis/index.ts` `gateDecision`) now both delegate to `gate.py` — one gate
    implementation. `praxis-frame-stamp.sh` is a no-op; `praxis-payload-read-stamp.sh` and the Pi
    `tool_result` handler write the journal note; the Pi inline-injection path records the read at
    injection time. No tmp session-stamp files, no 1800s/60s freshness windows.
  - **Tests green** (conductor 10, praxis 224, corpora 167). `test_hooks.py` / `test_hook_glob_parity.py`
    rewritten from stamp-seeding to journal-seeding; `test_front_door_server.py` gains a
    `JournalBridge` class; retired the stamp-projection parity + stamp-write tests. `index.ts` has no
    test harness in this repo (built in the sibling `~/jdev/skills`), so its port is verified by
    parity of logic with `gate.py`, not by a run here.
  - **Surface note.** The *live* Claude Code hooks (`~/.claude/hooks/*.sh`) symlink to the sibling
    repo `~/jdev/skills`, not here — so skills-pi's own `praxis/hooks/*.sh` copies are exercised
    only by skills-pi's test suite, not by a live Claude Code session. This P2 put skills-pi's
    copies AND the Pi extension on the journal; porting the journal-first gate into the *live*
    Claude Code surface (`~/jdev/skills`) is separate work, to be done there.
  - **Follow-ups (deferred, non-blocking):** `close_frame_marker`'s now-vestigial
    `clear_session_stamps` can go in a later de-cruft pass; skills-pi's `praxis-frame-stamp.sh` is a
    retired no-op (kept so any local reference stays valid).
- **P3 — DONE.** The provider seam + situation schema; corpora wrapped as one provider. 25 new
  conductor tests (35 total, green).
  - **`conductor/situation.py`** — the `Situation` feature object (task_kind/intent/subject + the
    refining fields), with the closed vocabularies validated and the open ones (`suggested_kind`,
    `label`) left free to grow. Carries the prime directive: `routed_kind` derives `unclassified`
    from `fit == "none"` (never a value the model picks), and `surface_gap` /
    `surface_task_kind_gap` write a `conductor.gap` event when `fit` is `loose`/`none` — the
    always-on detector, feeding `journal.gap_candidates`.
  - **`conductor/providers.py`** — the `Provider` protocol (`compose`/`ratify`/`retrospect`/
    `capabilities`), `NullProvider` (degrades every hook to a well-formed empty result),
    `CorporaProvider` (wraps corpora: keys `select` on the `label` bridge noun, routes a `fit==none`
    match to `unclassified` = universals-only instead of the junk drawer, and turns `spawn-parts`
    bodies into `artifacts`), and `consult(provider, situation, root)` — the hook that surfaces the
    gap then composes. Conductor imports neither praxis nor corpora: `CorporaProvider` is fed plain
    callables, so the core stays transport-free and a second engine is just a second provider.
  - **Real wrap proven, not just stubbed.** `RealCorporaWrapTest` builds the callables over the
    actual corpora engine (via `praxis/scripts/engine.py` + the corpora manifest — a cross-layer
    reach the *test* is allowed, the core is not) and composes a real situation: prose-craft lands
    in `domains`, real domain bodies come back as `artifacts`. Skips cleanly if the engine manifest
    isn't loadable, so the suite stays portable.
  - **PG (gap surfacing) landed here, as planned.** The surfacing hook is live in `consult`; the
    promotion loop (operator mints a recurring `suggested` into real vocabulary) is still its own
    later step, to be built once real gaps accumulate.
  - **Deferred to later phases:** `CorporaProvider.ratify`/`retrospect` degrade unless their
    callables are supplied (P-later housekeeping); the situation→corpora key still rides the `label`
    bridge noun — P8 migrates corpora selection from unit-of-work strings to feature predicates so
    the provider maps situation features → domains natively.
- **P4 — DONE.** The linear conductor core, `conductor/run.py`. 16 new conductor tests (51 total,
  green).
  - **Dataclasses.** `Receipt` (the terminal claim contract — outcome/status/surfaced/evidence/
    cost/tool_calls, with `from_dict`/`to_dict` and a stall as a first-class outcome), `Unit` (id +
    situation + unit_of_work, defaulting to the situation's `label` then `task_kind`), `Plan` (a
    linear list of units for now; the DAG is P6).
  - **Executor abstraction** — the 'how it runs' seam the conductor never sees through: `Executor`
    protocol + `InlineExecutor` (runs a handler in-process, normalizing a dict receipt) +
    `SubprocessExecutor` (isolated subprocess; JSON receipt on stdout parsed, clean exit taken as a
    bare result, and a nonzero exit / launch failure / timeout turned into a recorded blocked
    stall, never an exception that aborts the run).
  - **The loop** — `run_unit` drives one unit proposed→framed→dispatched→running→receipt→
    done/stalled, consulting the provider (`providers.consult`) BEFORE executing and folding the
    composed judgment + any surfaced gap into `unit.framed`; `run` iterates a plan and returns
    per-unit results plus the fold's deliver-vs-stall summary. The loop keeps NO state of its own —
    everything it knows is what it wrote, so a re-fold of the log reproduces the run exactly.
  - **tests + live.** `LiveConductorRunTest` drives a real 2-unit plan through the real corpora
    provider + an inline executor and reads the whole run back off the journal fold: unit a composes
    real corpora domains and ends `done`; unit b's forced (`fit==none`) match routes to
    `unclassified` and surfaces a `provision-infra` gap that lands in `gap_candidates`. Skips if
    corpora isn't loadable.
  - **Left for the next phases (as planned):** DAG scheduling + concurrency cap + reflexive routing
    are P6; cost/tokens captured from the child run is P7.
- **P5 — DONE.** The recorded verification gate, folded into the same `run_unit` loop. 13 new
  conductor tests (64 total, green).
  - **`Verdict`** (verified / defects / evidence, with `from_dict`) and the **`Verifier`** protocol —
    the 'is the delivered work actually right' seam the conductor never sees through, mirroring the
    executor seam. Concrete: `CallableVerifier` (in-process handler) and `CommandVerifier` (runs a
    command — e.g. the scaffold tests — exit 0 ⇒ verified with stdout evidence, nonzero / launch
    failure ⇒ a defect carrying the detail for the feedback loop).
  - **The gate, as a recorded transition.** After `unit.receipt` (verifying), the verifier runs:
    PASS ⇒ `unit.verified` (carrying evidence) → `unit.done`; DEFECT ⇒ a `unit.note kind=defect`
    event, then loop back to dispatch with the defects handed to the executor as `composed.feedback`,
    up to `max_retries` times; exhausted ⇒ `unit.stalled` (blocked) surfacing the outstanding
    defects. So "was this verified, and how many defect loops did it take?" is a fold over the log,
    not prose — the fix for the unenforced-verification hole.
  - **A receipt that stalls is not a defect.** When the executor itself returns a `stall` (the unit
    blocking on questions/tradeoffs), it is surfaced immediately and the verifier is never consulted —
    only *delivered* work is gated, and a stall is a first-class outcome, not a failed attempt.
  - **Backward compatible.** `verifier=None` keeps the exact P4 path (receipt accepted as-is, same
    event sequence), so all P4 tests pass unchanged; the gate is opt-in per `run`/`run_unit` call.
- **P6 — DONE.** DAG scheduling, the concurrency cap, and reflexive routing — `conductor/schedule.py`.
  13 new conductor tests (77 total, green).
  - **`Unit.depends_on` + `run_dag`.** Units declare dependency edges; `run_dag` runs them in
    dependency-ordered waves, each wave in parallel up to `concurrency` (a `ThreadPoolExecutor`),
    every unit still passing the P5 verification gate. Results come back in plan order; state is read
    back from the journal (the `unit.depends_on` edges + each unit's terminal state), so the schedule
    is reproducible from the log.
  - **Blocked-dependency cascade.** A unit whose dependency did not reach `done` (it stalled, failed
    verification, or was itself blocked) is not dispatched — it is recorded as a blocked stall
    surfacing which dep failed, and that block cascades to its own dependents. Unknown deps, duplicate
    ids, and cycles are rejected up front (Kahn's algorithm) as scheduling bugs, distinct from a
    runtime stall.
  - **Thread-safe journal.** `journal.append` now serializes its seq-assign→write under a lock, so
    the parallel workers share the one log with monotonic, non-duplicated seqs (exercised by a
    20-unit / concurrency-8 test). In-process only — a subprocess executor's child never writes the
    journal; the parent records its receipt.
  - **Reflexive routing.** Before scheduling, `reflexive_route` consults the provider about the
    conductor's OWN routing move via the *same* `providers.consult` hook, recording a
    `conductor.route` event — and the gap detector fires on the conductor's vocabulary too: a
    poor-fit routing situation (`fit==none`) surfaces a `conductor.gap` exactly as a unit's would.
    This is the "one hook applied even to the conductor's own moves" seam.
  - **Proven, not asserted.** Parallelism is shown with a `threading.Barrier` (N workers must arrive
    together or it times out), the cap with a peak-active counter, DAG order with a recorded run
    order, and the cascade by tracking which units actually executed.
