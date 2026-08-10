# Phase: routing

The routing judgment: given a framed task, decide the **unit-of-work**, the **stance**, and the
**execution shape** (inline / resume / isolate). This is *the* "I am the orchestrator" decision — so
it is deliberately thin: it reads almost entirely from `route.py` facts and `framing.md`'s
proportionality, and adds only the choices a fact cannot make. It never composes and never executes;
it selects, and hands the selection forward.

**Entry condition:** a task that has passed `framing` and is a *single* unit of work to route (not a
trivial inline edit that framing already dispatched, and not a spanning task — a spanning task's
verdict is `decompose`, which routes each piece here separately, one per root). Routing fires **per
unit of work**: crossing into a new unit is itself a routing point, never something to fall through
inline. That rule is the mitigation for the failure that killed the last praxis.

**Stance:** convergent. Routing narrows to one unit, one stance, one shape; it is not generative.

**Invocations:** none of its own. Composition is the *next* phase's engine call (GO-3), invoked only
after the unit-of-work is decided here — routing produces the decision that composition consumes.

## Deterministic facts — run first (they can't be wrong)

```
praxis/scripts/route.py --from <base> --target <path> [--files a,b] \
    --unit-of-work <uow> [--workstream <id>]
```

`route` bundles, as fact (it runs `frame` for the first three and adds the rest):

1. **Governing root** and, if the files span roots, the `decompose` verdict — *isolate per root*,
   handed to each; a single agent never straddles two roots.
2. **Composition availability** — whether the engine returned a domain set for the unit-of-work
   (composition itself is GO-3's; routing only needs to know it will resolve).
3. **Execution-shape signals** — `spans_multiple_roots` (→ isolate), and the workstream **ledger**
   state (`exists` → a *resume* candidate; `absent`/`unknown` → *new*). These are read via the
   generic engine capability, degrading to `unknown` when the engine is absent — the root facts still
   stand, and routing still decides.

## The judgment — three choices a fact cannot make

- **Unit-of-work.** Pick the one unit this task is. The candidate follows from framing's sizing (a
  one-property change is one small unit; a vague multi-part goal was already decomposed by framing
  into units, each routed here). This is the decision composition depends on — choose it before
  invoking the engine, never after. If the unit is genuinely ambiguous, that is a framing gap: route
  back to disambiguation, do not guess a unit to make the composition resolve.
- **Stance** — convergent / divergent / none. Read it from the unit-of-work's nature (a spec/decision
  with a right answer is convergent; open design exploration is divergent; a mechanical materialize is
  none), consistent with how the composed domains declare their own stance.
- **Execution shape** — pick from the signals:
  - **isolate** when `spans_multiple_roots` (the `decompose` verdict): stop, hand one unit per root to
    `interop`. Not a choice so much as an obligation the fact imposes.
  - **resume** when the workstream ledger `exists`: this unit continues an open workstream; carry its
    id so the chunk ledger threads (GO-6 close is ordered by `chunk_ledger`). The proportionality is
    framing's — resuming is not a licence to re-open settled scope.
  - **inline vs spawn** for new work: **spawn is the default.** A spawn's death is the unit's
    structural close-out — its context cannot carry one phase's judgment into the next, which is
    the failure mode inline invites (observed live: an entire implementation continued inline
    under a design composition). Inline is the explicit exception, chosen only when the operator
    asked for inline work or framing sized the unit trivial (one surfaced assumption); it must be
    declared (`execution="inline"`), never fallen into. Routing records which, so the loop
    conductor knows whether a spawn+handoff is owed.

## Route *to* the irreducible judgments — never automate them

Routing selects; it must not pre-empt the decisions the judgment engine keeps as live judgment. It
routes *to* the ratify gate's **domain-assignment** decision, it does not assign domains; it routes
*to* composition, it does not compose. The ordering invariants already captured elsewhere
(`chunk_ledger` close order, the migration verify-gate) are the loop's to enforce, not routing's to
re-implement.

**Artifact:** a *route* — the chosen unit-of-work, its stance, and the execution shape (isolate /
resume-with-workstream-id / new-inline / new-spawn), ready for GO-3 (compose + brief) or, for a
spanning task, for `interop`. One unit of work in, one route out — the boundary at which the
"one unit = one spawn = one handoff" invariant is committed to.

**Surfaced/lacking:** an ambiguous unit-of-work is a framing gap surfaced late — route back, don't
guess. A `ledger: unknown` when a resume was expected (engine unavailable) is surfaced as a fact the
operator confirms before treating the unit as new. A spanning task with no interop root to enter at
(from `frame`) surfaces the same unmet need `interop` reports: a root must be defined first.
