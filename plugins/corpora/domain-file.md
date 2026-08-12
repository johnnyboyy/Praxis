# Domain File — Schema / Contract

## Purpose

A **domain file** is a single markdown file that holds reusable engineering or design judgment scoped to exactly one subject or decision-class (e.g. `coding-general`, `color`, `testing`). It is authored by hand. A praxis plugin — the **Judgment Injector** (henceforth "the injector") — discovers the available domains, mechanically selects the ones relevant to the current task using the frontmatter facets, and injects their bodies into the model's context before work begins. This document defines the file's shape from first principles so that shape serves the injector: the frontmatter carries exactly the facets the injector matches or weights on, and the body separates two kinds of content — `conventions` and `principles` — that inject under different confidence rules.

**Judgment is distributed, not centralized — and there is no built-in base.** A domain file does not live in one central pool. It lives wherever its *owner* lives, and there are exactly **two** kinds of source the injector can see:

- **registered praxis contributors** — plugins that carry domains alongside their code by exposing a `domains_dir`;
- the **project-local pool** — an always-on convention at `root/.praxis/domains`, where the consuming repo keeps its own house rules.

There is no third, built-in tier. Cross-cutting judgment that used to feel "base" (like `coding-general`) now ships as an ordinary installable plugin (e.g. a `general` plugin) or is authored into the project-local pool — it is not baked into the injector. A source that is neither a registered contributor nor in the project-local pool is **invisible** to the injector: a generic, non-praxis plugin must be authored or copied into the project-local pool before its judgment can be seen.

The injector composes over the **union** of these two source kinds. Ownership (where a file lives, who versions it) and composition (who reads the union and decides what injects) are separate axes — this file's job is to carry enough identity and provenance that a domain from one source can be merged, namespaced, and overridden against another without collision. See [Distributed ownership & precedence](#distributed-ownership--precedence).

---

## File anatomy

A domain file is a YAML frontmatter block followed by a markdown body. The body is itself structured as two YAML sequences under `conventions:` and `principles:` headings (see [Body](#body)).

```
---
<frontmatter fields>
---

conventions:
  - id: ...
    rule: ...

principles:
  - id: ...
    rule: ...
    condition: ...
    reason: ...
```

---

## Frontmatter spec

The frontmatter is the injector's entire mechanical surface. It answers two questions: **is this domain admissible for the task?** (hard filters) and **how strongly does it apply?** (affinity weighting). Nothing in the body is read during selection.

| Field | Type | Required | Role | Default when absent |
|---|---|---|---|---|
| `id` | string | yes | Stable name of the domain within its owner (e.g. `color`). Namespaced to `owner/id` when merged. Identity only; not matched. | — (must be present) |
| `owner` | string | no | The source that owns this file. **Derived at discovery, never defaulted** — see below. Sets the namespace and the precedence layer. | — (stamped from the source, not from a default) |
| `subject` | enum | yes | Hard filter. | — (must be present) |
| `posture` | enum | yes | Selects which body sections inject and how confidently. | — (must be present) |
| `applies-when` | list of conditions | no | Hard filter on project shape. | empty = always applicable |
| `universal` | boolean | no | Bypasses the `subject` filter. | `false` |
| `task-kinds` | list | no | Affinity weight. | empty = all kinds |
| `workflows` | list | no | Affinity weight. | empty = untied |
| `labels` | list | no | Affinity weight. | empty = no label pins |

### `id` and `owner` — identity across sources

`id` names the domain **within its owner** — it need only be unique among that owner's files, so two different plugins may each ship a `color` domain without coordinating.

`owner` names the source, and it is **always derived from where the file was discovered — there is no default and no `base`.** A domain file authored inside a plugin need not declare `owner` at all; the injector stamps it at discovery:

- a domain found in a **registered contributor's** `domains_dir` is stamped with that contributor's `source` (its plugin name, e.g. `uiux`);
- a domain found in the **project-local pool** (`root/.praxis/domains`) is stamped `project`.

Because `owner` is derived, authoring a domain never involves choosing a tier by hand; distribution — where you put the file — *is* the choice. If a file does declare `owner`, it is only meaningful when it agrees with the derived source; the derived value is authoritative.

When the injector merges the discovered domains, a domain's **fully-qualified identity** is `owner/id` (e.g. `uiux/color`, `project/color`). Namespacing is what makes distributed ownership safe: two `color` domains from different owners are distinct entities, and the injector can hold both, dedup deliberately, or let one override the other by an explicit precedence rule rather than by accident. `owner` also fixes the precedence *layer* (project > plugin) — see [Distributed ownership & precedence](#distributed-ownership--precedence). Neither field is ever matched against the task; both are identity only.

### `subject` — the hard filter

One of: `coding` | `design` | `process` | `prose`.

This is the coarsest cut. The injector knows the subject of the task and **excludes any domain whose `subject` differs outright** — a `design` domain never injects into a `coding` task, and vice versa. There is no partial credit and no weighting here; wrong subject means the file is not read further.

The single exception is `universal: true` (below), which lets a domain opt out of this filter.

### `posture` — convergent | divergent | neutral

Declares the *stance* the domain takes toward established norms. The injector uses posture to decide **whether the `conventions` section injects at all**, and how it frames the injected judgment.

- `convergent` — "match the standard; regression to the mean is fine." The domain's value is in encoding the well-trodden path. Its `conventions` are safe defaults and should inject readily.
- `divergent` — "differentiate; carry an anti-mean anchor." The domain exists to push away from the default answer. `conventions` here are held more warily (a divergent domain often leans on `principles`, which carry the *why* that justifies departing from the norm).
- `neutral` — neither pull. The domain is factual/structural judgment with no stance toward the mean.

Posture is about the domain's relationship to convention, not about the task. It is set once by the author.

### `applies-when` — project-shape gate

A list of **conditions** on the project's shape. If present, *every* condition must hold for the domain to be admissible (logical AND). An empty or absent `applies-when` means the domain always passes this gate.

Recognized shape keys (the injector knows the project's value for each):

- `language` — e.g. `python`, `typescript`
- `framework` — e.g. `react`, `django`
- `styling` — e.g. `tailwind`, `css-modules`, `none`
- `has_ui` — `yes` | `no`

**Condition mini-syntax.** Each list entry is a single `key: matcher` mapping. Three matcher forms:

| Form | Written as | Holds when |
|---|---|---|
| equals | `framework: react` | project's `framework` is exactly `react` |
| not-none | `styling: not-none` | project's `styling` is set to anything other than `none`/unset |
| one-of | `language: [python, typescript]` | project's `language` is any value in the list |

Examples:

```yaml
applies-when:
  - has_ui: yes            # equals
  - styling: not-none      # not-none
  - framework: [react, vue, svelte]   # one-of
```

All three must hold. A project with `has_ui: no` fails the first condition and the domain is excluded.

### `universal` — cross-cutting bypass

Boolean. When `true`, the domain injects **regardless of `subject`** — it is judgment that cuts across all decision-classes (e.g. "name things for the reader," "leave the campsite cleaner than you found it"). `universal` still respects `applies-when`; it only waives the subject filter. Default `false`.

`universal` is a **per-domain property, fully decoupled from distribution.** A cross-cutting domain can be shipped by any plugin or authored into the project-local pool; universality says nothing about *where* a domain lives or *who* owns it, and it no longer implies any special tier. Any owner may ship a `universal` domain, and an owner's other domains may be non-universal at the same time.

### Facet-affinity tags — weight, not filter

These three fields do **not** exclude a domain. They let the injector *rank* admissible domains and decide how much room to give each when context budget is tight. A domain that passes every hard filter but matches no affinity tag still injects; it simply sorts lower.

| Field | Values | Matched against |
|---|---|---|
| `task-kinds` | subset of `create` \| `change` \| `explore` | the task's kind |
| `workflows` | free-form names (e.g. `tdd`, `build-verify`) | the workflow(s) the task runs under |
| `labels` | free-form tags | the task's `label`, if it pins one |

Empty/absent means "no opinion" on that axis, which is neutral for weighting (neither boosts nor penalizes).

---

## Body

The body holds the actual judgment, split into two sequences that inject under **deliberately different confidence rules**. This split is the heart of the contract.

> **Conventions want a tight, confident filter. Principles want a loose, generous one.**
>
> The mechanical frontmatter layer does only a *coarse* cut (right subject, right project shape). Beyond that, the two sections diverge:
>
> - `conventions` are hardened, high-confidence rules with no stated rationale. Because there is no *why* for the model to weigh, the injector must be the one that gates them — it injects them **only when posture/stance clearly calls for them**, compact and first. A misfired convention is dogma the model can't evaluate, so the filter is tight.
> - `principles` each carry a `reason`. That reason lets the *model* judge fine applicability for itself. So the injector is **generous**: it injects principles broadly and lets the model read the `condition` and `reason` and decide whether this principle bears on the case. The `condition` field is therefore **not mechanically matched** — it is prose injected for the model to read, not a selector the injector evaluates.

### `conventions:` — the hardened preamble

Terse, imperative, "just do this." These inject **first** and **compact**, as a high-confidence preamble.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `id` | string | yes | Stable unique id within the file (e.g. `naming`). |
| `rule` | string | yes | One imperative line. No rationale, no hedging. |

### `principles:` — the weighable body

The fuller judgment. Inject generously after the conventions; the model self-selects using the reason.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `id` | string | yes | Stable unique id within the file. |
| `rule` | string | yes | The judgment, stated as guidance (may be less terse than a convention). |
| `condition` | string (prose) | yes | When/where this applies — scope. **Read by the model, not matched by the injector.** |
| `reason` | string (prose) | yes | **The load-bearing field.** Why the rule holds. A rule without its reason is dogma; the reason is what lets the model judge whether the rule transfers to the case in front of it. |

---

## Example domain file — `coding-general`

Cross-cutting coding judgment like `coding-general` is not a built-in anymore: it ships as an ordinary installable plugin (a `general` plugin that exposes a `domains_dir`). The file below is authored inside that plugin. Note that it **declares no `owner`** — the injector derives `owner: general` from the plugin `source` at discovery. The same file, dropped into a repo's `root/.praxis/domains` instead, would be stamped `owner: project` with no change to its contents.

```markdown
---
id: coding-general
# no owner: line — derived from the source at discovery
#   in the `general` plugin's domains_dir  -> owner: general
#   in root/.praxis/domains                -> owner: project
subject: coding
posture: convergent
universal: false
applies-when: []            # always applicable within the coding subject
task-kinds: [create, change]
workflows: []
labels: [refactor, cleanup]
---

conventions:
  - id: names
    rule: Name things for the reader who has never seen this code; no abbreviations that aren't already domain words.
  - id: early-return
    rule: Guard and return early; do not nest the happy path inside conditionals.
  - id: no-dead-code
    rule: Delete unused code rather than commenting it out.
  - id: one-purpose
    rule: A function does one thing; if you need "and" to describe it, split it.

principles:
  - id: duplication-vs-abstraction
    rule: Tolerate a little duplication before you reach for an abstraction.
    condition: When two call sites look similar but you are not yet sure they will change together.
    reason: A wrong abstraction is more expensive to unwind than duplicated code is to maintain, because it couples callers that have no real reason to move in lockstep. Wait until the shared shape has proven itself across at least three uses before extracting it.
  - id: comments-explain-why
    rule: Comment the why, not the what.
    condition: When the code's intent or a non-obvious tradeoff cannot be recovered from reading it.
    reason: The what drifts out of sync with the code and then lies; the reasoning behind a choice is the thing a future reader cannot reconstruct from the source and most needs. A comment that restates the line adds noise; one that records a rejected alternative or an external constraint saves an investigation.
  - id: boundary-validation
    rule: Validate at the boundary, trust within the core.
    condition: When data crosses from outside the system (I/O, user input, network) into internal logic.
    reason: If every internal function re-checks its inputs, the checks multiply and still miss cases. Concentrating validation at the edge lets the interior assume well-formed data, which shrinks the surface where malformed state can exist and makes the invariants legible.
  - id: optimize-later
    rule: Make it correct and clear first; optimize only against a measured hot path.
    condition: When you feel the urge to hand-optimize before profiling.
    reason: Most code is not on the critical path, and optimization trades clarity for speed the program never needed. Measurement, not intuition, tells you where the time goes; optimizing elsewhere spends the clarity budget for nothing.
```

---

## What the injector reads vs. ignores

**Reads (mechanical selection):**

- `subject` — hard filter; excludes wrong-subject domains (unless `universal`).
- `applies-when` — hard filter; every condition must hold against project shape.
- `universal` — waives the subject filter.
- `posture` — decides whether/how `conventions` inject and how they're framed.
- `task-kinds`, `workflows`, `labels` — affinity weighting and ranking only; never exclude.
- Section identity (`conventions:` vs `principles:`) and the required fields of each entry, so it can inject them under the two different confidence rules.

**Ignores (passed through for the model, not matched):**

- `principles[].condition` — injected as prose for the model to read; never mechanically evaluated.
- `principles[].reason` — injected verbatim; it is the model's basis for judging applicability, not a selector.
- `rule` text of either section — injected, not parsed.
- `id` / `owner` fields — identity, namespacing, and precedence only; never matched against the task. (`owner` is derived at discovery, so it is not even authored input.)

---

## Distributed ownership & precedence

Domains come from exactly two source kinds — **registered contributors** (plugins with a `domains_dir`) and the **project-local pool** (`root/.praxis/domains`) — so the injector composes over a pool with just **two layers**, not three, and not a flat one. There is no base. This section fixes how identity, layering, and collisions resolve. The mechanics of *discovering* the sources belong to the injector (`injector-design.md`); what follows is the contract each file must satisfy so that merge is well-defined.

### The two layers (lowest → highest precedence)

| Layer | `owner` (derived) | Meaning |
|---|---|---|
| plugin | the contributor's `source` (`uiux`, `general`, `monorepo`, …) | Judgment a registered contributor brings along with its part. |
| project | `project` | The consuming repo's own house rules, from `root/.praxis/domains`. |

Project **wins** over plugins on conflict. The intent mirrors a cascade (CSS, `PATH`, layered config): a project can override a plugin's judgment; nobody silently mutates a layer they merely consume. Peer plugins do not form a sublayering among themselves — see below.

### Collision resolution

Two domains **collide** only when they share a fully-qualified identity `owner/id`; that is an authoring error within one owner and is rejected. Two domains with the **same bare `id` but different `owner`** (e.g. `uiux/color` and `project/color`) do **not** collide — they are distinct entities. How same-`id` domains combine depends on whether they sit in the same layer or across layers:

- **Cross-layer (project vs plugin), same bare `id` → project overrides the plugin, wholesale.** A project domain with the same bare `id` as a plugin domain **replaces** it entirely; the plugin's version is dropped and does not inject (the project's `color` supersedes `uiux/color`). This is the only override in the model.
- **Peer plugins (same layer), same bare `id` → coexist.** Two contributors that each ship a `color` domain **both inject**, as distinct `owner/id` entities (`uiux/color` and `theme/color`). Nothing installed is silently discarded — there is no first-wins, no last-wins, no shadowing among peers. Registration order in the root's `## contributors` list only breaks *weighting* ties later (which of two equally-ranked peers sorts first); it does **not** let one plugin override another.
- **Different bare `id` → coexist.** Domains with different bare `id`s all inject; ordering among them is by the injector's weighting.

Override (the cross-layer case) is deliberately wholesale, not a field-level merge: a half-overridden domain whose conventions came from one owner and principles from another would be judgment no one actually authored. If a project wants to keep most of a plugin's domain and change one principle, it copies the domain into its own project-local pool and edits it — the copy is honest provenance, and by living in `root/.praxis/domains` it is stamped `owner: project` and takes precedence automatically.

### Roots stay fully isolated — by definition, not by a guard

The two layers are the sources discovered for a **single pinned praxis root**: that root's registered contributors plus that root's own `root/.praxis/domains`. Layering lives within one root; **roots do not chain.** In a monorepo (a parent coordination root over child roots), the roots are **fully isolated and symmetric**:

- peers never mix — one child's pool never sees a sibling's;
- a parent is blind to its children — it composes only its own layers;
- a child does **not** inherit its parent — nesting is not inheritance.

This isolation is **definitional, and needs no enforcement code.** Contributors are per-root configuration: a root's `## contributors` list names only *its own* plugins, and the project-local pool it reads is *its own* `root/.praxis/domains`. Discovery therefore only ever reads the pinned root's own registrations and its own local pool; there is no path a sibling's, parent's, or child's judgment could travel to reach it. Because the isolation follows purely from what discovery reads, there is no `within_boundary` check, no path guard, and no root-resolution topology to enforce — cross-root leakage is not something to prevent, it is something the two-source model cannot express. The only way judgment is shared across roots is the ordinary one: each root that wants a shared domain **registers the contributing plugin itself**, or keeps the domain in its own local pool.

### Provenance travels with the file

`owner` is the minimum provenance every domain carries — derived at discovery, so it is always accurate — and it is enough for merge and override. A file **may** additionally record where a principle came from (author, date, the task that surfaced it) as free-form fields the injector passes through untouched — provenance is for humans and for the write-back/retrospective processes, never a selector. The one rule the injector enforces: a domain injected into context is always attributable to exactly one `owner`, so a reader can always ask "whose judgment is this?"
