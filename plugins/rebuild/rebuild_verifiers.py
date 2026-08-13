#!/usr/bin/env python3
"""The rebuild seam's gate forms (Python toolchain): the spec-adequacy gate at
extract-exit and the coverage-diff preservation gate at synthesize-exit."""
from __future__ import annotations

from pathlib import Path

import rebuild_spec
from run import CallableVerifier, CommandVerifier, Verdict

def coverage_verifier(test_cmd: str | None, threshold, target: str | None = None,
                      timeout: int = 300):
    if threshold is None or (not test_cmd and not target):
        return None
    import shlex
    argv = list(shlex.split(test_cmd)) if test_cmd else ["pytest"]
    if target:
        argv.append(f"--cov={target}")
    argv.append(f"--cov-fail-under={threshold}")
    return CommandVerifier(lambda unit, receipt, composed, _argv=argv: _argv,
                           timeout=timeout)

def coverage_verifier_from_config(root: Path):
    try:
        import config
        cfg = config.read(root)
    except Exception:
        cfg = {}
    return coverage_verifier(cfg.get("coverage-cmd"), cfg.get("coverage-threshold"),
                             cfg.get("coverage-target"))

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

def coverage_diff_verifier(timeout: int = 300):

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

        code, detail = _run_held_out(spec["tests"]["held_out"], synth_path, timeout)
        if code != 0:
            return Verdict(verified=False,
                           defects=[f"held-out tests failed (exit {code})"],
                           evidence={"check": "held_out", "returncode": code,
                                     "detail": detail})

        return Verdict(verified=True,
                       evidence={"check": "all", "surface": sorted(surface)})

    return CallableVerifier(_handler)

def adequacy_verifier(coverage=None):

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

def rebuild_triple_verifiers(root: Path) -> dict:
    import isolation
    coverage = coverage_verifier_from_config(root)
    return {"does-it": adequacy_verifier(coverage),
            "coverage-diff": isolation.synthesize_exit_gate(coverage_diff_verifier())}
