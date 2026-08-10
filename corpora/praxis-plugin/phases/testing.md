# Phase: testing

One phase covering the three corpora test processes, because they are one composition
(`implement-feature`, the `testing` domain) differing only in *entry condition* and *what they touch*
— not three routes. Migrated from `processes/test-writing-at-implementation.md`,
`processes/test-coverage-audit.md`, and `processes/integration-test-implementation.md`. None yields a
praxis script: what to test, at what shape, and whether a path is adequately covered are all the
`testing` domain's judgment, already loaded — praxis only names which of the three modes an incoming
task is, from its entry condition.

**Entry condition:** one of the three mode entries below — a coder unit reaching its terminal
checkpoint on new behavior or a bugfix (write-at-implementation), an operator-requested coverage
audit (coverage-audit), or audit-identified paths ready to implement (integration-implementation).
Praxis names the mode from the incoming task; the composition is the same for all three.

**Stance:** none of its own (the composition is the ordinary `implement-feature` set; the `testing`
domain judges within it).

**Invocations:** the judgment engine, composed once for `implement-feature` — the same composition
for all three modes. Praxis does not compose a separate spawn for any of them; they are not separate
units of work.

## Deterministic facts — run first

- `frame` for `implement-feature` — the governing root and its composition (which includes the
  `testing` domain). The three modes share this exact composition; the fact that distinguishes them
  is the *entry condition*, below, not a different domain set.

## The three modes (distinct entry conditions, one composition)

- **write-at-implementation** — *entry:* a coder unit reaches its terminal checkpoint on newly
  implemented user-facing behavior or a newly fixed bug. Write a test at the feature/end-to-end level
  by default; add a unit test only for one of the two named reasons, stated explicitly; do not add
  unit tests as general proactive coverage. Run the project's verification before the checkpoint is
  reached.
- **coverage-audit** — *entry:* the operator asks how well the suite covers real behavior, OR a
  runtime-verification/debugging pass surfaced that a real bug shipped with no test that would have
  caught it. Inventory the suite by the layer it exercises (not by file location); enumerate the
  app's real user-facing paths; per gap, name the specific behavior, cite any dated shipped bug on
  that path, and propose a test shape. **Do not write the tests in this mode** — hand the list to the
  implementation mode; an audit that also implements skips the operator's prioritization.
- **integration-implementation** — *entry:* an audit (or an explicit operator request naming paths)
  has identified concrete candidate paths, and the task is to write and wire them up. Exercise each
  path the way it is actually reached (a real running environment where the audit flagged one);
  stand up test infrastructure if needed (a dependency-addition judgment call); run the full suite
  after each new test, not only at the end. Do not backfill unit tests for every function touched.

**Artifact:** the tests written (write/integration modes), or the gap list (audit mode), in the
handoff's `Artifact`.

**Surfaced/lacking:** write-mode surfaces any behavior not reasonably testable at feature level with
current infra (a future audit candidate). Audit-mode surfaces ambiguous risk/value calls and any
infrastructure gap that would block the candidates. Integration-mode surfaces any candidate
infeasible to test at its intended layer, and any flakiness in the new tests. Name them rather than
dropping them.
