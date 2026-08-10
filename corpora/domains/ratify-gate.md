---
subject: process
posture: guardrail
units-of-work: [ratify]
universal: false
---

# Domain: ratify-gate

Judgment about assembling a complete spawn and processing what it returns — as opposed to
`orchestrator-routing`'s judgment about which composition to invoke and when. Split from
`orchestrator-routing` 2026-07-18; see `LINEAGE.md`, "The ratify-gate split." Audit metadata lives in `domains/audit.md`, loaded only at
ratify/retrospective time.

```yaml
last-retrospective: 2026-07-30

principles:

- id: surface-deterministic-shortcut-candidates-liberally
  rule: "Surface a plausible project utility whenever work reveals a concrete deterministic operation with noticeable inference, precision, or repetition cost. Require evidence to build it, not to mention it. Persist every disposition and resurface recurrence with prior evidence."
  condition: "When a spawn's handoff reports a possible deterministic shortcut after checking existing libraries, dependencies, runtime tools, and registered utilities."
  reason: "The operator can deny a weak candidate cheaply, while a candidate lost with a deleted handoff depends on human memory to be recognized next time. Persistent low-threshold surfacing lets recurrence supply the evidence without filling active config with speculation."

- id: narrated-computation-is-sufficient-utility-evidence
  rule: "Treat a single instance of a spawn narrating its way step-by-step through a deterministic, checkable procedure — arithmetic, color-space or geometric math, date math, precise counting or sorting — as sufficient evidence to build a utility on its own, without waiting for recurrence. This is the exception to requiring accumulated evidence before building."
  condition: "When a spawn's transcript or handoff shows guess-and-check or step-by-step narrated reasoning standing in for a process that has an exact, deterministic procedure, rather than a plausible-but-unverifiable judgment call."
  reason: "A model does not perform computation directly — it predicts a plausible reasoning trace that arrives at an answer, which is why trivial arithmetic gets narrated ('I have 2 apples, someone gives 2 more, now I have 4') instead of simply computed. That approximation holds for small cases and compounds into guess-and-check for anything with real numeric or geometric complexity. The degradation is structural, not incidental to one bad session — a single clear instance of it already proves the operation is deterministic and checkable, which is the only fact `surface-deterministic-shortcut-candidates-liberally`'s repeated-evidence requirement exists to establish for fuzzier candidates in the first place."

- id: spawn-token-summary
  rule: "Append the following section to every new isolated spawn's prompt, after the task: '## Token usage summary\nAt the end of your output, add a `### token usage` section listing: every file you read and its approximate line count, how many corpus principles you referenced, and your estimate of the single heaviest cost item.'"
  condition: "Every new isolated spawn."
  reason: "The process layer only receives an aggregate token count from the runtime — no per-operation breakdown. Self-reporting by the spawn is the only way to identify which reads or outputs drove cost."

- id: full-corpus-on-spawn
  rule: "Always pass every domain the spawn's composition includes, in full, when starting an isolated spawn. Do not excerpt or filter a domain by perceived task relevance. This bars dropping *principles* by relevance — it does not bar the working/audit storage split (see kernel.md), which removes audit metadata uniformly, nor the declaration itself (loading only the domains a composition declares is not a relevance judgment — it is a fixed, inspectable contract)."
  condition: "Any new isolated spawn whose composition includes one or more domains."
  reason: "Selective inclusion within a declared domain requires the process layer to judge which principles are relevant from the task framing — a judgment it cannot make reliably. A missed principle silently degrades the spec or implementation without any signal it was missed. The duplicate transmission cost is tolerated for this completeness guarantee, not desired or used as corpus-size control."

- id: ratify-gate-judgment-vs-knowledge
  rule: "At the ratify gate, ask for each proposal whether it encodes a judgment call (a decision made under uncertainty where context and tradeoffs shaped the outcome) or a knowledge item (something derivable from documentation or training). Surface this distinction with the proposal — the spawn knows it from the inside. Do not evaluate it from the outside at the gate."
  condition: "When presenting principle proposals to the operator at the ratify gate."
  reason: "The corpus's value is captured judgment, not recalled facts. A principle that only returns a lookup when it fires adds reader-tax without adding decision capacity. The spawn is better positioned to make the knowledge/judgment distinction than a gate-time reviewer because it has the context of how the decision was made. The process layer routes this question; it does not answer it."

- id: domain-assignment-at-ratify-gate
  rule: "At the ratify gate, assign each ratified proposal to a domain and write it there. If no existing domain fits, create a new domain (working file + declaration update on the compositions that should load it). If a proposal spans two domains, surface that as a possible domain-boundary problem rather than fragmenting the principle across both."
  condition: "When ratifying a proposal that arrived without a home domain."
  reason: "Proposals surface from work, not from a domain. The gate is the one human-gated point where domain assignment judgment belongs. A split-domain proposal is a signal the boundaries may be wrong — a fork candidate to surface, not a principle to duplicate."

- id: worker-handoffs-reach-orchestrator
  rule: "Allow a spawn to create autonomous, scope-bounded workers within its assigned task and stance. Work results return to the parent; questions, tradeoffs, proposals, violations, and routing requests go directly to the process layer when supported, or are relayed by the parent verbatim under `Delegated handoffs`. Cross-composition and deeper delegation return to the process layer."
  condition: "When a spawn delegates part of its assigned work."
  reason: "Local decomposition can reduce execution cost without changing workstream ownership. The failure mode is not delegation itself but allowing the parent to filter a child's routing-relevant handoff, which hides questions and corpus signals from the process layer, the only one authorized to route and ratify them."

- id: operator-ratifies-routing-corpus
  rule: "The process layer may surface observations about its own routing behavior, but it must not promote them into `orchestrator-routing` without explicit operator ratification."
  condition: "When work suggests a new or revised routing principle."
  reason: "The process layer cannot independently evaluate and ratify the policy governing its own choices. Operator ratification supplies the missing external gate; repeated, independently-observed evidence may later justify promotion into the skill or kernel as a meta-principle."

- id: artifact-points-to-persisted-file-not-full-reproduction
  rule: "When a spawn's deliverable is a write to a file the process layer can already read (a synced library doc, an edited source file, an updated config), the handoff's Artifact section states a diff/changelog plus a pointer to the file — it does not reproduce the full post-edit document. Reserve full reproduction for content with no other persisted home yet: a spec about to be handed to another composition, a tradeoff block, a fresh audit."
  condition: "When a spawn writes its Artifact section and the underlying deliverable already exists as a file the process layer can open directly."
  reason: "The schema's 'freeform' Artifact field left an implicit default of pasting the whole document, which pays real token cost once and is then discarded when the handoff file is deleted after ratification — the diff is what the audit trail actually needs going forward. A pointer plus a diff gives the ratify gate everything its audit-against-principles step requires, without the throwaway cost."

- id: separate-spec-fidelity-from-principle-compliance
  rule: "At the gate, check whether the spawn's output actually satisfies its own task's stated acceptance criteria as a finding structurally separate from the principle-compliance audit — report both, never merged into one combined severity list, and never let a clean pass on one stand in for the other."
  condition: "When auditing a spawn's handoff at the ratify gate, for any unit of work whose originating task or brief states an observable output or acceptance condition distinct from domain-principle compliance."
  reason: "A deliverable can cleanly pass every composed domain's principles while still not being what the task actually asked for, and vice versa — merging both checks into one pass lets a strong result on one axis mask a real failure on the other, the same masking `testing`'s runtime-verification-required-not-static-checks-alone already guards against for static-vs-runtime checks, applied here to principle-compliance vs. task-fidelity instead."

- id: verify-artifact-not-reported-status
  rule: "When processing a spawn's handoff, check the actual artifact it produced — the real diff, file contents, or test output — rather than treating its self-reported status field or narrative claim of success as sufficient evidence on its own."
  condition: "Processing any handoff whose status claims completion, a fix, or passing verification."
  reason: "A spawn's own status field is exactly the kind of self-report the operator can't independently observe happening — the same gap `spawn-token-summary` exists to close for cost, applied here to correctness. A reported 'complete' status is a claim, not evidence; the artifact it points to is the evidence."

killed:
```
