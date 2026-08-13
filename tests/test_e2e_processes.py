#!/usr/bin/env python3
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
        (self.root / ".praxis" / "config.json").write_text("{}\n")
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

class CloseUnitTest(unittest.TestCase):

    def test_close_unlocks_dependent_and_closes_gate(self):
        with TempRoot() as root:
            conduct_engine.register_plan(root, [
                {"intent": "u1", "id": "u1", "targets": ["u1.py"]},
                {"intent": "u2", "id": "u2", "depends_on": ["u1"], "targets": ["u2.py"]}])

            h1 = conduct_engine.next_handoff(root)
            self.assertEqual(h1["unit"], "u1")
            self.assertEqual(gate.gate_decision(root, str(root / "u1.py"))[0], "allow")

            closed = conduct_engine.close_unit(root)
            self.assertEqual(closed, {"status": "closed", "unit": "u1"})
            self.assertEqual(journal.state_of(root, "u1"), "done")
            self.assertEqual(gate.gate_decision(root, str(root / "u1.py"))[0], "no_unit")

            h2 = conduct_engine.next_handoff(root)
            self.assertEqual(h2["unit"], "u2")
            self.assertEqual(conduct_engine.close_unit(root, unit_id="u2", note="done")["unit"], "u2")
            self.assertEqual(conduct_engine.plan_status(root)["status"], "complete")

    def test_no_open_unit(self):
        with TempRoot() as root:
            self.assertEqual(conduct_engine.close_unit(root), {"status": "no-open-unit"})

class RecordReceiptTest(unittest.TestCase):

    def test_result_unlocks_dependent_then_stall_completes_plan(self):
        with TempRoot() as root:
            import handoff as handoff_mod
            import plan as plan_mod

            conduct_engine.register_plan(root, [
                {"intent": "u1", "id": "u1", "targets": ["u1.py"]},
                {"intent": "u2", "id": "u2", "depends_on": ["u1"], "targets": ["u2.py"]}])

            self.assertEqual(conduct_engine.next_handoff(root)["unit"], "u1")

            self.assertEqual(conduct_engine.record_receipt(root, "u1", "result"),
                             {"status": "recorded", "unit": "u1", "outcome": "result"})
            self.assertEqual(journal.state_of(root, "u1"), "done")

            self.assertEqual(conduct_engine.next_handoff(root)["unit"], "u2")
            conduct_engine.record_receipt(root, "u2", "stall", note="blocked on X")
            self.assertEqual(journal.state_of(root, "u2"), "stalled")
            u2 = journal.fold(root)["units"]["u2"]
            self.assertEqual(u2["surfaced"], ["blocked on X"])

            units = plan_mod.reconstruct_units(root)
            st = handoff_mod.status(root, units)
            self.assertTrue(st["complete"])
            self.assertEqual(len(st["done"]) + len(st["stalled"]), st["total"])
            self.assertIn("u2", st["stalled"])
            self.assertIn("u1", st["done"])

    def test_bogus_outcome_raises(self):
        with TempRoot() as root:
            with self.assertRaises(ValueError):
                conduct_engine.record_receipt(root, "u1", outcome="bogus")

class DetachedWorkerProcessTest(unittest.TestCase):

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
