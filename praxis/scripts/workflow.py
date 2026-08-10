#!/usr/bin/env python3
"""workflow — named, ordered phase sequences declared in <root>/.praxis/workflow.json.

    {
      "ship-feature": ["design-ux-flow", "implement-feature", "testing"],
      "hotfix":       ["fix-bug", "testing"]
    }

Keys are workflow ids; each value is the phases (unit-of-work names) in intended order. This is a
declarative TEMPLATE the operator edits and the planner/operator references. praxis tags each unit's
trace entry with its workflow + position, so the trace shows which phases — and which whole flows —
tend to stall vs deliver, and editing the array is how you change the intended flow.

Passive by design: nothing here forces execution order (that is the session loop's job). It only
declares intent and lets a unit locate itself within a flow (its index, and what phase comes next).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import root_tree  # noqa: E402


def _path(root: Path) -> Path:
    return root_tree.praxis_dir(Path(root)) / "workflow.json"


def load(root: Path) -> dict:
    """The root's declared workflows, or {} when none/unparseable (fail-soft)."""
    try:
        data = json.loads(_path(root).read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def info(root: Path, workflow: str, unit_of_work: str | None = None) -> dict | None:
    """Locate a unit within a declared workflow: the ordered phases, this unit's index, the phase
    that comes next, and whether the unit is even part of the flow. None if the workflow id is
    undeclared."""
    flows = load(root)
    if workflow not in flows:
        return {"workflow": workflow, "known": False,
                "known_workflows": sorted(flows.keys())}
    phases = flows[workflow]
    idx = phases.index(unit_of_work) if unit_of_work in phases else None
    nxt = phases[idx + 1] if idx is not None and idx + 1 < len(phases) else None
    return {"workflow": workflow, "known": True, "phases": phases,
            "phase_index": idx, "next_phase": nxt,
            "unit_in_workflow": (unit_of_work in phases) if unit_of_work else None}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="workflow")
    sub = ap.add_subparsers(dest="command", required=True)
    pl = sub.add_parser("list", help="list declared workflows")
    pl.add_argument("--root", required=True)
    pi = sub.add_parser("info", help="locate a unit within a workflow")
    pi.add_argument("--root", required=True)
    pi.add_argument("--workflow", required=True)
    pi.add_argument("--unit-of-work", default=None)
    args = ap.parse_args(argv)
    if args.command == "list":
        print(json.dumps(load(Path(args.root)), indent=2))
    else:
        print(json.dumps(info(Path(args.root), args.workflow, args.unit_of_work), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
