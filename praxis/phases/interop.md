# Phase: interop

What happens when a task spans roots. Interop is not a special system — it is just **entering at the
right root** and letting the boundary decide what's done here versus defined-and-passed-off. `framing`
routes here whenever `frame` returns the `decompose` verdict.

**Entry condition:** a task whose candidate files span more than one root (`frame` verdict:
`decompose`).

**Stance:** none for the deterministic facts; convergent judgment for defining each passed-off piece.

**Invocations:** the judgment engine, per child root, when a passed-off piece carries real judgment
(composed exactly as any single-root unit would be — in that child's own context, never the parent's).

## Deterministic facts — run first

`frame` already carries them for a spanning task:

- **The interop root** — the deepest root that contains all the spanned roots; the only place with the
  context to coordinate both sides. This is where the task enters. (`root_tree.py interop --files ...`)
- **If there is none** — the spanned roots are siblings with no common-ancestor root — the task has
  **nowhere to enter**. It cannot proceed as one task until an interop root is defined at the common
  ancestor directory `frame` names. Stop and surface that: defining a root is an operator decision.

## The boundary decides done-vs-passed-off

Entering at the interop root, split the task by root membership — a deterministic fact, not a
judgment call:

- **A piece in a child root's scope** (its files resolve to that child) is **defined here and passed
  off**: write the child a task brief in *its* vocabulary, hand it off, and let it execute in its own
  context — its own composition, its own domains, its own handoff. The interop root does not reach
  into the child and do the work; it defines the contract and delegates. A single agent never
  straddles two roots (this is the same rule `frame` enforces, now as the interop discipline).
- **A piece that is the interop concern itself** — the contract *between* the children (a shared type,
  an API boundary, the sequence in which the children's pieces must land) — is done at the interop
  root, which is the only root whose scope that concern actually is.

Each passed-off piece is its own unit of work and produces its own handoff (the praxis invariant
holds per root, not per task). Those child handoffs return to the interop root, which composes the
result and — if anything a child surfaced turns out to belong to a *third* root or back to the
parent — passes that off in turn. That return path is how the roots communicate without any of them
knowing another's internals.

**The mechanism — a handoff addressed across roots.** A cross-root handoff carries two optional
fields the base schema declares: `addressed-to:` (the root it crosses to next) and `return-to:` (the
reply address the receiving root uses to address its own completion back). `interop_handoff.py
deliver <file>` reads `addressed-to` and **moves the handoff into that root's `.praxis/inbox/`** — a
mechanical file move, so no agent ever straddles two roots; only the handoff crosses. So the boundary
flow is: the interop root writes a brief (`addressed-to: <child>`, `return-to: <interop>`), delivers
it to the child's inbox; the child works in its own context and delivers its completion
(`addressed-to: <interop>`) back to the interop root's inbox; the interop root reads its inbox
(`interop_handoff.py inbox <interop-root>`) and composes. Deliver is the same verb both ways — the
direction is whatever the handoff's `addressed-to` names.

**Artifact:** the interop root's own handoff, embedding (by reference) each child root's returned
handoff, plus whatever interop-concern work it did directly.

**Surfaced/lacking:** a child piece that can't be defined without knowing something only another root
holds is itself an interop concern that surfaced late — route it the same way, don't let the child
guess. If the task had no interop root to enter at, that unmet need for a defined boundary is the
whole of what this phase surfaces.
