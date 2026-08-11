#!/usr/bin/env python3
"""Tests for the background (async) cascade so the MCP `plan` call can't wedge on a long DAG of
spawns: `schedule.run_dag(resume=True)` (skip already-done units), `conduct.run_tasklist_async`
(background launch + fast return + idempotency), and `conduct.plan_status` (journal-folded progress).
"""
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

PRAXIS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PRAXIS))
sys.path.insert(0, str(PRAXIS / "scripts"))

import conduct as conduct_engine  # noqa: E402
import journal  # noqa: E402
from plan import TaskSpec, build_units, plan_tasks  # noqa: E402
from providers import NullProvider  # noqa: E402
from run import InlineExecutor, Plan, Receipt  # noqa: E402
from schedule import run_dag  # noqa: E402


class TempRoot:
    def __enter__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / ".praxis").mkdir()
        return self.root

    def __exit__(self, *a):
        self._tmp.cleanup()


class RunDagResumeTest(unittest.TestCase):
    def test_resume_skips_already_done_unit(self):
        with TempRoot() as root:
            units = build_units([TaskSpec(intent="a", id="a"),
                                 TaskSpec(intent="b", id="b", depends_on=["a"])])
            # a already concluded in a prior (interrupted) run
            journal.append(root, "unit.done", unit="a", outcome="result", status="complete")
            ran = []
            ex = InlineExecutor(lambda u, c: ran.append(u.id) or Receipt(outcome="result"))
            out = run_dag(Plan(units=units), NullProvider(), ex, root, concurrency=1, resume=True)
            self.assertEqual(ran, ["b"])                       # a was NOT re-dispatched
            results = {r["unit"]: r for r in out["results"]}
            self.assertTrue(results["a"].get("resumed"))       # a taken from the log
            self.assertEqual(results["b"]["outcome"], "result")

    def test_resume_cascades_a_prior_stall(self):
        with TempRoot() as root:
            units = build_units([TaskSpec(intent="a", id="a"),
                                 TaskSpec(intent="b", id="b", depends_on=["a"])])
            journal.append(root, "unit.stalled", unit="a", outcome="stall", status="blocked")
            ran = []
            ex = InlineExecutor(lambda u, c: ran.append(u.id) or Receipt(outcome="result"))
            out = run_dag(Plan(units=units), NullProvider(), ex, root, concurrency=1, resume=True)
            self.assertEqual(ran, [])                          # a stalled → b blocked, nothing ran
            results = {r["unit"]: r for r in out["results"]}
            self.assertEqual(results["b"]["outcome"], "stall")

    def test_no_resume_runs_everything(self):
        with TempRoot() as root:
            units = build_units([TaskSpec(intent="a", id="a")])
            journal.append(root, "unit.done", unit="a", outcome="result", status="complete")
            ran = []
            ex = InlineExecutor(lambda u, c: ran.append(u.id) or Receipt(outcome="result"))
            run_dag(Plan(units=units), NullProvider(), ex, root, concurrency=1, resume=False)
            self.assertEqual(ran, ["a"])                       # default path re-runs (unchanged)


class RunTasklistAsyncTest(unittest.TestCase):
    def _wait_done(self, root, timeout=5):
        key = str(Path(root).resolve())
        t0 = time.time()
        while time.time() - t0 < timeout:
            run = conduct_engine._RUNS.get(key)
            if run and run.get("done"):
                return True
            time.sleep(0.01)
        return False

    def test_returns_running_immediately_then_completes(self):
        with TempRoot() as root:
            done = []
            ex = InlineExecutor(lambda u, c: done.append(u.id) or Receipt(outcome="result"))
            out = conduct_engine.run_tasklist_async(
                root, [{"intent": "a", "id": "a"}, {"intent": "b", "id": "b", "depends_on": ["a"]}],
                executor=ex)
            self.assertEqual(out["status"], "running")
            self.assertEqual(out["plan"]["units"], ["a", "b"])
            self.assertTrue(self._wait_done(root), "background cascade did not finish")
            self.assertEqual(sorted(done), ["a", "b"])
            fold = journal.fold(root)
            self.assertTrue(all(fold["units"][u]["state"] == "done" for u in ("a", "b")))

    def test_second_call_while_running_is_rejected(self):
        with TempRoot() as root:
            gate = threading.Event()

            def handler(u, c):
                gate.wait(timeout=3)                           # hold the cascade in flight
                return Receipt(outcome="result")

            ex = InlineExecutor(handler)
            first = conduct_engine.run_tasklist_async(root, [{"intent": "a", "id": "a"}], executor=ex)
            self.assertEqual(first["status"], "running")
            second = conduct_engine.run_tasklist_async(root, [{"intent": "a", "id": "a"}], executor=ex)
            self.assertEqual(second["status"], "already-running")
            gate.set()
            self.assertTrue(self._wait_done(root))


class PlanStatusTest(unittest.TestCase):
    def test_no_plan(self):
        with TempRoot() as root:
            self.assertEqual(conduct_engine.plan_status(root)["status"], "no-plan")

    def test_progress_buckets_and_complete(self):
        with TempRoot() as root:
            plan_tasks(root, [TaskSpec(intent="a", id="a"),
                              TaskSpec(intent="b", id="b", depends_on=["a"])])
            st = conduct_engine.plan_status(root)
            self.assertEqual(st["status"], "idle")             # registered, not running, not done
            self.assertEqual(st["progress"]["waiting"], ["a", "b"])
            journal.append(root, "unit.done", unit="a", outcome="result", status="complete")
            journal.append(root, "unit.done", unit="b", outcome="result", status="complete")
            st2 = conduct_engine.plan_status(root)
            self.assertEqual(st2["status"], "complete")
            self.assertEqual(sorted(st2["progress"]["done"]), ["a", "b"])


if __name__ == "__main__":
    unittest.main()
