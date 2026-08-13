# Praxis glossary — names by what they do

The vocabulary of the system, named by what each part **provides** so the whole can be reasoned
about without decoding acronyms or build-lap codenames. This reflects the naming applied on
2026-08-12 (see `review-2026-08-12.md` F4); the retired-names table at the bottom decodes older
commits and history docs.

## Core vocabulary

| name | what it provides |
|---|---|
| **spec** (the rebuild blueprint) | the structured contract the `extract` phase emits — `interface` + `allowed_surface` + a `tests.{spec,held_out}` split (`rebuild_spec.py`). Threaded to `synthesize` as `composed["spec"]`. |
| **unit graph** | the plan's units + their `depends_on` edges; what the scheduler walks in dependency waves. |
| **adequacy barrier** | the test-strength signal: the fast per-unit **coverage gate** + the slow plan-level **mutation barrier** run once at close. |
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

## Deliberately not renamed

- **`run_dag` / `failing_subdag`** — the function identifiers keep `dag`. Prose says "unit graph,"
  but renaming these identifiers exceeded the confirmed scope of the naming pass (it touches ~10
  test files with no contract benefit). A candidate for a later mechanical rename.

## Open naming questions

- **`cascade`** — the detached background worker. If review F2 deprecates the detached path, this
  name retires with it; otherwise rename to something that says "detached unit-graph worker."
- **`accretion`** — gap-surfacing that promotes recurring gaps into minted vocabulary. Functional
  but obscure; candidate: **vocabulary minting**.
