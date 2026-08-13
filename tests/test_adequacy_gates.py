#!/usr/bin/env python3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
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

class CoverageVerifierBuilderTest(unittest.TestCase):
    def test_absent_config_returns_none_no_fabricated_pass(self):
        self.assertIsNone(R.coverage_verifier(None, None))
        self.assertIsNone(R.coverage_verifier(None, 80))
        self.assertIsNone(R.coverage_verifier("pytest", None))

    def test_exit_zero_passes_exit_nonzero_fails(self):

        ok = R.coverage_verifier("sh -c 'exit 0'", 80, target="pkg")
        bad = R.coverage_verifier("sh -c 'exit 1'", 80, target="pkg")
        self.assertTrue(ok.verify(None, None, {}).verified)
        self.assertFalse(bad.verify(None, None, {}).verified)

    def test_argv_enforces_threshold_via_exit_code(self):
        v = R.coverage_verifier("pytest", 91, target="pkg")
        argv = v._argv_builder(None, None, {})
        self.assertEqual(argv, ["pytest", "--cov=pkg", "--cov-fail-under=91"])

class _WalkBase(unittest.TestCase):
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

class CoverageGateWalkTest(_WalkBase):
    def test_coverage_pass_advances_walk(self):
        cov = R.coverage_verifier("sh -c 'exit 0'", 80, target="pkg")
        verifiers = R._workflow_verifiers(None, cov)
        visited, status = self._walk(_carry2(), verifiers)
        self.assertEqual(visited, ["A", "B"])
        self.assertEqual(status, "complete")
        self.assertTrue(all(e["verified"] for e in self._events("phase.exited")))

    def test_coverage_under_threshold_halts_walk(self):
        cov = R.coverage_verifier("sh -c 'exit 1'", 80, target="pkg")
        verifiers = R._workflow_verifiers(None, cov)
        visited, status = self._walk(_carry2(), verifiers)
        self.assertEqual(visited, ["A"])
        self.assertEqual(status, "halted")
        exited = self._events("phase.exited")
        self.assertFalse(exited[0]["verified"])

    def test_coverage_prefers_over_bare_test_verifier(self):

        bare_pass = R.verifier_from_test_cmd("true")
        cov_fail = R.coverage_verifier("sh -c 'exit 1'", 80, target="pkg")
        verifiers = R._workflow_verifiers(bare_pass, cov_fail)
        visited, status = self._walk(_carry2(), verifiers)
        self.assertEqual(visited, ["A"])
        self.assertEqual(status, "halted")

class TestCleanupReguardedByCoverageTest(_WalkBase):
    def test_coverage_gate_runs_on_test_cleanup_phase(self):

        cov = R.coverage_verifier("sh -c 'exit 0'", 80, target="pkg")
        visited, status = self._walk(W.TDD_UNIT, {"regression": cov})
        self.assertIn("test-cleanup", visited)
        exited = {e["phase"]: e for e in self._events("phase.exited")}
        self.assertEqual(exited["test-cleanup"]["gate"], "regression")
        self.assertTrue(exited["test-cleanup"]["verified"])

    def test_cleanup_dropping_coverage_below_threshold_halts(self):
        cov = R.coverage_verifier("sh -c 'exit 1'", 80, target="pkg")
        visited, status = self._walk(W.TDD_UNIT, {"regression": cov})

        self.assertNotIn("test-cleanup", visited)
        self.assertEqual(status, "halted")

class MutationVerifierBuilderTest(unittest.TestCase):
    def test_absent_config_returns_none(self):
        self.assertIsNone(R.mutation_verifier(None, 0.9))
        self.assertIsNone(R.mutation_verifier("sh -c 'exit 0'", None))

    def test_score_above_threshold_passes(self):
        v = R.mutation_verifier("sh -c 'echo 0.95'", 0.9)
        self.assertTrue(v.verify(None, None, {}).verified)

    def test_score_below_threshold_fails(self):
        v = R.mutation_verifier("sh -c 'echo 0.50'", 0.9)
        self.assertFalse(v.verify(None, None, {}).verified)

    def test_exit_code_mode_when_no_score_printed(self):
        self.assertTrue(R.mutation_verifier("sh -c 'exit 0'", 0.9).verify(None, None, {}).verified)
        self.assertFalse(R.mutation_verifier("sh -c 'exit 1'", 0.9).verify(None, None, {}).verified)

    def test_unparseable_output_fails_closed(self):
        v = R.mutation_verifier("sh -c 'echo BLOCKED; exit 0'", 0.9)
        self.assertFalse(v.verify(None, None, {}).verified)

    def test_command_that_cannot_run_fails_closed(self):
        v = R.mutation_verifier("this-command-does-not-exist-xyz", 0.9)
        self.assertFalse(v.verify(None, None, {}).verified)

if __name__ == "__main__":
    unittest.main()
