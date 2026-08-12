# Praxis — where things live

A **high-level map** of the praxis core. Deliberately shallow: it names each component, its
one job, and its entry-point file — the kind of overview that drifts slowly. For mechanism,
read the code; for the *why*, read `docs/design.md`; for the plugin contract, `docs/plugins.md`.

Praxis in one line: **a deterministic phase-graph engine that owns process invariants in
code, and composes all domain judgment from fail-soft, per-root code Contributors.** Nothing
composes until a plugin is registered; praxis bundles a default set under `plugins/` and a root
turns on the ones it wants.

## The model (concepts)

- **Unit of work** → walks a **workflow** (a graph of **phases**) instead of a single dispatch.
- **Phase** — one atomic move (`name`, `stance`, `delivery`, optional `run`). Delivery is
  `inline` | `spawn` | `deterministic` (a phase can run a script instead of an agent).
- **Edge** — typed transition between phases: `pass` | `fail` | `always` | `agent-choice` |
  `fact` (routes on a predicate over the phase's emitted facts). The context/preservation
  boundary is a property of the **edge**, not the phase (`docs/design.md`).
- **Contributor** — a plugin object that injects context (`contribute`), reacts at steps
  (`hooks`: `verify` / `unit-close` / `close`), declares an edit lease (`surface`), and/or
  provides `phases()` / `workflows()`. Registered per-root; loaded fail-soft.

## Components (file → job)

| File | Job |
|---|---|
| `contributors.py` | The **Contributor contract**: `contribute`/`hooks`/`surface`/`phases`/`workflows`, `Contribution`/`HookContext`, `contributors_for(root)` (loads `module:factory` specs from config), `gather`, `fire`. The plugin surface. |
| `workflow.py` | `Phase` / `Workflow` / edge dataclasses; `WHENS`; the seed phase/workflow library. |
| `workflow_run.py` | `run_workflow` — the phase walker: edge routing (`_choose_edge`), deterministic delivery, the aggregate receipt, `phase_fit`/`phase.route_unmatched` recording. |
| `registry.py` | `resolve_phases` / `resolve_workflows` — merge seed phases/workflows with contributor-provided ones (seed wins, first-plugin wins; fail-soft). |
| `run.py` | `run_unit` — the live drive: single-dispatch or resolve+run a named workflow; fires `verify` / `unit-close` / `close` hooks (`_finish`). |
| `situation.py` | `Situation` — the framing a Contributor sees (`task_kind`, `subject`, `phase`=stance, `phase_name`, `workflow`, `label`, `targets`, `intent`). Project-shape is not a Situation field — corpora detects it and stores it in its own config namespace. |
| `orchestrate.py` / `cascade.py` | Orchestration altitude: fan-out → barrier full-verify → bounded fix-loop → escalation. |
| `conduct.py` / `plan.py` / `handoff.py` | The inline drive: `register_plan` → `next_handoff` → `close_unit`; plan DAG bookkeeping; handoff assembly. |
| `scripts/gate.py`, `scripts/units.py`, `hooks/` | The **edit-lease gate**: a PreToolUse hook denies out-of-lease edits via a pure function over the journal (glob `surface_allows`). |
| `journal.py` | Append-only event log (`.praxis/journal.jsonl`) — the source of truth for plan/unit/phase state. |
| `config.py` | `.praxis/config.json` — the namespaced per-root store (the `## contributors` registry + each plugin's own scope). |
| `accretion.py` | Gap-surfacing: recurring `phase.gap` / `conductor.gap` → operator-minted vocabulary (names, not runnable phases). |
| `mcp_server.py` | The MCP tool surface (see entry points). |

## Plugins & how one is discovered

Plugins live under `plugins/<name>/` (bundled with praxis; see `plugins/ARCHITECTURE.md`).
A plugin identifies itself with a module-level `PRAXIS_PLUGIN = True` marker in its main
module — discovery is marker-driven and static (no import, no filename convention).
`scripts/plugin_registry.py` unions plugins across a layered search path, LOW→HIGH
precedence (higher wins on a name collision):

1. **bundled** — `plugins/` shipped with praxis (default plugins-root, derived from `__file__`).
2. **global** — best-effort enumeration of Claude Code's *installed* plugins under `~/.claude`:
   install paths read from `plugins/installed_plugins.json` (the authoritative v2 registry) plus
   `skills/` symlink targets (skills-directory plugins Claude Code symlinks in), each scanned for
   the marker. Plugin *source* does not live under `~/.claude/plugins/`, so that dir is never
   scanned directly. This makes a praxis plugin shipped inside an installed Claude Code plugin
   discoverable in every project. Fail-soft if the registry/skills dir is absent or malformed.
3. **project** — `<root>/.praxis/plugins`.
4. **explicit** — dirs listed in the root's top-level `plugins_search_paths` config key.

A root enables plugins with the `:register-plugins` skill, which writes the `## contributors`
map and a top-level `plugins_path` (the union of selected plugin dirs, prepended to `sys.path`
so the `module:make` specs import without any external `PYTHONPATH`).

## Entry points

- **MCP tools**: `init`, `register_plan`, `next_handoff`, `record_receipt`, `close_unit`,
  `plan`, `plan_status`, `conduct`, `conductor_*`.
- **Shell hooks** (`hooks/`): the frame-gate + payload stamps, wired via `hooks/hooks.json`.
- **Skills** (`skills/`): `init`, `inline`, `orchestrate`, `register-plugins`.

## Docs

- `docs/design.md` — the enduring conceptual model (edges, gates, the rebuild triple, the
  attractor theory). Load-bearing; read this for *why*.
- `docs/plugins.md` — the current Contributor contract.
- `docs/history/` — historical build-time IRs (superseded by code + tests).

## The invariant worth remembering

Mechanism is owned by the core and enforced in code; **judgment is deferred to the model**
and composed from plugins. Nothing composes until a plugin is registered — an unregistered
root injects nothing. Bundling a default plugin set is normal: they still only take effect
once a root turns them on.
