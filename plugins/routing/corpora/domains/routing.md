---
subject: process
posture: guardrail
units-of-work: [route-work]
universal: false
---

# Domain: routing

Judgment about routing, spawning, and relay — which composition handles a task, when to spawn vs. surface
vs. defer, and session/workstream continuity. **Engine- and concern-agnostic:** this is praxis's own
routing judgment, so it names no concern's artifacts. Routing judgment specific to *design* work —
spawning a designer, the design `deferred-decisions` queue, UI/UX audits, the UI/UX library — split
out to the uiux plugin's `design-routing` domain on 2026-08-05 (t-06) and composes for `route-work`
only when the design plugin is imported. Assembly and gate-processing mechanics live in `ratify-gate`
— split out 2026-07-18, see `LINEAGE.md`, "The ratify-gate split." Audit metadata lives in
`domains/audit.md`, loaded only at ratify/retrospective time.

```yaml
last-retrospective: 2026-07-18

principles:

- id: brief-ends-at-what
  rule: "The coder brief ends where 'how to build it' begins. Include the approved design spec in full; do not pre-solve implementation details."
  condition: "When writing a task brief for the coder composition."
  reason: "Pre-solving implementation in the brief does the coder's domain work for it, bypasses the pushback mechanism, and produces over-specified prompts. The coder's judgment — including whether the spec is implementable and at what cost — only fires if it receives a what, not a how."

- id: stop-and-route
  rule: "When the process layer finds itself making visual, UX, or code-level decisions inline, stop and route to the appropriate composition instead."
  condition: "Any time the process layer is doing domain work — design critique, layout decisions, code review, UX judgment — rather than routing."
  reason: "The process layer's value is in routing and relay, not domain execution. Inline domain work bypasses the corpus system — no principles surface, no judgment accumulates."

- id: frame-before-routing
  rule: "Before routing, frame what each composition is being asked to answer, not which pipeline to follow. If that framing reveals ambiguity, ask one clarifying question before spawning rather than routing on assumptions."
  condition: "Any task entering the corpora system, especially ambiguous or multi-domain requests."
  reason: "Routing judgment is about matching questions to the composition that owns them, not following a sequence. Explicit framing creates a check on whether the scope is clean before any subagent work begins."

- id: route-questions-not-roles
  rule: "Route a question to the composition that owns its judgment, not to the operator by default. If non-blocking, queue it to that composition's own queue for resolution at its next natural spawn — including questions raised by a different composition's session, not only its own self-deferrals. If blocking and that judgment is needed now, spawn or resume that composition; a live spawn that hits a genuine question mid-work can pause (`questions-pending`) and resume once answered. Surface to the operator directly only when neither path fits."
  condition: "Any time a question surfaces during work that a particular composition owns — from the operator, another session, or a spawned composition's output."
  reason: "Operator-surfacing became the default when spawned agents were one-shot (no resume) and a full spawn was expensive relative to one decision — asking the operator was the only cheap path. Neither constraint holds now: a spawn can pause on a genuine question and resume with the answer, and a non-blocking question can wait in the owning composition's queue for its next natural spawn instead of forcing an immediate round-trip. The operator is the fallback when neither path fits, not the first resort. (A concern's own queue and its threshold for spawning live with that concern; this is the general routing rule.)"

- id: spawn-threshold-is-spec-scope
  rule: "Spawn a composition when the task requires generating a full spec — a new feature, a redesign, a unit with several interdependent decisions. Surface to the operator instead when the question is a single decision point that can be answered in one exchange. When in doubt, surface first; spawn only if the operator's answer reveals that a full spec is needed."
  condition: "When deciding whether to spawn a composition to produce a spec vs. surface a single question to the operator."
  reason: "A full workstream carries substantial composition, domain, and review cost. A single direction question is often cheaper for the operator to resolve directly; a full spec earns the isolated spawn's context because several related decisions need coherent judgment. (The threshold is general to any composition; a concern that has a lighter-weight instance of it carries that instance itself.)"

- id: planner-over-brainstorming-for-scope
  rule: "When ambiguous scope surfaces in a corpora-managed project, route to the planner rather than reaching for the brainstorming skill."
  condition: "Any time the process layer (or an inline session) would otherwise invoke superpowers:brainstorming to resolve what a request decomposes into."
  reason: "Brainstorming's dialogue is valuable but produces no corpus artifact — no queue, no ratify gate, no planning-domain growth. The planner does the same ambiguity-resolving dialogue and captures the result as accumulated judgment, growing the very corpus this system depends on."

- id: persist-role-by-workstream
  rule: "Resume the spawn that owns an active workstream for questions, operator testing feedback, and revisions. Start a new workstream when the operator supplies a new plan, requests an unrelated outcome, the composition changes, or accumulated context makes continuation unsafe. Treat a handoff as a checkpoint, not automatic termination."
  condition: "When routing follow-up work after a spawn has returned a handoff."
  reason: "Small revisions benefit from the spawn's live understanding of the implementation and prior decisions. Replacing it at every handoff discards useful context, while carrying it into a new planned outcome risks reviving settled or rejected work through pattern matching."

- id: inline-coder-session-protocol
  rule: "Inline/informal coder work carries the same corpus discipline as a formal isolated spawn — compose the full coder composition before starting (see SKILL.md, 'For inline spawn work'), not a lighter version because it's inline. Flag interesting decisions as potential principles as they happen; ask 'any of these worth encoding?' at the natural seam (feature complete, direction approved, conversation shifts away from code) — not deferred to end of session, since decisions evaporate if not captured at the moment they're made."
  condition: "Any inline coding work in the process layer session — small tasks, experiments, pair-programming — where spawning a coder subagent would cost more than the isolation is worth."
  reason: "Corpus loading must happen before constraints are applied, same as a formal spawn — the 'inline' framing tempts skipping that because there's no separate spawn boundary to enforce it. In-flight flagging prevents decisions from evaporating in a long session. Binding the principles question to the natural seam rather than a formal spawn-exit event makes the check structural rather than optional."

- id: decompose-large-tasks-before-spawning
  rule: "When a task's scope spans many independent workstreams, decide their ownership in the process layer. Within one assigned workstream and stance, allow the owning spawn to create autonomous scope-bounded workers."
  condition: "When routing a task whose scope spans many independent files or units."
  reason: "Workstream boundaries affect routing, workstream ownership, and operator visibility, so they belong to the process layer. Local execution decomposition does not change ownership and is cheaper for the spawn closest to the work to manage."

- id: no-cost-driven-domain-omission
  rule: "Once routing judgment has determined a domain is relevant to a task, never drop it from the composition to save tokens or shorten the context. If total composition cost is a genuine concern, surface it as a tradeoff — decompose the task into smaller checkpointed spawns, or flag the cost to the operator — rather than silently thinning the domain set a relevant task would otherwise load."
  condition: "When composing domains for a spawn and the total token cost of the composed set is a concern."
  reason: "Observed in practice: cutting a relevant domain for cost produces worse output and dropped principles, the same attention-fighting failure as an oversized context. The honest move is to make the cost tradeoff visible — split the work or flag it — never to omit unilaterally."

- id: spawn-only-when-judgment-remains
  rule: "Before spawning an isolated composition, check whether the task brief already resolves every content decision — exact before/after state, no open questions. If so, execute directly instead of spawning; do not write a more detailed brief in place of acting."
  condition: "Any time about to spawn an isolated subagent for a task whose brief already specifies exact edits, verbatim text, or a fully-determined outcome, with no perceptual/aesthetic judgment, large unread context, or evaluator-independence need remaining downstream."
  reason: "Isolation cost — composing the full domain prompt, the spawn's own execution, and reviewing its handoff — buys nothing when no judgment, context-discovery, or independent evaluation is actually needed; the spawn's job degrades to pure text transcription. This is the inverse of stop-and-route: that principle guards against the process layer doing domain judgment itself, this one guards against over-resolving a brief until it reads like a diff and still paying for isolation as if judgment remained."
  see-also: stop-and-route, spawn-threshold-is-spec-scope

- id: concern-class-diversity-triggers-decomposition
  rule: "When filing or routing a coding task, check whether its scope bundles two or more of: core algorithmic/model-logic design, integration plumbing across many call sites (registering a new type/field with every consumer), and content or data correctness verification against external reference material. Decompose along those lines by default, even under one nominal feature, unless the pieces are a genuinely unavoidable single prerequisite for each other."
  condition: "Filing or reviewing a task whose description names work spanning more than one of those judgment classes."
  reason: "A task can touch many files within one judgment class (e.g. plumbing) cheaply, or few files across several classes expensively — judgment-class diversity, not file count, is the actual cost driver, so file count alone (`decompose-large-tasks-before-spawning`'s existing trigger) can miss a task that is actually oversized. Bundling unrelated judgment classes into one task also forces whoever reviews it to hold all of them in mind at once, which is itself a review-quality cost independent of execution cost."
  see-also: decompose-large-tasks-before-spawning

- id: parallel-dispatch-requires-verified-independence
  rule: "Dispatch multiple isolated agents in parallel only for problems verified independent — no shared state, no fix-one-might-fix-others risk — issuing all dispatches in the same turn. Never dispatch more than one implementation agent in parallel against the same working tree or branch, even when the underlying tasks are logically independent. After parallel agents return, check their changes for conflicts before treating the batch as integrated."
  condition: "Facing 2+ ostensibly separate failures, subsystems, or problems that could plausibly be delegated to concurrent agents, or deciding how to sequence multiple implementation tasks against the same codebase."
  reason: "Two failures that look separate can still share a root cause or touch the same state — dispatching independently risks conflicting fixes that only surface at integration. Implementation agents carry a sharper version of the same risk: even logically independent tasks write to the same working tree, so parallel implementation dispatch risks colliding edits regardless of task independence — investigation and review agents don't carry this risk because they only read."

- id: model-tier-by-task-complexity
  rule: "When dispatching an isolated spawn, choose the model tier by the judgment the task actually requires — a fast/cheap model for mechanical work with a complete, unambiguous spec touching few files; a standard model for multi-file integration or pattern-matching; the most capable model for architecture, design, or broad-context judgment calls. Specify the model explicitly — an unset model silently inherits the process layer's own tier for every spawn."
  condition: "Dispatching any isolated spawn where the platform supports selecting a model tier."
  reason: "Turn count, not just per-token price, drives real cost — a cheap model given work past its judgment ceiling routinely takes several times as many turns to converge, which can cost more overall than a single pass on a stronger model. Leaving the model unset defaults every spawn to the process layer's own tier regardless of what the task needs, silently paying the most expensive rate for mechanical work."

- id: verification-stays-with-orchestrator
  rule: "When work is delegated to implementer agents, verification stays with the orchestrator: implementers deliver code and report status, and the orchestrator — or a dedicated verification pass it runs after the implementation units — re-runs the suites and drives the observable behavior itself, never accepting an implementer's own report as the evidence. Defects found route to a fresh spawn, not back into the finished implementer's context."
  condition: "A parent agent dispatches implementation to one or more spawned agents and is deciding what to verify, and when, before integrating the results."
  reason: "An implementer's completion report is a claim by the party with the strongest incentive to believe it — and the cheaper the implementing model, the weaker that claim, while the orchestrator's re-run costs the same regardless."
  see-also: parallel-dispatch-requires-verified-independence, model-tier-by-task-complexity

- id: bounded-fix-loop-then-forced-disposition
  rule: "Cap fix-then-review rounds on the same finding at a small fixed number. Before hitting the cap, escalate — a fresh agent, a higher-capability model tier, or both — rather than resuming the same agent at the same capability again. At the cap, stop looping and explicitly dispose of every still-open finding: fixed, or ruled on with the ruling recorded — never left implicitly abandoned by simply moving on."
  condition: "A fix-then-review loop on the same finding(s) has not converged after multiple rounds."
  reason: "An uncapped loop risks silently consuming unbounded effort on a stall that repeated attempts at the same capability won't break — escalating capability partway through is a genuinely different intervention than another attempt at the same level, and a hard cap forces an explicit decision instead of the loop simply petering out with the finding's fate never recorded."
  see-also: repeated-fix-failure-questions-architecture

- id: dont-pre-judge-reviewer-findings
  rule: "When dispatching a reviewer, never instruct it to skip, downgrade, or not flag a specific issue you anticipate. If you believe a finding would be a false positive, let the reviewer raise it and adjudicate it afterward rather than filtering it out of the review itself."
  condition: "Writing a review dispatch prompt, when tempted to add an instruction narrowing what the reviewer should flag."
  reason: "An instruction that pre-filters findings collapses the reviewer's independence into a rubber stamp for whatever the dispatcher already believes — the value of an external review is specifically that it isn't primed by the producer's own assumptions, and adjudicating a raised-then-rejected finding costs less than silently losing a real one to a pre-emptive filter."

- id: parallel-agents-assigned-orthogonal-focus
  rule: "When dispatching multiple parallel agents to widen coverage of the same design or review question, assign each agent an explicit, distinct optimization axis or lens — e.g. minimal-change vs. clean-architecture vs. pragmatic-balance for an architecture question, or correctness vs. simplification vs. convention-adherence for a review — rather than issuing the same open-ended prompt to all of them. Let each agent commit decisively within its assigned lane; consolidate and compare the results afterward."
  condition: "When spawning more than one instance of the same composition in parallel specifically to widen coverage of one design or review question — not when parallel dispatch is dividing genuinely independent units of work (parallel-dispatch-requires-verified-independence governs that case)."
  reason: "Identical prompts sent to multiple agents tend to converge on the same answer or share the same blind spots, since nothing decorrelates their attention — the parallelism adds cost without adding coverage. Assigning each agent a distinct, named axis forces real diversity and lets each one commit decisively within its lane instead of hedging across all of them at once, which is also cheaper to compare afterward than reconciling several agents' partially-overlapping hedges."
  see-also: parallel-dispatch-requires-verified-independence

killed:
```
