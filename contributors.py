#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol, runtime_checkable

import journal
from situation import Situation, surface_task_kind_gap

@dataclass
class Contribution:

    source: str
    title: str
    body: str
    priority: int = 0
    meta: dict | None = None

@runtime_checkable
class Contributor(Protocol):

    def contribute(self, situation: Situation) -> list[Contribution]: ...

@dataclass
class HookContext:

    root: Path
    step: str
    unit: "object | None" = None
    receipt: dict | None = None
    verdict: dict | None = None

    def add_note(self, source: str, body: str, **extra) -> dict:
        uid = getattr(self.unit, "id", None)
        return journal.note(self.root, unit=uid, source=source, body=body, **extra)

    def notes(self, unit: str | None = None) -> list[dict]:
        return journal.notes(self.root, unit=unit)

StepHook = Callable[[HookContext], None]

def fire(contributors, step: str, ctx: HookContext) -> None:
    for c in contributors:
        provider = getattr(c, "hooks", None)
        table = provider() if callable(provider) else {}
        hook = (table or {}).get(step)
        if hook is not None:
            hook(ctx)

def surface_for(contributors, situation: Situation) -> list[str] | None:
    claimed: list[str] = []
    for c in contributors:
        provider = getattr(c, "surface", None)
        if not callable(provider):
            continue
        try:
            globs = provider(situation)
        except Exception:
            continue
        if globs:
            claimed.extend(globs)
    return sorted(set(claimed)) or None

def validate_contributor(obj) -> list[str]:
    problems: list[str] = []
    source = getattr(obj, "source", None)
    if not isinstance(source, str) or not source.strip():
        problems.append("source must be a non-empty str")
    if not callable(getattr(obj, "contribute", None)):
        problems.append("contribute must be callable")
    if hasattr(obj, "hooks") and not callable(getattr(obj, "hooks")):
        problems.append("hooks, when present, must be callable")
    if hasattr(obj, "surface") and not callable(getattr(obj, "surface")):
        problems.append("surface, when present, must be callable")
    if hasattr(obj, "phases") and not callable(getattr(obj, "phases")):
        problems.append("phases, when present, must be callable")
    if hasattr(obj, "workflows") and not callable(getattr(obj, "workflows")):
        problems.append("workflows, when present, must be callable")
    return problems

def _prepend_plugins_path(root: str | Path) -> None:
    import sys

    import config

    dirs = config.read(root).get("plugins_path")
    if not isinstance(dirs, list):
        return
    for entry in dirs:
        if not isinstance(entry, str) or not entry:
            continue
        if entry not in sys.path:
            sys.path.insert(0, entry)

def contributors_for(root: str | Path) -> list[Contributor]:
    import importlib

    import config

    _prepend_plugins_path(root)
    specs = config.read(root, "contributors")
    loaded: list[Contributor] = []
    for name, spec in specs.items():
        try:
            module_path, _, factory_name = spec.rpartition(":")
            if not module_path:
                continue
            module = importlib.import_module(module_path)
            factory = getattr(module, factory_name)
            contributor = factory(root)
        except Exception:
            continue
        if validate_contributor(contributor):
            continue
        loaded.append(contributor)
    return loaded

def gather(contributors, situation: Situation, root: Path | None = None,
           note: str | None = None) -> dict:
    gap = None
    if root is not None and situation.has_gap:
        gap = surface_task_kind_gap(root, situation, note=note)
    contributions: list[Contribution] = []
    for c in contributors:
        contributions.extend(c.contribute(situation) or [])
    contributions.sort(key=lambda c: c.priority)
    return {
        "contributions": contributions,
        "sources": [c.source for c in contributions],
        "routed_kind": situation.routed_kind,
        "gap_surfaced": gap is not None,
        "note": "ok",
    }
