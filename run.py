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
    import re
    nums = re.findall(r"[-+]?\d*\.?\d+", text or "")
    if not nums:
        return None
    try:
        return float(nums[-1])
    except ValueError:
        return None

def mutation_verifier(mutation_cmd, threshold, timeout: int = 600) -> "Verifier | None":
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

            return Verdict(verified=False, defects=["mutation score unparseable"],
                           evidence={"stdout": p.stdout.strip()[-1000:]})
        ok = p.returncode == 0
        return Verdict(verified=ok,
                       defects=[] if ok else [f"mutation barrier exit {p.returncode}"],
                       evidence={"returncode": p.returncode})

    return CallableVerifier(_handler)

def _norm_sig(sig: str | None) -> str:
    return "".join((sig or "").split())

def _fn_signature(node) -> str:
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

_DEFAULT_TSC_CMD = ["pnpm", "exec", "tsc"]

_DEFAULT_TS_HELD_CMD = ["pnpm", "exec", "vitest", "run"]

_TS_LANG_ALIASES = {"ts": "typescript", "typescript": "typescript", "tsx": "typescript"}
_PY_LANG_ALIASES = {"py": "python", "python": "python"}

class _ToolchainError(RuntimeError):
    pass

def _normalize_language(value) -> str:
    key = str(value or "python").strip().lower()
    return _TS_LANG_ALIASES.get(key) or _PY_LANG_ALIASES.get(key) or key

def _as_argv(cmd) -> list:
    if cmd is None:
        return []
    if isinstance(cmd, str):
        import shlex
        return shlex.split(cmd)
    return list(cmd)

def _is_ts_test_file(p: Path) -> bool:
    n = p.name
    if n.endswith(".d.ts"):
        return True
    stem = n.rsplit(".", 1)[0]
    if stem.endswith(".test") or stem.endswith(".spec"):
        return True
    return "__tests__" in p.parts

def _split_top_level(text: str) -> list:
    parts, depth, cur = [], 0, []
    for ch in text:
        if ch in "<({[":
            depth += 1
        elif ch in ">)}]":
            depth = max(0, depth - 1)
        if ch == "," and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    if cur:
        parts.append("".join(cur))
    return parts

def _ts_param_names(params: str) -> list:
    import re
    names = []
    for part in _split_top_level(params):
        part = part.strip()
        if not part:
            continue

        part = re.sub(r"^(?:public|private|protected|readonly)\s+", "", part).strip()
        m = re.match(r"(\.\.\.)?\s*([A-Za-z_$][\w$]*)", part)
        if m:
            names.append((m.group(1) or "") + m.group(2))
    return names

def _balanced_parens(text: str, open_idx: int) -> tuple:
    depth, i = 0, open_idx
    while i < len(text):
        c = text[i]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return text[open_idx + 1:i], i
        i += 1
    return "", len(text)

def _ts_parse_dts(text: str) -> tuple[set, dict]:
    import re
    surface: set = set()
    sigs: dict = {}
    decl = re.compile(
        r"\bexport\s+(?:declare\s+)?(?:default\s+)?(?:abstract\s+)?"
        r"(function|class|const|let|var|interface|type|enum)\s+"
        r"([A-Za-z_$][\w$]*)")
    for m in decl.finditer(text):
        kind, name = m.group(1), m.group(2)
        surface.add(name)
        if kind == "function":
            if name in sigs:
                continue
            paren = text.find("(", m.end())
            params, _ = _balanced_parens(text, paren) if paren != -1 else ("", 0)
            sigs[name] = f"{name}({', '.join(_ts_param_names(params))})"
        elif kind in ("class", "interface", "enum"):
            sigs.setdefault(name, f"{name}(...)")

    for m in re.finditer(r"\bexport\s*\{([^}]*)\}", text):
        for spec in _split_top_level(m.group(1)):
            spec = spec.strip()
            if not spec or spec.startswith("type "):
                continue
            name = spec.split(" as ")[-1].strip()
            if name and name != "default" and re.match(r"^[A-Za-z_$][\w$]*$", name):
                surface.add(name)
    return surface, sigs

def _ts_surface(tree_path: Path, tsc_cmd=None, timeout: int = 300) -> tuple[set, dict]:
    import subprocess
    import tempfile
    if tree_path.is_file():
        files = [tree_path]
    else:
        files = sorted(p for p in tree_path.rglob("*")
                       if p.suffix in (".ts", ".tsx") and not _is_ts_test_file(p))
    if not files:
        return set(), {}
    base = _as_argv(tsc_cmd) or list(_DEFAULT_TSC_CMD)
    with tempfile.TemporaryDirectory() as td:
        argv = base + ["--emitDeclarationOnly", "--declaration", "--skipLibCheck",
                       "--outDir", td, *[str(f) for f in files]]
        try:
            p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout,
                               cwd=str(tree_path if tree_path.is_dir() else tree_path.parent))
        except (subprocess.SubprocessError, OSError) as e:
            raise _ToolchainError(f"tsc could not run ({base[0]}): {e}") from e
        dts = sorted(Path(td).rglob("*.d.ts"))
        if not dts:
            detail = (p.stderr or p.stdout or "").strip()[-500:]
            raise _ToolchainError(f"tsc emitted no declarations (exit {p.returncode}): {detail}")
        surface: set = set()
        sigs: dict = {}
        for d in dts:
            try:
                s, g = _ts_parse_dts(d.read_text())
            except OSError:
                continue
            surface |= s
            sigs.update(g)
    return surface, sigs

def _run_held_out_ts(held: list, synth_path: Path, timeout: int, held_cmd=None) -> tuple[int, str]:
    import subprocess
    base = str(synth_path if synth_path.is_dir() else synth_path.parent)
    argv = (_as_argv(held_cmd) or list(_DEFAULT_TS_HELD_CMD)) + list(held)
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, cwd=base)
    except (subprocess.SubprocessError, OSError) as e:
        return 1, f"held-out run could not start: {e}"
    return p.returncode, (p.stdout or p.stderr or "").strip()[-1000:]

def ts_mutation_verifier(stryker_cmd=None, threshold=None, timeout: int = 600) -> "Verifier | None":
    if threshold is None:
        return None
    return mutation_verifier(stryker_cmd or "pnpm exec stryker run", threshold, timeout)

def coverage_diff_verifier(timeout: int = 300, language=None,
                           surface_cmd=None, held_out_cmd=None) -> "Verifier":
    import rebuild_spec

    def _handler(unit, receipt, composed):
        try:
            spec = rebuild_spec.validate_spec(composed.get("spec"))
        except Exception as e:
            return Verdict(verified=False, defects=[f"malformed spec: {e}"],
                           evidence={"check": "spec"})
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

        lang_signal = spec.get("language")
        if lang_signal is None:
            lang_signal = language
        lang = _normalize_language(lang_signal)
        ts_surface_cmd = spec.get("surface_cmd", surface_cmd)
        ts_held_cmd = spec.get("held_out_cmd", held_out_cmd)

        if lang == "typescript":
            try:
                surface, sigs = _ts_surface(synth_path, ts_surface_cmd, timeout)
            except _ToolchainError as e:
                return Verdict(verified=False,
                               defects=[f"TS surface extraction unavailable: {e}"],
                               evidence={"check": "toolchain", "language": lang})
        else:
            surface, sigs = _ast_surface(synth_path)

        missing = [s["symbol"] for s in spec["interface"] if s["symbol"] not in surface]
        if missing:
            return Verdict(verified=False,
                           defects=[f"missing interface symbols: {missing}"],
                           evidence={"check": "interface", "missing": missing})
        mism = []
        for s in spec["interface"]:
            want = _norm_sig(s.get("signature"))
            if want and _norm_sig(sigs.get(s["symbol"])) != want:
                mism.append({"symbol": s["symbol"], "expected": s["signature"],
                             "actual": sigs.get(s["symbol"])})
        if mism:
            return Verdict(verified=False,
                           defects=[f"signature mismatch: {mism}"],
                           evidence={"check": "interface", "mismatch": mism})

        extra = sorted(surface - set(spec["allowed_surface"]))
        if extra:
            return Verdict(verified=False,
                           defects=[f"surface exceeds allowed_surface: {extra}"],
                           evidence={"check": "surface", "extra": extra})

        if lang == "typescript":
            code, detail = _run_held_out_ts(spec["tests"]["held_out"], synth_path,
                                            timeout, ts_held_cmd)
        else:
            code, detail = _run_held_out(spec["tests"]["held_out"], synth_path, timeout)
        if code != 0:
            return Verdict(verified=False,
                           defects=[f"held-out tests failed (exit {code})"],
                           evidence={"check": "held_out", "returncode": code,
                                     "detail": detail})

        return Verdict(verified=True,
                       evidence={"check": "all", "surface": sorted(surface)})

    return CallableVerifier(_handler)

def adequacy_verifier(coverage: "Verifier | None" = None) -> "Verifier":
    import rebuild_spec

    def _handler(unit, receipt, composed):
        spec_raw = (receipt.evidence if receipt else None) or {}
        spec_raw = spec_raw.get("produces")
        if spec_raw is None:
            spec_raw = composed.get("spec")
        try:
            rebuild_spec.validate_spec(spec_raw)
        except Exception as e:
            return Verdict(verified=False, defects=[f"inadequate spec: {e}"],
                           evidence={"check": "spec-split"})
        if coverage is not None:
            v = coverage.verify(unit, receipt, composed)
            if not v.verified:
                return Verdict(verified=False,
                               defects=v.defects or ["adequacy threshold not met"],
                               evidence={"check": "adequacy", **(v.evidence or {})})
        return Verdict(verified=True, evidence={"check": "adequacy-ok"})

    return CallableVerifier(_handler)

def _rebuild_triple_verifiers(coverage: "Verifier | None" = None) -> dict:
    import isolation
    return {"does-it": adequacy_verifier(coverage),
            "coverage-diff": isolation.synthesize_exit_gate(coverage_diff_verifier())}

def _root_config(root: Path) -> dict:
    try:
        import config
        return config.read(root)
    except Exception:
        return {}

def coverage_verifier_from_config(root: Path) -> "Verifier | None":
    cfg = _root_config(root)
    return coverage_verifier(cfg.get("coverage-cmd"), cfg.get("coverage-threshold"),
                             cfg.get("coverage-target"))

def mutation_verifier_from_config(root: Path) -> "Verifier | None":
    cfg = _root_config(root)
    return mutation_verifier(cfg.get("mutation-cmd"), cfg.get("mutation-threshold"))

def _workflow_verifiers(verifier: "Verifier | None",
                        coverage: "Verifier | None" = None) -> dict:
    gate = coverage or verifier
    if gate is None:
        return {}
    return {"regression": gate, "does-it": gate}

def verifiers_for_workflow(root: Path, wf, verifier: "Verifier | None" = None) -> dict:
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
            wf_verifiers = verifiers if verifiers is not None\
                else verifiers_for_workflow(root, wf, verifier)
            return run_workflow(root, unit, wf, contributors, executor,
                                verifiers=wf_verifiers)
        journal.append(root, "workflow.unresolved", unit=unit.id,
                       workflow=unit.situation.workflow)

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
        attempt_composed = composed if not (feedback or attempt) else\
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

    barrier = barrier_verifier if barrier_verifier is not None\
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
