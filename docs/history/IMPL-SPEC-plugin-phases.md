# IMPL-SPEC — plugin-extensible phases/workflows (the IR)

**Status:** implementation spec. No code changed by this document. Every contract below is grounded in
current code with `file:line` references and is implementable without re-architecture. The four
following units implement Changes 4 → 1 → 2 → 3 verbatim from this spec.

Companion: `docs/plugin-phases.md` (the WHY), `docs/plugins.md` (Contributor contract), `docs/design.md`
(phase/workflow engine). Source of truth read for this spec: `workflow.py`, `workflow_run.py`,
`contributors.py`, `situation.py`, `run.py`, `conduct.py`, `orchestrate.py`, `handoff.py`,
`scripts/gate.py`, `scripts/units.py`, `journal.py`.

## Ground truth (what exists today)

- `Phase` dataclass — fields `name, stance, intent, produces, delivery` (`workflow.py:25-33`). No
  callable field. `delivery ∈ DELIVERIES = ("inline","spawn","deterministic")` (`workflow.py:22`);
  `stance ∈ STANCES = ("divergent","convergent","neutral")` (`workflow.py:21`).
- `Workflow` dataclass — `name, phases:list, edges:list, expand` (`workflow.py:35-49`). An edge is the
  4-tuple `(from, to, when, EdgeType)`; `when ∈ WHENS = ("pass","fail","always","agent-choice","feeds")`
  (`workflow.py:20`).
- `SEED_PHASES: dict[str,Phase]` (`workflow.py:79-82`), `SEED_WORKFLOWS: dict[str,Workflow]`
  (`workflow.py:116-118`). Hardcoded, no registry.
- `Contributor` protocol: `contribute` required, `hooks()` optional (`contributors.py:22-25`);
  `fire` reads `hooks` via `getattr(c,"hooks",None)` (`contributors.py:48-55`); `validate_contributor`
  (`contributors.py:57-66`); `contributors_for(root)` fail-soft loader (`contributors.py:69-89`);
  `gather` (`contributors.py:92-109`).
- `gather` derives stance as `situation.phase if situation.phase in ("divergent","convergent") else None`
  (`contributors.py:101`).
- `run_workflow` (`workflow_run.py:29-105`): sets `situation.phase = phase.name` (`:55`) and
  `composed["phase"] = phase.name` (`:57`); **always** calls `executor.run` (`:70`); reads
  `evidence["passed"]` (`:94`) and `evidence["next"]` (`:96`); `_choose_edge` (`:12-22`) matches an
  `agent-choice` edge when `when=="agent-choice" and t==choice`.
- `Situation` (`situation.py:19-68`): `phase` is stance-only, validated against
  `PHASES=("divergent","convergent","none")` in `__post_init__` (`:11,:36`); `workflow` field exists but
  is dead (`:31`); `targets` (`:29`). `run_workflow` bypasses validation because it assigns `phase` after
  `copy.copy` (no `__post_init__` re-run).
- Live drive path: `conduct.run_task` (`conduct.py:106`) builds a `Situation` (passing `workflow=`,
  `conduct.py:117`) and calls `run.run_unit` (`run.py:160`); `run_unit` calls `gather` (`run.py:164`) then
  loops `executor.run` (`run.py:184`). `handoff.pull` (`handoff.py:59`) is the inline-DAG pull path; it
  calls `gather` (`handoff.py:67`) and writes the `unit.framed` event.
- Edit lease: `handoff.pull` sets the journal `surface` from `unit.situation.targets or None`
  (`handoff.py:74`). `run_unit`'s `unit.framed` event (`run.py:165-168`) sets **no** surface. The gate
  reads `last.get("surface")` (`gate.py:54`) and enforces via `units.surface_allows` (`units.py:81-86`).
  Enforcement is complete; only the declaration seam is thin.

`run_workflow` has **no live caller** — only `tests/test_workflow.py`. This is the "built but unwired"
state the proposal names.

---

## Change 4 — contributor-declared edit lease

**Smallest change, enforcement already done.** Add a *declaration* seam and compose it into the journal
`surface`.

### Contract

New optional Contributor method (mirrors optional `hooks()`):

```python
def surface(self, situation: Situation) -> list[str] | None: ...
```

Returns a list of glob patterns (same dialect as `units.surface_allows` / fnmatch, `units.py:81-86`) that
this contributor claims as the unit's edit lease for this `situation`, or `None`/`[]` to claim nothing.
Optional: absent means "no opinion."

New composer in `contributors.py` (mirrors `gather`/`fire`):

```python
def surface_for(contributors, situation: Situation) -> list[str] | None:
    claimed: list[str] = []
    for c in contributors:
        provider = getattr(c, "surface", None)
        globs = provider(situation) if callable(provider) else None
        if globs:
            claimed.extend(globs)
    return sorted(set(claimed)) or None
```

**Composition with `situation.targets`:** a contributor-declared lease **overrides** `targets` when any
contributor claims one; otherwise fall back to `situation.targets`. Rationale: the lease is a property of
the *phase/process* the plugin owns (a divergent design phase must be barred from source regardless of
what `targets` the planner named), so a present plugin claim is authoritative; `targets` remains the
default when no plugin speaks. Multiple contributors → union (a lease can only widen across
co-present plugins, and the gate still denies everything outside the union).

### Files + lines to change

- `contributors.py:57-66` — extend `validate_contributor`: add
  `if hasattr(obj,"surface") and not callable(getattr(obj,"surface")): problems.append(...)`.
- `contributors.py` (new fn near `fire`, `:48`) — add `surface_for` as above.
- `handoff.py:74` — replace `surface=unit.situation.targets or None` with
  `surface=(surface_for(contributors, unit.situation) or (unit.situation.targets or None))`
  (import `surface_for` alongside `gather`, `handoff.py:7`).
- `run.py:165-168` — for parity on the `run_task`/`run_unit` path, add `surface=` to the `unit.framed`
  event using the same composer, so inline single-dispatch also declares a lease. (`run_unit` already has
  `contributors` and `unit.situation` in scope; compute once after `gather` at `run.py:164`.)

### Compatibility / fail-soft

- No contributor with `surface()` → `surface_for` returns `None` → `handoff.py:74` behavior is byte-for-byte
  what it is today (`targets or None`). Zero change for existing plugins.
- A `surface()` that raises must not block: wrap the per-contributor call in try/except and skip on error
  (fail-open, matching `contributors_for`'s `except Exception: continue`, `contributors.py:83`).

### Minimal test

`tests/test_contributors.py`: a stub contributor whose `surface(sit)` returns `["docs/**"]`; assert
`surface_for([stub], sit) == ["docs/**"]`; assert a contributor without `surface` is ignored; assert
`handoff.pull` writes `surface=["docs/**"]` into the `unit.framed` event even when
`situation.targets=["src/x.py"]` (override), and writes `["src/x.py"]` when no contributor claims.

---

## Change 1 — `phases()` / `workflows()` provider + registry

### Contract

Two new optional Contributor methods, shaped exactly like `hooks()` (`contributors.py:62-66`):

```python
def phases(self) -> list[Phase]: ...       # returns workflow.Phase objects
def workflows(self) -> list[Workflow]: ...  # returns workflow.Workflow objects
```

**Return real `Phase`/`Workflow` objects, not specs.** Justification: the dataclasses (`workflow.py:25-49`)
are plain, already importable, and plugins already import `Contribution` from `contributors`. Returning
objects (a) avoids inventing a parallel spec schema and a spec→object compiler, and (b) is *required* by
Change 3 — a deterministic phase must carry a Python callable (`Phase.run`, added below), which no JSON/dict
spec can hold. Fail-soft validation guards the object shape instead.

New module `registry.py` (avoids a `workflow ↔ contributors` import cycle — `workflow.py` imports neither;
`registry.py` imports both `workflow` and `contributors`):

```python
def resolve_phases(root, contributors=None) -> dict[str, Phase]
def resolve_workflows(root, contributors=None, phases=None) -> dict[str, Workflow]
```

- `contributors` defaults to `contributors_for(root)` (`contributors.py:69`) when `None`.
- `resolve_phases`: start `out = dict(SEED_PHASES)`; for each contributor with a callable `phases()`,
  for each returned `Phase` p: validate (below); **seed names always win** — skip if `p.name in SEED_PHASES`
  (log `phase.collision kind=seed`); **plugin-vs-plugin** — first loaded wins, skip a later duplicate
  (log `phase.collision kind=plugin`). Invalid or colliding → skip, never raise.
- `resolve_workflows`: identical policy against `SEED_WORKFLOWS`; additionally validate every
  `edge`/`phase` name in a workflow resolves within `phases` (the merged phase table) — a workflow naming
  an unknown phase is skipped whole (fail-soft), so a half-registered workflow can't strand the runner.

Validators (in `registry.py`, structural, never invoke callables):

```python
def validate_phase(obj) -> list[str]      # is Phase; name non-empty; stance in STANCES; delivery in DELIVERIES
def validate_workflow(obj, phases) -> list[str]  # is Workflow; name non-empty; phases non-empty;
                                                 # every edge endpoint names a known phase
```

Extend `validate_contributor` (`contributors.py:57-66`): `phases`/`workflows`, when present, must be
callable (same one-liner shape as the `hooks` check at `:64`).

### Files + lines to change

- new `registry.py` — `resolve_phases`, `resolve_workflows`, `validate_phase`, `validate_workflow`.
- `contributors.py:64` — add the two `callable` guards for `phases`/`workflows`.
- `workflow.py` — no change to `SEED_*`; they become the seed layer the resolver copies.

### Compatibility / fail-soft

- A contributor without `phases()`/`workflows()` contributes nothing to the registry; `resolve_*` returns
  exactly `SEED_*` when no plugin provides. Existing plugins unaffected.
- Any provider exception, bad object, or name collision is caught and skipped — the registry always returns
  at least the seed layer. Mirrors `contributors_for` fail-soft (`contributors.py:83-88`).

### Minimal test

`tests/test_registry.py`: stub contributor whose `phases()` returns `[Phase("design", stance="divergent")]`
and `workflows()` returns a `Workflow` naming `design`. Assert `resolve_phases(root,[stub])` contains both
seed `plan` and plugin `design`; assert a stub returning `Phase("plan",...)` does **not** override the seed
`plan` (collision skip); assert a workflow referencing an undefined phase is dropped; assert two stubs
claiming the same phase name keep the first.

---

## Change 2 — wire `run_workflow` live + resolve `Situation.workflow` + named phase

### (a) Live entry point + opt-in

`run.run_unit` (`run.py:160`) is the drive surface. A unit **opts in** by setting `situation.workflow`
(already a `Situation` field, `situation.py:31`, and already plumbed through `run_task(..., workflow=...)`,
`conduct.py:110,117`). When unset (`None`), `run_unit` keeps its current single-dispatch loop unchanged.

Add at the top of `run_unit`, after `gather` (`run.py:164`):

```python
if unit.situation.workflow:
    import registry
    wf = registry.resolve_workflows(root).get(unit.situation.workflow)
    if wf is not None:
        return run_workflow(root, unit, wf, contributors, executor, verifiers=None)
    journal.append(root, "workflow.unresolved", unit=unit.id, workflow=unit.situation.workflow)
    # fall through to single-dispatch
```

`verifiers=None` for the first cut: routing is deliberately decoupled from the preservation gate
(`design.md:142-143`), and `run_workflow` treats a missing verifier as `verified=True` (`workflow_run.py:74`).
A later unit can build the `{gate-name: Verifier}` map.

### (b) Name → Workflow

Resolution is `registry.resolve_workflows(root)[situation.workflow]` (Change 1). Unresolved name → journal
`workflow.unresolved` + fall back to single-dispatch (never crash). This retires the dead `workflow` field
by giving it its first reader.

### (c) Named-phase channel — add `situation.phase_name`, keep `phase` as stance

**Decision: add a distinct field, do not overload `phase`.** Today `run_workflow` sets
`situation.phase = phase.name` (`workflow_run.py:55`), which silently breaks two things: `gather` computes
stance from `situation.phase` (`contributors.py:101`), so a phase named `"design"` yields `stance=None`; and
every existing stance-only contributor branching on `situation.phase == "divergent"` would misread a phase
name. Overloading is a latent bug.

Changes:

- `situation.py:29-31` — add field `phase_name: str | None = None`. **Not** validated in `__post_init__`
  (free-form phase names); add it to `to_dict` (`situation.py:56-68`).
- `workflow_run.py:55` — replace `situation.phase = phase.name` with:
  ```python
  situation.phase = phase.stance if phase.stance in ("divergent","convergent") else "none"
  situation.phase_name = phase.name
  ```
  Now `situation.phase` carries a valid *stance* (so `gather`'s stance line, `contributors.py:101`, and
  every stance-only contributor keep working), and `situation.phase_name` carries the name.
- `workflow_run.py:57` — keep `composed["phase"] = phase.name` (executors already read it, `design.md:141`);
  optionally also expose `composed["stance"]` = `situation.phase`.
- `docs/plugins.md:12-18,32-33` — document `phase_name` (the named-phase channel) alongside `phase` (stance):
  "`contribute` may branch on `situation.phase_name` when a named workflow is driving; it is `None` outside a
  workflow run."

`gather` needs no change — it already reads `situation.phase` for stance, which now holds the stance again.

### Compatibility rule

- A contributor that only reads `situation.phase` (stance) is unaffected: `phase` is a stance in both the
  single-dispatch path (unchanged) and the workflow path (now stance, not name).
- A named-phase contributor reads `situation.phase_name`, which is `None` everywhere except inside
  `run_workflow`. So `phase_name is None` ≡ "no named phase; behave as before." That is the compatibility
  invariant the four following units and `uiux` code against.

### Files + lines

`run.py:164` (branch), `situation.py:29-31,56-68` (field + to_dict), `workflow_run.py:55,57` (stance/name
split), `docs/plugins.md:12-18,32-33`.

### Minimal test

`tests/test_workflow.py`: register a plugin workflow with a phase `Phase("design", stance="divergent")`;
drive `run_unit(root, Unit(sit(workflow="wf")), [named_contributor], capture_executor)`; assert the executor
saw `composed["phase"]=="design"` and the contributor's `contribute` saw `situation.phase_name=="design"`
**and** `situation.phase=="divergent"`. Assert `run_unit` with `situation.workflow=None` still runs the
single-dispatch loop (existing tests unchanged). Assert an unresolved workflow name journals
`workflow.unresolved` and falls back.

---

## Change 3 — deterministic delivery + fact-routing

### Contract

Add one optional field to `Phase` (`workflow.py:25-33`):

```python
run: object | None = None    # Callable[(root, unit, composed)] -> evidence dict, for delivery=="deterministic"
```

The callable signature and return:

```python
def phase_fn(root: Path, unit, composed: dict) -> dict:
    return {
        "passed": bool,          # required — drives advance/route (workflow_run.py:94)
        "next": "<phase-name>",  # optional — the target phase name (matched by _choose_edge as agent-choice)
        "facts": {...},          # optional — arbitrary emitted facts, recorded + surfaced
        # may also set "produces" (carried to the next phase, workflow_run.py:91)
    }
```

Branch in `run_workflow` at `workflow_run.py:70` (currently unconditional `executor.run`):

```python
if phase.delivery == "deterministic" and callable(getattr(phase, "run", None)):
    ev = phase.run(root, unit, composed) or {}
    facts = ev.get("facts") or {}
    if facts:
        journal.append(root, "phase.facts", unit=unit.id, phase=phase.name,
                       phase_index=phase_index, facts=facts)
    receipt = Receipt(outcome="result" if ev.get("passed", True) else "stall",
                      status="complete", evidence=ev)
else:
    receipt = executor.run(unit, composed)
```

(`Receipt` is importable from `run`; add the import in `workflow_run.py`.) Everything downstream is
**unchanged**: `evidence = receipt.evidence` (`:73`), `passed = evidence.get("passed", ...)` (`:94`),
`choice = evidence.get("next")` (`:96`), `_choose_edge(... choice)` (`:97`). So a deterministic phase's
`next` routes through the *existing* `agent-choice` edge mechanism (`workflow_run.py:12-22`).

**Facts routing / open-question 1 (route on an arbitrary emitted fact):** confirmed, no new mechanism. The
deterministic callable maps its fact (e.g. `library-state` eligibility) to a phase name and returns it as
`next`; the workflow author declares an `agent-choice` edge from that phase to each candidate target;
`_choose_edge` selects the edge whose `t == choice` (`workflow_run.py:16-17`). Routing on a fact ≡ the
callable choosing `next`, plus one `agent-choice` edge per branch. Note the guard: `choice` is only consulted
when `advance` is true (`passed and verified`, `workflow_run.py:95-96`), so a router phase must return
`passed=True` and set `next`.

**How a plugin supplies the callable:** via the `Phase` object it returns from `phases()` (Change 1) —
`Phase("library-state", delivery="deterministic", run=library_state.evaluate)`. The registry carries the
object with its callable intact (another reason Change 1 returns objects, not specs).

### Compatibility / fail-soft

- Seed deterministic phases `VERIFY`/`COVERAGE_DIFF` (`workflow.py:66-67,75-77`) have `delivery="deterministic"`
  but **no** `run` callable → the `and callable(...)` guard is false → they take `executor.run` exactly as
  today. No seed-workflow behavior change.
- Callable raises → catch, journal `phase.error`, synthesize `Receipt(outcome="stall")` so the workflow halts
  cleanly rather than propagating. (Matches the runner's fail-soft posture.)

### Minimal test

`tests/test_workflow.py`: a `Phase("route", delivery="deterministic", run=lambda r,u,c: {"passed":True,
"next":"b","facts":{"eligible":"b"}})` in a workflow with `agent-choice` edges `route→a` and `route→b`;
assert traversal goes `route→b`, assert a `phase.facts` event with `eligible=="b"` was journaled, and assert
`executor.run` was **not** called for `route`.

---

## The four open questions (resolved)

1. **Conditional/looping edges routing on an emitted fact** — *in scope, resolved by Change 3.* Mechanism:
   deterministic phase returns `next=<phase-name>`; workflow declares an `agent-choice` edge per branch;
   `_choose_edge` matches `t==choice` (`workflow_run.py:16-17`). Looping (e.g. B4's loop back to
   `library-state`) is the same `agent-choice` edge pointing back, bounded by the existing
   `max_phase_loops` guard (`workflow_run.py:48-51`).
2. **Deterministic phase return contract** — *in scope, resolved by Change 3.* `dict` with required
   `passed: bool`, optional `next`, `facts`, `produces`.
3. **Screenshot capture** — *out of scope for these four changes.* It is ordinary spawn/tool work inside a
   `delivery=="spawn"` phase (the spawn drives the app and captures), and the plugin's `close`/`verify`
   hook (`contributors.py:48-55`) files the manifest into plugin-owned state. No phase primitive, no engine
   change. The four changes already suffice: a `spawn` phase + a `hooks()` filer.
4. **Bootstrap trigger owner** — *out of scope for these four changes; operator-owned for now.* The trigger is
   an explicit operator invocation that sets `situation.workflow="design-bootstrap"` (already plumbed via
   `run_task(workflow=...)`, `conduct.py:110,117`, and resolved by Change 2). Auto-surfacing (accretion
   detecting `has-ui` + no libraries and proposing the workflow) is a *later* accretion feature, not one of
   these four core seams — the proposal itself lists it as an open question, not a change.

---

## Build order

Follow the proposal's order (`plugin-phases.md:180-182`), each independently landable:

1. **Change 4** (lease declaration) — smallest, enforcement done; touches `contributors.py`, `handoff.py:74`,
   `run.py:165`. No dependency on the others.
2. **Change 1** (registry) — new `registry.py`, `contributors.py:64`. Depends on nothing; unblocks 2 and 3.
3. **Change 2** (wire + named phase) — the keystone; `run.py:164`, `situation.py`, `workflow_run.py:55`,
   `docs/plugins.md`. Depends on Change 1 (needs `resolve_workflows`).
4. **Change 3** (deterministic delivery) — `workflow.py` (`Phase.run`), `workflow_run.py:70`. Depends on
   Change 1 (the callable rides the `Phase` object) and is only observable once Change 2 makes `run_workflow`
   reachable.

## Risk notes

- **`Phase.run` as a dataclass field holding a callable** — fine for an in-process registry, but a `Phase`
  is no longer trivially JSON-serializable. `journal`/`to_dict` never serialize `Phase` objects (they log
  names), so no serialization path breaks; keep it that way (log `phase.name`, never the object).
- **Stance/name split (Change 2c) is the highest-blast-radius edit** — it changes what `situation.phase`
  holds inside `run_workflow`. The compatibility invariant (`phase`=stance always; `phase_name`=name or
  `None`) must be covered by a test that a stance-only contributor is unaffected, or existing plugins
  silently misread. This is the one change that can regress live behavior; land it with the test in Change 2.
- **Lease override vs. intersect (Change 4)** — this spec chooses *override* (plugin claim wins over
  `targets`). If a future planner needs `targets` to *narrow* a plugin lease, switch the composer to
  intersect; the seam (`surface_for`) is the single place to change. Flagged, not blocking.
- **`verifiers=None` on the live workflow path (Change 2a)** — routing is decoupled from the preservation
  gate by design (`design.md:142-143`); acceptable for the first cut, but means a workflow's `carry`/`extract`
  gates are recorded, not enforced, until a verifier map is wired. Note it in the unit that lands Change 2.
