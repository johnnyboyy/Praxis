---
id: security
subject: coding
universal: false
applies-when: []
task-kinds: [create, change]
---

principles:

- id: scope-iac-permissions-to-stated-need
  rule: "Grant the minimum permission/role/policy scope the immediate feature requires; do not reach for a broader wildcard grant just because it guarantees the deployment succeeds without further debugging."
  condition: "Writing or editing IAM policies, k8s RBAC, cloud service roles, or DB grants for a new or changed resource."
  reason: "IaC is syntactically valid whether the grant is minimal or wildcard, so neither regex nor LLM diff-review flags an over-broad policy as wrong. An agent optimizing for 'deployment succeeds on first try' will widen scope to avoid a permission-denied error loop, since it never has to live with the consequences of an over-grant the way an on-call human would."

- id: gate-and-flag-security-check-bypass
  rule: "Gate a loosened or disabled security-relevant check (auth, CORS, TLS/cert verification, CSP) behind an explicit dev-only condition and state out loud that it's a bypass; never commit the loosened state as the new default."
  condition: "The fastest way to unblock the current task is to loosen or disable a security-relevant check."
  reason: "The agent's plan is scoped to 'make this error go away' for the stated task; nothing in that local loop asks whether the loosened check is safe to leave on. The bypass looks, in the diff, like ordinary configuration — not an injected vulnerability pattern — so it survives automated review and quietly becomes the shipped default. Unlike the performance-debt case a ceiling comment covers (terminal-checkpoint-pass), a live security exposure needs to be gated, not just commented, since leaving it reachable is itself the risk."

- id: fix-implementation-not-security-assertion
  rule: "Fix the implementation or environment causing a failing security-relevant assertion — never loosen or delete the assertion to make the check pass."
  condition: "A failing test or CI check asserts an auth, permission, crypto, or input-validation property."
  reason: "The agent is optimizing for 'checks pass,' and from its local view a broken security assertion looks structurally identical to a flaky or overly strict one. Loosening the assertion is a one-line diff that isn't obviously malicious to a scanner — the removed or weakened check just looks like a simplification. Whether the assertion was correct in the first place depends on intent a pattern-matcher can't determine."

- id: state-trust-model-for-vague-auth-asks
  rule: "State the specific mechanism and trust boundary you're assuming, and check it against the codebase's existing auth pattern, before implementing."
  condition: "A request specifies a security-relevant outcome (\"add auth\", \"make this admin-only\", \"internal-only endpoint\") without naming the mechanism or trust boundary."
  reason: "An agent fills the gap with whatever shape is statistically dominant in training data — often a second, parallel auth mechanism rather than the one this codebase already uses (e.g. bolting on session-cookie checks in a service-to-service token codebase). Each mechanism looks individually fine to a diff reviewer; the security problem is the divergence between them, which only shows up at the architecture level."

- id: verify-dependency-currency-not-familiarity
  rule: "Verify a candidate dependency's current maintenance and CVE status before adding it for an auth/crypto/session/sanitization function; do not choose it solely because it's the most frequently seen package for that purpose."
  condition: "Selecting among multiple candidate libraries for a security-relevant function, where more than one plausible option exists."
  reason: "Training data is a snapshot; a package that was the standard recommendation at training time may since be deprecated, abandoned, or carry a disclosed unpatched CVE. The agent has no innate signal distinguishing 'commonly seen' from 'currently safe' — it pattern-matches on frequency, not currency, and frequency is exactly what keeps a stale-but-once-popular package getting picked."

- id: hardened-defaults-for-scaffolded-services
  rule: "Configure a newly scaffolded datastore/queue/cache/service with auth enabled and network-scoped binding, even if the tool's own quickstart examples ship insecure-by-default; do not replicate the bare quickstart invocation."
  condition: "Standing up a new backing service (database, cache, message queue, etc.) with no prior configuration to inherit from."
  reason: "An agent scaffolding new infra pattern-matches against that tool's own quickstart docs/training examples, which are optimized for 'running in one command,' not production safety (no-auth Redis/Mongo, 0.0.0.0 binding). No diff-review flags this because the resulting config is literally what the tool's own documentation shows as correct usage — there's no anomalous pattern to catch."

- id: mask-secrets-in-debug-artifacts
  rule: "Use masked or placeholder values in debug/investigation artifacts (logs, scratch scripts, test fixtures) instead of copying the real secret value out of env/config."
  condition: "Creating debug/investigation artifacts that touch real credential values while troubleshooting a credential/token/API-key-related issue."
  reason: "The agent has broad, fast file-write access and, mid-debugging, optimizes purely for 'reproduce the issue' — pasting the actual token into a scratch script is the quickest way to test it. A human might hesitate knowing the file could get committed or left around; the agent has no equivalent hesitation and routinely leaves the scratch artifact in the working tree after the task ends. This isn't a 'hardcoded secret meant to ship' pattern, so the standard secret-scanner framing doesn't naturally catch a leftover debug file."

- id: flag-missing-abuse-bound-on-expensive-endpoints
  rule: "Explicitly flag the absence of a rate-limit or resource bound rather than treating the endpoint as complete."
  condition: "Implementing a new or modified user-facing endpoint that triggers an expensive downstream operation (external API call, LLM call, file/media processing, large DB write), with no rate-limit or quota requirement stated in the request."
  reason: "The agent optimizes for satisfying the literal feature request; unstated non-functional requirements like abuse-resistance don't surface on their own because nothing in the prompt names them. A human with incident-memory of a past cost-overrun or DoS would flag it unprompted — the agent has no equivalent memory to draw on. The endpoint isn't 'vulnerable' in any checkable sense, it's just unbounded, which is a scope-completeness judgment, not a code pattern."
