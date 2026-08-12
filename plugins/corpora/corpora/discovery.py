"""Discovery & precedence — assemble the composed domain pool.

The injector ships no domains of its own. Each phase it discovers the pool from
exactly two source kinds — registered praxis contributors that carry a
`domains_dir`, and the always-on project-local pool at `root/.praxis/domains` —
then merges them under the two-layer precedence rules (plugin < project) from
`domain-file.md`.
"""

from __future__ import annotations

import sys
from pathlib import Path

# praxis exposes `contributors_for`; make it importable.
_PRAXIS_PATH = str(Path(__file__).resolve().parents[3])
if _PRAXIS_PATH not in sys.path:
    sys.path.insert(0, _PRAXIS_PATH)

from contributors import contributors_for  # noqa: E402

from .parser import parse_domain_file


def discover_domain_dirs(root) -> list[tuple[str, Path]]:
    """Return `(owner, dir)` pairs for every source that may carry domains.

    Registered contributors that expose a `domains_dir` attribute contribute
    their directory (owner = the contributor's `source`). The project-local
    pool at `root/.praxis/domains` is always appended last (owner = 'project'),
    even when that directory is absent. The injector itself has no
    `domains_dir`, so it contributes no directory.
    """
    root = Path(root)
    dirs: list[tuple[str, Path]] = []
    for c in contributors_for(root):
        domains_dir = getattr(c, "domains_dir", None)
        if domains_dir:
            dirs.append((c.source, Path(domains_dir)))
    dirs.append(("project", root / ".praxis" / "domains"))
    return dirs


def merge_pool(dirs) -> list[Domain]:  # noqa: F821 - Domain imported lazily below
    """Parse and merge every discovered directory into one surviving pool.

    Precedence (from `domain-file.md`), applied here and nowhere else:
      (a) same `owner/id` twice within one owner -> hard error; skip the
          duplicate and report it (never silent last-wins).
      (b) cross-layer, same bare `id`: the project version REPLACES the plugin
          version wholesale (the plugin domain is dropped entirely).
      (c) peer plugins (same layer) with the same bare `id` COEXIST as distinct
          `owner/id` entities.
      (d) different bare ids coexist.

    `registration_index` is stamped in discovery/parse order (project entries
    come after plugins per the `dirs` order) for later tie-breaking.
    """
    parsed: list[Domain] = []
    errors: list[str] = []
    seen_fq: set[str] = set()
    index = 0

    for source, directory in dirs:
        directory = Path(directory)
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.md")):
            domain = parse_domain_file(path, owner=source)
            domain.owner = source  # stamp owner from the source, authoritative
            fq = domain.fq
            if fq in seen_fq:
                errors.append(
                    f"corpora: duplicate domain '{fq}' at {path}; skipping"
                )
                continue
            seen_fq.add(fq)
            domain.registration_index = index
            index += 1
            parsed.append(domain)

    # (b) cross-layer wholesale override: a project bare id drops every plugin
    # domain sharing that bare id.
    project_ids = {d.id for d in parsed if d.owner == "project"}
    survivors = [
        d for d in parsed if not (d.owner != "project" and d.id in project_ids)
    ]

    for err in errors:
        print(err, file=sys.stderr)

    return survivors


from .models import Domain  # noqa: E402  (used only as a return annotation)
