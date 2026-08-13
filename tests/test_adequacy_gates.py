#!/usr/bin/env python3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402
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

    return R.Receipt(outcome="result", evidence={"produces": composed.get("phase")})

def _carry2():
    a = W.Phase("A", stance="convergent")
    b = W.Phase("B", stance="convergent")
    return W.Workflow("carry2", [a, b],
                      edges=[("A", "B", "pass", W.EdgeType.carry)])

class _CloseWatcher:

    source = "close-watcher"

    def __init__(self):
        self.close_fired = False

    def contribute(self, situation):
        return []

    def hooks(self):
        return {"close": self._on_close}

    def _on_close(self, ctx):
        self.close_fired = True

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

class CoverageGateWalkTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".praxis").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def _events(self, event):
        return [e for e in journal.read(self.root) if e.get("event") == event]

    def test_coverage_pass_advances_walk(self):
        cov = R.coverage_verifier("sh -c 'exit 0'", 80, target="pkg")
        verifiers = R._workflow_verifiers(None, cov)
        out = run_workflow(self.root, R.Unit("u1", _sit()), _carry2(), [],
                           R.InlineExecutor(_pass_handler), verifiers=verifiers)
        self.assertEqual(out["phases"], ["A", "B"])
        self.assertTrue(all(e["verified"] for e in self._events("phase.exited")))

    def test_coverage_under_threshold_halts_walk(self):
        cov = R.coverage_verifier("sh -c 'exit 1'", 80, target="pkg")
        verifiers = R._workflow_verifiers(None, cov)
        out = run_workflow(self.root, R.Unit("u1", _sit()), _carry2(), [],
                           R.InlineExecutor(_pass_handler), verifiers=verifiers)
        self.assertEqual(out["phases"], ["A"])
        exited = self._events("phase.exited")
        self.assertFalse(exited[0]["verified"])
        self.assertNotIn("B", [e["phase"] for e in self._events("phase.entered")])

    def test_coverage_prefers_over_bare_test_verifier(self):

        bare_pass = R.verifier_from_test_cmd("true")
        cov_fail = R.coverage_verifier("sh -c 'exit 1'", 80, target="pkg")
        verifiers = R._workflow_verifiers(bare_pass, cov_fail)
        out = run_workflow(self.root, R.Unit("u1", _sit()), _carry2(), [],
                           R.InlineExecutor(_pass_handler), verifiers=verifiers)
        self.assertEqual(out["phases"], ["A"])

class TestCleanupReguardedByCoverageTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".praxis").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def _events(self, event):
        return [e for e in journal.read(self.root) if e.get("event") == event]

    def test_coverage_gate_runs_on_test_cleanup_phase(self):

        cov = R.coverage_verifier("sh -c 'exit 0'", 80, target="pkg")
        out = run_workflow(self.root, R.Unit("u1", _sit()), W.TDD_UNIT, [],
                           R.InlineExecutor(_pass_handler),
                           verifiers={"regression": cov})
        self.assertIn("test-cleanup", out["phases"])
        exited = {e["phase"]: e for e in self._events("phase.exited")}
        self.assertEqual(exited["test-cleanup"]["gate"], "regression")
        self.assertTrue(exited["test-cleanup"]["verified"])

    def test_cleanup_dropping_coverage_below_threshold_halts(self):
        cov = R.coverage_verifier("sh -c 'exit 1'", 80, target="pkg")
        out = run_workflow(self.root, R.Unit("u1", _sit()), W.TDD_UNIT, [],
                           R.InlineExecutor(_pass_handler),
                           verifiers={"regression": cov})

        self.assertNotIn("test-cleanup", out["phases"])

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

class MutationBarrierBlocksCloseTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".praxis").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def _events(self, event):
        return [e for e in journal.read(self.root) if e.get("event") == event]

    def _plan(self):
        return R.Plan([R.Unit("u1", _sit(fit="clean", label="implement"))])

    def _work(self, unit, composed):
        return R.Receipt(outcome="result", status="complete")

    def test_barrier_above_threshold_fires_close(self):
        watcher = _CloseWatcher()
        barrier = R.mutation_verifier("sh -c 'echo 0.95'", 0.9)
        out = R.run(self._plan(), [watcher], R.InlineExecutor(self._work), self.root,
                    barrier_verifier=barrier)
        self.assertTrue(watcher.close_fired)
        self.assertTrue(out["closed"])
        self.assertTrue(out["barrier"]["verified"])
        self.assertTrue(self._events("barrier.verified"))

    def test_barrier_below_threshold_blocks_close(self):
        watcher = _CloseWatcher()
        barrier = R.mutation_verifier("sh -c 'echo 0.50'", 0.9)
        out = R.run(self._plan(), [watcher], R.InlineExecutor(self._work), self.root,
                    barrier_verifier=barrier)
        self.assertFalse(watcher.close_fired)
        self.assertFalse(out["closed"])
        self.assertEqual(out["status"], "blocked")
        self.assertFalse(out["barrier"]["verified"])
        self.assertTrue(self._events("barrier.blocked"))
        self.assertEqual(len(out["results"]), 1)

    def test_no_barrier_config_closes_as_before(self):
        watcher = _CloseWatcher()
        out = R.run(self._plan(), [watcher], R.InlineExecutor(self._work), self.root)
        self.assertTrue(watcher.close_fired)
        self.assertTrue(out["closed"])
        self.assertIsNone(out["barrier"])

    def test_barrier_built_from_config_blocks_close(self):

        config.write(self.root, None, {"mutation-cmd": "sh -c 'echo 0.10'",
                                       "mutation-threshold": 0.9})
        watcher = _CloseWatcher()
        out = R.run(self._plan(), [watcher], R.InlineExecutor(self._work), self.root)
        self.assertFalse(watcher.close_fired)
        self.assertFalse(out["closed"])

if __name__ == "__main__":
    unittest.main()
