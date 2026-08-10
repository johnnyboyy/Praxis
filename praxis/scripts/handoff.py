#!/usr/bin/env python3
"""handoff — the praxis handoff primitive: compose the handoff schema from plugins, generate a
skeleton, and validate that every registered plugin's required fields come out the other side.

A handoff is a praxis fact: one unit-of-work produces exactly one handoff. Praxis owns the envelope
(handoff/base.json). Judgment engines hook in as *plugins* (handoff/plugins/*.json), each declaring
the fields it expects — praxis's engine composes them without knowing what any field means; it only
enforces presence. That is the whole point: the schema is dynamic and plugin-driven, so any engine
extends the handoff by dropping a manifest, not by editing praxis.

Deterministic + testable throughout: JSON manifests in, regex validation out, no YAML dependency
(matching the "flat enough to validate without a YAML lib" discipline).

The handoff LIFECYCLE is a praxis primitive end to end: praxis owns create (`template`), validate
(`validate`), AND close (`close`) — no engine is invoked for any of the three. `close` retires a
ratified handoff by deleting it, or archiving it under `<handoffs-dir>/archive/` when the governing
root's `praxis/config.md` sets `debug: yes`; the archive is never part of a pending backlog. It is
guarded so it can only ever act on a file sitting directly inside the handoffs dir.

Commands:
  schema   [--base B] [--plugins-dir D] [--json]        the composed schema (base + all plugins)
  template --unit-of-work U --workstream W --stance S    a skeleton handoff with every required field
             [--base B] [--plugins-dir D]
  validate FILE [--base B] [--plugins-dir D]             fail if any required field/section is missing
  close    FILE [--handoffs-dir D]                       delete (or archive when debug) a ratified handoff
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

HANDOFF_DIR = Path(__file__).resolve().parent.parent / "handoff"
DEFAULT_BASE = HANDOFF_DIR / "base.json"
DEFAULT_PLUGINS = HANDOFF_DIR / "plugins"


def load_manifests(base: Path, plugins_dir: Path) -> list[dict]:
    manifests = [json.loads(Path(base).read_text())]
    if Path(plugins_dir).is_dir():
        for p in sorted(Path(plugins_dir).glob("*.json")):
            manifests.append(json.loads(p.read_text()))
    return manifests


def compose(manifests: list[dict]) -> dict:
    """Merge base + plugins into one schema. Later plugins may not override base field definitions;
    a duplicate field name keeps the first (base wins) and records the conflict, so a plugin can't
    silently weaken a required base field."""
    frontmatter: list[dict] = []
    sections: list[dict] = []
    seen_f: dict[str, str] = {}
    seen_s: dict[str, str] = {}
    conflicts: list[str] = []
    for m in manifests:
        who = m.get("plugin", "?")
        for f in m.get("frontmatter", []):
            if f["field"] in seen_f:
                conflicts.append(f"frontmatter '{f['field']}' redeclared by {who} (kept {seen_f[f['field']]})")
                continue
            seen_f[f["field"]] = who
            frontmatter.append({**f, "plugin": who})
        for s in m.get("sections", []):
            if s["name"] in seen_s:
                conflicts.append(f"section '{s['name']}' redeclared by {who} (kept {seen_s[s['name']]})")
                continue
            seen_s[s["name"]] = who
            sections.append({**s, "plugin": who})
    return {"frontmatter": frontmatter, "sections": sections, "conflicts": conflicts,
            "plugins": [m.get("plugin", "?") for m in manifests]}


def split_frontmatter(text: str) -> tuple[str, str]:
    """Return (frontmatter_block, body). Frontmatter is the first '---'-delimited block."""
    m = re.match(r"\s*---\n(.*?)\n---\n?(.*)", text, re.DOTALL)
    if m:
        return m.group(1), m.group(2)
    return "", text


def validate(text: str, schema: dict) -> list[str]:
    fm, body = split_frontmatter(text)
    missing: list[str] = []
    for f in schema["frontmatter"]:
        if not f.get("required"):
            continue
        if not re.search(rf"^\s*{re.escape(f['field'])}\s*:", fm, re.MULTILINE):
            missing.append(f"frontmatter field '{f['field']}' (required by {f['plugin']})")
    for s in schema["sections"]:
        if not s.get("required"):
            continue
        if not re.search(rf"^##\s+{re.escape(s['name'])}\s*$", body, re.MULTILINE):
            missing.append(f"section '## {s['name']}' (required by {s['plugin']})")
    return missing


def render_template(schema: dict, values: dict) -> str:
    lines = ["---"]
    for f in schema["frontmatter"]:
        v = values.get(f["field"], "")
        if not v:
            if f["shape"] == "list":
                v = "[]"
            elif f["shape"] == "map":
                v = ""
            elif f["shape"] == "enum":
                v = f.get("values", [""])[0]
            else:
                v = f"<{f['field']}>" if f.get("required") else ""
        req = "" if f.get("required") else "   # optional"
        if f["shape"] == "map" and not values.get(f["field"]):
            lines.append(f"{f['field']}:{req}")
            lines.append("  screens: []")
            lines.append("  components: []")
        else:
            lines.append(f"{f['field']}: {v}{req}")
    lines.append("---")
    for s in schema["sections"]:
        lines.append("")
        lines.append(f"## {s['name']}")
        lines.append("")
        lines.append(f"<{s['desc']}>")
    return "\n".join(lines) + "\n"


def project_debug(root: Path) -> bool:
    """The governing root's `praxis/config.md` `debug: yes` opt-in. Read natively — praxis owns the
    handoff lifecycle, so it reads this filesystem flag itself rather than asking the engine (same
    regex, same yes/true tolerance)."""
    import root_tree as rt
    config = rt.praxis_dir(root) / "config.md"
    if not config.is_file():
        return False
    return re.search(r"^debug:\s*(yes|true)\s*$", config.read_text(),
                     re.MULTILINE | re.IGNORECASE) is not None


def close(file: str, handoffs_dir: Path, debug: bool) -> tuple[int, str]:
    """Close a ratified handoff. Delete it, or archive it under `<handoffs-dir>/archive/` when debug.

    Guard: the file must sit DIRECTLY inside handoffs_dir —
    never a nested path, never the archive itself — so close can only ever retire a real pending
    handoff. Returns (rc, message); rc is a process exit code (0 ok, 1 guard/precondition failure).
    """
    path = Path(file).resolve()
    hdir = Path(handoffs_dir).resolve()
    if not path.exists():
        return 1, f"no such file: {file}"
    if path.parent != hdir:
        return 1, f"{file} is not directly inside {handoffs_dir}"
    if debug:
        archive = hdir / "archive"
        archive.mkdir(parents=True, exist_ok=True)
        dest = archive / path.name
        os.replace(path, dest)
        return 0, f"archived to {dest}"
    path.unlink()
    return 0, f"deleted {path}"


def cmd_schema(args) -> int:
    schema = compose(load_manifests(args.base, args.plugins_dir))
    if args.json:
        print(json.dumps(schema, indent=2))
        return 0
    print(f"handoff schema · plugins: {', '.join(schema['plugins'])}\n")
    print("frontmatter:")
    for f in schema["frontmatter"]:
        req = "required" if f.get("required") else "optional"
        print(f"  {f['field']:<34} {req:<8} [{f['plugin']}]  {f.get('desc','')}")
    print("\nsections:")
    for s in schema["sections"]:
        req = "required" if s.get("required") else "optional"
        print(f"  ## {s['name']:<20} {req:<8} [{s['plugin']}]")
    if schema["conflicts"]:
        print("\n⚠ conflicts:")
        for c in schema["conflicts"]:
            print(f"  {c}")
    return 0


def cmd_template(args) -> int:
    schema = compose(load_manifests(args.base, args.plugins_dir))
    values = {"unit-of-work": args.unit_of_work, "workstream": args.workstream, "stance": args.stance}
    sys.stdout.write(render_template(schema, values))
    return 0


def cmd_validate(args) -> int:
    schema = compose(load_manifests(args.base, args.plugins_dir))
    text = Path(args.file).read_text()
    missing = validate(text, schema)
    if missing:
        print(f"INVALID handoff: {len(missing)} required field(s)/section(s) missing")
        for m in missing:
            print(f"  - {m}")
        return 1
    print(f"valid handoff (checked base + {len(schema['plugins'])-1} plugin(s): "
          f"{', '.join(schema['plugins'])})")
    return 0


def cmd_close(args) -> int:
    # Default the handoffs dir to the file's own parent, so a bare `close FILE` acts on the dir the
    # handoff lives in; the governing root is <handoffs-dir>/../.. (root/praxis/handoffs), from which
    # the debug flag is read. Callers that know the root (e.g. chunk_ledger) pass --handoffs-dir.
    handoffs_dir = Path(args.handoffs_dir) if args.handoffs_dir else Path(args.file).resolve().parent
    root = handoffs_dir.resolve().parent.parent
    rc, msg = close(args.file, handoffs_dir, project_debug(root))
    print(msg)
    return rc


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="handoff", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("--base", default=str(DEFAULT_BASE))
        p.add_argument("--plugins-dir", default=str(DEFAULT_PLUGINS))

    sc = sub.add_parser("schema", help="show the composed handoff schema")
    common(sc)
    sc.add_argument("--json", action="store_true")
    sc.set_defaults(func=cmd_schema)

    tp = sub.add_parser("template", help="emit a skeleton handoff with every required field")
    common(tp)
    tp.add_argument("--unit-of-work", required=True)
    tp.add_argument("--workstream", required=True)
    tp.add_argument("--stance", required=True)
    tp.set_defaults(func=cmd_template)

    va = sub.add_parser("validate", help="fail if any required field/section is missing")
    common(va)
    va.add_argument("file")
    va.set_defaults(func=cmd_validate)

    cl = sub.add_parser("close", help="delete (or archive when debug) a ratified handoff")
    cl.add_argument("file")
    cl.add_argument("--handoffs-dir", default="",
                    help="the handoffs dir the file must sit in (default: the file's own parent)")
    cl.set_defaults(func=cmd_close)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
