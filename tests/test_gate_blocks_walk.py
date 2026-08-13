#!/usr/bin/env python3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import conduct as conduct_engine  # noqa: E402
import journal  # noqa: E402
import phase_walk  # noqa: E402
import run as R  # noqa: E402
import workflow as W  # noqa: E402
from situation import Situation  # noqa: E402

def _sit(**over):
    kw = dict(task_kind="change", intent="do the thing", subject="coding")
    kw.update(over)
    return Situation(**kw)

def _carry2():
    a = W.Phase("A", stance="convergent")
    b = W.Phase("B", stance="convergent")
    return W.Workflow("carry2", [a, b],
                      edges=[("A", "B", "pass", W.EdgeType.carry)])

def _carry3():
    a = W.Phase("A", stance="convergent")
    b = W.Phase("B", stance="convergent")
    c = W.Phase("C", stance="convergent")
    return W.Workflow("carry3", [a, b, c], edges=[
        ("A", "B", "pass", W.EdgeType.carry),
        ("B", "C", "pass", W.EdgeType.carry),
    ])

class _Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".praxis").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def _events(self, event):
        return [e for e in journal.read(self.root) if e.get("event") == event]

    def _walk(self, wf, verifiers, max_steps=10):
        unit = R.Unit("u1", _sit())
        visited = []
        for _ in range(max_steps):
            step = phase_walk.next_phase(self.root, unit, workflow=wf)
            if step["status"] != "phase":
                return visited, step["status"]
            name = step["phase"]
            rec = phase_walk.record_phase(self.root, unit, name,
                                          {"produces": name},
                                          verifiers=verifiers, workflow=wf)
            visited.append(name)
            if not rec["advance"]:
                return visited, "halted"
        return visited, "loop"

class GateBlocksWalkTest(_Base):
    def test_failing_command_halts_walk_before_B(self):
        verifiers = R._workflow_verifiers(R.verifier_from_test_cmd("false"))
        self.assertIn("regression", verifiers)
        visited, status = self._walk(_carry2(), verifiers)

        self.assertEqual(visited, ["A"])
        self.assertEqual(status, "halted")

        exited = self._events("phase.exited")
        self.assertEqual([e["phase"] for e in exited], ["A"])
        self.assertFalse(exited[0]["verified"])

    def test_passing_command_lets_walk_advance(self):
        verifiers = R._workflow_verifiers(R.verifier_from_test_cmd("true"))
        visited, status = self._walk(_carry2(), verifiers)

        self.assertEqual(visited, ["A", "B"])
        self.assertEqual(status, "complete")

        exited = self._events("phase.exited")
        self.assertTrue(all(e["verified"] for e in exited))

    def test_regression_carry_gate_specifically_blocks_advance(self):
        fail = R.verifier_from_test_cmd("false")
        visited, status = self._walk(_carry3(), {"regression": fail})
        self.assertEqual(visited, ["A", "B"])
        self.assertEqual(status, "halted")

        exited = {e["phase"]: e for e in self._events("phase.exited")}
        self.assertEqual(exited["A"]["gate"], "does-it")
        self.assertTrue(exited["A"]["verified"])
        self.assertEqual(exited["B"]["gate"], "regression")
        self.assertFalse(exited["B"]["verified"])

class CloseUnitGatesWorkflowTest(_Base):

    def test_close_rejected_when_walk_halted(self):
        verifiers = R._workflow_verifiers(R.verifier_from_test_cmd("false"))
        self._walk(_carry2(), verifiers)

        out = conduct_engine.close_unit(self.root, unit_id="u1")
        self.assertEqual(out["status"], "blocked")
        self.assertIn("verify", out["reason"])
        self.assertFalse(self._events("unit.done"))

    def test_close_allowed_when_walk_completed(self):
        verifiers = R._workflow_verifiers(R.verifier_from_test_cmd("true"))
        self._walk(_carry2(), verifiers)
        out = conduct_engine.close_unit(self.root, unit_id="u1")
        self.assertEqual(out["status"], "closed")
        self.assertEqual(out["unit"], "u1")
        done = self._events("unit.done")
        self.assertEqual(len(done), 1)

    def test_non_workflow_unit_close_ungated(self):

        journal.append(self.root, "unit.proposed", unit="u9", unit_of_work="x")
        journal.append(self.root, "unit.framed", unit="u9", unit_of_work="x")
        out = conduct_engine.close_unit(self.root, unit_id="u9")
        self.assertEqual(out["status"], "closed")

if __name__ == "__main__":
    unittest.main()
