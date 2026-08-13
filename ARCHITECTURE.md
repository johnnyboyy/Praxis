# Praxis — where things live

A deterministic process referee: the model executes, praxis owns the invariants in code —
framing, the edit lease, gated phase walks, the journal — and composes domain judgment from
fail-soft, per-root Contributors. Nothing composes until a plugin is registered.

For the *why*, read `docs/design.md`; for the plugin contract, `docs/plugins.md`; for names,
`docs/glossary.md`; for plugin discovery, `plugins/ARCHITECTURE.md`.

## The one execution model

There is no in-process executor: praxis never spawns workers. Work is driven by the model
through the MCP surface, and the journal is the cursor:

```
register_plan → next_handoff (frames the unit, opens the edit gate)
             → [workflow units] next_phase → record_phase (gate runs FROM DISK) → …
             → close_unit / record_receipt (fires the unit-close hook)
```

Fan-out belongs to the harness (the orchestrate skill dispatches subagents); the engine
refuses to advance past a failed gate and refuses to close a halted walk.

## Components (file → job)

| File | Job |
|---|---|
| `contributors.py` | The Contributor contract: `contribute`/`hooks`/`surface`/`phases`/`workflows`, `contributors_for(root)`, `gather`, `fire`. |
| `workflow.py` | `Phase` / `Workflow` dataclasses, typed edges + `GATES`; the minimal seed: phases plan/implement/verify/fix/close, workflow **build-verify**. |
| `phase_walk.py` | The one walker: `decide_step` (edge routing + gate verdict) and the resumable `next_phase`/`record_phase` journal-cursor surface. |
| `registry.py` | `resolve_phases` / `resolve_workflows` — merge seed + contributor objects (seed wins, first-plugin wins, fail-soft). |
| `run.py` | Data model (`Receipt`, `Unit`, `Verdict`) + gate plumbing (`Verifier`, `CallableVerifier`/`CommandVerifier`, `verifier_from_test_cmd`, `verifiers_for_workflow` — honors a workflow's own `verifiers` factory). |
| `conduct.py` / `plan.py` / `handoff.py` | The drive: `register_plan` → `next_handoff` → `close_unit`; unit-graph bookkeeping; handoff assembly; `unit-close` hook firing. |
| `scripts/gate.py`, `scripts/units.py`, `hooks/` | The edit-lease gate: a PreToolUse hook denies out-of-lease edits via a pure function over the journal. |
| `journal.py` | Append-only event log (`.praxis/journal.jsonl`) — the source of truth for plan/unit/phase state. |
| `config.py` | `.praxis/config.json` — the namespaced per-root store (contributors registry + each plugin's scope). |
| `views.py` | `cost` — the journal's cost rollup. |
| `mcp_server.py` | The MCP tool surface. |

Process vocabulary beyond the seed is plugin content: `plugins/rebuild/` (the rebuild triple —
extract/synthesize, spec validation, isolation + tripwire, coverage-diff/adequacy gates) and
`plugins/coding-process/` (tdd-unit). See `plugins/ARCHITECTURE.md`.

## Entry points

- **MCP tools**: `init`, `register_plan`, `next_handoff`, `next_phase`, `record_phase`,
  `close_unit`, `record_receipt`, `escalate_unit`, `plan_status`, `conductor_status`.
- **Shell hooks** (`hooks/`): the frame-gate + payload stamps + the rebuild tripwire logger,
  wired via `hooks/hooks.json`.
- **Skills** (`skills/`): `init`, `inline`, `orchestrate`, `register-plugins`, `report`.
