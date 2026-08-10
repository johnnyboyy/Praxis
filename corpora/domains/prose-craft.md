---
subject: process
posture: guardrail
universal: true
---

# Domain: prose-craft

Judgment about the economy and legibility of prose corpora itself produces — task descriptions,
specs, handoff artifacts, domain principles, questions, proposals — independent of the subject
matter that prose is about. Distinct from `principle-judgment`, which governs whether a candidate
is genuine judgment at all; this governs how the prose stating an already-earned decision, or any
other corpora-authored text, is actually written once there's something to say. Universal because
a spawn is close to always producing prose of some kind — a task, a proposal, a question, a
handoff — regardless of stance or subject.

```yaml
last-retrospective: none

principles:

- id: prefer-leading-word-over-restated-phrasing
  rule: "When a piece of corpora-authored prose repeatedly restates the same qualifying idea in different phrasing across multiple places, name it once as a compact term and reuse that term going forward, rather than re-explaining the idea long-form each time it recurs."
  condition: "When writing or refining any corpora-authored prose — a principle, a task description, a spec, a handoff — that re-derives a concept already stated elsewhere in the same artifact or domain, in different words."
  reason: "Every restatement costs the same context-load tokens as the first without adding new judgment. A named, consistently-reused term is cheaper to load and easier to reach for than re-deriving the same qualifying clause each time it recurs."

killed:
```
