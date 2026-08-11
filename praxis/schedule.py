#!/usr/bin/env python3
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import journal
from contributors import HookContext, fire, gather
from run import Plan, Unit, run_unit
from situation import Situation


def _validate(units: dict[str, Unit]) -> None:
    for u in units.values():
        for d in u.depends_on:
            if d not in units:
                raise ValueError(f"unit '{u.id}' depends on unknown unit '{d}'")
    indeg = {uid: len(u.depends_on) for uid, u in units.items()}
    ready = [uid for uid, n in indeg.items() if n == 0]
    seen = 0
    dependents: dict[str, list[str]] = {uid: [] for uid in units}
    for u in units.values():
        for d in u.depends_on:
            dependents[d].append(u.id)
    while ready:
        uid = ready.pop()
        seen += 1
        for dep in dependents[uid]:
            indeg[dep] -= 1
            if indeg[dep] == 0:
                ready.append(dep)
    if seen != len(units):
        cyclic = sorted(uid for uid, n in indeg.items() if n > 0)
        raise ValueError(f"dependency cycle among units: {cyclic}")


def reflexive_route(root: Path, plan: Plan, contributors, routing_situation: Situation | None = None) -> dict:
    if routing_situation is None:
        edges = sum(len(u.depends_on) for u in plan.units)
        routing_situation = Situation(
            task_kind="change", subject="process", phase="convergent",
            intent=f"schedule {len(plan.units)} unit(s) across {edges} dependency edge(s)",
            suggested_kind="orchestrate", fit="clean")
    composed = gather(contributors, routing_situation, root=root)
    journal.append(root, "conductor.route", units=len(plan.units),
                   gap_surfaced=composed.get("gap_surfaced"),
                   routed_kind=composed.get("routed_kind"), note=composed.get("note"))
    return composed


def _blocked(root: Path, unit: Unit, failed_deps: list[str]) -> dict:
    journal.append(root, "unit.proposed", unit=unit.id, unit_of_work=unit.unit_of_work,
                   situation=unit.situation.to_dict())
    surfaced = [f"dependency '{d}' did not complete" for d in failed_deps]
    journal.append(root, "unit.stalled", unit=unit.id, outcome="stall", status="blocked",
                   surfaced=surfaced, note="blocked: unmet dependency")
    return {"unit": unit.id, "unit_of_work": unit.unit_of_work, "outcome": "stall",
            "status": "blocked", "verified": None, "attempts": 0, "defects": surfaced,
            "blocked_on": failed_deps, "receipt": None}


def _resumed_result(unit: Unit, fold: dict) -> dict:
    u = fold["units"].get(unit.id, {})
    st = u.get("state")
    outcome = u.get("outcome") or ("result" if st == "done" else "stall")
    return {"unit": unit.id, "unit_of_work": unit.unit_of_work, "outcome": outcome,
            "status": u.get("status"), "verified": (st == "done") or None, "attempts": None,
            "defects": u.get("surfaced") or [], "gap_surfaced": None,
            "routed_kind": u.get("last", {}).get("routed_kind"), "receipt": None, "resumed": True}


def run_dag(plan: Plan, contributors, executor, root: Path, verifier=None,
            concurrency: int | None = None, max_retries: int | None = None,
            routing_situation: Situation | None = None, policy=None, resume: bool = False) -> dict:
    import policy as policy_mod
    pol = policy or policy_mod.load_policy(root)
    if concurrency is None:
        concurrency = pol.concurrency
    if max_retries is None:
        max_retries = pol.max_retries
    if concurrency < 1:
        raise ValueError("concurrency must be >= 1")
    if pol.verify_required and verifier is None:
        raise ValueError("policy sets verify_required but no verifier was supplied")
    units = {u.id: u for u in plan.units}
    if len(units) != len(plan.units):
        raise ValueError("duplicate unit ids in plan")
    _validate(units)

    routing = reflexive_route(root, plan, contributors, routing_situation)

    state: dict[str, str] = {}
    results: dict[str, dict] = {}
    pending = list(plan.units)

    if resume:
        fold = journal.fold(root)
        for u in list(pending):
            st = fold["units"].get(u.id, {}).get("state")
            if st in ("done", "stalled"):
                state[u.id] = st
                results[u.id] = _resumed_result(u, fold)
                pending.remove(u)

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        while pending:
            wave = [u for u in pending if all(d in state for d in u.depends_on)]
            if not wave:
                raise RuntimeError(f"deadlock: {[u.id for u in pending]} have unmet dependencies")

            runnable = []
            for u in wave:
                failed = [d for d in u.depends_on if state.get(d) != "done"]
                if failed:
                    results[u.id] = _blocked(root, u, failed)
                    state[u.id] = "blocked"
                else:
                    for d in u.depends_on:
                        journal.append(root, "unit.depends_on", unit=u.id, depends_on=d)
                    runnable.append(u)

            futures = {pool.submit(run_unit, root, u, contributors, executor, verifier, max_retries): u
                       for u in runnable}
            for fut in as_completed(futures):
                u = futures[fut]
                res = fut.result()
                results[u.id] = res
                state[u.id] = "stalled" if res["outcome"] == "stall" else "done"

            for u in wave:
                pending.remove(u)

    fire(contributors, "close", HookContext(root=root, step="close"))
    import views
    return {"results": [results[u.id] for u in plan.units],
            "summary": journal.fold(root)["summary"], "routing": routing,
            "cost": views.cost(root)}
