#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from providers import CorporaProvider

DEFAULT_CORPUS_PY = Path(__file__).resolve().parents[1] / "corpora" / "scripts" / "corpus.py"

CORPORA_CAPABILITIES = ["compose", "spawn-parts", "manifest", "ratify", "retrospect"]


def _call(corpus_py: Path, root: str, argv_tail: list[str], timeout: int) -> dict | None:
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
