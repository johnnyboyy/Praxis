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


def _norm_sig(sig: str | None) -> str:
    """Whitespace-insensitive canonical form for signature comparison."""
    return "".join((sig or "").split())


def _fn_signature(node) -> str:
    """Build `name(a, b, *args, c, **kw)` from an ast function node's params."""
    import ast
    a = node.args
    parts = [arg.arg for arg in list(getattr(a, "posonlyargs", [])) + list(a.args)]
    if a.vararg:
        parts.append("*" + a.vararg.arg)
    parts += [arg.arg for arg in a.kwonlyargs]
    if a.kwarg:
        parts.append("**" + a.kwarg.arg)
    return f"{node.name}({', '.join(parts)})"


def _is_test_file(p: Path) -> bool:
    n = p.name
    return n.startswith("test_") or n.endswith("_test.py") or n == "conftest.py"


def _ast_surface(tree_path: Path) -> tuple[set, dict]:
    """Walk a synth tree's non-test `.py` files and collect its PUBLIC surface.

    Returns (surface, signatures): `surface` is the set of module-level public
    (non-underscore) def/class/assignment names across the tree; `signatures`
    maps function/class names to a canonical signature string. Read from DISK
    via `ast` — never from model-supplied evidence."""
    import ast
    surface: set = set()
    sigs: dict = {}
    files = [tree_path] if tree_path.is_file() else sorted(tree_path.rglob("*.py"))
    for f in files:
        if _is_test_file(f):
            continue
        try:
            mod = ast.parse(f.read_text())
        except (OSError, SyntaxError):
            continue
        for node in mod.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not node.name.startswith("_"):
                    surface.add(node.name)
                    sigs[node.name] = _fn_signature(node)
            elif isinstance(node, ast.ClassDef):
                if not node.name.startswith("_"):
                    surface.add(node.name)
                    sigs[node.name] = f"{node.name}(...)"
            elif isinstance(node, ast.Assign):
                for tgt in node.targets:
                    if isinstance(tgt, ast.Name) and not tgt.id.startswith("_"):
                        surface.add(tgt.id)
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                if not node.target.id.startswith("_"):
                    surface.add(node.target.id)
    return surface, sigs


def _run_held_out(held: list, synth_path: Path, timeout: int) -> tuple[int, str]:
    """Run the held-out test files under pytest with the SYNTH on PYTHONPATH.

    The process EXIT CODE is the verdict (0 == pass). No model claims consulted."""
    import os
    import subprocess
    import sys
    env = dict(os.environ)
    base = str(synth_path if synth_path.is_dir() else synth_path.parent)
    env["PYTHONPATH"] = base + os.pathsep + env.get("PYTHONPATH", "")
    argv = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *held]
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, env=env, cwd=base)
    except (subprocess.SubprocessError, OSError) as e:
        return 1, f"held-out run could not start: {e}"
    return p.returncode, (p.stdout or p.stderr or "").strip()[-1000:]


def coverage_diff_verifier(timeout: int = 300) -> "Verifier":
    """The rebuild-triple PRESERVATION gate (R3a) — fires at synthesize-exit.

    Reads the IR from `composed["ir"]` (threaded via the extract edge) and the
    synth tree path from `receipt.evidence["produces"]`, and returns verified iff
    ALL hold, each derived from DISK (never model evidence):
      (c) every `interface` symbol is present in the synth with a matching
          signature (completeness);
      (b) the synth's public surface (ast walk of its `.py`) ⊆ `allowed_surface`
          (losslessness — anything extra fails);
      (a) the IR's `held_out` tests PASS against the synth tree (generalization —
          subprocess pytest, exit code is the verdict).
    Fail-closed on a malformed IR or a missing synth path. NOTE: this takes the
    synth path AS GIVEN — isolation/copy-detection is R3b, not closed here."""
    import rebuild_ir

    def _handler(unit, receipt, composed):
        try:
            ir = rebuild_ir.validate_ir(composed.get("ir"))
        except Exception as e:
            return Verdict(verified=False, defects=[f"malformed IR: {e}"],
                           evidence={"check": "ir"})
        ev = (receipt.evidence if receipt else None) or {}
        synth = ev.get("produces")
        if not synth:
            return Verdict(verified=False,
                           defects=["no synth tree path in receipt.evidence['produces']"],
                           evidence={"check": "synth-path"})
        synth_path = Path(synth)
        if not synth_path.exists():
            return Verdict(verified=False, defects=[f"synth tree missing: {synth}"],
                           evidence={"check": "synth-path"})

        surface, sigs = _ast_surface(synth_path)

        # (c) completeness: every interface symbol present with matching signature.
        missing = [s["symbol"] for s in ir["interface"] if s["symbol"] not in surface]
        if missing:
            return Verdict(verified=False,
                           defects=[f"missing interface symbols: {missing}"],
                           evidence={"check": "interface", "missing": missing})
        mism = []
        for s in ir["interface"]:
            want = _norm_sig(s.get("signature"))
            if want and _norm_sig(sigs.get(s["symbol"])) != want:
                mism.append({"symbol": s["symbol"], "expected": s["signature"],
                             "actual": sigs.get(s["symbol"])})
        if mism:
            return Verdict(verified=False,
                           defects=[f"signature mismatch: {mism}"],
                           evidence={"check": "interface", "mismatch": mism})

        # (b) losslessness: nothing exported outside the allowed surface.
        extra = sorted(surface - set(ir["allowed_surface"]))
        if extra:
            return Verdict(verified=False,
                           defects=[f"surface exceeds allowed_surface: {extra}"],
                           evidence={"check": "surface", "extra": extra})

        # (a) generalization: held-out tests pass against the synth (exit code).
        code, detail = _run_held_out(ir["tests"]["held_out"], synth_path, timeout)
        if code != 0:
            return Verdict(verified=False,
                           defects=[f"held-out tests failed (exit {code})"],
                           evidence={"check": "held_out", "returncode": code,
                                     "detail": detail})

        return Verdict(verified=True,
                       evidence={"check": "all", "surface": sorted(surface)})

    return CallableVerifier(_handler)


def adequacy_verifier(coverage: "Verifier | None" = None) -> "Verifier":
    """The rebuild-triple ADEQUACY gate (R3a) — the does-it gate at extract-exit.

    Reads the IR from `receipt.evidence["produces"]` (the extract phase's output;
    the extract edge only threads it into composed["ir"] at synthesize-entry) and
    passes iff BOTH hold:
      * the IR is well-formed AND its held-out split is real (fail-closed via
        `rebuild_ir.validate_ir`);
      * the wrapped R2 `coverage` verifier (pointed at the ORIGINAL) passes — the
        extracted tests clear the adequacy threshold. When no coverage verifier is
        configured, only the split-enforcement applies."""
    import rebuild_ir

    def _handler(unit, receipt, composed):
        ir_raw = (receipt.evidence if receipt else None) or {}
        ir_raw = ir_raw.get("produces")
        if ir_raw is None:
            ir_raw = composed.get("ir")
        try:
            rebuild_ir.validate_ir(ir_raw)
        except Exception as e:
            return Verdict(verified=False, defects=[f"inadequate IR: {e}"],
                           evidence={"check": "ir-split"})
        if coverage is not None:
            v = coverage.verify(unit, receipt, composed)
            if not v.verified:
                return Verdict(verified=False,
                               defects=v.defects or ["adequacy threshold not met"],
                               evidence={"check": "adequacy", **(v.evidence or {})})
        return Verdict(verified=True, evidence={"check": "adequacy-ok"})

    return CallableVerifier(_handler)


def _rebuild_triple_verifiers(coverage: "Verifier | None" = None) -> dict:
    """Gate map for a rebuild-triple walk: does-it -> adequacy (extract-exit),
    coverage-diff -> preservation (synthesize-exit). Both read from disk only.

    The synthesize-exit gate is COMPOSED (R3b): the copy-detection tripwire runs
    FIRST (a read outside the synth worktree = a copy attempt = fail, regardless
    of behavior), then the R3a `coverage_diff_verifier` preservation gate. This
    keeps the walk's single `coverage-diff` gate at that edge (routing unchanged)
    while making a silent absolute-path copy un-passable. The read-log SOURCE is
    an input for now (composed/receipt); wiring it to a real dispatched subagent's
    log is the B lap."""
    import isolation
    return {"does-it": adequacy_verifier(coverage),
            "coverage-diff": isolation.synthesize_exit_gate(coverage_diff_verifier())}


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


def verifiers_for_workflow(root: Path, wf, verifier: "Verifier | None" = None) -> dict:
    """Build the gate map for a workflow walk from policy/config (single source).

    Used by BOTH the synchronous `run_unit` path and the resumable phase-walk
    surface so the two never gate on a different verifier set. `rebuild-triple`
    gets the R3a/R3b triple gates; every other workflow gets the per-unit
    coverage/regression gate (coverage if configured, else the `verifier`)."""
    if wf.name == "rebuild-triple":
        return _rebuild_triple_verifiers(coverage_verifier_from_config(root))
    return _workflow_verifiers(verifier, coverage_verifier_from_config(root))


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
                else verifiers_for_workflow(root, wf, verifier)
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
