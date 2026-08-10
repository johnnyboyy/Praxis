# Phase: prose-revision

Run a deliberate tightening pass over a piece of corpora-authored prose — a handoff `Artifact`, a
spec, a batch of freshly-drafted principles, a proposal, an operator-facing summary — against
`prose-craft` before it is finalized. Homes a real, recurring, previously-homeless behavior: the
"self-edit-tighten before finalizing, don't wait to be asked" pattern (verbosity and restated
phrasing accumulate under long context, and the fix is a revision pass the author should run
unprompted, not a thing the operator has to catch). `prose-craft` already carries the *judgment*
(its principle's condition is explicitly "writing **or refining**"); this phase is the *process* that
schedules that judgment as its own pass rather than trusting it to happen for free.

**Entry condition:** the finalize seam of any unit of work whose artifact is nontrivial prose the
author drafted this session — before a handoff is closed, a spec handed forward, a proposal set
submitted to the gate, or a long operator summary sent. Not every one-line message: the trigger is a
draft long enough to have accumulated restated ideas or padding (the author's own read is the test;
there is no token threshold to game). Also available on operator command, `revise-prose [target]`,
to tighten an existing document.

**Stance:** convergent — it converges an existing draft toward economy, it does not generate new
content or new judgment. A revision that discovers something genuinely new to *say* is out of scope:
that is fresh authoring, and any new *principle* it earns still goes through `proposals:` and the
ratify gate.

**Invocations:** the judgment engine composed for `revise-prose` — `prose-craft` (which rides along
universally in any project that imported this plugin) applied artifact-in-hand. No stack or design
domain is pulled in: this is about the prose, not its subject matter, exactly as `comment-cleanup` is
about the comment and not the surrounding code.

## Deterministic facts — run first

- none that are engine-owned. The scope is simply the named target, or the draft the finishing unit
  is about to hand forward — which the author already holds. There is no fact to compute before the
  judgment; the whole phase is the judgment pass. (A future deterministic aide — flag sentences that
  restate an already-named term, à la `prose-craft`'s `prefer-leading-word-over-restated-phrasing` —
  is a candidate praxis script, left unbuilt until the pattern is concrete enough to script without
  guessing.)

## The pass

- Read the draft once for its **restated ideas**: a qualifying clause re-explained long-form each
  time it recurs becomes a compact named term, reused (`prefer-leading-word-over-restated-phrasing`).
- Cut **padding that carries no judgment** — a sentence that only restates the prior one in different
  words, a preamble the reader does not need to reach the point, a caveat that negates nothing the
  rule itself turns on.
- **Preserve every load-bearing distinction.** Tightening is removing tokens that add no judgment,
  never collapsing two ideas that a future reader needs kept apart. A cut that changes what the prose
  *means* is not a tightening — leave it.

## Artifact

The tightened draft, in place — the same handoff/spec/proposal/summary, shorter, with no distinction
lost. This phase produces no separate document; its output is the finalized prose the finishing unit
hands forward.

**Surfaced/lacking:** if the pass reveals the draft is missing something (a genuine gap, not a
verbosity), that is a **finding** for the unit's `Surfaced` section, not something to invent-and-fill
here. If it earns a new principle about *how corpora writes*, that goes through `proposals:` to the
gate — `prose-craft` grows the same way any domain does.
