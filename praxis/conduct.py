#!/usr/bin/env python3
"""conduct — the wiring that lets a real harness drive work THROUGH the conductor.

This is surface/wiring, not core (like adapters.py it is allowed to know the world): it binds the
pure conductor loop (`run.run_unit`) to a real judgment provider (corpora, via `adapters`), a real
executor (an isolated `claude -p` subprocess), and a real verifier (a project test command). The
core modules still import neither praxis nor corpora.

`run_task` is the single entry the MCP tool (mcp_server.py) and the CLI call. A `dry_run` builds the
situation, consults corpora (surfacing any vocabulary gap), and assembles the child command —
WITHOUT spawning claude or writing a unit lifecycle — so an operator can preview the composed
judgment and the routing before paying for a real run.
"""
from __future__ import annotations

import json
import re
import shlex
import subprocess
import time
from pathlib import Path

import accretion
import adapters
import handoff as handoff_mod
import journal
import policy as policy_mod
import providers
import views
from run import CommandVerifier, Receipt, Unit, run_unit
from situation import Situation

# ── project shape (features corpora's applies-when predicates read) ──────────────────────────────

_SHAPE_KEYS = ("language", "framework", "has-ui", "styling", "package-manager")


def project_shape_for(root: str | Path) -> dict:
    """Read the `## project-shape` fields from `<root>/.corpora/config.md` (the features
    non-universal corpora domains gate on). Missing file → {} (universals + subject-matched
    non-gated domains still compose)."""
    for cfg in (Path(root) / ".corpora" / "config.md", Path(root) / "corpora" / "config.md"):
        try:
            text = cfg.read_text()
        except OSError:
            continue
        shape = {}
        for key in _SHAPE_KEYS:
            m = re.search(rf"^{re.escape(key)}:\s*(.+?)\s*$", text, re.MULTILINE)
            if m:
                shape[key] = m.group(1).strip()
        return shape
    return {}


# ── the claude-p executor (the 'how it runs' seam, pointed at Claude Code headless) ──────────────

class ClaudeExecutor:
    """Runs a unit as an isolated `claude -p` subprocess seeded with the composed judgment as the
    appended system prompt. Clean run → a `result` receipt carrying the child's summary as evidence
    and its cost; a nonzero exit / launch failure / timeout / `is_error` → a recorded blocked stall,
    never an exception. `allow_edits` adds `--permission-mode bypassPermissions` so the child can
    actually edit (off by default — a read-only child is a safe no-op); extra flags come from
    `CONDUCTOR_CLAUDE_EXTRA_ARGS`."""

    def __init__(self, *, brief: str | None = None, model: str | None = None,
                 cwd: str | None = None, timeout: int = 900, allow_edits: bool = False,
                 max_turns: int | None = None, dry_run: bool = False):
        self.brief = brief
        self.model = model
        self.cwd = cwd
        self.timeout = timeout
        self.allow_edits = allow_edits
        self.max_turns = max_turns
        self.dry_run = dry_run

    def _argv(self, brief: str, judgment: str) -> list[str]:
        import os
        argv = ["claude", "-p", brief, "--output-format", "json"]
        if judgment:
            argv += ["--append-system-prompt", judgment]
        if self.model:
            argv += ["--model", self.model]
        if self.allow_edits:
            argv += ["--permission-mode", "bypassPermissions"]
        if self.max_turns:
            argv += ["--max-turns", str(self.max_turns)]
        extra = os.environ.get("CONDUCTOR_CLAUDE_EXTRA_ARGS")
        if extra:
            argv += shlex.split(extra)
        return argv

    def preview(self, unit: Unit, composed: dict) -> dict:
        ho = handoff_mod.assemble(unit.situation.intent, composed, brief=self.brief)
        judgment, brief = ho["judgment"], ho["brief"]
        argv = self._argv(brief, judgment)
        # redact the (large) judgment from the shown argv
        shown = [("<judgment %d bytes>" % len(judgment)) if a is judgment else a for a in argv]
        return {"argv": shown, "brief": brief, "judgment_bytes": len(judgment),
                "allow_edits": self.allow_edits, "model": self.model, "cwd": self.cwd}

    def run(self, unit: Unit, composed: dict) -> Receipt:
        ho = handoff_mod.assemble(unit.situation.intent, composed, brief=self.brief)
        judgment, brief = ho["judgment"], ho["brief"]
        argv = self._argv(brief, judgment)
        if self.dry_run:
            return Receipt(outcome="result", status="complete",
                           evidence={"dry_run": self.preview(unit, composed)})
        try:
            p = subprocess.run(argv, capture_output=True, text=True, timeout=self.timeout,
                               cwd=self.cwd)
        except (subprocess.SubprocessError, OSError) as e:
            return Receipt(outcome="stall", status="blocked", surfaced=[f"claude spawn failed: {e}"])
        if p.returncode != 0:
            reason = (p.stderr.strip() or p.stdout.strip())[:800] or f"exit {p.returncode}"
            return Receipt(outcome="stall", status="blocked", surfaced=[reason])
        return self._receipt_from_claude_json(p.stdout)

    @staticmethod
    def _receipt_from_claude_json(stdout: str) -> Receipt:
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            # a clean exit with unparseable output: took as a bare result with the raw text
            return Receipt(outcome="result", status="complete",
                           evidence={"result": stdout.strip()[:2000]})
        if data.get("is_error"):
            return Receipt(outcome="stall", status="blocked",
                           surfaced=[str(data.get("result") or "claude reported an error")])
        cost = None
        if data.get("total_cost_usd") is not None or data.get("usage"):
            usage = data.get("usage") or {}
            cost = {"usd": data.get("total_cost_usd"),
                    "tokens": (usage.get("input_tokens", 0) or 0) + (usage.get("output_tokens", 0) or 0)}
        return Receipt(outcome="result", status="complete",
                       evidence={"result": data.get("result"), "num_turns": data.get("num_turns")},
                       cost=cost)


# ── the entry the MCP tool + CLI call ────────────────────────────────────────────────────────────

def run_task(root: str | Path, *, intent: str, brief: str | None = None,
             task_kind: str = "change", subject: str = "coding",
             suggested_kind: str | None = None, fit: str = "clean", phase: str = "none",
             targets=(), label: str | None = None, workflow: str | None = None,
             project_shape: dict | None = None, test_cmd: str | None = None,
             model: str | None = None, max_retries: int | None = None,
             allow_edits: bool = False, dry_run: bool = False) -> dict:
    """Drive one unit of work through the conductor: build the situation (harvesting the model's
    `suggested_kind`/`fit`), consult corpora, dispatch to an isolated claude, verify with the test
    command, and record everything to the journal. `dry_run` previews composition + routing + the
    child command without spawning or writing a unit."""
    root = Path(root).resolve()
    shape = project_shape if project_shape is not None else project_shape_for(root)
    situation = Situation(task_kind=task_kind, intent=intent, subject=subject,
                          suggested_kind=suggested_kind, fit=fit, phase=phase,
                          project_shape=shape, root=str(root), targets=list(targets),
                          workflow=workflow, label=label)
    provider = adapters.corpora_provider(root)

    if dry_run:
        composed = providers.consult(provider, situation, root=root)
        preview = ClaudeExecutor(brief=brief, model=model, cwd=str(root), allow_edits=allow_edits,
                                 dry_run=True).preview(_stub_unit(situation), composed)
        return {"dry_run": True, "routed_kind": composed.get("routed_kind"),
                "gap_surfaced": composed.get("gap_surfaced"), "stance": composed.get("stance"),
                "domains": composed.get("domains"), "note": composed.get("note"),
                "child_command": preview,
                "next": "re-call with dry_run=false and allow_edits=true to execute"}

    retries = (policy_mod.load_policy(root).max_retries if max_retries is None else max_retries)
    executor = ClaudeExecutor(brief=brief, model=model, cwd=str(root), allow_edits=allow_edits)
    verifier = None
    if test_cmd:
        argv = shlex.split(test_cmd)
        verifier = CommandVerifier(lambda u, r, c, _argv=argv: _argv)
    unit = Unit(id=_gen_id(task_kind), situation=situation)
    result = run_unit(root, unit, provider, executor, verifier, retries)
    result["cost"] = views.cost(root)
    return result


# ── the tasklist entry (1..N tasks → plan → cascade through run_dag) ────────────────────────

def run_tasklist(root: str | Path, tasks: list[dict], *, test_cmd: str | None = None,
                 model: str | None = None, max_retries: int | None = None,
                 concurrency: int | None = None, allow_edits: bool = False,
                 dry_run: bool = False) -> dict:
    """Drive a whole tasklist through the conductor: the caller (the interactive planner) hands over
    structured tasks — each with its intent, seed `task_kind`, the gap signal (`suggested_kind`/
    `fit`), and any `depends_on` edges — and the conductor plans them into a DAG and sets it
    cascading through `run_dag`, each unit composing its own judgment and gating on `test_cmd`.

    `dry_run` previews the plan (the units, their edges, and each unit's composed routing + gap)
    WITHOUT spawning or writing a plan — call it once to check the shape, then re-call with
    dry_run=false, allow_edits=true to execute."""
    import plan as plan_mod
    root = Path(root).resolve()
    provider = adapters.corpora_provider(root)
    specs = _specs_for(root, tasks)

    if dry_run:
        units = plan_mod.build_units(specs, root)
        preview = []
        for u in units:
            composed = providers.consult(provider, u.situation, root=None)  # no gap write on preview
            preview.append({"unit": u.id, "depends_on": u.depends_on,
                            "routed_kind": composed.get("routed_kind"),
                            "would_surface_gap": u.situation.has_gap,
                            "domains": composed.get("domains"), "note": composed.get("note")})
        return {"dry_run": True, "plan": {"units": [u.id for u in units],
                "edges": [[d, u.id] for u in units for d in u.depends_on]}, "units": preview,
                "next": "re-call with dry_run=false and allow_edits=true to execute"}

    executor = ClaudeExecutor(model=model, cwd=str(root), allow_edits=allow_edits)
    verifier = None
    if test_cmd:
        argv = shlex.split(test_cmd)
        verifier = CommandVerifier(lambda u, r, c, _argv=argv: _argv)
    return plan_mod.plan_and_run(root, specs, provider, executor, verifier=verifier,
                                 concurrency=concurrency, max_retries=max_retries)


def _specs_for(root: Path, tasks: list[dict]) -> list:
    """Build TaskSpecs from a raw tasklist, defaulting each task's project_shape to the root's shape
    (the features non-universal domains gate on)."""
    import plan as plan_mod
    shape = project_shape_for(root)
    specs = []
    for t in tasks:
        d = dict(t)
        d.setdefault("project_shape", shape)
        specs.append(plan_mod.TaskSpec.from_dict(d))
    return specs


# ── background cascade (so the MCP call can't wedge on a long DAG of spawns) ──────────────────────

import threading  # noqa: E402

_RUNS: dict[str, dict] = {}          # root path -> {thread, started, done}
_RUNS_LOCK = threading.Lock()


def _cascade_running(key: str) -> bool:
    run = _RUNS.get(key)
    return bool(run and not run.get("done") and run["thread"].is_alive())


def run_tasklist_async(root: str | Path, tasks: list[dict], *, test_cmd: str | None = None,
                       model: str | None = None, max_retries: int | None = None,
                       concurrency: int | None = None, allow_edits: bool = False,
                       executor=None, provider=None) -> dict:
    """Record the plan, then run the DAG in a BACKGROUND thread and return immediately — so a long
    cascade of isolated child spawns never blocks (and never times out) the MCP call. Progress is
    observed through the journal via `plan_status` / `conductor_status`. The background run is
    `resume=True`, so a re-invocation (or a restart) continues from the journal instead of
    re-spawning finished units; a cascade already in flight for this root is not started twice.
    `executor` is injectable for tests; production uses an isolated `ClaudeExecutor`."""
    import plan as plan_mod
    from run import Plan
    from schedule import run_dag
    root = Path(root).resolve()
    key = str(root)
    with _RUNS_LOCK:
        if _cascade_running(key):
            return {"status": "already-running", "since": _RUNS[key]["started"],
                    "note": "a cascade is already in flight for this root; poll plan_status"}

    specs = _specs_for(root, tasks)
    outcome = plan_mod.plan_tasks(root, specs)
    if outcome.status == "questions":
        return {"status": "questions", "questions": outcome.questions, "note": outcome.note}
    units = outcome.units
    prov = provider if provider is not None else adapters.corpora_provider(root)
    ex = executor if executor is not None else ClaudeExecutor(model=model, cwd=str(root),
                                                              allow_edits=allow_edits)
    verifier = None
    if test_cmd:
        argv = shlex.split(test_cmd)
        verifier = CommandVerifier(lambda u, r, c, _argv=argv: _argv)

    def _worker():
        try:
            run_dag(Plan(units=units), prov, ex, root, verifier=verifier,
                    concurrency=concurrency, max_retries=max_retries, resume=True)
        except Exception as e:  # never let a background crash vanish silently — record it
            journal.append(root, "conductor.plan", status="error", note=f"cascade failed: {e}")
        finally:
            with _RUNS_LOCK:
                if key in _RUNS:
                    _RUNS[key]["done"] = True

    t = threading.Thread(target=_worker, name=f"cascade:{key}", daemon=True)
    with _RUNS_LOCK:
        _RUNS[key] = {"thread": t, "started": time.time(), "done": False}
    t.start()
    return {"status": "running",
            "plan": {"units": [u.id for u in units],
                     "edges": [[d, u.id] for u in units for d in u.depends_on]},
            "note": "the cascade runs in the background — poll plan_status (or conductor_status) to "
                    "watch units complete; call again to resume if it is interrupted"}


def plan_status(root: str | Path) -> dict:
    """Where the current plan stands, folded from the journal: per-unit progress buckets
    (done / in_flight / stalled / waiting), whether a background cascade is still running, and the
    cost rollup. `no-plan` when no tasklist has been registered for this root."""
    import handoff as handoff_mod
    import plan as plan_mod
    root = Path(root).resolve()
    units = plan_mod.reconstruct_units(root)
    if units is None:
        return {"status": "no-plan", "note": "no tasklist has been planned for this root yet"}
    prog = handoff_mod.status(root, units)
    running = _cascade_running(str(root))
    status = "running" if running else ("complete" if prog["complete"] else "idle")
    return {"status": status, "progress": prog, "cost": views.cost(root)}


def register_plan(root: str | Path, tasks: list[dict]) -> dict:
    """Record a tasklist's DAG to the journal WITHOUT running it — the entry the pull workflow needs.
    Registering is judgment-free (the deterministic PassthroughPlanner): it assigns ids, validates
    the edges, and writes one `conductor.plan` event carrying the resolved specs, so `next_handoff`
    can reconstruct the plan and hand units into the caller's OWN context one at a time. No provider
    consult, no spawn, no cascade — the opposite of `run_tasklist` (which records AND cascades
    isolated children). Use this when you mean to implement the units inline, pulling each handoff."""
    import plan as plan_mod
    root = Path(root).resolve()
    specs = _specs_for(root, tasks)
    outcome = plan_mod.plan_tasks(root, specs)
    if outcome.status == "questions":
        return {"status": "questions", "questions": outcome.questions, "note": outcome.note}
    units = outcome.units
    return {"status": "registered",
            "plan": {"units": [u.id for u in units],
                     "edges": [[d, u.id] for u in units for d in u.depends_on]},
            "next": "call next_handoff to pull the next ready unit into this context (it frames the "
                    "unit and opens the edit gate); repeat until status is complete"}


def next_handoff(root: str | Path, brief: str | None = None) -> dict:
    """The PULL: reconstruct the current plan from the journal and hand the next ready unit's brief +
    composed judgment to a self-advancing agent, recording the read that opens the edit gate for it.
    Returns a `waiting`/`complete` status when nothing is ready. No plan on the log → an error dict."""
    import handoff as handoff_mod
    import plan as plan_mod
    root = Path(root).resolve()
    units = plan_mod.reconstruct_units(root)
    if units is None:
        return {"status": "no-plan", "note": "no tasklist has been planned for this root yet"}
    return handoff_mod.pull(root, units, adapters.corpora_provider(root), brief=brief)


def _stub_unit(situation: Situation) -> Unit:
    return Unit(id="preview", situation=situation)


def _gen_id(task_kind: str) -> str:
    return f"{task_kind}-{int(time.time())}-{int(time.time() * 1000) % 1000:03d}"


# ── CLI (a runnable entrypoint independent of MCP) ───────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="conduct", description="drive a unit of work through the conductor")
    ap.add_argument("--root", default=".")
    ap.add_argument("--intent", required=True)
    ap.add_argument("--brief", default=None)
    ap.add_argument("--task-kind", default="change")
    ap.add_argument("--subject", default="coding")
    ap.add_argument("--suggested-kind", default=None)
    ap.add_argument("--fit", default="clean", choices=["clean", "loose", "none"])
    ap.add_argument("--phase", default="none")
    ap.add_argument("--targets", default="")
    ap.add_argument("--test-cmd", default=None)
    ap.add_argument("--model", default=None)
    ap.add_argument("--allow-edits", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    out = run_task(a.root, intent=a.intent, brief=a.brief, task_kind=a.task_kind, subject=a.subject,
                   suggested_kind=a.suggested_kind, fit=a.fit, phase=a.phase,
                   targets=[t for t in a.targets.split(",") if t], test_cmd=a.test_cmd,
                   model=a.model, allow_edits=a.allow_edits, dry_run=a.dry_run)
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
