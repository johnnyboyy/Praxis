# Praxis glossary — names by what they do

The vocabulary of the system, named by what each part **provides** so the whole can be reasoned
about without decoding acronyms or build-lap codenames. This reflects the naming applied on
2026-08-12 (see `review-2026-08-12.md` F4); the retired-names table at the bottom decodes older
commits and history docs.

## Core vocabulary

| name | what it provides |
|---|---|
| **spec** (the rebuild blueprint) | the structured contract the `extract` phase emits — `interface` + `allowed_surface` + a `tests.{spec,held_out}` split (`rebuild_spec.py`). Threaded to `synthesize` as `composed["spec"]`. |
| **unit graph** | the plan's units + their `depends_on` edges; what the drive walks in dependency order. |
| **adequacy barrier** | the test-strength signal at close. Its FORM is plugin/root content (the core owns only "close is reachable through passed gates"); the rebuild plugin ships a coverage form. |
| **preservation gate** | the rebuild-seam check — coverage-diff / held-out — answering "did the rebuild preserve behavior?" (`coverage_diff_verifier`). |
| **rebuild isolation** | the synth-seam defense: a spec-only seeded worktree + a copy-detection **tripwire** + dependency hygiene (`isolation.py`). Best-effort, not a capability boundary. |
| **barrier** | the contract the work must satisfy, authored up front; close is reachable only through it. |
| **gate** | a deterministic check on an edge that can refuse to advance a unit/phase. |
| **phase** | one atomic move — an agent dispatch or a deterministic step. |
| **edge** | a typed transition between phases (`create`/`carry`/`extract`); carries the preservation gate. |
| **workflow** | a graph of phases a unit walks instead of a single dispatch. |
| **frontier** | the decision checklist the interview settles before planning (`.praxis/planner/frontier.md`); `open` until every item is answered. |
| **attractor** | an artifact in context that instructions cannot reliably override; the reason the context boundary is a property of the edge. |
| **rebuild triple** | `extract → synthesize → coverage-diff`, the expanded `extract` edge. |
| **tripwire** | the copy-detection detector that flags a synth read resolving outside its worktree. |
| **contributor** | a per-root plugin object that injects context / hooks / edit-lease / phases. |
| **composer** | corpora — composes judgment from registered plugins' domains. |

## Retired names (decode older commits / history docs)

| retired | now |
|---|---|
| `IR` | **spec** (identifier `ir` → `spec`; `rebuild_ir.py` → `rebuild_spec.py`; `IRError`/`validate_ir` → `SpecError`/`validate_spec`) |
| `DAG` | **unit graph** (in prose; the `run_dag` / `failing_subdag` function identifiers are unchanged — see below) |
| `R1` | the engine-run **block gate** (create/`does-it`) |
| `R2` | the **adequacy barrier** (coverage + mutation) |
| `R3a` | the **preservation gate** (+ the extract-exit **adequacy gate**) |
| `R3b` | **rebuild isolation** |

## Retired with the 2026-08-12 cut (see `cut-plan-2026-08-12.md`)

- **`cascade` / `run_dag`** — the detached in-process execution engine; deleted (F2 resolved by
  deprecation). The model drives; the journal is the cursor.
- **`accretion` / minting** — the promotion machinery; deleted. The gap SIGNAL remains
  (`fit`/`suggested`, `conductor.gap`/`phase.gap` events, `/praxis:report gaps`); promoting a
  gap is an operator act: add the phase to a plugin.
- **stance** (`Situation.phase`, divergent/convergent) — the second per-phase channel; deleted.
  `phase_name` is the only channel `contribute` branches on. (`Phase.stance` remains as
  descriptive metadata on phase definitions.)
- **`agent-choice` edges** — routing by `evidence["next"]`; deleted. Routing is gates + `fact`
  predicates + `pass`/`fail`/`always` defaults.
