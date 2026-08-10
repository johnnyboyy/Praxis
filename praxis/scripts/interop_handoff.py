#!/usr/bin/env python3
"""interop_handoff — deliver a handoff across roots. Part of praxis-core.

The handoff is a praxis primitive; interop makes it a MESSAGE between roots. A cross-root handoff
carries `addressed-to:` (the root it crosses to next) and `return-to:` (the reply address). This
script routes such a handoff into the addressed root's `praxis/inbox/` — a mechanical file move, so
no agent ever straddles two roots; only the handoff crosses. The receiving root's agent picks the
brief up from its inbox, works in its OWN context (its own composition, its own handoff), and
addresses its completion back to `return-to`. Delivering that completion (same `deliver`) lands it in
the interop root's inbox, where the interop phase composes the children's results.

The round-trip, entirely as file moves between roots' inboxes:
  interop root writes a brief (addressed-to: child, return-to: interop) → deliver → child inbox
  → child works, writes its handoff (addressed-to: interop) → deliver → interop inbox → compose.

Commands:
  deliver FILE [--from BASE]   move a handoff into its `addressed-to` root's praxis/inbox/
  inbox ROOT  [--from BASE]    list the cross-root handoffs waiting in a root's inbox (read-only)
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import root_tree as rt  # noqa: E402
import handoff as ho  # noqa: E402  reuse the handoff primitive's frontmatter splitter


def field(text: str, name: str) -> str:
    """Read one frontmatter scalar from a handoff, via the handoff primitive's own splitter."""
    fm, _ = ho.split_frontmatter(text)
    m = re.search(rf"^\s*{re.escape(name)}\s*:\s*(.*)$", fm, re.MULTILINE)
    return m.group(1).strip() if m else ""


def resolve_root_by_name(base: Path, name: str) -> Path | None:
    """The single root under `base` whose declared name is `name`, or None (absent or ambiguous)."""
    matches = [r for r in rt.find_roots(base, rt.DEFAULT_MARKERS)
               if rt.root_name(r, rt.DEFAULT_MARKERS) == name]
    return matches[0] if len(matches) == 1 else None


def inbox_dir(root: Path) -> Path:
    import root_tree as rt
    return rt.praxis_dir(root) / "inbox"


def deliver(file: str, base: Path) -> tuple[int, str]:
    """Move a cross-root handoff into its `addressed-to` root's inbox. Returns (rc, message)."""
    path = Path(file).resolve()
    if not path.is_file():
        return 1, f"no such handoff file: {file}"
    text = path.read_text()
    to = field(text, "addressed-to")
    if not to:
        return 1, f"{file} has no `addressed-to:` — not a cross-root handoff; nothing to deliver"
    target = resolve_root_by_name(base, to)
    if target is None:
        names = ", ".join(rt.root_name(r, rt.DEFAULT_MARKERS)
                          for r in rt.find_roots(base, rt.DEFAULT_MARKERS)) or "none"
        return 1, (f"addressed-to '{to}' did not resolve to exactly one root under {base} "
                   f"(roots: {names})")
    dest_dir = inbox_dir(target)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / path.name
    shutil.move(str(path), str(dest))
    ret = field(text, "return-to")
    return 0, f"delivered to '{to}' inbox: {dest}" + (f"  (return-to: {ret})" if ret else "")


def cmd_deliver(args) -> int:
    rc, msg = deliver(args.file, Path(args.frm).resolve())
    print(msg)
    return rc


def cmd_inbox(args) -> int:
    base = Path(args.frm).resolve()
    root = resolve_root_by_name(base, args.root)
    if root is None and Path(args.root).is_dir():
        root = Path(args.root)
    if root is None:
        print(f"no root '{args.root}' under {base}")
        return 1
    name = rt.root_name(root, rt.DEFAULT_MARKERS)
    d = inbox_dir(root)
    files = sorted(d.glob("*.md")) if d.is_dir() else []
    if not files:
        print(f"{name}: inbox empty")
        return 0
    print(f"{name} inbox — {len(files)} cross-root handoff(s):")
    for f in files:
        text = f.read_text()
        print(f"  - {f.name}  return-to={field(text, 'return-to') or '?'}  "
              f"unit-of-work={field(text, 'unit-of-work') or '?'}  status={field(text, 'status') or '?'}")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="interop_handoff", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("deliver", help="move a handoff into its addressed-to root's praxis/inbox/")
    d.add_argument("file")
    d.add_argument("--from", dest="frm", default=".", help="search base for root discovery (default cwd)")
    d.set_defaults(func=cmd_deliver)

    i = sub.add_parser("inbox", help="list the cross-root handoffs waiting in a root's inbox")
    i.add_argument("root", help="the root (name, or a path) whose inbox to list")
    i.add_argument("--from", dest="frm", default=".", help="search base for root discovery (default cwd)")
    i.set_defaults(func=cmd_inbox)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
