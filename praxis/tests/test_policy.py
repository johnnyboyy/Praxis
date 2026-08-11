import json
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import policy as P  # noqa: E402
import providers as pv  # noqa: E402
import run as R  # noqa: E402
import schedule as S  # noqa: E402
from situation import Situation  # noqa: E402


def _sit(**over):
    kw = dict(task_kind="change", intent="do the thing", subject="coding")
    kw.update(over)
    return Situation(**kw)


class PolicyLoadTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".praxis").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def _write(self, obj):
        P.policy_path(self.root).write_text(json.dumps(obj))

    def test_defaults_when_absent(self):
        pol = P.load_policy(self.root)
        self.assertEqual((pol.concurrency, pol.max_retries, pol.verify_required), (4, 2, False))

    def test_partial_dict_merges_over_defaults(self):
        self._write({"concurrency": 8})
        pol = P.load_policy(self.root)
        self.assertEqual(pol.concurrency, 8)
        self.assertEqual(pol.max_retries, 2)

    def test_full_policy(self):
        self._write({"concurrency": 1, "max_retries": 0, "verify_required": True})
        pol = P.load_policy(self.root)
        self.assertEqual((pol.concurrency, pol.max_retries, pol.verify_required), (1, 0, True))

    def test_corrupt_file_degrades_to_defaults(self):
        P.policy_path(self.root).write_text("{not json")
        self.assertEqual(P.load_policy(self.root).concurrency, 4)

    def test_non_dict_degrades_to_defaults(self):
        self._write([1, 2, 3])
        self.assertEqual(P.load_policy(self.root).max_retries, 2)


class PolicyDrivesLoopTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".praxis").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def _policy(self, obj):
        P.policy_path(self.root).write_text(json.dumps(obj))

    def test_max_retries_comes_from_policy(self):
        self._policy({"max_retries": 0})
        verifier = R.CallableVerifier(lambda u, r, c: R.Verdict(verified=False, defects=["x"]))
        res = R.run(R.Plan([R.Unit("u1", _sit())]), pv.NullProvider(),
                    R.InlineExecutor(lambda u, c: R.Receipt(outcome="result")), self.root,
                    verifier=verifier)
        self.assertEqual(res["results"][0]["attempts"], 1)

    def test_explicit_arg_overrides_policy(self):
        self._policy({"max_retries": 0})
        verifier = R.CallableVerifier(lambda u, r, c: R.Verdict(verified=False, defects=["x"]))
        res = R.run(R.Plan([R.Unit("u1", _sit())]), pv.NullProvider(),
                    R.InlineExecutor(lambda u, c: R.Receipt(outcome="result")), self.root,
                    verifier=verifier, max_retries=2)
        self.assertEqual(res["results"][0]["attempts"], 3)

    def test_concurrency_cap_comes_from_policy(self):
        self._policy({"concurrency": 1})
        peak = [0]
        active = [0]
        lock = threading.Lock()

        def handler(unit, composed):
            with lock:
                active[0] += 1
                peak[0] = max(peak[0], active[0])
            time.sleep(0.02)
            with lock:
                active[0] -= 1
            return R.Receipt(outcome="result")

        plan = R.Plan([R.Unit(f"u{i}", _sit(label="x")) for i in range(4)])
        S.run_dag(plan, pv.NullProvider(), R.InlineExecutor(handler), self.root)
        self.assertEqual(peak[0], 1)

    def test_verify_required_rejects_a_run_without_a_verifier(self):
        self._policy({"verify_required": True})
        plan = R.Plan([R.Unit("u1", _sit())])
        work = R.InlineExecutor(lambda u, c: R.Receipt(outcome="result"))
        with self.assertRaises(ValueError):
            R.run(plan, pv.NullProvider(), work, self.root)
        with self.assertRaises(ValueError):
            S.run_dag(plan, pv.NullProvider(), work, self.root)

    def test_verify_required_allows_a_run_with_a_verifier(self):
        self._policy({"verify_required": True})
        plan = R.Plan([R.Unit("u1", _sit())])
        work = R.InlineExecutor(lambda u, c: R.Receipt(outcome="result"))
        verifier = R.CallableVerifier(lambda u, r, c: R.Verdict(verified=True))
        out = R.run(plan, pv.NullProvider(), work, self.root, verifier=verifier)
        self.assertEqual(out["results"][0]["outcome"], "result")


if __name__ == "__main__":
    unittest.main()
