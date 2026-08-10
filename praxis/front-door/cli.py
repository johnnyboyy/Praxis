#!/usr/bin/env python3
"""cli.py — the praxis front door as a plain JSON-emitting CLI, the transport Pi's native
extension drives (and any caller that does not want the `mcp` package).

Mirrors server.py's four MCP tools as subcommands; each prints the core function's result dict as
JSON on stdout and exits 0 (a returned dict with an `error` key is still exit 0 — the error is
data the caller surfaces, not a process failure). This is deliberately dependency-free beyond the
praxis scripts: it never imports `mcp`, so Pi can shell to it with only python3 present.

    python3 cli.py begin-work   --unit-of-work implement-feature --target path --execution spawn
    python3 cli.py compose-spawn --unit-of-work implement-feature --target path
    python3 cli.py close-work    --search-base .
    python3 cli.py work-status   --search-base .

`--files` is comma-separated (the core splits it); every path arg is optional exactly as the tools
are. The session-stamp/gate bookkeeping the shell hooks used to own is done natively in the Pi
extension (it has the session id in-process); this CLI only runs the front-door logic and writes
the shared frame marker + payload files that both the CLI and the extension read.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

PRAXIS_SCRIPTS = Path(os.environ.get("PRAXIS_SCRIPTS")
                      or Path(__file__).resolve().parent.parent / "scripts")
sys.path.insert(0, str(PRAXIS_SCRIPTS))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import front_door_core as core  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="praxis-front-door-cli",
                                     description="praxis front door — JSON transport")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(p, *, needs_unit: bool, targeted: bool):
        if needs_unit:
            p.add_argument("--unit-of-work", required=True)
        if targeted:
            p.add_argument("--target", default=None)
            p.add_argument("--files", default=None, help="comma-separated")
        p.add_argument("--search-base", default=None)

    p_begin = sub.add_parser("begin-work")
    add_common(p_begin, needs_unit=True, targeted=True)
    p_begin.add_argument("--workstream", default=None)
    p_begin.add_argument("--execution", default=None, choices=["inline", "spawn"])
    p_begin.add_argument("--workflow", default=None)

    p_compose = sub.add_parser("compose-spawn")
    add_common(p_compose, needs_unit=True, targeted=True)
    p_compose.add_argument("--workflow", default=None)

    p_close = sub.add_parser("close-work")
    add_common(p_close, needs_unit=False, targeted=False)

    p_status = sub.add_parser("work-status")
    add_common(p_status, needs_unit=False, targeted=False)

    p_pre = sub.add_parser("preframe")
    add_common(p_pre, needs_unit=False, targeted=True)

    p_trace = sub.add_parser("trace")
    add_common(p_trace, needs_unit=False, targeted=False)

    args = parser.parse_args(argv)

    if args.command == "begin-work":
        result = core.begin_work(args.unit_of_work, args.target, args.files,
                                 args.workstream, args.execution, args.search_base,
                                 args.workflow)
    elif args.command == "compose-spawn":
        result = core.compose_spawn(args.unit_of_work, args.target, args.files,
                                    args.search_base, args.workflow)
    elif args.command == "close-work":
        result = core.close_work(args.search_base)
    elif args.command == "work-status":
        result = core.work_status(args.search_base)
    elif args.command == "preframe":
        result = core.preframe(args.target, args.files, args.search_base)
    elif args.command == "trace":
        result = core.trace(args.search_base)
    else:  # pragma: no cover — argparse required=True guards this
        parser.error(f"unknown command {args.command}")
        return 2

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
