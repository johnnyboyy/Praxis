---
subject: process
posture: guardrail
units-of-work: [coordinate-work]
universal: false
---

# Domain: monorepo-coordination

Judgment about running a coordination root — a root whose children include other praxis roots.
The coordination phase (this plugin's praxis face) is the process; this domain is the judgment
that process composes for its `coordinate-work` unit. Seeded 2026-08-07 from the
motors-and-controls kingdom/castle migration; each principle below was earned there, not
authored speculatively. Audit metadata lives in `domains/audit.md`, loaded only at
ratify/retrospective time.

```yaml
last-retrospective: none

principles:

- id: root-config-describes-own-shape
  rule: "A coordination root's project-shape (.corpora/config.md) declares only what exists at that root itself — its workspace tooling's language and package manager, has-ui: no, framework/styling none unless the root itself has such code. Never copy a child app's shape up to the root."
  condition: "Bootstrapping or editing the .corpora/config.md of a root whose children include other praxis roots."
  reason: "Every domain's applies-when fires off these exact fields. An app's shape copied to the root composes a full app-shaped pool — css, framework domains, ui phases — for a location with no application code to apply them to, and library-init machinery (has-ui: yes) activates against a UI that isn't there. The children's shapes live in the children's own configs, where their gates actually fire."

- id: coordination-pool-holds-only-composable-judgment
  rule: "Import into a coordination root's domain pool only domains a unit that actually runs at that root would compose — coordination judgment, process judgment, and coding judgment scoped to the workspace tooling the root itself owns. Treat a full app-shaped pool at a coordination root as drift to remove, not history to preserve."
  condition: "Importing, bootstrapping, or auditing the domain pool of a root whose children include other praxis roots."
  reason: "A domain no unit at this root ever composes is a file no gate ever fires for — its ledger can only be reconciled by hand and its content can only be edited outside a retrospective, which is exactly the drift the ledger exists to catch. The tempting default is the opposite: import everything the shape matches, on the theory that extra judgment is harmless. It isn't — ungoverned files are where drift accumulates."

killed:

- id: child-root-work-runs-childs-own-gate
  rule: "A unit of work handed to a child root frames against the child root, composes from the child's own domain pool, and closes its handoff at the child's own ratify gate. Never compose the coordination root's domains for it, and never ratify its proposals into the coordination root's pool."
  kill_type: container
  reason_killed: "Process restated as a principle: the coordination phase's own hand-off step already states this sequencing, and mined-workflow-stays-a-workflow bars atomizing a phase's steps into rule/condition/reason form. The one clause the phase lacked — proposals ratify at the child's gate, never into the coordination root's pool — was folded into the phase's step 3; nothing weighable remains here that the phase doesn't already deliver to the same composition."
  killed: 2026-08-07
```
