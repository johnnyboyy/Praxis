#!/usr/bin/env python3
"""praxis-front-door — the praxis front door as MCP tools, so framing is a tool call, not a
convention.

Why this exists: praxis's "frame before acting" rule was enforced by prose (advisory) plus a
PreToolUse hook reading a bare-timestamp marker — which proved a frame *ran*, not that its
composition ever reached the conversation. A tool call's return value lands in context by
construction; the companion hooks (`praxis-frame-stamp.sh` writing a session-keyed stamp,
`praxis-frame-gate.sh` requiring it) make "this session framed this root" the verified fact.

The logic lives transport-free in `front_door_core.py`; this file is only the FastMCP transport
over it. The core imports praxis scripts as library code and calls corpora's `compose` /
`spawn-parts` capabilities (via `engine.py`, from the manifest the governing root registers) to
build each frame. With no engine registered every tool degrades to root facts.

Delivery/lease/gate rationale, in brief: domain bodies are 60–140KB — above Claude Code's byte
threshold for inlining MCP results — so delivery is FILE-MEDIATED and hook-verified (payload →
`<root>/.praxis/.frame-payload.md`, a Read stamps delivery). SPAWN IS THE DEFAULT; inline is the
explicit exception, and cross-root inline is rejected. When `<root>/.praxis/units.md` declares the
unit, begin_work carries its edit surface and output; the gate denies edits outside the surface.

The Pi-native transport is `cli.py` (JSON on stdout, no `mcp` dependency) driven by the Pi
extension in `pi-extension/praxis/`; both transports share `front_door_core.py`.

Registered user-scope: `claude mcp add praxis-front-door -s user -- python3 <this file>`.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Source of record is <repo>/praxis/front-door/server.py; the deployed path under
# ~/.claude/mcp-servers/ is a symlink, which resolve() follows — so the sibling scripts dir is
# found wherever the repo lives. PRAXIS_SCRIPTS env overrides for tests.
PRAXIS_SCRIPTS = Path(os.environ.get("PRAXIS_SCRIPTS")
                      or Path(__file__).resolve().parent.parent / "scripts")
sys.path.insert(0, str(PRAXIS_SCRIPTS))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import front_door_core as core  # noqa: E402

from mcp.server.fastmcp import FastMCP  # noqa: E402

mcp = FastMCP("praxis-front-door")


@mcp.tool()
def begin_work(unit_of_work: str, target: str | None = None,
               files: list[str] | str | None = None, workstream: str | None = None,
               execution: str | None = None, search_base: str | None = None) -> str:
    """Praxis front door in one call: frame + route the unit of work, persist the frame when a
    workstream is named, and open the edit gate for this session (via the stamp hook).

    `execution` declares your routing decision: "spawn" (the default — a subagent implements;
    call compose_spawn, Read the payload it writes, and inject it into the Agent prompt) or
    "inline" (you implement here — an EXPLICIT exception, for work the operator asked to run
    inline or that framing sized trivial; the payload file carries the domain bodies to work
    under). Undeclared execution defaults to spawn: one unit of work = one spawn = one handoff,
    and the spawn's death is the unit's close-out. Inline is additionally REJECTED when the
    work's governing root differs from the seat (search_base's own governing root): a seat root
    holds judgment between roots, never works inside another root — cross-root work spawns, or
    the caller re-seats by declaring search_base=<that root>. `files`/`target` are the paths the
    task touches; `search_base` is the root-discovery base (defaults to cwd)."""
    return json.dumps(core.begin_work(unit_of_work, target, files, workstream, execution,
                                      search_base), indent=2)


@mcp.tool()
def compose_spawn(unit_of_work: str, target: str | None = None,
                  files: list[str] | str | None = None,
                  search_base: str | None = None) -> str:
    """The spawn-side counterpart of begin_work: compose the domain set for a unit of work and
    write the assembled spawn-prompt parts (stance frame, full domain bodies, handoff-read
    schema) to `<root>/.praxis/.frame-payload.md`, returning the path. Read that file and inject
    its content into the Agent prompt — the spawned implementer's judgment rides there, not in
    the parent."""
    return json.dumps(core.compose_spawn(unit_of_work, target, files, search_base), indent=2)


@mcp.tool()
def close_work(search_base: str | None = None) -> str:
    """Close out the current unit of work for the governing root: marks the frame marker closed so
    the next edit anywhere in the root requires a fresh begin_work, and the stamp hook clears this
    session's stamp. Marker hygiene only — the chunk ledger and handoff ceremony keep their own
    gates."""
    return json.dumps(core.close_work(search_base), indent=2)


@mcp.tool()
def work_status(search_base: str | None = None) -> str:
    """Read-only introspection: the governing root, the shared frame marker's contents and age,
    and which sessions currently hold a stamp for it."""
    return json.dumps(core.work_status(search_base), indent=2)


if __name__ == "__main__":
    mcp.run()
