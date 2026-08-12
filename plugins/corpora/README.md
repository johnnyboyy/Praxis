# Corpora

**Corpora** is a **pure-composer** praxis contributor. Once per phase, praxis
calls `contribute(situation)` and Corpora injects reusable engineering and design
**judgment** — hand-authored *domain files* — into the task's working context
*before* the model starts work. It does a coarse mechanical cut (right subject,
right project shape), modulates framing and weight, and steps back; the fine call
of whether a given principle applies is left to the model, which reads each
principle's `reason`.

**It ships NO domains of its own.** Corpora is a composer, not a source: it
holds no `domains_dir`, no built-in base, no seed content. It reads the union of
whatever is installed and authored locally, and composes. The direct consequence
is **empty by default**: a project with no domain-carrying plugins registered and
an empty local pool → the injector injects nothing. That is intended — no judgment
is smuggled in; it appears only because someone put it there.

## Registering it

In the consuming praxis root's `.praxis/config.json`, add Corpora under the
`contributors` namespace, pointing at the `make(root)` factory:

```json
{
  "contributors": {
    "corpora": "corpora.injector:make"
  }
}
```

Ensure the `corpora` package is importable on `sys.path`. The contributor's
`source` is `"corpora"` (it stamps every `Contribution` it emits).

## The two source kinds it composes over

Judgment is *distributed*, not centralized. Each phase Corpora discovers a
pool from exactly two kinds of source (no third, built-in tier):

1. **Registered praxis contributors that carry domains** — any contributor
   registered to *this* root that exposes a `domains_dir` attribute alongside its
   code. Its domains are stamped `owner = <contributor source>`.
2. **The always-on project-local pool** at `root/.praxis/domains` (owner =
   `project`) — the consuming repo's own house rules, present even when empty.

**Precedence is two layers, plugin < project.** A project domain with the same
bare `id` as a plugin domain **overrides it wholesale** (never a field-level
merge). Peer plugins that ship the same bare `id` coexist as distinct `owner/id`
entities. Same `owner/id` twice is an authoring error (skipped + reported).
Cross-root isolation is definitional: discovery reads only this root's own
registrations and its own local pool.

## The two-layer body of a domain file

Every domain file carries two bodies that inject under deliberately different
confidence rules:

- **conventions** — hardened, terse, imperative rules with no rationale. A
  misfired convention reads as dogma the model can't weigh, so they inject under a
  **tight, confident** filter: only when subject and stance clearly call for them,
  compact, and **first** (the preamble).
- **principles** — rule + `condition` + `reason`. The `reason` is load-bearing:
  it lets the model judge fine applicability itself. So principles inject
  **loose and generously**, at higher volume, self-justified. The `condition` is
  injected as prose for the model to read — it is **never** matched as a selector.

## Config — Corpora's own namespace

Corpora reads its settings from its **own** namespaced section of the praxis
config store (`config.read(root, "corpora")`) — never the unnamed praxis-core
scope. That section is injectable with anything Corpora wants; today it reads one
key:

- **`project_shape`** — a dict (`language` / `framework` / `styling` / `has_ui`)
  used to prune any domain whose `applies-when` conditions fail against the
  project's shape. Absent/empty shape lets everything pass the prune, so a root
  that ships no shape-gated domains never needs to set it.

```json
{
  "corpora": {
    "project_shape": { "language": "python", "has_ui": "no" }
  }
}
```

## Layout

- `injector.py` — the `Corpora` contributor, selection pipeline, and the
  `make(root)` factory.
- `discovery.py` — `discover_domain_dirs(root)` (the two source kinds) and
  `merge_pool(dirs)` (precedence merge).
- `parser.py` — `parse_domain_file(path, owner)`: frontmatter + `conventions`/
  `principles` body → `Domain`.
- `models.py` — `Domain`, `Convention`, `Principle` dataclasses.
- `weights.py` / `facet_weights.yaml` — the declarative facet→weight table
  (task-kind lens, stance posture, workflow/label affinity).
- `__init__.py` — package exports (compose layer lazy-loaded).

## Full spec

See **`injector-design.md`** for the selection pipeline, discovery/precedence,
and output priority tiers, and **`domain-file.md`** for the domain-file schema.
