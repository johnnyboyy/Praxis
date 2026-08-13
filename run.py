#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable

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

def _workflow_verifiers(verifier: "Verifier | None") -> dict:
    if verifier is None:
        return {}
    return {"regression": verifier, "does-it": verifier}

def verifiers_for_workflow(root: Path, wf, verifier: "Verifier | None" = None) -> dict:
    factory = getattr(wf, "verifiers", None)
    if callable(factory):
        try:
            return factory(root)
        except Exception:
            return {}
    return _workflow_verifiers(verifier)
