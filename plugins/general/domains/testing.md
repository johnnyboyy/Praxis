---
id: testing
subject: coding
universal: false
applies-when: []
workflows: [tdd, build-verify]
---

principles:

- id: runtime-verification-required-not-static-checks-alone
  rule: "Passing lint/typecheck/build/test does not prove a code change with a runtime-observable surface actually works. Drive the real, rendered/running surface and observe the actual result before considering the work verified — never substitute re-running static checks or re-reading the diff."
  condition: "Any code change with a runtime-observable surface (not docs-only, types-only, or test-only) about to be reported complete — especially a refactor or consolidation pass that only reorganizes existing wiring (dependency reordering, hook consolidation, a mutation path rewired through a different call shape), which is exactly the class of change where static checks pass while the app breaks."
  reason: "Static checks verify shape and syntax, not behavior at runtime — a stale closure, a hook-execution-order change, a dropped dependency, or two independent module-graph instances of what should be one singleton are all invisible to typecheck/build/lint and only surface by actually exercising the path."

- id: probe-one-adversarial-case-beyond-happy-path
  rule: "When driving a real surface to verify a change, exercise at least one case beyond the primary intended flow — an error path, an edge input, a repeated action — not only the happy path."
  condition: "Any runtime verification pass on a change with a runtime-observable surface."
  reason: "The happy path is the path most likely to have already been exercised informally while building the feature. The adversarial/edge case is where an unverified assumption (an error state, a race, a boundary value) actually lives, and is disproportionately cheap to check while already driving the surface."

- id: feature-level-test-by-default
  rule: "Write tests for newly implemented user-facing behavior at the feature/end-to-end level by default — exercising the actual path a user or caller goes through, not the internal functions that implement it."
  condition: "A coder-composed spawn reaches its own terminal checkpoint on newly implemented user-facing behavior or a newly fixed bug."
  reason: "A feature-level test exercises the same integration points (routing, state wiring, the actual rendered/executed path) that a real usage would, and survives internal refactors that don't change observable behavior. A test written against internal functions instead couples to implementation shape that has no reason to stay fixed."

- id: unit-test-only-for-named-reasons
  rule: "Add a unit-level test only for one of two reasons, stated explicitly which applies: (a) it regresses a specific bug just found during this implementation pass, or (b) the logic is genuinely intricate pure computation where hitting every edge case through an end-to-end test would be slow and imprecise about which case broke. Never add unit tests as a general policy of covering every new function, argument, or branch touched."
  condition: "When deciding whether newly implemented logic needs a unit-level test in addition to (or instead of) feature-level coverage."
  reason: "A test that asserts on internal shape — an argument name, a helper's call signature, a mocked internal — raises the cost of the next harmless refactor without adding a proportionate signal. The two named exceptions are the cases where that cost is actually worth paying: a regression test pins down a real, previously-missed failure mode; intricate pure computation is genuinely hard to pinpoint a failing case for through an end-to-end test alone."

- id: test-shape-matches-what-a-lower-level-test-cannot-reproduce
  rule: "Choose a real, rendered/running-environment test for interactive-layer behavior that a lower-level or mocked test environment (a virtual DOM, a stubbed runtime) cannot faithfully reproduce — framework-internal registries, real layout/resize/focus behavior, an actual network or module-boundary interaction. Choose a component- or unit-level test only for logic genuinely reachable and representative without that real environment."
  condition: "When deciding what layer/shape of test to write for new behavior or to close a named coverage gap."
  reason: "A mocked or lower-level test environment approximates the real one; the approximation is exact for pure logic and unreliable for anything that depends on the real runtime's actual behavior. Choosing the lower-level shape for that second category produces a test that can pass while the real path is broken — the same failure mode runtime-verification-required-not-static-checks-alone names for verification, applied to test authoring itself."

- id: coverage-audit-by-layer-and-real-paths-not-location
  rule: "When assessing how well a test suite covers the application's actual behavior, inventory by the layer each test actually exercises (pure logic vs. the interactive/rendered layer) and check that against the real user-facing paths a person or caller actually takes — not by file location or test-runner category. Cite a concrete, dated instance of this project already having shipped a bug on a given path as stronger risk evidence than a hypothetical when prioritizing which gaps matter."
  condition: "When explicitly assessing test coverage (not routine test-writing alongside a feature, which feature-level-test-by-default already covers)."
  reason: "File location and test-runner category describe how tests are organized, not what they actually verify — two files in the same 'unit tests' folder can be exercising completely different layers of confidence. A dated, concrete prior incident is falsifiable evidence a hypothetical risk assessment isn't, and keeps prioritization from defaulting to whichever gap is easiest to imagine rather than the one that has actually bitten this project."

- id: wait-for-condition-not-arbitrary-delay
  rule: "When a test needs to wait for an async operation or eventual state change, poll for the actual condition it depends on rather than sleeping a guessed duration. Reserve a fixed delay for the rare case of testing timing behavior itself (a debounce or throttle interval), and state explicitly why the delay is needed when one is used."
  condition: "Writing or fixing a test that waits on asynchronous behavior or eventual state."
  reason: "An arbitrary delay encodes a guess about how long an operation takes on a given machine under a given load — it passes when the guess happens to be generous enough and fails intermittently otherwise, which is exactly the profile of a flaky test. Waiting on the condition itself ties the test's timing to the actual behavior instead of an assumption about it."

- id: watch-test-fail-before-implementing
  rule: "When adding a test for new behavior or a bug fix, write the test before the implementation and run it to confirm it fails for the expected reason — not a typo or setup error — before writing the code that makes it pass."
  condition: "Adding a test that doesn't yet have a passing implementation behind it — new behavior or a bug fix, not a test added after the fact for already-shipped behavior."
  reason: "A test written after the code it verifies, or never watched failing, hasn't been proven capable of catching the defect it claims to guard against — it may assert on the implementation you just wrote rather than the actual required behavior, and a test that passes on its first run provides no evidence either way."

- id: reverify-after-state-changes-not-from-memory
  rule: "Re-run verification (tests, build, typecheck) on the actual current state of the code before treating it as passing — a prior green run does not carry forward across a merge, rebase, or further edits."
  condition: "Before reporting work verified, complete, or ready-to-integrate, when the tree has changed (a merge, a rebase, additional edits) since verification last actually ran."
  reason: "A verification result is a claim about the exact tree it ran against — treating it as still true after the tree changes substitutes memory for evidence, the same gap runtime-verification-required-not-static-checks-alone names for static-vs-runtime checks, applied here to time instead of check type."

- id: scaffolding-tests-are-disposable-boundary-tests-survive
  rule: "Unit tests written only as a means to drive an implementation into existence are scaffolding; once a feature- or contract-level test guards the module's public boundary, delete the scaffolding. Keep the test that pins the boundary; discard the test that pins the internals."
  condition: "After an implementation pass where unit tests were written to reach a working implementation and a boundary/contract test now covers the observable behavior — especially before a later refactor or rebuild of that module's internals."
  reason: "An implementation-coupled test is an ATTRACTOR — during a rebuild it pulls the work back toward the current implementation because the test restates the implementation rather than the contract. Keeping only the boundary test leaves the internals genuinely free to change while the contract stays guarded. This is the same move as the rebuild triple (extract the contract as the spec, synthesize freely, coverage-diff against the contract, not the implementation). Relates to interface-is-the-test-surface (codebase-design domain) and unit-test-only-for-named-reasons (this domain)."

- id: golden-fixture-pins-reversible-transform-output
  rule: "Pin the exact serialized output of a reversible transform with a hard-coded golden fixture, alongside any round-trip assertion."
  condition: "Testing an encode/decode or serialize/parse pair whose forward and inverse directions share constants — keys, version bytes, character mappings, separators."
  reason: "A round-trip assertion (decode(encode(x)) == x) cannot detect a mutation to a shared constant, because both directions change together and the inverse still holds; only asserting the concrete serialized output catches it. This is why such a codec can hold high line coverage and a passing round-trip suite while mutation testing still finds surviving mutants in its shared constants."
