# Historical build-time specs

These are the **implementation IRs** that were written to drive specific builds, and the
**proposal doc** for work that is now shipped. They are **superseded by the code and its
tests, which are the current source of truth.**

Kept — not deleted — because they carry the *design rationale* (the "why" behind decisions)
that the code does not. **Do not read them as a description of current behavior**; where they
say "will" / "in the next unit" / "proposal", the work is done. Consult `../design.md` (the
enduring conceptual model) and `../plugins.md` (the current Contributor contract) instead.

| File | Was the IR for | Now lives in code as |
|---|---|---|
| `plugin-phases.md` | the proposal + demonstrations for making phases plugin-extensible | `registry.py`, `workflow.py` providers, `run.py` workflow wiring, deterministic delivery |
| `IMPL-SPEC-plugin-phases.md` | the 4 core changes (phases/workflows provider, wiring, deterministic delivery, edit lease) | `registry.py`, `contributors.py` (`surface`), `workflow_run.py`, `run.py` + their tests |
| `IMPL-SPEC-fact-routing.md` | fact-predicate edges + facts-only routing | `workflow.py` (`"fact"` edges), `workflow_run.py` (`_choose_edge`) + tests |
| `IMPL-SPEC-unit-close.md` | the per-unit `unit-close` hook + aggregate receipt | `run.py` (`_finish`), `workflow_run.py` + tests |
