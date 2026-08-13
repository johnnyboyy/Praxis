# Praxis plugins — where things live

Plugins bundled with praxis under `plugins/<name>/` are **process-only** now: each is a
Contributor (`contribute` / `hooks` / `surface` / `phases` / `workflows`). None of them ship a
`domains_dir` any more.

Judgment (hand-authored domain files) lives in the peer **domains bucket**
(`~/jdev/skills/domains`, collections `general`/`coding-stack`/`uiux`/`planner`), a standalone
repo consumed via corpora's import/sources flow — not injected by a praxis plugin. See that
repo's `README.md` for the collection model, and `corpora:import` / a root's `corpora.sources`
config for how a project pulls from it.

Enabled by a `module:factory` line in a root's `.praxis/config.json` under `contributors`
(fail-soft). How to build a judgment-carrying plugin (still a supported mechanism, just not one
praxis ships any of): `JUDGMENT-PLUGIN.md`. Domain schema + composer internals: the peer
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
| **corpora** (peer repo) | The pure composer — ships NO domains. Discovers every registered contributor's `domains_dir` (none of the bundled plugins have one now) + the project pool + the domains bucket's sources, merges, coarse-cuts by subject/applies-when, defers the fine call to the model. Harvests proposals on `unit-close`. |
| **writing** | Process-only: prose draft/revision phases + workflow. |
| **rebuild** | Process-only: the rebuild triple — extract/synthesize phases, the `rebuild-triple` workflow with its own gate forms (spec adequacy at extract-exit; tripwire ∘ coverage-diff at synthesize-exit), spec validation (`rebuild_spec.py`), and worktree isolation + copy-detection (`isolation.py`, `hooks/tripwire_log.sh`). |
| **coding-process** | Process-only: TDD vocabulary — write-tests/refactor/test-cleanup phases + the `tdd-unit` workflow. |

**Retired:** `general`, `coding-stack` — bare judgment plugins (a `domains_dir` + a
contribute-returns-`[]` stub) that carried stack-agnostic and stack-specific coding judgment.
Deleted wholesale; their domain files were seeded into the peer domains bucket's `general` and
`coding-stack` collections before removal.

**Retired (moved to a peer repo):** `uiux` — the full process example
(`contribute`/`hooks`/`surface`/`phases`/`workflows`, backed by `library_state.py`,
`deferred_queue.py`) now lives and is maintained at `~/jdev/skills/uiux` (its own repo, own test
suite), not under `plugins/`. A consuming root registers it via the **explicit** discovery layer
(`plugins_search_paths`) rather than the bundled layer; its `contributors` entry
(`"uiux": "uiux_plugin:make"`) is unchanged. Its former design-judgment domains still live in the
peer domains bucket's `uiux` collection.

**Retired:** `monorepo` — cross-root delegation is now default praxis behavior, not opt-in
judgment. Its one load-bearing rule (a task spanning roots is one unit per owning root, `root_tree`
owns traversal, interact at the parent root and delegate into the owning root) is folded into
`skills/orchestrate/SKILL.md` directly.

**Retired:** `planner` — dissolved: its judgment lives in the peer domains bucket's `planner`
collection (composed via corpora as before), and its process discipline (`interview -> frontier ->
barrier -> plan`) is now owned directly by `skills/orchestrate/SKILL.md` rather than claimed as an
engine-driven workflow.

## Core pattern

Judgment lives in **domain files owned by the peer domains bucket**, composed by **corpora**
(many collections, one composer) via import/sources — not by praxis plugins. Process lives in
**Contributors** praxis core runs. A judgment plugin (the mechanism still exists, just unused by
anything bundled here) is a `domains_dir` + a ~10-line contributor whose `contribute` returns
`[]`.
