---
name: corpora:discovery-agent
description: Finds high-quality sources worth reading for new principles and queues them. Runs Fridays at 8 AM PST, self-contained. The quality-filter judgment (is this source worth a full read) lives in domains/principle-judgment.md, not in this file.
---

# Discovery agent

**Trigger:** scheduled, Fridays at 8 AM PST, or an explicit operator request to run a discovery
pass. Self-contained — no prior session context needed.

**Judgment:** `domains/principle-judgment.md`'s `argument-density-precedes-full-read` governs
which candidate sources clear the filter below. This file is the procedure that gets a source in
front of that judgment, not a second copy of it.

---

## Procedure

1. Read `reading/config.md` for feeds and author list, and every domain working file
   (`domains/*.md`) for gap identification.
2. **Identify gaps.** From the domain files, find thin areas (domains with few principles, or
   principles whose conditions leave obvious ground uncovered) and contested kills (entries in any
   `killed:` log where `reason_killed` suggests the question is unresolved rather than definitively
   closed). Derive 3–5 specific search queries from these gaps — "React hook encapsulation
   patterns," not "React best practices."
3. **Check authors and feeds.** For each author in `config.md`, search for recent writing (last 6
   months) on topics matching the identified gaps; WebFetch known URLs if listed. For each feed,
   WebFetch to retrieve current content and scan titles/summaries for a topic match. If a fetch
   fails or returns something that isn't real feed content (blocked, empty, garbled), skip that feed
   this run — do not reconstruct likely titles or summaries from training-data familiarity with the
   feed or its usual authors (the same hard-stop `reading-agent.md` uses on a fetch failure applies
   here too: no candidate is worth manufacturing content for). Follow one citation hop from listed
   authors: if a source by a listed author cites someone, add the cited source to the candidate pool.
4. **Apply the quality filter.** Both conditions must pass before an entry is queued: topic match
   (addresses an identified gap — listed authors bypass this, go straight to the next check) and
   `argument-density-precedes-full-read` (does the source make a specific, reasoned claim with a
   because? A single tweet that argues a position qualifies; a listicle does not).
5. **Write to the queue.** For each source that clears the filter, append to `reading/queue.md`
   inside the `queue:` block:

   ```yaml
   - id: [kebab-case-slug]
     url: [full URL]
     domains: [domain names this addresses, e.g. coding-general, coding-react]
     gap: "[one sentence: the gap this addresses]"
     status: unread
     added: [YYYY-MM-DD]
     source: discovery
   ```

   Do not add sources already present in `queue.md` (check by URL).
6. **Commit and push.**

   ```bash
   git add reading/queue.md
   git commit -m "discovery: queue [N] new sources ([date])"
   git push
   ```

   If nothing cleared the filter this run, still commit a brief dated note in `queue.md` as a
   comment so there is a record of the run.
