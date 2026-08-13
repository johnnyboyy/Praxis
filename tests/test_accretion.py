import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import accretion as acc  # noqa: E402
import journal  # noqa: E402
import situation as sit  # noqa: E402

def _sit(**over):
    kw = dict(task_kind="change", intent="stand up infra", subject="process")
    kw.update(over)
    return sit.Situation(**kw)

class VocabularyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".praxis").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_base_seeds_are_known(self):
        self.assertTrue(acc.is_known(self.root, "task_kind", "create"))
        self.assertTrue(acc.is_known(self.root, "subject", "coding"))
        self.assertTrue(acc.is_known(self.root, "phase", "divergent"))

    def test_unminted_term_is_unknown(self):
        self.assertFalse(acc.is_known(self.root, "task_kind", "refactor"))

    def test_mint_makes_a_term_known(self):
        ev = acc.mint(self.root, "task_kind", "refactor")
        self.assertIsNotNone(ev)
        self.assertTrue(acc.is_known(self.root, "task_kind", "refactor"))
        self.assertIn("refactor", acc.vocabulary(self.root)["task_kind"])
        self.assertIn("create", acc.vocabulary(self.root)["task_kind"])

    def test_mint_is_idempotent(self):
        acc.mint(self.root, "task_kind", "refactor")
        self.assertIsNone(acc.mint(self.root, "task_kind", "refactor"))
        self.assertIsNone(acc.mint(self.root, "task_kind", "  Refactor "))
        mints = [e for e in journal.read(self.root) if e["event"] == "conductor.mint"]
        self.assertEqual(len(mints), 1)

    def test_minting_a_seed_is_a_noop(self):
        self.assertIsNone(acc.mint(self.root, "task_kind", "create"))

    def test_open_vocabularies_start_empty(self):
        self.assertEqual(acc.vocabulary(self.root)["workflow"], [])
        acc.mint(self.root, "workflow", "fan-out-verify")
        self.assertEqual(acc.vocabulary(self.root)["workflow"], ["fan-out-verify"])

    def test_bad_vocabulary_rejected(self):
        with self.assertRaises(ValueError):
            acc.mint(self.root, "colour", "teal")

    def test_empty_term_rejected(self):
        with self.assertRaises(ValueError):
            acc.mint(self.root, "task_kind", "   ")

class PromotionLoopTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".praxis").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def _gap(self, suggested, fit="none", chosen="change"):
        sit.surface_gap(self.root, vocabulary="task_kind", chosen=chosen, suggested=suggested,
                        fit=fit, intent="stand up infra")

    def test_recurrence_drives_promotable(self):
        for _ in range(3):
            self._gap("provision-infra")
        self._gap("refactor")
        prom = acc.promotable(self.root, min_count=3)
        self.assertEqual([c["suggested"] for c in prom], ["provision-infra"])

    def test_min_count_threshold(self):
        self._gap("provision-infra")
        self._gap("provision-infra")
        self.assertEqual(acc.promotable(self.root, min_count=3), [])
        self.assertTrue(acc.promotable(self.root, min_count=2))

    def test_minting_removes_from_promotable(self):
        for _ in range(3):
            self._gap("provision-infra")
        cand = acc.promotable(self.root, min_count=3)[0]
        acc.mint_candidate(self.root, cand, note="operator: real devops verb")
        self.assertEqual(acc.promotable(self.root, min_count=3), [])
        self.assertTrue(acc.is_known(self.root, "task_kind", "provision-infra"))

    def test_mint_candidate_carries_examples(self):
        for _ in range(3):
            self._gap("provision-infra")
        cand = acc.promotable(self.root, min_count=3)[0]
        ev = acc.mint_candidate(self.root, cand)
        self.assertEqual(ev["examples"], cand["examples"])

    def test_review_surface(self):
        for _ in range(3):
            self._gap("provision-infra")
        acc.mint(self.root, "subject", "devops")
        r = acc.review(self.root, min_count=3)
        self.assertEqual(r["min_count"], 3)
        self.assertEqual([c["suggested"] for c in r["promotable"]], ["provision-infra"])
        self.assertEqual(r["minted"]["subject"], ["devops"])
        self.assertIn("devops", r["vocabulary"]["subject"])
        self.assertIn("coding", r["vocabulary"]["subject"])

if __name__ == "__main__":
    unittest.main()
