# Barrier — Lap A: voltage engine rebuild, TS-gated

## Goal
Rebuild the nodal voltage solver + voltmeter FRESH from the preserved source
(troubleshooting-mode@dda42fe), isolated (seeded worktree + tripwire), gated by a TS coverage-diff
adapter — dogfooding the rebuild-triple on real TypeScript. Plus the enabling TS gate machinery.

## TS gate adapter (enabling infra, in praxis)
- The rebuild coverage-diff verifier becomes LANGUAGE-AWARE. For TS: public-surface extraction via
  ts-morph / tsc (exported symbols + signatures); held-out tests via a configurable command
  (e.g. `pnpm exec vitest run <files>`); interface-presence check. Verdict = set-diff + exit code,
  from disk. Fixture-proven on a tiny TS package.
- Mutation adequacy for TS via a Stryker adapter (configurable; fixture/fake-proven, no hard dep in
  the praxis suite). Python path stays intact.

## The rebuild (in motors-and-controls, on feat/voltage-fault-mode)
- EXTRACT the voltage engine's behavioral contract from the preserved source -> IR
  { interface (solver + meter API), allowed_surface, tests: {spec, held_out} as Vitest tests }.
- SYNTHESIZE nodal-solve + voltmeter fresh against the IR in a seeded worktree; the synthesize agent
  is isolated from the preserved source (tripwire fails on any out-of-worktree read).
- COVERAGE-DIFF (TS adapter): held-out Vitest tests pass in the synth + public surface ⊆ allowed +
  every interface symbol present.
- INTEGRATE: thread nodePotentials into simulation/evaluate.ts + mount the meter UI.

## Acceptance
- TS coverage-diff adapter: passes a faithful TS synth; fails missing-symbol / smuggled-surface /
  failed-held-out (fixture-proven, from disk).
- Rebuilt engine: `pnpm test` green in circuit-builder; voltage-propagation + voltmeter behaviors
  pass; @vitest/coverage tooling present with a threshold.
- Tripwire clean: the synthesize agent did not read the preserved source.
