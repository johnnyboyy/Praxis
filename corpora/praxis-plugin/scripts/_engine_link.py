"""_engine_link — how corpora's praxis-plugin scripts reach praxis-core's generic engine resolver.

These scripts are corpora's contribution to praxis: corpora-specific orchestration (ordering,
preconditions, guards) over corpora's own CLI verbs. They depend on praxis-core (the direction a
plugin should depend), never the reverse — praxis-core names nothing here.

This module (1) puts praxis-core's `scripts/` on the path so the generic `engine` resolver is
importable, and (2) loads corpora's capabilities manifest — the one place a corpora verb name and
corpora's CLI location live. A plugin script names a *capability*; the manifest maps it to the verb +
argv shape and declares where `corpus.py` is.
"""
from __future__ import annotations

import sys
from pathlib import Path

_PLUGIN = Path(__file__).resolve().parents[1]              # source: skills/corpora/praxis-plugin
                                                           # imported: <project>/praxis
# This module runs from two layouts: in the source repo (skills/corpora/praxis-plugin/scripts/),
# praxis-core is a sibling of the corpora skill; snapshot-imported into a project
# (<project>/praxis/scripts/), praxis-core is not copied in — it lives at the globally provisioned
# skill. Try each known location and take the first that actually carries the resolver.
_PRAXIS_SCRIPT_CANDIDATES = [
    _PLUGIN.parents[1] / "praxis" / "scripts",                    # source-repo sibling
    Path.home() / ".claude" / "skills" / "praxis" / "scripts",    # global skill (imported layout)
]
for _candidate in _PRAXIS_SCRIPT_CANDIDATES:
    if (_candidate / "engine.py").is_file():
        sys.path.insert(0, str(_candidate))
        break
else:
    raise ImportError(
        "praxis-core's scripts/ not found — looked in: "
        + ", ".join(str(c) for c in _PRAXIS_SCRIPT_CANDIDATES)
    )

import engine  # noqa: E402  praxis-core's generic resolver

MANIFEST_PATH = _PLUGIN / "engine" / "plugins" / "corpora.json"


def manifest() -> dict:
    """Corpora's capabilities manifest (capability→verb map + the corpora CLI location)."""
    return engine.load_manifest(MANIFEST_PATH)


def cli_override(corpus_py: str | None) -> list[str] | None:
    """A test/override CLI for the engine, or None to use the manifest's declared corpus.py."""
    return ["python3", str(corpus_py)] if corpus_py else None
