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

class ReceiptTest(unittest.TestCase):
    def test_rejects_bad_outcome(self):
        with self.assertRaises(ValueError):
            R.Receipt(outcome="maybe")

    def test_roundtrip(self):
        r = R.Receipt(outcome="stall", status="blocked", surfaced=["q?"], tool_calls=2,
                      cost={"tokens": 10, "usd": 0.01})
        self.assertEqual(R.Receipt.from_dict(r.to_dict()).to_dict(), r.to_dict())

    def test_from_dict_defaults(self):
        r = R.Receipt.from_dict({})
        self.assertEqual(r.outcome, "result")
        self.assertEqual(r.status, "complete")
        self.assertEqual(r.surfaced, [])

class UnitTest(unittest.TestCase):
    def test_unit_of_work_defaults_to_label_then_task_kind(self):
        self.assertEqual(R.Unit("u", _sit(label="scaffold-tests")).unit_of_work, "scaffold-tests")
        self.assertEqual(R.Unit("u", _sit(label=None, task_kind="explore")).unit_of_work, "explore")

    def test_explicit_unit_of_work_wins(self):
        self.assertEqual(R.Unit("u", _sit(label="x"), unit_of_work="named").unit_of_work, "named")

class VerifierTest(unittest.TestCase):
    def test_command_verifier_pass_and_fail(self):
        ok = R.verifier_from_test_cmd("true")
        bad = R.verifier_from_test_cmd("false")
        self.assertTrue(ok.verify(None, None, {}).verified)
        self.assertFalse(bad.verify(None, None, {}).verified)

    def test_no_test_cmd_is_none(self):
        self.assertIsNone(R.verifier_from_test_cmd(None))
        self.assertIsNone(R.verifier_from_test_cmd(""))

    def test_callable_verifier_normalizes_dict(self):
        v = R.CallableVerifier(lambda u, r, c: {"verified": True, "defects": []})
        self.assertTrue(v.verify(None, None, {}).verified)

    def test_command_that_cannot_run_fails_closed(self):
        v = R.CommandVerifier(lambda u, r, c: ["/no/such/binary/xyzzy"])
        out = v.verify(None, None, {})
        self.assertFalse(out.verified)
        self.assertTrue(out.defects)

if __name__ == "__main__":
    unittest.main()
