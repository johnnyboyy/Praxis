# Judgment Injector — Design

## Purpose

The **judgment injector** (henceforth "the injector") is a praxis contributor that injects reusable engineering and design judgment into a task's working context before the model starts work. It reads a pool of hand-authored **domain files** (schema: `domain-file.md`), each holding the hardened conventions and weighable principles for one subject or decision-class (`color`, `testing`, …). Once per phase, praxis calls `contribute(situation)`; the injector mechanically selects the domains relevant to the current task from the frontmatter facets and returns a small set of `Contribution` sections.

**The injector is a pure composer — it ships NO domains of its own.** It is itself a registered praxis contributor (the thing praxis calls for `contribute()`), always-on, but it exposes no `domains_dir`. Every domain it injects comes from somewhere else: a plugin that carries domains alongside its code, or the project-local pool. The injector holds no privileged tier, no shipped base, no seed content. It reads the union of what is installed and authored locally, and composes.

The immediate consequence, stated plainly: **a project with no domain-carrying plugins installed and an empty local pool → the injector injects nothing, and that is intended.** No judgment is smuggled in. Judgment appears in context only because someone installed a plugin that carries it or authored a domain into the local pool. Empty by default is the correct default.

That pool is therefore **not one directory**. Judgment is distributed across exactly two kinds of source: registered contributors that carry domains, and the always-on project-local pool at `root/.praxis/domains`. The injector's first job each phase is to **discover and merge** these sources into one composed pool; only then does it select. Ownership (where a domain lives) and composition (what the injector picks) are separate axes — many owners, one composer. See [Discovery & precedence](#discovery--precedence-assembling-the-pool).

The governing idea is a **division of labor between the mechanism and the model**. The injector does only a *coarse* cut — right subject, right project shape — and then modulates framing and weight. It never tries to decide, per principle, whether a specific piece of judgment applies to the case in front of it. That fine call is delegated to the model, which reads each principle's `reason` and judges applicability itself. The mechanism's job is to get the right *pool of judgment* into context under the right *framing*, not to pre-chew it.

`hooks()` (the `verify`/`close` callbacks) are out of scope for this document; the injector is a pure `contribute`-time component.

---

## The two-layer model

Every domain file carries two bodies that inject under **deliberately different confidence rules**. This asymmetry is the core of the design. (Note: "two-layer" here refers to conventions vs principles inside a file — distinct from the two *precedence layers*, plugin vs project, in [Discovery](#discovery--precedence-assembling-the-pool).)

**Conventions — the preamble.** Hardened, terse, imperative rules with no stated rationale ("Guard and return early"). Because there is no *why* for the model to weigh, a misfired convention reads as dogma the model cannot evaluate and cannot safely discount. So conventions demand a **tight, confident filter**: inject them only when subject and stance clearly call for them, compact, and **first**. They are the preamble the rest of the work reads against.

**Principles — the body.** Rule + `condition` + `reason`. The `reason` is load-bearing: it lets the *model* judge fine applicability for itself. So principles demand a **loose, generous filter**: inject them broadly and let the model read the reason and decide whether the principle bears on the case. Higher volume is fine here because each principle self-justifies.

The critical consequence: **the injector does NOT mechanically match a principle's prose `condition`.** The `condition` is injected as text for the model to read, never evaluated as a selector. Mechanically, all the injector does at the principle level is a coarse admissibility cut and a task-kind lens on framing. Relevance is the model's call.

| | Conventions | Principles |
|---|---|---|
| Content | imperative rule, no rationale | rule + condition + reason |
| Filter | tight, confident | loose, generous |
| Injected | first, compact | after, higher volume |
| Gated by | subject + stance (posture) | coarse admissibility only |
| Fine relevance decided by | the injector | the model, via `reason` |

---

## Field-role table

Each `situation` field does exactly **one** job. Keeping the jobs disjoint is what keeps the selection logic small and the failure modes legible.

| situation field | Role | What it does |
|---|---|---|
| `subject` (coding \| design \| prose \| process) | **HARD FILTER** | Excludes any domain whose `subject` differs. Keeps matching-subject domains OR `universal: true` domains. No partial credit. |
| `project_shape` (dict) | **SHAPE PRUNE** | Drops domains whose `applies-when` conditions fail against the shape (language / framework / styling / has_ui). |
| `task_kind` (create \| change \| explore) | **THE LENS** | Frames *which* judgment leads. `create` → new-behavior principles; `change` → preservation / "don't break the anchor"; `explore` → read-only, suppress prescriptive conventions. |
| `phase`/stance (divergent \| convergent \| none) | **POSTURE + TONE** | `convergent` pulls conventions hard; `divergent` suppresses convergent-posture conventions and prepends an anti-mean anchor; `none` is neutral. |
| `workflow` (str \| None) | **PROCESS ADD** | Adds the process-family domain via the `workflows` affinity (tdd → testing, build-verify → verification). |
| `label` (str \| None) | **OVERRIDE / PIN** | Pins a named domain or tag via the `labels` affinity — an explicit author-of-the-task escape hatch. |

Note the deliberate separation: `subject` and `project_shape` **exclude**; `task_kind`, `stance`, `workflow`, `label` **modulate** (weight and framing) and only rarely hard-exclude.

---

## Discovery & precedence (assembling the pool)

Before selection can run, the injector must build the pool from every source that carries judgment. This happens once per `contribute` call (the set of installed sources is cheap to enumerate and can change between runs).

There are exactly **two kinds of source** the injector can see, and it ships neither of them itself:

- **registered praxis contributors** that carry domains — a plugin that exposes a `domains_dir` attribute alongside its code;
- the **project-local pool** — the always-on convention at `root/.praxis/domains`, where the consuming repo keeps its own house rules.

There is no third, built-in tier. The injector is a pure composer over the union of these two kinds.

### What is visible, and what is not

A source is visible to the injector **only if** it is a registered contributor carrying `domains_dir`, or it lives in the project-local pool. Everything else is invisible. In particular, a generic non-praxis Claude plugin — one that is not registered as a praxis contributor and carries no `domains_dir` — contributes nothing until its judgment is **authored or copied into the project-local pool**. Being installed in the environment is not enough; being a *registered, domain-carrying contributor* or being *in the local pool* is the only way in.

This is what makes "empty by default" concrete: with no domain-carrying plugins registered and an empty `root/.praxis/domains`, `discover_domain_dirs` returns only the (empty) project pool entry, the merged pool is empty, and `contribute` returns no `Contribution`s. Nothing is smuggled in.

### Discovery — two source kinds, no base

The injector is itself a registered contributor, so it holds the `root`, and praxis already exposes `contributors_for(root)` — the same call praxis uses to load the plugins. The injector reuses it to find the domain-carrying contributors registered *to this root*, and always adds the project-local pool:

```python
def discover_domain_dirs(root) -> list[tuple[str, Path]]:
    dirs = []
    for c in contributors_for(root):                 # THIS root's own registered contributors
        d = getattr(c, "domains_dir", None)          # optional attribute; the injector itself has none
        if d:
            dirs.append((c.source, Path(d)))         # owner = the contributor's source
    project = root / ".praxis" / "domains"           # always-on project-local pool
    dirs.append(("project", project))                # present even when the dir is empty/absent
    return dirs
```

Two things to notice. First, **there is no base seed line** — the injector adds no directory of its own. Second, a plugin becomes **judgment-bearing** simply by (a) shipping a `domains/` directory and (b) exposing its path as a `domains_dir` attribute. No manifest, no new registration surface — it registers as a contributor for its process framing *and* carries domains the injector picks up. The `owner` of every file it finds is stamped from the source that provided the directory (falling back to the file's own `owner` frontmatter only when present, which must agree; the derived value is authoritative).

### Isolation is definitional — no guard, no topology code

Discovery reads `contributors_for(root)` and `root/.praxis/domains`, and nothing else. Both are **per-root configuration**: a root's `## contributors` list names only *its own* plugins, and the project-local pool it reads is *its own* `root/.praxis/domains`. Because contributors are per-root config entries, the injector pinned to a root can only ever read that root's own registrations plus its own local pool.

From that single fact the isolation guarantees fall out **for free, with zero topology code**:

- **Peers don't mix** — pinned to child A, the injector reads A's registered contributors and A's `.praxis/domains`. Child B's judgment lives in B's config and B's pool, which A's discovery never reads.
- **The parent is blind to its children** — the parent composes only from its own registrations and its own local pool; a child's domains sit under a different root the parent never enumerates.
- **A child does not inherit its parent** — nesting is not inheritance. Filesystem or root nesting never implies a domain chain; a child sees only what *it* registers and what sits in *its* pool.

These guarantees are **emergent, not enforced.** There is no `within_boundary` check, no `crosses_nested_root` walk, no `resolve_root` topology, no "pin vs discover" apparatus, and no hard-coded composition boundary. Cross-root leakage is not something to prevent — it is something the two-source model simply cannot express, because there is no path a sibling's, parent's, or child's judgment could travel to reach a discovery that reads only one root's own config. The only way judgment is shared across roots is the ordinary one: each root that wants a shared domain **registers the contributing plugin itself**, or keeps the domain in its own local pool.

(Cross-root *orchestration* — decomposing a task that spans several roots and handing each unit into its child root pinned to that child — is a separate concern owned by the monorepo plugin, not by the injector. The injector only ever composes within the single root it is pinned to.)

### Precedence — two layers, plugins < project-local

The discovered directories form exactly **two precedence layers** (from `domain-file.md`): **plugin < project**. The injector globs each directory, parses the files, stamps `owner`, and merges under these rules — which match the schema doc's precedence section exactly:

1. **Fully-qualified identity is `owner/id`.** Two files sharing the same `owner/id` are an authoring error within one owner → hard error (skip + report), never a silent last-writer-wins.
2. **Cross-layer (project vs plugin), same bare `id` → project overrides the plugin, WHOLESALE.** A project domain with the same bare `id` as a plugin domain *replaces* it entirely; the plugin's version is dropped and does not inject (`project/color` supersedes `uiux/color`). This is the **only** override in the model, and it is never a field-level merge — a domain whose conventions and principles came from different owners is judgment no one authored. A project that wants to keep most of a plugin's domain and change one part copies the domain into `root/.praxis/domains` and edits it; the copy is honest provenance and is stamped `owner: project`, so it takes precedence automatically.
3. **Peer plugins (same layer), same bare `id` → COEXIST.** Two contributors that each ship a `color` domain **both inject**, as distinct `owner/id` entities (`uiux/color` and `theme/color`). Nothing installed is silently discarded — no first-wins, no last-wins, no shadowing among peers. Registration order in the root's `## contributors` list only breaks *weighting* ties later (which of two equally-ranked peers sorts first); it **never** lets one plugin override another.
4. **Different bare `id` → coexist.** Domains with different bare `id`s all inject; ordering among them is decided later by weighting, not by layer.

The output of this stage is a flat list of *surviving* domains, each tagged with its `owner`, handed to the selection pipeline below. Layer precedence is spent entirely here; selection never reconsiders it.

### Cross-cutting judgment ships as a plugin

Because there is no base, cross-cutting or "general" judgment — the sort that used to feel built-in (e.g. `coding-general`, or a `universal` domain like "name things for the reader") — is now just an ordinary installable plugin (for example a `general` plugin that exposes a `domains_dir`). It is discovered like any other contributor, stamped with its own `owner` (e.g. `general`), and enjoys **no privileged tier**. Universality (`universal: true`) remains a per-domain property fully decoupled from distribution: any plugin, or the project-local pool, may ship a universal domain, and it waives only the subject filter — never the precedence rules.

### What this means for the write side

Distributed ownership shapes the *write* side too (out of scope for `contribute`, noted for the surface/retrospective components): new judgment a task surfaces writes to the **project** layer, never into a plugin you installed — you don't mutate a consumed source. Promotion of project judgment up into a plugin is a separate, deliberate move. The injector only *reads* the layers; it never writes across them.

---

## Selection pipeline (coarse → fine)

```
pool  ← merged union from Discovery (registered plugins + project-local, deduped); losers already dropped
 │  1. subject filter      keep subject==situation.subject OR universal   ── CONFIDENT CUT
 │  2. shape prune         drop where applies-when fails project_shape    ── CONFIDENT CUT
 │  3. task_kind lens      choose which principles lead / how framed      ── modulate
 │  4. stance posture      convergent pulls conventions; divergent        ── modulate
 │                         suppresses them + emits anti-mean anchor
 │  5. workflow add        pull in the process-family domain              ── modulate
 │  6. label override      pin / boost a named domain or tag              ── modulate
 ▼
two body layers assembled → Contributions emitted with priorities
```

Steps **1–2 are the confident cut** — they decide *membership*. A domain that survives them is definitely going to inject something. Steps **3–6 modulate** weight and framing and rarely remove a domain outright (the exceptions: `explore` suppresses conventions; `divergent` suppresses convergent-posture conventions). This ordering means the expensive, opinionated decisions happen on the smallest possible set.

---

## Matching as data, not branching code

The modulation steps (3–6) are expressed as a small declarative **facet → weight** table that the selection reads, rather than as a thicket of `if` branches. New task kinds, stances, or workflows grow the table; they do not rewrite logic.

Each row keys on a facet value and declares how it bends selection: a multiplier on a domain's rank weight, whether it enables or suppresses the conventions layer, and an optional tone tag / anchor to prepend.

```yaml
# facet-weights.yaml — read by the injector; not code

task_kind:
  create:
    principle_lens: new-behavior      # prefer principles about producing new code/design
    convention_weight: 1.0
  change:
    principle_lens: preservation      # prefer "don't break the anchor" principles
    convention_weight: 1.0
  explore:
    principle_lens: read-only
    convention_weight: 0.0            # suppress prescriptive conventions entirely

stance:                               # situation.phase
  convergent:
    convention_multiplier: 1.5        # pull conventions hard
    anchor: null
  divergent:
    convention_multiplier: 0.0        # suppress convergent-posture conventions
    suppress_posture: convergent
    anchor: anti-mean                 # emit the anti-mean anchor Contribution
  none:
    convention_multiplier: 1.0
    anchor: null

workflow:                             # matched against domain frontmatter `workflows`
  tdd:            { adds_affinity: tdd,          weight: 2.0 }
  build-verify:   { adds_affinity: build-verify, weight: 2.0 }

label:                                # matched against domain frontmatter `labels`
  "*":            { pin_weight: 3.0 }  # any label pin strongly boosts its matches
```

The affinity fields on domains (`task-kinds`, `workflows`, `labels`) supply the *other half* of each match: the table says "a `tdd` workflow adds weight 2.0 to domains tagged `tdd`," and the domain's `workflows: [tdd]` is what earns it. Empty affinity on a domain means "no opinion" — neutral, neither boosted nor penalized.

---

## `contribute()` pseudocode

```python
class JudgmentInjector:
    source = "judgment-injector"
    # NOTE: no domains_dir attribute — the injector ships no domains of its own.

    def __init__(self, root, weights):
        self.root = root          # this praxis root; used to discover domain-carrying contributors
        self.weights = weights    # facet-weights.yaml

    def contribute(self, s) -> list[Contribution]:
        W = self.weights

        # ── 0. DISCOVER + MERGE: build the pool from the two source kinds ─
        #   registered contributors' domains_dir (owner = source)
        #   + the project-local pool (owner = project). No base.
        pool = merge_pool(discover_domain_dirs(self.root))
        #   merge_pool namespaces to owner/id, applies wholesale cross-layer
        #   override (project > plugin) on same bare id, lets peers coexist,
        #   and drops the losers. See "Discovery & precedence".
        #   If nothing is installed and the local pool is empty, pool == [].

        # ── 1–2. CONFIDENT CUT: subject filter + shape prune ─────────────
        admissible = [
            d for d in pool
            if (d.universal or d.subject == s.subject)
            and shape_ok(d.applies_when, s.project_shape)
        ]

        # ── 3–6. MODULATE: compute a rank weight per domain ──────────────
        tk   = W.task_kind[s.task_kind]
        st   = W.stance[s.phase]
        for d in admissible:
            d.weight = 1.0
            if s.task_kind in d.task_kinds:  d.weight *= 1.5      # affinity
            if s.workflow and s.workflow in d.workflows:
                d.weight *= W.workflow[s.workflow].weight        # process add
            if s.label and s.label in d.labels:
                d.weight *= W.label["*"].pin_weight              # label pin
        # registration order in `## contributors` breaks ties only:
        admissible.sort(key=lambda d: (-d.weight, d.registration_index))

        out = []

        # ── anti-mean anchor: only when diverging (priority -10) ─────────
        if st.anchor == "anti-mean":
            out.append(Contribution(
                self.source, "Resist the mean",
                ANTI_MEAN_ANCHOR_TEXT, priority=-10))

        # ── conventions preamble: tight filter (priority 0) ──────────────
        if tk.convention_weight > 0 and st.convention_multiplier > 0:
            lines = []
            for d in admissible:
                if getattr(st, "suppress_posture", None) == d.posture:
                    continue                                     # e.g. divergent drops convergent conventions
                lines += [c.rule for c in d.conventions]
            if lines:
                out.append(Contribution(
                    self.source, "Conventions",
                    terse_list(lines), priority=0))

        # ── domain principles: generous, grouped, lensed (priority 10) ───
        for d in admissible:
            body = render_principles(d.principles, lens=tk.principle_lens)
            #   render injects rule + condition + reason verbatim.
            #   `lens` only orders/frames; it never drops on prose condition.
            out.append(Contribution(
                self.source, f"{d.owner}/{d.id} — principles",
                body, priority=10))

        # ── workflow process principles: only if workflow matched (20) ───
        if s.workflow:
            for d in admissible:
                if s.workflow in d.workflows:
                    out.append(Contribution(
                        self.source, f"{d.owner}/{d.id} — {s.workflow} process",
                        render_principles(d.principles, lens="process"),
                        priority=20))

        return out
```

`shape_ok` implements the `applies-when` mini-syntax (equals / `not-none` / one-of list), AND across all conditions. `render_principles` emits each principle's `rule`, `condition`, and `reason` as prose — it **never** evaluates `condition` as a selector; the lens only affects ordering and a one-line framing header. Contribution titles carry `owner/id` so a reader can always ask "whose judgment is this?", and so two coexisting peers (`uiux/color`, `theme/color`) inject as clearly distinct sections.

---

## Output priority spec

`contribute()` returns `Contribution`s; praxis sorts them by `priority` ascending (lower = earlier in context). Four tiers, in inject order:

| priority | Contribution | When emitted |
|---|---|---|
| **-10** | Anti-mean anchor | Only when `phase == divergent`. A short prepended stance: "the default answer is a starting point to push against, not a target." |
| **0** | Conventions preamble | Subject + stance filtered, terse, compact. Suppressed entirely when `task_kind == explore` or when stance suppresses the domain's posture. |
| **10** | Domain principles | rule + condition + reason, grouped by `owner/id`, ordered by the task-kind lens. The generous, high-volume layer. |
| **20** | Workflow process principles | Only when `workflow` matches a domain's `workflows` affinity (tdd → testing, build-verify → verification). |

The ordering is intentional: the anchor sets stance, the conventions set hard rules, the principles fill in weighable judgment, and the process guidance lands last, closest to the work.

---

## Worked examples

### 1. `coding / change / convergent / workflow=build-verify`

Refactoring existing code under a build-verify loop, converging on the standard. Assume a `general` plugin (carrying cross-cutting coding judgment) and a `verification` plugin are registered contributors.

- **Subject filter:** keep `coding` + `universal` domains; drop all `design`/`prose` domains.
- **Shape prune:** e.g. a `python` project drops `applies-when: [framework: react]` domains.
- **task_kind lens** (`change`): principles framed for **preservation** — "don't break the anchor," keep existing behavior intact.
- **stance** (`convergent`): `convention_multiplier 1.5` — conventions pull hard. No anchor.
- **workflow** (`build-verify`): boosts and adds the `verification/verification` domain (tagged `workflows: [build-verify]`); its process principles inject at priority 20.

Injected:
- *(no -10 anchor — not divergent)*
- **priority 0** — Conventions: `general/coding-general` rules (names, early-return, no-dead-code, one-purpose), terse.
- **priority 10** — `general/coding-general` principles (duplication-vs-abstraction, boundary-validation, …) framed toward preservation.
- **priority 20** — `verification/verification` process principles ("re-run the build after each change; a green anchor is the precondition for the next edit").

### 2. `design / create / divergent / label=color`

Creating a new visual design, pushing away from the default, with an explicit `color` label. Assume a `uiux` plugin ships a `color` domain.

- **Subject filter:** keep `design` + `universal`; drop all `coding` domains.
- **Shape prune:** `has_ui: yes` domains pass; a headless project would have dropped them.
- **task_kind lens** (`create`): principles framed for **new-behavior** — generative design judgment.
- **stance** (`divergent`): emits the **anti-mean anchor** at priority -10; `convention_multiplier 0` with `suppress_posture: convergent`, so convergent-posture conventions do **not** inject (their safe-default rules would pull toward the mean we're trying to leave).
- **label** (`color`): `pin_weight 3.0` boosts the `uiux/color` domain (tagged `labels: [color]`) to the top of the principle ordering.

Injected:
- **priority -10** — Anti-mean anchor: "differentiate; the obvious palette is the one to interrogate."
- *(priority 0 conventions largely suppressed — divergent drops convergent conventions; only a divergent- or neutral-posture domain's conventions could survive)*
- **priority 10** — `uiux/color` principles first (contrast, meaning, restraint — each with its reason), then other admissible `design` principles, framed for new-behavior.
- *(no priority 20 — no workflow)*

*(If a peer `theme` plugin also shipped a `color` domain, both `uiux/color` and `theme/color` would coexist and inject as distinct sections; the `## contributors` order would only decide which sorts first among equally-weighted ties. Had the **project** authored its own `color` domain, it would override the plugin's `color` wholesale.)*

### 3. `coding / explore / none`

Reading code to understand it; no stance, no changes. Assume the `general` plugin is registered.

- **Subject filter:** keep `coding` + `universal`.
- **Shape prune:** normal.
- **task_kind lens** (`explore`): `convention_weight 0` — **conventions suppressed entirely**. Explore is read-only; prescriptive "just do this" rules are noise when nothing is being written. Principles framed **read-only** (comprehension, not prescription).
- **stance** (`none`): neutral, `convention_multiplier 1.0`, no anchor — but conventions are already off from the lens.
- **workflow / label:** none.

Injected:
- *(no -10 anchor)*
- *(no priority 0 conventions — suppressed by explore)*
- **priority 10** — `general/coding-general` principles only, framed for comprehension (e.g. boundary-validation and comments-explain-why read as "here is what to look for," not "here is what to do").
- *(no priority 20)*

*(Counterfactual — the empty-by-default case: if no domain-carrying plugin were registered and `root/.praxis/domains` were empty, this same task would inject **nothing**. The injector ships no `coding-general` of its own to fall back on.)*

---

## Summary

The injector is a coarse mechanical filter plus a data-driven modulator, sitting in front of a model that makes the fine calls — and it is a **pure composer that ships no domains of its own**. It first **discovers and merges** a distributed pool from exactly two source kinds — registered contributors that carry a `domains_dir`, and the always-on project-local pool at `root/.praxis/domains` — so judgment can live with its owner while composition stays central: many owners, one composer, no base. With nothing installed and an empty local pool it injects nothing, by design.

Precedence is two layers, **plugin < project**: same `owner/id` twice is an error; project overrides a plugin's same-`id` domain wholesale; peer plugins with the same bare `id` coexist as distinct `owner/id` entities, with registration order breaking only weighting ties. Isolation between roots (peers don't mix, parent blind to children, child does not inherit parent) is **definitional** — it falls out of discovery reading only the pinned root's own per-root config, with zero topology code and no boundary guard.

Then `subject` and `project_shape` decide membership with confidence; `task_kind`, `stance`, `workflow`, and `label` bend framing and weight through a declarative facet→weight table. Conventions inject tight and first; principles inject loose and generous, self-justified by their reasons. Everything the injector chooses NOT to decide — per-principle applicability — it hands to the model by injecting the `reason` and stepping back.
