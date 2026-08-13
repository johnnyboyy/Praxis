#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import units  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import journal  # noqa: E402

def _rel(root: Path, abs_file: str) -> str | None:
    try:
        return str(Path(abs_file).resolve().relative_to(root))
    except ValueError:
        return None

def gate_decision(root: Path, abs_file: str) -> tuple[str, str | None]:
    try:
        unit = journal.open_unit(root)
    except Exception:
        return "no_unit", None
    if unit is None:
        return "no_unit", None

    last = unit["last"]
    uow = last.get("unit_of_work", "unknown")
    rel = _rel(root, abs_file)
    surface = last.get("surface")
    if rel is not None and not units.surface_allows(surface, rel):
        surface_list = ", ".join(surface or [])
        return "deny", (
            f"Out of lease surface: the open unit (unit-of-work: {uow}) authorizes edits only "
            f"within [{surface_list}] plus praxis bookkeeping — {rel} is outside that, i.e. a "
            f"DIFFERENT unit of work. Call begin_work for the unit whose work this edit is "
            f"(close_work first if this unit's output is delivered); do not continue the current "
            f"frame into it.")

    delivery = last.get("delivery")
    if delivery in ("file", "spawn") and not last.get("payload_read"):
        if delivery == "spawn":
            return "deny", (
                f"This root ({root}) is framed for a SPAWN (unit-of-work: {uow}) — call "
                f"compose_spawn, Read the payload it writes, and inject it into the Agent prompt. "
                f"The payload read is required before any edit; editing here without it is the "
                f"inline path wearing spawn's clothes.")
        payload = last.get("payload") or "the frame payload file"
        return "deny", (
            f"begin_work ran for this root ({root}) but its domain payload has not been read in "
            f"this session — Read {payload} in full first; it is the judgment this work runs "
            f"under.")

    return "allow", None

def mark_payload_read(root: Path) -> bool:
    unit = journal.open_unit(root)
    if unit is None:
        return False
    journal.append(root, "unit.note", unit=unit["unit"], payload_read=True)
    return True

def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="gate", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_check = sub.add_parser("check", help="gate decision for an edit")
    p_check.add_argument("--root", required=True)
    p_check.add_argument("--file", required=True)

    p_read = sub.add_parser("mark-payload-read", help="record the payload read for the open unit")
    p_read.add_argument("--root", required=True)

    args = ap.parse_args(argv)
    root = Path(args.root).resolve()

    if args.cmd == "check":
        verdict, reason = gate_decision(root, args.file)
        print(json.dumps({"verdict": verdict, "reason": reason}))
        return 0

    if args.cmd == "mark-payload-read":
        marked = mark_payload_read(root)
        print(json.dumps({"marked": marked}))
        return 0

    return 1

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
