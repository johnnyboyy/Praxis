"""Parse a domain-file.md into a `Domain`.

A domain file is a YAML frontmatter block delimited by `---` lines, followed by
a markdown body that is itself YAML with top-level `conventions:` and
`principles:` sequences (see domain-file.md 'File anatomy').
"""

from __future__ import annotations

from pathlib import Path

import yaml

from .models import Convention, Domain, Principle


def _split_frontmatter(text: str) -> tuple[str, str]:
    """Split leading `---`-delimited frontmatter from the body.

    Returns (frontmatter_text, body_text). Raises ValueError if the file does
    not open with a frontmatter block.
    """
    lines = text.splitlines(keepends=True)
    # Skip any leading blank lines before the opening delimiter.
    idx = 0
    while idx < len(lines) and lines[idx].strip() == "":
        idx += 1
    if idx >= len(lines) or lines[idx].strip() != "---":
        raise ValueError("domain file must begin with a '---' frontmatter block")
    start = idx + 1
    for end in range(start, len(lines)):
        if lines[end].strip() == "---":
            frontmatter = "".join(lines[start:end])
            body = "".join(lines[end + 1 :])
            return frontmatter, body
    raise ValueError("unterminated frontmatter block (missing closing '---')")


def parse_domain_file(path, owner: str | None = None) -> Domain:
    """Parse a domain file at `path` into a `Domain`.

    `owner` is the derived/passed-in source. If the file also declares `owner`
    in frontmatter, the two must agree; the passed-in value is authoritative.
    """
    path = Path(path)
    text = path.read_text(encoding="utf-8")

    frontmatter_text, body_text = _split_frontmatter(text)

    fm = yaml.safe_load(frontmatter_text) or {}
    if not isinstance(fm, dict):
        raise ValueError(f"{path}: frontmatter must be a YAML mapping")

    # Required frontmatter fields.
    for required in ("id", "subject", "posture"):
        if fm.get(required) is None:
            raise ValueError(f"{path}: missing required frontmatter field '{required}'")

    # Owner reconciliation: file-declared owner (if any) must agree with the
    # passed-in owner; the derived/passed owner is authoritative.
    declared_owner = fm.get("owner")
    if declared_owner is not None and owner is not None and declared_owner != owner:
        raise ValueError(
            f"{path}: frontmatter owner '{declared_owner}' disagrees with "
            f"derived owner '{owner}'"
        )
    resolved_owner = owner if owner is not None else declared_owner

    # Body is YAML with top-level `conventions` and `principles` sequences.
    body = yaml.safe_load(body_text) or {}
    if not isinstance(body, dict):
        raise ValueError(f"{path}: body must be a YAML mapping with conventions/principles")

    conventions = [
        Convention(id=c["id"], rule=c["rule"]) for c in (body.get("conventions") or [])
    ]
    principles = [
        Principle(
            id=p["id"],
            rule=p["rule"],
            condition=p["condition"],
            reason=p["reason"],
        )
        for p in (body.get("principles") or [])
    ]

    return Domain(
        id=fm["id"],
        owner=resolved_owner,
        subject=fm["subject"],
        posture=fm["posture"],
        applies_when=fm.get("applies-when") or [],
        universal=fm.get("universal", False),
        task_kinds=fm.get("task-kinds") or [],
        workflows=fm.get("workflows") or [],
        labels=fm.get("labels") or [],
        conventions=conventions,
        principles=principles,
        source_path=path,
    )
