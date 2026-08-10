#!/usr/bin/env python3
"""plugin_scaffold — create and validate a plugin's structure, generically.

Part of praxis-core, the authoring companion to `plugin_import` (which moves a plugin IN; this stands
one UP). It is the deterministic half of plugin authoring: the dir layout and manifest shape are
structure, so they are a tested script — never hand-mkdir'd and hand-written. The JUDGMENT half (should
this concern be a plugin? which domains belong? should its judgment ship or accrete?) is deliberately
NOT here; that is earned at the gate, not scripted — the same discipline that keeps a new concern's
judgment face empty until real work fills it.

Purity: praxis-core names no engine. This validates a plugin's SHAPE — its `plugin.json`, its `provides`
slots (praxis's own: engine/handoff/phases/scripts), and that a declared `judgment_face` path is a real
dir — without knowing what any face contains or which engine a judgment face targets. A `judgment_face`
is just a path the manifest declares; the scaffolder writes and reads it generically.

Commands:
  new      --path DIR --name NAME [--phases] [--scripts] [--judgment-face RELPATH]
           scaffold a plugin: write plugin.json + create the requested face dirs.
  validate --path DIR
           check a plugin's manifest + layout; exit non-zero and list problems if any.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import plugin_import  # noqa: E402  reuse the one definition of praxis's slot names

VALID_SLOTS = set(plugin_import.SLOT_TARGETS)   # {"engine", "handoff", "phases", "scripts"}
# where a `new` scaffold puts each requested praxis-face slot, relative to the plugin dir
DEFAULT_SUBDIR = {"phases": "praxis/phases", "scripts": "praxis/scripts"}


def scaffold(path: Path, name: str, phases: bool, scripts: bool, judgment_face: str | None) -> dict:
    path = Path(path)
    if (path / "plugin.json").exists():
        raise SystemExit(f"plugin.json already exists in {path} — refusing to overwrite")
    provides: dict[str, str] = {}
    if phases:
        provides["phases"] = DEFAULT_SUBDIR["phases"]
    if scripts:
        provides["scripts"] = DEFAULT_SUBDIR["scripts"]
    manifest: dict = {"name": name, "kind": "plugin", "doc": "", "provides": provides}
    if judgment_face:
        manifest["judgment_face"] = judgment_face

    for subdir in provides.values():
        (path / subdir).mkdir(parents=True, exist_ok=True)
    if judgment_face:
        (path / judgment_face).mkdir(parents=True, exist_ok=True)
    path.mkdir(parents=True, exist_ok=True)
    (path / "plugin.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return {"path": str(path), "provides": provides, "judgment_face": judgment_face}


def validate(path: Path) -> list[str]:
    """Return a list of problems (empty = valid)."""
    path = Path(path)
    problems: list[str] = []
    manifest_path = path / "plugin.json"
    if not manifest_path.is_file():
        return [f"no plugin.json in {path}"]
    try:
        data = json.loads(manifest_path.read_text())
    except json.JSONDecodeError as e:
        return [f"plugin.json is not valid JSON: {e}"]

    if not data.get("name"):
        problems.append("plugin.json declares no `name`")

    provides = data.get("provides", {})
    if not isinstance(provides, dict):
        problems.append("`provides` must be an object (slot → subdir)")
        provides = {}
    for slot, subdir in provides.items():
        if slot not in VALID_SLOTS:
            problems.append(f"`provides` names unknown slot '{slot}' (praxis slots: {sorted(VALID_SLOTS)})")
            continue
        if not (path / subdir).is_dir():
            problems.append(f"`provides.{slot}` points at '{subdir}', which is not a directory")

    jf = data.get("judgment_face")
    if jf is not None:
        if not isinstance(jf, str) or not jf:
            problems.append("`judgment_face` must be a non-empty path string")
        elif not (path / jf).is_dir():
            problems.append(f"`judgment_face` points at '{jf}', which is not a directory")

    if not provides and jf is None:
        problems.append("plugin declares neither a praxis face (`provides`) nor a `judgment_face` — empty")
    return problems


def cmd_new(args) -> int:
    r = scaffold(Path(args.path), args.name, args.phases, args.scripts, args.judgment_face)
    faces = list(r["provides"]) + (["judgment_face"] if r["judgment_face"] else [])
    print(f"scaffolded plugin '{args.name}' at {r['path']} (faces: {', '.join(faces) or 'none'})")
    return 0


def cmd_validate(args) -> int:
    problems = validate(Path(args.path))
    if problems:
        print(f"plugin at {args.path} is INVALID:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1
    print(f"plugin at {args.path} is valid")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="plugin_scaffold", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    nw = sub.add_parser("new", help="scaffold a plugin's manifest + face dirs")
    nw.add_argument("--path", required=True, help="the plugin dir to create")
    nw.add_argument("--name", required=True)
    nw.add_argument("--phases", action="store_true", help="give it a praxis phases face")
    nw.add_argument("--scripts", action="store_true", help="give it a praxis scripts face")
    nw.add_argument("--judgment-face", default=None,
                    help="relative path for a judgment face dir (the engine's domains dir, e.g. <engine>/domains)")
    nw.set_defaults(func=cmd_new)

    va = sub.add_parser("validate", help="check a plugin's manifest + layout")
    va.add_argument("--path", required=True)
    va.set_defaults(func=cmd_validate)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
