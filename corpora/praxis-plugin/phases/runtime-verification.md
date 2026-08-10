# Phase: runtime-verification

Drive a real, running surface and observe the actual result before a coder-composed unit with
runtime-observable output can be called complete. Migrated from corpora
`processes/runtime-verification.md` — "no composition, no stance; driving the app and observing what
happens needs no design or code judgment of its own." The judgment is the `testing` domain's
(`runtime-verification-required-not-static-checks-alone`,
`probe-one-adversarial-case-beyond-happy-path`), already loaded in the unit's own `implement-feature`
composition. No praxis script: whether a surface is *runtime-observable* is a judgment the domain
makes, and how to drive it is project-tooling-specific, not a fact praxis computes.

**Entry condition:** a coder-composed unit's work includes a runtime-observable surface (not
docs-only, types-only, or test-only) and is about to reach its terminal checkpoint. Required, not
suggested — it is part of what "the unit's work is done" means, not a separate step.

**Stance:** none. Mechanical driving; the judgment is the engine's.

**Invocations:** none of its own — it runs inside the unit's existing `implement-feature`
composition, which already carries the `testing` judgment. This phase names *when* that judgment
binds (at the terminal checkpoint of a runtime-observable unit).

## Deterministic facts — run first

- none beyond the unit's own `frame`. There is no fact prior to judgment here to script; the phase
  is a discipline applied at a checkpoint, not a fact bundle.

## Procedure

1. Use this project's `verify` skill (or a project-specific verifier) if one exists; otherwise drive
   the surface directly with whatever tooling the project actually has.
2. Drive the **real** surface — not import-and-call, not re-running tests or typecheck. For a change
   that only reorganizes wiring (a refactor, a rewired mutation), exercise every interaction path
   whose call site or dependency ordering changed, not only the nominal point of the change.
3. Probe at least one adversarial or edge case beyond the happy path.
4. Report what was actually observed in the handoff's `Artifact` — the steps taken and what happened
   at each, not a pass/fail verdict.

**Artifact:** the observation record in the handoff's `Artifact` section.

**Surfaced/lacking:** if no way to drive the real surface is available this session (no browser
automation, no reachable runtime), say so explicitly in the handoff's `Surfaced` section rather than
reporting the work complete on static tooling alone.
