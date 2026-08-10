# praxis + corpora — first-class Pi integration

This directory holds the **Pi-native** integration of the praxis process engine (and, through it,
the corpora judgment engine). It began as a faithful port of the Claude Code integration — one MCP
server plus three shell hooks — collapsed into a single Pi extension, and now goes beyond it with
Pi-only capabilities (native isolated spawns, in-context judgment delivery, ambient status).

This is the **Pi-dedicated fork** of the skills house (`~/jdev/skills-pi`), split from the
Claude-Code-hosted original (`~/jdev/skills`) so it can optimize for Pi without interop constraints.

## What it replaces

| Claude Code | Pi (this extension) |
|---|---|
| `praxis/front-door/server.py` (FastMCP server, stdio) | four native tools registered via `pi.registerTool()` |
| `praxis-frame-gate.sh` (PreToolUse gate) | a `tool_call` handler that blocks `edit`/`write` in a praxis root until this session framed it |
| `praxis-frame-stamp.sh` (PostToolUse) | in-process stamping when `begin_work`/`close_work` run |
| `praxis-payload-read-stamp.sh` (PostToolUse on Read) | a `tool_result` handler on `read` |

The brain is unchanged. All the tools shell to the **transport-free CLI**
`praxis/front-door/cli.py`, which runs praxis's python scripts and invokes corpora for composition
and spawn assembly.

Why the port is *cleaner* than the original: the whole session-stamp file dance existed only because
the Claude Code MCP server never received `session_id` while the hooks did. A Pi extension tool runs
**in-process** with `ctx.sessionManager.getSessionId()`, so `begin_work` stamps its own session
directly. The stamp/marker **files** are still written (same paths, same shape) so the CLI engine
room and the python test-suite interoperate unchanged.

## The tools

- **`begin_work`** — the front door. Frame + route a unit of work (governing root, size, composed
  judgment, assumptions), then open the edit gate for this session. `execution` is `spawn` (default)
  or `inline`. For inline work the composed judgment is **injected directly into the tool result**
  (Pi is in-process), so the parent works under it by construction — no separate payload read.
- **`praxis_spawn`** — run a unit of work as an **isolated `pi` subprocess** seeded with the composed
  judgment as its system prompt (`--append-system-prompt`, run with `-ne` so the child has no praxis
  gate — the parent's frame authorizes the whole unit). Returns the child's final message as the
  unit's handoff. One spawn = one unit = one handoff; the child dies with its context. The handoff is
  a **claim** — verification stays with the router.
- **`compose_spawn`** — the manual counterpart: compose + write the payload to
  `<root>/.praxis/.frame-payload.md` and hand you the path to inject yourself. Prefer `praxis_spawn`.
- **`close_work`** — end the unit; the next edit requires a fresh `begin_work`.
- **`work_status`** — read-only introspection of the frame marker and session stamps.

## Pi-only upgrades over the Claude Code port

- **In-context inline delivery (#1)** — the `.frame-payload.md` + Read + read-stamp dance existed only
  because Claude Code persisted oversized MCP results out of context. In Pi the extension is
  in-process, so `begin_work` injects the domain bodies straight into its own tool result; the gate
  no longer requires a payload read for inline work. Only `spawn` delivery keeps a read requirement
  (and `praxis_spawn` sidesteps that entirely by carrying the payload in the child's system prompt).
- **Native isolated spawn (#4)** — `praxis_spawn`, above. Replaces Claude's Agent-tool convention with
  a real subprocess; naturally enforces "verification stays with the router" (the child cannot leak
  context back). Same-composition spawns share a byte-identical system-prompt prefix → provider cache.
- **Ambient status (#2)** — a footer line (`praxis[root]: <unit> · <age>m`, or `UNFRAMED` / `STALE`)
  refreshed on `session_start` and after each tool call.
- **`renderResult` (#8)** — `begin_work` renders a compact TUI summary (unit · root · size · judgment ·
  warnings · gate) while keeping full detail in the tool `details`.
- **Judgment eviction on close (#7)** — the inline-injected judgment (7–140KB) is pruned from the
  outgoing LLM context once `close_work` fires, via the `context` event. It stays live for the whole
  span between `begin_work` and `close_work`; the stored transcript keeps the full record, only the
  model context is trimmed. Set `PRAXIS_DEBUG=1` to log evictions to `$TMPDIR/praxis-evict.log`.
- **Stance → runtime policy (#9)** — *how* a unit runs (the reasoning budget) is a praxis decision,
  not corpora's. `praxis/scripts/runtime_policy.py` maps the unit's stance (divergent = explore →
  more thinking; convergent = settle → standard) plus the size floor to a thinking level. It rides
  the `begin_work` / `compose_spawn` result as a `runtime` block; the extension **applies** it (child
  `--thinking` for a spawn, `setThinkingLevel` for inline, restored on `close_work`) and **audits**
  every applied decision to `<root>/.praxis/runtime-audit.log`, surfaced back through `work_status`
  (`runtime_audit`). Review/override per root in `.praxis/config.md` (`runtime-policy: off`,
  `runtime-thinking: <level>`); set `PRAXIS_NO_RUNTIME=1` to stop the extension applying it at all.
  The policy table in `runtime_policy.py` is the whole decision — edit it to change how units run.
- **Praxis mode / input-boundary framing (L1)** — opt-in (`/praxis on`, or `PRAXIS_MODE=on`). When on,
  an edit-intent ask is **pre-framed before the model responds**: an `input` handler runs the
  engine-light `preframe` (governing root, span verdict, size floor, phase inventory) and injects it,
  so the model frames up front and adopts the loop (`begin_work` → `praxis_spawn` → verify) instead of
  getting bounced by the gate mid-edit. Conservative: non-edit asks and asks outside a governed root
  pass through untouched, and the edit gate remains the backstop for anything the classifier misses.
  This is the shift from praxis-as-a-tool-you-call toward praxis-as-the-loop; `/praxis` toggles it,
  `/praxis status` reports it. `PRAXIS_DEBUG=1` logs each injection to `$TMPDIR/praxis-input.log`.
- **Workflow trace (task → unit-of-work → result/stall)** — the legibility layer. Every unit appends a
  line to `<root>/.praxis/trace.jsonl`: `frame` (begin_work), `spawn` (praxis_spawn, with the
  detected outcome), `close` (close_work). A **stall** is first-class: `praxis_spawn` asks the child
  to end with `praxis-status: <complete|blocked|questions-pending|tradeoffs-pending>` (+
  `praxis-surfaced:` when not complete), so a non-complete status is a *routed outcome*, not a
  guessed one. `/praxis trace` shows the deliver-vs-stall summary **by phase and by workflow** plus
  recent stalls; `work_status` carries the same. This is how you see which phases produce better
  results and where to spend effort.
- **Named workflows (`.praxis/workflow.json`)** — declarative, editable phase sequences:
  `{"ship-feature": ["design-ux-flow", "implement-feature", "testing"], "hotfix": ["fix-bug",
  "testing"]}`. Keys are workflow ids; the array is the phases in intended order. Pass
  `workflow=<id>` to `begin_work` / `praxis_spawn` and each unit's trace entry is tagged with the
  flow + its position, so the trace becomes an A/B surface across whole flows; a completed spawn also
  reports the *next phase* in the flow. Passive by design — editing the array changes the intended
  flow; nothing forces execution order (that is the session-loop's job, the L2 rung). `/praxis
  workflows` lists them; `praxis/scripts/workflow.py` is the loader.

## The edit gate

A `tool_call` handler intercepts `edit` and `write`. In a praxis-managed root (nearest ancestor with
`.praxis/config.md`) it blocks the edit unless **this session** has a fresh frame — and, for
`file`/`spawn` delivery, until the payload file has been read this session. Outside any praxis root
it is fully transparent. Fail-open on any ambiguity. Set `PRAXIS_HOOK_BYPASS=1` to disable.

## Install

Point Pi at the extension and (optionally) the two skills. In `~/.pi/settings.json`:

```json
{
  "extensions": ["/Users/<you>/jdev/skills-pi/pi-extension/praxis/index.ts"],
  "skills": [
    "/Users/<you>/jdev/skills-pi/praxis",
    "/Users/<you>/jdev/skills-pi/corpora"
  ]
}
```

Or drop a symlink for auto-discovery + hot-reload (`/reload`):

```bash
mkdir -p ~/.pi/agent/extensions
ln -s ~/jdev/skills-pi/pi-extension/praxis ~/.pi/agent/extensions/praxis
```

`pi` must be on `PATH` for `praxis_spawn` (it launches child `pi` processes).

Quick test without installing:

```bash
pi -e ~/jdev/skills-pi/pi-extension/praxis/index.ts -p -t work_status \
  "Call work_status and report the root field."
```

## Configuration (env)

| Variable | Default | Purpose |
|---|---|---|
| `PRAXIS_HOUSE` | the repo this extension lives in (symlinks resolved) | repo root holding `praxis/front-door/cli.py` |
| `PRAXIS_PYTHON` | `python3` | interpreter used to run the CLI |
| `PRAXIS_HOOK_BYPASS` | unset | set to any value to disable the edit gate |
| `PRAXIS_DEBUG` | unset | log judgment evictions (#7) to `$TMPDIR/praxis-evict.log` |
| `PRAXIS_NO_RUNTIME` | unset | set to any value to stop applying the stance→thinking runtime policy (#9) |
| `PRAXIS_MODE` | unset | `on` starts sessions in praxis mode (input-boundary auto-framing; L1) |

## Verify

```bash
# transport-free core + CLI (no mcp dependency needed):
python3 ~/jdev/skills-pi/praxis/front-door/cli.py work-status --search-base ~/jdev/skills-pi

# the python suites still pass with the extracted core:
cd ~/jdev/skills-pi/praxis && python3 -m unittest discover -s tests
```
