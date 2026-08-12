---
id: debugging
subject: coding
universal: false
applies-when: []
workflows: [debug]
---

principles:

- id: root-cause-before-fix
  rule: "Complete root-cause investigation — reproduce the issue, read the full error or stack trace, check what recently changed, and for a multi-component system gather evidence at each component boundary — before proposing or applying any fix."
  condition: "Any bug, test failure, unexpected behavior, or build/integration failure, including under time pressure, when a fix looks obvious, or after a previous fix has already failed."
  reason: "A fix aimed at a guessed cause tends to land on a symptom rather than the actual defect — the surface appears to work while the underlying issue keeps producing new symptoms elsewhere. Investigation is disproportionately cheap relative to the cost of an unresolved defect recurring downstream, and the evidence gathered here is also what makes a hypothesis testable in the first place."

- id: fix-at-source-not-symptom
  rule: "Trace a bug backward through the call chain to the value or decision that originally introduced it, and fix there. Do not fix only at the point where the error surfaced."
  condition: "The bug's error or symptom appears at a point in the code distinct from where the invalid state or decision actually originated."
  reason: "The point where an error surfaces is often several calls removed from where the bad value was produced — a fix applied at the surface point suppresses the visible symptom while the same root defect stays free to produce a different symptom elsewhere."

- id: single-hypothesis-minimal-test-reform-on-failure
  rule: "Form one specific, stated hypothesis about the root cause and make the smallest possible change to test it — one variable at a time, never several candidate fixes bundled together. If the change does not resolve the issue, form a new hypothesis from what the failed attempt revealed rather than adding another change on top of the unresolved one."
  condition: "Testing a hypothesis about a bug's root cause, including immediately after a prior attempt has failed to resolve it."
  reason: "A bundled set of changes that happens to resolve the symptom leaves it unknown which change actually mattered, and the untested changes remain in the codebase as unexplained modifications. Stacking a second fix on an unresolved first compounds this: a failed fix is itself evidence, and conflating it with a second untested change destroys the ability to attribute cause when something later works or continues not to."

- id: repeated-fix-failure-questions-architecture
  rule: "When three or more fix attempts on the same issue have failed and each attempt revealed a new instance of the same problem, or new shared state or coupling, in a different location, stop attempting further fixes and raise whether the underlying pattern or architecture is sound instead of attempting another fix."
  condition: "Three or more fix attempts have failed on the same issue, and the failures share a pattern — a new symptom in a new location, a growing scope of required change — rather than being unrelated misses."
  reason: "A repeated fix-reveals-new-symptom-elsewhere pattern is evidence the issue isn't a local defect at all but a structural property of the design. Continuing to patch symptoms under that condition trades increasing effort for decreasing signal, while the actual decision — whether to change the architecture or pattern — needs to be evaluated on its own rather than stumbled into as fix attempt four."

- id: compare-against-complete-reference
  rule: "When implementing against a known-working pattern or reference implementation, read it in full and enumerate every difference between the reference and the broken code before adapting it — do not assume a given difference doesn't matter without checking."
  condition: "A working example or reference implementation exists for the pattern being debugged or applied."
  reason: "A partially-read reference produces an adaptation built on an incomplete model of the pattern, and the unread part is exactly where an untested assumption is most likely to be wrong, because it's the part that was never checked against the broken case."

- id: state-uncertainty-instead-of-plausible-guess
  rule: "When investigation has not produced a clear, verified understanding of the cause, state that explicitly rather than proceeding with a plausible-sounding fix presented as if it were confirmed."
  condition: "At any point during root-cause investigation or hypothesis testing where the actual mechanism remains unclear."
  reason: "A fix built on a plausible-sounding but unverified explanation carries the same risk as guessing while reading as confident — the gap between 'sounds right' and 'verified' is exactly where symptom fixes originate. Naming the uncertainty directly keeps what's actually known separate from what's assumed."

- id: reproduce-as-failing-test-before-fixing
  rule: "Before implementing a fix, create the smallest failing test — or a one-off reproduction script if no test framework applies to the case — that reproduces the issue."
  condition: "A root cause has been identified and a fix is about to be implemented."
  reason: "A reproduction created before the fix is the only evidence afterward that the fix actually addressed the issue rather than coincidentally changing behavior — the same evidence discipline testing's runtime-verification-required-not-static-checks-alone requires for feature work, applied here to the bug/fix cycle itself."

- id: validate-at-every-layer-after-root-cause
  rule: "Once the root cause is found and fixed at its source, add validation at every layer the invalid data or state actually passes through on its way to the failure point, not only at the one checkpoint the fix touches."
  condition: "A root-cause fix has been implemented for a bug caused by invalid data, state, or an unexpected code path reaching a place it shouldn't."
  reason: "A single validation point can be bypassed by a different code path, a refactor, or a mock that doesn't go through it — a bug fixed at one checkpoint stays reproducible through any path that skips that checkpoint. Validating at every layer the bad value actually crosses makes the failure mode structurally unreachable rather than merely blocked at the one point it was last observed."
