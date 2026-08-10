#!/usr/bin/env python3
"""frame_store — persist a task's frame, so a redirect leaves a trace and a re-framed (fresh) spawn
sees what was assumed. Part of praxis-core; framing Stage 3, the first vertebra of the backward spine.

A frame is a BEFORE-work artifact — the governing root, the assumptions stated for redirection, the
size verdict, the route taken, and the composition — produced the moment a task is framed, before
anything acts. The chunk ledger records what happened AFTER a unit closes; the frame records what was
assumed BEFORE it ran, and exists even for tasks that never chunk (trivial changes, the no-handoff
exemption). So it is its own artifact (`<root>/praxis/frames/<workstream>.md`), not folded into the
ledger.

Frames APPEND: each re-frame of a workstream adds an entry, so a redirect is a new frame beside the
old, not a silent overwrite — the backward trace. The trace is for LEGIBILITY: a fresh spawn reads the
prior frame as explicit input (which assumptions still hold, what was already composed) and
re-composes for the actual current task. It is deliberately NOT a queue you resume a closed unit from
(planning.md: a trace keeps the boundary legible without becoming a second resumable queue).

Commands:
  write --root R --workstream W --unit-of-work U [--target ...] [--engine-plugins ...]
          compute the frame (via frame.build_frame) and append it to the workstream's frame ledger.
  show  --root R --workstream W
          print the persisted frame trace a fresh/re-framed spawn reads.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import frame as fr  # noqa: E402
import root_tree as rt  # noqa: E402
from chunk_ledger import today, _parse_inline_list as _inline_list  # noqa: E402


def frames_dir_for(root: str | Path) -> Path:
    return rt.praxis_dir(root) / "frames"


def frame_path(root: str | Path, workstream: str) -> Path:
    return frames_dir_for(root) / f"{workstream}.md"


def frame_entry(frame: dict, shape: str | None = None) -> dict:
    """Distill a build_frame result into a persisted frame entry — the artifact framing.md names
    (root, assumptions, size verdict, route/shape) plus the composition, for a fresh spawn's reuse."""
    root = frame["roots"][0]["name"] if frame.get("roots") else "(no root)"
    comp = frame.get("composition") or []
    return {
        "recorded": today(),
        "unit-of-work": frame.get("unit_of_work") or "(undecided)",
        "root": root,
        "size-floor": frame.get("size_floor", "?"),
        "shape": shape or frame.get("verdict", "?"),
        "composition": comp,
        "assumptions": list(frame.get("assumptions", [])),
    }


def parse_frames(path: str | Path) -> tuple[str, list[dict]]:
    """Flat parser (same spirit as the chunk ledger). Returns (workstream, entries); each entry's
    `composition` is a list and `assumptions` is a list of quoted lines."""
    workstream = ""
    entries: list[dict] = []
    item: dict | None = None
    in_frames = False
    in_assumptions = False
    for raw in open(path):
        line = raw.rstrip()
        stripped = line.strip()
        if in_frames and stripped == "```":
            break
        if not in_frames and stripped.startswith("workstream:"):
            workstream = stripped.split(":", 1)[1].strip()
            continue
        if stripped in ("frames:", "frames: []"):
            in_frames = True
            continue
        if not in_frames or not stripped or stripped.startswith(("#", "```")):
            continue
        if stripped.startswith("- recorded:"):
            item = {"assumptions": []}
            entries.append(item)
            in_assumptions = False
            stripped = stripped[2:]  # drop "- "
        if item is None:
            continue
        if stripped == "assumptions:":
            in_assumptions = True
            continue
        if in_assumptions and stripped.startswith("- "):
            item["assumptions"].append(stripped[2:].strip().strip('"'))
            continue
        if ":" in stripped:
            in_assumptions = False
            key, _, value = stripped.partition(":")
            key, value = key.strip(), value.strip()
            item[key] = _inline_list(value) if key == "composition" else value
    return workstream, entries


def render_frames(workstream: str, entries: list[dict]) -> str:
    lines = ["# Frames", "", f"workstream: {workstream}", "",
             "# BEFORE-work trace: what was framed/assumed before each (re-)frame of this workstream.",
             "# A redirect appends a new frame beside the old. Read for legibility, not to resume from.",
             "", "```yaml", "frames:", ""]
    for e in entries:
        lines.append(f"  - recorded: {e['recorded']}")
        lines.append(f"    unit-of-work: {e['unit-of-work']}")
        lines.append(f"    root: {e['root']}")
        lines.append(f"    size-floor: {e['size-floor']}")
        lines.append(f"    shape: {e['shape']}")
        lines.append(f"    composition: [{', '.join(e.get('composition', []))}]")
        lines.append("    assumptions:")
        for a in e.get("assumptions", []):
            lines.append(f'      - "{a}"')
        lines.append("")
    lines.append("```")
    return "\n".join(lines) + "\n"


def append_frame(root: str | Path, workstream: str, frame: dict, shape: str | None = None) -> Path:
    """Append a frame entry to the workstream's frame ledger (created on first write). The append is
    the trace: a re-frame does not overwrite the prior frame, it lands beside it."""
    path = frame_path(root, workstream)
    ws, entries = (workstream, [])
    if path.is_file():
        ws, entries = parse_frames(path)
        ws = ws or workstream
    entries.append(frame_entry(frame, shape))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_frames(ws, entries))
    return path


def cmd_write(args) -> int:
    base = Path(args.root).resolve()
    files = rt.split_files(args.files)
    manifest = fr.manifest_for(base, args.target, files, args.engine_plugins)
    frame = fr.build_frame(base, args.target, files, args.unit_of_work or None, manifest)
    path = append_frame(base, args.workstream, frame)
    fr.touch_if_framed(frame)  # persisting a frame via the CLI is framing for real — stamp freshness
    _, entries = parse_frames(path)
    print(f"frame {len(entries)} recorded for workstream '{args.workstream}': {path}")
    return 0


def cmd_show(args) -> int:
    path = frame_path(Path(args.root).resolve(), args.workstream)
    if not path.is_file():
        print(f"no frame trace for workstream '{args.workstream}' at {path}")
        return 1
    sys.stdout.write(path.read_text())
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="frame_store", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    w = sub.add_parser("write", help="compute the frame and append it to the workstream's frame ledger")
    w.add_argument("--root", required=True)
    w.add_argument("--workstream", required=True)
    w.add_argument("--unit-of-work", default="")
    w.add_argument("--target", help="a candidate path the task touches")
    w.add_argument("--files", default="", help="comma-separated candidate files")
    w.add_argument("--engine-plugins", default=None,
                   help="engine slot (omit to auto-resolve the root's own slot)")
    w.set_defaults(func=cmd_write)

    s = sub.add_parser("show", help="print the persisted frame trace")
    s.add_argument("--root", required=True)
    s.add_argument("--workstream", required=True)
    s.set_defaults(func=cmd_show)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
