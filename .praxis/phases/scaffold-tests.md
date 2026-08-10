# Phase: scaffold-tests  (DRAFT — first-attempt-is-first-draft)

The opening phase of the `test-scaffold` workflow. Stand up **throwaway driver tests** that pin the
specific behavior the next `implement-feature` unit must produce, so implementation has a concrete
target to turn green. These are scaffolding, not coverage: they are created to be *triaged* at the
end of the workflow (`triage-scaffold`), where each is either promoted to a kept test or removed.

This is a PROCESS phase — the *shape* of the work (create → implement → verify → triage → teardown)
is praxis's; the judgment about what/at-what-layer to write, and what is worth keeping, stays the
`testing` domain's, composed into this unit.

**Entry condition:** the operator (or planner) routes a unit through the `test-scaffold` workflow —
a change where writing the target behavior as a failing test first is worth the round trip (a bug fix
with a reproducible failure, a feature with a crisp acceptance check). Not for exploratory/divergent
work where the behavior isn't yet pinned.

**Stance:** convergent — the target behavior is being pinned, not explored.

**Invocations:** the judgment engine composed for `scaffold-tests` (loads `testing` + `coding-general`
+ universal). The `testing` domain governs test shape: pin the behavior at the layer a lower-level
test can't fake, prefer the real path, and *watch each scaffold fail for the right reason before
implementation* (`watch-test-fail-before-implementing`).

## Deterministic facts — run first
- `frame` / `preframe` for the governing root and composition.
- the project's test command (from `.corpora/config.md` verification commands, if declared).

## Artifact
A set of failing tests that pin the target behavior, each confirmed to fail for the intended reason —
explicitly marked/understood as **scaffold** (temporary drivers), plus a one-line note per test of the
behavior it pins, carried forward for `triage-scaffold`.

## Surfaced / lacking
- if the behavior can't be pinned as a test without first making a design decision → **stall**
  (`questions-pending` / `tradeoffs-pending`): surface it; the scaffold can't precede the decision.
- if a scaffold passes on first run → it isn't pinning new behavior; drop or rewrite it.

> Loop note (advisory at L1): the workflow's `verify-scaffold → implement-feature` loop-back is
> declared, not enforced, until praxis owns the session loop (L2). Follow it by routing a failed
> verify to a *fresh* implement spawn, never back into a finished one.
