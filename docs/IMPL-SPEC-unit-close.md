# IMPL-SPEC: per-unit `unit-close` hook step

Status: SPEC (the IR). No code changes here. Every contract below is pinned to real
code with `file:line` refs. Implementation-ready.

---

## 0. Problem (grounded)

The `close` hook fires **once per run** with an **empty** `HookContext` — no unit, no
receipt:

- `run.py:241` — `fire(contributors, "close", HookContext(root=root, step="close"))`
- `schedule.py:133` — same call at the end of the DAG walk.

By contrast the `verify` hook is fired with a **populated** context (`run.py:212-215`):
`HookContext(root=root, step="verify", unit=unit, receipt=receipt.to_dict(), verdict={...})`.

`HookContext` already carries the fields we need — they are simply never populated at the
close site:

- `contributors.py:33-35` — `unit`, `receipt`, `verdict` fields (all default `None`).
- `contributors.py:37-39` — `add_note` keys the journal entry on `getattr(self.unit, "id", None)`.

So a plugin whose per-unit logic needs the unit's own receipt cannot get it from `close`.
The live proof is uiux: its `_on_close` reads drift/decision/screenshot signals off
`ctx.receipt` (`uiux_plugin.py:437,441,463`), but at the real batch-close seam `ctx.receipt`
is `None`. The uiux e2e suite even documents this gap and works around it by manually
firing a synthetic receipt-bearing `"close"` context instead of driving the real seam
(`praxis-plugins/uiux/tests/test_design_sync_e2e.py:10-14`).

**Fix:** add an additive step **`unit-close`**, fired **once per unit** with the unit's
final receipt. Leave `close` exactly as-is.

---

## 1. Step name

**`unit-close`** (confirmed). Rationale: it reads as the per-unit twin of the batch
`close`; it is not a stance or phase name (so it never collides with `situation.phase` /
`phase_name` channels); and it composes with the existing `verify`/`close` vocabulary in
`plugins.md:42-45`. No code currently matches on the literal `"unit-close"` (verified:
`grep` for `unit-close`/`unit_close` across `praxis/` and `praxis-plugins/` returns
nothing but this spec), so the name is free.

---

## 2. The single dispatch invariant: fire inside `run_unit` / `run_workflow`

`run_unit` (`run.py:160`) is the **one** per-unit entry point on **every** path. Trace:

- **single-dispatch batch** — `run()` maps `run_unit` over `plan.units` (`run.py:239`).
- **DAG / conductor** — `run_dag` submits `run_unit` per runnable unit (`schedule.py:122`).
- **orchestrate/replan** — `run_orchestrated` calls `run_dag` for the fan-out
  (`orchestrate.py:49`) and `run_unit` directly for each fix unit (`orchestrate.py:77`);
  `replan` funnels back through `run_orchestrated` (`orchestrate.py:97`).
- **cascade** — the detached worker calls `orchestrate.run_orchestrated`
  (`cascade.py:88-89`), i.e. the same two sites above.
- **single MCP dispatch** — `conduct` calls `run_unit` directly (`conduct.py:134`).

Therefore **firing `unit-close` inside the per-unit function guarantees exactly-once per
unit on all paths** — no caller needs to change, and multi-unit paths get one fire per
unit for free (N units ⇒ N fires), independent of the single batch `close` each
orchestrator still fires at the end.

`run_unit` has two internal completion paths; pin one fire site on each:

### 2.1 Single-dispatch path (executor produces the receipt)

The single-dispatch path has **four** terminal `return _result(...)` sites, each with the
unit's final `receipt` in hand:

- `run.py:201` — stall from executor (`receipt` = the stalled receipt), verdict n/a.
- `run.py:206` — done, no verifier (`receipt` complete), verdict n/a.
- `run.py:218` — done, verified (`receipt` complete + a `Verdict`).
- `run.py:227` — stall after retries exhausted (`receipt` = last attempt), verdict n/a.

**Do not** sprinkle four `fire(...)` calls. Introduce one `_finish(...)` closure alongside
`_result` (`run.py:181-186`) that fires exactly once, then returns `_result(...)`, and
replace each `return _result(...)` with `return _finish(...)`:

```python
def _finish(outcome, status, receipt, verified, attempts, defects, verdict=None):
    fire(contributors, "unit-close", HookContext(
        root=root, step="unit-close", unit=unit,
        receipt=receipt.to_dict() if receipt else None,
        verdict=verdict))
    return _result(outcome, status, receipt, verified, attempts, defects)
```

- `run.py:201` → `return _finish("stall", receipt.status, receipt, None, attempt + 1, [])`
- `run.py:206` → `return _finish("result", receipt.status, receipt, None, attempt + 1, [])`
- `run.py:218` → `return _finish("result", receipt.status, receipt, True, attempt + 1, [], verdict={"verified": True, "defects": verdict.defects, "evidence": verdict.evidence})`
- `run.py:227` → `return _finish("stall", "blocked", receipt, False, max_retries + 1, feedback)`

`verdict` is populated **only where a `Verdict` is in hand** — the verified return
(`run.py:209-218`). Elsewhere it is `None` ("verdict = if available", per the pinned
contract). `receipt` is `None`-guarded because the retry-exhausted path can in principle
carry a `None` receipt if the first attempt never produced one (`run.py:189` initializes
`receipt = None`).

The `receipt=receipt.to_dict()` shape is deliberately **identical** to the existing
`verify` fire (`run.py:213`) — canonical 6-key `Receipt.to_dict()` (`run.py:30-32`:
`outcome`, `status`, `surfaced`, `evidence`, `cost`, `tool_calls`). The free-form
`evidence` dict is the payload channel (see §5).

### 2.2 Workflow path (delegated to `run_workflow`)

When `unit.situation.workflow` resolves, `run_unit` does `return run_workflow(...)` and
**never reaches** the single-dispatch returns (`run.py:171-176`). So the workflow fire
must live **inside `run_workflow`**, at its **single** return point (`workflow_run.py:209`
— the other `return`s in that module are in `_choose_edge`/`_incoming` helpers, not the
walk). Firing there — not in `run_unit` around the delegated call — keeps exactly-once and
avoids a double-fire if the branch is ever refactored.

If the workflow is **unresolved** (`registry.resolve_workflows` misses it), `run_unit`
falls through to single-dispatch (`run.py:177-179`), and §2.1 fires. So: resolved ⇒
`run_workflow` fires once; unresolved ⇒ `_finish` fires once. Never both.

**Workflow fire (at `workflow_run.py:209`, just before `return`):**

```python
fire(contributors, "unit-close", HookContext(
    root=root, step="unit-close", unit=unit,
    receipt=final_receipt, verdict=None))
return {"unit": unit.id, "workflow": workflow.name, "phases": walked,
        "phase_fits": phase_fits, "gaps": gaps,
        "final": final_receipt, "receipt": final_receipt}
```

`verdict=None`: workflow verification is per-phase/per-gate (`workflow_run.py:147-149`),
not a single unit verdict, so there is no unit-level `Verdict` to carry.

---

## 3. Workflow "final receipt" — the aggregate decision

**Decision: the workflow unit's final receipt is an AGGREGATE of walked-phase evidence,
not the literal last-phase receipt.**

Why not the literal last phase (`result["final"]` today = `receipt.to_dict()` of the last
phase walked, `workflow_run.py:169,211`): uiux and every design workflow route to a
terminal seed **`close`** phase (`workflow.py:82` `CLOSE = Phase("close", …)`; e.g.
`uiux_plugin.py:135,142,187` all end `… -> close`). That final `close` phase is an inline
"finalize the unit" pass — it carries **none** of the drift/decision/screenshot signals a
per-unit consumer needs; those were produced **mid-walk** by `design-decision-review` /
`*-library-sync` phases (`uiux_plugin.py:79` `produces="decision"`, sync phases produce
`ui-library`/`ux-library`). Handing the consumer only the last phase's receipt would drop
exactly the payload this feature exists to deliver.

**Aggregate shape.** `run_workflow` already walks every phase, holding each phase's
`receipt` (`workflow_run.py:145` executor / `141-143` deterministic) and its
`evidence = receipt.evidence or {}` (`workflow_run.py:151`). Accumulate a merged
`evidence` across the walk and synthesize one receipt-shaped dict:

- Maintain `agg_evidence: dict = {}` in the walk; after each phase, if `evidence` is a
  dict, `agg_evidence.update(evidence)` — **walk order, last-writer-wins per key** (a later
  phase's `ui-drift` supersedes an earlier one; keys no phase overwrites persist).
- After the loop, build:

```python
final_receipt = {
    "outcome": receipt.outcome if receipt else "stall",   # terminal phase outcome
    "status":  receipt.status  if receipt else "blocked",
    "surfaced": list(receipt.surfaced) if receipt else [],
    "evidence": agg_evidence,        # <-- merged across the whole walk
    "cost": receipt.cost if receipt else None,
    "tool_calls": receipt.tool_calls if receipt else 0,
}
```

This is a `Receipt.to_dict()`-shaped dict (`run.py:30-32`), so consumers treat the
single-dispatch receipt and the workflow receipt **identically**: read domain payload from
`receipt["evidence"]`.

**Backward-compat for `run_workflow`'s return:** keep the existing `"final"` key pointing
at this aggregate (its current consumers read it as "the result"; the aggregate is a strict
superset — same six keys, richer `evidence`) and **add** a `"receipt"` alias for clarity.
`"final"` was previously the last-phase receipt; the only behavioral delta is a merged
`evidence`, which no current reader depends on field-by-field (verified: `grep` for
`["final"]`/`.get("final")` shows result-shape plumbing only, no per-key evidence reads).
If a reader must keep exact last-phase semantics, preserve the old value under
`"final_phase"`; default recommendation is to fold it into the aggregate.

---

## 4. `close` stays unchanged

- `run.py:241` and `schedule.py:133` keep firing `close` once, end-of-run, empty context.
- No semantics change; every existing `close` hook keeps its current inputs.
- `unit-close` is **purely additive** — a contributor with only a `close` hook is
  unaffected; a contributor with only a `unit-close` hook never sees `close`.

`fire` already no-ops for any contributor lacking a step (`contributors.py:48-54`:
`table.get(step)` → `None` → skipped), so introducing a new step name requires **zero**
change to `fire`, `validate_contributor` (`contributors.py:72-87`, structural only), or the
`hooks()` contract.

---

## 5. `plugins.md` doc addition

Edit the "Steps praxis fires" section (`docs/plugins.md:40-45`). Replace the two-item list
with three, and frame `unit-close` as the general per-unit hook:

> ### Steps praxis fires
>
> Praxis fires three named steps through `hooks()`:
>
> - `verify` — after a unit is verified as passing (once per verified pass). Context
>   carries `unit`, `receipt`, and the `verdict`.
> - `unit-close` — **once per unit**, as that unit finishes (whatever its outcome), on
>   every dispatch path (single-dispatch, DAG, orchestrate/cascade, and workflow-driven).
>   Context carries the `unit` and its **final `receipt`** (for a workflow-driven unit, an
>   aggregate whose `receipt["evidence"]` merges every phase's evidence). This is the
>   general per-unit seam any contributor can ride — e.g. a **uiux** staleness/drift
>   recorder that bumps counters and marks surfaces stale off the unit's receipt; or a
>   **corpora** per-unit harvest / a **metrics** recorder that folds each unit's
>   `receipt["cost"]` and `tool_calls` into a running tally.
> - `close` — once at the end of a run (batch/end-of-run event). Empty context (no unit,
>   no receipt). Use it for run-level rollups, not per-unit work.

Also update the worked example prose if desired (`plugins.md:99`) — no code change needed
there; the `close` lambda still illustrates the batch hook.

---

## 6. uiux migration

Move uiux's per-unit logic from `close` to `unit-close`. The logic body is unchanged; only
the **step key** and the **receipt read paths** change.

### 6.1 hooks() table (`uiux_plugin.py:426-429`)

```python
def hooks(self) -> dict:
    return {"unit-close": self._on_close}
```

uiux keeps **no** `close` hook. Everything `_on_close` does is per-unit (drift bump/reset,
mark_stale, decision filing, per-library cadence note) and needs the receipt — none of it
is a run-level rollup. Dropping `close` also removes the current dead path where uiux's
`close` hook fired with `ctx.receipt is None` and silently no-op'd its drift/decision
branches.

### 6.2 Receipt read paths — read from `evidence`

Today `_on_close` reads top-level keys: `receipt.get("ui-drift")` (`uiux_plugin.py:437`),
`receipt.get("decision")` (`:441`), `receipt.get("screenshots")` (`:463`). Under the pinned
contract the receipt is `Receipt.to_dict()`-shaped (§2.1) / the aggregate (§3), whose
free-form payload lives under **`evidence`** (`Receipt.to_dict` only preserves the six
canonical keys — top-level custom keys are dropped by `Receipt.from_dict`, `run.py:34-38`).
So the design phases emit `ui-drift`/`decision`/`screenshots` inside `evidence`, the
workflow aggregate merges them there (§3), and `_on_close` reads:

```python
receipt = ctx.receipt or {}
ev = receipt.get("evidence") or {}
drift    = ev.get("ui-drift")   or {}     # was receipt.get("ui-drift")
decision = ev.get("decision")   or {}     # was receipt.get("decision")
captured = list((ev.get("screenshots") or {}).get("captured") or [])   # was receipt.get("screenshots")
```

Everything downstream is unchanged: `screens`/`components`/`global`/`tokens` off `drift`
(`uiux_plugin.py:438-439,469`), the drift counter reset/bump keyed on `phase_name`
(`:449-455`), `mark_fresh`/`mark_stale` (`:462-464,470-472`), `_file_decision` +
deferred resolve (`:475-476,500-527`), and the `design-sync due` cadence note via
`ctx.add_note` (`:492-497`). `phase_name`/`targets` still come off
`ctx.unit.situation` (`:434-436`) — unchanged, since `unit-close` populates `ctx.unit`.

### 6.3 uiux test updates

The uiux hook tests construct `HookContext(step="close", …, receipt={"ui-drift": {...}})`
with top-level keys and fire `"close"`:

- `tests/test_uiux_hooks.py:75-76,85-86,104-105,167-168,217`
- `tests/test_design_sync_routing.py:175,188,200-201`
- `tests/test_design_sync_e2e.py:144-147,178` (and its header note `:10-14`)

Update each to `step="unit-close"`, `fire(..., "unit-close", ...)`, and nest the payload:
`receipt={"evidence": {"ui-drift": {...}}}` / `{"evidence": {"decision": {...}}}` /
`{"evidence": {"screenshots": {"captured": [...]}}}`. The e2e header note (`:10-14`) that
documents "batch close fires an empty ctx, so the live seam is `fire` with a
receipt-bearing context" is now **obsolete** — the live seam is `run_unit`/`run_workflow`
firing `unit-close` with the real receipt; rewrite it to drive that seam directly.

---

## 7. Backward-compat rules (summary)

1. `close` unchanged — same site, same empty context (`run.py:241`, `schedule.py:133`).
2. `unit-close` is additive — `fire` no-ops for contributors without the step
   (`contributors.py:52-54`); no contract/validation change.
3. `HookContext` needs **no** new field — `unit`/`receipt`/`verdict` already exist
   (`contributors.py:33-35`).
4. `run_workflow`'s `"final"` remains present; its `evidence` becomes the merged aggregate
   (strict superset), with `"receipt"` added as an alias (§3).
5. Receipt shape for `unit-close` == the `verify` shape (`Receipt.to_dict()`), so any rider
   reads payload from `receipt["evidence"]` uniformly across single-dispatch and workflow.

---

## 8. Minimal tests

**T1 — core fire, single-dispatch, exactly once (`praxis/tests/`).**
Register a contributor whose `hooks()` returns `{"unit-close": recorder}` where `recorder`
appends `(ctx.unit.id, ctx.receipt)` to a list. Run a 1-unit `run(plan, …)` with a passing
inline executor + a verifier. Assert: recorder called exactly once; `ctx.unit.id` matches;
`ctx.receipt["outcome"] == "result"`; `ctx.verdict["verified"] is True`. Add a stalling
executor variant: recorder still fires once, `ctx.receipt["outcome"] == "stall"`,
`ctx.verdict is None`.

**T2 — one fire per unit on the DAG path.**
2-unit plan (one depends on the other) through `run_dag`. Assert recorder fired exactly
twice, once per unit id; and the batch `close` recorder (separate hook) fired exactly once.

**T3 — workflow aggregate receipt.**
Drive a `run_workflow` walk where an early phase's evidence carries
`{"ui-drift": {"screens": ["s"]}}` and the terminal `close` phase carries none. Assert the
`unit-close` `ctx.receipt["evidence"]["ui-drift"]["screens"] == ["s"]` (proves mid-walk
signal survives the aggregate) and `ctx.receipt` is 6-key shaped.

**T4 — uiux end-to-end via the real seam.**
Rewrite `test_design_sync_e2e.py` scenario 1 to run a `feature-design` unit through
`run_unit` with `uiux` config-registered, and assert the `unit-close`-driven side effects
(surface marked stale, `ui_drift`/`ux_drift` bumped, "design-sync due" note) WITHOUT
manually firing a hook — proving the live seam threads the receipt.

**T5 — `close` regression.**
A contributor with only a `close` hook still fires once at end-of-run with
`ctx.receipt is None` and `ctx.unit is None` (guards the additive-only guarantee).

---

## 9. Build order

1. **Core fire (praxis).** Add `_finish` in `run_unit` and repoint the four returns
   (`run.py:181-227`); add the aggregate + `unit-close` fire in `run_workflow`
   (`workflow_run.py:145-211`). Land T1-T3, T5. No consumer change yet — `unit-close`
   simply has no riders, so behavior is inert.
2. **uiux move.** Flip `hooks()` to `unit-close`, drop `close`, repoint reads to
   `evidence` (`uiux_plugin.py:426-463`); update uiux tests (§6.3). Land T4.
3. **Docs.** Update `plugins.md:40-45` (§5).
4. **e2e.** Run the full uiux + praxis suites; confirm the obsolete e2e workaround is gone.

---

## 10. Risk notes

- **Exactly-once on every path.** The whole guarantee rests on `run_unit` being the sole
  per-unit entry point and each of its two completion paths firing once. The single-dispatch
  risk is a missed/duplicated return — mitigated by routing **all four** returns through one
  `_finish` (§2.1). The workflow risk is double-fire if someone also fires in `run_unit`'s
  workflow branch — **do not**; the only workflow fire is at `workflow_run.py:209`.
- **Unresolved-workflow fall-through.** `run.py:177-179` falls through to single-dispatch
  when the workflow name misses; `_finish` covers it. Confirm no path both delegates to
  `run_workflow` and falls through (it does not — the fall-through only runs when
  `wf is None`).
- **Workflow "final receipt" definition.** Choosing the aggregate over the last-phase
  receipt is load-bearing for uiux (§3); the last phase is the inert `close` seed phase.
  The compat risk is `run_workflow`'s `"final"` gaining merged evidence — a superset, but
  audit any consumer that asserts exact last-phase evidence (none found).
- **Receipt payload channel.** uiux's move from top-level receipt keys to `receipt["evidence"]`
  (§6.2) is mandatory because `Receipt.to_dict`/`from_dict` (`run.py:30-38`) drop unknown
  top-level keys. Any other rider must likewise read domain payload from `evidence`, not
  invent top-level keys.
- **`add_note` unit id.** `HookContext.add_note` keys on `getattr(self.unit, "id", None)`
  (`contributors.py:37-39`); because `unit-close` populates `ctx.unit`, uiux's cadence note
  is now correctly attributed to the unit (previously, at empty batch `close`, it would have
  been `unit=None`).
```
