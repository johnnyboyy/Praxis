#!/usr/bin/env python3
"""situation — the feature object a provider composes against, and the gap-surfacing hook.

This is P3 of docs/CONDUCTOR-PLAN.md. A `Situation` is the placement-agnostic description of a unit
of work the conductor hands a judgment provider: not another system's unit-of-work nouns, but the
features (task_kind, intent, subject, phase, project_shape, targets) a provider maps to its own
domains. The conductor consults the provider *with a situation*, folding in what it returns.

The core mechanism (docs/CONDUCTOR-PLAN.md "The point" / the prime directive) rides here too. Every
situation carries two things harvested from the model naturally: `suggested_kind` (what it would
freely call this) and `fit` (how well the chosen seed verb fits that suggestion). The divergence
between the two is the always-on gap detector; `unclassified` is not a value the model picks but a
*derived* one (`fit == "none"`). When `fit` is `loose`/`none`, `surface_gap` records a
`conductor.gap` event — the raw material for vocabulary accretion, symmetric to corpora's ratify
gate. The counter/tally over these lives in journal.gap_candidates.

Closed vocabularies (their honored fallout is `unclassified`, derived not chosen):
  task_kind  — create | change | explore   (the minimal seed the work RUNS under)
  subject    — coding | design | process | prose
  phase      — divergent | convergent | none
  fit        — clean | loose | none
`suggested_kind` and `label` are OPEN free-text (the candidate verb, and the bridge noun a provider
keys on); they grow by discovery, so they are never validated against a closed set.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import journal

TASK_KINDS = ("create", "change", "explore")
SUBJECTS = ("coding", "design", "process", "prose")
PHASES = ("divergent", "convergent", "none")
FITS = ("clean", "loose", "none")

VOCABULARIES = ("task_kind", "subject", "phase", "workflow", "unit")

UNCLASSIFIED = "unclassified"


@dataclass
class Situation:
    """The feature object (docs/CONDUCTOR-PLAN.md "Situation"). `task_kind`, `intent`, `subject` are
    the minimum a provider needs; the rest refine placement. `suggested_kind` + `fit` are the gap
    detector and are always collected, never guessed — a caller that has not asked the model leaves
    `suggested_kind=None` and `fit="clean"` (no divergence claimed, no gap)."""

    task_kind: str
    intent: str
    subject: str
    suggested_kind: str | None = None
    fit: str = "clean"
    phase: str = "none"
    project_shape: dict = field(default_factory=dict)
    root: str | None = None
    targets: list = field(default_factory=list)
    workflow: str | None = None
    label: str | None = None

    def __post_init__(self):
        self._check("task_kind", self.task_kind, TASK_KINDS)
        self._check("subject", self.subject, SUBJECTS)
        self._check("phase", self.phase, PHASES)
        self._check("fit", self.fit, FITS)

    @staticmethod
    def _check(name: str, value: str, allowed: tuple[str, ...]):
        if value not in allowed:
            raise ValueError(f"{name} must be one of {allowed}, got {value!r}")

    @property
    def classified(self) -> bool:
        """False exactly when `fit == "none"` — the derived `unclassified` state."""
        return self.fit != "none"

    @property
    def routed_kind(self) -> str:
        """The task_kind-vocabulary value work is classified under: the chosen seed verb normally,
        or the DERIVED `unclassified` when the model rated the fit `none`. `unclassified` is never
        picked — it falls out of a `none` rating."""
        return self.task_kind if self.classified else UNCLASSIFIED

    @property
    def has_gap(self) -> bool:
        """Whether this situation's own task_kind axis diverges enough to surface (loose/none)."""
        return self.fit in ("loose", "none")

    def to_dict(self) -> dict:
        return {
            "task_kind": self.task_kind,
            "suggested_kind": self.suggested_kind,
            "fit": self.fit,
            "intent": self.intent,
            "subject": self.subject,
            "phase": self.phase,
            "project_shape": self.project_shape,
            "root": self.root,
            "targets": self.targets,
            "workflow": self.workflow,
            "label": self.label,
        }


def surface_gap(root: Path, *, vocabulary: str, chosen: str, suggested: str | None, fit: str,
                intent: str, situation: dict | Situation | None = None,
                note: str | None = None) -> dict | None:
    """Record a `conductor.gap` event when `fit` is `loose`/`none` — the surfacing half of the
    conductor's ratify gate (docs/CONDUCTOR-PLAN.md "Gap"). Work still ran under `chosen`; the gap
    captures that the model's free `suggested` name diverged, so recurrence of `suggested` across
    gaps (journal.gap_candidates) can later mint it into real vocabulary. Returns the written event,
    or None when `fit` is `clean` (no divergence to surface).

    Generic over the vocabulary: `chosen` is the seed value work ran under and `suggested` the free
    candidate, for task_kind or any other closed vocabulary."""
    if fit not in ("loose", "none"):
        return None
    sit = situation.to_dict() if isinstance(situation, Situation) else situation
    return journal.append(root, "conductor.gap", vocabulary=vocabulary, chosen=chosen,
                          suggested=suggested, fit=fit, intent=intent, situation=sit, note=note)


def surface_task_kind_gap(root: Path, situation: Situation, note: str | None = None) -> dict | None:
    """The always-on detector for the primary axis: surface a task_kind gap straight from a
    situation's own `suggested_kind` / `fit` (a no-op when `fit == "clean"`)."""
    return surface_gap(root, vocabulary="task_kind", chosen=situation.task_kind,
                       suggested=situation.suggested_kind, fit=situation.fit,
                       intent=situation.intent, situation=situation, note=note)
