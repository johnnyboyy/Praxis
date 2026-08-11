#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from typing import Callable, Protocol, TypedDict, runtime_checkable

from situation import Situation, surface_task_kind_gap


@runtime_checkable
class Provider(Protocol):

    def compose(self, situation: Situation) -> dict: ...
    def ratify(self, proposal: dict) -> dict: ...
    def retrospect(self, scope: dict) -> dict: ...
    def capabilities(self) -> list[str]: ...


class NullProvider:

    NOTE = "no provider registered — degraded to facts"

    def compose(self, situation: Situation) -> dict:
        return {"artifacts": [], "stance": None, "note": self.NOTE, "domains": [],
                "routed_kind": situation.routed_kind}

    def ratify(self, proposal: dict) -> dict:
        return {"verdict": "unavailable", "note": self.NOTE}

    def retrospect(self, scope: dict) -> dict:
        return {"signals": [], "note": self.NOTE}

    def capabilities(self) -> list[str]:
        return []


class Selection(TypedDict):
    domains: list[str]
    warnings: list[str]


class Parts(TypedDict):
    parts: list
    problems: list


class DomainSpec(TypedDict):
    name: str
    subject: str
    universal: bool
    applies_when: list


SelectFn = Callable[[str, str], Selection]
PartsFn = Callable[[str, list], Parts]
ManifestFn = Callable[[str], list[DomainSpec]]


def _norm(v) -> str:
    return str(v).strip().lower()


def _applies_when_matches(applies_when: list, project_shape: dict) -> bool:
    for pred in applies_when or []:
        for key, val in pred.items():
            actual = _norm(project_shape.get(key, ""))
            if val == "not-none":
                if actual in ("", "none"):
                    return False
                continue
            options = val if isinstance(val, list) else [val]
            if actual not in {_norm(o) for o in options}:
                return False
    return True


def select_by_features(manifest: list, situation: Situation) -> list[str]:
    selected = []
    for d in manifest or []:
        if d.get("universal"):
            selected.append(d["name"])
            continue
        if not situation.classified:
            continue
        if d.get("subject") != situation.subject:
            continue
        if not _applies_when_matches(d.get("applies_when", []), situation.project_shape or {}):
            continue
        selected.append(d["name"])
    return sorted(selected)


class CorporaProvider:

    def __init__(self, select_fn: SelectFn | None = None, parts_fn: PartsFn | None = None,
                 capabilities: list[str] | None = None,
                 ratify_fn: Callable[[dict], dict] | None = None,
                 retrospect_fn: Callable[[dict], dict] | None = None,
                 manifest_fn: ManifestFn | None = None):
        if select_fn is None and manifest_fn is None:
            raise ValueError("CorporaProvider needs a select_fn (unit-of-work mode) or a "
                             "manifest_fn (feature mode)")
        self._select = select_fn
        self._parts = parts_fn
        self._capabilities = list(capabilities or [])
        self._ratify = ratify_fn
        self._retrospect = retrospect_fn
        self._manifest = manifest_fn

    def _compose_key(self, situation: Situation) -> str:
        if not situation.classified:
            return "unclassified"
        return situation.label or situation.task_kind

    def compose(self, situation: Situation) -> dict:
        root = situation.root or ""
        if self._manifest is not None:
            domains = select_by_features(self._manifest(root) or [], situation)
            notes: list = []
        else:
            sel = self._select(root, self._compose_key(situation)) or {}
            domains = sel.get("domains", []) or []
            notes = list(sel.get("warnings", []) or [])
        artifacts: list[dict] = []
        if self._parts and domains:
            parts = self._parts(root, domains) or {}
            notes = notes + list(parts.get("problems", []) or [])
            for p in parts.get("parts", []) or []:
                artifacts.append({"slot": p.get("slot"), "body": p.get("body"),
                                  "provenance": "corpora"})
        stance = situation.phase if situation.phase in ("divergent", "convergent") else None
        return {"artifacts": artifacts, "stance": stance,
                "note": "; ".join(notes) if notes else "ok",
                "domains": domains, "routed_kind": situation.routed_kind}

    def ratify(self, proposal: dict) -> dict:
        if self._ratify is None:
            return {"verdict": "unavailable", "note": "ratify not wired for this provider"}
        return self._ratify(proposal)

    def retrospect(self, scope: dict) -> dict:
        if self._retrospect is None:
            return {"signals": [], "note": "retrospect not wired for this provider"}
        return self._retrospect(scope)

    def capabilities(self) -> list[str]:
        return list(self._capabilities)


def consult(provider: Provider, situation: Situation, root: Path | None = None,
            note: str | None = None) -> dict:
    gap = None
    if root is not None and situation.has_gap:
        gap = surface_task_kind_gap(root, situation, note=note)
    result = dict(provider.compose(situation))
    result["gap_surfaced"] = gap is not None
    result["routed_kind"] = situation.routed_kind
    return result
