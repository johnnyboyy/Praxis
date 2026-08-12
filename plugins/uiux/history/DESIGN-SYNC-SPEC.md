# DESIGN-SYNC-SPEC — the `design-sync` path (IR)

Status: SPEC (intermediate representation). **No code changes here.** Every contract
below is pinned to the real code with `file:line` refs so the two impl units can be
built mechanically.

Scope: introduce a per-library staleness model, a new `design-sync` workflow with a
surgical screenshot recapture phase, a surfaced sync recommendation, removal of the
feature-design ui-sync piggyback, and an explicit **GO/DEFER** verdict on the
global/blast-radius hop.

Files in play:
- `praxis-plugins/uiux/library_state.py` — facts, manifest, drift counters.
- `praxis-plugins/uiux/uiux_plugin.py` — phases, workflows, close hook, contribute.
- `praxis-plugins/uiux/tests/*` — routing / hooks / phases tests.
- `praxis/workflow.py`, `praxis/registry.py` — read-only contracts (edge tuple shape,
  `validate_workflow`). No edits.

---

## Build split (two impl units)

- **Unit A — facts & counters** (`library_state.py` + close-hook counter/note logic in
  `uiux_plugin.py`). Deliverable: `evaluate` emits per-library staleness facts; drift
  becomes two attributable counters; `mark_fresh` added; close hook bumps/resets the
  right counter and surfaces the recommendation note. No workflow topology change.
- **Unit B — sync workflow** (`uiux_plugin.py` phases/workflows + `contribute` +
  feature-design edit). Deliverable: `SCREENSHOT_LIBRARY_SYNC` phase, `design-sync`
  workflow, surgical stale-set disclosure, feature-design piggyback removed.

Unit A lands first (Unit B's predicates read Unit A's facts). Each unit ships with its
own tests (below).

---

## 1. Per-library staleness model

### 1.1 The honest ui-vs-ux attribution assessment

The only drift signal the close hook receives is `receipt["ui-drift"]` carrying
`screens` and `components` (`uiux_plugin.py:384-386`). Assessment:

- `screens` → maps cleanly to **screenshot** surfaces (they name manifest entries;
  already consumed by `mark_stale`, `uiux_plugin.py:399-400`).
- `components` → a **UI-library** atom (a component is a ui-library concept).
- **There is no ux-flow signal in the receipt.** The channel is literally named
  `ui-drift`; nothing distinguishes a ui-identity change from a ux-flow change.

**Verdict: ui-vs-ux drift cannot be cleanly separated on the BUMP side.** Stated
plainly so no one invents a `ux-drift` signal that isn't derivable.

The RESET side *is* attributable: the sync phase name (`ui-library-sync` vs
`ux-library-sync`) tells us exactly which library was just brought current
(`uiux_plugin.py:393`).

### 1.2 Pragmatic model chosen: two counters, bump-both / reset-own

Replace the single scalar `library_drift.since_last_sync` with **two counters** that
share a bump but reset independently:

- `library_drift.ui_drift` (int) and `library_drift.ux_drift` (int).
- **BUMP (unattributable):** any design-touching unit bumps **both** counters by 1.
  This is a deliberate conservative over-signal — since we can't tell which library
  drifted, both accrue. Documented limitation: a pure-ux change still bumps `ui_drift`
  and vice-versa. It never *under*-signals (never leaves a real drift uncounted).
- **RESET (attributable by phase name):** an accepted `ui-library-sync` sets
  `ui_drift = 0`; an accepted `ux-library-sync` sets `ux_drift = 0`. Only the synced
  library's counter clears.
- **Screenshots** are the one cleanly separable dimension — they carry per-surface
  `status: stale|fresh` in the manifest (`library_state.py:85-113`). No counter; the
  manifest *is* the state.

Why two counters over one shared `design_drift`: with a single counter, syncing ui
would reset it and ux would then read clean — an *under*-signal that silently drops a
due ux sync. Two counters let ui and ux each become due and each clear on their own
sync, so a `design-sync` loop syncs both. The cost is the documented over-signal,
which is the safe direction.

### 1.3 Facts shape `evidence["facts"]["library_state"]` gains

`evaluate` (`library_state.py:213-230`) currently spreads `build_state` and adds
`drift` + `eligibility`. It gains the per-library staleness block:

```python
def evaluate(root, unit=None, composed=None) -> dict:
    s = build_state(Path(root))
    manifest = read_manifest(root)
    stale = [e["screen"] for e in manifest if e.get("status") == "stale"]
    ui_d, ux_d = _drift_counts(root)          # (ui_drift, ux_drift)
    s = {
        **s,
        # --- backward-compat scalar (kept; see §1.4) -----------------------------
        "drift": max(ui_d, ux_d),
        # --- NEW: per-library staleness ------------------------------------------
        "ui_drift": ui_d,
        "ux_drift": ux_d,
        "screenshots": {
            "stale": stale,                    # list[str] of screen names
            "stale_count": len(stale),         # int
            "any_stale": bool(stale),          # bool
        },
        "eligibility": {p["phase"]: bool(p["eligible"]) for p in s["phases"]},
    }
    return {"passed": True, "facts": {"library_state": s}, "produces": s}
```

Resulting fact paths (what Unit B predicates read):
- `facts.library_state.screenshots.stale` — `list[str]`
- `facts.library_state.screenshots.stale_count` — `int`
- `facts.library_state.screenshots.any_stale` — `bool`
- `facts.library_state.ui_drift` — `int`
- `facts.library_state.ux_drift` — `int`
- `facts.library_state.drift` — `int` (backcompat alias == `max(ui_drift, ux_drift)`)

Note the two distinct `screenshots` paths, both legitimate and non-colliding:
`libraries.screenshots` stays a bool = "manifest file exists" (`library_state.py:199`);
`screenshots.{stale,any_stale}` is the new staleness block.

### 1.4 Counter read helper + backward compat

Replace `_drift_count` (`library_state.py:206-210`) with `_drift_counts` returning the
pair, migrating the old scalar shape fail-soft:

```python
def _drift_counts(root) -> tuple[int, int]:
    """(ui_drift, ux_drift). Migrates the OLD `since_last_sync` scalar fail-soft:
    a legacy value seeds BOTH counters so no accumulated drift is dropped."""
    d = config.read(root, SCOPE).get("library_drift", {})
    if not isinstance(d, dict):
        return 0, 0
    legacy = int(d.get("since_last_sync", 0) or 0)
    ui_d = int(d.get("ui_drift", legacy) or 0)
    ux_d = int(d.get("ux_drift", legacy) or 0)
    return ui_d, ux_d
```

Backward compat: a root whose config still holds `{"since_last_sync": 2}` reads as
`(2, 2)` until the next close writes the new keys. `evaluate` keeps emitting `drift`
(now `max`) so any external reader of the old scalar fact keeps working.

### 1.5 Close-hook counter changes (Unit A, `uiux_plugin.py:390-396`)

Replace the single-scalar bump/reset with the two-counter contract:

```python
# 1. drift counters — reset the synced library's counter on accept, else bump BOTH.
cur = config.read(root, "uiux").get("library_drift") or {}
ui_d, ux_d = library_state._drift_counts(root)
if accepted and phase_name == "ui-library-sync":
    config.write(root, "uiux", {"library_drift": {"ui_drift": 0, "ux_drift": ux_d}})
elif accepted and phase_name == "ux-library-sync":
    config.write(root, "uiux", {"library_drift": {"ui_drift": ui_d, "ux_drift": 0}})
elif screens or components or targets:
    config.write(root, "uiux",
                 {"library_drift": {"ui_drift": ui_d + 1, "ux_drift": ux_d + 1}})
```

`SYNC_PHASES` (`uiux_plugin.py:167`) is still used for `contribute`/`surface` gating;
leave it, but the reset branch now keys on the exact phase name, not set membership,
because ui and ux reset *different* counters.

Screenshot reset is handled in §2.4 (manifest, not counter), so `screenshot-library-sync`
is deliberately absent from this counter block.

### 1.6 Minimal test (Unit A)

Extend `tests/test_uiux_hooks.py`:
- `test_close_bumps_both_drift_counters`: after an `implement` close with
  `ui-drift.screens`, both `ui_drift == 1` and `ux_drift == 1`.
- `test_close_ui_sync_resets_only_ui`: seed `{ui_drift:3, ux_drift:3}`, accepted
  `ui-library-sync` → `ui_drift == 0`, `ux_drift == 3`.
- `test_close_ux_sync_resets_only_ux`: symmetric.
- `test_legacy_since_last_sync_migrates`: seed `{since_last_sync:2}`, `evaluate` facts
  show `ui_drift == ux_drift == 2`.
- Update existing `test_close_accepted_sync_resets_drift` (`test_uiux_hooks.py:88-95`)
  and helper `_drift` (`:56-58`) to read `ui_drift`.

---

## 2. `design-sync` workflow

A new maintenance workflow, authoritative for all sync. Screenshots route **EAGER**
(any stale surface), ui/ux route **THRESHOLD-gated** (their own counter ≥
`DRIFT_THRESHOLD`, `library_state.py:50`).

### 2.1 New phase object (`uiux_plugin.py`, near `:66`)

```python
SCREENSHOT_LIBRARY_SYNC = Phase(
    "screenshot-library-sync", stance="neutral", delivery="spawn",
    intent="surgical recapture: reshoot ONLY the surfaces the manifest marks stale",
    produces="screenshots")
```

Add to `UIUX_PHASES` (`:76-79`). Registry validation (`registry.validate_phase`,
`registry.py:30-40`) passes: `stance="neutral"` ∈ `STANCES`, `delivery="spawn"` ∈
`DELIVERIES`. `SEVEN` in `test_uiux_phases.py:12` becomes `EIGHT` (add the name).

### 2.2 New predicates (`uiux_plugin.py`, near `:108`)

Replace `_drift_over_threshold` (`:108-110`) with three per-library predicates
(pure, fail-soft `.get` reads, per the `_facts`/`_libs` convention at `:87-110`):

```python
def _screenshots_any_stale(ev):
    return bool((_facts(ev).get("screenshots") or {}).get("any_stale"))

def _ui_drift_over_threshold(ev):
    return (_libs(ev).get("ui", False)
            and _facts(ev).get("ui_drift", 0) >= library_state.DRIFT_THRESHOLD)

def _ux_drift_over_threshold(ev):
    return (_libs(ev).get("ux", False)
            and _facts(ev).get("ux_drift", 0) >= library_state.DRIFT_THRESHOLD)
```

### 2.3 The workflow object (`uiux_plugin.py`, near `:156`)

```python
DESIGN_SYNC = Workflow(
    name="design-sync",
    phases=[LIBRARY_STATE, SCREENSHOT_LIBRARY_SYNC, UI_LIBRARY_SYNC,
            UX_LIBRARY_SYNC, DESIGN_DECISION_REVIEW, CLOSE],
    edges=[
        # EAGER: any stale surface -> surgical recapture (declared first = highest prio).
        ("library-state", "screenshot-library-sync", "fact", EdgeType.create,
         _screenshots_any_stale),
        # THRESHOLD-gated: ui / ux drift at or over the threshold.
        ("library-state", "ui-library-sync", "fact", EdgeType.create,
         _ui_drift_over_threshold),
        ("library-state", "ux-library-sync", "fact", EdgeType.create,
         _ux_drift_over_threshold),
        # all clean -> explicit default so the no-match guard does NOT trip.
        ("library-state", "close", "pass", EdgeType.carry),
        # mechanical recapture: straight back to re-evaluate (manifest now fresher).
        ("screenshot-library-sync", "library-state", "pass", EdgeType.carry),
        # divergent/convergent syncs go through review, then loop to re-evaluate.
        ("ui-library-sync", "design-decision-review", "pass", EdgeType.carry),
        ("ux-library-sync", "design-decision-review", "pass", EdgeType.carry),
        ("design-decision-review", "library-state", "pass", EdgeType.carry),
    ],
)

UIUX_WORKFLOWS = [DESIGN_BOOTSTRAP, FEATURE_DESIGN, DESIGN_SYNC]   # was two (:156)
```

Loop-to-`library-state` semantics (mirrors `design-bootstrap`, `:131-133`): each sync
returns to re-evaluate; when every dimension reads clean the `pass → close` default
exits. This is why two counters (§1.2) matter — ui and ux each clear on their own sync
so a single `design-sync` run drains both. Declaration order is the priority ladder:
screenshots (cheapest, mechanical) drain first, then ui, then ux.

`route_unmatched` safety: the `pass → close` carry edge (`workflow.py:52-65` normalizes
it) guarantees a match when no fact predicate fires — the same guarantee
`design-bootstrap` relies on (`test_uiux_routing.py:101-108`).

Validation: `validate_workflow` (`registry.py:43-70`) requires every fact edge to carry
a callable predicate — all three do. Every phase name resolves in the merged table
(`SCREENSHOT_LIBRARY_SYNC` added in §2.1; `CLOSE`/`DESIGN_DECISION_REVIEW` already
present).

### 2.4 Surgical recapture — stale set in, stale flags out

**In (get the stale set from the manifest).** The phase is `delivery="spawn"`; its work
brief is composed by `contribute` (`uiux_plugin.py:306-368`). Add a branch mirroring the
existing `screenshot-capture` branch (`:359-365`) but explicitly surgical:

```python
if name in ("screenshot-capture", "screenshot-library-sync"):
    entries = library_state.read_manifest(self.root)
    stale = [e["screen"] for e in entries if e.get("status") == "stale"]
    verb = ("Recapture ONLY these stale surfaces (surgical — never a full recapture)"
            if name == "screenshot-library-sync" else "Stale set to (re)capture")
    body = self._index_body() + f"\n\n{verb}: " + (
        ", ".join(stale) if stale else "(none stale)")
    return [Contribution(source="uiux", title="Screenshot recapture set", body=body,
                         priority=_INDEX_PRIORITY, meta={"disclosure": "manifest"})]
```

The manifest read (`library_state.read_manifest`, `:88-113`) is the single source of the
stale set. A full recapture is never composed — only `status == "stale"` surfaces are
named.

**Out (clear the flags / reset the dimension on completion).** Add a `mark_fresh`
helper to `library_state.py` (inverse of `mark_stale`, `:130-156`):

```python
def mark_fresh(root, screens=None) -> bool:
    """Clear the stale flag on the named screens (default: ALL currently-stale).
    Called from the close hook after a screenshot-library-sync recapture."""
    entries = read_manifest(root)
    target = set(screens) if screens else None
    changed = False
    for e in entries:
        if e.get("status") == "stale" and (target is None or e["screen"] in target):
            e["status"] = "fresh"
            changed = True
    if changed:
        write_manifest(root, entries)
    return changed
```

Wire it in the close hook (`uiux_plugin.py`, in `_on_close` after the counter block):

```python
# screenshot recapture: mark the reshot surfaces fresh (default all stale).
if accepted and phase_name == "screenshot-library-sync":
    captured = list((receipt.get("screenshots") or {}).get("captured") or [])
    library_state.mark_fresh(root, screens=captured or None)
```

The receipt may carry `screenshots.captured` (the exact surfaces reshot); absent that,
`mark_fresh` clears all stale (surgical recapture shot exactly the stale set, so this is
correct). Because screenshots have no counter, clearing the manifest flags *is* the
"reset the relevant drift" for this dimension — the next `library-state` eval reads
`any_stale == False` and the `pass → close` default fires.

### 2.5 Minimal test (Unit B)

New `tests/test_design_sync_routing.py` (pattern of `test_uiux_routing.py`, driving the
live `run_workflow`):
- `test_sync_stale_screenshots_route_eager`: fresh drift 0, one manifest entry
  `status: stale` → first hop is `screenshot-library-sync`.
- `test_sync_ui_drift_at_threshold_routes_ui`: no stale screenshots, `ui_drift == 3`
  → first hop `ui-library-sync`.
- `test_sync_ux_drift_at_threshold_routes_ux`: `ui_drift == 0`, `ux_drift == 3`
  → `ux-library-sync`.
- `test_sync_all_clean_exits_to_close_no_unmatched`: everything fresh, drift 0 →
  `["library-state", "close"]`, zero `phase.route_unmatched`.
- `test_sync_eager_beats_threshold`: stale screenshot AND `ui_drift == 5` → screenshots
  first (declaration-order priority).
- `test_design_sync_validates`: `registry.validate_workflow(DESIGN_SYNC, phases) == []`.
- `mark_fresh` unit test + a close-hook test that an accepted `screenshot-library-sync`
  flips a stale entry to fresh.

Update `test_uiux_phases.py`: `SEVEN`→eight-name set incl. `screenshot-library-sync`;
`test_resolve_workflows_contains_both` → also assert `"design-sync" in workflows`.

---

## 3. Recommendation signal (surfaced, not auto-run)

After the close hook records staleness (end of `_on_close`, replacing the existing
`ctx.add_note` at `uiux_plugin.py:407-411`), surface a per-library cadence note. This is
a **recommendation only** — nothing runs `design-sync` automatically.

```python
ui_d, ux_d = library_state._drift_counts(root)
stale = [e["screen"] for e in library_state.read_manifest(root)
         if e.get("status") == "stale"]
th = library_state.DRIFT_THRESHOLD
due = ([f"screenshots ({len(stale)} stale)"] if stale else []) \
    + ([f"ui ({ui_d}/{th})"] if ui_d >= th else []) \
    + ([f"ux ({ux_d}/{th})"] if ux_d >= th else [])
body = ("design-sync due: " + "; ".join(due)) if due else \
       (f"design-sync cadence: screenshots {len(stale)} stale; "
        f"ui {ui_d}/{th}; ux {ux_d}/{th}")
try:
    ctx.add_note("uiux", body,
                 screenshots_stale=len(stale),
                 ui_drift=ui_d, ux_drift=ux_d, threshold=th,
                 due=[d.split(" ")[0] for d in due])
except Exception:
    pass
```

Note shape (via `HookContext.add_note`, `contributors.py:37-39` → `journal.note`):
- `source`: `"uiux"`
- `body`: `"design-sync due: screenshots (N stale); ui (M/threshold); ux (K/threshold)"`
  when anything is due; otherwise a quiet `"design-sync cadence: ..."` line.
- structured extras: `screenshots_stale=N`, `ui_drift=M`, `ux_drift=K`,
  `threshold=DRIFT_THRESHOLD`, `due=["screenshots","ui","ux"]` (subset actually due).

Minimal test (Unit A): after a drift-bumping close, `ctx.notes()` contains a note whose
body starts `design-sync` and whose `due` reflects the crossed thresholds.

---

## 4. Drop the feature-design ui piggyback

`design-sync` is now the authoritative sync path, so feature-design stops piggybacking a
ui-sync. Edits to `FEATURE_DESIGN` (`uiux_plugin.py:137-154`):

- **Remove** the fact edge `("library-state", "ui-library-sync", "fact",
  EdgeType.create, _drift_over_threshold)` (`:143`).
- **Remove** `UI_LIBRARY_SYNC` and `DESIGN_DECISION_REVIEW` from `phases`
  (`:139`) and their now-dead carry edges `("plan","ui-library-sync",…)` (`:147`) and
  `("ui-library-sync","design-decision-review",…)` (`:148`) and
  `("design-decision-review","implement",…)` (`:149`).
- Feature-design becomes the plain feature path:

```python
FEATURE_DESIGN = Workflow(
    name="feature-design",
    phases=[LIBRARY_STATE, PLAN, IMPLEMENT, VERIFY, CLOSE],
    edges=[
        ("library-state", "plan", "pass", EdgeType.carry),   # sole route out
        ("plan", "implement", "pass", EdgeType.carry),
        ("implement", "verify", "pass", EdgeType.carry),
        ("verify", "close", "pass", EdgeType.carry),
        ("verify", "implement", "fail", EdgeType.carry),
    ],
)
```

`library-state` still runs (facts feed the close-hook cadence note and disclosure) but no
longer branches — the `pass → plan` carry is the only edge out, so it always advances and
never emits `route_unmatched`. `_drift_over_threshold` is deleted (replaced by the three
§2.2 predicates; it has no other caller — confirmed by grep, only ref was `:143`).

### Test updates required
- `tests/test_uiux_routing.py`:
  - `test_feature_drift_at_threshold_routes_to_ui_sync` (`:124-131`) — **delete or
    rewrite**: at-threshold now routes to `plan`, not `ui-library-sync` (that behavior
    moves to `test_design_sync_routing.py`, §2.5).
  - `test_feature_drift_below_threshold_routes_to_plan` (`:113-121`) and
    `test_feature_missing_manifest_low_drift_still_routes_to_plan` (`:134-144`) still
    pass (they already assert `plan`), but their `library_drift` fixtures should move to
    the `{ui_drift, ux_drift}` shape; the legacy-migration path (§1.4) keeps them green
    in the interim.
  - `test_both_workflows_validate` (`:149-153`) now also exercises `design-sync`.
- `tests/test_uiux_phases.py`: `test_resolve_workflows_contains_both` → assert all three.

---

## 5. TRIVIALITY VERDICT — the global / blast-radius hop

**The ask:** a `global`/`tokens` dimension on the `ui-drift` receipt that `mark_stale`
fans out to mark **all** manifest surfaces stale (blast radius for token/theme/shell
changes), plus a full-recapture escape hatch. Build it only if trivial; else defer.

### Assessment against the real code

- `mark_stale` (`library_state.py:130-156`) **already iterates every manifest entry** in
  the `for e in entries:` loop (`:143-148`) and already flips `status → "stale"` with a
  `changed` guard. A "mark all" branch is a superset of a loop it already runs.
- The receipt is a **free-form dict**; `ui-drift` is read with `.get` for `screens` /
  `components` (`uiux_plugin.py:384-386`). A `global`/`tokens` flag already has a home —
  it is one more `.get` on the same dict, no schema to extend.
- The close hook already calls `mark_stale(root, screens=…, components=…)`
  (`:399-400`); adding a keyword is a one-line change.
- The full-recapture escape hatch is *free*: `mark_stale(root, all_surfaces=True)` marks
  every surface stale, and the existing `screenshot-library-sync` surgical phase (§2.4)
  then reshoots exactly that set — which, when all are stale, *is* a full recapture. No
  separate `resync --full` code path is required.

### Exact minimal implementation (≈7 lines, two functions)

`library_state.mark_stale` — add a param + one branch (`:130`, `:143`):

```python
def mark_stale(root, screens=None, components=None, all_surfaces=False) -> bool:
    screens = set(screens or [])
    components = set(components or [])
    if not screens and not components and not all_surfaces:
        return False
    entries = read_manifest(root)
    changed = False
    seen = set()
    for e in entries:
        seen.add(e["screen"])
        tagged = bool(components & set(e.get("components") or []))
        if (all_surfaces or e["screen"] in screens or tagged) and e.get("status") != "stale":
            e["status"] = "stale"
            changed = True
    # (brand-new-screen append loop unchanged)
```

`uiux_plugin._on_close` — read the flag and pass it (`:398-400`):

```python
glob = bool(drift.get("global") or drift.get("tokens"))
if screens or components or glob:
    library_state.mark_stale(root, screens=screens, components=components,
                             all_surfaces=glob)
```

Backward compat: `all_surfaces` defaults `False`; every existing caller and test is
unaffected. The receipt gains an *optional* `global`/`tokens` key — absent means old
behavior.

Minimal test: `mark_stale(root, all_surfaces=True)` flips two fresh entries to stale and
returns `True`; a close with `receipt={"ui-drift": {"global": True}}` marks every
catalogued surface stale.

### VERDICT: **GO (trivial)**

Rationale: the two touch-points are already shaped for it — `mark_stale` already loops
over all surfaces (the branch is a one-condition widening of a loop that exists), and the
receipt is a free-form dict where `global`/`tokens` already has a home (one `.get`). Total
change is ~7 lines across two functions with a default-off param, fully backward
compatible, and the full-recapture escape hatch falls out of `all_surfaces=True` +
the surgical sync phase with **zero** additional code. This clears the triviality bar
decisively; no manual-resync deferral is warranted.

---

## Appendix — change map (files × lines)

| Unit | File | Location | Change |
|---|---|---|---|
| A | `library_state.py` | `206-210` | `_drift_count` → `_drift_counts` (pair, legacy migration) |
| A | `library_state.py` | `213-230` | `evaluate` emits `screenshots.{stale,stale_count,any_stale}`, `ui_drift`, `ux_drift`, `drift`=max |
| A | `library_state.py` | after `156` | add `mark_fresh` |
| A | `uiux_plugin.py` | `390-396` | two-counter bump-both / reset-own |
| A | `uiux_plugin.py` | `407-411` | recommendation cadence note |
| A | `uiux_plugin.py` | in `_on_close` | `mark_fresh` on accepted `screenshot-library-sync` |
| B | `uiux_plugin.py` | `~66`, `76-79` | add `SCREENSHOT_LIBRARY_SYNC` phase |
| B | `uiux_plugin.py` | `108-110` | replace `_drift_over_threshold` with 3 predicates |
| B | `uiux_plugin.py` | `~156` | add `DESIGN_SYNC` workflow; extend `UIUX_WORKFLOWS` |
| B | `uiux_plugin.py` | `137-154` | strip feature-design piggyback → plain feature |
| B | `uiux_plugin.py` | `359-365` | surgical `screenshot-library-sync` disclosure branch |
| GO | `library_state.py` | `130`, `143` | `all_surfaces` param + branch |
| GO | `uiux_plugin.py` | `398-400` | read `global`/`tokens`, pass `all_surfaces` |
