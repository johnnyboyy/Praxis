---
subject: design
posture: guardrail
applies-when:
  - has-ui: yes
units-of-work: [design-ux-flow, design-ui-surface, bootstrap-ui-surface, bootstrap-ux-surface]
universal: false
---

# Domain: design-method

Design *process and discipline* — the clarity/polish priority and documentation rules. A
**convergent** body of correctness guardrails: the anti-mean *stance* is deliberately **not** here —
it is a generative stance, not a principle, and lives on the divergent stance itself (see
`kernel.md`, "Generative stance"); mixing it in was the worked example of the stance hard line.
Loaded by both a UX-composed spawn (`wizards-flows`, `ranking-evaluation`, `validation-feedback`,
`recoverability`, `lists-selection`, `forms-inputs`, convergent) and a UI-composed spawn (`color`,
`surfaces-elevation`, `visual-hierarchy`, `motion`, `validation-feedback`, `recoverability`,
`lists-selection`, `forms-inputs`, divergent). Audit metadata lives in `domains/audit.md`, loaded
only at ratify/retrospective time.

A design spec is iterated on a scale — awful → bad → good → great → perfect — rather than judged
pass/fail. Target great; perfect is aspirational, not a bar every spec must clear before shipping.

Read the project's UI or UX library first — authoritative for current visual character and
experience patterns respectively; do not re-derive either from code or screenshots. If the relevant
library doesn't exist yet, the project needs the founding `bootstrap-ui`/`bootstrap-ux` pass first,
not ongoing design work.

A UX-composed spawn's output is a user flow spec: current experience, proposed flow per step (what's
seen, actions available, system response, error/empty/edge cases), clarity requirements. Describe
what the user perceives and does — never visual layout, styling, colors, or typography; that is a
UI-composed spawn's job. Most proposals are `kind: judgment`; a genuine direction question
mid-work is `status: questions-pending`, never a silent assumption.

A UI-composed spawn's output is a design spec: current state, proposed design per UI state
(elements, layout, hierarchy, interaction behavior, empty/loading/selected/error states). Describe
proportions in relative terms — no pixel values, no CSS class names, no component names;
implementation is not this spawn's concern. Ground visual decisions in a UX flow spec when one was
provided. This output is an identity choice, not a weighable rule — it is never a `proposals:`
entry; it goes in `Artifact` and is reviewed through the design plugin's `design-decision-review` phase
(`kernel.md`, "Design decision review"), entirely separate from the ratify gate. Name every screen
a spec changes in `ui-drift.screens` and every shared component it changes in
`ui-drift.components`. `proposals:` is reserved for genuine judgment (rarely knowledge) the session
also surfaced — a real tradeoff whose reason will bind future weighing, distinct from the identity
choice itself.

```yaml
last-retrospective: 2026-06-20

principles:

- id: clarity-over-polish
  rule: "When there is tension between what feels polished and what is immediately clear, prefer clarity. A user must know what to do and how to do it upon seeing any screen — without reading instructions."
  condition: "Any UX decision where aesthetic sophistication and immediate comprehension pull in different directions."
  reason: "Polish optimizes for the observer's impression; clarity optimizes for the user's success. The product's job is the latter."

- id: document-visual-sub-systems
  rule: "When a surface develops a distinct visual language, mark it in the project's design system documentation. How much to document scales with complexity: a self-contained surface unlikely to spawn new design questions gets a boundary note (one paragraph). A surface actively growing or sharing components gets fuller treatment."
  condition: "When a page or section accumulates 3+ design decisions that diverge from the main design system."
  reason: "Undocumented sub-systems let future design work accidentally import the wrong conventions. But over-documenting self-contained surfaces creates a second source of truth that drifts from the code."

- id: documentation-before-screenshots
  rule: "Consult the screenshot cache (`.corpora/screenshots/manifest.md`) freely for orientation and reuse-discovery — reading it costs nothing new. Reach for the browser automation tool for a fresh capture only when the cache is missing or stale for a screen you need, or to verify aesthetic quality the text documentation can't fully characterize. Documented specification remains the default source of truth for exact values."
  condition: "Any time visual information about the current product is needed during a design task."
  reason: "Reading cached images is normal now — the cache already paid its capture cost at handoff time, so re-reading it is free. Live capture stays the exception: it still repeats the token cost the design system documentation exists to avoid, and shows a snapshot rather than documented intent."

- id: check-existing-patterns-before-specifying-new
  rule: "Before specifying a new flow pattern, navigation convention, or UI component, check the project's UX/UI library and existing component documentation for one that already covers the need."
  condition: "Any design spec that introduces a flow step, interaction pattern, or visual component not already named in the project's library documentation."
  reason: "A design spec is read downstream and implemented as written. Specifying a near-duplicate of an existing pattern creates two conventions where one would do, and the implementer has no way to know a simpler existing option was available — the check has to happen at design time, not implementation time."

- id: plan-distills-library-into-tasks
  rule: "When a design or planning unit produces task files a separate execution spawn will implement, quote the relevant library content into each task — the specific components, tokens, and patterns by name, with the governing excerpt — so the task is self-contained. The execution spawn reads its task file, not ui-library.md/ux-library.md; a task that would force its executor to open the library wholesale is not yet done being planned."
  condition: "Any planning or design unit whose artifact is a task file (or task list) handed to a separate implementation spawn — applied when writing each task, and again when reviewing the task set before handoff."
  reason: "The library's read cost is paid once at planning time, where the whole document genuinely informs decomposition. Left undistilled, every execution spawn re-pays that cost — and an executor reading the full library 'to be safe' dilutes attention across mostly-irrelevant patterns exactly where convergent focus matters. The plan is the only point that knows which slice each task needs; distilling there is cheap, and impossible to recover later."
  see-also: check-existing-patterns-before-specifying-new, consult-libraries-before-scoping-ui-work

killed:
```
