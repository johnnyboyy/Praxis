---
subject: coding
posture: guardrail
units-of-work: [migrate-dependencies]
universal: false
---

# Domain: dependency-management

Judgment for tasks whose actual subject is upgrading, migrating, or auditing dependencies — not
feature work that happens to touch a dependency in passing. Composed instead of `coding-general`
for this task shape: a task's coding-general judgment applies to every coding task regardless of
shape, but upgrade/migration judgment only applies when the task is actually about that. Audit
metadata lives in `domains/audit.md`, loaded only at ratify/retrospective time.

Read `.corpora/config.md` first, for registered utilities and verification commands. Run the
project's verification commands before finishing. Report a `tradeoffs` block for any migration step
where cost clearly outweighs value, rather than proceeding or skipping silently.

```yaml
last-retrospective: 2026-07-22

principles:

- id: adopt-forced-migration-early-on-disposable-branch
  rule: "When a platform or framework sets a hard cutover date for a breaking architectural change (support for the old path ends on a named future release) but the change is still optional now, adopt it early on a disposable test branch rather than deferring to the deadline. Assess feasibility by temporarily removing or swapping out dependencies suspected of incompatibility to isolate what actually breaks, instead of reading changelogs and guessing."
  condition: "A framework or platform announces a mandatory architectural migration with a stated future cutoff while the current version still allows opting out."
  reason: "The real breakage surface of a large architectural change — especially one touching low-level internals a project doesn't control — is only discoverable by actually running the project against it, not by reading migration docs. Waiting until the deadline converts a bounded, correctable investigation into a forced, time-pressured cutover. A disposable branch makes the experiment free to abandon and cheap to repeat as dependencies update."
  domains: [dependency-management]
  see-also: expo-filesystem-migrate-once-feature-gaps-close, version-conditioned-workarounds-reopen-at-upgrade

- id: audit-transitive-dependencies-after-major-upgrade
  rule: "If code imports a package never added directly to the project's own dependency manifest — it worked because a parent dependency happened to include it — declare it explicitly rather than relying on the transitive resolution, and re-audit for this specifically after any major upgrade of a dependency it comes through."
  condition: "A dependency upgrade, especially a framework's own major version bump, removes an internal dependency that other packages had been quietly relying on without declaring it."
  reason: "A framework can stop bundling a package it previously included transitively; projects that imported it directly without listing it in their own manifest get module-not-found errors with no obvious link back to the upgrade, because nothing in their own dependency list changed — the removal happened one level up, invisible to their own diff. The fix (declare it explicitly, or migrate off it) is cheap, but only if caught by intentional audit rather than by a production stack trace with no clear cause."
  domains: [dependency-management]

- id: version-conditioned-workarounds-reopen-at-upgrade
  rule: "Every version-conditioned decision in a project — a pin, a patch, an install-exclude, a compat or fallback flag, a deferred migration, an interop shim kept because the new API could not yet do something — carries an implicit expiry condition and no mechanism that rechecks it. At every SDK, framework, or major-dependency upgrade, inventory all of them and re-judge each against the new version: remove or complete the ones whose blocking reason the upgrade closed."
  condition: "Planning any SDK, framework, or major-dependency upgrade — before executing it, as part of scoping what the upgrade includes."
  reason: "A workaround is correctly in place only while its blocking condition holds, but nothing prompts a recheck, and each one silently keeps the project on stale dependency resolution, stale patched source, or a stale API past the point the real fix shipped — the unreviewed-ceiling-comment failure shape, at the dependency layer. The upgrade is the one event that systematically moves these conditions, so it is the anchor: the recheck is part of what an upgrade is, not an optional cleanup after one."
  domains: [dependency-management]
  see-also: adopt-forced-migration-early-on-disposable-branch, expo-filesystem-migrate-once-feature-gaps-close, terminal-checkpoint-pass

killed:
```
