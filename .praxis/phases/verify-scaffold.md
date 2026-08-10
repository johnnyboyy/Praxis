# Phase: verify-scaffold  (DRAFT — first-attempt-is-first-draft)

The verification step of the `test-scaffold` workflow: run **the specific scaffold tests** the
`scaffold-tests` phase produced against the `implement-feature` output, and decide pass or loop-back.
This is the router's verification role made an explicit workflow step — verification stays with the
router; the implementer's report is a claim.

**Entry condition:** an `implement-feature` unit inside a `test-scaffold` workflow has reported its
work done, with scaffold tests standing from the opening phase.

**Stance:** none — this is a mechanical run-and-decide, not a judgment composition.

**Invocations:** none of the engine's judgment is required to *run* tests. (The unit composes the
`testing` domain only so the router reads the results at the right layer — a green unit run does not
prove a runtime-observable surface works; see `runtime-verification-required-not-static-checks-alone`.)

## Deterministic facts — run first
- run the scaffold tests (and the project's broader suite) against the current tree.
- re-run on the *actual current state*, not a remembered prior green (`reverify-after-state-changes`).

## Artifact
A pass/fail verdict on the scaffold tests, and — on failure — a defect description handed to a
**fresh** `implement-feature` spawn (the loop-back), never back into the finished implementer.

## Surfaced / lacking
- **pass** → proceed to `triage-scaffold`.
- **fail** → loop back to `implement-feature` (fresh spawn) with the failing cases. Advisory at L1
  (the loop-back is declared in the workflow; L2 is where praxis enforces "verify failed → respawn").
- **repeated failure across N loops** → **stall**: the scaffold may be wrong or the design contested;
  surface it rather than looping indefinitely.
