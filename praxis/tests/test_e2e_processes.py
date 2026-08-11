#!/usr/bin/env python3
"""End-to-end process tests: drive the conductor's whole workflows through its public entries and
read the outcome back off the journal — the inline PULL process (register → next_handoff → done),
the background CASCADE process (async → stall cascade → plan_status complete), and RESUME after an
interruption. These exercise the real wiring (plan → schedule → handoff → journal → views), not a
single unit."""
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

PRAXIS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PRAXIS / "scripts"))
sys.path.insert(0, str(PRAXIS))

import cascade  # noqa: E402
import conduct as conduct_engine  # noqa: E402
import gate  # noqa: E402
import journal  # noqa: E402
from run import InlineExecutor, Receipt  # noqa: E402


class TempRoot:
    def __enter__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / ".praxis").mkdir()
        (self.root / ".praxis" / "config.md").write_text("root: e2e\n")
        return self.root

    def __exit__(self, *a):
        self._tmp.cleanup()


def _wait_worker_done(root, timeout=20):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if cascade.is_running(root) is None and conduct_engine.plan_status(root)["status"] != "idle":
            return True
        time.sleep(0.02)
    return False


class InlinePullProcessTest(unittest.TestCase):
    """The 'implement it yourself' process: register a DAG, pull each ready unit into context (the
    pull opens the edit gate for it), advance as each is finished, until the plan is complete."""

    def test_register_pull_advance_to_complete(self):
        with TempRoot() as root:
            target = {"types": "types.py", "solver": "solver.py", "tests": "test_solver.py"}
            tasks = [
                {"intent": "define the constraint types", "id": "types", "task_kind": "create",
                 "targets": ["types.py"]},
                {"intent": "implement the solver", "id": "solver", "depends_on": ["types"],
                 "targets": ["solver.py"]},
                {"intent": "cover the solver", "id": "tests", "depends_on": ["solver"],
                 "targets": ["test_solver.py"], "suggested_kind": "scaffold-tests", "fit": "none"},
            ]
            self.assertEqual(conduct_engine.register_plan(root, tasks)["status"], "registered")

            verdict, _ = gate.gate_decision(root, str(root / "types.py"))
            self.assertIn(verdict, ("no_unit", "deny"))

            order = []
            while True:
                h = conduct_engine.next_handoff(root)
                if h["status"] != "ready":
                    break
                order.append(h["unit"])
                v, _ = gate.gate_decision(root, str(root / target[h["unit"]]))
                self.assertEqual(v, "allow")
                journal.append(root, "unit.done", unit=h["unit"], outcome="result",
                               status="complete")

            self.assertEqual(order, ["types", "solver", "tests"])
            self.assertEqual(conduct_engine.plan_status(root)["status"], "complete")
            self.assertTrue(any(g["suggested"] == "scaffold-tests" for g in journal.gaps(root)))


class CascadeProcessTest(unittest.TestCase):
    """The cascade process (worker core, in-process): a DAG runs in dependency order to completion; a
    unit that stalls blocks its dependents, and the whole run is recoverable from the journal."""

    def test_cascade_with_stall_cascade(self):
        with TempRoot() as root:
            def handler(u, c):
                if u.id == "provision":
                    return Receipt(outcome="stall", status="blocked", surfaced=["no credentials"])
                return Receipt(outcome="result")

            conduct_engine.register_plan(root, [
                {"intent": "schema", "id": "schema"},
                {"intent": "api", "id": "api", "depends_on": ["schema"]},
                {"intent": "provision infra", "id": "provision", "depends_on": ["api"]},
                {"intent": "deploy", "id": "deploy", "depends_on": ["provision"]},
            ])
            cascade.run_cascade(root, executor=InlineExecutor(handler), contributors=[],
                                concurrency=1)

            st = conduct_engine.plan_status(root)
            self.assertEqual(st["status"], "complete")
            self.assertEqual(set(st["progress"]["done"]), {"schema", "api"})
            self.assertEqual(set(st["progress"]["stalled"]), {"provision", "deploy"})
            self.assertEqual(journal.fold(root)["units"]["deploy"]["state"], "stalled")
            self.assertIn("cost", st)


class DetachedWorkerProcessTest(unittest.TestCase):
    """The durable 'hand off and come back later' process: a real detached worker PROCESS runs the
    plan, survives independently, and the run is observed by reattaching through plan_status. The
    worker uses a fake executor (PRAXIS_CASCADE_FAKE) so no child is spawned and nothing is spent."""

    def test_detached_cascade_runs_to_completion(self):
        with TempRoot() as root:
            os.environ["PRAXIS_CASCADE_FAKE"] = "1"
            try:
                out = conduct_engine.run_tasklist_detached(
                    root, [{"intent": "a", "id": "a"},
                           {"intent": "b", "id": "b", "depends_on": ["a"]}])
                self.assertEqual(out["status"], "running")
                self.assertTrue(out["detached"])
                self.assertTrue(_wait_worker_done(root), "detached worker did not finish")
                st = conduct_engine.plan_status(root)
                self.assertEqual(st["status"], "complete")
                self.assertEqual(sorted(st["progress"]["done"]), ["a", "b"])
            finally:
                os.environ.pop("PRAXIS_CASCADE_FAKE", None)


class ResumeProcessTest(unittest.TestCase):
    """Resume after interruption: a plan whose leaf already finished re-runs only the remainder."""

    def test_resume_runs_only_the_remaining_units(self):
        with TempRoot() as root:
            conduct_engine.register_plan(root, [{"intent": "a", "id": "a"},
                                                {"intent": "b", "id": "b", "depends_on": ["a"]},
                                                {"intent": "c", "id": "c", "depends_on": ["b"]}])
            journal.append(root, "unit.done", unit="a", outcome="result", status="complete")
            ran = []
            ex = InlineExecutor(lambda u, c: ran.append(u.id) or Receipt(outcome="result"))
            cascade.run_cascade(root, executor=ex, contributors=[], concurrency=1)
            self.assertEqual(ran, ["b", "c"])
            self.assertEqual(conduct_engine.plan_status(root)["status"], "complete")


if __name__ == "__main__":
    unittest.main()
