# Plugin-extensible phases — proposal + two worked demonstrations

**Status:** proposal, no code yet. Grounds the "make phases extensible by plugins" decision in two
end-to-end walkthroughs so the shape can be judged before building.

Companion to `docs/plugins.md` (the Contributor contract) and `docs/design.md` (phases/workflows).

## Why

The phase/workflow engine (`workflow.py`, `workflow_run.py`) is **built and tested but unwired** —
nothing on the live drive path constructs a Phase or Workflow. Accretion surfaces gaps and lets an
operator mint a *term string*, but it does **not** synthesize a runnable Phase — so "grow phases from
gaps" is a naming loop, not a phase factory. To let a plugin like `uiux` carry real process
(library-init / library-sync / design-decision-review) rather than just judgment, the phase system
must become extensible. The good news: the seams already exist; this is **wiring + one optional
provider**, not a re-architecture.

## The four core changes (rides existing seams)

1. **Contributor `phases()` / `workflows()` provider** — optional methods, mirroring the existing
   optional `hooks()` (`contributors.py`). Their returns merge into `SEED_PHASES` / `SEED_WORKFLOWS`,
   turning those hardcoded dicts into a **registry keyed off `contributors_for(root)`**. Reuses the
   exact `module:factory` config loading plugins already use — no new registration surface.
2. **Wire `run_workflow` into a live drive surface** and resolve the (currently dead)
   `Situation.workflow` string through that registry. The runner already threads the named phase into
   `situation.phase` / `composed["phase"]`, so contributors gain **named-phase awareness** for free
   once it's reachable. (Today `situation.phase` is stance-only; the named channel exists but is
   unreached.)
3. **`delivery == "deterministic"` branch** in `run_workflow` — run a plugin-supplied callable/script
   instead of the agent executor, and record its output as a fact. This is how a plugin ships a
   deterministic phase (e.g. uiux's `library_state` eligibility).
4. **Contributor-declared edit surface** — let a Contributor set a unit's `targets`/`surface`. The
   **enforcement half already works**: `gate.py` + `units.surface_allows` glob-deny out-of-lease
   edits today. Only the *declaration* seam is missing.

Each change is independently useful; together they let a plugin contribute phases, a workflow, a
deterministic fact-phase, and an edit lease.

## What `uiux` provides once the four land

A **full contributor** (not the bare judgment plugin):

- **`domains_dir`** → design judgment (already migrated; composed by `corpora`).
- **`phases()`** → `library-init`, `library-sync`, `design-decision-review`, and a deterministic
  `library-state` phase.
- **`workflows()`** → a `design-bootstrap` workflow (the init sequence) and a `feature-design`
  fragment spliced into feature work.
- **`contribute(situation)`** → keyed on `situation.phase` (now the phase *name*): injects the
  library-state fact, the relevant surfaces + current screenshots, and per-variant instructions.
- **`hooks()`** → `close`: bump `library-drift`, mark changed surfaces' screenshots stale, file an
  accepted design decision into the library.
- **declared edit surface** → design/init units lease `docs/**, *.md, .praxis/**` (never source).
- **owned state** → `ui-library.md`, `ux-library.md`, screenshot manifest+images, deferred queue,
  drift counter (in the project / plugin config namespace).
- **shipped scripts** → `library_state.py`, `deferred_queue.py` (called from the deterministic phase
  and hooks).

`library_state` eligibility rules (from the existing script), the backbone of both scenarios:

```
ui-library-init         has-ui AND no ui-library.md                bootstrap, divergent
screenshot-library-init has-ui AND ui-library.md AND no manifest   bootstrap, mechanical
ux-library-init         has-ui AND ui-library.md AND no ux-library  bootstrap, convergent
ui/ux/screenshot-sync   library exists                             ongoing, drift-gated
```

---

## Graduated disclosure — how libraries reach a phase

The libraries (`ui-library.md`, `ux-library.md`, screenshot manifest+images) are large, file-backed
project artifacts. `contribute` does **not** inject them in full. The default is **suggest** (an
index + paths); **full** inlining is the exception, reserved for the specific entries the current
phase operates on. Full-library injection is *specifically avoided in the divergent design phase*.

Injecting a whole library every phase is wrong three ways: it blows context budget; it creates an
**attractor** the model can't override — fatal for a divergent phase whose job is to push *away* from
the existing mean; and it drags in stale/irrelevant surfaces. So the mechanism mirrors the judgment
injector: **the plugin surfaces an index (coarse); the model pulls the specifics it needs (fine).**

Disclosure is set on two axes:

1. **Which entries** — relevance. The surfaces the task touches (named by the plan), never the whole
   catalog.
2. **How much of each** — index vs. full, keyed on **stance**: *convergent phases disclose more* (they
   must cohere with what exists); *divergent phases disclose less* (they must differentiate from it).

The substrate is the `library-state` fact: a compact manifest of `{id, one-line role, file path,
screenshot path + freshness}`. Because the libraries are files in the project, **"full" is always
pull-on-demand**: `contribute` injects the index + paths, and the spawn reads a specific file or opens
a specific screenshot (vision) only when it decides it needs it — so `contribute` never chooses
between "tiny hint" and "paste the whole thing"; it hands a map and inlines only a handful.

| Phase | Stance | What `contribute` injects |
|-------|--------|---------------------------|
| `plan` | reuse-oriented | **index only** — surface names + one-liners + paths, so the planner designs for reuse and *names* the surfaces to touch |
| `design` | divergent | index + a **small curated consistency pin** (only the tokens/constraints the new surface must not violate) + anti-mean anchor + adjacent screenshots **by reference**. **Not** the full `ui-library.md` |
| `implement` | convergent | **full specs of the named few** only (the components the plan named), for reuse fidelity — still never the whole library |
| `ux-library-init` | convergent | the freshly-built `ui-library.md` **in full** — UX must cohere with the UI identity |
| `ui-library-init` | divergent | nothing to disclose — the identity is authored from the rendered app, not a library |

This rule is a function of the **named phase** (`design` suggests, `implement` discloses the named
few, `ux-init` discloses ui fully) — which `contribute` can only act on if it knows which named phase
it is in. So graduated disclosure is another concrete dependency on **Change 2 (named-phase wiring)**.

---

## Demonstration A — a new feature request

**Request:** "Add a Settings screen." Project already has UI libraries (bootstrapped).

| # | Step | Which seam / piece |
|---|------|--------------------|
| 1 | praxis frames the unit; resolves `Situation.workflow` → `feature-design` (a uiux-registered workflow spliced into the default feature path). | **Change 2** (workflow registry) |
| 2 | **Phase `library-state`** runs first — a deterministic script phase. `library_state.py` reports: has-ui, libraries present, drift below threshold → **no init/sync needed**; emits the surface inventory as a fact. | **Change 3** (deterministic delivery) |
| 3 | **Phase `plan`** (core). `contribute` runs with `phase="plan"`: corpora composes coding+design judgment for planning; uiux injects the relevant existing surfaces so the planner designs Settings *against the real component inventory* (reuse, not reinvention). | **Change 2** (named phase) + corpora |
| 4 | **Phase `design`** (divergent, uiux-registered). Unit leases `docs/**, *.md` — the gate **denies any source edit**. uiux `contribute` (phase=`design`) injects: the anti-mean anchor (via corpora, divergent), design domains (color/motion/…), current screenshots of adjacent screens. The spawn authors the Settings design decision into a draft. | **Change 1+4** (phase + lease), corpora divergent |
| 5 | **Phase `design-decision-review`** (uiux-registered). The divergent Artifact is reviewed accept/revise/reject. On accept, a `close`-style hook **files it into `ui-library.md`** — not the ratify gate (a design decision has no `condition` to weigh). | **Change 1** (phase) + `hooks()` |
| 6 | **Phase `implement`** (core). Lease flips to source. corpora composes coding judgment (the `general` plugin's `coding-general`/testing), `change`/preservation lens. The spawn builds the screen. | corpora, existing gate |
| 7 | **Phase `verify`** (core) → passes. | existing |
| 8 | **`close`** across the unit: uiux hook bumps `library-drift` for the touched surface and **marks the Settings screenshot stale** (a new screen exists with no current capture). | `hooks()` |

**Outcome:** the feature ships *and* the design system stays coherent — the new screen was designed
against the real inventory, its identity decision is recorded in the library, and drift is flagged
for the next sync. Every non-core step is plugin-contributed; praxis enforced phase order and the
design→code lease.

---

## Demonstration B — bootstrapping an existing project

**Situation:** an existing app, `has-ui: yes`, but **no** `ui-library.md`, `ux-library.md`, or
screenshot manifest. The design libraries have never been established.

| # | Step | Which seam / piece |
|---|------|--------------------|
| 1 | Operator invokes the design-bootstrap. praxis resolves `Situation.workflow` → uiux's **`design-bootstrap`** workflow. | **Change 2** (workflow registry) |
| 2 | **Phase `library-state`** (deterministic) runs. `library_state.py`: has-ui, no libraries → eligible = `ui-library-init` first; `screenshot-init` and `ux-init` gated behind `ui-library.md` existing. Emits the eligibility+ordering fact; the workflow's edges route on it. | **Change 3** (deterministic) + **Change 2** (conditional edges) |
| 3 | **Phase `library-init` (ui variant, divergent).** uiux `contribute` (phase=`library-init`, and it reads the library-state fact to know it's the *ui* variant) injects: "catalog this project's UI identity — components, tokens, patterns — from the rendered app." Lease = `docs/**, *.md`. The spawn drives the app to observe surfaces and authors **`ui-library.md`**. | **Change 1** (phase) + **Change 4** (lease) + named phase |
| 4 | Loop back to **`library-state`**: now `ui-library.md` exists → `screenshot-library-init` (mechanical) and `ux-library-init` (convergent) become eligible, independent of each other. | **Change 3** + conditional edges |
| 5 | **Phase `library-init` (screenshot variant, mechanical).** This is largely capture: the spawn drives the app to screenshot each catalogued surface; uiux's hook/script writes the **screenshot manifest** and stores images. (Capture is spawn/tool work; the plugin owns the manifest.) | spawn work + plugin state |
| 6 | **Phase `library-init` (ux variant, convergent).** uiux `contribute` injects convergent UX-pattern judgment; the spawn authors **`ux-library.md`** against the established ui-library. Lease = docs. | **Change 1** + corpora convergent |
| 7 | **`library-state`** now reports all three present → bootstrap complete; the workflow exits. Ongoing work will use the *sync* variants (drift-gated), not init. | **Change 3** |
| 8 | **`close`:** drift counter initialized to zero; the project is now in the "libraries present" regime — Demonstration A's feature flow is unlocked. | `hooks()` |

**Outcome:** a project with no design system now has `ui-library.md`, `ux-library.md`, and a
screenshot manifest, built in the correct dependency order (ui → {screenshot, ux}), each under the
right stance, with design units structurally barred from touching source. The *ordering and
eligibility* were a deterministic fact; the *content* was plugin judgment; the *phase shape* was
plugin-registered but praxis-run.

---

## What the two scenarios prove about the four changes

- **Change 1 (phase provider)** is exercised by every non-core step (`library-init`, `-sync`,
  `design-decision-review`) — none of which core should hardcode.
- **Change 2 (workflow wiring + named phase)** is load-bearing: uiux's `contribute` *must* branch on
  the phase name (ui vs ux vs screenshot init) — impossible under today's stance-only `situation.phase`.
- **Change 3 (deterministic delivery)** is what makes `library-state` a real gating fact rather than
  prose the spawn is trusted to compute.
- **Change 4 (declared lease)** is what keeps a divergent design unit from silently editing source —
  and the enforcement already exists.

## Open questions surfaced by the walkthroughs

1. **Conditional/looping workflow edges** (steps A2/B2/B4 route on the library-state fact). `design.md`
   says conditional-edge traversal is implemented (`fail`/`agent-choice`); confirm a phase can route on
   an arbitrary emitted fact, not just pass/fail. *Resolved for the failure mode:* a phase that emits a
   `next` no agent-choice edge here targets no longer falls through silently — the walk journals
   `phase.route_unmatched` (classified `unknown` = typo/removed phase, or `unwired` = registered but no
   edge here), and the opt-in core flag `stall-on-unmatched-route: "true"` turns the fall-through into a
   `phase.stalled` halt instead.
2. **Deterministic phase → workflow routing.** How does a script phase's emitted fact (eligibility)
   drive the next edge? Needs a defined contract for what a deterministic phase returns.
3. **Screenshot capture** is spawn/tool work inside a phase, not a phase primitive — confirm a phase
   can instruct the spawn to drive the app and hand back artifacts the plugin then files.
4. **Who owns the bootstrap trigger?** A explicit operator invocation (as in B) vs. auto-surfacing when
   `library-state` finds `has-ui` + no libraries during unrelated work.

## Recommendation

Build the four changes in praxis core (they unblock every process-bearing plugin — uiux now, writing
and monorepo later), then build the uiux full plugin on top. Suggested order: **Change 4** (smallest,
enforcement done) → **Change 1** (provider) → **Change 2** (wiring, the keystone) → **Change 3**
(deterministic). Spec each against the open questions above as it's built.
