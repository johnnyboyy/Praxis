#!/usr/bin/env python3
"""adapters — the direct corpora provider binding (P9 of docs/CONDUCTOR-PLAN.md).

This is the wiring layer, not the core: unlike journal/situation/providers/run/schedule/views (which
import neither praxis nor corpora), this module knows corpora's CLI and calls it. It builds a
`CorporaProvider` by invoking `corpus.py`'s read verbs DIRECTLY (`manifest`, `select`,
`emit-spawn-parts`), collapsing the praxis engine-plugin hop — no manifest resolution, no generic
argv builder, no `engine.call_json` indirection. One subprocess, straight to the engine.

`corpora_provider(root)` is the production seam the conductor composes through; the engine-plugin
path stays available for a project that registers a *different* engine, but the conductor's own
corpora access no longer detours through it.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from providers import CorporaProvider

# corpus.py lives beside the conductor in the repo: <repo>/corpora/scripts/corpus.py.
DEFAULT_CORPUS_PY = Path(__file__).resolve().parents[1] / "corpora" / "scripts" / "corpus.py"

# The capabilities corpora declares — reported by the provider so the conductor can see what corpora
# offers without this module hardcoding a judgment about it (parity with the engine manifest).
CORPORA_CAPABILITIES = ["compose", "spawn-parts", "manifest", "ratify", "retrospect"]


def _call(corpus_py: Path, root: str, argv_tail: list[str], timeout: int) -> dict | None:
    """Invoke corpus.py directly (root is a global option, before the verb) and parse its JSON.
    Returns None on any failure — the provider degrades exactly as it does for a null engine."""
    try:
        p = subprocess.run([sys.executable, str(corpus_py), "--root", root, *argv_tail],
                           capture_output=True, text=True, timeout=timeout)
    except (subprocess.SubprocessError, OSError):
        return None
    if p.returncode != 0:
        return None
    try:
        return json.loads(p.stdout)
    except json.JSONDecodeError:
        return None


def corpora_provider(root: str | Path, *, corpus_py: str | Path | None = None,
                     mode: str = "features", parts: bool = True, timeout: int = 30) -> CorporaProvider:
    """A `CorporaProvider` bound directly to corpora's CLI. `mode='features'` (default, the P8
    decoupling) selects by situation features via corpora's `manifest`; `mode='units'` uses the
    legacy `select` verb keyed on the situation's label noun. `parts=True` wires the `emit-spawn-parts`
    verb so composed domains come back as body artifacts."""
    corpus = Path(corpus_py) if corpus_py else DEFAULT_CORPUS_PY
    root = str(root)

    def manifest_fn(r: str) -> list:
        d = _call(corpus, r or root, ["manifest", "--json"], timeout) or {}
        return d.get("domains", [])

    def select_fn(r: str, uow: str) -> dict:
        d = _call(corpus, r or root, ["select", "--unit-of-work", uow, "--json"], timeout) or {}
        return {"domains": d.get("domains", []), "warnings": d.get("warnings", [])}

    def parts_fn(r: str, domains: list) -> dict:
        d = _call(corpus, r or root, ["emit-spawn-parts", "--domains", ",".join(domains), "--json"],
                  timeout) or {}
        return {"parts": d.get("parts", []), "problems": d.get("problems", [])}

    kwargs = {"parts_fn": parts_fn if parts else None, "capabilities": CORPORA_CAPABILITIES}
    if mode == "features":
        return CorporaProvider(manifest_fn=manifest_fn, **kwargs)
    if mode == "units":
        return CorporaProvider(select_fn=select_fn, **kwargs)
    raise ValueError(f"mode must be 'features' or 'units', got {mode!r}")
