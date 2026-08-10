---
subject: coding
posture: guardrail
units-of-work: [implement-feature, scan-architecture]
universal: false
---

# Domain: codebase-design

Shared vocabulary and judgment for designing deep modules: a lot of behaviour behind a small
interface, placed at a clean seam, testable through that interface. Seeded 2026-08-01, resolving
`nys-01` from the architecture-health capability's scratch queue — `architecture-health.md`
depended on this vocabulary informally (module, interface, depth, seam, adapter, leverage,
locality) without corpora having a formal home for it. Adapted from mattpocock/skills'
codebase-design skill, screened hard against `principle-judgment`'s genuine-fork test: most of that
source's content — the glossary itself, its Relationships section, and its "designing for
testability" list — doesn't fit `principles:` or `conventions:` at all, either because it's pure
definition with no decision in it, or because it reads as generic OOP-testability doctrine rather
than judgment earned anywhere. Only the Glossary below is carried in full, as reference — matching
`planning.md`'s own "Queue file schema" section, prose that documents rather than a principle that
decides. The `principles:` block holds only what actually cleared the fork test.

## Glossary

Use these terms exactly — don't substitute "component," "service," "API," or "boundary."

**Module** — anything with an interface and an implementation. Deliberately scale-agnostic: a
function, class, package, or tier-spanning slice. _Avoid_: unit, component, service.

**Interface** — everything a caller must know to use the module correctly: the type signature, but
also invariants, ordering constraints, error modes, required configuration, and performance
characteristics. _Avoid_: API, signature (too narrow — refers only to the type-level surface).

**Implementation** — what's inside a module, its body of code. Distinct from **Adapter**: a thing
can be a small adapter with a large implementation (a Postgres repo) or a large adapter with a
small implementation (an in-memory fake). Reach for "adapter" when the seam is the topic,
"implementation" otherwise.

**Depth** — leverage at the interface: the amount of behaviour a caller (or test) can exercise per
unit of interface they have to learn. A module is **deep** when a large amount of behaviour sits
behind a small interface, **shallow** when the interface is nearly as complex as the implementation.
Depth is measured at the interface only — a deep module can be internally composed of small,
mockable, swappable parts (internal seams, private to its own implementation and tests) without
that internal structure counting against its depth.

**Seam** _(Michael Feathers)_ — a place where you can alter behaviour without editing in that
place; the *location* at which a module's interface lives. Where to put the seam is its own design
decision, distinct from what goes behind it. _Avoid_: boundary (overloaded with DDD's bounded
context).

**Adapter** — a concrete thing that satisfies an interface at a seam. Describes *role* (what slot
it fills), not substance (what's inside).

**Leverage** — what callers get from depth: more capability per unit of interface they learn. One
implementation pays back across N call sites and M tests.

**Locality** — what maintainers get from depth: change, bugs, knowledge, and verification
concentrate in one place rather than spreading across callers. Fix once, fixed everywhere.

```yaml
last-retrospective: none

principles:

- id: deletion-test-for-suspected-shallow-module
  rule: "When a module is suspected of being shallow — a wrapper, a pass-through, an abstraction with no clear payoff — imagine deleting it. If the complexity it held simply vanishes, it was a pass-through and should go. If the complexity reappears at every caller that used it, it was earning its keep."
  condition: "When judging whether an existing or proposed module is worth keeping as a separate seam, distinct from inlining it into its caller(s)."
  reason: "A module can look justified by its existence alone — it has a name, a file, a test — without that presence proving it does anything its callers couldn't do as easily inline. The deletion test forces the question onto what actually happens to the complexity, not whether the module currently exists, which is the only reliable way to tell a real abstraction from a decorative one."

- id: interface-is-the-test-surface
  rule: "Test a module through its public interface, the same surface its real callers use — not by reaching past it into internals. If a test needs to reach past the interface to make an assertion, that's a signal the module's interface is the wrong shape, not a reason to test around it."
  condition: "When writing or reviewing a test for a module that already has, or is being designed with, a defined interface."
  reason: "A test that reaches past the interface couples to implementation details a caller never depends on, so it breaks on refactors that don't change real behavior and can pass while real behavior is broken. Treating a forced internal-reaching test as a design smell — rather than patching around it — routes the fix to where it actually belongs: the interface's shape, not the test's reach."

- id: two-adapters-before-a-real-seam
  rule: "Don't introduce a seam — an interface a caller must go through, with the abstraction cost that entails — until something actually varies across it. One adapter behind a seam is a hypothetical: the seam is speculative until a second, genuinely different adapter exists or is concretely imminent."
  condition: "When deciding whether to introduce an interface/seam ahead of a second implementation, versus writing directly against the one implementation that exists."
  reason: "A seam paid for before it's needed is speculative generality: it adds a layer of indirection, a name to learn, and a contract to maintain, all to serve variation that may never materialize. Waiting for the second adapter turns the seam's shape into an empirical question — what the two adapters actually have in common — rather than a guess made before any of the real variation is visible."

killed:
```
