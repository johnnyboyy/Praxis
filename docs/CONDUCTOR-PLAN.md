# The conductor plan — toward the independent ideal

The north star for reshaping this repo into two genuinely independent systems that meet at a clean
seam. I (the agent) execute this in small, testable phases; this file is both the roadmap and the
running progress ledger. Steer by editing the "Target contracts" or reordering phases.

## Start here (cold-boot briefing for a fresh session)

**This reshape is COMPLETE.** Every phase (P1–P9) plus the PG promotion loop is done, committed, and
green; the post-roadmap questions are resolved (see the ledger). `~/jdev/skills-pi` (the Pi-dedicated
fork of a praxis+corpora system) is the live, git-tracked Claude Code surface. Read this whole file
for context; the contracts and the progress ledger are authoritative — do not re-derive them, and
don't re-open a settled phase or resolved question without a new steer.

- **Layout:** `conductor/` (the new judgment-agnostic core being built — start here), `corpora/` (the
  judgment engine, becomes a provider), `praxis/` (legacy process scripts, retired phase by phase),
  `pi-extension/praxis/` (the Pi extension — the stable outer shell; swap its guts conductor-ward),
  `.praxis/` (per-root state: journal.jsonl, config, phases, workflow.json).
- **Run tests:** `cd conductor && python3 -m unittest discover -s tests` (and likewise in `praxis/`,
  `corpora/`). Keep all green.
- **Working rule:** nothing old is removed before its replacement passes tests (see Migration). Small
  phases; checkpoint after each; update the progress ledger at the bottom.
- **State now:** P1–P9 + PG done — the roadmap is complete. P1 = `conductor/journal.py` (the event-log source of truth + gap
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
  routing move (same hook, same gap detector). P7 = `conductor/views.py`: handoff, chunk-ledger, and
  cost as pure folds over the journal (the separate primitives become views), and
  `SubprocessExecutor` captures the child run's cost. P8 = corpora decoupling: corpora exposes a
  `manifest` capability (each domain's subject / applies-when / universal), and
  `providers.select_by_features` maps a situation's features (subject + project_shape predicates) →
  domains natively — no unit-of-work string. P9 = guardrails as editable policy (`conductor/policy.py`,
  read from `.praxis/conductor.json`) feeding `run`/`run_dag`, and the engine-plugin hop collapsed to
  a direct corpora binding (`conductor/adapters.py` calling `corpus.py`). Contracts settled through
  the gap-harvest refinement. **The spine and all refinements (P1–P9) are done.**
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

## Phases (small, testable; each enables the next) — ALL DONE ✓

- [x] **P1 — Event log as source of truth.** `conductor/journal.py`: append + fold-to-state + summary +
  `open_unit`. The keystone; everything reads state from here. *(tests)*
- [x] **P2 — Gate reads the log.** Rewrite the edit gate to consult the journal fold; retire the
  tmp session-stamp files + freshness windows (vestigial in the Pi fork). *(tests + live)*
- [x] **P3 — Provider seam + situation schema.** `conductor/situation.py` + `conductor/providers.py`;
  wrap corpora as a provider behind `compose`. The conductor consults the hook, not a hardcoded
  engine call. Degrades with a null provider. *(tests)*
- [x] **P4 — Conductor core (linear).** `conductor/run.py`: iterate a plan's units, consult the provider,
  dispatch via an **executor** (inline / spawn), write receipts as events. *(tests + live)*
- [x] **P5 — Verification gate.** Recorded verify transition; defect → feedback loop-back, bounded
  retries, then surface. Fixes the unenforced-verification hole; hardens `test-scaffold`'s loop-back.
- [x] **P6 — DAG + concurrency + reflexive routing.** `depends_on` scheduling, concurrency cap
  (parallel-then-verify enforced); the conductor consults judgment about its *own* routing.
- [x] **P7 — Fold in receipts/handoff/cost; retire redundant primitives.** Handoff/chunk-ledger become
  views over the journal; cost/tokens captured from the child run. *(views built; the trace was the
  one genuine duplicate and was migrated — chunk-ledger/handoff are lifecycle machinery, left as-is,
  see the ledger.)*
- [x] **P8 — Corpora decoupling.** Migrate corpora selection from `units-of-work` strings to feature
  predicates; the provider maps situation features → domains natively. *(the conductor composes
  feature-first via `select_by_features`; corpora keeping its own `units-of-work` was accepted, see
  the ledger.)*
- [x] **PG — Gap-surfacing & vocabulary accretion (cross-cutting; the conductor's ratify gate).** The
  *surfacing hook* lands early in **P3** (the provider reports `fit`; a forced/weak match emits
  `conductor.gap` and routes to `unclassified` instead of composing the junk drawer). The *promotion
  loop* — operator reviews surfaced gaps and mints a new verb/phase/workflow — is its own step, built
  once real gaps have accumulated (first-attempt-is-first-draft, applied to the vocabulary itself).
- [x] **P9 — Guardrails as policy + final de-cruft.** Operator guards become editable policy; collapse
  the engine-plugin hop to a direct provider call.

Also done beyond the numbered phases: a capstone end-to-end test of the whole vertical, the workflow
trace migrated onto the journal, skills-pi git-initialized and made the live Claude Code surface.

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
- **P7 — DONE.** Handoff, chunk-ledger, and cost folded into views over the journal; cost captured
  from the child run. 8 new conductor tests (85 total, green).
  - **`conductor/views.py` — three pure folds.** `handoff(root, unit)` (the terminal artifact a
    downstream consumer like corpora reads: outcome, verification evidence, domains composed,
    surfaced items, defects, attempts, cost — folded from the unit's events, not a written file);
    `ledger(root)` (the chunk-ledger, one row per unit in first-seen order); `cost(root)` (the cost
    rollup across every receipt — tokens/usd/tool_calls, total and per-unit, with retries summing).
    Because they are folds, the separate handoff/chunk-ledger/cost files a process layer kept are
    redundant — re-derived from the log rather than maintained alongside it.
  - **Cost captured from the child run.** `SubprocessExecutor` gains a `cost_extractor(stdout,
    stderr)` that pulls token/usd usage out of a child's output (e.g. a `pi` spawn's stream) when
    the child doesn't fold cost into its receipt; an explicit `cost` in the receipt JSON always
    wins. `run`/`run_dag` now return the cost rollup alongside the deliver-vs-stall summary.
  - **Surface-side retirement deferred (as noted):** wiring praxis's file-based handoff + chunk
    ledger to consume these views (deleting the standalone files) is the surface integration; the
    core proves the artifacts are recoverable from the journal.
- **P8 — DONE.** Corpora decoupling — selection by situation features, not a unit-of-work string.
  9 new conductor tests (94 total, green); corpora's 167 tests untouched (the change is additive).
  - **corpora exposes a `manifest` capability** (the existing `manifest` verb, newly registered in
    `corpora.json`): each domain's `subject`, `applies-when` predicates, and `universal` flag as
    JSON — the machine-readable feature index a process layer selects against.
  - **`providers.select_by_features(manifest, situation)`** maps a situation's features onto that
    index natively: universal domains always; otherwise a non-universal domain matches when its
    `subject` equals the situation's subject AND its applies-when predicates hold for the situation's
    `project_shape` (predicate evaluation mirrored conductor-side). A `fit==none` situation composes
    universals only. No unit-of-work string anywhere on this path — the decoupling.
  - **`CorporaProvider` gains a feature mode** (`manifest_fn`) alongside the legacy unit-of-work
    mode (`select_fn`); it raises if given neither. `RealFeatureSelectionTest` proves it against the
    real corpora manifest: subject=coding on the self-host shape composes prose-craft + the
    framework-agnostic coding domains, and excludes design domains and framework-gated ones.
  - **Deferred (bigger corpora migration):** corpora's OWN `select` verb still uses `units-of-work`
    (its 167 tests rely on it), so domains keep both fields for now. Re-authoring domains to drop
    `units-of-work` and making corpora's native selection feature-only is a larger corpora-side
    migration; P8 delivers the decoupled path the conductor composes through.
- **P9 — DONE.** Guardrails as editable policy + the engine-plugin hop collapsed. 14 new conductor
  tests (108 total, green). **This closes the roadmap.**
  - **`conductor/policy.py`.** The concurrency cap, retry bound, and a `verify_required` guard are a
    `Policy` the operator edits at `<root>/.praxis/conductor.json`, not loop constants; `run` and
    `run_dag` read their defaults from `load_policy(root)` (a missing/corrupt file degrades to the
    historical defaults, so nothing changes until the operator edits it). An explicit argument always
    overrides the policy.
  - **`conductor/adapters.py` — the direct provider binding.** `corpora_provider(root)` builds a
    `CorporaProvider` by calling `corpus.py`'s read verbs (`manifest`/`select`/`emit-spawn-parts`)
    DIRECTLY — no praxis engine-plugin manifest resolution, no generic argv builder, no
    `engine.call_json` indirection. One subprocess straight to the engine, the hop collapsed. It is
    the wiring layer (it knows corpora's CLI); the core modules still import neither praxis nor
    corpora. A broken binding degrades to empty domains rather than raising.
  - **Proven live.** `DirectBindingComposeTest` composes real corpora through the direct adapter
    (feature mode: prose-craft + framework-agnostic coding domains, framework-gated ones excluded);
    the policy tests pin `run_dag`'s concurrency to 1 via a `conductor.json` and confirm the retry
    bound comes from policy with an explicit arg overriding.
  - **Left as noted:** the vestigial `clear_session_stamps` in praxis's `close_frame_marker` is
    harmless and kept (removing it touches praxis close-side tests for little gain); the engine-plugin
    path itself stays for a project that registers a *different* engine — only the conductor's own
    corpora access is now direct.

- **PG (promotion loop) — DONE.** The vocabulary-accretion half of the gap mechanism — the
  conductor's ratify gate. `conductor/accretion.py`. 13 new conductor tests (121 total, green).
  - **`promotable(root, min_count)`** — the mint signal: `journal.gap_candidates` suggestions that
    have recurred ≥ `min_count` times and aren't already known vocabulary. Real gaps, accumulated,
    ready for the operator to judge.
  - **`mint(root, vocabulary, term)`** — promote a suggestion into real vocabulary by recording a
    `conductor.mint` event (idempotent; a seed or already-minted term is a no-op; unknown vocabulary
    rejected). The accreted vocabulary is a fold, not a registry: **`vocabulary(root)`** replays the
    mints on top of the built-in seeds, and **`is_known`** / **`minted`** / **`review`** read it.
  - **Closed loop, proven.** A recurring `fit==none` suggestion surfaces as `promotable`; minting it
    makes it `is_known` and drops it from `promotable` (resolved), while the base seeds are retained
    — the surfacing half (P3) and the promotion half now meet. Where corpora accretes judgment, the
    conductor accretes process vocabulary, both through a ratify gate.

## Status: roadmap complete
All nine phases plus the PG promotion loop are done and every suite is green (conductor 123,
praxis 228, corpora 167). The conductor is a working judgment-agnostic core — event-log source of
truth, journal-first edit gate, provider seam with the full gap mechanism (surface → recur → mint),
linear + DAG execution with a recorded verification gate, views over the log, feature-based corpora
selection, and editable policy — with corpora wrapped as one provider behind a direct binding. A
capstone `test_end_to_end.py` exercises the whole vertical composed.

### Post-roadmap surface/migration items — all resolved
- **Workflow trace → journal view: DONE.** It was the one genuine view-duplicate (it recomputed the
  fold's deliver-vs-stall summary). `record_outcome` bridges spawn outcomes into the journal;
  `trace()`/`work_status` are now views over `journal.fold` + `views.ledger`; `trace.jsonl` retired
  on both surfaces.
- **chunk-ledger + handoff → views: EVALUATED, left as-is.** Both are genuine write-lifecycle
  machinery, not view-duplicates. The chunk-ledger exists for its write-time reconciliation gates
  (workstream match; the handoff's self-reported `domains-loaded` vs a live `compose()`; the ordering
  gate) and the `next` pointer / drift-verify — none are folds. The handoff is create/validate/close
  over an *authored, plugin-schema'd file*; `views.handoff` is a different artifact (a derived
  receipt-summary, not authored input). Migrating either would relocate storage while keeping every
  gate — churn for no semantic gain. Only additive idea for later: emit a `chunk.closed` event +
  enrich `record_outcome` with uow/workstream so receipts are joinable — a feature, not a retirement.
- **corpora units-of-work retirement: NOT pursued — decoupling accepted as done.** units-of-work is
  corpora's `unit`/`phase` selectivity axis, orthogonal to `applies-when` (project shape) and richer
  than the situation's `task_kind` seeds (8 of 12 values — `ratify`, `retrospect`, `verify-scaffold`,
  `design-*`… — don't reduce to create/change/explore). The genuine decoupling already shipped in P8:
  the conductor composes through `select_by_features`, which never touches units-of-work. corpora's
  own `select` keeping units-of-work is its legitimate internal vocabulary, not a coupling to fix;
  deleting it would lose selectivity (e.g. `ratify-gate` would load for every process task), and a
  faithful "promote it to a `unit` feature predicate" refactor is behaviorally identical to today
  while churning ~25 test fixtures. **Operator steer:** the original worry — a task/phase overstuffed
  with domains, or one phase spanning many domains — is itself the *signal that the phase/task is
  drawn too broadly*, which the gap mechanism already surfaces; so let the selection vocabulary grow
  organically through use rather than force a schema migration now.

### Live surface — verified post-restart
The MCP server was restarted and the whole live flow was exercised end-to-end through it on an
isolated root: `begin_work` → `record_outcome` → `work_status` (its trace is now the journal view:
`views.ledger` + `journal.fold` summary) → `close_work`. The journal recorded `unit.framed →
unit.receipt → unit.closed`, no `trace.jsonl` was written, and skills-pi's own journal was untouched.
The standing "MCP needs a restart to pick up `record_outcome` + the journal-view `trace()`" caveat is
closed. Nothing outstanding.
