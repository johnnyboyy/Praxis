#!/usr/bin/env python3
"""providers — the judgment-provider seam (P3 of docs/CONDUCTOR-PLAN.md).

The conductor is judgment-agnostic: at its lifecycle points it consults a registered **provider**
with a `Situation` and folds in what the provider returns, rather than calling a hardcoded engine.
This module defines that seam — the `Provider` protocol, a `NullProvider` the conductor degrades to
when nothing is registered, and `CorporaProvider`, which wraps corpora (one provider among possible
many) behind `compose`.

Decoupling discipline: conductor never imports praxis or corpora. `CorporaProvider` is fed plain
callables that speak corpora's read capabilities (`select` → domains, `emit-spawn-parts` → bodies);
the orchestration layer that HAS the engine manifest builds those callables (via praxis's
engine.call_json) and hands them in. Tests inject stubs; the real wrap injects the engine calls. So
the core stays transport-free and provider-neutral, and a second engine is just a second provider.

`consult` is the hook the conductor calls: it surfaces the gap (the always-on detector) and then
composes, returning the artifacts plus whether a gap was recorded.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Protocol, TypedDict, runtime_checkable

from situation import Situation, surface_task_kind_gap


@runtime_checkable
class Provider(Protocol):
    """What a provider exposes (docs/CONDUCTOR-PLAN.md "Provider protocol"). `compose` is the
    lifecycle hook; `ratify`/`retrospect` are housekeeping capabilities the conductor triggers;
    `capabilities` lets the conductor discover what a provider can do without naming it."""

    def compose(self, situation: Situation) -> dict: ...
    def ratify(self, proposal: dict) -> dict: ...
    def retrospect(self, scope: dict) -> dict: ...
    def capabilities(self) -> list[str]: ...


class NullProvider:
    """The degrade path: no provider registered. Every hook returns a well-formed empty result with
    a note, so the conductor proceeds on facts alone instead of crashing — the same discipline as
    praxis's empty engine slot."""

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
    """Whether a domain's applies-when predicates hold for a project shape — the conductor-side
    evaluation of corpora's shape predicates (mirrors corpus.applies_when_matches). `applies_when`
    is corpora's manifest shape: a list of single-key dicts `{key: value | [values] | "not-none"}`."""
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
    """Map a situation's FEATURES → domain names natively (docs/CONDUCTOR-PLAN.md P8), with no
    unit-of-work string. Universal domains always apply; a `fit==none` situation composes universals
    only (the derived `unclassified`); otherwise a non-universal domain is selected when its
    `subject` matches the situation's subject AND its applies-when predicates match the situation's
    `project_shape`. This is the decoupling: corpora declares each domain's features (the manifest),
    the provider maps the situation onto them."""
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
    """Wraps corpora as a provider behind `compose`, in one of two selection modes:

    - FEATURE mode (`manifest_fn` supplied) — the P8 decoupling: the provider fetches corpora's
      domain manifest and maps the situation's FEATURES (subject + project_shape predicates) onto it
      via `select_by_features`, with no unit-of-work string. This is the orchestrator-agnostic path.
    - UNIT-OF-WORK mode (`select_fn` only) — the legacy bridge: keys corpora's `select` on the
      situation's `label` noun (or the seed `task_kind` when unlabeled). Kept for backward compat.

    Either way a `fit==none` situation routes to `unclassified` (universals only) instead of
    composing the junk drawer for a forced match, and a `parts_fn` (when supplied) turns the selected
    domains into body `artifacts`. `capabilities` is the wrapped engine's declared capability list;
    `ratify`/`retrospect` degrade unless their callables are supplied."""

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
    """The conductor's compose hook: surface the vocabulary gap (when the situation's own task_kind
    axis diverges — loose/none), then compose against the provider. Returns the provider's compose
    result annotated with `gap_surfaced` and the `routed_kind`. Passing `root` enables gap
    recording; without it the divergence is still reflected in `routed_kind` but nothing is written.
    """
    gap = None
    if root is not None and situation.has_gap:
        gap = surface_task_kind_gap(root, situation, note=note)
    result = dict(provider.compose(situation))
    result["gap_surfaced"] = gap is not None
    result["routed_kind"] = situation.routed_kind
    return result
