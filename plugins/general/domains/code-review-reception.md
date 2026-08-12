---
id: code-review-reception
subject: coding
universal: false
applies-when: []
labels: [code-review]
---

principles:

- id: verify-feedback-against-codebase-before-implementing
  rule: "Before implementing code review feedback, check it against the actual codebase — does the suggestion break existing functionality, is there a reason the current implementation is the way it is, does it hold across the platforms/versions this project targets. Implement only after that check, not on the feedback's own authority."
  condition: "Receiving code review feedback of any kind — from the operator, an external reviewer, or a reviewer subagent — before acting on it."
  reason: "Feedback that reads as confident and technically-framed is not automatically correct for this specific codebase — the reviewer may be missing context (a compatibility constraint, a prior deliberate decision) that only checking against the actual code surfaces. Implementing on the feedback's authority alone substitutes the reviewer's assumed context for the codebase's actual state."

- id: clarify-all-unclear-items-before-implementing-any
  rule: "When a batch of review feedback contains items you understand and items you don't, stop and ask for clarification on the unclear ones before implementing any of them — including the ones already understood."
  condition: "Receiving multi-item review feedback where at least one item's intent or scope is unclear."
  reason: "Items in a batch of feedback are often related — implementing the clear items first on a partial understanding risks building on an assumption the unclear items would have corrected, producing rework once the clarification arrives instead of before."

- id: push-back-on-review-feedback-you-can-show-is-wrong
  rule: "When review feedback appears technically incorrect for this codebase, would break existing functionality, or conflicts with a prior recorded decision, push back with technical reasoning — cite the specific test, usage, or decision — rather than implementing it to avoid friction."
  condition: "Review feedback conflicts with observable evidence already in the codebase or its history."
  reason: "Implementing feedback to avoid friction, when the codebase already shows it's wrong, trades a correct outcome for a socially smooth one — a well-documented pull toward agreeableness independent of whether the suggestion is actually correct. Citing concrete evidence keeps the pushback technical rather than a bare disagreement the reviewer has no way to weigh."

- id: verify-usage-before-implementing-reviewer-completeness-request
  rule: "When review feedback asks to 'implement properly' or complete a partial feature, check the feature's actual usage in the codebase first. If it is unused, propose removing it rather than completing it; only build it out fully if something actually calls it."
  condition: "Review feedback requests completing, hardening, or 'properly implementing' something whose current call-site usage has not yet been confirmed."
  reason: "A reviewer's 'do this properly' framing reads as authoritative regardless of whether the feature is exercised anywhere — building out an unused code path to satisfy that framing spends real effort on something nothing calls, the same waste avoided anywhere else usage is checked before investing in completeness."
