#!/usr/bin/env python3
"""Tests for the resumable DAG and the detached cascade worker: `schedule.run_dag(resume=True)`
(skip already-done units), `cascade.run_cascade` (the worker core, in-process), the pidfile/flock
liveness + idempotency guard, and `conduct.plan_status` folded from the journal + pidfile."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

PRAXIS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PRAXIS / "scripts"))
sys.path.insert(0, str(PRAXIS))

import cascade  # noqa: E402
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
            journal.append(root, "unit.done", unit="a", outcome="result", status="complete")
            ran = []
            ex = InlineExecutor(lambda u, c: ran.append(u.id) or Receipt(outcome="result"))
            out = run_dag(Plan(units=units), NullProvider(), ex, root, concurrency=1, resume=True)
            self.assertEqual(ran, ["b"])
            results = {r["unit"]: r for r in out["results"]}
            self.assertTrue(results["a"].get("resumed"))
            self.assertEqual(results["b"]["outcome"], "result")

    def test_resume_cascades_a_prior_stall(self):
        with TempRoot() as root:
            units = build_units([TaskSpec(intent="a", id="a"),
                                 TaskSpec(intent="b", id="b", depends_on=["a"])])
            journal.append(root, "unit.stalled", unit="a", outcome="stall", status="blocked")
            ran = []
            ex = InlineExecutor(lambda u, c: ran.append(u.id) or Receipt(outcome="result"))
            out = run_dag(Plan(units=units), NullProvider(), ex, root, concurrency=1, resume=True)
            self.assertEqual(ran, [])
            self.assertEqual({r["unit"]: r["outcome"] for r in out["results"]}["b"], "stall")

    def test_no_resume_runs_everything(self):
        with TempRoot() as root:
            units = build_units([TaskSpec(intent="a", id="a")])
            journal.append(root, "unit.done", unit="a", outcome="result", status="complete")
            ran = []
            ex = InlineExecutor(lambda u, c: ran.append(u.id) or Receipt(outcome="result"))
            run_dag(Plan(units=units), NullProvider(), ex, root, concurrency=1, resume=False)
            self.assertEqual(ran, ["a"])


class RunCascadeCoreTest(unittest.TestCase):
    def test_runs_the_registered_plan(self):
        with TempRoot() as root:
            plan_tasks(root, [TaskSpec(intent="a", id="a"),
                              TaskSpec(intent="b", id="b", depends_on=["a"])])
            ran = []
            ex = InlineExecutor(lambda u, c: ran.append(u.id) or Receipt(outcome="result"))
            out = cascade.run_cascade(root, executor=ex, provider=NullProvider(), concurrency=1)
            self.assertEqual(out["status"], "complete")
            self.assertEqual(ran, ["a", "b"])
            fold = journal.fold(root)
            self.assertTrue(all(fold["units"][u]["state"] == "done" for u in ("a", "b")))

    def test_no_plan_is_reported(self):
        with TempRoot() as root:
            out = cascade.run_cascade(root, executor=InlineExecutor(lambda u, c: Receipt(outcome="result")))
            self.assertEqual(out["status"], "no-plan")


class LivenessGuardTest(unittest.TestCase):
    def test_live_pidfile_reads_running_stale_is_cleaned(self):
        with TempRoot() as root:
            pf = cascade._pidfile(root)
            pf.write_text(json.dumps({"pid": os.getpid(), "started": 1.0}))
            self.assertIsNotNone(cascade.is_running(root))     # our own pid is alive
            pf.write_text(json.dumps({"pid": 2 ** 22, "started": 1.0}))  # almost-certainly-dead pid
            self.assertIsNone(cascade.is_running(root))
            self.assertFalse(pf.exists())                       # stale pidfile removed

    def test_launch_detached_refuses_when_a_worker_is_live(self):
        with TempRoot() as root:
            cascade._pidfile(root).write_text(json.dumps({"pid": os.getpid(), "started": 1.0}))
            out = cascade.launch_detached(root, [{"intent": "a", "id": "a"}])
            self.assertEqual(out["status"], "already-running")
            self.assertEqual(out["pid"], os.getpid())
            # no plan was recorded and no worker spawned
            self.assertFalse([e for e in journal.read(root) if e["event"] == "conductor.plan"])


class PlanStatusTest(unittest.TestCase):
    def test_no_plan(self):
        with TempRoot() as root:
            self.assertEqual(conduct_engine.plan_status(root)["status"], "no-plan")

    def test_idle_then_complete(self):
        with TempRoot() as root:
            plan_tasks(root, [TaskSpec(intent="a", id="a"),
                              TaskSpec(intent="b", id="b", depends_on=["a"])])
            self.assertEqual(conduct_engine.plan_status(root)["status"], "idle")
            for uid in ("a", "b"):
                journal.append(root, "unit.done", unit=uid, outcome="result", status="complete")
            st = conduct_engine.plan_status(root)
            self.assertEqual(st["status"], "complete")
            self.assertEqual(sorted(st["progress"]["done"]), ["a", "b"])

    def test_running_reflects_a_live_worker(self):
        with TempRoot() as root:
            plan_tasks(root, [TaskSpec(intent="a", id="a")])
            cascade._pidfile(root).write_text(json.dumps({"pid": os.getpid(), "started": 9.0}))
            st = conduct_engine.plan_status(root)
            self.assertEqual(st["status"], "running")
            self.assertEqual(st["worker"]["pid"], os.getpid())


if __name__ == "__main__":
    unittest.main()
