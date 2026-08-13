#!/usr/bin/env python3
"""A deterministic, engine-run gate actually BLOCKS a workflow walk.

Part B drives run_workflow DIRECTLY (no model, no `claude -p`): a CommandVerifier
bound to a command we control gates the walk on the command's exit code alone.
A FAILING command halts advance; a PASSING command lets the walk proceed. Part C
proves close_unit refuses to certify a workflow unit whose walk halted."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import conduct as conduct_engine  # noqa: E402
import journal  # noqa: E402
import run as R  # noqa: E402
import workflow as W  # noqa: E402
from situation import Situation  # noqa: E402
from workflow_run import run_workflow  # noqa: E402


def _sit(**over):
    kw = dict(task_kind="change", intent="do the thing", subject="coding")
    kw.update(over)
    return Situation(**kw)


def _pass_handler(unit, composed):
    # every phase's own execution succeeds; only the engine-run gate can halt us
    return R.Receipt(outcome="result", evidence={"produces": composed.get("phase")})


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


class GateBlocksWalkTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".praxis").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def _events(self, event):
        return [e for e in journal.read(self.root) if e.get("event") == event]

    def test_failing_command_halts_walk_before_B(self):
        # The command we control (`false`, exit 1) is wired to the workflow gates
        # exactly as run_unit wires them (does-it AND regression -> the project's
        # test command). does-it guards A's outgoing carry edge; it fails, so the
        # walk cannot advance to B.
        verifiers = R._workflow_verifiers(R.verifier_from_test_cmd("false"))
        self.assertIn("regression", verifiers)  # regression IS wired to the command
        out = run_workflow(self.root, R.Unit("u1", _sit()), _carry2(), [],
                           R.InlineExecutor(_pass_handler), verifiers=verifiers)

        walked = out["phases"]
        self.assertEqual(walked, ["A"])  # HALTS before B

        exited = self._events("phase.exited")
        self.assertEqual([e["phase"] for e in exited], ["A"])
        self.assertFalse(exited[0]["verified"])          # gate said no

        entered = [e["phase"] for e in self._events("phase.entered")]
        self.assertNotIn("B", entered)                   # B never entered

    def test_passing_command_lets_walk_advance(self):
        verifiers = R._workflow_verifiers(R.verifier_from_test_cmd("true"))
        out = run_workflow(self.root, R.Unit("u1", _sit()), _carry2(), [],
                           R.InlineExecutor(_pass_handler), verifiers=verifiers)

        walked = out["phases"]
        self.assertEqual(walked, ["A", "B"])             # advances A -> B

        exited = self._events("phase.exited")
        self.assertTrue(all(e["verified"] for e in exited))

    def test_regression_carry_gate_specifically_blocks_advance(self):
        # Isolate the `carry`->regression gate: wire ONLY regression. A is entered
        # via `create` (does-it, unwired -> verified) and advances; B is entered
        # via `carry`, so B's gate is regression -> the failing command halts the
        # walk at B, before C.
        fail = R.verifier_from_test_cmd("false")
        out = run_workflow(self.root, R.Unit("u1", _sit()), _carry3(), [],
                           R.InlineExecutor(_pass_handler),
                           verifiers={"regression": fail})
        self.assertEqual(out["phases"], ["A", "B"])      # halts at B, before C

        exited = {e["phase"]: e for e in self._events("phase.exited")}
        self.assertEqual(exited["A"]["gate"], "does-it")
        self.assertTrue(exited["A"]["verified"])
        self.assertEqual(exited["B"]["gate"], "regression")
        self.assertFalse(exited["B"]["verified"])        # regression gate blocked
        self.assertNotIn("C", [e["phase"] for e in self._events("phase.entered")])


class CloseUnitGatesWorkflowTest(unittest.TestCase):
    """Part C: close_unit refuses to certify a workflow unit whose walk halted."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".praxis").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def _events(self, event):
        return [e for e in journal.read(self.root) if e.get("event") == event]

    def test_close_rejected_when_walk_halted(self):
        verifiers = R._workflow_verifiers(R.verifier_from_test_cmd("false"))
        run_workflow(self.root, R.Unit("u1", _sit()), _carry2(), [],
                     R.InlineExecutor(_pass_handler), verifiers=verifiers)
        # the walk halted at A (gate failed); certification must be refused
        out = conduct_engine.close_unit(self.root, unit_id="u1")
        self.assertEqual(out["status"], "blocked")
        self.assertIn("verify", out["reason"])
        self.assertFalse(self._events("unit.done"))      # NOT certified

    def test_close_allowed_when_walk_completed(self):
        verifiers = R._workflow_verifiers(R.verifier_from_test_cmd("true"))
        run_workflow(self.root, R.Unit("u1", _sit()), _carry2(), [],
                     R.InlineExecutor(_pass_handler), verifiers=verifiers)
        out = conduct_engine.close_unit(self.root, unit_id="u1")
        self.assertEqual(out["status"], "closed")
        self.assertEqual(out["unit"], "u1")
        done = self._events("unit.done")
        self.assertEqual(len(done), 1)

    def test_non_workflow_unit_close_ungated(self):
        # a single-dispatch unit has no phase events -> close behaves as before
        journal.append(self.root, "unit.proposed", unit="u9", unit_of_work="x")
        journal.append(self.root, "unit.framed", unit="u9", unit_of_work="x")
        out = conduct_engine.close_unit(self.root, unit_id="u9")
        self.assertEqual(out["status"], "closed")


if __name__ == "__main__":
    unittest.main()
