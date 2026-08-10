# Phase: comment-cleanup

Sweep a managed project's code comments against the `coding-general` comment-shape principles —
delete what is redundant, version-pin a real framework quirk, and queue everything else for a
concrete non-comment fix. Migrated from corpora `processes/comment-cleanup.md`. Every comment's
outcome is a judgment call (the `coding-general` comment-shape siblings, plus `testing` for what
counts as an adequate regression test); praxis composes that judgment and enforces the scoping and
no-behavior-change discipline. No praxis script yet — see the note below on the one candidate.

**Entry condition:** operator command only, `comment-cleanup [target]` (target is an optional dir or
file list; default is the whole source tree, tests excluded). Never automatic — same standalone
posture as architecture-scan.

**Stance:** convergent. Composition is `unit-of-work: cleanup-comments` — `coding-general` (the
umbrella `minimize-comments-prefer-self-documenting-code` plus its five comment-shape siblings) and
`testing`. Stack-specific domains are deliberately **not** pulled in — this is about the comment, not
the surrounding code style.

**Invocations:** the judgment engine composed for `cleanup-comments`. The per-comment classification
is that composition's judgment, applied comment by comment.

## Deterministic facts — run first

- `frame` for `cleanup-comments` — the governing root and its (deliberately narrow) composition.
- scope: the named target, else the whole source tree with test files/dirs excluded. Batch by
  directory for parallel review, keeping each batch's file list disjoint so parallel agents never
  edit the same file (a mechanical partition, not judgment).

## The test — every comment gets exactly one of three outcomes

1. **Delete now** — restates the code, decorative divider, past-bug/tradeoff narration with no live
   guard, or stale/actively wrong (verify against current code first).
2. **Rewrite now** — a genuine framework/library quirk that does not name the exact package+version;
   add the pin from the manifest. The only case that survives as a permanent comment.
3. **Queue for follow-up** — load-bearing but the fix is a real code change (missing regression test,
   magic number → named constant, invariant → type/assertion). Queue it in
   `.corpora/comment-cleanup-queue.md` with the concrete action; do **not** restructure inline. A
   queue entry that just says "keep" has failed — every entry names what makes the comment
   unnecessary. Functional pragmas (`eslint-disable`, `@ts-expect-error`, …) are left completely
   alone.

No behavior changes beyond the comment edits themselves. Verify with the project's
typecheck/lint/test commands — a comment-only edit should never break them.

**Artifact:** the edited comments and the reconciled queue file. Report counts (deleted / rewritten /
queued) per batch and total, any actively-stale comment corrected, and the queue's current size —
relayed verbatim, not a summary that hides the queue size.

**Surfaced/lacking:** the queue file is itself the deferred-work surface. **Migration note:** the
queue *reconciliation* (drop entries whose comment no longer exists, append new ones) is a candidate
future praxis script — see `MIGRATION-NOTES.md`; it is left as phase prose for now because "the
comment no longer exists" needs the judgment pass to establish.
