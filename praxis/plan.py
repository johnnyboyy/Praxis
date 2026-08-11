#!/usr/bin/env python3
"""plan — the tasklist intake + planning head that feeds the DAG scheduler.

This is the missing head of the conductor (docs/CONDUCTOR-PLAN.md left P6's `run_dag` reachable only
from tests): it turns a **tasklist** — one task or many — into a `Plan` (a DAG of units with
`depends_on` edges), then sets it in motion through `schedule.run_dag`. The operator hands over
tasks; the conductor plans, sequences, and cascades — reporting progress through the one journal.

Planning here is deterministic assembly: `plan_tasks` builds a plan straight from the specs the
caller declared (honoring their `depends_on`), infers nothing, and records one `conductor.plan`
event so the plan is a fold, not prose. A judgment planner (an interactive agent that decomposes,
infers dependencies, or pauses to interview) is a separate seam to reintroduce when a real one lands
— the interactive agent currently plans upstream and hands `plan_tasks` finished specs.
"""
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
    """One raw task from the operator's tasklist. `id` is optional (generated when absent) and is how
    other specs reference this one in `depends_on`. The gap signal (`suggested_kind` / `fit`) rides
    here exactly as on a Situation — always collected, never guessed."""

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
    """Turn one spec into a Unit + its Situation. Deterministic: no inference, no judgment — just the
    faithful projection of the spec's declared features onto the feature object the provider composes
    against."""
    sit = Situation(task_kind=spec.task_kind, intent=spec.intent, subject=spec.subject,
                    suggested_kind=spec.suggested_kind, fit=spec.fit, phase=spec.phase,
                    project_shape=spec.project_shape, root=str(root) if root else None,
                    targets=list(spec.targets), workflow=spec.workflow, label=spec.label)
    return Unit(id=spec.id, situation=sit, depends_on=list(spec.depends_on))


def build_units(specs: list[TaskSpec], root: Path | None = None) -> list[Unit]:
    """Assign stable ids (declared or generated), validate that ids are unique and every `depends_on`
    names a task in this same tasklist, and project each spec to a Unit. Raises on a duplicate id or
    a dangling dependency — a tasklist bug the caller must fix, distinct from a runtime stall (the
    cycle check itself lives in schedule._validate, run at scheduling time)."""
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
    """Assemble a tasklist into its DAG of units (deterministic — honoring the declared `depends_on`,
    inferring nothing) and record one `ready` `conductor.plan` event carrying the resolved specs, unit
    ids, and edges, so the plan is reconstructable from the journal. Returns the units."""
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
    """Rebuild a plan's units from the journal — the latest `ready` `conductor.plan` event's stored
    specs. This is how a STATELESS surface (an MCP `next_handoff` call) recovers the tasklist to find
    the next ready unit, keeping the journal the single source of truth. None when no plan is on the
    log."""
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
    """The whole head-to-tail move: plan a tasklist, then set the DAG in motion through `run_dag` and
    let the units cascade. Returns the `run_dag` result (`{status:'ran', results, summary, routing,
    cost}`)."""
    root = Path(root).resolve()
    units = plan_tasks(root, specs)
    result = run_dag(Plan(units=units), provider, executor, root, verifier=verifier,
                     concurrency=concurrency, max_retries=max_retries)
    return {"status": "ran", "plan": {"units": [u.id for u in units]}, **result}
