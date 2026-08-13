---
id: behavioral-spec
subject: process
universal: false
workflows: [intake]
---

# Domain: behavioral-spec
#
# Judgment about defining the barrier a piece of work must satisfy — the observable behavior and the
# interface surface, stated so the contract survives any particular implementation. This is the
# planner's role in the extract step of the rebuild triple — produce the intermediate representation
# that says what must be true, drop the original, and let a fresh agent synthesize freely against the
# barrier alone. Governs how to write a contract that pins behavior without pinning internals, that a
# synthesizer can build against with nothing else locked in, and that the coverage-diff can later
# check both directions against. A good barrier is the one thing that must not move while everything
# behind it is free to.

principles:

- id: specify-behavior-and-interface-not-implementation
  rule: "State the contract as observable behavior and the interface surface — the inputs it accepts, the outputs and effects it must produce, the invariants it must hold — never the internal structure, algorithm, or data layout that would produce them. If a line of the spec would still have to be true after a total rewrite of the internals, it belongs in the barrier; if a rewrite could falsify it without changing any observable result, it does not."
  condition: "When authoring the barrier for a unit of work, whether a fresh capability or a rebuild of existing code."
  reason: "A barrier that names internals couples the contract to one implementation, so the synthesizer inherits the very structure the extract step exists to shed. Behavior and interface are what a caller actually depends on; everything else is a private decision the synthesizer must be left free to make, or the rebuild is not a rebuild — it is a transcription."

- id: barrier-must-survive-implementation-drift
  rule: "Write each clause of the barrier so it stays true across implementation changes that leave behavior intact. Prefer stating a required outcome or invariant over a required mechanism, and quantify observable properties (what is returned, what is persisted, what error is raised) rather than describing the steps that get there."
  condition: "When phrasing any individual clause of a behavioral contract."
  reason: "The barrier's whole value is that it is the fixed point while the implementation is the variable — a clause that breaks the moment an internal detail changes is an attractor pulling the synthesizer back toward the old shape, exactly what dropping the original was meant to escape. A clause pinned to observable outcome only fails when behavior actually regresses, which is the only failure the barrier should be able to signal."

- id: barrier-is-what-a-fresh-agent-can-synthesize-against
  rule: "Test the barrier by asking whether a fresh agent, given only this contract and no access to the original or any surrounding context, could build a correct implementation from it. If synthesis would require guessing at unstated behavior, reading the old code, or asking a clarifying question the spec should have answered, the barrier is incomplete — close the gap before the extract step is done."
  condition: "When judging whether a behavioral contract is finished and ready to hand to a synthesize step."
  reason: "The synthesize step runs against the spec alone with the original deliberately dropped, so anything the barrier leaves implicit is not filled in from the original — it is filled in by guess, or it stalls. Completeness measured against a context-free reader is the honest test, because that is exactly the reader the rebuild triple creates. A barrier that only makes sense to someone who has already seen the implementation has smuggled the original back in."

- id: for-code-the-barrier-is-the-test-contract
  rule: "When the work is code, express the barrier as the acceptance or test contract — the executable checks a correct implementation must pass — not as prose description alone. Name the cases the tests must cover: the primary behavior, the interface's boundaries, and at least one adversarial or error path, so the contract is something a synthesizer can run against rather than only read."
  condition: "When the unit of work behind the barrier is code with a runtime-observable surface."
  reason: "Prose describes intent but cannot be executed, so a synthesizer cannot mechanically tell whether it has met a prose barrier. An executable acceptance contract turns the barrier into a runnable target: the synthesizer builds until it passes, and the coverage-diff has a concrete artifact to check completeness against. This is the same discipline as testing a module through its public interface — the contract lives at the surface callers use, not against internals."

- id: barrier-is-the-coverage-diff-target
  rule: "Author the barrier as the thing the coverage-diff will measure against in both directions — losslessness (does the rebuilt work still satisfy every clause the original's behavior implied?) and completeness (does it meet the spec that was asked for?). Make each clause discrete and checkable enough that a later diff can point at exactly which behaviors are covered and which are missing."
  condition: "When structuring the barrier, given that a coverage-diff step will later compare the synthesized artifact against it."
  reason: "Coverage-diff is the compensating control the extract edge pays for having dropped the original — it can only catch a lost behavior if that behavior was written down as a discrete clause to check. A barrier stated as one undifferentiated paragraph gives the diff nothing to enumerate, so a dropped behavior passes silently. Discrete, checkable clauses are what make the two-direction diff able to name a specific gap instead of a vague sense that something changed."
