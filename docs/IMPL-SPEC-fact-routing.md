# IMPL-SPEC — fact-predicate routing (the IR)

**Status:** implementation spec. No code is changed by this document. Every contract below is grounded
in current code with `file:line` references and is implementable without re-architecture. The units
that follow implement it verbatim, in the build order of the final section.

Companion reading: `docs/design.md` (phase/workflow engine, the route-guard §"Unmatched-route
observability"), `docs/plugin-phases.md` and `docs/IMPL-SPEC-plugin-phases.md` (the deterministic-phase
`evidence {passed,next,facts}` contract), `praxis-plugins/uiux/UIUX-UPGRADE-SPEC.md` (the library-state
regime prose this change supersedes).

Source of truth read for this spec: `praxis/workflow.py`, `praxis/workflow_run.py`, `praxis/registry.py`,
`praxis/tests/test_workflow.py`, `praxis-plugins/uiux/library_state.py`,
`praxis-plugins/uiux/uiux_plugin.py`, and their tests.

---

## The problem being fixed

A deterministic phase picks a route **name** from the *global* phase namespace, but routing only
matches a workflow's *locally-wired* edges. Worse, `library_state._route` (`library_state.py:218-233`)
decides the **regime** (bootstrap vs feature) from *library completeness*, not from the running
workflow:

- `evaluate` calls `_route(s, root)` and returns it as `evidence["next"]` (`library_state.py:243-245`).
- In `feature-design` a missing screenshot manifest makes `build_state`'s `next_bootstrap_step` resolve
  to `screenshot-library-init` → remapped to `screenshot-capture` (`library_state.py:227-229`,
  `191-193`). `evaluate` emits `next="screenshot-capture"`.
- But `feature-design` wires **no** `screenshot-capture` edge (`uiux_plugin.py:104-118`). `_choose_edge`
  finds no matching `agent-choice` edge and falls through to the `pass` edge → `plan`
  (`workflow_run.py:47-57`). The route-guard fires `phase.route_unmatched` (kind `unwired`,
  `workflow_run.py:152-167`) — the failure is *announced* but the misroute is silent to the workflow.

Root cause: the emitter makes a **routing/regime decision that belongs to the WORKFLOW**. The
deterministic phase should not know whether it runs inside `design-bootstrap` or `feature-design`.

**Fix.** The deterministic phase emits **FACTS only** (no `next`). Each workflow's edges carry
**PREDICATES** over those facts. The workflow owns its own lifecycle routing: `design-bootstrap`
predicates on library-absence; `feature-design` predicates on drift and *does not wire* any
screenshot-absence branch, so a missing manifest can no longer misroute a feature.

---

## Ground truth (what exists today)

- **Edge shape.** An edge is the 4-tuple `(from, to, when, EdgeType)`; `when ∈ WHENS =
  ("pass","fail","always","agent-choice","feeds")` (`workflow.py:20`). Edges are unpacked as 4-tuples at
  four sites:
  - `workflow.next_phases` — `for (f, t, w, _et) in workflow.edges` (`workflow.py:52-54`)
  - `workflow_run._has_choice_edge` — `for (f, t, when, _et) in workflow.edges` (`workflow_run.py:15-17`)
  - `workflow_run._choose_edge` — `[(t, when, et) for (f, t, when, et) in workflow.edges …]`
    (`workflow_run.py:48`)
  - `workflow_run._incoming` — `for (f, t, _when, et) in workflow.edges` (`workflow_run.py:60-61`)
  - `registry.validate_workflow` unpacks by **index** `edge[0], edge[1]` (`registry.py:54-63`) — already
    length-tolerant.
- **`_choose_edge`** (`workflow_run.py:47-57`): consults `choice` first (an `agent-choice` edge whose
  `t == choice`), then the pass/fail default (`when in (want, "always")` where `want = "pass" if passed
  else "fail"`). Returns `(to, EdgeType)` or `None`.
- **Deterministic-phase drive** (`workflow_run.py:106-121`): `ev = phase.run(root, unit, composed)`;
  `facts = ev.get("facts") or {}`; a non-empty `facts` is journaled as `phase.facts`
  (`workflow_run.py:115-118`); `receipt.evidence = ev`.
- **Advance + choice + route-guard** (`workflow_run.py:147-167`): `passed = evidence.get("passed",
  receipt.outcome == "result")`; `advance = passed and verified`; `choice = evidence.get("next") if
  advance else None`; `nxt = _choose_edge(workflow, name, advance, choice)`. Then the existing
  name-based route-guard: if `emitted = evidence.get("next")` is set **and** `_has_choice_edge` is false,
  journal `phase.route_unmatched(unit, phase, phase_index, next, kind, resolved)` where `kind =
  _classify_route(root, emitted)` ∈ `{"unwired","unknown"}` (`workflow_run.py:31-37`) and `resolved =
  "stall" | fallthrough-phase-name`; when `_stall_on_unmatched(root)` is true (config
  `stall-on-unmatched-route == "true"`, `workflow_run.py:20-28`) it appends `phase.stalled` and breaks.
- **`library_state.evaluate`** (`library_state.py:236-245`): `s = build_state(root)`; `nxt = _route(s,
  root)`; returns `{"passed": True, "next": nxt, "facts": {"library_state": s}, "produces": s}`.
- **`build_state`** (`library_state.py:158-202`): pure filesystem + config. Returns `root`, `has_ui`,
  `libraries: {ui, ux, screenshots}` (`:198`), `phases` (list of per-phase dicts incl. `eligible`,
  `:169-188`), `eligible` (name list, `:190`), `next_bootstrap_step` (`:191-193`). **Unchanged by this
  spec.**
- **`_drift_count`** (`library_state.py:211-215`): reads `config.read(root,"uiux")["library_drift"]
  ["since_last_sync"]`. `DRIFT_THRESHOLD = 3` (`library_state.py:49`).
- **`_route`** (`library_state.py:218-233`): the regime logic to retire. Also `SCREENSHOT_PHASE`
  (`:206`) and `_OLD_SCREENSHOT_INIT` (`:208`) exist only to serve `_route`.
- **The two workflows** (`uiux_plugin.py:86-120`): `design-bootstrap` routes `library-state` to the
  three inits/capture via `agent-choice` edges keyed on `next` (`:90-94`) and loops back (`:96-100`);
  `feature-design` has `library-state → plan (pass)` and `library-state → ui-library-sync
  (agent-choice)` (`:108-110`). **`screenshot-library-sync` is registered in `build_state`'s phase table
  (`library_state.py:188`) but wired into no workflow.**

---

## Change 1 — the fact-predicate edge (core)

### 1.1 Edge shape

`workflows()` returns real Python `Workflow` objects, so a predicate is a **real callable** — no DSL.
Add one `when` value and a 5th, optional tuple element:

- `when="fact"` — new. Add `"fact"` to `WHENS` (`workflow.py:20`).
- **Predicate edge tuple:** `(from, to, "fact", EdgeType, predicate)` — a **5-tuple**. `predicate` is
  `Callable[[dict], bool]`.
- **Existing 4-tuples are unchanged** and keep working (backward-compat rule below).

**What the predicate receives.** Exactly the phase's emitted **evidence dict** — `receipt.evidence`,
i.e. the dict the deterministic `phase.run` returned (`workflow_run.py:108,121,129`). For
`library-state` that is `{"passed": True, "facts": {"library_state": {...}}, "produces": {...}}`. The
predicate reads facts via `evidence["facts"]`. A predicate MUST be pure and side-effect-free and MUST
tolerate missing keys (use `.get`); a predicate that raises is treated as **no-match** (fail-soft, see
1.3).

Recommended predicate body shape (predicates live next to the facts producer or the workflow that uses
them):

```python
def _needs_ui_init(evidence: dict) -> bool:
    ls = (evidence.get("facts") or {}).get("library_state") or {}
    return not (ls.get("libraries") or {}).get("ui", False)
```

### 1.2 Edge normalization helper (backward-compat)

Add one helper in `workflow.py` and route every unpack site through it, so a 4-tuple and a 5-tuple are
both accepted:

```python
def edge_parts(edge) -> tuple:
    """Normalize an edge to (frm, to, when, edge_type, predicate).
    4-tuples (from,to,when,EdgeType) pad predicate=None — fully backward-compatible."""
    frm, to, when, et = edge[0], edge[1], edge[2], edge[3]
    predicate = edge[4] if len(edge) > 4 else None
    return frm, to, when, et, predicate
```

Update the four unpack sites to use it (behavior identical for existing 4-tuples):

- `workflow.next_phases` (`workflow.py:52-54`)
- `workflow_run._has_choice_edge` (`workflow_run.py:15-17`)
- `workflow_run._incoming` (`workflow_run.py:60-61`)
- `workflow_run._choose_edge` (`workflow_run.py:48`)

### 1.3 `_choose_edge` composition

`_choose_edge` needs the evidence to evaluate predicates. New signature:

```python
def _choose_edge(workflow, from_phase, passed, choice=None, evidence=None):
```

Evaluation order (fail-route first as today, then the forward branches — predicate then agent-choice —
then the pass/always default). Within the predicate tier, **declaration order wins: the first matching
predicate edge is taken.**

```python
def _choose_edge(workflow, from_phase, passed, choice=None, evidence=None):
    edges = [(t, when, et, pred)
             for (f, t, when, et, pred) in map(edge_parts, workflow.edges) if f == from_phase]
    # 1. Failure short-circuits: fail/always route wins. Forward branches (predicate/
    #    agent-choice) are only consulted when advancing — matches today, where the caller
    #    passes choice=None on failure (workflow_run.py:149).
    if not passed:
        for (t, when, et, pred) in edges:
            if when in ("fail", "always"):
                return t, et
        return None
    # 2. Advancing — predicate edges, DECLARATION ORDER, first match wins.
    if evidence is not None:
        for (t, when, et, pred) in edges:
            if when == "fact" and pred is not None:
                try:
                    if pred(evidence):
                        return t, et
                except Exception:
                    continue  # fail-soft: a raising predicate is a no-match, try the next edge
    # 3. Advancing — agent-choice match (unchanged mechanism).
    if choice is not None:
        for (t, when, et, pred) in edges:
            if when == "agent-choice" and t == choice:
                return t, et
    # 4. Default — pass/always.
    for (t, when, et, pred) in edges:
        if when in ("pass", "always"):
            return t, et
    return None
```

Caller change (`workflow_run.py:150`): pass evidence through —
`nxt = _choose_edge(workflow, name, advance, choice, evidence)`.

**Composition note.** Predicate and agent-choice are both forward-branch tiers gated on `advance`; a
workflow uses one style per phase, so their relative order is not load-bearing — predicate-first is
chosen so a workflow that wires both gets deterministic, code-owned routing before falling to an
agent's emitted `next`. `fail`/`always` still win on failure, preserving
`test_failed_gate_overrides_agent_choice_next` (`tests/test_workflow.py:197-213`) and
`test_verified_gate_takes_pass_route` (`:186`).

### 1.4 Backward-compat rule

Every existing 4-tuple edge normalizes to `predicate=None`, never has `when=="fact"`, and is therefore
never matched by tier 2. Tiers 1/3/4 are the pre-existing agent-choice + pass/fail/always logic
reordered but behaviorally identical for non-predicate edges. The full existing `test_workflow.py`
suite must stay green unmodified.

### 1.5 Minimal test (core)

Add to `tests/test_workflow.py`, mirroring `_router_wf` (`:415-425`):

```python
def test_predicate_edge_first_match_wins(self):
    # library-state-like: emits facts only, no `next`.
    def run(r, u, c):
        return {"passed": True, "facts": {"k": {"go_b": True, "go_c": False}}}
    route = W.Phase("route", stance="neutral", delivery="deterministic", run=run)
    b = W.Phase("b", stance="convergent"); c = W.Phase("c", stance="convergent")
    wf = W.Workflow("pred", [route, b, c], edges=[
        ("route", "c", "fact", W.EdgeType.carry, lambda ev: ev["facts"]["k"]["go_c"]),
        ("route", "b", "fact", W.EdgeType.carry, lambda ev: ev["facts"]["k"]["go_b"]),
    ])
    out = run_workflow(self.root, R.Unit("u1", _sit()), wf, [], _Capture())
    self.assertEqual(out["phases"], ["route", "b"])  # declaration order: c-edge tests false, b-edge wins
```

Plus: a `pass` default fires when no predicate matches; a raising predicate is skipped (no-match). A
regression assertion that an all-4-tuple workflow (e.g. `W.TDD_UNIT`) still walks unchanged.

---

## Change 2 — uniform unmatched observability (core)

When a phase emits **facts** (or `next`) and **NO** edge matched — no predicate edge and no default —
the failure must stay announced/recorded uniformly, whether routing was name-based or fact-based.
**Reuse** the existing `phase.route_unmatched` event and the `stall-on-unmatched-route` flag; do **not**
remove the existing name-based route-guard.

New classification for the fact case: **`kind="no-match"`** (distinct from the name-based `"unwired"` /
`"unknown"` from `_classify_route`, `workflow_run.py:31-37`).

Extend the guard block (`workflow_run.py:152-167`). The name-based branch is unchanged; add an
`elif` for the facts-only, nothing-matched case, gated so the two branches never double-fire:

```python
emitted = evidence.get("next")
facts_emitted = bool(evidence.get("facts"))
if emitted and not _has_choice_edge(workflow, name, emitted):
    # existing name-based guard — UNCHANGED (workflow_run.py:156-167)
    ...
elif facts_emitted and not emitted and nxt is None:
    # a facts-only phase whose predicates/default all missed — nothing to route to.
    stall = _stall_on_unmatched(root)
    _journal_route_unmatched(
        root, unit=unit.id, phase=name, phase_index=phase_index,
        next=None, kind="no-match", resolved="stall" if stall else None)
    if stall:
        journal.append(root, "phase.stalled", unit=unit.id, phase=name,
                       phase_index=phase_index,
                       note="unmatched fact route (no predicate/default matched)")
        break
```

Rationale for the gate conditions:
- `not emitted` — if a phase emitted `next`, the name-based branch already owns it; don't double-record.
- `nxt is None` — a matched predicate **or** a `pass`/`always` default means routing succeeded; only a
  total miss is a no-match. This is why the workflows below wire an **explicit default/exit edge**
  (Change 5): a legitimate "all done" exit matches a default and does not trip `no-match`.

**Field shape** stays identical to the name-based event
(`{unit, phase, phase_index, next, kind, resolved}`, `workflow_run.py:159-162`) so downstream readers
need no schema change; `next` is `None` for the fact case.

### Minimal test (core)

In the `UnmatchedRouteGuardTest` class (`tests/test_workflow.py:494-566`), add a workflow whose only
edge is a predicate that returns false and no default:

```python
def _wf_facts_no_match(self):
    route = W.Phase("route", stance="neutral", delivery="deterministic",
                    run=lambda r, u, c: {"passed": True, "facts": {"k": 1}})
    a = W.Phase("a", stance="convergent")
    return W.Workflow("nomatch", [route, a], edges=[
        ("route", "a", "fact", W.EdgeType.carry, lambda ev: False),
    ])

def test_facts_no_match_journals_kind_no_match_and_ends(self):
    out = run_workflow(self.root, R.Unit("u1", _sit()), self._wf_facts_no_match(), [], _Capture())
    self.assertEqual(out["phases"], ["route"])          # nowhere to go → walk ends
    ev = self._events("phase.route_unmatched")
    self.assertEqual(len(ev), 1)
    self.assertEqual(ev[0]["kind"], "no-match")
    self.assertIsNone(ev[0]["next"])
    self.assertFalse(self._events("phase.stalled"))     # flag off → no stall

def test_facts_no_match_stalls_when_flag_on(self):
    config.write(self.root, None, {"stall-on-unmatched-route": "true"})
    ... assert ev[0]["resolved"] == "stall" and one phase.stalled ...
```

Also assert the **negative**: a facts-emitting phase that DOES match a predicate/default emits **no**
`phase.route_unmatched` (parity with `test_matched_agent_choice_route_emits_no_event`,
`:568`).

---

## Change 3 — registry validation of predicate edges

`validate_workflow` (`registry.py:43-64`) must accept predicate edges. Today it index-unpacks
`edge[0], edge[1]` and checks both endpoints are known phases (`:54-63`) — length-tolerant, so a
5-tuple already passes the endpoint checks. Add the predicate-specific checks:

```python
for edge in obj.edges or []:
    try:
        frm, to = edge[0], edge[1]
        when = edge[2]
    except (TypeError, IndexError):
        problems.append(f"malformed edge {edge!r}")
        continue
    if frm not in phases:
        problems.append(f"edge endpoint {frm!r} names an unknown phase")
    if to not in phases:
        problems.append(f"edge endpoint {to!r} names an unknown phase")
    if when == "fact":
        pred = edge[4] if len(edge) > 4 else None
        if not callable(pred):
            problems.append(f"predicate edge {frm!r}->{to!r} must carry a callable predicate")
```

- **Contract:** for a `when=="fact"` edge, element `[4]` must be callable and `to` must name a known
  phase (already enforced). Non-`fact` edges are validated exactly as today.
- **Backward-compat:** existing 4-tuples never have `when=="fact"`, so the new branch never runs for
  them.
- Invalid workflows are skipped fail-soft by `resolve_workflows` (`registry.py:119-121`), as today.

### Minimal test (registry)

In `tests/test_registry.py`: a `Workflow` with a valid predicate edge validates clean
(`validate_workflow(w, phases) == []`); a `when="fact"` edge whose `[4]` is missing or a non-callable
yields the `"must carry a callable predicate"` problem; a predicate edge to an unknown phase still
yields the unknown-endpoint problem.

---

## Change 4 — `library_state` → facts-only (uiux)

Retire the regime decision. `evaluate` emits facts and **no `next`**; `build_state`'s filesystem logic
is untouched.

### 4.1 New `evaluate`

```python
def evaluate(root, unit=None, composed=None) -> dict:
    """Deterministic `Phase.run` for `library-state`. FACTS ONLY — no `next`.
    Routing is owned by the workflow's predicate edges (IMPL-SPEC-fact-routing §5)."""
    s = build_state(Path(root))
    s = {
        **s,
        "drift": _drift_count(root),                                   # was read only by _route
        "eligibility": {p["phase"]: bool(p["eligible"]) for p in s["phases"]},
    }
    return {"passed": True, "facts": {"library_state": s}, "produces": s}
```

- `passed` stays `True` — a fact is never a failure.
- **No `next` key.** This is the crux: the phase no longer names a route.
- `produces` still carries the state dict forward as `composed["carry"]` for the spawn phases
  (unchanged consumer contract, `workflow_run.py:97-100,144-145`).

### 4.2 Facts shape (the predicate surface)

`evidence["facts"]["library_state"]` exposes, for workflows to predicate on:

| key | type | source | meaning |
|-----|------|--------|---------|
| `libraries.ui` | bool | `build_state:198` | `ui-library.md` exists |
| `libraries.ux` | bool | `build_state:198` | `ux-library.md` exists |
| `libraries.screenshots` | bool | `build_state:198` | screenshot manifest exists |
| `drift` | int | `_drift_count` (`:211-215`) | UI-drift units since last accepted sync |
| `eligibility.<phase>` | bool | `build_state` phase table (`:169-188`) | per-phase eligibility flag (e.g. `eligibility["ui-library-sync"]`) |
| `has_ui` | bool | `build_state:162,198` | root has a UI surface (predicates may guard on this) |

`phases`, `eligible`, `next_bootstrap_step` remain in the dict (build_state output, unchanged) but are
not the predicate surface; `next_bootstrap_step` is now inert output, no longer a router input.

### 4.3 Retire

- Delete `_route` (`library_state.py:218-233`) and the constants that served only it: `SCREENSHOT_PHASE`
  (`:206`), `_OLD_SCREENSHOT_INIT` (`:208`). (`grep` confirms both are used only inside `_route` and its
  docstring.)
- Keep `_drift_count` (`:211-215`) — now consumed by `evaluate`.
- Keep `build_state`, `next_bootstrap_step`, `print_state`, the CLI — unchanged.
- Update the module docstring (`:29-31`) and the `evaluate` docstring (`:236-245`): the drift counter and
  regime decision now belong to the workflow, not `_route`.

### 4.4 Backward-compat rule

`evaluate` still returns `passed`, `facts.library_state`, `produces`. The only removed key is `next`.
Every existing consumer of `facts.library_state.libraries` (`uiux_plugin._index_body:213`, etc.) is
unaffected — the state dict is a superset of before (adds `drift`, `eligibility`).

### 4.5 Minimal test (uiux)

Rewrite `tests/test_library_state_phase.py` (`:30-86`) — those tests assert `ev["next"]`, which is gone:

```python
def test_evaluate_emits_facts_no_next(tmp_path):
    ev = library_state.evaluate(tmp_path)
    assert "next" not in ev
    assert ev["passed"] is True
    ls = ev["facts"]["library_state"]
    assert ls["libraries"] == {"ui": False, "ux": False, "screenshots": False}  # bare root
    assert ls["drift"] == 0
    assert ls["eligibility"]["ui-library-init"] is <expected from has_ui>
    assert ev["produces"] is ls
```

Cover: ui present toggles `libraries.ui`/`eligibility`; drift is read from config; `has_ui=no` yields
all-false eligibility. (The routing that these tests used to assert moves to the workflow tests in
Change 5.)

---

## Change 5 — the two workflows' predicate edges (uiux; the lifecycle scoping)

Rewire only the edges out of `library-state`. Downstream edges and phase lists change only where an
explicit exit is added.

Predicate helpers — define next to the workflows in `uiux_plugin.py` (small, named, testable). Each
reads the facts fail-soft:

```python
def _facts(ev):        # evidence -> library_state fact dict (fail-soft)
    return (ev.get("facts") or {}).get("library_state") or {}
def _libs(ev):
    return (_facts(ev).get("libraries") or {})

def _needs_ui_init(ev):        return not _libs(ev).get("ui", False)
def _needs_screenshots(ev):    return _libs(ev).get("ui", False) and not _libs(ev).get("screenshots", False)
def _needs_ux_init(ev):        return _libs(ev).get("ui", False) and not _libs(ev).get("ux", False)
def _drift_over_threshold(ev): return _libs(ev).get("ui", False) and \
                                      _facts(ev).get("drift", 0) >= library_state.DRIFT_THRESHOLD
```

### 5.1 `design-bootstrap` — route on library-absence

Replace the three `agent-choice` edges (`uiux_plugin.py:90-94`) with predicate edges in **this
declaration order** (first match wins), then loop-backs (unchanged), then an **explicit exit**:

```python
DESIGN_BOOTSTRAP = Workflow(
    name="design-bootstrap",
    phases=[LIBRARY_STATE, UI_LIBRARY_INIT, UX_LIBRARY_INIT, SCREENSHOT_CAPTURE,
            DESIGN_DECISION_REVIEW, CLOSE],                       # + CLOSE as the all-present exit
    edges=[
        # library absence — declaration order encodes the ui -> {screenshot, ux} dependency.
        ("library-state", "ui-library-init",   "fact", EdgeType.create, _needs_ui_init),
        ("library-state", "screenshot-capture","fact", EdgeType.create, _needs_screenshots),
        ("library-state", "ux-library-init",   "fact", EdgeType.create, _needs_ux_init),
        # all present -> clean exit (a real default so the no-match guard does NOT trip).
        ("library-state", "close", "pass", EdgeType.carry),
        # divergent inits -> review -> re-evaluate (unchanged).
        ("ui-library-init", "design-decision-review", "pass", EdgeType.carry),
        ("ux-library-init", "design-decision-review", "pass", EdgeType.carry),
        ("design-decision-review", "library-state", "pass", EdgeType.carry),
        # screenshot capture is mechanical: straight back to re-evaluate (unchanged).
        ("screenshot-capture", "library-state", "pass", EdgeType.carry),
    ],
)
```

**Ordering — explicit.** `ui-library-init` is tested **first**: while `ui` is absent it wins and
screenshot/ux are content-blocked on the ratified ui-library (`build_state:178-184`). Once `ui` exists,
`_needs_ui_init` is false and the next tested edge is **`screenshot-capture` BEFORE `ux-library-init`**
— reproducing the OLD `next_bootstrap_step` ordering (bootstrap phase 3 before phase 4,
`build_state:179-184,191-193`). Each init loops back through `library-state`, which re-emits facts and
re-routes on the now-changed absence set.

**Import.** `CLOSE` is already imported in `uiux_plugin.py` (`:26`).

**Decision — the exit edge.** `library-state`'s all-present case previously ended the walk by returning
`next=None` (walk `break` on `nxt is None`, `workflow_run.py:169`). Under Change 2 that would now
*false-positive* as `kind="no-match"` (facts emitted, nothing matched). So the "all present" exit is
made an **explicit `pass` edge to the seed `close` phase** — a real default that Change 2's `nxt is
None` gate treats as a successful route. `close` emits no facts and has no outgoing edge, so the walk
ends cleanly with no spurious event. (Alternative considered: suppress `no-match` when a phase has
outgoing predicate edges that all missed — rejected as fuzzier and it would hide genuine
predicate-coverage gaps.)

### 5.2 `feature-design` — drift-gated sync, screenshots NOT wired

Replace `library-state`'s two edges (`uiux_plugin.py:108-110`) with a **drift-gated predicate edge**
first, then a **`pass` default to `plan`**:

```python
FEATURE_DESIGN = Workflow(
    name="feature-design",
    phases=[LIBRARY_STATE, PLAN, UI_LIBRARY_SYNC, DESIGN_DECISION_REVIEW, IMPLEMENT, VERIFY, CLOSE],
    edges=[
        ("library-state", "ui-library-sync", "fact", EdgeType.create, _drift_over_threshold),  # drift → sync first
        ("library-state", "plan", "pass", EdgeType.carry),                                     # else → design
        # downstream unchanged (uiux_plugin.py:111-117)
        ("plan", "ui-library-sync", "pass", EdgeType.carry),
        ("ui-library-sync", "design-decision-review", "pass", EdgeType.carry),
        ("design-decision-review", "implement", "pass", EdgeType.carry),
        ("implement", "verify", "pass", EdgeType.carry),
        ("verify", "close", "pass", EdgeType.carry),
        ("verify", "implement", "fail", EdgeType.carry),
    ],
)
```

- **`ui-library-sync` is gated** on `facts.libraries.ui and facts.drift >= DRIFT_THRESHOLD`. Below
  threshold, the `pass` default routes to `plan`.
- **`screenshot-capture` is NOT wired here** (deferred-sync decision). A missing screenshot manifest
  produces `libraries.screenshots == False` in the facts, but `feature-design` has **no predicate that
  reads it** — so a missing manifest can no longer misroute a feature. This is the concrete bug fix:
  the regime is now a property of *which predicates the workflow wired*, not of library completeness.

### 5.3 Minimal test (uiux workflows)

New `tests/test_uiux_routing.py` driving `run_workflow` with a stub executor (pattern:
`tests/test_workflow.py:427-446`, and the existing uiux e2e `tests/test_end_to_end.py`):

- **bootstrap, bare root:** `library-state` → `ui-library-init` (only `_needs_ui_init` true).
- **bootstrap, ui present, no manifest, no ux:** → `screenshot-capture` (ordering: screenshot before
  ux).
- **bootstrap, ui+screenshots present, no ux:** → `ux-library-init`.
- **bootstrap, all present:** → `close`, walk ends, **no** `phase.route_unmatched`.
- **feature, drift below threshold:** `library-state` → `plan`.
- **feature, drift ≥ threshold, ui present:** `library-state` → `ui-library-sync`.
- **feature, ui present, manifest MISSING, drift below threshold:** `library-state` → `plan` (the
  regression-guard for the fixed bug — assert **no** hop to `screenshot-capture` and **no**
  `phase.route_unmatched`).

Update `tests/test_uiux_phases.py` (`:42-47`) — both workflows must still validate against the merged
phase table (now that predicate edges carry callables and `close` is a bootstrap phase).

---

## Change 6 — known deferred gap (record only; not built here)

The feature-end **screenshot recapture** is deferred to a **drift-gated sync**: the close hook already
marks changed surfaces' screenshots stale (`uiux_plugin._on_close` action 2, `:362-364` →
`library_state.mark_stale`). But **`screenshot-library-sync` has no wired home** — it is registered in
`build_state`'s phase table (`library_state.py:188`) yet routed to by no workflow (confirmed by grep:
the only `screenshot-*` edges live in `design-bootstrap`, and they target `screenshot-capture`, not
`screenshot-library-sync`). Consequently a manifest that goes stale mid-feature is recorded but never
re-captured by any current traversal.

This is a **known deferred gap**, explicitly out of scope for this change. This spec deliberately does
**not** wire a screenshot-sync branch into `feature-design` (§5.2). A follow-up unit would add a
predicate edge (e.g. `library-state → screenshot-library-sync when facts.libraries.screenshots and
<manifest-has-stale>`) once a "manifest staleness" fact is exposed by `build_state`/`evaluate`; that
staleness fact does not exist today and is not added here.

---

## Build order

1. **Core — Change 1 + 2 + 3 together** (`workflow.py`, `workflow_run.py`, `registry.py`): `edge_parts`,
   `when="fact"`, `_choose_edge` predicate tier + evidence pass-through, the `no-match` guard, registry
   validation. Land with the core tests (1.5, Change-2 tests, Change-3 tests). The full existing
   `test_workflow.py` / `test_registry.py` suites stay green **unmodified** — this proves backward-compat.
2. **uiux — Change 4 + 5** (`library_state.py`, `uiux_plugin.py`): facts-only `evaluate`, retire
   `_route`; rewire both workflows with predicate edges + explicit exits. Land with rewritten
   `test_library_state_phase.py` and new `test_uiux_routing.py`; re-green `test_uiux_phases.py`.
3. **e2e** (`praxis-plugins/uiux/tests/test_end_to_end.py`): drive `design-bootstrap` from a bare root
   through the init loop to `close`, and `feature-design` with a missing manifest + low drift landing on
   `plan` (no misroute, no `route_unmatched`).

---

## Risk notes

- **Reordering `_choose_edge`.** The refactor splits the old single `want in (want,"always")` loop into
  a fail-tier and a pass/always-default tier and inserts predicate + choice tiers between. Confirm
  parity against every existing `_choose_edge`-exercising test (`test_workflow.py:175-227`,
  `:427-476`). The load-bearing invariants: failure never consults forward branches; `agent-choice`
  still beats pass/always; a bare `always` still fires in both tiers.
- **Predicate exceptions.** A raising predicate is swallowed as no-match (`_choose_edge` tier 2
  `except: continue`). This can silently skip a branch; the Change-2 `no-match` guard is the safety net
  that makes a total miss observable. Predicates must be trivial fact reads (§5 helpers use `.get`
  throughout).
- **The exit-edge false-positive.** Without §5.1's explicit `close` edge, `design-bootstrap`'s legitimate
  all-present completion would emit `phase.route_unmatched(kind="no-match")`. The explicit default is
  mandatory, not cosmetic. Any facts-only phase that is meant to be terminal must carry a default edge.
- **Facts dict growth.** `evaluate` now returns a superset state dict (`drift`, `eligibility`); it is
  journaled verbatim as `phase.facts` (`workflow_run.py:115-118`). Keep it JSON-serializable (it is —
  bools/ints/lists/dicts only).
- **`next_bootstrap_step` now inert.** It remains in `build_state` output and `print_state`, but nothing
  routes on it. Leave it (the CLI `state` view still shows it); do not let a future reader mistake it for
  a router input.

---

## Pinned contracts (summary)

1. **Fact-predicate edge** — `(from, to, "fact", EdgeType, predicate)`, `predicate: Callable[[dict],
   bool]` receiving the phase's **evidence dict** (incl. `evidence["facts"]`). `"fact"` added to
   `WHENS`. `edge_parts` normalizes 4-/5-tuples so existing edges are untouched. `_choose_edge` order:
   **fail/always → predicate (declaration order, first match) → agent-choice → pass/always default**;
   evidence threaded in from the caller. A raising predicate = no-match.
2. **Uniform unmatched observability** — reuse `phase.route_unmatched` + `stall-on-unmatched-route`. New
   `kind="no-match"` fires when a phase emitted facts, emitted no `next`, and `nxt is None`. Existing
   name-based guard (`unwired`/`unknown`) is untouched; the two branches never double-fire.
3. **Registry validation** — `validate_workflow` requires `edge[4]` callable when `when=="fact"`;
   endpoints validated as today; 4-tuples unaffected.
4. **library_state facts-only** — `evaluate` returns `{passed: True, facts: {library_state: {...libraries,
   drift, eligibility, ...}}, produces}` with **no `next`**; `_route`/`SCREENSHOT_PHASE`/
   `_OLD_SCREENSHOT_INIT` retired; `build_state` unchanged.
5. **Workflow predicate edges** — `design-bootstrap` routes on library absence in the order
   **ui-init → screenshot-capture → ux-init**, loops back to re-evaluate, and exits via an explicit
   `pass → close` when all present. `feature-design` routes `→ ui-library-sync` only when
   `libraries.ui and drift >= DRIFT_THRESHOLD`, else `→ plan`; **screenshot-capture is not wired**, which
   is the fix.
6. **Deferred gap** — feature-end screenshot recapture is deferred; `screenshot-library-sync` has no
   wired home and this change does not build one (needs a manifest-staleness fact that does not yet
   exist).

### Decisions made in writing this spec

- **Explicit `close` exit for `design-bootstrap`** (§5.1) rather than the old implicit `next=None`
  termination — required so Change 2's `no-match` guard does not false-positive on legitimate
  completion. Chose the seed `close` phase (already imported) over inventing a terminal phase.
- **Predicate tier ordered before agent-choice** in `_choose_edge` — so a workflow that wires both gets
  deterministic code-owned routing before an agent's emitted `next`. Not load-bearing today (no workflow
  mixes them from one phase) but makes the composition total and explicit.
- **`kind="no-match"`** as a third classification, disjoint from `_classify_route`'s `unwired`/`unknown`
  which stay bound to the name-based (`next`-carrying) path — keeps the two guard branches
  non-overlapping and their events distinguishable.
- **Facts surface = `libraries` + `drift` + `eligibility` (+ `has_ui`)** exposed as a flat, predicate-
  friendly superset of `build_state` output, so workflow predicates never have to walk the `phases`
  list.
