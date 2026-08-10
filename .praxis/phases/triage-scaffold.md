# Phase: triage-scaffold  (DRAFT — first-attempt-is-first-draft)

The teardown step of the `test-scaffold` workflow, and the reason the whole shape earns its keep:
with all scaffold tests visible at once and green, decide each one's fate — **promote** it to a kept
test, or **remove** it. This is the slot the workflow creates; the *decision* is the `testing`
domain's in-process judgment, run here at a clean checkpoint instead of scattered mid-implementation.

**Entry condition:** `verify-scaffold` passed inside a `test-scaffold` workflow — the scaffold tests
are green against the implemented behavior and ready to triage.

**Stance:** convergent — a bounded keep/remove decision per test, against a stated bar.

**Invocations:** the judgment engine composed for `triage-scaffold` (loads `testing` + universal).
The keep bar is the `testing` domain's, unchanged:
- **keep** a scaffold test only if it clears `unit-test-only-for-named-reasons` — (a) it regresses a
  specific bug found during this work, or (b) it covers genuinely intricate pure computation an
  end-to-end test can't pinpoint. Promote those (rename/relocate as a permanent regression test).
- otherwise **remove** it. A scaffold that merely re-asserts internal shape now built is exactly the
  standing refactor tax `unit-test-only-for-named-reasons` and `feature-level-test-by-default` warn
  against — its job (driving implementation) is done.
- where kept coverage is genuinely wanted for the new behavior, prefer replacing scaffold units with
  a **feature/end-to-end test** (`feature-level-test-by-default`) rather than keeping the drivers.

## Deterministic facts — run first
- the list of scaffold tests + their pinned-behavior notes from `scaffold-tests`.
- re-run the suite after any removal/promotion (`reverify-after-state-changes`).

## Artifact
A test suite carrying only kept tests (promoted regressions / intricate-pure units + any
feature-level tests written to replace scaffolds), with the throwaway drivers removed — and a one-line
triage record per scaffold (kept-because / removed) for the trace.

## Surfaced / lacking
- if a scaffold seems worth keeping but doesn't clear the bar → **tradeoffs-pending**: surface the
  judgment call rather than silently keeping it and re-incurring the refactor tax.
- a surfaced pattern ("this kind of scaffold keeps earning promotion") is candidate judgment for the
  `testing` domain — ratify it rather than re-deciding it every run.
