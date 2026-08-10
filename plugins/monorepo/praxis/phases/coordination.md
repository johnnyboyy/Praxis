# Phase: coordination

Run a task that arrives at a root whose children include other praxis roots — the coordination
root. The root's job at this border is to frame, decompose, and hand off; the work itself runs
inside whichever child root owns it, through that child's own front door. Recursive by
construction: a child root that itself contains roots runs this same phase at its own border.

**Entry condition:** a task arrives at (or resolves to) a root containing child `.praxis` roots,
and the task either spans more than one child root or names an outcome no single child root wholly
owns. A task whose files all resolve to one child root is not this phase — `root_tree`'s
`nearest_root` already routes it there directly.

**Stance:** convergent — coordination is orchestration work; there is no anti-mean anchor.

**Invocations:** the registered engine's `compose` for the coordination root's own unit
(`coordinate-work`); each decomposed unit invokes nothing here — it enters its owning child root's
front door and composes there.

## Deterministic facts / steps — run as scripts, not by hand

1. **Map the border** — `root_tree.py find_roots` from the coordination root lists the child roots;
   `nearest_root` per touched file assigns each file to its owner. Which root owns which file is a
   fact, not a judgment.
2. **Frame at the coordination root** — `frame.py` (or `begin_work`) with the coordination root as
   base. A spanning task verdicts `decompose` / `isolate_per_root`; the frame lists one unit per
   child root touched.
3. **Hand each unit through its child's own front door** — the spawn for a child-root unit frames
   against the child root (`search_base` = the child), composes from the child's own domain pool,
   and its handoff closes at the child's own gate — its proposals ratify there too, never into the
   coordination root's pool. One unit of work = one spawn = one handoff, per child.
4. **Cross-root dependencies** go through `interop_handoff.py` and `phases/interop.md` — a
   bidirectional handoff between the two child roots, never a straddling agent.
5. **Root-only work** (workspace tooling, shared pipeline config — files owned by the coordination
   root itself) is an ordinary unit at the coordination root, composed from the coordination root's
   own pool.

## The judgment seam (not scripted)

- **Which child owns an ambiguous outcome** — a task named by goal rather than by files may
  plausibly land in more than one child; assigning it is the coordination root's judgment, informed
  by the `monorepo-coordination` domain.
- **Whether a task is genuinely cross-cutting** — or is one child's work wearing a broad
  description. Decomposing a single-child task adds ceremony without value; straddling a genuinely
  cross-cutting one violates sovereignty. The seam is deciding which it is.
- **Sequencing the decomposed units** — which child's unit must land first when an interop handoff
  links them.

**Artifact:** the decomposition — one framed unit per child root, each entered through its owner's
front door, plus any interop handoffs linking them.

**Surfaced/lacking:** a task that repeatedly resists clean decomposition at the same border is a
signal the border is drawn wrong — a candidate for moving code between roots or merging roots,
surfaced to the operator, never resolved by letting an agent straddle.
