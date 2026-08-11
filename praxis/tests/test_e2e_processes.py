#!/usr/bin/env python3
"""End-to-end process tests: drive the conductor's whole workflows through its public entries and
read the outcome back off the journal — the inline PULL process (register → next_handoff → done),
the background CASCADE process (async → stall cascade → plan_status complete), and RESUME after an
interruption. These exercise the real wiring (plan → schedule → handoff → journal → views), not a
single unit."""
import sys
import tempfile
import time
import unittest
from pathlib import Path

PRAXIS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PRAXIS / "scripts"))
sys.path.insert(0, str(PRAXIS))

import conduct as conduct_engine  # noqa: E402
import gate  # noqa: E402
import journal  # noqa: E402
from providers import NullProvider  # noqa: E402
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


def _wait_done(root, timeout=15):
    key = str(Path(root).resolve())
    t0 = time.time()
    while time.time() - t0 < timeout:
        run = conduct_engine._RUNS.get(key)
        if run and run.get("done"):
            return True
        time.sleep(0.01)
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

            # nothing framed yet ⇒ the gate refuses an edit
            verdict, _ = gate.gate_decision(root, str(root / "types.py"))
            self.assertIn(verdict, ("no_unit", "deny"))

            order = []
            while True:
                h = conduct_engine.next_handoff(root)
                if h["status"] != "ready":
                    break
                order.append(h["unit"])
                # the pull framed THIS unit and recorded the read ⇒ the gate now allows its target
                v, _ = gate.gate_decision(root, str(root / target[h["unit"]]))
                self.assertEqual(v, "allow")
                journal.append(root, "unit.done", unit=h["unit"], outcome="result",
                               status="complete")

            self.assertEqual(order, ["types", "solver", "tests"])
            self.assertEqual(conduct_engine.plan_status(root)["status"], "complete")
            # the fit==none unit surfaced a mintable vocabulary gap along the way
            self.assertTrue(any(g["suggested"] == "scaffold-tests" for g in journal.gaps(root)))


class CascadeProcessTest(unittest.TestCase):
    """The background cascade process: hand over a DAG, it runs in dependency order to completion; a
    unit that stalls blocks its dependents, and the whole run is recoverable from the journal."""

    def test_async_cascade_with_stall_cascade(self):
        with TempRoot() as root:
            def handler(u, c):
                if u.id == "provision":
                    return Receipt(outcome="stall", status="blocked", surfaced=["no credentials"])
                return Receipt(outcome="result")

            tasks = [
                {"intent": "schema", "id": "schema"},
                {"intent": "api", "id": "api", "depends_on": ["schema"]},
                {"intent": "provision infra", "id": "provision", "depends_on": ["api"]},
                {"intent": "deploy", "id": "deploy", "depends_on": ["provision"]},
            ]
            out = conduct_engine.run_tasklist_async(root, tasks, executor=InlineExecutor(handler),
                                                    provider=NullProvider(), concurrency=1)
            self.assertEqual(out["status"], "running")
            self.assertTrue(_wait_done(root), "cascade did not finish")

            st = conduct_engine.plan_status(root)
            self.assertEqual(st["status"], "complete")
            self.assertEqual(set(st["progress"]["done"]), {"schema", "api"})
            self.assertEqual(set(st["progress"]["stalled"]), {"provision", "deploy"})

            fold = journal.fold(root)
            self.assertEqual(fold["units"]["deploy"]["state"], "stalled")  # cascaded block
            self.assertIn("cost", st)


class ResumeProcessTest(unittest.TestCase):
    """Resume after interruption: a plan whose leaf already finished re-runs only the remainder."""

    def test_resume_runs_only_the_remaining_units(self):
        with TempRoot() as root:
            tasks = [{"intent": "a", "id": "a"},
                     {"intent": "b", "id": "b", "depends_on": ["a"]},
                     {"intent": "c", "id": "c", "depends_on": ["b"]}]
            conduct_engine.register_plan(root, tasks)
            journal.append(root, "unit.done", unit="a", outcome="result", status="complete")

            ran = []
            ex = InlineExecutor(lambda u, c: ran.append(u.id) or Receipt(outcome="result"))
            out = conduct_engine.run_tasklist_async(root, tasks, executor=ex,
                                                    provider=NullProvider(), concurrency=1)
            self.assertEqual(out["status"], "running")
            self.assertTrue(_wait_done(root))
            self.assertEqual(ran, ["b", "c"])                 # 'a' resumed from the log, not re-run
            self.assertEqual(conduct_engine.plan_status(root)["status"], "complete")


if __name__ == "__main__":
    unittest.main()
