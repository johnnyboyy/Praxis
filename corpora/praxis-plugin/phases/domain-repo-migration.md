---
name: corpora:domain-repo-migration
description: One-time migration for a project bootstrapped under the old live seed/project domain merge, before it runs its first session under the no-merge model. Materializes what the live merge was already applying into the project's own .corpora/domains/, so nothing the project already relied on silently disappears. Never runs against this skill's own domains/.
---

# Domain repo migration

**Entry condition:** a project bootstrapped before `kernel.md`'s "Project corpora" section dissolved the
live seed/project merge is about to run a session under the no-merge model for the first time. One
time per project — once migrated, a project never needs this again unless it wants to pull in more
of the seed pool later, which is an ordinary `import-default-pool` re-run (`kernel.md`, "Import"),
not another migration.

Nothing about this trigger is automatic or time-pressured: a project that never runs `select`/
`emit-spawn-parts`/`manifest` again simply never notices the merge is gone. The trigger fires
the first time one of those commands would matter — the next real spawn.

**Composition:** none — this is a mechanical `corpus.py` step plus a verification read, not a
generative or convergent spawn. No domain corpus is loaded to perform it.

---

## Procedure

1. **Compute and materialize the effective set.** Run:

   ```bash
   corpus.py migrate-domains
   ```

   Source defaults to this skill's own `domains/`; override with `--source <path>` for a project
   migrating from a different domain repo (a monorepo's shared root, for instance). This does, in
   one pass, per domain:
   - Selects every source domain whose `applies-when` already matches this project's
     `.corpora/config.md` shape, or is `universal` — the same day-one pool `import-default-pool`
     would offer, not scoped to any one `unit-of-work` — **plus** every domain the project's own
     `.corpora/domains/` already has, even if its `applies-when` would no longer match today (a
     domain the project already accumulated judgment in is never silently dropped for a shape
     mismatch).
   - For each selected domain, merges the source's `conventions:`/`principles:` entries with the
     project's own existing entries (if any) into one working file, **project entries winning on
     id collision** — a project's own accumulated judgment for an id is never silently overwritten
     by the source's version of the same id.
   - Carries the domain's frontmatter (`subject`/`posture`/`applies-when`/`units-of-work`) over
     from whichever file already had it, project file first.
   - Preserves every migrated entry's existing `id` — nothing is renamed, split, or reworded.

   **Scoped to `conventions:`/`principles:` only — a domain's `killed:` log is not migrated.**
   This is a deliberate, documented gap, not an oversight: a killed entry's fields don't map onto
   the principle/convention schema, and the cost of the gap is low and self-correcting — if
   something already rejected upstream gets re-proposed once in the new project, the ordinary
   ratify-gate judgment (`domains/principle-judgment.md`, `container-kill-hit-is-a-rehoming-
   candidate-not-a-rejection`) catches it the same as any other re-proposed idea. Silently writing
   a plausible-looking but wrong killed-entry shape would be worse than this gap.

2. **This writes directly, bypassing the candidate/ratify-gate pipeline — on purpose.** Unlike
   `import-candidate`/`import-default-pool`, migration never asks the operator to re-approve each
   entry individually. The content being materialized was already live and already applying to
   every spawn this project ran before the merge dissolved — migration makes that explicit, it
   doesn't propose anything new. Re-running it through the gate would ask the operator to
   re-ratify judgment the project already operated under, for no benefit.

3. **Record provenance.** `migrate-domains` already appends a `provenance`/`history` entry per
   newly-materialized id to the project's own `.corpora/domains/audit.md` (`type:
   migrated-from-seed`, dated) — this happens automatically as part of step 1, not a separate
   manual step. A later reader can see this content arrived via migration, not a fresh
   proposal or import.

4. **Verify before trusting it.** Run:

   ```bash
   corpus.py measure
   corpus.py verify
   ```

   `verify` must report the ledger reconciled — the newly-materialized files register their
   current contents as baseline (nothing was "ratified" this session, so there is nothing to
   reconcile against). If `verify` reports a discrepancy, do not proceed; the migration did not
   complete cleanly. Also run `corpus.py lint-domains --domains-dir .corpora/domains` to confirm
   every migrated file's frontmatter and `conventions:` shape are still valid.

5. **Only after verification is clean does the project stop reading the live seed layer** — which,
   mechanically, it already has, the moment this project's own `corpus.py` is the one built after
   the dissolution (`select`/`emit-spawn-parts`/`manifest` never merged automatically once that
   shipped). This step is really: confirm nothing the project relied on silently vanished, not a
   separate cutover switch to flip.

---

## Rollback

This only ever writes to the project's own `.corpora/domains/` and `.corpora/domains/audit.md` — it
never touches the source domains-dir (this skill's own `domains/`, or whatever `--source` pointed
at). The migration is safe to re-run or abandon: the project's prior (pre-migration) state is
whatever was in `.corpora/domains/` before step 1, recoverable via git the same way any other
working-tree change is. Running `migrate-domains` again after a partial or aborted run is safe and
idempotent — it never overwrites an id already present in the project's own files, so a second run
only fills in whatever the first run didn't reach.

---

## What this is not

- Not a sync mechanism. A project that wants to keep tracking the seed pool's evolution after this
  one-time migration re-runs `import-default-pool` periodically (`kernel.md`, "Import") — an
  ordinary, individually-ratifiable candidate proposal, not another silent bulk write.
- Not a substitute for dogfooding the mechanism itself on a throwaway project first
  (`proposals/domain-repo-import.md`, open question) before trusting it against a project whose
  domain content actually matters.
