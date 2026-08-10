#!/usr/bin/env python3
"""run — the linear conductor core with the verification gate (P4 + P5 of docs/CONDUCTOR-PLAN.md).

Given a plan (a list of units), the conductor iterates it, and for each unit:
  1. records `unit.proposed`,
  2. consults the judgment provider (`providers.consult`) — folding in the composed judgment and
     surfacing any vocabulary gap — and records `unit.framed`,
  3. dispatches the unit through an **executor** (`unit.dispatched` → `unit.running`), which is the
     only thing that knows *how* a unit runs (inline, subprocess, later remote); the conductor cares
     only that it hands back a `Receipt`,
  4. records the receipt (`unit.receipt` → verifying), then runs the **verification gate**:
       - no verifier ⇒ the receipt is accepted as-is (`result` → `unit.done`, `stall` → stalled);
       - a verifier that PASSES ⇒ `unit.verified` (carrying evidence) → `unit.done`;
       - a verifier that finds a DEFECT ⇒ record it and loop back to step 3 with the defects as
         feedback, up to `max_retries` times; when the retries are exhausted the unit is SURFACED as
         a blocked stall carrying the outstanding defects.
     A receipt that is itself a `stall` (the unit blocking on questions/tradeoffs, not a defect in
     delivered work) is surfaced immediately and never retried.

Everything is a journal event, so state and the deliver-vs-stall summary are the fold over what this
loop wrote — the conductor keeps no state of its own. This is the LINEAR core: units run in order.
The DAG (`depends_on` scheduling) and the concurrency cap are P6. The verification gate is a
RECORDED transition (the `unit.verified` event and the `unit.note kind=defect` events), not prose —
so "was this verified, and how many defect loops did it take?" is a fold over the log.
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


@dataclass
class Verdict:
    """The outcome of verifying a receipt (docs/CONDUCTOR-PLAN.md P5). `verified` is the gate;
    `defects` is what to feed back on the retry when it isn't; `evidence` is the recorded proof
    (test output, a diff check) attached to the `unit.verified` event or the surfaced stall."""

    verified: bool
    defects: list = field(default_factory=list)
    evidence: dict | None = None

    @classmethod
    def from_dict(cls, d: dict) -> "Verdict":
        return cls(verified=bool(d.get("verified")), defects=list(d.get("defects", []) or []),
                   evidence=d.get("evidence"))


@runtime_checkable
class Verifier(Protocol):
    """The 'is the delivered work actually right' seam. Given the unit, its receipt, and the composed
    judgment, return a Verdict. The conductor never learns *how* verification happens (run the tests,
    diff the output, ask a provider) — only whether it passed and, if not, what the defects are."""

    def verify(self, unit: Unit, receipt: Receipt, composed: dict) -> Verdict: ...


class CallableVerifier:
    """Verifies in-process via a handler `(unit, receipt, composed) -> Verdict | dict`."""

    def __init__(self, handler):
        self._handler = handler

    def verify(self, unit: Unit, receipt: Receipt, composed: dict) -> Verdict:
        out = self._handler(unit, receipt, composed)
        return out if isinstance(out, Verdict) else Verdict.from_dict(out)


class CommandVerifier:
    """Verifies by running a command (e.g. the scaffold tests): `argv_builder(unit, receipt,
    composed) -> list[str]`. Exit 0 ⇒ verified, with a tail of stdout as evidence; a nonzero exit ⇒
    a defect carrying the command's stderr/stdout for the feedback loop; a launch failure / timeout ⇒
    a defect too (verification could not be established, so the work is not accepted)."""

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


def run_unit(root: Path, unit: Unit, provider, executor: Executor,
             verifier: Verifier | None = None, max_retries: int = 2) -> dict:
    """Drive one unit through its lifecycle — including the verification gate — writing each
    transition as a journal event, and return a per-unit result. Consults the provider before
    executing (the pre-execute hook); the executor turns the composition into a receipt; the
    verifier (when present) gates that receipt, looping back with defect feedback up to
    `max_retries` times before surfacing a blocked stall."""
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

        # A receipt that stalls is the unit blocking itself (questions/tradeoffs/blocked), not a
        # defect in delivered work — surface it, never retry.
        if receipt.outcome == "stall":
            journal.append(root, "unit.stalled", unit=unit.id, outcome="stall",
                           status=receipt.status)
            return _result("stall", receipt.status, receipt, None, attempt + 1, [])

        # No verifier: accept the receipt as-is (the P4 path, unchanged).
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

        # Defect: record it and loop back with the defects as feedback (bounded by max_retries).
        feedback = verdict.defects
        journal.append(root, "unit.note", unit=unit.id, kind="defect", attempt=attempt,
                       defects=verdict.defects, evidence=verdict.evidence)

    # Retries exhausted without a passing verification — surface the outstanding defects.
    journal.append(root, "unit.stalled", unit=unit.id, outcome="stall", status="blocked",
                   surfaced=feedback,
                   note=f"verification failed after {max_retries + 1} attempt(s)")
    return _result("stall", "blocked", receipt, False, max_retries + 1, feedback)


def run(plan: Plan, provider, executor: Executor, root: Path,
        verifier: Verifier | None = None, max_retries: int = 2) -> dict:
    """Run a linear plan to completion, returning per-unit results plus the fold's deliver-vs-stall
    summary. The loop keeps no state of its own — everything it knows is what it wrote to the
    journal, so a re-fold of the log reproduces this run exactly. Pass a `verifier` to enforce the
    verification gate on every unit."""
    results = [run_unit(root, unit, provider, executor, verifier, max_retries)
               for unit in plan.units]
    return {"results": results, "summary": journal.fold(root)["summary"]}
