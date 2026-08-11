#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from typing import Callable

import journal
import schedule
from run import Plan, Unit, Verdict, run_unit, verifier_from_test_cmd
from situation import Situation


def _default_owner(defect: str) -> dict:
    return {"intent": f"fix: {defect}", "targets": []}


def barrier_from_test_cmd(test_cmd: str | None) -> Callable[[], Verdict]:
    verifier = verifier_from_test_cmd(test_cmd)
    if verifier is None:
        return lambda: Verdict(verified=True)
    return lambda: verifier.verify(None, None, None)


def run_orchestrated(root: Path, units, contributors, executor,
                     barrier: Callable[[], Verdict], *, fix_rounds: int = 3,
                     defect_owner: Callable[[str], dict] | None = None,
                     resume: bool = False, concurrency: int | None = None,
                     max_retries: int | None = None) -> dict:
    result = schedule.run_dag(Plan(units), contributors, executor, root, verifier=None,
                              resume=resume, concurrency=concurrency, max_retries=max_retries)
    stalled = [r["unit"] for r in result["results"] if r["outcome"] == "stall"]
    if stalled:
        journal.append(root, "orchestration.escalated", reason="unit-stalled", units=stalled)
        return {"status": "escalated", "reason": "unit-stalled", "attempts": 0,
                "units": stalled, "fanout": result}

    own = defect_owner or _default_owner
    for attempt in range(fix_rounds + 1):
        verdict = barrier()
        if verdict.verified:
            journal.append(root, "orchestration.closed", attempt=attempt)
            return {"status": "complete", "reason": None, "attempts": attempt + 1,
                    "escalation": None, "fanout": result}
        journal.append(root, "orchestration.barrier_failed", attempt=attempt,
                       defects=verdict.defects)
        for i, d in enumerate(verdict.defects or []):
            spec = own(d)
            fu = Unit(id=f"fix-{attempt}-{i}", situation=Situation(
                task_kind="change", intent=spec["intent"], subject="coding",
                targets=spec.get("targets", []), root=str(root)))
            fr = run_unit(root, fu, contributors, executor)
            fit = (fr.get("receipt") or {}).get("evidence") or {}
            if fr["outcome"] == "stall" or fit.get("phase_fit") in ("loose", "none"):
                journal.append(root, "orchestration.escalated", reason="structural-misfit",
                               fix_unit=fu.id)
                return {"status": "escalated", "reason": "structural-misfit",
                        "attempts": attempt + 1, "fix_unit": fu.id, "fanout": result}

    journal.append(root, "orchestration.escalated", reason="loop-exhausted")
    return {"status": "escalated", "reason": "loop-exhausted", "attempts": fix_rounds + 1,
            "fanout": result}
