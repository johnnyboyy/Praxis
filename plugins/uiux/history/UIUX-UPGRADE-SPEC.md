# UIUX-UPGRADE-SPEC — turning the bare `uiux` judgment plugin into a full praxis contributor (the IR)

**Status:** implementation spec. No code changed by this document. Every contract below is grounded in
current code with `file:line` references. It builds strictly on the four core seams already landed in
praxis (`registry.py`, `workflow.py` `Phase.run`, `workflow_run.py` deterministic branch,
`situation.phase_name`) — see `skills/praxis/docs/IMPL-SPEC-plugin-phases.md`. It ports the OLD uiux
praxis face (`attempted_skills/plugins/uiux/praxis/…`) onto those seams.

Read alongside: `skills/praxis/docs/plugin-phases.md` (the WHY + the disclosure table), and the OLD
sources it ports — `library_state.py`, `deferred_queue.py`, `phases/library-init.md`,
`phases/library-sync.md`, `phases/design-decision-review.md`, `units.md`.

## Design boundary (what this plugin is and is NOT)

The bare plugin today is `UiuxJudgment` (`skills/praxis-plugins/uiux/uiux_plugin.py:14-37`): it carries
`domains_dir` (`:23`) and a no-op `contribute` (`:30-32`). Corpora discovers that `domains_dir` and
composes the design **judgment** (`corpora/injector.py:117` via `discover_domain_dirs`) — the color /
motion / hierarchy / elevation principles. **This upgrade does not touch that path.** `uiux.contribute`
must never re-inject design domains; corpora owns judgment composition
(`corpora/injector.py:178-186`). What this upgrade adds is the **process face**: phases, a workflow, a
deterministic eligibility fact, graduated disclosure of the *library files* (not domains), close-time
state mutation, and the design→code edit lease.

The upgraded object keeps `source = "uiux"` and `domains_dir` unchanged (so corpora still finds it), and
grows the optional providers `phases()`, `workflows()`, `contribute()`, `hooks()`, `surface()`. All are
read fail-soft by praxis (`registry._provider` `contributors.py:74-82`; `contributors.fire`
`contributors.py:48-55`; `contributors.surface_for` `contributors.py:57-69`; `validate_contributor`
`contributors.py:72-87`).

---

## 1. `phases()` / `workflows()` — the process the contributor registers

`phases(self) -> list[Phase]` and `workflows(self) -> list[Workflow]`, returning real objects imported
from `workflow` (the registry carries the objects with callables intact —
`registry.resolve_phases` `registry.py:85-105`, `resolve_workflows` `registry.py:108-130`). Both are
optional and validated structurally (`validate_phase` `registry.py:30-40`; `validate_workflow`
`registry.py:43-64`). Seed names always win, so none of the names below may collide with `SEED_PHASES`
(`workflow.py:80-83`) — they do not.

### 1.1 Phase objects (five)

Mapping the OLD six corpora processes (ui/ux/screenshot × init/sync) onto praxis phases. The OLD design
already collapsed the three init variants into one phase file (`library-init.md:1-9`) and the three sync
variants into one (`library-sync.md:1-8`); the *variant* is a per-invocation fact read from
library-state, not a separate phase. We keep that collapse and add the deterministic gating phase and the
review phase.

| Phase object | `name` | `stance` | `delivery` | `run`? | `intent` (from OLD) |
|---|---|---|---|---|---|
| `LIBRARY_STATE` | `library-state` | `neutral` | `deterministic` | **yes** — `library_state.evaluate` | eligibility + ordering fact for the root's design libraries (`library_state.py:1-30`) |
| `LIBRARY_INIT` | `library-init` | `divergent` | `spawn` | no | found a project's libraries from nothing; per-variant stance overridden at runtime (`library-init.md:1-27`) |
| `LIBRARY_SYNC` | `library-sync` | `divergent` | `spawn` | no | bring libraries back in line with drifted state (`library-sync.md:1-8`) |
| `DESIGN_DECISION_REVIEW` | `design-decision-review` | `neutral` | `inline` | no | accept/revise/reject a divergent Artifact, file into library (`design-decision-review.md:1-10`) |
| `SCREENSHOT_CAPTURE` | `screenshot-capture` | `neutral` | `spawn` | no | mechanical capture: drive app, shoot each catalogued surface (`library-init.md:44-46`, `library-sync.md:49-51`) |

Notes on the modeling decisions (each a deliberate call, flagged):

- **`library-init` / `library-sync` carry a single dataclass `stance`, but the UI vs UX variant needs
  different stances** (ui-init divergent, ux-init convergent — `library-init.md:18-21`; ui-sync
  divergent, ux-sync convergent — `library-sync.md:24-26`). The `Phase.stance` field is single-valued
  (`workflow.py:29`) and `run_workflow` copies it into `situation.phase` (`workflow_run.py:56`). **We
  cannot encode two stances in one Phase object.** Decision: split each into two named phases —
  `ui-library-init` (divergent) / `ux-library-init` (convergent), and `ui-library-sync` (divergent) /
  `ux-library-sync` (convergent). This makes the variant a *phase name* (routable by an `agent-choice`
  edge, `workflow_run.py:13-23`) rather than a runtime override the stance system can't carry. The
  screenshot variants become the single `screenshot-capture` phase (mechanical, no stance —
  `library-init.md:20-22`, `library-sync.md:20-22,26`). So the concrete phase list is:

  `library-state` (det), `ui-library-init` (div), `ux-library-init` (conv), `ui-library-sync` (div),
  `ux-library-sync` (conv), `screenshot-capture` (neutral spawn), `design-decision-review` (neutral
  inline) — **seven Phase objects**. The `LIBRARY_INIT`/`LIBRARY_SYNC` single-phase rows above are the
  conceptual origin; the shipped objects are the split pair. This keeps stance correct at
  `workflow_run.py:56` and lets `contribute` branch on `situation.phase_name`
  (`workflow_run.py:57`) to pick the variant's disclosure.

- **`screenshot-capture` is one phase used in both bootstrap and sync** — capture is the same mechanical
  move either way (`library-init.md:44-46` vs `library-sync.md:49-51`); init seeds the manifest, sync
  recaptures the stale entries. The stale-set is a fact the phase reads from library-state facts / the
  triggering handoff `ui-drift`, not a separate phase.

### 1.2 Deterministic `run` callable placement

Only `library-state` carries `run` (`workflow.py:33` — `run: object | None`). It is set on the object:

```python
LIBRARY_STATE = Phase("library-state", stance="neutral", delivery="deterministic",
                      intent="library eligibility + ordering fact",
                      produces="library-state", run=library_state.evaluate)
```

`run_workflow` invokes it only because `delivery=="deterministic" and callable(phase.run)`
(`workflow_run.py:72`); the seed deterministic phases `VERIFY`/`COVERAGE_DIFF` (`workflow.py:67,76`)
carry no `run` and fall through to the executor, unaffected (`workflow_run.py:88-89`).

### 1.3 Workflow objects (two)

**`design-bootstrap`** — the init sequence for a project with `has-ui` but no libraries (Demonstration B,
`plugin-phases.md:131-150`). The ordering constraint from OLD `library_state.py:20-23` is: **ui-init
precedes both screenshot-init and ux-init, which are independent of each other** — a content dependency
proxied by `ui-library.md` existing. We express ordering **as edges routed by library-state's `next`**,
per `IMPL-SPEC-plugin-phases.md:337-341` (deterministic `next` + one `agent-choice` edge per branch):

```python
DESIGN_BOOTSTRAP = Workflow(
    name="design-bootstrap",
    phases=[LIBRARY_STATE, UI_LIBRARY_INIT, UX_LIBRARY_INIT, SCREENSHOT_CAPTURE,
            DESIGN_DECISION_REVIEW],
    edges=[
        # library-state routes to the next eligible init (agent-choice keyed on run()'s `next`)
        ("library-state", "ui-library-init",     "agent-choice", EdgeType.create),
        ("library-state", "screenshot-capture",  "agent-choice", EdgeType.create),
        ("library-state", "ux-library-init",     "agent-choice", EdgeType.create),
        # a divergent init's Artifact goes through design-decision-review, then loops back to re-evaluate
        ("ui-library-init",        "design-decision-review", "pass", EdgeType.carry),
        ("ux-library-init",        "design-decision-review", "pass", EdgeType.carry),
        ("design-decision-review", "library-state",          "pass", EdgeType.carry),
        # screenshot capture is mechanical: straight back to re-evaluate
        ("screenshot-capture",     "library-state",          "pass", EdgeType.carry),
    ],
)
```

How ordering (`ui → {screenshot, ux}`) is enforced: it is **not** in the edge topology (all three init
edges leave `library-state`); it is in **which `next` library-state returns**. `library_state.evaluate`
returns `next` = the lowest-numbered eligible init (OLD `library_state.py:92-94`
`next_bootstrap_step`), which is `ui-library-init` while `ui-library.md` is absent, and only becomes
`screenshot-capture` / `ux-library-init` once ui exists (OLD gating `library_state.py:80-85`). Because
`_choose_edge` consults `choice` only when `advance` is true and matches the `agent-choice` edge whose
`t == choice` (`workflow_run.py:13-23`), the workflow *cannot* enter screenshot/ux before ui exists —
the router never names them. The loop back to `library-state` (bounded by `max_phase_loops`,
`workflow_run.py:48-52`) re-derives eligibility after each init lands, exactly the OLD "loop back to
library-state" steps (`plugin-phases.md:140,143`). When all three libraries are present, `evaluate`
returns `passed=True, next=None` → `_choose_edge` finds no `agent-choice` match, no `pass` edge from
`library-state` → the workflow exits (`workflow_run.py:117-119`). Bootstrap complete.

**`feature-design`** — the fragment spliced into feature work (Demonstration A, `plugin-phases.md:109-126`).
It front-loads the same deterministic gate, then design-then-implement:

```python
FEATURE_DESIGN = Workflow(
    name="feature-design",
    phases=[LIBRARY_STATE, PLAN, UI_LIBRARY_SYNC, DESIGN_DECISION_REVIEW, IMPLEMENT, VERIFY, CLOSE],
    edges=[
        ("library-state", "plan",           "pass",         EdgeType.carry),   # libraries present → design
        ("library-state", "ui-library-sync", "agent-choice", EdgeType.create), # drift over threshold → sync first
        ("plan",          "ui-library-sync", "pass",         EdgeType.carry),
        ("ui-library-sync","design-decision-review","pass",  EdgeType.carry),
        ("design-decision-review","implement",  "pass",      EdgeType.carry),
        ("implement",     "verify",          "pass",         EdgeType.carry),
        ("verify",        "close",           "pass",         EdgeType.carry),
        ("verify",        "implement",       "fail",         EdgeType.carry),
    ],
)
```

`PLAN`, `IMPLEMENT`, `VERIFY`, `CLOSE` are the **seed** phases (`workflow.py:80-83`) — the registry
merges them in, the workflow only references them by name (`validate_workflow` checks every edge/phase
endpoint resolves in the merged table, `registry.py:51-63`). The `library-state → plan` `pass` edge vs.
the `library-state → ui-library-sync` `agent-choice` edge is the drift branch: `evaluate` returns
`next="ui-library-sync"` when drift is over threshold, else `passed=True, next=None` and the `pass` edge
to `plan` fires (`workflow_run.py:113-119`).

### 1.4 Minimal test (`tests/test_uiux_phases.py`)

- `resolve_phases(root, [uiux])` (`registry.py:85`) contains all seven uiux phase names plus seed `plan`;
  `resolve_workflows(root, [uiux])` contains `design-bootstrap` and `feature-design`.
- A uiux Phase named `plan` (were one authored) does **not** override the seed (`registry.py:97-99`
  collision skip) — guards the boundary.
- `validate_workflow(DESIGN_BOOTSTRAP, resolve_phases(root,[uiux]))` returns `[]` (every edge endpoint
  resolves).

---

## 2. `library_state` → `Phase.run` adaptation

The OLD `library_state.py` is a CLI (`build_state(root)` `:56-103`, `main` `:141-150`). The port wraps
`build_state` in the deterministic-phase callable contract (`workflow.py:33`,
`IMPL-SPEC-plugin-phases.md:276-284`):

```python
def evaluate(root: Path, unit, composed: dict) -> dict:
    s = build_state(root)                       # OLD library_state.build_state, verbatim
    nxt = _route(s)                             # map the fact -> a phase name (or None)
    return {"passed": True, "next": nxt,
            "facts": {"library_state": s},
            "produces": s}
```

`build_state` is ported **unchanged** except its state-dir resolution (see §6). It already returns the
whole fact praxis needs (`library_state.py:96-103`): `has_ui`, `libraries{ui,ux,screenshots}`, the six
`phases[]` rows with `eligible/unit_of_work/stance/mechanical/bootstrap_phase/drift_gated/blocked_by`
(`:72-89`), `eligible[]`, and `next_bootstrap_step` (`:94`).

**What `facts` carries** — the entire `build_state` dict under key `library_state`. `run_workflow`
journals it as a `phase.facts` event (`workflow_run.py:82-84`) and it is the substrate `contribute`
reads for disclosure (§3): the surface inventory (`libraries`, the per-phase `unit_of_work`/`stance`) and
eligibility. It is also set as `produces` so it carries to the next phase as `composed["carry"]`
(`workflow_run.py:110-111,63-66`) — the init/sync spawn phases read the variant + eligibility from it
rather than recomputing.

**What `next` returns** (`_route`, the new thin mapping — the ONLY new judgment beyond OLD):

- Bootstrap regime (`design-bootstrap`): return `s["next_bootstrap_step"]` directly — it is already
  `"ui-library-init"` while ui absent, `"screenshot-library-init"`/`"ux-library-init"` once ui exists
  (OLD `:92-94`). Remap the OLD `screenshot-library-init` name → the shipped `screenshot-capture` phase
  name; `ui-library-init`/`ux-library-init` match the shipped phase names 1:1. When
  `next_bootstrap_step is None` (all present), return `None` → workflow exits.
- Feature regime (`feature-design`): if any sync phase is `eligible` **and** drift is over threshold
  (see below), return `"ui-library-sync"`; else return `None` so the `pass` edge to `plan` fires.

`_route` is a pure function of the `build_state` fact plus the drift counter — deterministic, no judgment
(the judgment stays in the phase files, per OLD `library_state.py:8-9`).

**Drift is a counter the PLUGIN owns now, not a corpora counter.** OLD `library_state.py:25-26,86-89`
explicitly refused to compute drift — it marked syncs `drift_gated: true` and left the count to a corpora
counter (`library-drift.since-last-sync ≥ 3`, `library-sync.md:12-14`). In the upgraded plugin there is
no corpora counter to defer to; **uiux owns it**. It lives in the uiux config namespace (§6):
`config.read(root, "uiux").get("library_drift", {"since_last_sync": 0})`. `_route` reads it to decide the
`feature-design` sync branch (`since_last_sync >= 3`, the OLD threshold `library-sync.md:12`); the `close`
hook (§4) increments it; a completed sync resets it to 0 (OLD `sync-done`, `library-sync.md:47`). So
`build_state` stays a pure filesystem fact (unchanged), and the drift *threshold* decision moves into
`_route`/hooks reading plugin-owned config — the single behavioral change from OLD, and a deliberate one
(there is no longer an external counter).

### 2.1 Minimal test (`tests/test_library_state_phase.py`)

- Fixture root with `.praxis/config.json` `{"uiux":{"has_ui":"yes"}}`, no library files → `evaluate`
  returns `{"passed":True,"next":"ui-library-init","facts":{"library_state":{...}}}`; the fact's
  `libraries=={"ui":False,"ux":False,"screenshots":False}` (OLD `:99`).
- Add `ui-library.md` → `evaluate` `next` becomes `"screenshot-capture"` (lowest-numbered eligible
  init after ui, OLD ordering `:92-94`), proving ui→{screenshot,ux} ordering is data-driven.
- All three present, drift below 3 → `next is None`, `passed True` (workflow exits).
- All present, `library_drift.since_last_sync = 3` in config → feature regime `_route` returns
  `"ui-library-sync"`.

---

## 3. `contribute()` — graduated disclosure keyed on `situation.phase_name`

`contribute(self, situation) -> list[Contribution]` (`contributors.py:13-19,25`). It branches on
`situation.phase_name` (`situation.py:29`), the named-phase channel set by `run_workflow`
(`workflow_run.py:57`); `situation.phase` remains stance (`workflow_run.py:56`) and is **not** read here
(corpora reads stance, `injector.py:136`). This implements the disclosure table
`plugin-phases.md:94-101`. **Substrate is the library-state fact** — `contribute` reads it from
`situation`-adjacent state, not by recomputing: it calls `build_state(self.root)` (cheap, pure FS) to get
the surface inventory (`library_state.py:56-103`), then injects an **index + paths**, inlining at most a
handful — never a whole library (`plugin-phases.md:74-92`). It never injects design domains (corpora's
job, §Design boundary).

`Contribution(source, title, body, priority, meta)` (`contributors.py:12-19`). All emitted with
`source="uiux"`. Priorities chosen to sit **below** corpora's principle tiers so the map frames the
judgment (corpora anchor `-10`, conventions `0`, principles `10` — `injector.py:157,174,185`); uiux uses
`priority=5` for the index (after conventions, before principles) and `priority=-5` for a divergent
consistency pin (near the anti-mean anchor).

Per `phase_name`:

| `phase_name` | Contributions emitted |
|---|---|
| `plan` | **index only.** One `Contribution("uiux","Design surface inventory", <index>, priority=5)`. `<index>` = for each library surface: `{id · one-line role · file path · screenshot path + freshness}` built from `build_state` `libraries` + the manifest (`plugin-phases.md:96`). Lets the planner name the surfaces to touch. No library bodies. |
| `ui-library-init` (divergent) | **nothing to disclose** — identity is authored from the rendered app, not a library (`plugin-phases.md:100`). Emit `[]` (or a single instruction Contribution pointing the spawn at the app + the `bootstrap-ui-surface` unit-of-work, no library content). |
| `ux-library-init` (convergent) | **full `ui-library.md`** — UX must cohere with the freshly-built UI identity (`plugin-phases.md:99`). One `Contribution("uiux","UI library (full)", <ui-library.md contents>, priority=5)`. This is the one full-body inline; it is a *convergent* phase, so an attractor is desired. |
| `ui-library-sync` / `ux-library-sync` (a *divergent* design pass) | **index + curated consistency pin + anti-mean-by-reference + screenshots by reference** (the `design` row, `plugin-phases.md:97`). Three Contributions: the index (`priority=5`); a **small** curated pin = only the tokens/constraints the touched surface must not violate, drawn from the named surfaces in `situation.targets` (`priority=-5`); and adjacent screenshots **by path reference** (not inlined bytes — the spawn opens them via vision on demand, `plugin-phases.md:89-92`). **Not** the full `ui-library.md`. |
| `implement` | **full specs of the named few** (`plugin-phases.md:98`). For each component the plan named (`situation.targets`), inline that component's section from `ui-library.md` — reuse fidelity. Never the whole library. One `Contribution` per named surface, `priority=5`. |
| `screenshot-capture` | the manifest index + the stale-set to (re)capture (`priority=5`), read from the library-state fact / triggering `ui-drift`. Mechanical; no judgment content. |
| `design-decision-review` | `[]` — this is an operator decision, no engine composition (`design-decision-review.md:18-21`). |

**Fallback when `phase_name is None`** (single-dispatch, no workflow driving — the compatibility invariant
`IMPL-SPEC-plugin-phases.md:243-247`): emit the **index only** (the `plan`-row default) — a sensible,
cheap map with no full-body inline and no attractor risk. This is what the bare plugin's callers see
today, so it is safe for the non-workflow path. Concretely: `if situation.phase_name is None: return
[self._index_contribution()]`.

### 3.1 How it reads the facts / files

- Surface inventory + freshness → `build_state(self.root)` (`library_state.py:56-103`) + the screenshot
  manifest (`{state_dir}/screenshots/manifest.md`, `library_state.py:68`).
- Full/section bodies → read the library file at the path `build_state` resolved (`ui_rel`/`ux_rel`,
  `library_state.py:63-64`, honoring a config relocation, `:41-42`). Section slicing for the
  "named-few" rows is by markdown heading matching `situation.targets`.
- Screenshots are always **path references**, never inlined (`plugin-phases.md:89-92`).

### 3.2 Minimal test (`tests/test_uiux_contribute.py`)

- `phase_name="plan"` → exactly one Contribution, title "Design surface inventory", body contains the
  surface paths, contains **no** full library body.
- `phase_name="ux-library-init"` with a fixture `ui-library.md` → a Contribution whose body **equals**
  the file contents (full inline).
- `phase_name="ui-library-sync"` → index + a consistency-pin Contribution at `priority=-5` + screenshot
  refs; assert the full `ui-library.md` body is **absent** (divergent non-disclosure).
- `phase_name=None` → single index Contribution (fallback), no full bodies.
- `contribute` emits nothing owned `owner`-tagged as a design domain (boundary: corpora still owns
  domains).

---

## 4. `hooks()` — the `close` hook

`hooks(self) -> dict[str, StepHook]` (`contributors.py:45,48-55`). Return `{"close": self._on_close}`.
`_on_close(ctx: HookContext)` fires at unit close (`contributors.fire(contributors,"close",ctx)`
`contributors.py:48-55`). It ports the OLD close-time behavior split across the phase files
(`plugin-phases.md:121,144`; `design-decision-review.md:36-45`).

**What it reads from `HookContext`** (`contributors.py:28-42`): `ctx.root` (the praxis root, for state
paths §6); `ctx.unit` (its `id`, and `unit.situation` for `phase_name`/`targets` — the touched surfaces);
`ctx.receipt` (the handoff/Artifact dict — its `ui-drift.screens`/`.components`, `stance`, and library
target); `ctx.verdict`. Helpers `ctx.add_note` / `ctx.notes` (`:37-42`) journal a trace.

Three actions (each gated on what the unit was):

1. **Bump the drift counter for touched surfaces** (`plugin-phases.md:121,144`; OLD threshold
   `library-sync.md:12-14`). Read the touched surfaces from `ctx.unit.situation.targets` /
   `ctx.receipt["ui-drift"]`; increment `config.read(ctx.root,"uiux")["library_drift"]["since_last_sync"]`
   by 1 (per unit that touched a UI surface), via `config.write(ctx.root,"uiux",…)` (`config.py:23-30`).
   This is the counter §2 said uiux now owns. A **completed sync** unit (`phase_name` ∈
   {`ui-library-sync`,`ux-library-sync`} with an accepted Artifact) instead **resets** it to 0 (OLD
   `sync-done`, `library-sync.md:47`).
2. **Mark changed surfaces' screenshots stale** (`plugin-phases.md:121`; OLD screenshot-mark-stale
   `library-sync.md:49-51`). From `ctx.receipt["ui-drift"].screens`/`.components`, mark those entries in
   `{state_dir}/screenshots/manifest.md` stale (expanding components → their tagged screens, OLD
   `library-sync.md:49-50`). If no drift reported, no-op. A brand-new screen with no capture is marked
   stale so the next `screenshot-capture` shoots it (`plugin-phases.md:121`).
3. **File an accepted design-decision Artifact into the library** (`design-decision-review.md:31-38`).
   Only when the closing unit is a `design-decision-review` acceptance (or a divergent init/sync whose
   Artifact targets `ui-library.md`/`ux-library.md`, the routing fact `design-decision-review.md:12-14`):
   write the accepted content into `ui-library.md`/`ux-library.md`, **replacing the superseded section
   outright — no dates, no "supersedes", no naming what was rejected** (`design-decision-review.md:32-35`).
   Then **resolve any deferred-queue entry this settles** — call the ported `deferred_queue.resolve(root,
   id, resolution)` (OLD `deferred_queue.py:188-221`), which keeps it as a trace, not a delete
   (`design-decision-review.md:42-45`, OLD `deferred_queue.py:38-42`). `ui-drift` stays open until this
   write happens (`design-decision-review.md:39-41`) — a revise/reject fires none of action 3 and leaves
   drift as-is.

The hook is fail-soft by construction: `fire` calls it inside the contributor loop with no try/except
(`contributors.py:48-55`), so `_on_close` must not raise on a missing file / absent config — guard each
action (mirror OLD `deferred_queue.cmd_resolve`'s existence checks `:193-199`).

### 4.1 Minimal test (`tests/test_uiux_hooks.py`)

- `hooks()["close"]` is callable; `validate_contributor` passes (`contributors.py:79-81`).
- Close a unit whose `receipt["ui-drift"]={"screens":["settings"]}` → drift counter incremented by 1 in
  `config.read(root,"uiux")`; the `settings` manifest entry marked stale.
- Close a `ui-library-sync` acceptance → counter reset to 0.
- Close a `design-decision-review` accept whose Artifact targets `ui-library.md` and settles deferred id
  `X` → `ui-library.md` contains the new section; `deferred-decisions.md` entry `X` is `status: resolved`
  with a `resolution:` (kept, not deleted — OLD `deferred_queue.py:212-219`).

---

## 5. `surface()` — the docs-only design lease

`surface(self, situation) -> list[str] | None` (`contributors.py:57-69`, `IMPL-SPEC-plugin-phases.md:59-77`).
Returns the edit-lease globs **only for design/library phases**, else `None` ("no opinion", so the
default `situation.targets` lease stands — `IMPL-SPEC-plugin-phases.md:80-85`). This is the hard
design→code boundary from OLD `units.md:5-9`: a design unit's work lands in documents, never source; the
first source edit bounces into its own implement unit (`units.md:6-9`).

```python
def surface(self, situation):
    DESIGN_PHASES = {"ui-library-init", "ux-library-init", "ui-library-sync",
                     "ux-library-sync", "design-decision-review"}
    if situation.phase_name in DESIGN_PHASES:
        return ["docs/*", "docs/**", "*.md", ".praxis/**"]
    return None
```

Globs are the OLD unit lease surfaces (`units.md:11,15,19` — `docs/*, *.md, .corpora/*`), retargeted from
`.corpora/*` to `.praxis/**` since library state moves under the praxis root (§6), and widened to
`docs/**` for nested design docs. `screenshot-capture` is **excluded** — it captures images into the
manifest dir (state, leased via `.praxis/**` if needed), and returning `None` for it lets its capture
work proceed under the default lease. The dialect is fnmatch, matching enforcement
(`units.surface_allows` referenced in `IMPL-SPEC-plugin-phases.md:64`). `surface_for` unions across
contributors and the gate denies everything outside the union (`IMPL-SPEC-plugin-phases.md:85`), so a
present uiux claim authoritatively bars source under a design phase.

### 5.1 Minimal test (`tests/test_uiux_surface.py`)

- `surface(sit(phase_name="ui-library-sync"))` → the docs/`.praxis` globs; `surface_for([uiux], sit)`
  returns the sorted union (`contributors.py:57-69`).
- `surface(sit(phase_name="implement"))` and `phase_name=None` → `None` (source phases keep their
  `targets` lease).
- Assert a `src/*.py` path is **not** matched by the returned design globs (the design→code bar,
  `units.md:6-9`).

---

## 6. Owned-state layout — where the libraries, manifest, drift, and queue live

OLD uiux stored everything under the corpora state dir `.corpora/` (or legacy `corpora/`), resolved by
`state_dir(root)` (`library_state.py:45-48`, `deferred_queue.py:62-65`). In an upgraded praxis root the
managed-state marker is `.praxis/config.json` (`config.py:5-8,33-41`), and the plugin owns a **named
config scope** `"uiux"` (`config.py:20-30` — "every named scope belongs to a plugin"). Layout:

| State | Location | Resolved by | Ported from |
|---|---|---|---|
| `has-ui` flag | `config.read(root,"uiux")["has_ui"]` | `config.py:20` | OLD `has-ui:` in `config.md` (`library_state.py:39,62`) |
| `ui-library.md` | project path, default `docs/design/ui-library.md`; relocatable via `config.read(root,"uiux")["ui_library"]` | new `_lib_paths(root)` | OLD `ui-library:` config key / `{base}/ui-library.md` (`library_state.py:41,63`) |
| `ux-library.md` | default `docs/design/ux-library.md`; relocatable via `["ux_library"]` | same | OLD `ux-library:` (`library_state.py:42,64`) |
| screenshot manifest + images | `.praxis/uiux/screenshots/manifest.md` + `.praxis/uiux/screenshots/*.png` | `_state_dir(root)/screenshots` | OLD `{base}/screenshots/manifest.md` (`library_state.py:68`) |
| drift counter | `config.read(root,"uiux")["library_drift"]["since_last_sync"]` (int) | `config.py` | **new** — OLD deferred this to a corpora counter (`library_state.py:25-26`); uiux now owns it (§2) |
| deferred queue | `.praxis/uiux/deferred-decisions.md` | `deferred_queue.queue_path` retargeted | OLD `{base}/deferred-decisions.md` (`deferred_queue.py:68-69`) |

**How the plugin resolves them from the root** — a single helper the ported scripts share, replacing OLD
`state_dir`:

```python
def _state_dir(root: Path) -> Path:     # replaces library_state.state_dir / deferred_queue.state_dir
    return Path(root) / ".praxis" / "uiux"

def _lib_paths(root):
    cfg = config.read(root, "uiux")
    ui = Path(root) / cfg.get("ui_library", "docs/design/ui-library.md")
    ux = Path(root) / cfg.get("ux_library", "docs/design/ux-library.md")
    return ui, ux
```

Design decision (flagged): **`has-ui` and library paths move from a parsed `config.md` (regex, OLD
`library_state.py:39-64`) into the typed `uiux` config scope** (`config.read`/`write`, `config.py:20-30`)
— the config store already holds nested objects and lists (`config.py:5-6`), so `library_drift` is a
native `{"since_last_sync": int}` rather than a hand-parsed counter. `build_state`'s regex parsing
(`library_state.py:39-64`) is replaced by `config.read` lookups; the rest of `build_state` (existence
checks, phase table, ordering `:66-103`) is unchanged. This is the one structural port beyond a
path-retarget, and it removes the `.corpora/config.md` dependency entirely.

Rationale for library files at `docs/design/` (not under `.praxis/`): the design lease is `docs/**`
(§5), the libraries are human-facing design artifacts the OLD `units.md:6-8` already routed into
`docs/`/`.corpora/`, and keeping them in `docs/` means the `surface()` docs lease already covers writes to
them. The manifest+images and queue are plugin *working state* → under `.praxis/uiux/`.

---

## Build split

Two units, each independently landable and testable, mirroring the process/contribute seam.

### PROCESS unit — phases, workflow, deterministic fact, ported scripts

Scope: everything that is pure praxis-object + ported CLI, no `contribute`/`hooks`/`surface`.

- Port `library_state.py` → module `uiux_library_state.py`: keep `build_state` (`:56-103`) minus the
  regex config parse (§6 `_state_dir`/`_lib_paths` + `config.read`); add `evaluate(root,unit,composed)`
  and `_route` (§2).
- Port `deferred_queue.py` verbatim except `state_dir`/`queue_path` retarget to `.praxis/uiux/` (§6). Its
  `resolve` (`:188-221`) is called by the close hook (§4).
- Define the seven `Phase` objects (§1.1) and two `Workflow` objects (§1.3) in the plugin module; add
  `phases()`/`workflows()` providers returning them.
- Tests: `test_uiux_phases.py` (§1.4), `test_library_state_phase.py` (§2.1), plus the ported
  `test_deferred_queue.py` (retargeted paths).
- Verifies via: `resolve_phases`/`resolve_workflows` (`registry.py:85,108`) see the objects;
  `run_workflow` drives `design-bootstrap` end-to-end against a fixture root (deterministic
  `library-state` routing only, no spawn executor — a capture executor for the spawn phases).

### CONTRIBUTE unit — disclosure, hooks, lease, state config

Scope: the runtime behaviors reading the PROCESS unit's fact.

- `contribute(situation)` graduated disclosure keyed on `phase_name` (§3), reading `build_state` +
  library files; the `phase_name is None` fallback.
- `hooks()` → `close` (§4): drift bump/reset, screenshot-stale, file-accepted-decision + deferred
  resolve.
- `surface(situation)` design-lease globs (§5).
- The `uiux` config-scope helpers (§6): `has_ui`, `library_drift` read/write, `_lib_paths`.
- Tests: `test_uiux_contribute.py` (§3.2), `test_uiux_hooks.py` (§4.1), `test_uiux_surface.py` (§5.1).
- Depends on the PROCESS unit (reads `build_state`, the phase names, `deferred_queue.resolve`).

The bare plugin (`uiux_plugin.py`) is edited in place both units: `source`/`domains_dir` unchanged
(`:19-23`), `contribute` grows from no-op (`:30-32`) to §3, and the four new providers are added.
`make(root)` (`:35-37`) unchanged.

---

## Risk notes

- **Two-stance split of init/sync (§1.1)** — the single `Phase.stance` field (`workflow.py:29`) forced
  `ui-*`/`ux-*` into separate named phases. Blast radius: the `design-bootstrap` edges must name the
  split phases, and `_route` must return the split names, not the OLD collapsed `library-init`. If a
  future `Phase` grew a per-variant stance channel, these could recollapse; the split is the safe choice
  today and keeps `situation.phase` a valid stance at `workflow_run.py:56`.
- **Drift counter ownership move (§2, §6)** — the single behavioral departure from OLD, which explicitly
  deferred drift to an external corpora counter (`library_state.py:25-26`). uiux now owns the threshold
  in its config scope. Risk: two writers (close hook increments, sync resets) must agree on the key
  shape `{"since_last_sync": int}`; `config.write` is a shallow merge (`config.py:26-30`), so nest under
  a single `library_drift` object written whole, never two sibling keys.
- **`verifiers=None` on the workflow path** (`IMPL-SPEC-plugin-phases.md:381-383`) — `feature-design`'s
  `carry`/`fail` gates are recorded, not enforced, until a verifier map is wired. The design→code lease
  (§5) is enforced independently by the gate (`surface_for`), so the *safety* boundary holds; only the
  preservation gates are advisory for the first cut.
- **`agent-choice` routing depends on `advance` (`passed and verified`)** (`workflow_run.py:114-116`) —
  `library_state.evaluate` must always return `passed=True` (it is a fact, never a failure) or its `next`
  is ignored and the router stalls. The `_route`→`None` case (all libraries present / drift low) is not a
  failure; it is "no branch," letting the `pass` edge fire. Test both explicitly (§2.1).
- **Fallback disclosure when `phase_name is None`** — the single-dispatch path (`run_unit` without a
  workflow, `IMPL-SPEC-plugin-phases.md:188-189`) still calls `contribute`. Returning the index-only map
  is safe, but means a non-workflow design edit gets no lease from `surface` either (it returns `None`);
  the design→code bar only exists **inside** a uiux workflow. Flagged: bootstrapping/feature-design must
  run as workflows for the lease to bind (the operator-owned trigger, `IMPL-SPEC-plugin-phases.md:348-352`).
- **Screenshot capture is spawn/tool work, not a phase primitive** (`plugin-phases.md:170-173`,
  `IMPL-SPEC-plugin-phases.md:345-347`) — `screenshot-capture` is a `delivery="spawn"` phase; if no
  browser tool is available the spawn must surface the skip, not report the cache complete (OLD
  `library-init.md:46`, `library-sync.md:51`). The plugin owns only the manifest write (the hook/spawn
  hands back images), not the capture mechanism.
```
