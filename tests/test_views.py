import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import journal  # noqa: E402
import views  # noqa: E402

class CostViewTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".praxis").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_cost_rollup_sums_across_units_and_receipts(self):
        for uid, n in (("u1", 1), ("u2", 2)):
            for _ in range(n):
                journal.append(self.root, "unit.receipt", unit=uid, tool_calls=2,
                               cost={"tokens": 50, "usd": 0.01})
        cost = views.cost(self.root)
        self.assertEqual(cost["tokens"], 150)
        self.assertEqual(cost["tool_calls"], 6)
        self.assertAlmostEqual(cost["usd"], 0.03)
        self.assertEqual(cost["per_unit"]["u2"]["tokens"], 100)

    def test_cost_is_zero_without_receipts(self):
        self.assertEqual(views.cost(self.root),
                         {"tokens": 0, "usd": 0.0, "tool_calls": 0, "per_unit": {}})

    def test_missing_cost_fields_tolerated(self):
        journal.append(self.root, "unit.receipt", unit="u1")
        journal.append(self.root, "unit.receipt", unit="u1", cost={"tokens": None})
        self.assertEqual(views.cost(self.root)["tokens"], 0)

if __name__ == "__main__":
    unittest.main()
