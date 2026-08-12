---
id: monorepo-coordination
# no owner: line — derived from the plugin source at discovery
#   in the `monorepo` plugin's domains_dir -> owner: monorepo
#   in root/.praxis/domains               -> owner: project
subject: process
posture: convergent
universal: false
applies-when: []
workflows: [coordinate-work]
---

principles:
  - id: root-config-describes-own-shape
    rule: A coordination root's project-shape declares only what exists at that root itself — its workspace tooling's language and package manager, has-ui no, framework/styling none unless the root itself has such code. Never copy a child app's shape up to the root.
    condition: Bootstrapping or editing the project-shape config of a root whose children include other praxis roots.
    reason: Every domain's applies-when fires off these exact fields. An app's shape copied to the root composes a full app-shaped pool — css, framework domains, ui phases — for a location with no application code to apply them to, and library-init machinery (has-ui yes) activates against a UI that isn't there. The children's shapes live in the children's own configs, where their gates actually fire.
  - id: coordination-pool-holds-only-composable-judgment
    rule: Import into a coordination root's domain pool only domains a unit that actually runs at that root would compose — coordination judgment, process judgment, and coding judgment scoped to the workspace tooling the root itself owns. Treat a full app-shaped pool at a coordination root as drift to remove, not history to preserve.
    condition: Importing, bootstrapping, or auditing the domain pool of a root whose children include other praxis roots.
    reason: A domain no unit at this root ever composes is a file no gate ever fires for — its ledger can only be reconciled by hand and its content can only be edited outside a retrospective, which is exactly the drift the ledger exists to catch. The tempting default is the opposite — import everything the shape matches, on the theory that extra judgment is harmless. It isn't, because ungoverned files are where drift accumulates.
