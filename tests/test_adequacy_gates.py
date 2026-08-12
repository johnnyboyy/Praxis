#!/usr/bin/env python3
"""R2 of the spine: the two adequacy gates at their altitudes, fixture-proven.

Both gates are deterministic and engine-run — the verdict is a command's exit
code / score, never model evidence. No model, no `claude -p`, and NO hard
mutmut/cosmic-ray dependency: every command here is a CONTROLLABLE fake
(`sh -c 'exit N'` / `sh -c 'echo <score>'`), exactly like R1 used true/false.

  * COVERAGE (fast, per-unit): wired as the does-it/regression gate; the unit's
    walk advances only when the coverage command exits 0 (passes threshold), and
    halts when it exits non-zero (under threshold). Re-runs after test-cleanup.
  * MUTATION (slow, plan-level): run once by run() after all units, before the
    close hook. Score >= threshold fires close; score < threshold blocks it.
"""
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
    # every phase's own execution succeeds; only the engine-run gate can halt us
    return R.Receipt(outcome="result", evidence={"produces": composed.get("phase")})


def _carry2():
    a = W.Phase("A", stance="convergent")
    b = W.Phase("B", stance="convergent")
    return W.Workflow("carry2", [a, b],
                      edges=[("A", "B", "pass", W.EdgeType.carry)])


class _CloseWatcher:
    """A contributor that records whether the plan-level `close` hook fired."""

    source = "close-watcher"

    def __init__(self):
        self.close_fired = False

    def contribute(self, situation):
        return []

    def hooks(self):
        return {"close": self._on_close}

    def _on_close(self, ctx):
        self.close_fired = True


# ---------------------------------------------------------------------------
# 1. COVERAGE verifier — the builder itself (exit code is the verdict)
# ---------------------------------------------------------------------------
class CoverageVerifierBuilderTest(unittest.TestCase):
    def test_absent_config_returns_none_no_fabricated_pass(self):
        self.assertIsNone(R.coverage_verifier(None, None))
        self.assertIsNone(R.coverage_verifier(None, 80))      # threshold but no cmd/target
        self.assertIsNone(R.coverage_verifier("pytest", None))  # cmd but no threshold

    def test_exit_zero_passes_exit_nonzero_fails(self):
        # controllable fake commands; appended --cov flags are ignored by `sh -c`
        ok = R.coverage_verifier("sh -c 'exit 0'", 80, target="pkg")
        bad = R.coverage_verifier("sh -c 'exit 1'", 80, target="pkg")
        self.assertTrue(ok.verify(None, None, {}).verified)
        self.assertFalse(bad.verify(None, None, {}).verified)

    def test_argv_enforces_threshold_via_exit_code(self):
        v = R.coverage_verifier("pytest", 91, target="pkg")
        argv = v._argv_builder(None, None, {})
        self.assertEqual(argv, ["pytest", "--cov=pkg", "--cov-fail-under=91"])


# ---------------------------------------------------------------------------
# 2. COVERAGE as the per-unit gate — a unit's walk advances/halts on coverage
# ---------------------------------------------------------------------------
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
        verifiers = R._workflow_verifiers(None, cov)  # coverage IS the per-unit gate
        out = run_workflow(self.root, R.Unit("u1", _sit()), _carry2(), [],
                           R.InlineExecutor(_pass_handler), verifiers=verifiers)
        self.assertEqual(out["phases"], ["A", "B"])  # advances A -> B
        self.assertTrue(all(e["verified"] for e in self._events("phase.exited")))

    def test_coverage_under_threshold_halts_walk(self):
        cov = R.coverage_verifier("sh -c 'exit 1'", 80, target="pkg")
        verifiers = R._workflow_verifiers(None, cov)
        out = run_workflow(self.root, R.Unit("u1", _sit()), _carry2(), [],
                           R.InlineExecutor(_pass_handler), verifiers=verifiers)
        self.assertEqual(out["phases"], ["A"])  # HALTS before B
        exited = self._events("phase.exited")
        self.assertFalse(exited[0]["verified"])  # coverage gate said no
        self.assertNotIn("B", [e["phase"] for e in self._events("phase.entered")])

    def test_coverage_prefers_over_bare_test_verifier(self):
        # both supplied: the coverage gate (failing) must win over the bare test
        # verifier (passing), proving coverage replaces the bare test command.
        bare_pass = R.verifier_from_test_cmd("true")
        cov_fail = R.coverage_verifier("sh -c 'exit 1'", 80, target="pkg")
        verifiers = R._workflow_verifiers(bare_pass, cov_fail)
        out = run_workflow(self.root, R.Unit("u1", _sit()), _carry2(), [],
                           R.InlineExecutor(_pass_handler), verifiers=verifiers)
        self.assertEqual(out["phases"], ["A"])  # coverage halted it


# ---------------------------------------------------------------------------
# 3. test-cleanup re-guard — the coverage gate re-runs after test-cleanup so
#    pruning scaffolding cannot drop coverage below threshold.
# ---------------------------------------------------------------------------
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
        # Wire coverage to `regression` only; TDD_UNIT's test-cleanup is entered
        # via a carry edge, so its gate IS the coverage verifier — proving the
        # coverage check re-runs AFTER cleanup prunes scaffolding.
        cov = R.coverage_verifier("sh -c 'exit 0'", 80, target="pkg")
        out = run_workflow(self.root, R.Unit("u1", _sit()), W.TDD_UNIT, [],
                           R.InlineExecutor(_pass_handler),
                           verifiers={"regression": cov})
        self.assertIn("test-cleanup", out["phases"])
        exited = {e["phase"]: e for e in self._events("phase.exited")}
        self.assertEqual(exited["test-cleanup"]["gate"], "regression")
        self.assertTrue(exited["test-cleanup"]["verified"])  # coverage re-ran, held

    def test_cleanup_dropping_coverage_below_threshold_halts(self):
        cov = R.coverage_verifier("sh -c 'exit 1'", 80, target="pkg")
        out = run_workflow(self.root, R.Unit("u1", _sit()), W.TDD_UNIT, [],
                           R.InlineExecutor(_pass_handler),
                           verifiers={"regression": cov})
        # first carry-entered phase (implement) fails the coverage gate and halts
        self.assertNotIn("test-cleanup", out["phases"])


# ---------------------------------------------------------------------------
# 4. MUTATION verifier — the builder (score-mode and exit-code-mode)
# ---------------------------------------------------------------------------
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
        self.assertFalse(v.verify(None, None, {}).verified)  # non-empty, no score -> fail

    def test_command_that_cannot_run_fails_closed(self):
        v = R.mutation_verifier("this-command-does-not-exist-xyz", 0.9)
        self.assertFalse(v.verify(None, None, {}).verified)


# ---------------------------------------------------------------------------
# 5. MUTATION as the plan-level FINAL BARRIER — run() fires/blocks close
# ---------------------------------------------------------------------------
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
        self.assertTrue(watcher.close_fired)          # close hook DID fire
        self.assertTrue(out["closed"])
        self.assertTrue(out["barrier"]["verified"])
        self.assertTrue(self._events("barrier.verified"))

    def test_barrier_below_threshold_blocks_close(self):
        watcher = _CloseWatcher()
        barrier = R.mutation_verifier("sh -c 'echo 0.50'", 0.9)
        out = R.run(self._plan(), [watcher], R.InlineExecutor(self._work), self.root,
                    barrier_verifier=barrier)
        self.assertFalse(watcher.close_fired)         # close hook did NOT fire
        self.assertFalse(out["closed"])
        self.assertEqual(out["status"], "blocked")
        self.assertFalse(out["barrier"]["verified"])
        self.assertTrue(self._events("barrier.blocked"))
        self.assertEqual(len(out["results"]), 1)      # units still ran

    def test_no_barrier_config_closes_as_before(self):
        watcher = _CloseWatcher()
        out = R.run(self._plan(), [watcher], R.InlineExecutor(self._work), self.root)
        self.assertTrue(watcher.close_fired)
        self.assertTrue(out["closed"])
        self.assertIsNone(out["barrier"])

    def test_barrier_built_from_config_blocks_close(self):
        # no explicit barrier_verifier — run() builds it from policy/config
        config.write(self.root, None, {"mutation-cmd": "sh -c 'echo 0.10'",
                                       "mutation-threshold": 0.9})
        watcher = _CloseWatcher()
        out = R.run(self._plan(), [watcher], R.InlineExecutor(self._work), self.root)
        self.assertFalse(watcher.close_fired)
        self.assertFalse(out["closed"])


if __name__ == "__main__":
    unittest.main()
