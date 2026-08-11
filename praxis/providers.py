#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

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


def provider_for(root: str | Path) -> Provider:
    # engine-resolution seam: no engine is wired into praxis-core, so every root
    # degrades to facts. Registering an engine replaces this body with a lookup.
    return NullProvider()


def consult(provider: Provider, situation: Situation, root: Path | None = None,
            note: str | None = None) -> dict:
    gap = None
    if root is not None and situation.has_gap:
        gap = surface_task_kind_gap(root, situation, note=note)
    result = dict(provider.compose(situation))
    result["gap_surfaced"] = gap is not None
    result["routed_kind"] = situation.routed_kind
    return result
