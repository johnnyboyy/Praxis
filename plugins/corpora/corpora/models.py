"""Dataclasses for the judgment injector's parse layer.

These mirror the domain-file.md schema: a `Domain` carries frontmatter facets
plus two bodies (`conventions` and `principles`) that inject under different
confidence rules. `weight` and `registration_index` are mutable runtime fields
set later by the selection pipeline, not by the parser.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Convention:
    """A hardened, terse, imperative rule with no stated rationale."""

    id: str
    rule: str


@dataclass
class Principle:
    """A weighable rule with a load-bearing `reason` the model reads."""

    id: str
    rule: str
    condition: str
    reason: str


@dataclass
class Domain:
    """One subject/decision-class of reusable judgment.

    Frontmatter facets drive mechanical selection; the two bodies inject under
    different confidence rules. `weight` and `registration_index` are runtime
    state set by selection, not by parsing.
    """

    id: str
    owner: str | None
    subject: str
    posture: str
    applies_when: list[dict]
    universal: bool
    task_kinds: list[str]
    workflows: list[str]
    labels: list[str]
    conventions: list[Convention]
    principles: list[Principle]
    source_path: Path | None = None
    # Mutable runtime fields, defaulted here and set later by selection.
    weight: float = 1.0
    registration_index: int = 0

    @property
    def fq(self) -> str:
        """Fully-qualified identity: `owner/id`."""
        return f"{self.owner}/{self.id}"
