import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import journal  # noqa: E402
import providers as pv  # noqa: E402
import run as R  # noqa: E402
from situation import Situation  # noqa: E402


def _sit(**over):
    kw = dict(task_kind="change", intent="do the thing", subject="coding")
    kw.update(over)
    return Situation(**kw)


def _result(unit, composed):
    return R.Receipt(outcome="result", status="complete")


class VerdictTest(unittest.TestCase):
    def test_from_dict(self):
        v = R.Verdict.from_dict({"verified": 1, "defects": ["x"], "evidence": {"n": 1}})
        self.assertTrue(v.verified)
        self.assertEqual(v.defects, ["x"])
        self.assertEqual(v.evidence, {"n": 1})

    def test_from_dict_defaults(self):
        v = R.Verdict.from_dict({})
        self.assertFalse(v.verified)
        self.assertEqual(v.defects, [])

    def test_callable_verifier_normalizes_dict(self):
        vr = R.CallableVerifier(lambda u, r, c: {"verified": True})
        self.assertTrue(vr.verify(R.Unit("u", _sit()), R.Receipt(outcome="result"), {}).verified)


class _VerifyAfter:
    """A verifier that fails until its `pass_on`-th call, then passes."""

    def __init__(self, pass_on):
        self.calls = 0
        self.pass_on = pass_on

    def verify(self, unit, receipt, composed):
        self.calls += 1
        if self.calls >= self.pass_on:
            return R.Verdict(verified=True, evidence={"ok": True})
        return R.Verdict(verified=False, defects=[f"defect #{self.calls}"])


class VerificationGateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".praxis").mkdir()
        self.provider = pv.NullProvider()

    def tearDown(self):
        self.tmp.cleanup()

    def _events(self, uid):
        return [e["event"] for e in journal.read(self.root) if e.get("unit") == uid]

    def test_verified_first_try_records_unit_verified_then_done(self):
        res = R.run_unit(self.root, R.Unit("u1", _sit()), self.provider,
                         R.InlineExecutor(_result), _VerifyAfter(pass_on=1))
        self.assertTrue(res["verified"])
        self.assertEqual(res["attempts"], 1)
        self.assertEqual(self._events("u1"),
                         ["unit.proposed", "unit.framed", "unit.dispatched", "unit.running",
                          "unit.receipt", "unit.verified", "unit.done"])
        self.assertEqual(journal.state_of(self.root, "u1"), "done")
        verified = next(e for e in journal.read(self.root) if e["event"] == "unit.verified")
        self.assertEqual(verified["evidence"], {"ok": True})

    def test_defect_then_pass_loops_back_with_feedback(self):
        seen_feedback = []

        def handler(unit, composed):
            seen_feedback.append(composed.get("feedback"))
            return R.Receipt(outcome="result")

        res = R.run_unit(self.root, R.Unit("u1", _sit()), self.provider,
                         R.InlineExecutor(handler), _VerifyAfter(pass_on=2))
        self.assertTrue(res["verified"])
        self.assertEqual(res["attempts"], 2)
        self.assertEqual(seen_feedback, [None, ["defect #1"]])
        self.assertEqual(self._events("u1"),
                         ["unit.proposed", "unit.framed",
                          "unit.dispatched", "unit.running", "unit.receipt", "unit.note",
                          "unit.dispatched", "unit.running", "unit.receipt", "unit.verified",
                          "unit.done"])
        defect = next(e for e in journal.read(self.root) if e["event"] == "unit.note")
        self.assertEqual(defect["kind"], "defect")
        self.assertEqual(defect["defects"], ["defect #1"])

    def test_retries_exhausted_surfaces_blocked_stall(self):
        res = R.run_unit(self.root, R.Unit("u1", _sit()), self.provider,
                         R.InlineExecutor(_result), _VerifyAfter(pass_on=99), max_retries=1)
        self.assertEqual(res["outcome"], "stall")
        self.assertFalse(res["verified"])
        self.assertEqual(res["attempts"], 2)
        self.assertEqual(res["defects"], ["defect #2"])
        self.assertEqual(journal.state_of(self.root, "u1"), "stalled")
        u = journal.fold(self.root)["units"]["u1"]
        self.assertEqual(u["status"], "blocked")
        self.assertEqual(u["surfaced"], ["defect #2"])
        notes = [e for e in journal.read(self.root)
                 if e["event"] == "unit.note" and e.get("kind") == "defect"]
        self.assertEqual(len(notes), 2)

    def test_max_retries_zero_is_single_attempt(self):
        res = R.run_unit(self.root, R.Unit("u1", _sit()), self.provider,
                         R.InlineExecutor(_result), _VerifyAfter(pass_on=99), max_retries=0)
        self.assertEqual(res["outcome"], "stall")
        self.assertEqual(res["attempts"], 1)

    def test_receipt_stall_is_surfaced_not_retried(self):
        verifier = _VerifyAfter(pass_on=1)
        stall = lambda u, c: R.Receipt(outcome="stall", status="questions-pending",
                                       surfaced=["which db?"])
        res = R.run_unit(self.root, R.Unit("u1", _sit()), self.provider,
                         R.InlineExecutor(stall), verifier)
        self.assertEqual(res["outcome"], "stall")
        self.assertIsNone(res["verified"])
        self.assertEqual(verifier.calls, 0)
        self.assertEqual(self._events("u1"),
                         ["unit.proposed", "unit.framed", "unit.dispatched", "unit.running",
                          "unit.receipt", "unit.stalled"])

    def test_no_verifier_keeps_p4_behavior(self):
        res = R.run_unit(self.root, R.Unit("u1", _sit()), self.provider, R.InlineExecutor(_result))
        self.assertIsNone(res["verified"])
        self.assertEqual(self._events("u1"),
                         ["unit.proposed", "unit.framed", "unit.dispatched", "unit.running",
                          "unit.receipt", "unit.done"])


class CommandVerifierTest(unittest.TestCase):
    def setUp(self):
        self.unit = R.Unit("u1", _sit())

    def _v(self, code):
        return R.CommandVerifier(lambda u, r, c: [sys.executable, "-c", code])

    def test_exit_zero_verifies_with_evidence(self):
        v = self._v("print('all green')").verify(self.unit, R.Receipt(outcome="result"), {})
        self.assertTrue(v.verified)
        self.assertIn("all green", v.evidence["stdout"])

    def test_nonzero_exit_is_a_defect_with_detail(self):
        v = self._v("import sys; sys.stderr.write('2 failed'); sys.exit(1)").verify(
            self.unit, R.Receipt(outcome="result"), {})
        self.assertFalse(v.verified)
        self.assertIn("2 failed", v.defects[0])

    def test_launch_failure_is_a_defect(self):
        v = R.CommandVerifier(lambda u, r, c: ["/no/such/verifier/xyzzy"]).verify(
            self.unit, R.Receipt(outcome="result"), {})
        self.assertFalse(v.verified)


class RunWithVerifierTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".praxis").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_plan_run_gates_every_unit(self):
        def verify(unit, receipt, composed):
            return R.Verdict(verified=unit.id != "u2",
                             defects=[] if unit.id != "u2" else ["still broken"])

        plan = R.Plan([R.Unit(f"u{i}", _sit(label="implement-feature")) for i in (1, 2, 3)])
        out = R.run(plan, pv.NullProvider(), R.InlineExecutor(_result), self.root,
                    verifier=R.CallableVerifier(verify), max_retries=1)
        self.assertEqual([r["outcome"] for r in out["results"]], ["result", "stall", "result"])
        self.assertEqual([r["verified"] for r in out["results"]], [True, False, True])
        bucket = out["summary"]["by_phase"]["implement-feature"]
        self.assertEqual((bucket["runs"], bucket["result"], bucket["stall"]), (3, 2, 1))


if __name__ == "__main__":
    unittest.main()
