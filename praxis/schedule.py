#!/usr/bin/env python3
"""schedule — the DAG scheduler, concurrency cap, and reflexive routing (P6 of
docs/CONDUCTOR-PLAN.md).

`run_dag` generalizes the linear `run` (run.py): units declare `depends_on` edges, and the
conductor schedules them in dependency order, running each ready wave in parallel up to a
concurrency cap ("parallel-then-verify" — every unit still passes the same verification gate from
run_unit). A unit whose dependency did not complete is not run; it is surfaced as a blocked stall,
and that block cascades to its own dependents.

Reflexive routing: before scheduling, the conductor consults the judgment provider about its OWN
routing move — the same `providers.consult` hook it applies to a unit is applied to the conductor's
decision, so the gap detector fires on the conductor's vocabulary too (docs/CONDUCTOR-PLAN.md "The
seam": one hook applied even to the conductor's own moves). It records a `conductor.route` event.

State lives only in the journal: `run_dag` reads dependency outcomes from the events run_unit wrote,
so the schedule is reproducible from the log. journal.append is thread-safe, so the parallel workers
share the one log safely.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import journal
from providers import consult
from run import Plan, Unit, run_unit
from situation import Situation


def _validate(units: dict[str, Unit]) -> None:
    """Reject a plan that names an unknown dependency or contains a cycle — a scheduling bug the
    caller must fix, raised before any unit runs (unlike a runtime stall, which is a first-class
    outcome)."""
    for u in units.values():
        for d in u.depends_on:
            if d not in units:
                raise ValueError(f"unit '{u.id}' depends on unknown unit '{d}'")
    # Kahn's algorithm: peel zero-in-degree nodes; anything left is in a cycle.
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


def reflexive_route(root: Path, plan: Plan, provider, routing_situation: Situation | None = None) -> dict:
    """Consult the provider about the conductor's OWN routing move, then record `conductor.route`.
    The default routing situation describes the schedule shape (unit + edge counts); a caller can
    pass its own — including a `fit` of `loose`/`none`, which surfaces a gap in the conductor's
    routing vocabulary exactly as a unit's would. Degrades cleanly under a null provider."""
    if routing_situation is None:
        edges = sum(len(u.depends_on) for u in plan.units)
        routing_situation = Situation(
            task_kind="change", subject="process", phase="convergent",
            intent=f"schedule {len(plan.units)} unit(s) across {edges} dependency edge(s)",
            suggested_kind="orchestrate", fit="clean")
    composed = consult(provider, routing_situation, root=root)
    journal.append(root, "conductor.route", units=len(plan.units),
                   gap_surfaced=composed.get("gap_surfaced"),
                   routed_kind=composed.get("routed_kind"), note=composed.get("note"))
    return composed


def _blocked(root: Path, unit: Unit, failed_deps: list[str]) -> dict:
    """Record and return the result for a unit that cannot run because a dependency did not
    complete. Proposed then immediately stalled (blocked) — never dispatched."""
    journal.append(root, "unit.proposed", unit=unit.id, unit_of_work=unit.unit_of_work,
                   situation=unit.situation.to_dict())
    surfaced = [f"dependency '{d}' did not complete" for d in failed_deps]
    journal.append(root, "unit.stalled", unit=unit.id, outcome="stall", status="blocked",
                   surfaced=surfaced, note="blocked: unmet dependency")
    return {"unit": unit.id, "unit_of_work": unit.unit_of_work, "outcome": "stall",
            "status": "blocked", "verified": None, "attempts": 0, "defects": surfaced,
            "blocked_on": failed_deps, "receipt": None}


def _resumed_result(unit: Unit, fold: dict) -> dict:
    """Reconstruct a per-unit result for a unit that already concluded in the journal (resume path),
    shaped like `run_unit`'s result so the returned list is uniform."""
    u = fold["units"].get(unit.id, {})
    st = u.get("state")
    outcome = u.get("outcome") or ("result" if st == "done" else "stall")
    return {"unit": unit.id, "unit_of_work": unit.unit_of_work, "outcome": outcome,
            "status": u.get("status"), "verified": (st == "done") or None, "attempts": None,
            "defects": u.get("surfaced") or [], "gap_surfaced": None,
            "routed_kind": u.get("last", {}).get("routed_kind"), "receipt": None, "resumed": True}


def run_dag(plan: Plan, provider, executor, root: Path, verifier=None,
            concurrency: int | None = None, max_retries: int | None = None,
            routing_situation: Situation | None = None, policy=None, resume: bool = False) -> dict:
    """Run a plan honoring `depends_on`, one ready wave at a time, each wave in parallel up to
    `concurrency`. Returns per-unit results (in plan order) + the fold's deliver-vs-stall summary +
    the reflexive-routing result. A unit is `done` only when it delivered AND passed verification;
    a dependency that stalled/blocked blocks its dependents (cascading). `concurrency` and
    `max_retries` default to the root's editable conductor policy (`policy.load_policy`).

    `resume=True` seeds state from the journal: a unit that already reached a terminal state (`done`
    or `stalled`) is NOT re-dispatched — its outcome is taken from the log and its dependents proceed
    (or cascade-block) accordingly. This makes a background cascade restart-safe and idempotent: a
    re-invoked plan continues from where it stopped instead of re-spawning finished units."""
    import policy as policy_mod
    pol = policy or policy_mod.load_policy(root)
    if concurrency is None:
        concurrency = pol.concurrency
    if max_retries is None:
        max_retries = pol.max_retries
    if concurrency < 1:
        raise ValueError("concurrency must be >= 1")
    units = {u.id: u for u in plan.units}
    if len(units) != len(plan.units):
        raise ValueError("duplicate unit ids in plan")
    _validate(units)

    routing = reflexive_route(root, plan, provider, routing_situation)

    state: dict[str, str] = {}          # unit id -> "done" | "stalled" | "blocked"
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
            # A wave = every pending unit whose dependencies have all concluded (any terminal state).
            wave = [u for u in pending if all(d in state for d in u.depends_on)]
            if not wave:
                # Should be unreachable after _validate (no cycles) — guard against a logic slip.
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

            futures = {pool.submit(run_unit, root, u, provider, executor, verifier, max_retries): u
                       for u in runnable}
            for fut in as_completed(futures):
                u = futures[fut]
                res = fut.result()
                results[u.id] = res
                state[u.id] = "stalled" if res["outcome"] == "stall" else "done"

            for u in wave:
                pending.remove(u)

    import views
    return {"results": [results[u.id] for u in plan.units],
            "summary": journal.fold(root)["summary"], "routing": routing,
            "cost": views.cost(root)}
