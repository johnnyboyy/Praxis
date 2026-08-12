# Praxis plugins — where things live

A **high-level map** of the plugins, bundled with praxis under `praxis/plugins/<name>/`.
Shallow by design (names + one job each). For how to build one, read `JUDGMENT-PLUGIN.md`;
for the domain schema, the peer corpora repo (`~/jdev/skills/corpora`, package `corpora`).

Two kinds of thing a plugin can carry (a plugin may do either or both):
- **Judgment** — a `domains_dir` of `*.md` domain files that **corpora** discovers and composes.
- **Process** — a Contributor with `contribute` / `hooks` / `surface` / `phases` / `workflows`.

A plugin is enabled by a `module:factory` line in a consuming root's
`.praxis/config.json` under `## contributors`. Loading is fail-soft.

## How a plugin is discovered

A plugin's main module sets a module-level `PRAXIS_PLUGIN = True` marker; discovery
(`praxis/scripts/plugin_registry.py`) finds it **statically** by that marker — not by
filename and without importing. Plugins are unioned across a layered search path, LOW→HIGH
precedence (higher layer wins on a name collision):

1. **bundled** — `praxis/plugins/` (the default plugins-root, derived from `__file__`).
2. **global** — best-effort enumeration of Claude Code's *installed* plugins under `~/.claude`:
   install paths read from `plugins/installed_plugins.json` (the authoritative v2 registry) plus
   `skills/` symlink targets, each scanned for the marker. Plugin *source* does not live under
   `~/.claude/plugins/`, so that dir is never scanned directly. This makes a praxis plugin bundled
   inside a globally-installed Claude Code plugin discoverable in every project.
3. **project** — `<root>/.praxis/plugins`.
4. **explicit** — dirs in the root's top-level `plugins_search_paths` config key.

## The composer

corpora is **no longer bundled here** — it lives as a **peer repo** (`~/jdev/skills/corpora`,
package `corpora`) registered as `corpora.plugin:make` (discovered via the `~/.claude/skills`
symlink or a `plugins_search_paths` entry). It is not one of the plugins under `praxis/plugins/`.

| Plugin | Role |
|---|---|
| **corpora** (peer) | The **pure composer** — ships NO domains. Discovers every registered plugin's `domains_dir` + the project-local pool (`<root>/.praxis/domains`), merges under two-layer precedence (plugin < project), does a coarse subject + applies-when cut, and defers the fine "does this apply" call to the model. (See the peer corpora repo for the composer's internals.) Also **harvests** proposals into an unratified `candidates.md` on `unit-close`. Modules: `plugin.py` (`make`), `compose.py` (compose), `discovery.py` (merge), `parser.py`, `models.py`. |

## Judgment plugins (carry domains, composed by corpora)

| Plugin | Carries |
|---|---|
| **general** | Stack-agnostic coding judgment (coding-general, debugging, testing, security, architecture-health, codebase-design, code-review-reception, dependency-management). |
| **coding-stack** | Stack-specific coding judgment, gated by `applies-when` (coding-ts/react/nextjs/expo, css, dependency-management-expo, release-readiness-expo). |
| **uiux** | Design-decision judgment (color, motion, visual-hierarchy, surfaces-elevation, forms-inputs, lists-selection, validation-feedback, wizards-flows, recoverability, ranking-evaluation). |
| **monorepo** | Coordination judgment (monorepo-coordination). |

## Process plugins (contribute / phases / workflows / hooks)

| Plugin | Process face |
|---|---|
| **uiux** | The full example. `contribute` (graduated disclosure keyed on phase name), `hooks` (`unit-close`: drift, screenshot staleness, decision filing, design-sync recommendation), `surface` (docs-only design lease), `phases()`/`workflows()` (library-init/sync, design-decision-review, the deterministic `library-state` fact phase, `design-bootstrap` / `feature-design` / `design-sync` workflows). Backed by `library_state.py`, `deferred_queue.py`. |
| **writing** | Process-only (no domains, by design): `contribute` (prose draft/revision by stance) + `writing-draft`/`writing-revision` phases + workflow. |
| **monorepo** | Coordination framing: `contribute` for cross-root/process units; defers traversal to core `root_tree`. |

## Contracts (current, load-bearing)

- `JUDGMENT-PLUGIN.md` — how to build a plugin + the old→new domain transform rules.
- the peer corpora repo (`~/jdev/skills/corpora`) — the domain-file schema and the composer's design (discovery, precedence, graduated disclosure) now live with the peer package.
- `REGISTER-EXAMPLE.md` — a sample `.praxis/config.json` registration.
- `<plugin>/history/` — historical build-time IRs where present (superseded by code + tests).

## The pattern worth remembering

Judgment lives in **domain files owned by plugins** and is composed by **corpora** (many
owners, one composer). Process lives in **Contributors** that praxis core runs. A "bare"
judgment plugin is just a `domains_dir` + a ~10-line contributor whose `contribute` returns `[]`.
