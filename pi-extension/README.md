# praxis on Pi — status after the conductor cutover

**The front-door Pi extension is retired.** This directory used to hold a Pi-native port of the
praxis *front door* — a single extension (`praxis/index.ts`) that registered `begin_work`,
`compose_spawn`, `praxis_spawn`, `close_work`, `work_status` as native Pi tools, shelled to
`praxis/front-door/cli.py`, and delegated the edit gate to `praxis/scripts/gate.py`.

That whole surface was superseded by the **conductor cutover** (see `docs/CONDUCTOR-PLAN.md`):
the front door was removed, `conductor/` became `praxis/`, and the one orchestrator is now the
judgment-agnostic conductor (event-log journal, provider seam, DAG planner, pull-handoffs,
verification gate, gap accretion). `praxis/front-door/cli.py` no longer exists, so the old
`index.ts` could not run; it was `git rm`'d and is recoverable from git history for reference
(its gate delegation and native-spawn patterns are the useful parts of any future port).

## The Pi path now

Pi is an MCP client, and the new praxis surface is a plain MCP server — the *same* one Claude Code
registers. So Pi gets full parity by registering it, no bespoke extension required:

```
# the praxis conductor MCP server (plan / next_handoff / conduct / conductor_status /
# conductor_gaps / conductor_mint):
python3 ~/jdev/skills-pi/praxis/mcp_server.py
```

The **edit gate** is the shared, journal-first `praxis/scripts/gate.py` (a pure function of
`praxis/journal.open_unit`) — the same implementation the Claude Code shell hook calls. A Pi
`tool_call` handler that blocks `edit`/`write` until an open unit authorizes it is a thin wrapper
over `gate.py check --root <root> --file <path>` (allow / deny / no_unit), and a `tool_result`
handler on `read` records the payload read via `gate.py mark-payload-read` — but note the conductor's
own `pull` (`next_handoff`) already records that read when it hands over a unit, so the gate opens
for a self-advancing agent without a separate stamp.

## Future work — a Pi-native conductor extension (optional)

The MCP server gives Pi functional parity today. A Pi-*native* extension would only add the Pi-only
niceties the old front-door extension had, re-derived for the conductor model:

- native isolated spawns for each DAG unit (vs the MCP `plan` driving isolated `claude`/`pi` children);
- in-context judgment delivery (inline injection of the composed handoff) instead of a subprocess;
- an ambient status line folded from the journal (`views.ledger` + `journal.fold`).

None of these are required to use praxis on Pi — they are optimizations. Start from the retired
`index.ts` in git history for the gate/spawn plumbing, and register the tools against
`praxis/conduct.py` (`run_tasklist`, `next_handoff`, `run_task`) instead of the deleted front-door CLI.
