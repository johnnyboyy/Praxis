# Reading agent

Reads queued sources through the appropriate domain composition and extracts principle candidates.
Runs weeknights at 2 AM PST. Self-contained — no prior session context needed.

---

## Setup

1. Add and clone the corpora repo: `johnnyboyy/corpora`
2. Read `reading/queue.md`. Work: every `status: unread` entry, plus every `status: fetch-failed`
   entry that now has a matching `reading/saved/<id>.*` file or a `local-content:` field (skip
   `fetch-failed` entries with neither — they're still genuinely blocked, not retried on a timer).
   If nothing qualifies, exit — nothing to do.

## For each qualifying entry (one at a time, fresh context per entry)

### 1. Compose the stance and domains

From the entry's `domains` field, compose the spawn (see `kernel.md`, "Spawns: stance + composition"):
- `coding-general` → convergent, load `domains/coding-general.md`
- `coding-ts` → convergent, load `domains/coding-general.md` + `domains/coding-ts.md`
- `coding-react` → convergent, load `domains/coding-general.md` + `domains/coding-react.md`
- `ux-design`, `interaction`, or similar → convergent, load `wizards-flows`, `ranking-evaluation`,
  `validation-feedback`, `recoverability`, `lists-selection`, `forms-inputs`, `design-method`
- `ui-design` or similar → divergent, load `color`, `surfaces-elevation`, `visual-hierarchy`,
  `motion`, `validation-feedback`, `recoverability`, `lists-selection`, `forms-inputs`,
  `design-method`

You are now reasoning under that stance, with those domains, for this entry.

### 2. Fetch and read

Before fetching, check for a saved copy: `reading/saved/<entry-id>.html` (also try `.md`, `.txt`).
If found, read that file directly — skip WebFetch entirely, go straight to reading through the composition
below. If the entry instead has an explicit `local-content:` field (a saved copy under a different
name or location), read that file instead. Either way, no fetch is attempted once local content
exists.

Otherwise: WebFetch the URL. If the URL is unknown (flagged in the entry), search for it first.

**Hard stop on fetch failure — no substitute source, of any kind.** If the fetch errors
(non-success response, timeout, blocked, paywalled) or returns something that isn't the actual
article (a bot-block page, a stub, garbled content), stop working this entry immediately. This
covers both failure modes seen in this repo's own history: reconstructing the article from
training-data familiarity, and synthesizing an approximation from search-result summaries (the
`fetch-note:` pattern on some pre-2026-07-22 entries in `reading/queue.md`) — the second is less
lossy than the first but is still not the source itself, and still lets a candidate's provenance
claim a specific citation as its evidence when the model never actually read that citation. A
citation to a source that was never actually retrieved is worse grounding than no citation, because
it reads as more trustworthy than it is (see `principle-judgment` domain,
`reading-pipeline-provenance-flags-knowledge-risk`, and `LINEAGE.md`'s entry on this). Go to step 4
and record the failure instead of extracting anything.

Read through the loaded composition. For each claim:
- Does it confirm, extend, or contradict an existing principle? (Note the principle id.)
- Does it address a gap the composition's domains don't cover?
- Is it specific enough to encode as `rule` + `condition` + `reason`?

### 3. Extract candidates

For each principled claim worth encoding, append to `reading/candidates.md`
inside the `candidates:` block:

```yaml
- id: [kebab-case-slug]
  rule: [the judgment, stated as guidance]
  condition: [when it applies — be specific]
  reason: [why — the justification that generalizes]
  domains: [domain names this belongs to]
  provenance:
    source: [URL]
    gap: [the gap this addressed]
    extracted: [YYYY-MM-DD]
  see-also: [ids of existing principles this relates to, if any]
```

If the source yields nothing principled, write nothing. Do not force candidates from
weak material.

### 4. Mark the entry

On a successful read, update the entry in `reading/queue.md`:

```yaml
  status: read
  read: [YYYY-MM-DD]
  candidates: [N]
```

On a fetch failure (step 2's hard stop), update it instead with:

```yaml
  status: fetch-failed
  attempted: [YYYY-MM-DD]
  error: "[what happened: HTTP status, timeout, bot-block page, paywall, etc.]"
```

Leave `candidates.md` untouched for this entry — a `fetch-failed` entry is not retried
automatically on the next run; it waits for the operator to save a copy to
`reading/saved/<entry-id>.html` (or `.md`/`.txt`) — no status edit needed, step 2 checks that path
automatically on the next run — or resolve it another way, per `SKILL.md`'s ratify-gate surfacing
step.

## Commit and push

```bash
git add reading/queue.md reading/candidates.md
git commit -m "reading: [source-id] → [N] candidate(s)"
git push
```

If any entries hit a fetch failure this run, commit those too (`reading: [N] fetch failure(s)`) —
`status: fetch-failed` is itself the durable record; nothing else needs to happen in this agent.
