import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import journal  # noqa: E402
import run as R  # noqa: E402
import workflow as W  # noqa: E402
from situation import Situation  # noqa: E402
from workflow_run import run_workflow  # noqa: E402


def _sit(**over):
    kw = dict(task_kind="change", intent="do the thing", subject="coding")
    kw.update(over)
    return Situation(**kw)


class SeedLibraryTest(unittest.TestCase):
    def test_seed_phases_present(self):
        for name in ("plan", "write-tests", "implement", "refactor", "test-cleanup",
                     "verify", "fix", "close", "extract", "synthesize", "coverage-diff"):
            self.assertIn(name, W.SEED_PHASES)
            self.assertIn(W.SEED_PHASES[name].stance, W.STANCES)

    def test_gate_mapping(self):
        self.assertEqual(W.GATES[W.EdgeType.create], "does-it")
        self.assertEqual(W.GATES[W.EdgeType.carry], "regression")
        self.assertEqual(W.GATES[W.EdgeType.extract], "coverage-diff")

    def test_tdd_workflow_shape(self):
        wf = W.TDD_UNIT
        self.assertEqual([p.name for p in wf.phases],
                         ["write-tests", "implement", "refactor", "test-cleanup"])
        self.assertEqual([p.name for p in W.next_phases(wf, "write-tests", "pass")],
                         ["implement"])
        self.assertEqual(W.next_phases(wf, "test-cleanup", "pass"), [])
        for (_f, _t, _w, et) in wf.edges:
            self.assertEqual(et, W.EdgeType.carry)

    def test_rebuild_triple_extract_edge(self):
        wf = W.REBUILD_TRIPLE
        self.assertEqual([p.name for p in wf.phases],
                         ["extract", "synthesize", "coverage-diff"])
        et = next(et for (f, t, w, et) in wf.edges if f == "extract" and t == "synthesize")
        self.assertEqual(et, W.EdgeType.extract)


class _Capture:
    def __init__(self):
        self.seen = []

    def run(self, unit, composed):
        self.seen.append(dict(composed))
        return R.Receipt(outcome="result", evidence={"produces": f"art-{len(self.seen)}"})


class WalkTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".praxis").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def _phase_events(self, event):
        return [e for e in journal.read(self.root) if e.get("event") == event]

    def test_walks_tdd_in_order_with_increasing_index(self):
        out = run_workflow(self.root, R.Unit("u1", _sit()), W.TDD_UNIT, [], _Capture())
        self.assertEqual(out["phases"],
                         ["write-tests", "implement", "refactor", "test-cleanup"])
        entered = self._phase_events("phase.entered")
        self.assertEqual([e["phase"] for e in entered],
                         ["write-tests", "implement", "refactor", "test-cleanup"])
        self.assertEqual([e["phase_index"] for e in entered], [0, 1, 2, 3])
        exited = self._phase_events("phase.exited")
        self.assertEqual([e["phase_index"] for e in exited], [0, 1, 2, 3])

    def test_carry_edge_threads_prior_output_and_first_phase_is_fresh(self):
        cap = _Capture()
        run_workflow(self.root, R.Unit("u1", _sit()), W.TDD_UNIT, [], cap)
        first, second = cap.seen[0], cap.seen[1]
        self.assertNotIn("carry", first)
        self.assertNotIn("ir", first)
        self.assertEqual(second["carry"], "art-1")
        self.assertNotIn("ir", second)

    def test_extract_edge_puts_ir_not_carry(self):
        cap = _Capture()
        run_workflow(self.root, R.Unit("u1", _sit()), W.REBUILD_TRIPLE, [], cap)
        synth = cap.seen[1]
        self.assertEqual(synth["ir"], "art-1")
        self.assertNotIn("carry", synth)
        coverage = cap.seen[2]
        self.assertEqual(coverage["carry"], "art-2")

    def test_coverage_diff_sees_both_ir_and_synthesis(self):
        cap = _Capture()
        run_workflow(self.root, R.Unit("u1", _sit()), W.REBUILD_TRIPLE, [], cap)
        coverage = cap.seen[2]
        self.assertEqual(coverage["inputs"], {"extract": "art-1", "synthesize": "art-2"})

    def test_task_kind_gap_surfaces_once_not_per_phase(self):
        run_workflow(self.root, R.Unit("u1", _sit(fit="none", suggested_kind="provision")),
                     W.TDD_UNIT, [], _Capture())
        self.assertEqual(len(journal.gaps(self.root)), 1)

    def test_edge_in_recorded_on_entry(self):
        run_workflow(self.root, R.Unit("u1", _sit()), W.REBUILD_TRIPLE, [], _Capture())
        entered = self._phase_events("phase.entered")
        self.assertEqual([e["edge_in"] for e in entered], ["create", "extract", "carry"])

    def test_loose_fit_records_phase_gap(self):
        def handler(unit, composed):
            return R.Receipt(outcome="result",
                             evidence={"phase_fit": "loose", "suggested": "design-api"})

        run_workflow(self.root, R.Unit("u1", _sit()), W.TDD_UNIT, [],
                     R.InlineExecutor(handler))
        pg = journal.phase_gaps(self.root, unit="u1")
        self.assertTrue(pg)
        self.assertEqual(pg[0]["suggested"], "design-api")
        self.assertEqual(pg[0]["fit"], "loose")

    def test_gate_selected_by_edge_name_and_failure_recorded(self):
        failing = R.CallableVerifier(
            lambda unit, receipt, composed: R.Verdict(verified=False, defects=["dropped a symbol"]))
        out = run_workflow(self.root, R.Unit("u1", _sit()), W.REBUILD_TRIPLE, [],
                           _Capture(), verifiers={"coverage-diff": failing})
        exited = {e["phase"]: e for e in self._phase_events("phase.exited")}
        self.assertEqual(exited["synthesize"]["gate"], "coverage-diff")
        self.assertFalse(exited["synthesize"]["verified"])
        self.assertEqual(exited["extract"]["gate"], "does-it")
        self.assertTrue(exited["extract"]["verified"])
        self.assertEqual(out["phase_fits"]["synthesize"], "clean")


if __name__ == "__main__":
    unittest.main()
