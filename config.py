#!/usr/bin/env python3
"""config — the per-root namespaced config store (`.praxis/config.json`).

A JSON object of `{"<namespace>": {…}}`. The unnamed scope (`namespace=None`) is reserved for
praxis-core needs; every named scope belongs to a plugin (its `source`), which reads and writes
only its own section. Values are stored raw — a plugin may persist lists, numbers, nested objects,
not just strings. Its existence (not its contents) is what marks a directory a managed praxis root,
so a clean root is simply `{}`.
"""
from __future__ import annotations

import json
from pathlib import Path

CONFIG_NAME = "config.json"


def path(root: str | Path) -> Path:
    return Path(root) / ".praxis" / CONFIG_NAME


def read(root: str | Path, namespace: str | None = None) -> dict:
    return _load(root).get(_scope(namespace), {})


def write(root: str | Path, namespace: str | None, updates: dict) -> None:
    scopes = _load(root)
    scope = _scope(namespace)
    merged = dict(scopes.get(scope, {}))
    merged.update({str(k): v for k, v in updates.items()})
    scopes[scope] = merged
    _dump(root, scopes)


def ensure(root: str | Path) -> bool:
    """Create an empty `.praxis/config.json` if absent (marking the root). True if it was created."""
    p = path(root)
    if p.exists():
        return False
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{}\n")
    return True


def _scope(namespace: str | None) -> str:
    return "" if namespace is None else namespace


def _load(root: str | Path) -> dict:
    try:
        data = json.loads(path(root).read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _dump(root: str | Path, scopes: dict) -> None:
    p = path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(scopes, indent=2, sort_keys=True) + "\n")
