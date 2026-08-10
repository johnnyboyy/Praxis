# Phase: framing

The universal front door. Every task passes through framing before anything acts on it — but the
step's *output scales to the task*, so a one-property change costs one line and a vague goal earns a
full disambiguation. This is the phase that makes proportionality real and that surfaces the
assumptions being made before they're realized.

**Entry condition:** every task, before acting. Not skippable. (What *is* proportional is the depth of
what framing produces — see Proportionality.)

**Stance:** none for the deterministic facts; light convergent judgment for sizing and assumption
statement. Not generative.

**Invocations:** the registered judgment engine — invoked **only when sizing lands above trivial**
and genuine judgment remains: a disambiguation dialogue when the ask is ambiguous, or a composed
spawn when a real spec/decision is warranted. A trivial task invokes nothing.

## Entry — a raw ask or a targeted frame

There are two ways in, same deterministic facts underneath:

- **From a raw ask** (Stage 2 — nothing decided but a sentence): `route.py --ask "<the ask>"`.
  It runs frame+route and **degrades cleanly** — with no targets guessed there is no root to compose
  against, so it reports exactly what is still unresolved (which file(s), which unit-of-work) as the
  assumptions to settle. The raw-ask → targets/uow mapping is judgment; route is the deterministic
  frame around it and never invents targets. Pass `--target`/`--unit-of-work` as you guess them and
  the readout fills in.
- **From a targeted frame** (targets already known): `frame.py` / `route.py` directly (below).

The **engine slot is auto-resolved** from the task's own governing root — its `.praxis/config.md` (legacy `praxis/config.md` recognized) may
declare `engine-plugins: <path>`, else the convention `<root>/.praxis/engine/plugins` (where
`plugin_import` lands a manifest). So none of these need `--engine-plugins` passed by hand; pass it
only to override.

## Deterministic facts — run these first, always (they can't be wrong)

Gather them in one call:

```
praxis/scripts/frame.py --from <search-base> --target <path> [--files a,b] --unit-of-work <uow>
```

It returns, as fact:

1. **Which root governs this task** — and if the candidate files span more than one root, the verdict
   is **decompose**: it is N units of work, one handed to each root, and it is *not composed or acted
   on as one task*. A single agent never straddles two roots. Stop here and hand off per root.
2. **Composition** — the domain set for the task's unit-of-work, obtained by invoking the judgment
   engine (the engine composes; praxis relays). Composition is a fact only once the unit-of-work is
   decided — that decision is routing judgment (below); everything after it is fact.
3. **`size_signals` + `size_floor`** — the deterministic inputs the sizing judgment sits on
   (`target_count`, `roots_spanned`, `unit_of_work_known`, `composition_size`, `unrouted_count`) and
   the part of the size verdict facts alone can settle: `decompose` (spans roots), `underspecified`
   (no uow, unrouted targets, or no governing root — the trivial/execute path isn't reachable until
   these resolve), or `by-judgment` (facts are complete; the size is the phase's call).
4. **`assumptions`** — the confirmable statements the frame is acting on (which root, which uow,
   what's in scope), as data to relay before acting, not prose to re-derive each time.

If the engine is unavailable the root facts still stand — praxis does not depend on it. Only what
remains after these facts is judgment.

## Proportionality — the frame scales to the task

The step always runs; its *volume* is proportional to real ambiguity. `size_floor` settles the
deterministic part; the three sizes below are the judgment on top — and a floor of `decompose` or
`underspecified` is a hard gate, never sized past into "execute directly":

- **Trivial / unambiguous** — one property, one file, matches a pattern the library already
  documents. State the single assumption inline — *"changing the primary login button's background
  token from `X` to `Y`; say so if you meant a different button or property"* — then execute
  directly. No spawn, no questions, no plan. The assumption-relay **is** the disambiguation here.
- **Bounded but ambiguous** — one or two targeted questions (framed for a cheap answer; state a clear
  direction rather than manufacturing a false choice), then execute or a single composed spawn.
- **Vague / multi-part** — full disambiguation → planning → decomposition. This is the shape that has
  been working well; framing just makes it the *earned* path, not the default one.

The failure to avoid in both directions: ballooning "change the button color" into a UI/UX →
implementation pipeline, and jumping into a vague goal without surfacing what was assumed.

## Assumptions are always surfaced

Whatever the size, framing states the assumptions it is acting on **before** acting, so they can be
redirected before they're realized. This is the floor of the step — even the trivial case surfaces
its one assumption. `frame.py` emits the deterministic ones (root, uow, in-scope targets) as its
`assumptions` list; the phase adds any judgment-level assumption it made to *size* the task (see
Surfaced/lacking). Non-blocking for trivial (state and proceed, interruptible); blocking for larger
(state and wait).

**Artifact:** a *frame* — the governing root, the assumptions stated for redirection, the size
verdict, and the route taken. For a trivial task the frame is one or two inline lines proceeded past;
for a vague task it is the entry into disambiguation/planning.

**Persist it — Stage 3 (the backward trace).** A framed unit of work with a workstream persists its
frame: `route.py --persist --workstream <id>` (or `frame_store.py write`) appends it to
`<root>/.praxis/frames/<workstream>.md`. This is a *before-work* trace, distinct from the chunk ledger
(an after-work record) and kept even for units that never chunk. It APPENDS: a redirect re-frames and
lands beside the old frame, so the redirect leaves a trace. A re-framed (fresh) spawn reads it back
(`frame_store.py show --workstream <id>`) to see what was assumed and already composed — then
re-composes for the actual current task. The trace is for legibility, not a queue to resume a closed
unit from.

**Surfaced/lacking:** if the *size itself* is unclear — the request is ambiguous enough that you'd
have to assume its shape to size it — that is the signal to invoke disambiguation, not to guess a
size. Record any shape-assumption made to size the task as the first thing to confirm.
