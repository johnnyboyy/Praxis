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
from typing import Callable, Protocol, runtime_checkable

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


# Callable shapes CorporaProvider is fed — corpora's two read capabilities, as plain functions.
SelectFn = Callable[[str, str], dict]          # (root, unit_of_work) -> {"domains", "warnings"}
PartsFn = Callable[[str, list], dict]          # (root, domains)      -> {"parts", "problems"}


class CorporaProvider:
    """Wraps corpora as a provider behind `compose`. Given a situation it keys corpora's `select` on
    the bridge noun (`label`, or the seed `task_kind` when unlabeled) — except when the model rated
    the fit `none`, where it routes to `unclassified` (composing corpora's universal domains only)
    instead of composing the junk drawer for a forced match. When a `parts_fn` is supplied it also
    fetches the domain bodies and returns them as `artifacts`; without one it returns the domain
    names alone.

    `capabilities` is the declared capability list of the wrapped engine (so the conductor can see
    corpora offers `ratify`/`retrospect` without this module naming them); `ratify`/`retrospect`
    degrade unless their callables are supplied — this phase wraps `compose`."""

    def __init__(self, select_fn: SelectFn, parts_fn: PartsFn | None = None,
                 capabilities: list[str] | None = None,
                 ratify_fn: Callable[[dict], dict] | None = None,
                 retrospect_fn: Callable[[dict], dict] | None = None):
        self._select = select_fn
        self._parts = parts_fn
        self._capabilities = list(capabilities or [])
        self._ratify = ratify_fn
        self._retrospect = retrospect_fn

    def _compose_key(self, situation: Situation) -> str:
        # fit == none ⇒ route to unclassified (universals only), never the forced verb's full set.
        if not situation.classified:
            return "unclassified"
        return situation.label or situation.task_kind

    def compose(self, situation: Situation) -> dict:
        root = situation.root or ""
        key = self._compose_key(situation)
        sel = self._select(root, key) or {}
        domains = sel.get("domains", []) or []
        notes = list(sel.get("warnings", []) or [])
        artifacts: list[dict] = []
        if self._parts and domains:
            parts = self._parts(root, domains) or {}
            notes.extend(parts.get("problems", []) or [])
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
