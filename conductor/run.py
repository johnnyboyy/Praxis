#!/usr/bin/env python3
"""run — the linear conductor core (P4 of docs/CONDUCTOR-PLAN.md).

Given a plan (a list of units), the conductor iterates it, and for each unit:
  1. records `unit.proposed`,
  2. consults the judgment provider (`providers.consult`) — folding in the composed judgment and
     surfacing any vocabulary gap — and records `unit.framed`,
  3. dispatches the unit through an **executor** (`unit.dispatched` → `unit.running`), which is the
     only thing that knows *how* a unit runs (inline, subprocess, later remote); the conductor cares
     only that it hands back a `Receipt`,
  4. records the receipt (`unit.receipt`) and the terminal state (`unit.done` on a result,
     `unit.stalled` on a stall).

Everything is a journal event, so state and the deliver-vs-stall summary are the fold over what this
loop wrote — the conductor keeps no state of its own. This is the LINEAR core: units run in order.
The DAG (`depends_on` scheduling) and the concurrency cap are P6; the recorded verification gate
(receipt → verified / defect loop-back) is P5, which slots between step 4's receipt and its terminal
state. For now a receipt is accepted as-is (`result` → done), with the verify step still to come.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable

import journal
from providers import consult
from situation import Situation

OUTCOMES = ("result", "stall")
STATUSES = ("complete", "blocked", "questions-pending", "tradeoffs-pending")


@dataclass
class Receipt:
    """The terminal claim an executor returns (docs/CONDUCTOR-PLAN.md "Receipt"). A stall is a
    first-class outcome, not a failure: it means the unit could not complete and surfaced why."""

    outcome: str                                  # result | stall
    status: str = "complete"                      # complete | blocked | questions-pending | tradeoffs-pending
    surfaced: list = field(default_factory=list)  # proposals / questions / tradeoffs to relay
    evidence: dict | None = None                  # verification evidence (populated from P5 on)
    cost: dict | None = None                       # {tokens, usd} | None
    tool_calls: int = 0

    def __post_init__(self):
        if self.outcome not in OUTCOMES:
            raise ValueError(f"outcome must be one of {OUTCOMES}, got {self.outcome!r}")

    def to_dict(self) -> dict:
        return {"outcome": self.outcome, "status": self.status, "surfaced": self.surfaced,
                "evidence": self.evidence, "cost": self.cost, "tool_calls": self.tool_calls}

    @classmethod
    def from_dict(cls, d: dict) -> "Receipt":
        return cls(outcome=d.get("outcome", "result"), status=d.get("status", "complete"),
                   surfaced=list(d.get("surfaced", []) or []), evidence=d.get("evidence"),
                   cost=d.get("cost"), tool_calls=int(d.get("tool_calls", 0) or 0))


@dataclass
class Unit:
    """One unit of work in a plan: an id, the situation the provider composes against, and the
    unit-of-work noun (defaults to the situation's bridge label, then its seed task_kind)."""

    id: str
    situation: Situation
    unit_of_work: str | None = None

    def __post_init__(self):
        if self.unit_of_work is None:
            self.unit_of_work = self.situation.label or self.situation.task_kind


@dataclass
class Plan:
    """A linear plan. P6 adds `depends_on` edges (a DAG) and a concurrency cap; here units run in
    listed order."""

    units: list


@runtime_checkable
class Executor(Protocol):
    """The 'how it runs' seam: given a unit and the composed judgment, return a Receipt. The
    conductor never learns whether the work ran inline, in a subprocess, or on a remote host."""

    def run(self, unit: Unit, composed: dict) -> Receipt: ...


class InlineExecutor:
    """Runs a unit in-process by calling a handler `(unit, composed) -> Receipt | dict`. The handler
    is the actual work (or, in tests, a stub); a plain dict it returns is normalized to a Receipt."""

    def __init__(self, handler):
        self._handler = handler

    def run(self, unit: Unit, composed: dict) -> Receipt:
        out = self._handler(unit, composed)
        return out if isinstance(out, Receipt) else Receipt.from_dict(out)


class SubprocessExecutor:
    """Runs a unit as an isolated subprocess. `argv_builder(unit, composed) -> list[str]` yields the
    command; a JSON receipt on stdout is parsed, a clean exit with no structured receipt is taken as
    a bare result, and a nonzero exit / launch failure / timeout becomes a blocked stall carrying
    the reason — so an executor failure is a recorded stall, never an exception that aborts the run.
    """

    def __init__(self, argv_builder, timeout: int = 300):
        self._argv_builder = argv_builder
        self._timeout = timeout

    def run(self, unit: Unit, composed: dict) -> Receipt:
        import json
        import subprocess
        argv = self._argv_builder(unit, composed)
        try:
            p = subprocess.run(argv, capture_output=True, text=True, timeout=self._timeout)
        except (subprocess.SubprocessError, OSError) as e:
            return Receipt(outcome="stall", status="blocked", surfaced=[f"executor failed: {e}"])
        if p.returncode != 0:
            reason = p.stderr.strip()[:500] or f"exit {p.returncode}"
            return Receipt(outcome="stall", status="blocked", surfaced=[reason])
        try:
            return Receipt.from_dict(json.loads(p.stdout))
        except (json.JSONDecodeError, ValueError):
            # A clean exit with no receipt JSON: the unit ran and did not declare a stall.
            return Receipt(outcome="result", status="complete")


def run_unit(root: Path, unit: Unit, provider, executor: Executor) -> dict:
    """Drive one unit through its lifecycle, writing each transition as a journal event, and return
    a per-unit result. Consults the provider before executing (the pre-execute hook) and folds in
    the composed judgment; the executor turns that into a receipt."""
    journal.append(root, "unit.proposed", unit=unit.id, unit_of_work=unit.unit_of_work,
                   situation=unit.situation.to_dict())
    composed = consult(provider, unit.situation, root=root)
    journal.append(root, "unit.framed", unit=unit.id, unit_of_work=unit.unit_of_work,
                   routed_kind=composed.get("routed_kind"), gap_surfaced=composed.get("gap_surfaced"),
                   domains=composed.get("domains", []), stance=composed.get("stance"),
                   note=composed.get("note"))
    journal.append(root, "unit.dispatched", unit=unit.id)
    journal.append(root, "unit.running", unit=unit.id)
    receipt = executor.run(unit, composed)
    journal.append(root, "unit.receipt", unit=unit.id, **receipt.to_dict())
    terminal = "unit.done" if receipt.outcome == "result" else "unit.stalled"
    journal.append(root, terminal, unit=unit.id, outcome=receipt.outcome, status=receipt.status)
    return {"unit": unit.id, "unit_of_work": unit.unit_of_work, "outcome": receipt.outcome,
            "status": receipt.status, "gap_surfaced": composed.get("gap_surfaced"),
            "routed_kind": composed.get("routed_kind"), "receipt": receipt.to_dict()}


def run(plan: Plan, provider, executor: Executor, root: Path) -> dict:
    """Run a linear plan to completion, returning per-unit results plus the fold's deliver-vs-stall
    summary. The loop keeps no state of its own — everything it knows is what it wrote to the
    journal, so a re-fold of the log reproduces this run exactly."""
    results = [run_unit(root, unit, provider, executor) for unit in plan.units]
    return {"results": results, "summary": journal.fold(root)["summary"]}
