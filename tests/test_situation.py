import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import journal  # noqa: E402
import situation as sit  # noqa: E402


class SituationSchemaTest(unittest.TestCase):
    def _base(self, **over):
        kw = dict(task_kind="change", intent="do the thing", subject="coding")
        kw.update(over)
        return sit.Situation(**kw)

    def test_valid_construction(self):
        s = self._base(suggested_kind="refactor", fit="loose", phase="convergent")
        self.assertEqual(s.task_kind, "change")
        self.assertEqual(s.suggested_kind, "refactor")

    def test_rejects_bad_enum_values(self):
        for bad in (dict(task_kind="frobnicate"), dict(subject="cooking"),
                    dict(phase="sideways"), dict(fit="perfect")):
            with self.assertRaises(ValueError):
                self._base(**bad)

    def test_open_fields_are_not_validated(self):
        s = self._base(suggested_kind="provision-infra", label="whatever-noun")
        self.assertEqual(s.label, "whatever-noun")

    def test_classified_and_routed_kind(self):
        clean = self._base(fit="clean")
        self.assertTrue(clean.classified)
        self.assertEqual(clean.routed_kind, "change")
        loose = self._base(fit="loose")
        self.assertTrue(loose.classified)
        self.assertEqual(loose.routed_kind, "change")
        none = self._base(fit="none")
        self.assertFalse(none.classified)
        self.assertEqual(none.routed_kind, sit.UNCLASSIFIED)

    def test_has_gap(self):
        self.assertFalse(self._base(fit="clean").has_gap)
        self.assertTrue(self._base(fit="loose").has_gap)
        self.assertTrue(self._base(fit="none").has_gap)

    def test_to_dict_shape(self):
        s = self._base(suggested_kind="refactor", fit="loose", label="tidy-up",
                       targets=["a.py"], workflow="wf1")
        d = s.to_dict()
        self.assertEqual(set(d), {"task_kind", "suggested_kind", "fit", "intent", "subject",
                                  "phase", "project_shape", "root", "targets", "workflow", "label"})
        self.assertEqual(d["suggested_kind"], "refactor")
        self.assertEqual(d["targets"], ["a.py"])


class SurfaceGapTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".praxis").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def _sit(self, **over):
        kw = dict(task_kind="change", intent="tidy the module", subject="coding")
        kw.update(over)
        return sit.Situation(**kw)

    def test_clean_fit_surfaces_nothing(self):
        s = self._sit(fit="clean", suggested_kind="change")
        self.assertIsNone(sit.surface_task_kind_gap(self.root, s))
        self.assertEqual(journal.gaps(self.root), [])

    def test_loose_fit_records_a_gap(self):
        s = self._sit(fit="loose", suggested_kind="refactor")
        ev = sit.surface_task_kind_gap(self.root, s)
        self.assertIsNotNone(ev)
        gaps = journal.gaps(self.root)
        self.assertEqual(len(gaps), 1)
        g = gaps[0]
        self.assertEqual(g["vocabulary"], "task_kind")
        self.assertEqual(g["chosen"], "change")
        self.assertEqual(g["suggested"], "refactor")
        self.assertEqual(g["fit"], "loose")
        self.assertEqual(g["situation"]["intent"], "tidy the module")

    def test_none_fit_records_a_gap(self):
        ev = sit.surface_task_kind_gap(self.root, self._sit(fit="none", suggested_kind="migrate"))
        self.assertIsNotNone(ev)
        self.assertEqual(journal.gaps(self.root)[0]["fit"], "none")

    def test_recurrence_tallies_in_gap_candidates(self):
        for _ in range(3):
            sit.surface_task_kind_gap(self.root, self._sit(fit="none", suggested_kind="provision-infra"))
        sit.surface_task_kind_gap(self.root, self._sit(fit="loose", suggested_kind="refactor"))
        cands = journal.gap_candidates(self.root)
        top = cands[0]
        self.assertEqual(top["suggested"], "provision-infra")
        self.assertEqual(top["count"], 3)
        self.assertIn("change", top["chosen_as"])

    def test_generic_vocabulary_gap(self):
        ev = sit.surface_gap(self.root, vocabulary="subject", chosen="process",
                             suggested="devops", fit="none", intent="stand up infra")
        self.assertIsNotNone(ev)
        self.assertEqual(journal.gaps(self.root)[0]["vocabulary"], "subject")


if __name__ == "__main__":
    unittest.main()
