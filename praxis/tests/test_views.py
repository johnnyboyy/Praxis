import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import journal  # noqa: E402
import providers as pv  # noqa: E402
import run as R  # noqa: E402
import views  # noqa: E402
from situation import Situation  # noqa: E402


def _sit(**over):
    kw = dict(task_kind="change", intent="do the thing", subject="coding")
    kw.update(over)
    return Situation(**kw)


class HandoffViewTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".praxis").mkdir()
        self.provider = pv.CorporaProvider(lambda r, u: {"domains": ["prose-craft"], "warnings": []})

    def tearDown(self):
        self.tmp.cleanup()

    def test_unknown_unit_is_none(self):
        self.assertIsNone(views.handoff(self.root, "nope"))

    def test_verified_unit_handoff(self):
        def work(unit, composed):
            return R.Receipt(outcome="result", tool_calls=4, cost={"tokens": 100, "usd": 0.02})

        verify = R.CallableVerifier(lambda u, r, c: R.Verdict(verified=True, evidence={"tests": "42 passed"}))
        R.run_unit(self.root, R.Unit("u1", _sit(label="implement-feature")), self.provider,
                   R.InlineExecutor(work), verify)
        h = views.handoff(self.root, "u1")
        self.assertEqual(h["state"], "done")
        self.assertTrue(h["verified"])
        self.assertEqual(h["evidence"], {"tests": "42 passed"})
        self.assertEqual(h["domains_loaded"], ["prose-craft"])
        self.assertEqual(h["attempts"], 1)
        self.assertEqual(h["cost"], {"tokens": 100, "usd": 0.02})
        self.assertEqual(h["tool_calls"], 4)

    def test_stalled_unit_handoff_carries_defects(self):
        verify = R.CallableVerifier(lambda u, r, c: R.Verdict(verified=False, defects=["boom"]))
        R.run_unit(self.root, R.Unit("u1", _sit()), self.provider,
                   R.InlineExecutor(lambda u, c: R.Receipt(outcome="result")), verify, max_retries=1)
        h = views.handoff(self.root, "u1")
        self.assertEqual(h["outcome"], "stall")
        self.assertFalse(h["verified"])
        self.assertEqual(h["attempts"], 2)                # initial + 1 retry
        self.assertEqual(h["defects"], [["boom"], ["boom"]])  # one per failed attempt
        self.assertEqual(h["surfaced"], ["boom"])


class LedgerViewTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".praxis").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_ledger_is_one_row_per_unit_in_order(self):
        def handler(unit, composed):
            return R.Receipt(outcome="stall", status="blocked") if unit.id == "u2" \
                else R.Receipt(outcome="result")

        plan = R.Plan([R.Unit(f"u{i}", _sit(label="implement-feature")) for i in (1, 2, 3)])
        R.run(plan, pv.NullProvider(), R.InlineExecutor(handler), self.root)
        rows = views.ledger(self.root)
        self.assertEqual([r["unit"] for r in rows], ["u1", "u2", "u3"])
        self.assertEqual([r["outcome"] for r in rows], ["result", "stall", "result"])
        self.assertEqual([r["state"] for r in rows], ["done", "stalled", "done"])
        self.assertTrue(all(r["attempts"] == 1 for r in rows))


class CostViewTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".praxis").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_cost_rollup_sums_across_units_and_retries(self):
        # u1 verifies first try (1 receipt); u2 fails twice (2 receipts) then stalls.
        def verify(unit, receipt, composed):
            return R.Verdict(verified=unit.id == "u1", defects=[] if unit.id == "u1" else ["x"])

        def work(unit, composed):
            return R.Receipt(outcome="result", tool_calls=2, cost={"tokens": 50, "usd": 0.01})

        plan = R.Plan([R.Unit("u1", _sit(label="a")), R.Unit("u2", _sit(label="b"))])
        out = R.run(plan, pv.NullProvider(), R.InlineExecutor(work), self.root,
                    verifier=R.CallableVerifier(verify), max_retries=1)
        cost = out["cost"]
        # u1: 1 receipt; u2: 2 receipts (initial + retry) ⇒ 3 receipts total.
        self.assertEqual(cost["tokens"], 150)
        self.assertEqual(cost["tool_calls"], 6)
        self.assertAlmostEqual(cost["usd"], 0.03)
        self.assertEqual(cost["per_unit"]["u2"]["tokens"], 100)  # summed over 2 attempts

    def test_cost_is_zero_without_receipts(self):
        self.assertEqual(views.cost(self.root), {"tokens": 0, "usd": 0.0, "tool_calls": 0, "per_unit": {}})


class SubprocessCostCaptureTest(unittest.TestCase):
    def setUp(self):
        self.unit = R.Unit("u1", _sit())

    def test_cost_extractor_fills_missing_cost(self):
        # Child prints a bare "done" (no receipt JSON); the extractor pulls cost from its output.
        def argv(unit, composed):
            return [sys.executable, "-c", "print('usage tokens=321')"]

        def extractor(stdout, stderr):
            import re
            m = re.search(r"tokens=(\d+)", stdout)
            return {"tokens": int(m.group(1)), "usd": 0.0} if m else None

        r = R.SubprocessExecutor(argv, cost_extractor=extractor).run(self.unit, {})
        self.assertEqual(r.outcome, "result")
        self.assertEqual(r.cost, {"tokens": 321, "usd": 0.0})

    def test_receipt_cost_wins_over_extractor(self):
        def argv(unit, composed):
            code = "import json;print(json.dumps({'outcome':'result','cost':{'tokens':9,'usd':0.0}}))"
            return [sys.executable, "-c", code]

        r = R.SubprocessExecutor(argv, cost_extractor=lambda o, e: {"tokens": 999}).run(self.unit, {})
        self.assertEqual(r.cost["tokens"], 9)   # the child's own receipt cost is authoritative


if __name__ == "__main__":
    unittest.main()
