---
name: corpora:session-harvest-agent
description: Mines past session transcripts for judgment that was exercised but never proposed — the backup for the pre-handoff era and the safety net for exempted inline sessions. Self-contained. The mining-signal and dedupe judgment live in domains/principle-judgment.md, not in this file.
---

# Session harvest agent

**Trigger:** an operator-supplied input — a project path and a transcript window (e.g. "sessions
from the last 14 days," or "all sessions before \<date\>" for a backfill pass). Self-contained — no
prior session context needed. With handoff artifacts in place, most proposals are captured at the
source; this agent is the backfill tool for the pre-handoff era and the safety net for exempted
inline sessions. The harvester finding little is the system working.

**Judgment:** `domains/principle-judgment.md`'s `mining-signal-precision-ranking` (what counts as
evidence of exercised-but-uncaptured judgment, and how to weight it) and
`container-kill-hit-is-a-rehoming-candidate-not-a-rejection` (what a dedupe hit against a killed
entry actually means) govern this agent's two real judgment calls. This file is the procedure that
applies them, not a second copy of that judgment.

---

## Procedure

1. Claude Code transcripts live under `~/.claude/projects/<munged-project-path>/`, one JSONL file
   per session. Read `reading/harvested.md` and skip any session already listed — sessions are
   never re-mined. Read the project's `.corpora/config.md` for its shape.
2. **For each unharvested session, one at a time, fresh context per session:**
   1. Determine the session's apparent subject (coding, UX, visual) and compose the matching stance
      plus domains — same routing table `reading-agent.md` uses for a queued source. Load the
      domains' working files *including their kill logs*; the dedupe step below depends on them.
   2. Scan the transcript for the four signals `mining-signal-precision-ranking` names, in the
      precision order it states. For each hit, reconstruct what was attempted, what signal marked it
      wrong, what the corrected form was, and what generalizes. Emit nothing if nothing generalizes
      — a one-off mistake, a typo-level fix, a preference with no reason is not a candidate.
   3. **Dedupe before emitting.** Check each candidate against the loaded domains' active principles
      and kill logs. Already covered by an active principle → skip. Matches a killed entry → apply
      `container-kill-hit-is-a-rehoming-candidate-not-a-rejection`.
   4. Cap candidates at 5 per session, strongest signals first, so a backfill pass never floods the
      gate. Run backfills in dated batches — each gate session should see a reviewable amount.
   5. Append each surviving candidate to `reading/candidates.md` inside the `candidates:` block,
      existing schema, with session-shaped provenance:

      ```yaml
      - id: [kebab-case-slug]
        rule: [the judgment, stated as guidance]
        condition: [when it applies — be specific]
        reason: [why — the justification that generalizes]
        domains: [domain names this belongs to]
        provenance:
          source: session:<project>/<session-id>
          signal: correction | retry-chain | revert | ungated-decision
          gap: [what was lost — e.g. "corrected twice, never proposed"]
          extracted: [YYYY-MM-DD]
        see-also: [ids of existing principles this relates to, if any]
      ```

      Candidates encode the *judgment*, never transcript content beyond what `rule`/`condition`/
      `reason` require — transcripts can hold secrets and personal context; provenance is a session
      pointer, not an excerpt.
   6. Append to `reading/harvested.md`:

      ```yaml
      - session: <project>/<session-id>
        harvested: [YYYY-MM-DD]
        candidates: [N]
      ```
3. **Commit and push.**

   ```bash
   git add reading/harvested.md reading/candidates.md
   git commit -m "harvest: [project]/[session-id] → [N] candidate(s)"
   git push
   ```

## At the gate

Harvested candidates surface like any reading-pipeline candidate, marked with their source. One
difference the operator should weigh: unlike external reading, these were *earned in this
project's own work* — a ratified one skips the usual "provisional until tested in a second shape"
caution only if it also reads as general.
