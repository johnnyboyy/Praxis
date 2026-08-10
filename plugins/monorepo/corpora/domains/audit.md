# Audit record — monorepo plugin's judgment face

Provenance and per-kill audit detail for the monorepo plugin's domain (`monorepo-coordination`).
Loaded only at ratify/retrospective time — never in a spawn's working context. Keyed by principle
`id`, each noting its `domain`. See `kernel.md`, "Storage: working vs audit."

```yaml
provenance:

# domain: monorepo-coordination
- id: root-config-describes-own-shape
  domain: monorepo-coordination
  provenance: "2026-08-07, motors-and-controls migration. The coordination root's config.md carried framework: next / has-ui: yes / styling: tailwind copy-pasted from a child app; the root has zero .ts/.tsx/.css files of its own. Composition at the root produced a full app-shaped pool for a location with no application code."

- id: child-root-work-runs-childs-own-gate
  domain: monorepo-coordination
  provenance: "2026-08-07, motors-and-controls migration. The kingdom/castle intent — each app sovereign over its own composition, ratify gate, and domain pool — was already served by route.py's spans_multiple_roots → decompose and root_tree.py's nested-root resolution; the failure mode observed was the root being treated as a fourth castle instead of a border."
  history:
    - date: 2026-08-07
      type: killed
      reason: "Container kill at the seeding session's own gate, on operator challenge (process hiding as a principle): the rule restated the coordination phase's hand-off step, which the same coordinate-work composition already delivers. The never-ratify-into-the-parent clause folded into the phase's step 3."

- id: coordination-pool-holds-only-composable-judgment
  domain: monorepo-coordination
  provenance: "2026-08-07, motors-and-controls session-start ledger reconciliation. Sixteen root-pool domains (coding-general with 21 of 43 principles removed, css, testing, security, and others) showed entries removed outside any retrospective, plus two unrecorded graduations in coding-ts — files accreted at a root where no unit of work composed them, so no gate ever fired to keep their ledgers honest."
```
