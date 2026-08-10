# Audit record — routing plugin's judgment face

Provenance and per-kill audit detail for the routing plugin's domains (`routing`,
`spawn-integrity`, `planning`) — extracted from corpora-core's own `domains/audit.md` when
these process-judgment domains were relocated to `plugins/routing/`. The former
`orchestrator-routing` domain is recorded here under its extracted name `routing` (working file
`routing.md`). Loaded only at ratify/retrospective time — never in a spawn's working context.
Keyed by principle `id`, each noting its `domain`. See `kernel.md`, "Storage: working vs audit."

```yaml
provenance:

# domain: routing
- id: brief-ends-at-what
  domain: routing
  provenance: "2026-06-01, box-fill calculator box picker. Orchestrator computed SVG coordinates and TypeScript types in the brief, leaving the coder nothing to transcribe."

- id: stop-and-route
  domain: routing
  provenance: "2026-06-01, box-fill calculator redesign. Orchestrator entered designer mode and produced the full design spec inline rather than spawning the designer role."

- id: frame-before-routing
  domain: routing
  provenance: "2026-06-01, orchestrator corpus setup."

- id: route-questions-not-roles
  domain: routing
  provenance: "2026-06-12, operator feedback: established pipeline caused reflex spawning; question-routing better matches actual cost structure."
  history:
    - date: 2026-07-18
      type: generalized
      reason: "Absorbed design-question-during-coder-session. Rewrote the operator-surfacing default: it existed because spawned roles couldn't resume (one-shot) and a full spawn was expensive for one decision. Neither holds now — a role can pause on a question and resume, and non-blocking questions queue to the owning role's deferred-decisions queue for its next natural spawn instead of defaulting to the operator."
    - date: 2026-07-18
      type: narrowed
      reason: "Dropped the code-question clause. Operator reported never observing a code question routed to the coder in practice; the theoretical case (coder signal on a design tradeoff) is already better served by the coder's own tradeoffs block, surfaced once actually implementing rather than via a separate pre-implementation question."

- id: surface-design-questions-neutrally
  domain: routing
  provenance: "2026-06-12, operator clarified: orchestrator should not drift into design thinking even when capable."
  history:
    - date: 2026-07-22
      type: moved
      reason: "pokemon-game dry-run exercise, planner-decomposition session. Generalized beyond its UX/UI-specific condition and relocated to the new interviewing domain as frame-questions-for-cheap-answers — the same test (frame for a cheap answer, omit a baked-in opinion) applies to any question-framing moment (planner dialogue, any lens's questions-pending pause), not only the orchestrator routing a design question. Removed from orchestrator-routing's principles: the orchestrator now draws this judgment by composing interviewing (directly, or via the planner alias) rather than carrying a duplicate, narrower copy of its own."

- id: spawn-threshold-is-spec-scope
  domain: routing
  provenance: "2026-06-12, operator noted spawn cost often exceeds decision value."

- id: planner-over-brainstorming-for-scope
  domain: routing
  provenance: "2026-07-18, operator observation: the orchestrator already splits steps and roles well informally, but ambiguous-scope requests were often absorbed by the superpowers:brainstorming skill where the planner would be the better-fit reach — brainstorming has no corpus artifact, so that path leaves the planning domain permanently thin (planning had never had a retrospective at the time this was surfaced)."

- id: prefer-independent-evaluation
  domain: routing
  provenance: "2026-07-17, retrospective on review-composition cost. A standing reviewer composition was cut the same day for low uptake relative to its cost — this principle captures the replacement approach: an independent coder instance scoped to the review gets the same fresh-context benefit without a rarely-invoked dedicated composition."
  killed: 2026-07-27

- id: inline-coder-session-protocol
  domain: routing
  provenance: "2026-06-17, orchestrator retrospective. Merged from inline-session-enters-coder-role and close-inline-role-at-approval-gate."
  history:
    - date: 2026-06-22
      type: generalized
      reason: "Reworded from 'load coder.md' to 'load the coder lens and its declared domains' to match the lens+declaration model introduced in the corpus redesign. No change to the judgment."
    - date: 2026-07-21
      type: generalized
      reason: "Reworded from 'load the coder lens and its declared domains' to 'compose the coder alias' to match v3-redesign-proposal.md's stance+composition model — coder.md no longer exists as a file. No change to the judgment."
    - date: 2026-07-27
      type: trimmed
      reason: "Session-mining background-agent audit (FAMOUS project) flagged this as a mixed principle under principle-judgment.md's mined-workflow-stays-a-workflow test: its rule was a three-stage ordered workflow (compose domains, flag in-flight, ask at the seam) rather than a single resolved tradeoff. The domain-composing step was confirmed a near-verbatim duplicate of SKILL.md's own 'For inline spawn work' instructions — not unmined process needing a praxis phase, just redundant restatement — so it was dropped rather than routed anywhere. The judgment kernel (inline work gets the same corpus discipline as a formal spawn; capture principle candidates at the natural seam, not deferred to session-end) was kept, reworded to lead with it directly instead of the procedural framing."

- id: design-question-during-coder-session
  domain: routing
  provenance: "2026-06-17, orchestrator retrospective."
  killed: 2026-07-18

- id: audit-request-means-spawn-designer
  domain: routing
  provenance: "2026-06-13, load calculator audit session — orchestrator implemented operator-listed concerns as code and skipped the designer spawn."
  history:
    - date: 2026-07-21
      type: generalized
      reason: "Reworded from 'spawn the UI Designer' to 'spawn a ui-design-composed spawn' — ui-designer.md no longer exists as a file. No change to the judgment."

- id: screenshot-recapture-is-orchestrator-mechanical
  domain: routing
  provenance: "2026-07-22, UI screenshot cache design (docs/superpowers/specs/2026-07-22-ui-screenshot-cache-design.md). A fresh-context review of the design found that grounding orchestrator-run recapture by analogy to `corpus.py` invocation alone was a weaker fit than presented — script invocation has zero interpretation, while navigating to the correct rendered state to capture involves some procedural judgment. This principle states the narrower claim directly and names the boundary against `stop-and-route` explicitly (visual judgment about the recaptured state routes to a role; mechanical recording of current state does not)."
  killed: 2026-07-27

- id: no-cost-driven-domain-omission
  domain: routing
  kind: judgment
  provenance: "2026-07-22, operator conversation on lens/domain composition design. Discussion of whether lenses should be the mandatory composition unit (to guard against relevant domains going unloaded) surfaced a distinct, already-observed failure: the orchestrator thinning a composition to save tokens rather than never having known a domain was relevant in the first place. Paired with spawn-integrity's checkpoint-on-context-pressure-tell, added the same session, as the two sides (routing-time vs. spawn-side) of the same pressure."

- id: spawn-only-when-judgment-remains
  domain: routing
  kind: judgment
  provenance: "2026-07-26, Blog UI-library-sync task. The task brief for a ui-design-composed spawn already specified the exact before/after text for every edit — no design decision remained; the spawn's job had degraded to text transcription, and the isolation overhead (composed prompt, spawn execution, handoff review) cost more than making the edit directly would have."

- id: concern-class-diversity-triggers-decomposition
  domain: routing
  kind: judgment
  provenance: "Operator-authored, 2026-07-30, based on observed behavior in motors-and-controls' sim-09 task (2.5-3x the tool calls/tokens of sibling tasks, bundling engine-design judgment, catalog/UI plumbing, and lab-content re-derivation into one task), root-caused and refined through direct dialogue rather than a spawned proposal."
  history:
    - date: 2026-07-26
      type: moved
      reason: "Ratified into Blog's project-layer orchestrator-routing domain first, then promoted to this kernel-seed layer the same day — operator confirmed the pattern had recurred across projects (Blog, FAMOUS, Meridian) and was part of the original motivation for building corpora/praxis at all: superpowers' plan-then-execute skills were solving the same ambiguity-resolution problem twice, once in the plan and again when agents re-litigated it during execution."

# domain: planning
- id: concern-names-work-not-role
  domain: planning
  kind: judgment
  provenance: "2026-07-22, pokemon-game dry-run exercise. Decomposed from planner.md's step 4 ('set concern... do not name roles'), which stated the constraint in lens prose without a corresponding ratified domain principle."

- id: self-check-against-domain-before-finalizing
  domain: planning
  kind: judgment
  provenance: "2026-07-22, pokemon-game dry-run exercise. Decomposed from planner.md's step 6 ('self-check against planning principles' before writing the queue). Genuine-fork-tested against the same session's own evidence: the orchestrator did not catch its own full-corpus-on-spawn violations until asked to review — explicit self-checking does not happen for free under accumulated context, which is also why coding-general's structural-examination-at-working-checkpoint exists as a ratified principle rather than assumed behavior."
  history:
    - date: 2026-07-22
      type: moved
      reason: "Domain-decomposition audit (same day, later pass): the underlying test — check your own output against your own composed domains before finishing — has nothing planning-specific about it. Generalized and promoted to the new kernel-seed spawn-integrity domain as self-check-against-composed-domains-before-finalizing (domains/audit.md carries that entry's own provenance, below)."

- id: open-questions-are-explicit
  domain: planning
  provenance: "No provenance was ever recorded for this principle — a pre-existing gap found while executing the 2026-07-18 structural-kinship merge, backfilled here rather than left orphaned."
  history:
    - date: 2026-07-18
      type: generalized
      reason: "Absorbed surface-shared-concept-before-implementation as a named instance — a shared runtime concept two tasks would each touch is exactly 'information the planner doesn't have.'"

- id: task-describes-output-not-implementation
  domain: planning
  provenance: "2026-06-22, FAMOUS disc-02. Planner described the implementation path (files to touch, data to thread) rather than the observable output. Operator noticed and flagged it; principle surfaced through operator investigation, not through the planner's self-check."

- id: surface-shared-concept-before-implementation
  domain: planning
  provenance: "No provenance was ever recorded for this principle — same pre-existing gap as open-questions-are-explicit, backfilled here rather than left orphaned."
  killed: 2026-07-18

- id: fog-before-ticket
  domain: planning
  kind: judgment
  provenance: "2026-08-01, reviewing mattpocock/skills (github.com/mattpocock/skills) for principles transferable to corpora's own planning domain — its wayfinder skill's 'Not yet specified' / fog-of-war mechanic named a gap the queue schema had no category for: an in-scope area sensed but not yet sharp enough to state as a task or open question. Reading-pipeline provenance flagged at ratification per reading-pipeline-provenance-flags-knowledge-risk; ratified anyway because the gap is real against corpora's own existing task-is-actionable-without-planning and open-questions-are-explicit principles, not merely plausible-sounding imported doctrine."

- id: scope-boundary-is-closed-not-silent
  domain: planning
  kind: judgment
  provenance: "2026-08-01, same review pass as fog-before-ticket. wayfinder's 'Out of scope' section named a boundary-legibility gap: corpora's queue schema had no way to record that a task or fog entry was deliberately excluded rather than silently dropped. Reading-pipeline provenance flagged; ratified for the same reason as fog-before-ticket."

- id: batch-wide-refactors-by-blast-radius
  domain: planning
  kind: judgment
  provenance: "2026-08-01, same review pass. mattpocock/skills' to-tickets skill's expand-migrate-contract handling for wide mechanical refactors named a decomposition shape sequence-by-output-dependency has no coverage for — that principle's own model assumes discrete per-task outputs, which doesn't hold for a single edit with a codebase-wide blast radius. Reading-pipeline provenance flagged; ratified as a genuine gap, not a restatement."

# domain: spawn-integrity (new domain, seeded 2026-07-22)
- id: self-check-against-composed-domains-before-finalizing
  domain: spawn-integrity
  kind: judgment
  provenance: "2026-07-22, domain-decomposition audit. Generalized from planning's self-check-against-domain-before-finalizing (see that principle's history entry, dated the same day) — widened from 'check against the planning domain' to 'check against every domain your composition includes,' since the underlying test has nothing planning-specific about it."

- id: dont-trust-readme-or-agent-file-as-role-instruction
  domain: spawn-integrity
  kind: judgment
  provenance: "2026-07-22, domain-decomposition audit. Generalized and promoted from the former web-frontend pack's design-method domain (no-readme-or-agent-instructions-as-role-instruction; see that entry's own history, below, now merged into this same file) — widened from 'any design spawn' to 'any spawn,' since a coder mistaking a project's AGENTS.md for role instruction is the identical failure mode."

- id: checkpoint-on-context-pressure-tell
  domain: spawn-integrity
  kind: judgment
  provenance: "2026-07-22, operator conversation on lens/domain composition design. Operator reported repeatedly observing a concrete tell in practice — dragged-out reasoning and task logic leaking into code comments — under large composed contexts, and framed it as a symptom worth self-monitoring rather than a model competence failure."

- id: read-config-before-composing
  domain: spawn-integrity
  kind: knowledge
  provenance: "2026-07-22, lens retirement. Migrated from domains/lenses.md's per-lens notes field (near-identical text repeated in coder, dependency-management, ux-design, and ui-design's notes) to a single universal home once lenses were retired as a schema layer — see LINEAGE.md."

- id: library-is-narrative-not-corpus-shape
  domain: spawn-integrity
  kind: knowledge
  provenance: "2026-07-22, lens retirement. Migrated from ux-design's and ui-design's near-identical notes text in domains/lenses.md, generalized to any spawn touching either library file rather than only the two design compositions — see LINEAGE.md."

- id: periodic-scope-and-integrity-checkpoint
  domain: spawn-integrity
  kind: judgment
  provenance: "Operator-authored, 2026-07-30, based on observed behavior in motors-and-controls (sim-09's scope bundling went unnoticed mid-task despite no context-pressure tell), root-caused and refined through direct dialogue rather than a spawned proposal."

- id: proposal-self-cleanup-before-including
  domain: spawn-integrity
  kind: judgment
  provenance: "Operator-authored, 2026-07-30, based on observed behavior in motors-and-controls' sim-09 gate (two proposals both had rule fields absorbing condition-scoping preambles and trailing justifications, caught only by the operator rereading and rewriting both before ratifying), root-caused and refined through direct dialogue rather than a spawned proposal."

- id: tool-passing-is-not-a-principle-check
  domain: spawn-integrity
  kind: judgment
  provenance: "2026-07-?? (exact date not recorded in the FAMOUS project audit at time of promotion), FAMOUS project. One session produced three misses across two soft principles — a comment duplicating ux-library.md content written twice in QueueRows.tsx, the same architectural point re-explained three times in player.tsx, and tag-identity-dependencies-check-before-handoff never once applied to a matching ref-based committer pattern — while self-check-against-composed-domains-before-finalizing was already loaded and verification commands stayed green throughout."
  history:
    - date: 2026-07-23
      type: generalized
      reason: "Promoted from FAMOUS's project-level spawn-integrity domain to seed, alongside minimize-comments-prefer-self-documenting-code (its reason text names 'comment discipline' as one of the unenforced-principle examples this principle guards). Rule/reason otherwise unchanged from the FAMOUS original."

# domain: planning — first retrospective, 2026-08-02
- id: planning-states-what-not-how-or-who
  domain: planning
  kind: judgment
  provenance: "2026-08-02, planning's first retrospective (triggered: working-file-tokens grew 59% over baseline). structural-kinship-condensation-candidate flagged task-describes-output-not-implementation and concern-names-work-not-role as stating the same underlying test in different words. A second candidate (open-questions-are-explicit/fog-before-ticket/scope-boundary-is-closed-not-silent) was drafted and rejected — its rule read as three routing rules stapled with 'respectively,' not one test; see-also cross-links added between those three instead. This one held up: drafted with its reason grounded independently in what information planning structurally lacks, not in citing the two instances by name, per operator's explicit request. Held as a peer of both instances (domains/audit.md's explicit-by-default/prefer-error-exposing-form precedent), not a replacement."

# superpowers skill-mining queue, second wave (2026-08-02): dispatching-parallel-agents,
# subagent-driven-development, receiving-code-review, test-driven-development,
# finishing-a-development-branch, verification-before-completion, writing-plans, writing-skills.
# executing-plans, requesting-code-review, using-git-worktrees, using-superpowers, and brainstorming
# contributed nothing new — either pure superpowers-mechanism (git worktree/branch mechanics, plan-doc
# pipeline scaffolding), already covered by an existing corpora principle, or (brainstorming's
# "every project needs a full design regardless of simplicity") in direct conflict with corpora's
# already-settled lighter-path principles (spawn-threshold-is-spec-scope,
# design-pattern-application-lighter-path) and deliberately not imported.
- id: parallel-dispatch-requires-verified-independence
  domain: routing
  kind: judgment
  provenance: "2026-08-02, mined from superpowers:dispatching-parallel-agents (independence check before fan-out) merged with superpowers:subagent-driven-development's stricter same-working-tree rule for implementation agents specifically."

- id: model-tier-by-task-complexity
  domain: routing
  kind: judgment
  provenance: "2026-08-02, mined from superpowers:subagent-driven-development's Model Selection section. Genuinely new axis for corpora — no existing principle governs model-tier choice, only domain/composition choice."

- id: verification-stays-with-orchestrator
  domain: routing
  kind: judgment
  provenance: "2026-08-07, operator interjection during the script-alignment workstream (model-tiered batch spawns). Ratified with operator's rewording: verification runs as a pass after the implementation units (implementers collide when each runs the suites), defects route to a fresh spawn. Originating evidence: the orchestrator's own post-batch drive of route.py exposed a marker-clobbering close_work crash the implementing batch's green suites had not surfaced. A sibling proposal (defer-work-that-anchors-an-undecided-decision) was killed at the same gate: process-not-judgment (planning's open-questions-are-explicit + queue blocked-by machinery already carry it) and provenance leaked into its rule field."

- id: bounded-fix-loop-then-forced-disposition
  domain: routing
  kind: judgment
  provenance: "2026-08-02, mined from superpowers:subagent-driven-development's fix-loop/breaker/adjudication mechanism, generalized past its source's specific 5-round cap and ledger format to the transferable rule (cap, escalate before the cap, force a recorded disposition at the cap)."

- id: dont-pre-judge-reviewer-findings
  domain: routing
  kind: judgment
  provenance: "2026-08-02, mined from superpowers:subagent-driven-development's task-review dispatch guidance ('never instruct a reviewer to ignore or not flag a specific issue')."

- id: no-placeholder-content-in-task-steps
  domain: planning
  kind: judgment
  provenance: "2026-08-02, mined from superpowers:writing-plans' 'No Placeholders' section, generalized past its source's plan-document-specific examples to task content generally."

- id: verify-interface-consistency-across-tasks
  domain: planning
  kind: judgment
  provenance: "2026-08-02, mined from superpowers:writing-plans' self-review step (\"clearLayers() in Task 3 but clearFullLayers() in Task 7\")."

- id: parallel-agents-assigned-orthogonal-focus
  domain: routing
  kind: judgment
  provenance: "2026-08-02, mined from marketplace plugin feature-dev (commands/feature-dev.md Phase 4 architect dispatch and Phase 6 reviewer dispatch, both assigning named distinct focuses to parallel agents)"

# domain: interviewing (moved from the prose plugin — clarifying-dialogue judgment that companions planning; consumed by the framing phase)
- id: ask-one-question-at-a-time
  domain: interviewing
  kind: judgment
  provenance: "2026-07-22, pokemon-game dry-run exercise. Decomposed from planner.md's 'Dialogue' step. Genuine-fork-tested against the operator's own observed default: batching multiple clarifying questions into one turn is a concrete, recurring model behavior, not a strawman."

- id: name-clear-direction-dont-manufacture-choice
  domain: interviewing
  kind: judgment
  provenance: "2026-07-22, pokemon-game dry-run exercise. Decomposed from planner.md's 'Dialogue' step. Directly evidenced within the same session: the orchestrator manufactured multi-option choices until the operator asked it to stop and proceed on recommendation instead."

- id: frame-questions-for-cheap-answers
  domain: interviewing
  kind: judgment
  provenance: "2026-07-22, pokemon-game dry-run exercise. Absorbs and generalizes orchestrator-routing's surface-design-questions-neutrally (see that principle's history entry, dated the same day) — widened from 'a UX or UI question routed to the operator' to any question-framing moment, since the condition named no genuinely UX/UI-specific mechanism."
```

<!-- corpus-script:begin — maintained by scripts/corpus.py; do not edit by hand -->

## counters (script-maintained)

```yaml
counters:
  - domain: interviewing
    since: 2026-07-23
    ratified: 0
    killed: 0
    graduated: 0
    gate-violations: 0
    working-file-tokens: 828
    baseline-tokens: 810
    principles-at-baseline: 3
    kills-at-baseline: 0
    conventions-at-baseline: 0
  - domain: planning
    since: 2026-08-04
    ratified: 0
    killed: 0
    graduated: 0
    gate-violations: 0
    working-file-tokens: 4318
    baseline-tokens: 4318
    principles-at-baseline: 11
    kills-at-baseline: 1
    conventions-at-baseline: 0
  - domain: routing
    since: 2026-08-04
    ratified: 0
    killed: 0
    graduated: 0
    gate-violations: 0
    working-file-tokens: 5403
    baseline-tokens: 5403
    principles-at-baseline: 21
    kills-at-baseline: 3
    conventions-at-baseline: 0
  - domain: spawn-integrity
    since: 2026-08-04
    ratified: 0
    killed: 0
    graduated: 0
    gate-violations: 0
    working-file-tokens: 2189
    baseline-tokens: 2189
    principles-at-baseline: 5
    kills-at-baseline: 3
    conventions-at-baseline: 0
efficacy:
co-occurrence:
library-drift:
  since-last-sync: 0
```

<!-- corpus-script:end -->

# Kill log — relocated out of the domain working files (2026-08-07, operator decision:
# working-context cost of carrying kills into every spawn outweighed the re-proposal-prevention
# benefit in practice). Each entry keeps its full working-file record plus its domain. The ratify
# gate consults this list (audit load); spawns never see it.

```yaml
kills:

- id: surface-shared-concept-before-implementation
  domain: planning
  rule: "When orientation reveals that two or more tasks in the decomposition will operate on the same runtime concept — a current position, a selection, a history, a running count — add an open question naming that concept, stating the conflict or ambiguity, and blocking all affected tasks. Do not decompose into tasks that will independently decide how a shared concept behaves."
  kill_type: quality
  reason_killed: "Merged into open-questions-are-explicit as a named instance — a shared concept two tasks would each touch is exactly 'information the planning spawn doesn't have.' The composition itself already states the general test in prose (step 3, 'Settle open questions')."

- id: defer-only-nonblocking-design-decisions
  domain: routing
  rule: "Queue a UI or UX decision only when implementation can proceed with an explicit, narrow, reversible provisional treatment. Surface any blocking decision immediately."
  kill_type: container
  reason_killed: "Relocated to the uiux plugin's `design-routing` domain (t-06, 2026-08-05). Routing judgment about design work specifically — it names the design `deferred-decisions` queue — so it belongs with the design concern, not praxis's engine-agnostic routing domain. A project importing routing but not the design plugin no longer carries it."

- id: batch-deferred-decisions-coherently
  domain: routing
  rule: "Group deferred decisions by owning composition and related surface rather than count alone. Route a designer workstream when several items require coherent judgment, an item becomes blocking, provisional work risks material rework, or the operator requests review."
  kill_type: container
  reason_killed: "Relocated to the uiux plugin's `design-routing` domain (t-06, 2026-08-05) — it governs the design deferred-decision queue, a design-concern artifact."

- id: audit-request-means-spawn-designer
  domain: routing
  rule: "When the operator uses the phrase 'full audit' or 'UI/UX audit', spawn a `ui-design`-composed spawn for a holistic review even if specific operator-stated concerns were also provided."
  kill_type: container
  reason_killed: "Relocated to the uiux plugin's `design-routing` domain (t-06, 2026-08-05) — specifically about spawning a designer composition on a UI/UX audit request."

- id: design-pattern-application-lighter-path
  domain: routing
  rule: "When a design task is pattern-application — applying documented UI/UX library vocabulary to a new surface with no genuine visual judgment — prefer the surface-to-operator path over a full designer spawn."
  kill_type: container
  reason_killed: "Relocated to the uiux plugin's `design-routing` domain (t-06, 2026-08-05) — it turns on the UI/UX library, a design-concern artifact."

- id: prefer-independent-evaluation
  domain: routing
  rule: "Prefer a fresh isolated context when a spawn evaluates work produced by the current agent or context. There is no standing reviewer composition — when code review is warranted, spawn a fresh coder agent scoped to the review, not the coder that produced the work."
  kill_type: container
  reason_killed: "The default (fresh context, no standing reviewer role) is a routing rule with no real per-instance judgment beyond the cost/risk tradeoff, which SKILL.md's \"Inline, resume, or isolate\" already named as a factor (`evaluator independence`) — that section now states the default directly. Folded into praxis's `independent-review` phase as the general, reusable version for a project running praxis, distinct from that phase's producer-side counterpart, `self-verification`."

- id: screenshot-recapture-is-orchestrator-mechanical
  domain: routing
  rule: "Operate the project's browser automation tool directly to recapture a stale screen for the screenshot cache, rather than spawning a composition for it. Route to a composition instead when the task requires visual judgment about what the recaptured state should look like."
  kill_type: container
  reason_killed: "Its own reason field states it outright: 'requires no design or code judgment' — a process-not-judgment admission about as direct as the corpus has. Folded into praxis's `screenshot-recapture` phase for a project running praxis; SKILL.md's \"Screenshot cache upkeep\" already carries the mechanical procedure corpora needs standalone, so nothing else changes there beyond the cross-reference."

- id: design-question-during-coder-session
  domain: routing
  rule: "When a UX or UI question surfaces during inline coder work, pause and surface it to the operator: name the domain (UX or UI), the specific decision needed, and the context required to answer it. Present two options explicitly — operator resolves directly (coder continues with that answer), or operator escalates to the appropriate designer (spawn, relay output, coder resumes with spec)."
  kill_type: quality
  reason_killed: "Merged into route-questions-not-roles, which now covers this case directly. The two 'operator resolves or operator escalates' options assumed operator-surfacing was the only cheap path — the queue-to-owning-role option didn't exist here at all."

- id: self-check-against-composed-domains-before-finalizing
  domain: spawn-integrity
  rule: "Before finalizing your output, re-read it against the ratified principles in every domain your composition includes and revise any violation found."
  kill_type: container
  reason_killed: "Purely temporal (when to check) with no domain-specific judgment of its own — the same category error praxis's `mined-workflow-stays-a-workflow` names directly. Folded into `kernel.md`'s \"The handoff artifact\" as part of the handoff-writing procedure so corpora keeps the behavior standalone; the general version (a deliverable needs this check once it concretely exists, whatever governs it) now lives as praxis's `self-verification` phase for any project running praxis."

- id: tool-passing-is-not-a-principle-check
  domain: spawn-integrity
  rule: "Passing lint/typecheck/tests is not evidence that the composed domains' qualitative principles were checked. At the same seam `self-check-against-composed-domains-before-finalizing` already names, actually re-read the diff against each composed domain principle one by one."
  kill_type: container
  reason_killed: "Elaboration on the same killed self-check principle's timing/procedure, not a separate judgment call. Folded into the same `kernel.md` paragraph; also covered in praxis's `self-verification` phase."
  see-also: minimize-comments-prefer-self-documenting-code

- id: read-config-before-composing
  domain: spawn-integrity
  rule: "Read .corpora/config.md first, for registered utilities, library paths, and verification commands, before beginning task work. Halt and report if it is absent — bootstrap Phase 1 must run first."
  kill_type: quality
  reason_killed: "Already covered verbatim by SKILL.md (\"Every spawn reads .corpora/config.md at the start of its work\" and the bootstrap-first fallback) — restating it as a domain principle was pure duplication, not a judgment call. No fold needed; the behavior was never missing from corpora's own procedure."
```
