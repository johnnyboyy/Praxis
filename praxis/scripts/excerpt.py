#!/usr/bin/env python3
"""excerpt — byte-for-byte markdown section extraction, for composing curated context into a
spawn brief.

The deterministic half of "feed the spawn just the parts it needs": WHICH sections of a document
(a UI/UX library, a plan, any markdown reference) are relevant to a unit of work is routing
judgment; EXTRACTING the named sections and composing them into the brief is process, and process
is a script. Extraction is byte-for-byte — hand-paraphrasing a section into a brief is exactly
where compression and drift sneak in, so this tool removes the temptation: name the sections,
paste the output.

Engine-agnostic: knows markdown headings, not what any document means.

  excerpt.py list --file corpora/ui-library.md
  excerpt.py get  --file corpora/ui-library.md --sections "Buttons,Color tokens"

A section runs from its heading line to just before the next heading of the same or higher level.
Title match is case-insensitive on the heading text (leading #s and whitespace stripped). A miss
fails loudly, listing what the file actually offers — never silently emits less than asked for.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*$")


def parse_headings(text: str) -> list[dict]:
    """Every heading with its level, title, and line span (start inclusive, end exclusive —
    running to the next heading of same-or-higher level, or EOF)."""
    lines = text.split("\n")
    heads = []
    fence = False
    for i, line in enumerate(lines):
        if line.lstrip().startswith("```"):
            fence = not fence
            continue
        if fence:
            continue
        m = HEADING.match(line)
        if m:
            heads.append({"level": len(m.group(1)), "title": m.group(2), "start": i})
    for j, h in enumerate(heads):
        h["end"] = len(lines)
        for later in heads[j + 1:]:
            if later["level"] <= h["level"]:
                h["end"] = later["start"]
                break
    return heads


def extract(text: str, wanted: list[str]) -> tuple[str, list[str]]:
    """(joined sections byte-for-byte, missing titles). Each wanted title matches the first
    heading whose text equals it case-insensitively."""
    lines = text.split("\n")
    heads = parse_headings(text)
    by_title = {}
    for h in heads:
        by_title.setdefault(h["title"].lower(), h)
    out, missing = [], []
    for w in wanted:
        h = by_title.get(w.strip().lower())
        if h is None:
            missing.append(w.strip())
        else:
            out.append("\n".join(lines[h["start"]:h["end"]]).rstrip("\n"))
    return "\n\n".join(out), missing


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="excerpt", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    lp = sub.add_parser("list", help="enumerate the file's headings")
    lp.add_argument("--file", required=True)
    gp = sub.add_parser("get", help="emit the named sections byte-for-byte")
    gp.add_argument("--file", required=True)
    gp.add_argument("--sections", required=True,
                    help="comma-separated heading titles (case-insensitive)")
    args = ap.parse_args(argv)

    path = Path(args.file)
    if not path.is_file():
        print(f"error: no such file: {path}", file=sys.stderr)
        return 2
    text = path.read_text()

    if args.cmd == "list":
        for h in parse_headings(text):
            print(f"{'  ' * (h['level'] - 1)}{h['title']}")
        return 0

    wanted = [s for s in args.sections.split(",") if s.strip()]
    body, missing = extract(text, wanted)
    if missing:
        print(f"error: section(s) not found in {path}: {', '.join(missing)}", file=sys.stderr)
        print("available sections:", file=sys.stderr)
        for h in parse_headings(text):
            print(f"  {h['title']}", file=sys.stderr)
        return 1
    print(body)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
