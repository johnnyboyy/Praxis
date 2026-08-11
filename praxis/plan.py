#!/usr/bin/env python3
"""plan — the tasklist intake + planning head that feeds the DAG scheduler.

This is the missing head of the conductor (docs/CONDUCTOR-PLAN.md left P6's `run_dag` reachable only
from tests): it turns a **tasklist** — one task or many — into a `Plan` (a DAG of units with
`depends_on` edges), then sets it in motion through `schedule.run_dag`. The operator hands over
tasks; the conductor plans, sequences, and cascades — reporting progress through the one journal.

Planning is *judgment* (how to decompose, what depends on what, what to clarify), so it is a **seam**
the conductor never sees through — mirroring the executor / verifier seams in run.py:

  - `PassthroughPlanner` — the deterministic, judgment-free degrade: build a plan straight from the
    specs the caller declared (honoring their `depends_on`), infer nothing, ask nothing. Testable and
    reliable; the null-provider analogue for planning.
  - `CallablePlanner` — an **inline** planner: a handler decomposes / infers dependencies / and can
    PAUSE to interview the operator (return `questions`), all in the conductor's own context.
  - `SubprocessPlanner` — a **spawned** planner: an isolated subprocess consults docs/caches and
    returns a plan JSON (or a questions payload) on stdout. A spawn can pause and surface questions
    too, so the inline-vs-spawn choice is the conductor's per situation (e.g. a third planning pass
    it wants in fresh context), not a hardcoded one.

A planner concludes one of two ways, both recorded (so planning is a fold, not prose):
  - `ready`    — a set of units → `plan_and_run` hands them to `run_dag` and the cascade begins.
  - `questions`— the planner needs clarification → a recorded PAUSE (`conductor.plan` with
    status `questions-pending` + the surfaced questions); NOTHING runs until the operator answers.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable

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


@dataclass
class PlanOutcome:
    """The normalized result of a planning pass. `ready` carries the units to schedule; `questions`
    carries what the planner needs answered before it can plan (the interview pause)."""

    status: str                              # "ready" | "questions"
    units: list = field(default_factory=list)
    questions: list = field(default_factory=list)
    note: str | None = None

    def __post_init__(self):
        if self.status not in ("ready", "questions"):
            raise ValueError(f"status must be 'ready' or 'questions', got {self.status!r}")

    @classmethod
    def from_dict(cls, d: dict, root: Path | None = None) -> "PlanOutcome":
        status = d.get("status", "ready")
        if status == "questions":
            return cls(status="questions", questions=list(d.get("questions", []) or []),
                       note=d.get("note"))
        # ready: units may arrive as Unit objects or as plain spec dicts to build.
        raw = d.get("units", []) or []
        units = [u if isinstance(u, Unit) else spec_to_unit(TaskSpec.from_dict(u), root)
                 for u in raw]
        return cls(status="ready", units=units, note=d.get("note"))


# ── deterministic assembly (pure, testable — the judgment-free core) ─────────────────────────────

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


# ── the planner seam (inline / spawned / degrade) ────────────────────────────────────────────────

@runtime_checkable
class Planner(Protocol):
    """The 'how the tasklist becomes a DAG' seam. The conductor never learns whether planning ran in
    its own context, in a spawned subprocess, or was a passthrough — only the resulting PlanOutcome."""

    def plan(self, specs: list[TaskSpec], root: Path) -> PlanOutcome: ...


class PassthroughPlanner:
    """The judgment-free degrade: schedule the tasklist exactly as declared (deterministic assembly),
    inferring nothing and asking nothing. Always `ready`. The reliable floor — a tasklist with
    explicit `depends_on` runs correctly with no planning judgment at all."""

    def plan(self, specs: list[TaskSpec], root: Path) -> PlanOutcome:
        return PlanOutcome(status="ready", units=build_units(specs, root))


class CallablePlanner:
    """An inline planner: a handler `(specs, root) -> PlanOutcome | dict` does the decomposition /
    dependency inference and may PAUSE by returning `{status: 'questions', questions: [...]}`. The
    handler is where an interactive agent (which can interview the operator) plans."""

    def __init__(self, handler):
        self._handler = handler

    def plan(self, specs: list[TaskSpec], root: Path) -> PlanOutcome:
        out = self._handler(specs, root)
        return out if isinstance(out, PlanOutcome) else PlanOutcome.from_dict(out, root)


class SubprocessPlanner:
    """A spawned planner: `argv_builder(specs, root) -> list[str]` yields the command; the child
    returns a plan JSON (`{status:'ready', units:[…]}`) or a questions payload
    (`{status:'questions', questions:[…]}`) on stdout. A launch failure / timeout / nonzero exit /
    unparseable output surfaces as a questions pause carrying the reason — planning never crashes the
    run, it pauses it (symmetric to SubprocessExecutor turning a failure into a recorded stall)."""

    def __init__(self, argv_builder, timeout: int = 300):
        self._argv_builder = argv_builder
        self._timeout = timeout

    def plan(self, specs: list[TaskSpec], root: Path) -> PlanOutcome:
        import json
        import subprocess
        argv = self._argv_builder(specs, root)
        try:
            p = subprocess.run(argv, capture_output=True, text=True, timeout=self._timeout)
        except (subprocess.SubprocessError, OSError) as e:
            return PlanOutcome(status="questions",
                               questions=[f"planner spawn failed: {e}"], note="planner-failure")
        if p.returncode != 0:
            reason = (p.stderr.strip() or p.stdout.strip())[:500] or f"exit {p.returncode}"
            return PlanOutcome(status="questions", questions=[reason], note="planner-failure")
        try:
            return PlanOutcome.from_dict(json.loads(p.stdout), root)
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            return PlanOutcome(status="questions",
                               questions=[f"planner returned no usable plan: {e}"],
                               note="planner-failure")


# ── the entries the surface (MCP/CLI) calls ──────────────────────────────────────────────────────

def plan_tasks(root: str | Path, specs: list[TaskSpec], planner: Planner | None = None) -> PlanOutcome:
    """Run one planning pass over a tasklist and record it. Records `conductor.plan` with the outcome:
    the proposed unit ids + their edges when `ready`, or the surfaced questions when the planner
    paused to interview. Defaults to the deterministic `PassthroughPlanner` when no judgment planner
    is supplied (so a well-declared tasklist plans with zero inference)."""
    root = Path(root).resolve()
    planner = planner or PassthroughPlanner()
    outcome = planner.plan(specs, root)
    if outcome.status == "questions":
        journal.append(root, "conductor.plan", status="questions-pending",
                       tasks=len(specs), questions=outcome.questions, note=outcome.note)
    else:
        # Persist the resolved specs on the event so the plan is reconstructable from the journal
        # alone (what `reconstruct_units` / the stateless `next_handoff` pull read back).
        by_id = {u.id: u for u in outcome.units}
        specs_out = []
        for u in outcome.units:
            s = TaskSpec(intent=u.situation.intent, id=u.id, task_kind=u.situation.task_kind,
                         subject=u.situation.subject, suggested_kind=u.situation.suggested_kind,
                         fit=u.situation.fit, phase=u.situation.phase,
                         targets=list(u.situation.targets), project_shape=u.situation.project_shape,
                         workflow=u.situation.workflow, label=u.situation.label,
                         depends_on=list(u.depends_on))
            specs_out.append(s.to_dict())
        journal.append(root, "conductor.plan", status="ready", tasks=len(specs),
                       units=[u.id for u in outcome.units],
                       edges=[[d, u.id] for u in outcome.units for d in u.depends_on],
                       specs=specs_out, note=outcome.note)
    return outcome


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
                 planner: Planner | None = None, verifier=None, concurrency: int | None = None,
                 max_retries: int | None = None) -> dict:
    """The whole head-to-tail move: plan a tasklist, then — if the planner did not pause for an
    interview — set the DAG in motion through `run_dag` and let the units cascade. Returns either the
    interview pause (`{status:'questions', …}`, nothing run) or the `run_dag` result
    (`{status:'ran', results, summary, routing, cost}`)."""
    root = Path(root).resolve()
    outcome = plan_tasks(root, specs, planner)
    if outcome.status == "questions":
        return {"status": "questions", "questions": outcome.questions, "note": outcome.note}
    result = run_dag(Plan(units=outcome.units), provider, executor, root, verifier=verifier,
                     concurrency=concurrency, max_retries=max_retries)
    return {"status": "ran", "plan": {"units": [u.id for u in outcome.units]}, **result}
