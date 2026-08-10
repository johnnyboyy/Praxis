#!/usr/bin/env python3
"""praxis_init — make a directory a praxis root by writing its `.praxis/config.md` marker.

Part of praxis-core. A praxis root is just a directory carrying `praxis/config.md` (the marker
`root_tree` discovers); the file is structure, not judgment — a marker plus a `debug` flag — so
producing it is a deterministic script rather than a hand-crafted file. This is the root-level mirror
of `plugin_scaffold` (which scaffolds a plugin): here we scaffold a *root*.

It writes only the marker. The slot dirs (`engine/plugins`, `handoff/plugins`, `phases`, `scripts`)
are created by `plugin_import` when a plugin is moved in, and `chunks/` / `handoffs/` by the ledger and
handoff primitives when they first write — so init stays minimal and never pre-creates empty ceremony.

Engine-free: `praxis/config.md` is praxis's own marker. A project that also uses a judgment engine
carries that engine's own config beside this one (e.g. its project-shape file); producing THAT is the
engine's bootstrap, not praxis's.

Commands:
  init --root DIR [--name NAME] [--debug] [--force]
       write DIR/.praxis/config.md (refuses to overwrite unless --force).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def config_body(name: str | None, debug: bool) -> str:
    title = f"# praxis root: {name}\n" if name else "# praxis root\n"
    # A `name:` line (not just the header) so root_tree.root_name discovers the declared name — it is
    # what interop addressing (`addressed-to`/`return-to`) resolves a root by. Absent it, a root falls
    # back to its directory basename.
    name_line = f"name: {name}\n" if name else ""
    return (
        f"{title}\n"
        "# This file is the root marker `root_tree` discovers. Plugins moved in with plugin_import\n"
        "# land beside it (engine/plugins, handoff/plugins, phases, scripts); chunks/ and handoffs/\n"
        "# are created by the ledger and handoff primitives on first write.\n"
        "#\n"
        "# debug: yes → closing a ratified handoff archives it under handoffs/archive/ instead of\n"
        "# deleting it (handoff.py). Default off.\n"
        f"{name_line}"
        f"debug: {'yes' if debug else 'no'}\n"
    )


def init_root(root: Path, name: str | None, debug: bool, force: bool) -> Path:
    import root_tree as rt
    root = Path(root)
    # praxis_dir lands on `.praxis` for a fresh directory (the standard name) and on the existing
    # marker dir for an already-initialized root, so --force rewrites in place rather than creating
    # a second marker beside a legacy one.
    config = rt.praxis_dir(root) / "config.md"
    if config.exists() and not force:
        raise SystemExit(f"{config} already exists — this is already a praxis root (use --force to rewrite)")
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(config_body(name, debug))
    return config


def cmd_init(args) -> int:
    config = init_root(Path(args.root), args.name, args.debug, args.force)
    print(f"praxis root initialized: {config}"
          f"{' (debug on)' if args.debug else ''}")
    print("next: move a judgment engine + any plugins in with plugin_import, then frame/route a task.")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="praxis_init", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    it = sub.add_parser("init", help="write a praxis/config.md root marker into a directory")
    it.add_argument("--root", required=True, help="the directory to make a praxis root")
    it.add_argument("--name", default=None, help="a human name for the root (recorded in the marker)")
    it.add_argument("--debug", action="store_true", help="set debug: yes (archive closed handoffs)")
    it.add_argument("--force", action="store_true", help="overwrite an existing config.md")
    it.set_defaults(func=cmd_init)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
