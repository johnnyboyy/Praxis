#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable

import journal
from contributors import HookContext, fire, gather, surface_for
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


def coverage_verifier(test_cmd: str | None, threshold, target: str | None = None,
                      timeout: int = 300) -> "Verifier | None":
    """The fast, per-unit COVERAGE gate — deterministic, exit-code only (R2).

    Runs the acceptance suite WITH coverage enforcement so the process EXIT CODE
    is the verdict: e.g. `pytest --cov=<target> --cov-fail-under=<threshold>`,
    which pytest-cov exits non-zero on when coverage is under the threshold. We
    never parse stdout for the pass/fail — the exit code alone decides. Absent
    config (no threshold, and neither a test command nor a target) => return None
    so the gate is simply unwired; we never fabricate a passing verifier."""
    if threshold is None or (not test_cmd and not target):
        return None
    import shlex
    argv = list(shlex.split(test_cmd)) if test_cmd else ["pytest"]
    if target:
        argv.append(f"--cov={target}")
    argv.append(f"--cov-fail-under={threshold}")
    return CommandVerifier(lambda unit, receipt, composed, _argv=argv: _argv,
                           timeout=timeout)


def _parse_mutation_score(text: str | None) -> float | None:
    """Robustly pull a numeric mutation score out of command output (last number
    wins), or None when nothing numeric is present. Fail-closed callers treat
    None as 'unparseable'."""
    import re
    nums = re.findall(r"[-+]?\d*\.?\d+", text or "")
    if not nums:
        return None
    try:
        return float(nums[-1])
    except ValueError:
        return None


def mutation_verifier(mutation_cmd, threshold, timeout: int = 600) -> "Verifier | None":
    """The slow, plan-level MUTATION barrier — deterministic (R2).

    Runs a CONFIGURABLE `mutation_cmd` (argv or a shell string) once and passes
    iff the mutation score >= threshold. Two signalling modes, both exit/score
    based (never model evidence):
      * the command prints a score  -> that score is authoritative (score >= th),
      * the command prints nothing  -> its EXIT CODE is the verdict (0 == pass).
    Fail-closed: a command that cannot run, or emits output with no parseable
    score, is a FAIL. There is NO hard mutmut/cosmic-ray dependency here — the
    command is whatever config names (fixtures use a controllable fake)."""
    if not mutation_cmd or threshold is None:
        return None
    import shlex
    argv = shlex.split(mutation_cmd) if isinstance(mutation_cmd, str) else list(mutation_cmd)

    def _handler(unit, receipt, composed):
        import subprocess
        try:
            p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        except (subprocess.SubprocessError, OSError) as e:
            return Verdict(verified=False, defects=[f"mutation barrier could not run: {e}"])
        score = _parse_mutation_score(p.stdout)
        if score is not None:
            ok = score >= float(threshold)
            return Verdict(verified=ok,
                           defects=[] if ok else
                           [f"mutation score {score} < threshold {threshold}"],
                           evidence={"score": score, "threshold": float(threshold),
                                     "returncode": p.returncode})
        if p.stdout.strip():
            # Non-empty output we could not read a score from — fail closed.
            return Verdict(verified=False, defects=["mutation score unparseable"],
                           evidence={"stdout": p.stdout.strip()[-1000:]})
        ok = p.returncode == 0
        return Verdict(verified=ok,
                       defects=[] if ok else [f"mutation barrier exit {p.returncode}"],
                       evidence={"returncode": p.returncode})

    return CallableVerifier(_handler)


def _root_config(root: Path) -> dict:
    """Read the core/unnamed-scope config for this root (fail-soft, like the walk)."""
    try:
        import config
        return config.read(root)
    except Exception:
        return {}


def coverage_verifier_from_config(root: Path) -> "Verifier | None":
    """Build the per-unit coverage gate from policy/config, or None when unwired.

    Keys (unnamed scope): `coverage-threshold`, `coverage-target`, `coverage-cmd`
    (the suite command; falls back to pytest inside `coverage_verifier`)."""
    cfg = _root_config(root)
    return coverage_verifier(cfg.get("coverage-cmd"), cfg.get("coverage-threshold"),
                             cfg.get("coverage-target"))


def mutation_verifier_from_config(root: Path) -> "Verifier | None":
    """Build the plan-level mutation barrier from policy/config, or None when unwired.

    Keys (unnamed scope): `mutation-cmd`, `mutation-threshold`. Absent => no barrier."""
    cfg = _root_config(root)
    return mutation_verifier(cfg.get("mutation-cmd"), cfg.get("mutation-threshold"))


def _workflow_verifiers(verifier: "Verifier | None",
                        coverage: "Verifier | None" = None) -> dict:
    """Map workflow gate names to real Verifiers.

    The `create`→does-it and `carry`→regression gates run the per-unit adequacy
    gate. When a COVERAGE gate is configured for the root it IS that gate (R2):
    the walk only advances when the suite passes AT the coverage threshold, not
    on a bare test run. Otherwise the gate is the project's test command (the
    `verifier`, built by `verifier_from_test_cmd`). When neither is configured
    the map is empty — absent key = the walk treats that gate as verified
    (no-op), NOT a fabricated passing verifier. `extract`→coverage-diff is left
    UNWIRED. Gates read only exit codes/scores, never model-supplied evidence."""
    gate = coverage or verifier
    if gate is None:
        return {}
    return {"regression": gate, "does-it": gate}


def run_unit(root: Path, unit: Unit, contributors, executor: Executor,
             verifier: Verifier | None = None, max_retries: int = 2,
             verifiers: dict | None = None) -> dict:
    journal.append(root, "unit.proposed", unit=unit.id, unit_of_work=unit.unit_of_work,
                   situation=unit.situation.to_dict())
    composed = gather(contributors, unit.situation, root=root)
    surface = surface_for(contributors, unit.situation) or (unit.situation.targets or None)
    journal.append(root, "unit.framed", unit=unit.id, unit_of_work=unit.unit_of_work,
                   routed_kind=composed.get("routed_kind"), gap_surfaced=composed.get("gap_surfaced"),
                   sources=composed.get("sources", []), stance=composed.get("stance"),
                   surface=surface, note=composed.get("note"))

    if unit.situation.workflow:
        import registry
        from workflow_run import run_workflow
        wf = registry.resolve_workflows(root).get(unit.situation.workflow)
        if wf is not None:
            wf_verifiers = verifiers if verifiers is not None \
                else _workflow_verifiers(verifier, coverage_verifier_from_config(root))
            return run_workflow(root, unit, wf, contributors, executor,
                                verifiers=wf_verifiers)
        journal.append(root, "workflow.unresolved", unit=unit.id,
                       workflow=unit.situation.workflow)
        # fall through to single-dispatch

    def _result(outcome, status, receipt, verified, attempts, defects):
        return {"unit": unit.id, "unit_of_work": unit.unit_of_work, "outcome": outcome,
                "status": status, "verified": verified, "attempts": attempts, "defects": defects,
                "gap_surfaced": composed.get("gap_surfaced"),
                "routed_kind": composed.get("routed_kind"),
                "receipt": receipt.to_dict() if receipt else None}

    def _finish(outcome, status, receipt, verified, attempts, defects, verdict=None):
        fire(contributors, "unit-close", HookContext(
            root=root, step="unit-close", unit=unit,
            receipt=receipt.to_dict() if receipt else None,
            verdict=verdict))
        return _result(outcome, status, receipt, verified, attempts, defects)

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
            return _finish("stall", receipt.status, receipt, None, attempt + 1, [])

        if verifier is None:
            journal.append(root, "unit.done", unit=unit.id, outcome="result",
                           status=receipt.status)
            return _finish("result", receipt.status, receipt, None, attempt + 1, [])

        verdict = verifier.verify(unit, receipt, composed)
        if verdict.verified:
            journal.append(root, "unit.verified", unit=unit.id, attempt=attempt,
                           evidence=verdict.evidence)
            fire(contributors, "verify", HookContext(
                root=root, step="verify", unit=unit, receipt=receipt.to_dict(),
                verdict={"verified": True, "defects": verdict.defects,
                         "evidence": verdict.evidence}))
            journal.append(root, "unit.done", unit=unit.id, outcome="result",
                           status=receipt.status)
            return _finish("result", receipt.status, receipt, True, attempt + 1, [],
                           verdict={"verified": True, "defects": verdict.defects,
                                    "evidence": verdict.evidence})

        feedback = verdict.defects
        journal.append(root, "unit.note", unit=unit.id, kind="defect", attempt=attempt,
                       defects=verdict.defects, evidence=verdict.evidence)

    journal.append(root, "unit.stalled", unit=unit.id, outcome="stall", status="blocked",
                   surfaced=feedback,
                   note=f"verification failed after {max_retries + 1} attempt(s)")
    return _finish("stall", "blocked", receipt, False, max_retries + 1, feedback)


def run(plan: Plan, contributors, executor: Executor, root: Path,
        verifier: Verifier | None = None, max_retries: int | None = None,
        policy=None, barrier_verifier: Verifier | None = None) -> dict:
    import views
    import policy as policy_mod
    pol = policy or policy_mod.load_policy(root)
    if pol.verify_required and verifier is None:
        raise ValueError("policy sets verify_required but no verifier was supplied")
    retries = pol.max_retries if max_retries is None else max_retries
    results = [run_unit(root, unit, contributors, executor, verifier, retries)
               for unit in plan.units]

    # Plan-level FINAL BARRIER (R2): the slow mutation signal, run ONCE after all
    # units, BEFORE close. A failing barrier BLOCKS close (the hook never fires).
    # Deterministic, exit-code/score based — never model evidence. Absent config
    # => no barrier is built and close proceeds exactly as before.
    barrier = barrier_verifier if barrier_verifier is not None \
        else mutation_verifier_from_config(root)
    barrier_info = None
    if barrier is not None:
        verdict = barrier.verify(None, None, {})
        barrier_info = {"verified": verdict.verified, "defects": verdict.defects,
                        "evidence": verdict.evidence}
        journal.append(root, "barrier.verified" if verdict.verified else "barrier.blocked",
                       verified=verdict.verified, defects=verdict.defects,
                       evidence=verdict.evidence)
        if not verdict.verified:
            return {"results": results, "barrier": barrier_info, "closed": False,
                    "status": "blocked", "summary": journal.fold(root)["summary"],
                    "cost": views.cost(root)}

    fire(contributors, "close", HookContext(root=root, step="close"))
    return {"results": results, "barrier": barrier_info, "closed": True,
            "summary": journal.fold(root)["summary"], "cost": views.cost(root)}
