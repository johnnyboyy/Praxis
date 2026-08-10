# Phase: session

The loop conductor: given a task source (a tasklist, a plan's task files, or a workstream's own
recorded `next` pointers), run unit of work after unit of work — frame → route → compose → spawn →
close — until the source is exhausted or a halt signal fires. This phase adds **no new judgment and
no new machinery**: every step it takes is an existing phase or script, invoked in the order the
front door already defines. Its one job is deciding, after each close, whether to take the next unit
or stop loudly — and it is deliberately boring: sequential, one unit at a time, no re-planning, no
parallelism. Cleverness here is how the last conductor died.

**Entry condition:** more than one unit of work is queued for the same root — a tasklist handed in,
a plan whose artifact is a set of task files, or a resumed workstream whose ledger carries `next`
pointers. A single unit does not need a session; it is just the front door once.

**Stance:** none. The session composes and spawns stanced work; the conductor itself only sequences.

**Invocations:** none of its own. Composition and spawning happen inside each iterated unit, through
the same phases (`routing`, then compose + spawn) they always go through. The conductor never calls
the engine directly.

## Deterministic facts — between every two units

```
praxis/scripts/chunk_ledger.py next --root <root> --workstream <ws>   # the recorded next pointer
praxis/scripts/route.py --from <base> --unit-of-work <uow> --workstream <ws> [--files …]
```

1. **The next unit.** `chunk_ledger next` prints the last closed chunk's `next:` pointer (exit 0) or
   says why there is none (exit 1: absent ledger, empty ledger, at rest). When it has no pointer,
   the **task source** names the next unit — the ledger never invents work, and the conductor never
   guesses. Task source order is the operator's; the conductor takes units in the order given.
2. **The previous unit actually closed.** The chunk-done-before-handoff-close gate already enforces
   this; the conductor's rule is only that it never starts unit N+1 while unit N's handoff is still
   open. One unit of work = one spawn = one handoff, serially.

## The loop

For each unit, in order:

1. **Frame + route it** — the ordinary front door (`route.py`, then `phases/routing.md`'s judgment).
   Framing's proportionality still applies per unit: a trivial unit runs inline, a bounded one
   spawns. Being inside a session is not a licence to skip framing, and not a licence to balloon.
2. **Compose, spawn, hand off** — the ordinary steps 3–4 of the front door. The spawn's brief
   scopes its self-checking to its own slice; the authoritative verification is the conductor's
   (step 3), so concurrent implementers are never each driving the shared tree's suites.
3. **Verify — the conductor's own pass, never the spawn's report.** Re-run the suites and drive
   the changed behavior against the actual tree before reading the handoff's claims
   (`verification-stays-with-orchestrator`, the routing domain). Record the outcome on the chunk
   close (`--tier`, recording which tier the spawn ran on; `--verification clean|defects-found`) —
   this is the evidence `model-tier-by-task-complexity` needs to ever be tuned, and `defects-found`
   plus the fresh debug-issue spawn below is the normal path, not a failure to hide. A defect found
   here routes to a **fresh spawn** as its own unit (`debug-issue`), never back into the finished
   implementer's context — its close-out already happened; reopening it is the mode-carryover this
   system exists to prevent.
4. **Read the handoff's `status` and `Surfaced` section, then decide:**
   - `complete` with an empty `Surfaced` → close the chunk (`chunk_ledger close`, recording `--next`
     when the task source already names the following unit, and optionally `--tier`/`--verification`
     — see step 3) and continue.
   - `complete` with a non-empty `Surfaced` → judge it: a note that doesn't change the remaining
     units is carried into the session report and the loop continues; anything that invalidates or
     reorders remaining work is a **halt**.
   - `blocked`, `questions-pending`, or `tradeoffs-pending` → **halt.** These statuses exist to
     reach the operator; a conductor that answers them itself is a spawn straddling the operator's
     seat. Close nothing past the gate, stop, and escalate.
5. **Halt means stop loudly, not pause quietly:** report which units closed, which unit halted the
   loop and why (the status or the surfaced item, quoted), and what remains untouched. The ledger
   plus the still-open handoff are the resume point — a later session re-enters with the same
   workstream id and the `resume` signal fires on its own.

## What the conductor must never do

- **Answer a question a spawn surfaced.** Questions and tradeoffs halt; only the operator advances
  them.
- **Re-plan mid-session.** A `Surfaced` item that invalidates remaining units is a halt and a
  re-framing, not an in-loop edit to the task source.
- **Batch closes.** Each unit closes before the next begins; the ledger's ordering gate is per-unit
  and stays that way.
- **Straddle roots.** A task source spanning roots was decomposed at framing; a session runs one
  root's queue. Cross-root units go through `interop`, each leg its own unit.

**Artifact:** the session report — units closed (from `chunk_ledger summary`), the halt (if any)
with its quoted cause, and what remains. The ledger and any open handoff are the durable state; the
report only narrates them.

**Surfaced/lacking:** a halt's cause is itself the surfaced item, relayed verbatim — the conductor
adds routing context (which unit, what remains) but never paraphrases a spawn's question into
something easier to answer. A task source whose next unit is ambiguous (two candidate units, no
stated order) is a framing gap: halt and ask, do not pick.
