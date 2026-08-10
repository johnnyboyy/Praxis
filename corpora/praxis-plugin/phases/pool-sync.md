---
name: corpora:pool-sync
description: The ordered sequence for bringing a project's domain pool up to date with the source pool — schema migrations first, then shells for new domains, then the candidate sync (adds, updates, kills, moves, supersedes), then the operator's gate review, then ledger re-baselining and verification. Every content change stays gate-mediated; only storage-format migrations apply mechanically.
---

# Pool sync

The step-by-step sequence for updating a project's `.corpora/domains` pool from the source pool
(this skill's own `domains/`, or any other pool the project imports from). Run it when the source
pool has changed since the project last synced — new principles, edited ones, kills, or
reorganizations — or when the project's SessionStart `verify` reports a stale schema. Everything
below except step 4 is deterministic; step 4 is the only judgment step, and it is the operator's.

**Entry condition:** operator command, or a SessionStart `verify` failure naming a stale
schema-version. Never automatic.

## 1. Schema migrations

```
corpus.py migrate
```

Runs every storage-format migration between the pool's `schema-version` stamp in config.md and
current, in order, and re-stamps. Idempotent; a current pool prints "already current." This is the
only step that writes without the gate: schema migrations change where things are stored, never
what judgment the pool holds. `verify` refuses to reconcile a stale pool until this has run, so a
symptom like "kill entries in the working file" always resolves to this one command.

## 2. Shells for new domains

For each source domain that matches the project's shape (`applies-when` against
`.corpora/config.md`) but has no file in the project's pool, create its empty container:

```
corpus.py adopt-domain-shell ...
```

Container only — frontmatter and empty sections, no principles, no audit entries. The judgment
arrives as candidates in the next step and enters through the gate like everything else
(`principle-judgment`'s dont-pre-author-judgment-when-scaffolding).

## 3. Candidate sync

```
corpus.py import-default-pool
```

Queues into `.corpora/import-candidates.md`, pending-deduped and re-runnable:

- **new** — source ids absent from the project pool.
- **`change: update`** — same id, source content differs.
- **`change: kill`** — source-side kills (read from the source audit's kill log) of ids still live
  here.
- **`change: move`** — the source relocated an id to another domain (read from the source audit's
  `history` stanzas, `type: moved`; the entry's current `domain:` is the destination) and this
  pool still holds it in the old one.
- **`change: supersede`** — the source consolidated/generalized an id away (`history` stanza with
  a `successor:` field) and this pool still holds the old id live.

Nothing is written to the pool by this step — it only stages.

## 4. Gate review (operator)

Review the queue; apply each approved candidate:

```
corpus.py ratify-import-candidate --id <id> [--as-domain <d>] [--as-id <id2>]
```

Each application does its own write-back, audit note, and ledger accounting atomically — moves
relocate across domains, supersedes remove in favor of the named successor. **A declined
supersede (or update, or kill) is legitimate divergence, not drift**: the same rule can be
ratified in one root and killed in the next, both correctly, and a project that deliberately kept
its own version of something the source consolidated should decline the candidate and leave it in
the queue's history — do not re-propose it as if the project missed it.

## 5. Re-baseline and verify

`ratify-import-candidate` keeps the ledger reconciled as it goes, so this is a check, not a
ceremony:

```
corpus.py verify
corpus.py lint-domains --domains-dir .corpora/domains
```

If the operator hand-applied anything outside the scripted paths during review, `retro-done
--domain <d>` re-baselines that domain knowingly. Green `verify` + clean lint is the exit
condition; the next SessionStart confirms it independently.
