---
subject: coding
posture: guardrail
units-of-work: [scan-architecture]
universal: false
---

# Domain: architecture-health

Judgment about proactively scanning a managed project's codebase for architecture-deepening
opportunities — refactors that turn shallow modules into deep ones — independent of any specific
feature request. Distinct from `coding-general`'s implementation judgment, which governs how code
gets written once a change is already scoped; this governs where to look and what's worth
surfacing before any change is scoped at all. Seeded 2026-08-01 from reviewing mattpocock/skills'
improve-codebase-architecture skill, which named a capability corpora had no equivalent of.
Composed alongside `codebase-design`'s deep-module vocabulary (module, interface, depth, seam,
adapter, leverage, locality) wherever a candidate needs to be described — corpora does not yet
have its own formal equivalent (see `.corpora/queue.md`'s `not-yet-specified`, area
`architecture-health`, for that open thread). Audit metadata lives in `domains/audit.md`, loaded
only at ratify/retrospective time.

```yaml
last-retrospective: none

principles:

- id: scan-scope-by-recent-churn
  rule: "When no explicit direction (a module, subsystem, or pain point) is given for where to scan, weight the search toward the codebase's git-churn hot spots — the files and areas that recur most across recent commit history — rather than scanning indiscriminately across the whole codebase. If the changes are scattered with no clear hot spot, widen the net rather than picking arbitrarily."
  condition: "When starting an architecture-deepening scan and the operator hasn't already named where to look."
  reason: "Deepening a module pays off by making future changes to it easier — recent churn is the strongest available signal for where future changes are actually likely to land, so scanning there concentrates effort where it has the best chance of producing a candidate worth acting on, rather than spreading equal attention across code that may never be touched again."

- id: dont-relitigate-adr-without-real-friction
  rule: "When a deepening candidate would contradict an existing ADR, surface it only when the friction motivating the candidate is real and specific enough to justify reopening that decision — not merely because a theoretical refactor exists that the ADR forbids. Mark the conflict explicitly when it is surfaced."
  condition: "When a scan turns up a candidate whose recommended change contradicts a decision already recorded in an ADR."
  reason: "An ADR records a decision made for reasons that may not be visible from the code alone — surfacing every theoretical refactor an ADR forbids treats the ADR as if it were never decided, generating noise the operator has to re-litigate on every scan. Real, currently-felt friction is the signal that the original tradeoff may no longer hold; a candidate with no such friction is exactly the re-litigation ADRs exist to prevent, mirroring `domain-modeling`'s own ADR-sparingly criteria applied to consuming an ADR instead of creating one."

killed:
```
