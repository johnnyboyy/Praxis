#!/usr/bin/env python3
"""root_tree — deterministic discovery of the tree of concern-boundaries ("roots") in a source tree.

Part of praxis-core, the process/orchestration layer. Two disciplines keep praxis decoupled from any
judgment engine it drives:

  1. Praxis never imports or invokes an engine. This script reads the filesystem and reports facts.
  2. A root is a directory carrying praxis's own config marker. `.praxis/config.md` is the standard
     (so a repo that SHIPS a praxis/ source tree can self-host without its source dir doubling as the
     marker); bare `praxis/config.md` stays recognized for existing roots. The marker set is
     configurable (`--marker`), so a project can add an engine's own config marker without any code
     change here.

A *root* is a boundary of concern: a directory meant to be reasoned about in isolation from its siblings
(FAMOUS app vs admin; motors circuit-builder vs marketing). The point is to make the root tree a **fact
produced before any routing**, never inferred: given a task (a path, or a set of touched files) the
caller asks which root(s) own it, and a task spanning two roots is two units of work — one handed to each
root — not one agent straddling both.

Commands:
  tree   [--from DIR] [--marker M ...] [--json]   discover every root under DIR, print the tree
  resolve PATH [--from DIR] [--marker M ...]       which root governs PATH (nearest ancestor root)
  span    --files a,b,c [--from DIR] [--marker M]  which roots a set of files spans (decomposition fact)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

DEFAULT_MARKERS = [".praxis/config.md", "praxis/config.md"]


def split_files(files: str) -> list[str]:
    return [f.strip() for f in files.split(",") if f.strip()]


def praxis_dir(root: Path) -> Path:
    root = Path(root)
    for name in (".praxis", "praxis"):
        if (root / name / "config.md").is_file():
            return root / name
    return root / ".praxis"

SKIP_DIRS = {
    "node_modules", ".git", ".next", ".turbo", ".expo", "dist", "build", "out",
    "coverage", ".venv", "venv", "__pycache__", "vendor", ".cache", ".parcel-cache",
    ".pytest_cache", "ios", "android", ".gradle", "Pods", ".claude",
}

NAME_RE = re.compile(r"^\s*name:\s*(.+?)\s*$", re.MULTILINE)


def find_roots(base: Path, markers: list[str]) -> list[Path]:
    roots: set[Path] = set()
    base = base.resolve()
    for dirpath, dirnames, _ in os.walk(base):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        here = Path(dirpath)
        for marker in markers:
            if (here / marker).is_file():
                roots.add(here)
                break
    return sorted(roots, key=lambda p: str(p))


def root_name(root: Path, markers: list[str]) -> str:
    for marker in markers:
        cfg = root / marker
        if cfg.is_file():
            m = NAME_RE.search(cfg.read_text(encoding="utf-8", errors="replace"))
            if m:
                return m.group(1)
            break
    return root.name


def which_marker(root: Path, markers: list[str]) -> str:
    for marker in markers:
        if (root / marker).is_file():
            return marker.split("/")[0]
    return "?"


def nearest_root(target: Path, roots: list[Path]) -> Path | None:
    target = target.resolve()
    best: Path | None = None
    for r in roots:
        try:
            target.relative_to(r)
        except ValueError:
            continue
        if best is None or len(r.parts) > len(best.parts):
            best = r
    return best


def governing_root_above(path: Path) -> Path | None:
    path = Path(path).resolve()
    for cur in (path, *path.parents):
        for name in (".praxis", "praxis"):
            if (cur / name / "config.md").is_file():
                return cur
    return None


def _is_ancestor_or_equal(anc: Path, node: Path) -> bool:
    try:
        node.resolve().relative_to(anc.resolve())
        return True
    except ValueError:
        return False


def interop_root(targets: list[Path], roots: list[Path]) -> dict:
    governing = sorted({r for r in (nearest_root(t, roots) for t in targets) if r is not None},
                       key=lambda p: str(p))
    if len(governing) <= 1:
        return {"spans": False, "governing": governing,
                "entry": governing[0] if governing else None, "define_at": None}
    candidates = [r for r in roots if all(_is_ancestor_or_equal(r, g) for g in governing)]
    entry = max(candidates, key=lambda r: len(r.resolve().parts)) if candidates else None
    define_at = None
    if entry is None:
        define_at = os.path.commonpath([str(g.resolve()) for g in governing])
    return {"spans": True, "governing": governing, "entry": entry, "define_at": define_at}


def build_tree(roots: list[Path], markers: list[str]) -> dict:
    nodes: dict[str, dict] = {}
    for r in roots:
        nodes[str(r)] = {
            "path": str(r),
            "name": root_name(r, markers),
            "engine": which_marker(r, markers),
            "parent": None,
            "children": [],
        }
    for r in roots:
        parent = None
        for cand in roots:
            if cand == r:
                continue
            try:
                r.resolve().relative_to(cand.resolve())
            except ValueError:
                continue
            if parent is None or len(cand.parts) > len(parent.parts):
                parent = cand
        if parent is not None:
            nodes[str(r)]["parent"] = str(parent)
            nodes[str(parent)]["children"].append(str(r))
    return nodes


def orphan_sibling_groups(nodes: dict) -> list[dict]:
    tops = [n for n in nodes.values() if n["parent"] is None]
    by_ancestor: dict[str, list[dict]] = {}
    for n in tops:
        by_ancestor.setdefault(str(Path(n["path"]).parent), []).append(n)
    groups = []
    for ancestor, members in by_ancestor.items():
        if len(members) >= 2:
            groups.append({"ancestor": ancestor, "members": [m["name"] for m in members],
                           "paths": [m["path"] for m in members]})
    return groups


def print_tree(base: Path, nodes: dict, markers: list[str]) -> None:
    if not nodes:
        print(f"no roots found under {base} (markers: {', '.join(markers)})")
        return

    def rel(p: str) -> str:
        try:
            return "." if Path(p) == base else "./" + str(Path(p).relative_to(base))
        except ValueError:
            return p

    def walk(node: dict, depth: int) -> None:
        indent = "  " * depth
        kind = "interop/parent" if node["children"] else "leaf"
        print(f"{indent}• {node['name']}  [{node['engine']}] ({kind})")
        print(f"{indent}  {rel(node['path'])}")
        for child_path in sorted(node["children"]):
            walk(nodes[child_path], depth + 1)

    tops = [n for n in nodes.values() if n["parent"] is None]
    print(f"root tree under {base}")
    print(f"markers: {', '.join(markers)} · {len(nodes)} root(s)\n")
    for t in sorted(tops, key=lambda n: n["path"]):
        walk(t, 0)

    groups = orphan_sibling_groups(nodes)
    if groups:
        print("\n⚠ missing interop root(s):")
        for g in groups:
            names = ", ".join(g["members"])
            try:
                anc = "./" + str(Path(g["ancestor"]).relative_to(base))
            except ValueError:
                anc = g["ancestor"]
            print(f"  {len(g['members'])} sibling roots ({names}) under {anc} with no parent root —")
            print(f"    a task spanning them has nowhere to route interop concerns.")


def cmd_tree(args) -> int:
    base = Path(args.__dict__["from"]).resolve()
    markers = args.marker or DEFAULT_MARKERS
    roots = find_roots(base, markers)
    nodes = build_tree(roots, markers)
    if args.json:
        print(json.dumps({
            "base": str(base),
            "markers": markers,
            "roots": list(nodes.values()),
            "missing_interop_roots": orphan_sibling_groups(nodes),
        }, indent=2))
    else:
        print_tree(base, nodes, markers)
    return 0


def cmd_resolve(args) -> int:
    base = Path(args.__dict__["from"]).resolve()
    markers = args.marker or DEFAULT_MARKERS
    roots = find_roots(base, markers)
    target = Path(args.path)
    if not target.is_absolute():
        target = base / target
    r = nearest_root(target, roots)
    if r is None:
        print(f"no root governs {target}")
        return 1
    print(f"{root_name(r, markers)}  [{which_marker(r, markers)}]")
    print(f"  {r}")
    return 0


def cmd_span(args) -> int:
    base = Path(args.__dict__["from"]).resolve()
    markers = args.marker or DEFAULT_MARKERS
    roots = find_roots(base, markers)
    files = split_files(args.files)
    spanned: dict[str, list[str]] = {}
    unrouted: list[str] = []
    for f in files:
        p = Path(f)
        if not p.is_absolute():
            p = base / p
        r = nearest_root(p, roots)
        if r is None:
            unrouted.append(f)
        else:
            spanned.setdefault(str(r), []).append(f)
    print(f"{len(files)} file(s) span {len(spanned)} root(s):\n")
    for root_path, fs in sorted(spanned.items()):
        print(f"• {root_name(Path(root_path), markers)}  [{which_marker(Path(root_path), markers)}]")
        for f in fs:
            print(f"    {f}")
    if unrouted:
        print("\n• (no root)")
        for f in unrouted:
            print(f"    {f}")
    if len(spanned) > 1:
        print(f"\n→ this task spans {len(spanned)} roots: it is {len(spanned)} units of work, one handed "
              f"to each root, not one agent straddling both.")
    return 0


def cmd_interop(args) -> int:
    base = Path(args.__dict__["from"]).resolve()
    markers = args.marker or DEFAULT_MARKERS
    roots = find_roots(base, markers)
    targets = []
    for f in args.files.split(","):
        f = f.strip()
        if f:
            p = Path(f)
            targets.append(p if p.is_absolute() else base / p)
    info = interop_root(targets, roots)
    if not info["spans"]:
        entry = info["entry"]
        print(f"single root — enter at: {root_name(entry, markers) if entry else '(no root)'}")
        return 0
    gov = ", ".join(root_name(g, markers) for g in info["governing"])
    if info["entry"] is not None:
        print(f"spans {{{gov}}} — enter at interop root: {root_name(info['entry'], markers)}")
        print(f"  {info['entry']}")
        return 0
    print(f"spans {{{gov}}} — NO interop root exists to enter at.")
    print(f"  define one at the common ancestor: {info['define_at']}")
    return 1


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="root_tree", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("tree", help="discover and print the root tree")
    t.add_argument("--from", default=".", help="directory to search from (default: cwd)")
    t.add_argument("--marker", action="append", help="boundary marker (repeatable; default .praxis/config.md, legacy praxis/config.md)")
    t.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    t.set_defaults(func=cmd_tree)

    r = sub.add_parser("resolve", help="which root governs a path")
    r.add_argument("path")
    r.add_argument("--from", default=".")
    r.add_argument("--marker", action="append")
    r.set_defaults(func=cmd_resolve)

    s = sub.add_parser("span", help="which roots a set of files spans")
    s.add_argument("--files", required=True, help="comma-separated file paths")
    s.add_argument("--from", default=".")
    s.add_argument("--marker", action="append")
    s.set_defaults(func=cmd_span)

    i = sub.add_parser("interop", help="the root a (possibly spanning) task must enter at")
    i.add_argument("--files", required=True, help="comma-separated file paths")
    i.add_argument("--from", default=".")
    i.add_argument("--marker", action="append")
    i.set_defaults(func=cmd_interop)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
