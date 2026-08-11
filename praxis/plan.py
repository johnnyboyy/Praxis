#!/usr/bin/env python3
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
import journal
from run import Plan, Unit
from schedule import run_dag
from situation import FITS, PHASES, SUBJECTS, TASK_KINDS, Situation


@dataclass
class TaskSpec:

    intent: str
    id: str | None = None
    task_kind: str = "change"
    subject: str = "coding"
    suggested_kind: str | None = None
    fit: str = "clean"
    phase: str = "none"
    targets: list = field(default_factory=list)
    project_shape: dict = field(default_factory=dict)
    workflow: str | None = None
    label: str | None = None
    depends_on: list = field(default_factory=list)

    def __post_init__(self):
        for name, value, allowed in (("task_kind", self.task_kind, TASK_KINDS),
                                     ("subject", self.subject, SUBJECTS),
                                     ("phase", self.phase, PHASES),
                                     ("fit", self.fit, FITS)):
            if value not in allowed:
                raise ValueError(f"{name} must be one of {allowed}, got {value!r}")

    @classmethod
    def from_dict(cls, d: dict) -> "TaskSpec":
        return cls(intent=d["intent"], id=d.get("id"), task_kind=d.get("task_kind", "change"),
                   subject=d.get("subject", "coding"), suggested_kind=d.get("suggested_kind"),
                   fit=d.get("fit", "clean"), phase=d.get("phase", "none"),
                   targets=list(d.get("targets", []) or []),
                   project_shape=dict(d.get("project_shape", {}) or {}),
                   workflow=d.get("workflow"), label=d.get("label"),
                   depends_on=list(d.get("depends_on", []) or []))

    def to_dict(self) -> dict:
        return {"intent": self.intent, "id": self.id, "task_kind": self.task_kind,
                "subject": self.subject, "suggested_kind": self.suggested_kind, "fit": self.fit,
                "phase": self.phase, "targets": list(self.targets),
                "project_shape": dict(self.project_shape), "workflow": self.workflow,
                "label": self.label, "depends_on": list(self.depends_on)}


def spec_to_unit(spec: TaskSpec, root: Path | None = None) -> Unit:
    sit = Situation(task_kind=spec.task_kind, intent=spec.intent, subject=spec.subject,
                    suggested_kind=spec.suggested_kind, fit=spec.fit, phase=spec.phase,
                    project_shape=spec.project_shape, root=str(root) if root else None,
                    targets=list(spec.targets), workflow=spec.workflow, label=spec.label)
    return Unit(id=spec.id, situation=sit, depends_on=list(spec.depends_on))


def build_units(specs: list[TaskSpec], root: Path | None = None) -> list[Unit]:
    ids: list[str] = []
    seen: set[str] = set()
    for i, spec in enumerate(specs):
        uid = spec.id or _gen_id(spec.task_kind, i)
        if uid in seen:
            raise ValueError(f"duplicate task id {uid!r} in tasklist")
        seen.add(uid)
        spec.id = uid
        ids.append(uid)
    known = set(ids)
    for spec in specs:
        for d in spec.depends_on:
            if d not in known:
                raise ValueError(f"task {spec.id!r} depends on unknown task {d!r}")
    return [spec_to_unit(spec, root) for spec in specs]


def _gen_id(task_kind: str, i: int) -> str:
    return f"{task_kind}-{int(time.time())}-{i:02d}"


def plan_tasks(root: str | Path, specs: list[TaskSpec]) -> list[Unit]:
    root = Path(root).resolve()
    units = build_units(specs, root)
    specs_out = []
    for u in units:
        s = TaskSpec(intent=u.situation.intent, id=u.id, task_kind=u.situation.task_kind,
                     subject=u.situation.subject, suggested_kind=u.situation.suggested_kind,
                     fit=u.situation.fit, phase=u.situation.phase,
                     targets=list(u.situation.targets), project_shape=u.situation.project_shape,
                     workflow=u.situation.workflow, label=u.situation.label,
                     depends_on=list(u.depends_on))
        specs_out.append(s.to_dict())
    journal.append(root, "conductor.plan", status="ready", tasks=len(specs),
                   units=[u.id for u in units],
                   edges=[[d, u.id] for u in units for d in u.depends_on],
                   specs=specs_out)
    return units


def reconstruct_units(root: str | Path) -> list | None:
    root = Path(root).resolve()
    latest = None
    for e in journal.read(root):
        if e.get("event") == "conductor.plan" and e.get("status") == "ready" and e.get("specs"):
            latest = e
    if latest is None:
        return None
    specs = [TaskSpec.from_dict(s) for s in latest["specs"]]
    return build_units(specs, root)


def plan_and_run(root: str | Path, specs: list[TaskSpec], provider, executor, *,
                 verifier=None, concurrency: int | None = None,
                 max_retries: int | None = None) -> dict:
    root = Path(root).resolve()
    units = plan_tasks(root, specs)
    result = run_dag(Plan(units=units), provider, executor, root, verifier=verifier,
                     concurrency=concurrency, max_retries=max_retries)
    return {"status": "ran", "plan": {"units": [u.id for u in units]}, **result}
