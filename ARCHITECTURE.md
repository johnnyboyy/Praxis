# Praxis — where things live

A **high-level map** of the praxis core. Deliberately shallow: it names each component, its
one job, and its entry-point file — the kind of overview that drifts slowly. For mechanism,
read the code; for the *why*, read `docs/design.md`; for the plugin contract, `docs/plugins.md`.

Praxis in one line: **a deterministic phase-graph engine that owns process invariants in
code, and composes all domain judgment from fail-soft, per-root code Contributors.** The core
ships no judgment.

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
| `situation.py` | `Situation` — the framing a Contributor sees (`task_kind`, `subject`, `phase`=stance, `phase_name`, `project_shape`, `targets`, `workflow`, `label`). |
| `orchestrate.py` / `cascade.py` | Orchestration altitude: fan-out → barrier full-verify → bounded fix-loop → escalation. |
| `conduct.py` / `plan.py` / `handoff.py` | The inline drive: `register_plan` → `next_handoff` → `close_unit`; plan DAG bookkeeping; handoff assembly. |
| `scripts/gate.py`, `scripts/units.py`, `hooks/` | The **edit-lease gate**: a PreToolUse hook denies out-of-lease edits via a pure function over the journal (glob `surface_allows`). |
| `journal.py` | Append-only event log (`.praxis/journal.jsonl`) — the source of truth for plan/unit/phase state. |
| `config.py` | `.praxis/config.json` — the namespaced per-root store (the `## contributors` registry + each plugin's own scope). |
| `accretion.py` | Gap-surfacing: recurring `phase.gap` / `conductor.gap` → operator-minted vocabulary (names, not runnable phases). |
| `mcp_server.py` | The MCP tool surface (see entry points). |

## Entry points

- **MCP tools**: `init`, `register_plan`, `next_handoff`, `record_receipt`, `close_unit`,
  `plan`, `plan_status`, `conduct`, `conductor_*`.
- **Shell hooks** (`hooks/`): the frame-gate + payload stamps, wired via `hooks/hooks.json`.
- **Skills** (`skills/`): `init`, `inline`, `orchestrate`.

## Docs

- `docs/design.md` — the enduring conceptual model (edges, gates, the rebuild triple, the
  attractor theory). Load-bearing; read this for *why*.
- `docs/plugins.md` — the current Contributor contract.
- `docs/history/` — historical build-time IRs (superseded by code + tests).

## The invariant worth remembering

Mechanism is owned by the core and enforced in code; **judgment is deferred to the model**
and composed from plugins. An empty root injects nothing — that is intended.
