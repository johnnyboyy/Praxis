# Judgment Plugin — Contract & Reusable Scaffold

## What a judgment plugin is

A **judgment plugin** is a praxis plugin whose job is to *carry hand-authored
judgment* — a directory of domain files — so that the [`corpora`](./corpora/)
composer can discover, own, and inject it. It is a **source**, never a composer:
it ships judgment and does nothing else with it. Corpora reads the union of every
registered judgment plugin (plus the project-local pool) and does all the
selecting, weighting, and injecting.

Corpora discovers judgment plugins through praxis's `contributors_for(root)`. For
every contributor registered to *this* root, corpora's
[`discover_domain_dirs`](./corpora/corpora/discovery.py) asks a single question:

```python
for c in contributors_for(root):
    domains_dir = getattr(c, "domains_dir", None)
    if domains_dir:
        dirs.append((c.source, Path(domains_dir)))
```

So a judgment plugin is any registered contributor that **exposes a
`domains_dir` attribute**. Corpora then reads `*.md` from that directory and
stamps every domain with `owner = <the contributor's source>`. That is the whole
discovery contract. A contributor without `domains_dir` (like Corpora itself)
carries no judgment; a contributor *with* one carries all the `*.md` files in it.

### The three things a judgment plugin must provide

1. **A `domains/` directory** of domain files that conform to the parser
   (see [Transform rules](#the-oldnew-domain-transform-rules)).
2. **A minimal contributor object** with four members (next section).
3. **Registration** in the consuming root's `.praxis/config.json` under the
   `contributors` namespace (see [Registration](#registration)).

### Bare vs. full judgment plugins

- A **bare** judgment plugin *only* carries domains. Its `contribute` is a no-op
  returning `[]`; corpora does 100% of the composing. This is the common case and
  the template below.
- A **full** plugin (e.g. a future `uiux` that also injects process framing)
  additionally returns real `Contribution`s from `contribute`. That is an
  independent capability layered on top.

The distinction does not affect how judgment is carried. **Domains ride on
`domains_dir` identically in both cases** — corpora discovers the directory
whether or not `contribute` does anything. A plugin can start bare and grow a
real `contribute` later without touching a single domain file.

---

## The contributor contract

Praxis validates every contributor with
[`validate_contributor`](file:///Users/johnzdanis/.claude/skills/praxis/contributors.py),
which requires exactly two things: a non-empty string `source`, and a callable
`contribute`. Corpora adds the `domains_dir` convention on top. So the full
member set a judgment plugin needs is:

| Member | Required by | Contract |
|---|---|---|
| `source: str` | praxis | Non-empty. Becomes the `owner` stamped on every domain this plugin carries (e.g. `"general"`, `"uiux"`). Also the plugin's namespace and precedence identity. |
| `contribute(self, situation) -> list` | praxis | Must be callable. For a **bare** judgment plugin, a **no-op returning `[]`**. |
| `domains_dir` | corpora | Absolute path to the plugin's `domains/` directory, computed from the module file — **not** the consuming root. This is what makes corpora discover the domains. |
| `make(root)` | praxis registration | Module-level factory returning the contributor; registered as `"<module>:make"`. Praxis calls it as `factory(root)`. |

**`domains_dir` must be portable.** Compute it from the module's own location so
the plugin works no matter which root registers it or where it is installed on
disk:

```python
domains_dir = Path(__file__).resolve().parent / "domains"
```

Never derive it from the consuming `root` — the domains live *with the plugin
code*, not in the repo that consumes the plugin.

---

## Reference contributor template (complete, copy-pasteable)

This is the whole module for a bare judgment plugin. Name the file
`<name>_plugin.py` and set `source` to the plugin's name.

```python
"""<name> — a bare judgment plugin.

Carries hand-authored domain files for the corpora composer to discover and
inject. It does no composing itself: `contribute` is a no-op. Corpora finds this
plugin via `contributors_for(root)`, reads `*.md` from `domains_dir`, and stamps
every domain `owner = "<name>"`.
"""

from __future__ import annotations

from pathlib import Path


class <Name>Judgment:
    """A bare judgment source: carries domains, composes nothing."""

    # Non-empty source string. Becomes `owner` on every domain this plugin ships,
    # and this plugin's namespace + precedence identity.
    source = "<name>"

    # Absolute path to this plugin's own domains dir, derived from the module
    # file so it is portable — NOT derived from the consuming root.
    domains_dir = Path(__file__).resolve().parent / "domains"

    def __init__(self, root):
        # `root` is the consuming praxis root praxis hands to the factory. A bare
        # judgment plugin does not need it, but the signature must accept it.
        self.root = root

    def contribute(self, situation) -> list:
        """No-op: this plugin only carries judgment; corpora composes it."""
        return []


def make(root) -> "<Name>Judgment":
    """Factory. Register via `<name>_plugin:make` in the root's config."""
    return <Name>Judgment(root)
```

Replace `<name>` / `<Name>` throughout (e.g. `general` / `General`).

### Directory layout

```
praxis-plugins/<name>/
  <name>_plugin.py      # the contributor + make(root)
  domains/
    <domain>.md         # one or more domain files (parser-conformant)
    <domain>.md
```

The plugin directory must be importable on `sys.path` so that
`import <name>_plugin` resolves. Everything a judgment plugin owns lives under
`praxis-plugins/<name>/` — the code and the judgment travel together.

---

## Registration

In the **consuming** praxis root's `.praxis/config.json`, add the plugin under
the `contributors` namespace, pointing `"<name>"` at the `make` factory as
`"<module>:make"`:

```json
{
  "contributors": {
    "corpora": "corpora.plugin:make",
    "<name>": "<name>_plugin:make"
  }
}
```

Praxis's `contributors_for(root)` reads this namespace, imports each `module`,
calls `getattr(module, "make")(root)`, and validates the result. Corpora must
also be registered (as above) — it is the composer that turns the carried
domains into injected context. Registration is per-root: a root sees only the
plugins *it* lists, which is what keeps roots isolated.

---

## How corpora discovers, owns, and precedes a judgment plugin

- **Discovers**: `discover_domain_dirs(root)` walks `contributors_for(root)` and
  collects `(c.source, c.domains_dir)` for every contributor exposing
  `domains_dir`. It appends the project-local pool `(root/.praxis/domains)` last,
  as owner `project`.
- **Owns**: `merge_pool` parses each `*.md` with
  `parse_domain_file(path, owner=source)` and then stamps `domain.owner = source`
  authoritatively. **You do not hand-author `owner`** — it is derived from the
  plugin's `source`. If a file *does* declare `owner`, the parser requires it to
  equal the derived source or it raises; the derived value wins regardless.
- **Precedes**: precedence is two layers, **plugin < project**.
  - A **project** domain (from `root/.praxis/domains`) with the same bare `id` as
    a plugin domain **overrides it wholesale** — the plugin's version is dropped
    entirely (never a field-level merge).
  - **Peer plugins** that ship the same bare `id` **coexist** as distinct
    `owner/id` entities (e.g. `general/coding-general` and `uiux/coding-general`
    both inject). Nothing installed is silently shadowed.
  - Same `owner/id` twice (two files in one plugin sharing an `id`) is an
    authoring error: skipped and reported to stderr.

Because discovery only ever reads *this* root's registrations and *this* root's
local pool, roots are fully isolated with no enforcement code — a sibling's,
parent's, or child's judgment has no path to reach it.

---

## The old→new domain transform rules

Domain files from the old `attempted_skills/corpora/domains/` set **do not parse**
under the new schema. Every migrated file must end up as: parser-valid
frontmatter, followed by a body that is **pure YAML** with only top-level
`conventions:` and `principles:` keys. The parser does `yaml.safe_load` on the
*entire* body — any stray markdown, prose, or `#`-header outside those two
sequences breaks the load.

### Mapping table

| Old element | New element | Rule |
|---|---|---|
| frontmatter `posture: ...` | **DROP** | `posture` is retired — stance is a praxis phase concern now. The composer no longer reads it and the parser tolerates its absence; omit it entirely. |
| frontmatter `units-of-work: [...]` | **DROP**, or fold into affinity tags | Not a schema field. Where it carries signal: implementation-ish units → `task-kinds: [create, change]`; a named process (e.g. `debug`, `tdd`) → `workflows: [...]`; a topical tag → `labels: [...]`. Otherwise omit entirely. |
| frontmatter `subject` | `subject` | Keep unchanged (already compatible). |
| frontmatter `universal` | `universal` | Keep unchanged. |
| frontmatter `applies-when` | `applies-when` | Keep unchanged. |
| frontmatter `owner` (if present) | **OMIT** | Never hand-author. Derived from the plugin `source` at discovery. (If kept, it must equal the source or the parser raises.) |
| add frontmatter `id` | `id` | **Required** by the parser. Use the domain's stable name (e.g. `coding-general`). Old files often carried it only as a `# Domain:` header — promote it into frontmatter. |
| markdown preamble bullets (hardened rules stated in prose before `principles:`, no per-item reason) | `conventions:` entries | Convert each to `{id, rule}`. Terse, imperative, **no rationale**. Strip the explanatory prose — a convention has no `reason` field. |
| `principles:` list | `principles:` list | Keep. Each principle MUST have all four of `id`, `rule`, `condition`, `reason` (all required by the parser). If an old principle lacks `condition`/`reason`, supply a faithful one drawn from its surrounding text. |
| `killed:` sections | **DROP** | Not part of the schema. |
| audit references, `last-retrospective:`, `see-also:`, other stray body keys | **DROP** | Body must contain *only* `conventions:` and `principles:`. Anything else is stray YAML that pollutes the parse. |
| `# Domain: ...` markdown headers, any prose outside the two YAML sequences | **DROP** | The whole body is `yaml.safe_load`-ed; markdown headers and free prose are not valid there. |

### Required-field checklist per file

- **Frontmatter (required)**: `id`, `subject`. (`applies-when`,
  `universal`, `task-kinds`, `workflows`, `labels` are optional; `posture` is
  retired — omit it.)
- **Each convention**: `id`, `rule`.
- **Each principle**: `id`, `rule`, `condition`, `reason` — all four.
- **Body**: valid YAML mapping; only `conventions:` and `principles:` at top
  level; nothing else.

---

## Worked before/after — `coding-general.md`

### Before (old format — does NOT parse)

```markdown
---
subject: coding
posture: guardrail
units-of-work: [implement-feature, debug-issue]
universal: false
---

# Domain: coding-general

Stack-agnostic coding judgment — applies in any language or framework...

Foundational, stable across every project shape this domain serves — held here
in the preamble rather than in `principles:` ... (provenance: `domains/audit.md`):

- **No peer re-exports** — import from the authoritative module, not a peer that
  happens to re-export it. Barrel index files that explicitly aggregate a public
  surface are the only exception. Near-unconditional; needs no per-case
  condition-weighing.
- Keep scope tight: implement what was asked, nothing more. Before adding any new
  function, type, or abstraction, ask whether it needs to exist at all...
- Run the project's verification commands (lint, type-check, build) before
  finishing.

```yaml
last-retrospective: 2026-08-07

principles:

- id: ask-before-architecture
  rule: "When a task involves a structural or DRY question with two reasonable
    approaches, name both and ask before implementing."
  condition: "When implementing a structural change where multiple approaches
    are plausible — class vs. function extraction, inline vs. extracted helper."
  reason: "Architectural questions are cheap to clarify and expensive to
    implement wrong. One question saves a full round-trip correction."

- id: single-callsite-helper-scoped
  rule: "A function that computes a value and has exactly one callsite should not
    be extracted as a standalone function..."
  condition: "When a standalone helper has exactly one callsite..."
  reason: "A standalone function implies reuse. A single-callsite helper adds a
    named concept with no benefit."

killed:
```

Problems: `posture` is retired (drop it); `units-of-work` is not a
field; there is no `id` in frontmatter; the `# Domain:` header and the preamble
prose sit in the body where `yaml.safe_load` chokes; `last-retrospective:` and
`killed:` are stray body keys.

### After (migrated — parses under the new schema)

```markdown
---
id: coding-general
# no owner: line — derived from the plugin source at discovery
#   in the `general` plugin's domains_dir -> owner: general
#   in root/.praxis/domains              -> owner: project
subject: coding
universal: false
applies-when: []
task-kinds: [create, change]
---

conventions:
  - id: no-peer-re-exports
    rule: Import from the authoritative module, not a peer that re-exports it; barrel index files that aggregate a public surface are the only exception.
  - id: tight-scope
    rule: Implement what was asked and nothing more; before adding any function, type, or abstraction, stop at the first rung that already covers it (stdlib, an installed dependency), and prefer the framing with the smaller net addition.
  - id: run-verification
    rule: Run the project's verification commands (lint, type-check, build) before finishing.

principles:
  - id: ask-before-architecture
    rule: When a task involves a structural or DRY question with two reasonable approaches, name both and ask before implementing.
    condition: When implementing a structural change where multiple approaches are plausible — class vs. function extraction, inline vs. extracted helper.
    reason: Architectural questions are cheap to clarify and expensive to implement wrong. One question saves a full round-trip correction and avoids a messy intermediate state the user has to redirect out of.
  - id: single-callsite-helper-scoped
    rule: A function that computes a value and has exactly one callsite should not be extracted as a standalone function; resolve it in the calling scope, as a local when the expression is long or inlined when short.
    condition: When a standalone helper has exactly one callsite. Does not apply to functions called from two or more places — those earn the extraction.
    reason: A standalone function implies reuse. A single-callsite helper adds a named concept with no benefit; keeping the resolution local is more honest about its scope.
```

What changed: `guardrail → convergent`; `units-of-work` dropped, its
implementation signal folded into `task-kinds: [create, change]`; `id` promoted
into frontmatter; `owner` left underived; the preamble bullets became terse
`conventions:` entries with the rationale prose stripped; the principles kept all
four required fields; the `# Domain:` header, preamble prose, `last-retrospective:`,
and `killed:` all dropped so the body is pure `conventions:` + `principles:` YAML.

This migrated file, dropped into the `general` plugin's `domains/`, is stamped
`owner: general`. The identical file dropped into a repo's `root/.praxis/domains`
is stamped `owner: project` with no edit — distribution is the only choice that
sets the layer.
