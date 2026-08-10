---
subject: process
posture: guardrail
applies-when:
  - has-ui: yes
units-of-work: [route-work]
universal: false
---

# Domain: design-routing

Judgment about routing **design** work specifically — when to spawn a designer composition versus
surface a single decision, whether and how to defer a non-blocking UI/UX decision to the
`deferred-decisions` queue, and the lighter pattern-application path. The generic, engine-agnostic
routing judgment (framing, spawn-vs-surface thresholds, decomposition, model-tier, review discipline)
lives in the routing plugin's `routing` domain; this domain is the **design concern's** routing, so it
ships with the uiux plugin and composes for `route-work` only when `has-ui: yes`. `subject: process`,
not `design`, so it composes cleanly alongside `routing` for a routing unit — it is routing judgment
that happens to be about design work, not design judgment. Split out of `routing` on 2026-08-05 (t-06),
so a project that imports routing but not the design plugin no longer carries design-routing judgment
it can never use.

```yaml
last-retrospective: 2026-08-05

principles:

- id: defer-only-nonblocking-design-decisions
  rule: "Queue a UI or UX decision only when implementation can proceed with an explicit, narrow, reversible provisional treatment. Surface any blocking decision immediately."
  condition: "When considering whether to add a question to `.corpora/deferred-decisions.md`."
  reason: "Deferral is useful for batching small design questions, but a hidden blocker forces the coder either to make an unauthorized design decision or build on an assumption that may invalidate the work. A named reversible treatment makes the temporary state inspectable."

- id: batch-deferred-decisions-coherently
  rule: "Group deferred decisions by owning composition and related surface rather than count alone. Route a designer workstream when several items require coherent judgment, an item becomes blocking, provisional work risks material rework, or the operator requests review."
  condition: "When reviewing the active deferred-decision queue."
  reason: "A numeric threshold can bundle unrelated questions that gain nothing from shared context. Related questions amortize composition-load cost and let the designer resolve a surface coherently before temporary choices harden into implementation constraints."

- id: audit-request-means-spawn-designer
  rule: "When the operator uses the phrase 'full audit' or 'UI/UX audit', spawn a `ui-design`-composed spawn for a holistic review even if specific operator-stated concerns were also provided. Specific concerns are context for the audit, not a substitute for it."
  condition: "When the operator requests a full or holistic audit of a tool alongside specific known issues."
  reason: "A list of known problems is not an audit. An operator naming specific issues still benefits from a designer's fresh-eyes pass, which surfaces issues the operator didn't know to name."

- id: consult-libraries-before-scoping-ui-work
  rule: "Before scoping or briefing any unit that touches a UI surface, read the project's `ui-library.md`/`ux-library.md` sections covering the affected components and flows, and include the relevant sections in the implementation spawn's brief — extracted mechanically, byte-for-byte, never paraphrased by hand. Choosing WHICH sections are relevant is this routing judgment; the extraction and composition into the brief is process. A surface not yet in the library routes through a designer unit first (or an explicit deferred decision per defer-only-nonblocking-design-decisions), not straight to implementation."
  condition: "When routing, scoping, or writing the spawn brief for a unit whose targets include UI components, styling, or user-facing flows, before the brief is finalized."
  reason: "The libraries are the project's settled design state; an implementation spawn briefed without them re-derives or quietly contradicts decisions already ratified through design-decision-review. Delivering the relevant sections in the brief makes settled state binding at the point of use, while byte-for-byte extraction keeps curation honest — hand-summarizing a library section into a brief is exactly where compression and drift sneak in. The project-config spawn part names the full library paths, so a spawn whose scope outgrows its excerpt can read further; the excerpt sets the floor, not the ceiling."
  see-also: design-pattern-application-lighter-path, defer-only-nonblocking-design-decisions, plan-distills-library-into-tasks

- id: design-pattern-application-lighter-path
  rule: "When a design task is pattern-application — applying documented vocabulary from the UI or UX library to a new surface, with no genuine visual judgment under uncertainty — prefer the surface-to-operator path over a full designer spawn: read the library, identify the specific gaps, and surface them as targeted questions. Spawn only if the operator's answers reveal that actual design judgment is needed."
  condition: "When a queued task carries concern: visual or concern: interaction with judgment: settled, or when the process layer's own read of the task description and context reveals the library already settles the relevant decisions."
  reason: "A full designer spawn loads the stance frame, all composed domains, and runs the full ratify gate — 20k+ tokens. That cost is justified when there is genuine visual judgment under uncertainty. Applying established patterns to a new surface mostly isn't that: the useful output is which tokens go where, which the library already answers. The lighter path reaches the same place at a fraction of the cost."

killed:
```
