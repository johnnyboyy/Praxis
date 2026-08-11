import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import journal  # noqa: E402
import orchestrate as O  # noqa: E402
import run as R  # noqa: E402
from situation import Situation  # noqa: E402


def _sit(**over):
    kw = dict(task_kind="change", intent="do the thing", subject="coding", label="impl")
    kw.update(over)
    return Situation(**kw)


def _u(uid, deps=None, **sit):
    return R.Unit(uid, _sit(**sit), depends_on=deps or [])


def _ok(unit, composed):
    return R.Receipt(outcome="result")


def _stateful_barrier(*verdicts):
    calls = [0]

    def barrier():
        i = min(calls[0], len(verdicts) - 1)
        calls[0] += 1
        return verdicts[i]

    return barrier, calls


class OrchestrateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".praxis").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def _fix_units(self):
        return [e["unit"] for e in journal.read(self.root)
                if e.get("event") == "unit.proposed" and str(e.get("unit", "")).startswith("fix-")]

    def test_barrier_passes_first_time(self):
        barrier, calls = _stateful_barrier(R.Verdict(verified=True))
        out = O.run_orchestrated(self.root, [_u("a"), _u("b")], [],
                                 R.InlineExecutor(_ok), barrier)
        self.assertEqual(out["status"], "complete")
        self.assertEqual(out["reason"], None)
        self.assertEqual(out["attempts"], 1)
        self.assertEqual(calls[0], 1)
        self.assertEqual(self._fix_units(), [])

    def test_barrier_fails_once_then_passes(self):
        barrier, calls = _stateful_barrier(
            R.Verdict(verified=False, defects=["boom"]), R.Verdict(verified=True))
        out = O.run_orchestrated(self.root, [_u("a")], [], R.InlineExecutor(_ok), barrier)
        self.assertEqual(out["status"], "complete")
        self.assertEqual(out["attempts"], 2)
        self.assertEqual(calls[0], 2)
        self.assertIn("fix-0-0", self._fix_units())

    def test_barrier_always_fails_exhausts_budget(self):
        barrier, calls = _stateful_barrier(R.Verdict(verified=False, defects=["boom"]))
        out = O.run_orchestrated(self.root, [_u("a")], [], R.InlineExecutor(_ok),
                                 barrier, fix_rounds=2)
        self.assertEqual(out["status"], "escalated")
        self.assertEqual(out["reason"], "loop-exhausted")
        self.assertEqual(out["attempts"], 3)
        self.assertEqual(calls[0], 3)

    def test_fanout_stall_escalates_without_barrier(self):
        barrier, calls = _stateful_barrier(R.Verdict(verified=True))

        def handler(unit, composed):
            return R.Receipt(outcome="stall", status="blocked") if unit.id == "b" \
                else R.Receipt(outcome="result")

        out = O.run_orchestrated(self.root, [_u("a"), _u("b")], [],
                                 R.InlineExecutor(handler), barrier)
        self.assertEqual(out["status"], "escalated")
        self.assertEqual(out["reason"], "unit-stalled")
        self.assertEqual(out["units"], ["b"])
        self.assertEqual(calls[0], 0)

    def test_fix_unit_structural_misfit_escalates(self):
        barrier, calls = _stateful_barrier(R.Verdict(verified=False, defects=["boom"]))

        def handler(unit, composed):
            if unit.id.startswith("fix-"):
                return R.Receipt(outcome="result", evidence={"phase_fit": "none"})
            return R.Receipt(outcome="result")

        out = O.run_orchestrated(self.root, [_u("a")], [], R.InlineExecutor(handler), barrier)
        self.assertEqual(out["status"], "escalated")
        self.assertEqual(out["reason"], "structural-misfit")
        self.assertEqual(out["fix_unit"], "fix-0-0")

    def test_failing_subdag_transitive_dependents(self):
        units = [_u("a"), _u("b", ["a"]), _u("c", ["b"])]
        self.assertEqual(O.failing_subdag(units, ["a"]), ["a", "b", "c"])
        self.assertEqual(O.failing_subdag(units, ["b"]), ["b", "c"])
        self.assertEqual(O.failing_subdag(units, ["c"]), ["c"])

    def test_replan_splices_replacement_and_completes(self):
        barrier, _ = _stateful_barrier(R.Verdict(verified=True))

        def handler(unit, composed):
            return R.Receipt(outcome="stall", status="blocked") if unit.id == "b" \
                else R.Receipt(outcome="result")

        units = [_u("a"), _u("b")]
        out = O.run_orchestrated(self.root, units, [], R.InlineExecutor(handler), barrier)
        self.assertEqual(out["status"], "escalated")
        self.assertEqual(out["reason"], "unit-stalled")
        self.assertEqual(out["failing_subdag"], ["b"])

        replan_out = O.replan(self.root, units, out["failing_subdag"], [_u("b2")],
                              [], R.InlineExecutor(handler), barrier)
        self.assertEqual(replan_out["status"], "complete")


if __name__ == "__main__":
    unittest.main()
