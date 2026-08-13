# Praxis plugins — where things live

Plugins bundled with praxis under `plugins/<name>/`. A plugin can carry either or both:
- **Judgment** — a `domains_dir` of `*.md` files that **corpora** discovers and composes.
- **Process** — a Contributor (`contribute` / `hooks` / `surface` / `phases` / `workflows`).

Enabled by a `module:factory` line in a root's `.praxis/config.json` under `contributors`
(fail-soft). How to build one: `JUDGMENT-PLUGIN.md`. Domain schema + composer internals: the peer
`corpora` repo (`~/jdev/skills/corpora`).

## Discovery

A plugin's main module sets `PRAXIS_PLUGIN = True`; `scripts/plugin_registry.py` finds it
statically by that marker (no import, no filename convention), unioned across a layered search
path, LOW→HIGH precedence (higher wins a name collision):

1. **bundled** — `plugins/` (default plugins-root, from `__file__`).
2. **global** — Claude Code's *installed* plugins under `~/.claude` (paths from
   `plugins/installed_plugins.json` + `skills/` symlink targets, each scanned for the marker).
3. **project** — `<root>/.praxis/plugins`.
4. **explicit** — dirs in the root's `plugins_search_paths` config key.

## Plugins

| Plugin | Role |
|---|---|
| **corpora** (peer repo) | The pure composer — ships NO domains. Discovers every plugin's `domains_dir` + the project pool, merges (plugin < project), coarse-cuts by subject/applies-when, defers the fine call to the model. Harvests proposals on `unit-close`. |
| **general** | Stack-agnostic coding judgment (coding-general, debugging, testing, security, architecture-health, codebase-design, …). |
| **coding-stack** | Stack-specific judgment gated by `applies-when` (ts/react/nextjs/expo, css, …). |
| **uiux** | Design-decision judgment + the full process example: `contribute`/`hooks`/`surface`/`phases`/`workflows`, backed by `library_state.py`, `deferred_queue.py`. |
| **writing** | Process-only: prose draft/revision phases + workflow. |
| **rebuild** | Process-only: the rebuild triple — extract/synthesize phases, the `rebuild-triple` workflow with its own gate forms (spec adequacy at extract-exit; tripwire ∘ coverage-diff at synthesize-exit), spec validation (`rebuild_spec.py`), and worktree isolation + copy-detection (`isolation.py`, `hooks/tripwire_log.sh`). |
| **coding-process** | Process-only: TDD vocabulary — write-tests/refactor/test-cleanup phases + the `tdd-unit` workflow. |

**Retired:** `monorepo` — cross-root delegation is now default praxis behavior, not opt-in
judgment. Its one load-bearing rule (a task spanning roots is one unit per owning root, `root_tree`
owns traversal, interact at the parent root and delegate into the owning root) is folded into
`skills/orchestrate/SKILL.md` directly.

## Core pattern

Judgment lives in **domain files owned by plugins**, composed by **corpora** (many owners, one
composer). Process lives in **Contributors** praxis core runs. A "bare" judgment plugin is a
`domains_dir` + a ~10-line contributor whose `contribute` returns `[]`.
