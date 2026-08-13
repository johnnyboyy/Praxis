#!/usr/bin/env python3
"""forge_check — the deterministic gate for a candidate workflow-pack module.

Runs the same structural validation the engine runs at load time
(`registry.validate_phase` / `registry.validate_workflow`), then DRY WALKS
each workflow through `phase_walk` with stub evidence in a throwaway root,
so a forge can be told "this pack works" before it is ever registered.

Usage:
    python3 scripts/forge_check.py <module_path> [--workflow NAME]
                                    [--root DIR] [--facts JSON]

Exit 0 only when validation reports no problems AND every walked workflow
reached a genuine terminal (a phase with no outgoing edges at all) on the
stub-evidence path. Exit 1 otherwise. A JSON report is always printed to
stdout, win or lose.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

PRAXIS_ROOT = Path(__file__).resolve().parent.parent
if str(PRAXIS_ROOT) not in sys.path:
    sys.path.insert(0, str(PRAXIS_ROOT))

import registry  # noqa: E402
from workflow import SEED_PHASES, Phase, Workflow  # noqa: E402

MAX_WALK_STEPS = 20


def load_module(module_path: Path):
    module_path = module_path.resolve()
    mod_dir = str(module_path.parent)
    if mod_dir not in sys.path:
        sys.path.insert(0, mod_dir)
    spec = importlib.util.spec_from_file_location(module_path.stem, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load a module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _call(obj, method: str):
    provider = getattr(obj, method, None)
    if not callable(provider):
        return None
    return provider()


def collect(module, root) -> tuple[list, list, list[str]]:
    """Collect candidate phases/workflows: prefer the module's make(root)
    contributor when present, else fall back to module-level Phase/Workflow
    objects. Returns (phases, workflows, load_problems)."""
    make = getattr(module, "make", None)
    if callable(make):
        try:
            contributor = make(root)
        except Exception as e:
            return [], [], [f"make(root) raised: {e!r}"]
        phases = list(_call(contributor, "phases") or [])
        workflows = list(_call(contributor, "workflows") or [])
        return phases, workflows, []

    phases, workflows = [], []
    for _name, val in vars(module).items():
        if isinstance(val, Phase):
            phases.append(val)
        elif isinstance(val, Workflow):
            workflows.append(val)
    return phases, workflows, []


def validate(phases: list, workflows: list) -> tuple[list[str], set[str]]:
    """Returns (problems, names of workflows that failed validate_workflow)."""
    problems: list[str] = []
    merged_phases = dict(SEED_PHASES)
    merged_phases.update({p.name: p for p in phases if isinstance(p, Phase)})

    for p in phases:
        for msg in registry.validate_phase(p):
            problems.append(f"phase {getattr(p, 'name', p)!r}: {msg}")

    invalid_workflows: set[str] = set()
    for w in workflows:
        msgs = registry.validate_workflow(w, merged_phases)
        if msgs:
            invalid_workflows.add(getattr(w, "name", None))
        for msg in msgs:
            problems.append(f"workflow {getattr(w, 'name', w)!r}: {msg}")

    return problems, invalid_workflows


def _outgoing(workflow: Workflow, phase_name: str) -> list:
    return [e for e in workflow.edges if e[0] == phase_name]


def _structural_terminals(workflow: Workflow) -> set[str]:
    """Phases with no outgoing edge at all — the only phases a dead-end
    'complete' from the engine can be trusted to mean an actual terminal."""
    sources = {e[0] for e in workflow.edges}
    return {p.name for p in workflow.phases if p.name not in sources}


def _unreachable_phases(workflow: Workflow) -> list[str]:
    targets = {e[1] for e in workflow.edges}
    return [p.name for p in workflow.phases
            if p.name != workflow.first.name and p.name not in targets]


def dry_walk(workflow: Workflow, facts: dict) -> dict:
    import phase_walk
    from run import Unit
    from situation import Situation

    report = {"name": workflow.name, "walked": [], "terminal": None, "warnings": []}

    fail_edges = [(e[0], e[1]) for e in workflow.edges if e[2] == "fail"]
    if fail_edges:
        report["warnings"].append(
            f"fail edges never exercised by the stub walk (informational): {fail_edges}")

    unreachable = _unreachable_phases(workflow)
    if unreachable:
        report["warnings"].append(f"unreachable phases (no incoming edge): {unreachable}")

    structural_terminals = _structural_terminals(workflow)

    with tempfile.TemporaryDirectory() as tmp:
        walk_root = Path(tmp)
        (walk_root / ".praxis").mkdir(parents=True, exist_ok=True)

        situation = Situation(task_kind="change", intent="forge-check dry walk",
                              subject="coding", workflow=workflow.name)
        unit = Unit(id="forge-check-unit", situation=situation)

        steps = 0
        while steps < MAX_WALK_STEPS:
            nxt = phase_walk.next_phase(walk_root, unit, workflow=workflow)
            if nxt["status"] == "complete":
                phase_name = nxt.get("terminal")
                if phase_name in structural_terminals:
                    report["terminal"] = phase_name
                else:
                    report["warnings"].append(
                        f"{phase_name}: fact-gated route not exercisable with stub "
                        f"evidence; provide --facts JSON to exercise")
                break
            if nxt["status"] != "phase":
                report["warnings"].append(f"unexpected next_phase status: {nxt}")
                break

            phase_name = nxt["phase"]
            report["walked"].append(phase_name)

            outs = _outgoing(workflow, phase_name)
            has_default = any(e[2] in ("pass", "always") for e in outs)
            has_fact = any(e[2] == "fact" for e in outs)

            evidence = {"passed": True, "produces": f"stub-{phase_name}"}
            stub_facts = facts.get(phase_name)
            if stub_facts:
                evidence.update(stub_facts)
            elif has_fact and not has_default:
                report["warnings"].append(
                    f"{phase_name}: fact-gated edges with no default; walking with "
                    f"empty facts (pass --facts to exercise a specific route)")

            rec = phase_walk.record_phase(walk_root, unit, phase_name, evidence,
                                          verifiers={}, workflow=workflow)
            if not rec.get("advance"):
                report["warnings"].append(
                    f"{phase_name}: stub evidence did not advance "
                    f"(gate={rec.get('gate')}, defects={rec.get('defects')})")
                break
            steps += 1
        else:
            report["warnings"].append(
                f"dry walk exceeded {MAX_WALK_STEPS} steps without reaching a terminal")

    return report


def run_check(module_path: Path, workflow_name: str | None, root: Path,
             facts: dict | None = None) -> tuple[dict, bool]:
    facts = facts or {}
    problems: list[str] = []

    try:
        module = load_module(module_path)
    except Exception as e:
        return {"module": str(module_path), "phases": [], "workflows": [],
                "problems": [f"could not load module: {e!r}"]}, False

    phases, workflows, load_problems = collect(module, root)
    problems.extend(load_problems)
    val_problems, invalid_workflows = validate(phases, workflows)
    problems.extend(val_problems)

    to_walk = workflows
    if workflow_name is not None:
        to_walk = [w for w in workflows if getattr(w, "name", None) == workflow_name]
        if not to_walk:
            problems.append(f"no workflow named {workflow_name!r} among candidates")

    walked_reports = []
    all_terminal = True
    for w in to_walk:
        if not isinstance(w, Workflow) or w.name in invalid_workflows:
            all_terminal = False
            continue
        wr = dry_walk(w, facts)
        wr["valid"] = w.name not in invalid_workflows
        walked_reports.append(wr)
        if wr["terminal"] is None:
            all_terminal = False

    report = {
        "module": str(module_path),
        "phases": [getattr(p, "name", str(p)) for p in phases],
        "workflows": walked_reports,
        "problems": problems,
    }
    ok = not problems and all_terminal and (bool(walked_reports) or not workflows)
    return report, ok


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Validate + dry-walk a workflow-pack module.")
    ap.add_argument("module_path", help="path to the candidate pack module (.py)")
    ap.add_argument("--workflow", default=None,
                    help="only dry-walk this workflow by name (default: all candidates)")
    ap.add_argument("--root", default=None,
                    help="root passed to the module's make(root) contributor "
                         "(default: current directory)")
    ap.add_argument("--facts", default=None,
                    help='JSON: {"phase-name": {...stub evidence facts...}} — merged into '
                         'the stub evidence dict for that phase so fact-edge predicates '
                         'can match against it')
    args = ap.parse_args(argv)

    root = Path(args.root).resolve() if args.root else Path.cwd()
    facts = {}
    if args.facts:
        facts = json.loads(args.facts)

    report, ok = run_check(Path(args.module_path), args.workflow, root, facts)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
