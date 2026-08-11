#!/usr/bin/env python3
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
        return self.fit != "none"

    @property
    def routed_kind(self) -> str:
        return self.task_kind if self.classified else UNCLASSIFIED

    @property
    def has_gap(self) -> bool:
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
    if fit not in ("loose", "none"):
        return None
    sit = situation.to_dict() if isinstance(situation, Situation) else situation
    return journal.append(root, "conductor.gap", vocabulary=vocabulary, chosen=chosen,
                          suggested=suggested, fit=fit, intent=intent, situation=sit, note=note)


def surface_task_kind_gap(root: Path, situation: Situation, note: str | None = None) -> dict | None:
    return surface_gap(root, vocabulary="task_kind", chosen=situation.task_kind,
                       suggested=situation.suggested_kind, fit=situation.fit,
                       intent=situation.intent, situation=situation, note=note)
