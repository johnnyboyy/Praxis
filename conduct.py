#!/usr/bin/env python3
from __future__ import annotations

import json
import shlex
import subprocess
import time
from pathlib import Path

import accretion
import config as config_mod
import contributors as contributors_mod
import handoff as handoff_mod
import journal
import policy as policy_mod
import views
from run import Receipt, Unit, run_unit, verifier_from_test_cmd
from situation import Situation


_REBUILD_IGNORE = ".rebuild/"
_REBUILD_IGNORE_COMMENT = (
    "# praxis rebuild-triple scratch (extract→synthesize working dir) — never committed"
)


def _ensure_rebuild_gitignore(git_root: Path) -> bool:
    """Ensure the repo's `.gitignore` ignores the rebuild-triple scratch dir.

    Idempotent: a no-op if any line already ignores `.rebuild/`. A bare pattern
    (no leading slash) matches at any depth, so it covers `apps/*/.rebuild/` in a
    monorepo too. Returns True when it appended the entry.
    """
    gitignore = Path(git_root) / ".gitignore"
    existing = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
    if any(line.strip() == _REBUILD_IGNORE for line in existing.splitlines()):
        return False
    prefix = existing.rstrip() + "\n\n" if existing.strip() else ""
    gitignore.write_text(
        f"{prefix}{_REBUILD_IGNORE_COMMENT}\n{_REBUILD_IGNORE}\n", encoding="utf-8")
    return True


def init_root(root=None) -> dict:
    """Mark a directory a managed praxis root by ensuring an empty `.praxis/config.json` exists.

    In a git repo it also ensures `.gitignore` ignores the rebuild-triple scratch
    dir (`.rebuild/`), so extract→synthesize working files never get committed.
    """
    import root_tree
    start = Path(root).resolve() if root else Path.cwd()
    git_root = root_tree._git_toplevel(start)
    target = git_root if git_root is not None else start
    created = config_mod.ensure(target)
    gitignore_updated = (
        _ensure_rebuild_gitignore(git_root) if git_root is not None else False)
    return {"status": "initialized", "root": str(target),
            "config": str(config_mod.path(target)), "created": created,
            "gitignore_updated": gitignore_updated}


class ClaudeExecutor:

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

    def _argv(self, brief: str, overlay: str) -> list[str]:
        import os
        argv = ["claude", "-p", brief, "--output-format", "json"]
        if overlay:
            argv += ["--append-system-prompt", overlay]
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
        overlay, brief = ho["overlay"], ho["brief"]
        argv = self._argv(brief, overlay)
        redacted_argv = [("<overlay %d bytes>" % len(overlay)) if a is overlay else a for a in argv]
        return {"argv": redacted_argv, "brief": brief, "overlay_bytes": len(overlay),
                "allow_edits": self.allow_edits, "model": self.model, "cwd": self.cwd}

    def run(self, unit: Unit, composed: dict) -> Receipt:
        ho = handoff_mod.assemble(unit.situation.intent, composed, brief=self.brief)
        overlay, brief = ho["overlay"], ho["brief"]
        argv = self._argv(brief, overlay)
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


def run_task(root: str | Path, *, intent: str, brief: str | None = None,
             task_kind: str = "change", subject: str = "coding",
             suggested_kind: str | None = None, fit: str = "clean", phase: str = "none",
             targets=(), label: str | None = None, workflow: str | None = None,
             test_cmd: str | None = None,
             model: str | None = None, max_retries: int | None = None,
             allow_edits: bool = False, dry_run: bool = False) -> dict:
    root = Path(root).resolve()
    situation = Situation(task_kind=task_kind, intent=intent, subject=subject,
                          suggested_kind=suggested_kind, fit=fit, phase=phase,
                          root=str(root), targets=list(targets),
                          workflow=workflow, label=label)
    contributors = contributors_mod.contributors_for(root)

    if dry_run:
        composed = contributors_mod.gather(contributors, situation, root=root)
        preview = ClaudeExecutor(brief=brief, model=model, cwd=str(root), allow_edits=allow_edits,
                                 dry_run=True).preview(_stub_unit(situation), composed)
        return {"dry_run": True, "routed_kind": composed.get("routed_kind"),
                "gap_surfaced": composed.get("gap_surfaced"), "stance": composed.get("stance"),
                "sources": composed.get("sources"), "note": composed.get("note"),
                "child_command": preview,
                "next": "re-call with dry_run=false and allow_edits=true to execute"}

    retries = (policy_mod.load_policy(root).max_retries if max_retries is None else max_retries)
    executor = ClaudeExecutor(brief=brief, model=model, cwd=str(root), allow_edits=allow_edits)
    verifier = verifier_from_test_cmd(test_cmd)
    unit = Unit(id=_gen_id(task_kind), situation=situation)
    result = run_unit(root, unit, contributors, executor, verifier, retries)
    result["cost"] = views.cost(root)
    return result


def run_tasklist(root: str | Path, tasks: list[dict], *, test_cmd: str | None = None,
                 model: str | None = None, max_retries: int | None = None,
                 concurrency: int | None = None, allow_edits: bool = False,
                 dry_run: bool = False) -> dict:
    import plan as plan_mod
    root = Path(root).resolve()
    contributors = contributors_mod.contributors_for(root)
    specs = _specs_for(root, tasks)

    if dry_run:
        units = plan_mod.build_units(specs, root)
        preview = []
        no_gap_recording = None
        for u in units:
            composed = contributors_mod.gather(contributors, u.situation, root=no_gap_recording)
            preview.append({"unit": u.id, "depends_on": u.depends_on,
                            "routed_kind": composed.get("routed_kind"),
                            "would_surface_gap": u.situation.has_gap,
                            "sources": composed.get("sources"), "note": composed.get("note")})
        return {"dry_run": True, "plan": {"units": [u.id for u in units],
                "edges": [[d, u.id] for u in units for d in u.depends_on]}, "units": preview,
                "next": "re-call with dry_run=false and allow_edits=true to execute"}

    executor = ClaudeExecutor(model=model, cwd=str(root), allow_edits=allow_edits)
    verifier = verifier_from_test_cmd(test_cmd)
    return plan_mod.plan_and_run(root, specs, contributors, executor, verifier=verifier,
                                 concurrency=concurrency, max_retries=max_retries)


def _specs_for(root: Path, tasks: list[dict]) -> list:
    import plan as plan_mod
    return [plan_mod.TaskSpec.from_dict(dict(t)) for t in tasks]


def run_tasklist_detached(root: str | Path, tasks: list[dict], *, test_cmd: str | None = None,
                          model: str | None = None, max_retries: int | None = None,
                          concurrency: int | None = None, allow_edits: bool = False) -> dict:
    import cascade
    return cascade.launch_detached(root, tasks, test_cmd=test_cmd, model=model,
                                   max_retries=max_retries, concurrency=concurrency,
                                   allow_edits=allow_edits)


def plan_status(root: str | Path) -> dict:
    import cascade
    import handoff as handoff_mod
    import plan as plan_mod
    root = Path(root).resolve()
    units = plan_mod.reconstruct_units(root)
    if units is None:
        return {"status": "no-plan", "note": "no tasklist has been planned for this root yet"}
    prog = handoff_mod.status(root, units)
    live = cascade.is_running(root)
    status = "running" if live else ("complete" if prog["complete"] else "idle")
    out = {"status": status, "progress": prog, "cost": views.cost(root)}
    if live:
        out["worker"] = {"pid": live.get("pid"), "since": live.get("started")}
    return out


def register_plan(root: str | Path, tasks: list[dict]) -> dict:
    import plan as plan_mod
    root = Path(root).resolve()
    specs = _specs_for(root, tasks)
    units = plan_mod.plan_tasks(root, specs)
    return {"status": "registered",
            "plan": {"units": [u.id for u in units],
                     "edges": [[d, u.id] for u in units for d in u.depends_on]},
            "next": "call next_handoff to pull the next ready unit into this context (it frames the "
                    "unit and opens the edit gate); repeat until status is complete"}


def next_handoff(root: str | Path, brief: str | None = None) -> dict:
    import handoff as handoff_mod
    import plan as plan_mod
    root = Path(root).resolve()
    units = plan_mod.reconstruct_units(root)
    if units is None:
        return {"status": "no-plan", "note": "no tasklist has been planned for this root yet"}
    return handoff_mod.pull(root, units, contributors_mod.contributors_for(root), brief=brief)


def _find_unit(root: Path, unit_id: str):
    """Reconstruct the planned units and return the one named `unit_id`, or None."""
    import plan as plan_mod
    units = plan_mod.reconstruct_units(root)
    if units is None:
        return None
    return next((u for u in units if u.id == unit_id), None)


def next_phase(root: str | Path, unit_id: str) -> dict:
    """The resumable phase-walk read: the phase to execute now for `unit_id`.

    Mirrors `next_handoff` at the phase level — a pure fold over the journal, no
    mutation. `no-plan` when nothing is planned, `unknown-unit` when the id isn't
    in the plan."""
    import phase_walk
    root = Path(root).resolve()
    unit = _find_unit(root, unit_id)
    if unit is None:
        import plan as plan_mod
        if plan_mod.reconstruct_units(root) is None:
            return {"status": "no-plan",
                    "note": "no tasklist has been planned for this root yet"}
        return {"status": "unknown-unit", "unit": unit_id}
    return phase_walk.next_phase(root, unit)


def record_phase(root: str | Path, unit_id: str, phase: str, evidence: dict | None = None,
                 test_cmd: str | None = None) -> dict:
    """Record one phase's result and advance the journal cursor — mirrors
    `record_receipt` at the phase level. The incoming edge's gate is run FROM DISK
    against `evidence`; the cursor never advances past a failed gate."""
    import phase_walk
    root = Path(root).resolve()
    unit = _find_unit(root, unit_id)
    if unit is None:
        import plan as plan_mod
        if plan_mod.reconstruct_units(root) is None:
            return {"status": "no-plan",
                    "note": "no tasklist has been planned for this root yet"}
        return {"status": "unknown-unit", "unit": unit_id}
    return phase_walk.record_phase(root, unit, phase, evidence or {},
                                   verifier=verifier_from_test_cmd(test_cmd))


def _workflow_close_status(root: Path, unit_id: str) -> tuple[str, str | None] | None:
    """Certify a workflow-driven unit's walk for close, by pure fold over the journal.

    Returns None when the unit is NOT workflow-driven (no phase events) — close is
    ungated, preserving single-dispatch behavior. Otherwise returns ("complete", None)
    when the walk reached a terminal phase with every gate verified, or
    ("halted", reason) when the walk stalled or any gate failed to verify. The signal
    is the engine-run gate's `verified` flag on `phase.exited` (from a command's exit
    code) — never model-supplied evidence."""
    events = [e for e in journal.read(root) if e.get("unit") == unit_id]
    exited = [e for e in events if e.get("event") == "phase.exited"]
    entered = [e for e in events if e.get("event") == "phase.entered"]
    if not exited and not entered:
        return None  # not a workflow walk
    stalled = [e for e in events if e.get("event") == "phase.stalled"]
    if stalled:
        phase = stalled[-1].get("phase")
        return ("halted", f"workflow walk stalled at phase {phase!r}")
    if not exited:
        return ("halted", "workflow walk produced no completed phase")
    unverified = [e for e in exited if not e.get("verified")]
    if unverified:
        e = unverified[-1]
        return ("halted",
                f"gate {e.get('gate')!r} did not verify at phase {e.get('phase')!r}")
    return ("complete", None)


def _escalated_reason(root: Path, unit_id: str) -> str | None:
    """The reason a unit was escalated to a human, or None if it never was.

    Escalation is a one-way terminal state (`unit.escalated`): distinct from a
    retryable `stall`, it means the bounded fix loop is exhausted and a human is
    required. Once journaled it BLOCKS close / receipt(result) — an escalated unit
    can never be silently marked done, exactly like a halted workflow walk. Fail-soft:
    a malformed journal reads as not-escalated rather than raising."""
    reason: str | None = None
    for e in journal.read(root):
        if e.get("unit") == unit_id and e.get("event") == "unit.escalated":
            reason = e.get("reason") or "unit escalated for human review"
    return reason


def escalate_unit(root: str | Path, unit_id: str, reason: str | None = None) -> dict:
    """Record that a unit's bounded fix loop is exhausted and it NEEDS A HUMAN.

    This is the explicit escalation terminal — a one-way state that is neither a
    silent stall nor a retryable block. It journals `unit.escalated` (with `reason`)
    so the unit surfaces in its own `escalated` bucket and can no longer be closed
    or receipted `result` until a human intervenes."""
    root = Path(root).resolve()
    reason = (reason or "").strip() or "unit escalated for human review"
    journal.append(root, "unit.escalated", unit=unit_id, status="escalated", reason=reason)
    return {"status": "escalated", "unit": unit_id, "reason": reason}


def close_unit(root: str | Path, unit_id: str | None = None, note: str | None = None) -> dict:
    root = Path(root).resolve()
    target = unit_id
    if target is None:
        open_u = journal.open_unit(root)
        if open_u is None:
            return {"status": "no-open-unit"}
        target = open_u["unit"]
    esc = _escalated_reason(root, target)
    if esc is not None:
        journal.append(root, "unit.note", unit=target, kind="close-rejected",
                       reason=esc, escalated=True)
        return {"status": "blocked", "unit": target, "reason": esc, "escalated": True}
    walk = _workflow_close_status(root, target)
    if walk is not None and walk[0] == "halted":
        journal.append(root, "unit.note", unit=target, kind="close-rejected",
                       reason=walk[1])
        return {"status": "blocked", "unit": target, "reason": walk[1]}
    journal.append(root, "unit.done", unit=target, outcome="result", status="complete", note=note)
    return {"status": "closed", "unit": target}


def record_receipt(root: str | Path, unit_id: str, outcome: str = "result",
                   note: str | None = None) -> dict:
    root = Path(root).resolve()
    if outcome == "result":
        esc = _escalated_reason(root, unit_id)
        if esc is not None:
            journal.append(root, "unit.note", unit=unit_id, kind="close-rejected",
                           reason=esc, escalated=True)
            return {"status": "blocked", "unit": unit_id, "reason": esc, "escalated": True}
        journal.append(root, "unit.done", unit=unit_id, outcome="result",
                       status="complete", note=note)
    elif outcome == "stall":
        journal.append(root, "unit.stalled", unit=unit_id, outcome="stall",
                       status="blocked", surfaced=[note] if note else [], note=note)
    else:
        raise ValueError(f"outcome must be 'result' or 'stall', got {outcome!r}")
    return {"status": "recorded", "unit": unit_id, "outcome": outcome}


def _stub_unit(situation: Situation) -> Unit:
    return Unit(id="preview", situation=situation)


def _gen_id(task_kind: str) -> str:
    return f"{task_kind}-{int(time.time())}-{int(time.time() * 1000) % 1000:03d}"


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
