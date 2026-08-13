#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

import journal
from contributors import contributors_for
from workflow import (
    DELIVERIES,
    SEED_PHASES,
    SEED_WORKFLOWS,
    STANCES,
    Phase,
    Workflow,
)

def validate_phase(obj) -> list[str]:
    problems: list[str] = []
    if not isinstance(obj, Phase):
        return ["not a Phase"]
    if not isinstance(obj.name, str) or not obj.name.strip():
        problems.append("name must be a non-empty str")
    if obj.stance not in STANCES:
        problems.append(f"stance must be one of {STANCES}")
    if obj.delivery not in DELIVERIES:
        problems.append(f"delivery must be one of {DELIVERIES}")
    return problems

def validate_workflow(obj, phases: dict[str, Phase]) -> list[str]:
    problems: list[str] = []
    if not isinstance(obj, Workflow):
        return ["not a Workflow"]
    if not isinstance(obj.name, str) or not obj.name.strip():
        problems.append("name must be a non-empty str")
    if not obj.phases:
        problems.append("phases must be non-empty")
    for p in obj.phases or []:
        if getattr(p, "name", None) not in phases:
            problems.append(f"phase {getattr(p, 'name', p)!r} not in phase table")
    for edge in obj.edges or []:
        try:
            frm, to = edge[0], edge[1]
            when = edge[2]
        except (TypeError, IndexError):
            problems.append(f"malformed edge {edge!r}")
            continue
        if frm not in phases:
            problems.append(f"edge endpoint {frm!r} names an unknown phase")
        if to not in phases:
            problems.append(f"edge endpoint {to!r} names an unknown phase")
        if when == "fact":
            pred = edge[4] if len(edge) > 4 else None
            if not callable(pred):
                problems.append(
                    f"predicate edge {frm!r}->{to!r} must carry a callable predicate")
    return problems

def _log_collision(root, kind: str, name: str, what: str) -> None:
    try:
        journal.append(root, f"{what}.collision", kind=kind, name=name)
    except Exception:
        pass

def _provider(c, method: str):
    provider = getattr(c, method, None)
    if not callable(provider):
        return None
    try:
        items = provider()
    except Exception:
        return None
    return items or []

def resolve_phases(root, contributors=None) -> dict[str, Phase]:
    if contributors is None:
        contributors = contributors_for(root)
    out: dict[str, Phase] = dict(SEED_PHASES)
    plugin_names: set[str] = set()
    for c in contributors:
        items = _provider(c, "phases")
        if items is None:
            continue
        for p in items:
            if validate_phase(p):
                continue
            if p.name in SEED_PHASES:
                _log_collision(root, "seed", p.name, "phase")
                continue
            if p.name in plugin_names:
                _log_collision(root, "plugin", p.name, "phase")
                continue
            out[p.name] = p
            plugin_names.add(p.name)
    return out

def resolve_workflows(root, contributors=None, phases=None) -> dict[str, Workflow]:
    if contributors is None:
        contributors = contributors_for(root)
    if phases is None:
        phases = resolve_phases(root, contributors)
    out: dict[str, Workflow] = dict(SEED_WORKFLOWS)
    plugin_names: set[str] = set()
    for c in contributors:
        items = _provider(c, "workflows")
        if items is None:
            continue
        for w in items:
            if validate_workflow(w, phases):
                continue
            if w.name in SEED_WORKFLOWS:
                _log_collision(root, "seed", w.name, "workflow")
                continue
            if w.name in plugin_names:
                _log_collision(root, "plugin", w.name, "workflow")
                continue
            out[w.name] = w
            plugin_names.add(w.name)
    return out
