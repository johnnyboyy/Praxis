import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import run as R  # noqa: E402
from situation import Situation  # noqa: E402

def _sit(**over):
    kw = dict(task_kind="change", intent="do the thing", subject="coding")
    kw.update(over)
    return Situation(**kw)

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

if __name__ == "__main__":
    unittest.main()
