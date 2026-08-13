# Praxis — where things live

A deterministic phase-graph engine that owns process invariants in code, and composes domain
judgment from fail-soft, per-root Contributors. Nothing composes until a plugin is registered.

For the *why*, read `docs/design.md`; for the plugin contract, `docs/plugins.md`; for names,
`docs/glossary.md`; for plugin discovery, `plugins/ARCHITECTURE.md`.

## Components (file → job)

| File | Job |
|---|---|
| `contributors.py` | The Contributor contract: `contribute`/`hooks`/`surface`/`phases`/`workflows`, `contributors_for(root)`, `gather`, `fire`. |
| `workflow.py` | `Phase` / `Workflow` / edge dataclasses; the seed phase/workflow library. |
| `workflow_run.py` | `run_workflow` — the phase walker: edge routing, deterministic delivery, aggregate receipt, `phase_fit` recording. |
| `registry.py` | `resolve_phases` / `resolve_workflows` — merge seed + contributor objects (seed wins, first-plugin wins, fail-soft). |
| `run.py` | `run_unit` — single-dispatch or named-workflow drive; the coverage/mutation verifiers and rebuild gates (`adequacy_verifier`, `coverage_diff_verifier`). |
| `rebuild_spec.py` | The structured spec the `extract` phase emits (`interface` / `allowed_surface` / `tests.{spec,held_out}`); `validate_spec` is fail-closed and enforces a real held-out split. |
| `isolation.py` | Rebuild isolation + copy-detection: `seed_synth_worktree`, `dep_hygiene_ok`, `scan_tripwire`, `synthesize_exit_gate`. |
| `situation.py` | `Situation` — the framing a Contributor sees (`task_kind`, `subject`, `phase`=stance, `phase_name`, `workflow`, `targets`, `intent`). |
| `orchestrate.py` / `cascade.py` | Orchestration altitude: fan-out → barrier full-verify → bounded fix-loop → escalation. |
| `conduct.py` / `plan.py` / `handoff.py` | The inline drive: `register_plan` → `next_handoff` → `close_unit`; unit-graph bookkeeping; handoff assembly. |
| `scripts/gate.py`, `scripts/units.py`, `hooks/` | The edit-lease gate: a PreToolUse hook denies out-of-lease edits via a pure function over the journal. |
| `journal.py` | Append-only event log (`.praxis/journal.jsonl`) — the source of truth for plan/unit/phase state. |
| `config.py` | `.praxis/config.json` — the namespaced per-root store (contributors registry + each plugin's scope). |
| `accretion.py` | Gap-surfacing: recurring `phase.gap` / `conductor.gap` → operator-minted vocabulary. |
| `mcp_server.py` | The MCP tool surface. |

## Entry points

- **MCP tools**: `init`, `register_plan`, `next_handoff`, `record_receipt`, `close_unit`,
  `plan`, `plan_status`, `conduct`, `conductor_*`.
- **Shell hooks** (`hooks/`): the frame-gate + payload stamps, wired via `hooks/hooks.json`.
- **Skills** (`skills/`): `init`, `inline`, `orchestrate`, `register-plugins`.
