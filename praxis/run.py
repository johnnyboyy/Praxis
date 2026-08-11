#!/usr/bin/env python3
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

    outcome: str
    status: str = "complete"
    surfaced: list = field(default_factory=list)
    evidence: dict | None = None
    cost: dict | None = None
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

    id: str
    situation: Situation
    unit_of_work: str | None = None
    depends_on: list = field(default_factory=list)

    def __post_init__(self):
        if self.unit_of_work is None:
            self.unit_of_work = self.situation.label or self.situation.task_kind


@dataclass
class Plan:

    units: list


@runtime_checkable
class Executor(Protocol):

    def run(self, unit: Unit, composed: dict) -> Receipt: ...


class InlineExecutor:

    def __init__(self, handler):
        self._handler = handler

    def run(self, unit: Unit, composed: dict) -> Receipt:
        out = self._handler(unit, composed)
        return out if isinstance(out, Receipt) else Receipt.from_dict(out)


class SubprocessExecutor:

    def __init__(self, argv_builder, timeout: int = 300, cost_extractor=None):
        self._argv_builder = argv_builder
        self._timeout = timeout
        self._cost_extractor = cost_extractor

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
            receipt = Receipt.from_dict(json.loads(p.stdout))
        except (json.JSONDecodeError, ValueError):
            receipt = Receipt(outcome="result", status="complete")
        if receipt.cost is None and self._cost_extractor is not None:
            receipt.cost = self._cost_extractor(p.stdout, p.stderr)
        return receipt


@dataclass
class Verdict:

    verified: bool
    defects: list = field(default_factory=list)
    evidence: dict | None = None

    @classmethod
    def from_dict(cls, d: dict) -> "Verdict":
        return cls(verified=bool(d.get("verified")), defects=list(d.get("defects", []) or []),
                   evidence=d.get("evidence"))


@runtime_checkable
class Verifier(Protocol):

    def verify(self, unit: Unit, receipt: Receipt, composed: dict) -> Verdict: ...


class CallableVerifier:

    def __init__(self, handler):
        self._handler = handler

    def verify(self, unit: Unit, receipt: Receipt, composed: dict) -> Verdict:
        out = self._handler(unit, receipt, composed)
        return out if isinstance(out, Verdict) else Verdict.from_dict(out)


class CommandVerifier:

    def __init__(self, argv_builder, timeout: int = 300):
        self._argv_builder = argv_builder
        self._timeout = timeout

    def verify(self, unit: Unit, receipt: Receipt, composed: dict) -> Verdict:
        import subprocess
        argv = self._argv_builder(unit, receipt, composed)
        try:
            p = subprocess.run(argv, capture_output=True, text=True, timeout=self._timeout)
        except (subprocess.SubprocessError, OSError) as e:
            return Verdict(verified=False, defects=[f"verification could not run: {e}"])
        if p.returncode == 0:
            return Verdict(verified=True, evidence={"stdout": p.stdout.strip()[-1000:]})
        detail = (p.stderr.strip() or p.stdout.strip())[-1000:] or f"exit {p.returncode}"
        return Verdict(verified=False, defects=[detail],
                       evidence={"returncode": p.returncode})


def verifier_from_test_cmd(test_cmd: str | None) -> "Verifier | None":
    if not test_cmd:
        return None
    import shlex
    argv = shlex.split(test_cmd)
    return CommandVerifier(lambda unit, receipt, composed, _argv=argv: _argv)


def run_unit(root: Path, unit: Unit, provider, executor: Executor,
             verifier: Verifier | None = None, max_retries: int = 2) -> dict:
    journal.append(root, "unit.proposed", unit=unit.id, unit_of_work=unit.unit_of_work,
                   situation=unit.situation.to_dict())
    composed = consult(provider, unit.situation, root=root)
    journal.append(root, "unit.framed", unit=unit.id, unit_of_work=unit.unit_of_work,
                   routed_kind=composed.get("routed_kind"), gap_surfaced=composed.get("gap_surfaced"),
                   domains=composed.get("domains", []), stance=composed.get("stance"),
                   note=composed.get("note"))

    def _result(outcome, status, receipt, verified, attempts, defects):
        return {"unit": unit.id, "unit_of_work": unit.unit_of_work, "outcome": outcome,
                "status": status, "verified": verified, "attempts": attempts, "defects": defects,
                "gap_surfaced": composed.get("gap_surfaced"),
                "routed_kind": composed.get("routed_kind"),
                "receipt": receipt.to_dict() if receipt else None}

    feedback: list = []
    receipt = None
    for attempt in range(max_retries + 1):
        journal.append(root, "unit.dispatched", unit=unit.id, attempt=attempt)
        journal.append(root, "unit.running", unit=unit.id, attempt=attempt)
        attempt_composed = composed if not (feedback or attempt) else \
            {**composed, "feedback": feedback, "attempt": attempt}
        receipt = executor.run(unit, attempt_composed)
        journal.append(root, "unit.receipt", unit=unit.id, attempt=attempt, **receipt.to_dict())

        if receipt.outcome == "stall":
            journal.append(root, "unit.stalled", unit=unit.id, outcome="stall",
                           status=receipt.status)
            return _result("stall", receipt.status, receipt, None, attempt + 1, [])

        if verifier is None:
            journal.append(root, "unit.done", unit=unit.id, outcome="result",
                           status=receipt.status)
            return _result("result", receipt.status, receipt, None, attempt + 1, [])

        verdict = verifier.verify(unit, receipt, composed)
        if verdict.verified:
            journal.append(root, "unit.verified", unit=unit.id, attempt=attempt,
                           evidence=verdict.evidence)
            journal.append(root, "unit.done", unit=unit.id, outcome="result",
                           status=receipt.status)
            return _result("result", receipt.status, receipt, True, attempt + 1, [])

        feedback = verdict.defects
        journal.append(root, "unit.note", unit=unit.id, kind="defect", attempt=attempt,
                       defects=verdict.defects, evidence=verdict.evidence)

    journal.append(root, "unit.stalled", unit=unit.id, outcome="stall", status="blocked",
                   surfaced=feedback,
                   note=f"verification failed after {max_retries + 1} attempt(s)")
    return _result("stall", "blocked", receipt, False, max_retries + 1, feedback)


def run(plan: Plan, provider, executor: Executor, root: Path,
        verifier: Verifier | None = None, max_retries: int | None = None,
        policy=None) -> dict:
    import views
    import policy as policy_mod
    pol = policy or policy_mod.load_policy(root)
    if pol.verify_required and verifier is None:
        raise ValueError("policy sets verify_required but no verifier was supplied")
    retries = pol.max_retries if max_retries is None else max_retries
    results = [run_unit(root, unit, provider, executor, verifier, retries)
               for unit in plan.units]
    return {"results": results, "summary": journal.fold(root)["summary"],
            "cost": views.cost(root)}
