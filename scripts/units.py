#!/usr/bin/env python3
"""units — the lease declarations for a root's units of work: per unit, the EDIT SURFACE (which
paths that kind of work may write) and the OUTPUT (the deliverable whose delivery ends the unit).

Part of praxis-core. The frame marker and session stamp prove *that* a unit was framed; the lease
declares *what that unit's work may touch*, so the edit gate can bounce the first out-of-surface
write.

Declarations live in `<root>/.praxis/units.md` (legacy `praxis/units.md`), root-authored like
`config.md` — process metadata, not judgment, so it is praxis-side even though the unit *names*
are engine vocabulary. Format: one `## <unit-of-work>` section per unit, with `edit-surface:`
(comma-separated glob patterns matched against the root-relative path; `*` crosses `/`, so fnmatch
here and bash-`case` in the gate hook agree) and `output:` (prose — the deliverable). Everything
else in the file is prose and ignored.

Fail-open throughout: no units.md, or a unit with no section, means NO surface restriction — the
lease narrows known units without blocking vocabulary the file hasn't caught up to. Paths under
the root's praxis dir itself (`.praxis/`, `praxis/`) are always in-surface: process bookkeeping
(ledger, handoffs, payloads) is never out-of-phase.

Usage:
  units.py list  --root ROOT [--json]              show the declared leases
  units.py check --root ROOT --unit UOW --file F   exit 0 in-surface / 2 out-of-surface
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import root_tree as rt  # noqa: E402

UNITS_NAME = "units.md"


def units_path(root: Path) -> Path:
    return rt.praxis_dir(root) / UNITS_NAME


def parse_units(text: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    current: str | None = None
    for line in text.splitlines():
        heading = re.match(r"##\s+(\S+)\s*$", line)
        if heading:
            current = heading.group(1)
            out[current] = {"edit_surface": None, "output": None, "execution": None}
            continue
        if current is None:
            continue
        if line.startswith("edit-surface:"):
            globs = [g.strip() for g in line.split(":", 1)[1].split(",") if g.strip()]
            out[current]["edit_surface"] = globs or None
        elif line.startswith("output:"):
            out[current]["output"] = line.split(":", 1)[1].strip() or None
        elif line.startswith("execution:"):
            out[current]["execution"] = line.split(":", 1)[1].strip() or None
    return out


def load_units(root: Path) -> dict[str, dict]:
    path = units_path(root)
    if not path.is_file():
        return {}
    try:
        return parse_units(path.read_text())
    except OSError:
        return {}


def lease_for(root: Path, unit_of_work: str | None) -> dict | None:
    if not unit_of_work:
        return None
    return load_units(root).get(unit_of_work)


def surface_allows(surface: list[str] | None, rel_path: str) -> bool:
    if surface is None:
        return True
    if rel_path.startswith((".praxis/", "praxis/")):
        return True
    return any(fnmatch.fnmatch(rel_path, pattern) for pattern in surface)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="units", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_list = sub.add_parser("list", help="show the declared leases")
    p_list.add_argument("--root", required=True)
    p_list.add_argument("--json", action="store_true")
    p_check = sub.add_parser("check", help="is a file inside a unit's edit surface?")
    p_check.add_argument("--root", required=True)
    p_check.add_argument("--unit", required=True)
    p_check.add_argument("--file", required=True)
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    if args.cmd == "list":
        units = load_units(root)
        if args.json:
            print(json.dumps(units, indent=2))
        elif not units:
            print(f"no lease declarations ({units_path(root)} absent or empty) — "
                  f"every unit unrestricted")
        else:
            for unit, lease in units.items():
                surface = ", ".join(lease["edit_surface"]) if lease["edit_surface"] \
                    else "(unrestricted)"
                print(f"{unit}\n  edit-surface: {surface}\n"
                      f"  output: {lease['output'] or '(undeclared)'}")
        return 0

    given = Path(args.file)
    absolute = given if given.is_absolute() else root / given
    try:
        rel = str(absolute.resolve().relative_to(root))
    except ValueError:
        print(f"out-of-surface: {args.file} is not under {root}")
        return 2
    lease = lease_for(root, args.unit)
    surface = lease["edit_surface"] if lease else None
    if surface_allows(surface, rel):
        print(f"in-surface: {rel} (unit: {args.unit}, "
              f"surface: {', '.join(surface) if surface else 'unrestricted'})")
        return 0
    print(f"out-of-surface: {rel} — unit '{args.unit}' authorizes only: {', '.join(surface)}")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
