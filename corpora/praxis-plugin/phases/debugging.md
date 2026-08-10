# Phase: debugging

Investigating a bug, test failure, or unexpected behavior before proposing a fix. Migrated from
corpora `processes/debugging.md`, which is explicit that it is "mechanical — no composition, no
stance of its own": the four-step sequence is fixed, and every step's *judgment* lives in a corpora
domain (`debugging`), already loaded as part of the `debug-issue` composition. So this phase is thin:
it names the sequence and hands each step's judgment to the engine — praxis adds no deterministic
script here (there is nothing about reproducing or hypothesizing a bug that is a fact prior to
judgment; `root_tree` already told us which root the bug is in).

**Entry condition:** any bug, test failure, or unexpected behavior, before a fix is proposed or
applied. It is part of the `debug-issue` unit's own composition, not a separate opt-in.

**Stance:** none. The sequencing is mechanical; the judgment is the engine's.

**Invocations:** the judgment engine, composed once for `debug-issue` (which loads the `debugging`
domain). Praxis does not re-invoke per step — the domain judgment for all four steps is in that one
composition.

## Deterministic facts — run first

- `frame` (root + composition for `debug-issue`) — which root owns the failing surface, and the
  domain set that governs the investigation. A bug whose evidence spans two roots is, like any
  spanning task, a `decompose`: gather evidence at each boundary in its own root (this is exactly
  the domain's own "gather evidence at each component boundary" step, made structural by `frame`).

## The sequence (judgment per step is the engine's)

1. **Root cause investigation** — reproduce, read the full trace, check what changed; for a
   multi-component system gather evidence at each boundary before going deep on one component.
2. **Pattern analysis** — find a working analogue; if a reference implementation exists, read it in
   full and enumerate every difference rather than adapting a skim.
3. **Hypothesis and testing** — one specific hypothesis, the smallest change that tests it, verify
   before continuing; a failure reforms the hypothesis rather than stacking a second change. After
   three failed attempts sharing a pattern, stop and raise whether the architecture itself is sound.
4. **Implementation** — smallest failing test (or one-off reproduction) before the fix; fix at the
   root cause not the symptom; then validate at *every* layer the bad state passes through, not only
   the checkpoint the fix touched.

If at any point the actual cause is not clear, say so explicitly rather than proceeding on a
plausible guess.

**Artifact:** the fix, plus — in the handoff's `Artifact` section — what was actually investigated
and found: the hypothesis tested, the evidence, the fix and where it lands in the call chain, not a
pass/fail verdict.

**Surfaced/lacking:** an unresolved cause after the third failed same-pattern attempt is itself the
signal to surface (architecture may be unsound), not a fourth fix to attempt.
