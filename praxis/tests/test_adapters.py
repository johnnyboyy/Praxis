import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import adapters  # noqa: E402
import providers as pv  # noqa: E402
from situation import Situation  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
CORPUS_PY = REPO / "corpora" / "scripts" / "corpus.py"


def _sit(**over):
    kw = dict(task_kind="change", intent="do the thing", subject="coding")
    kw.update(over)
    return Situation(**kw)


class AdapterConstructionTest(unittest.TestCase):
    def test_features_mode_builds_feature_provider(self):
        prov = adapters.corpora_provider(REPO, mode="features")
        self.assertIsInstance(prov, pv.CorporaProvider)
        self.assertIn("manifest", prov.capabilities())

    def test_units_mode_builds_provider(self):
        self.assertIsInstance(adapters.corpora_provider(REPO, mode="units"), pv.CorporaProvider)

    def test_bad_mode_raises(self):
        with self.assertRaises(ValueError):
            adapters.corpora_provider(REPO, mode="sideways")

    def test_missing_corpus_degrades_to_empty(self):
        prov = adapters.corpora_provider(REPO, corpus_py="/no/such/corpus.py", mode="features")
        r = prov.compose(_sit(subject="coding", root=str(REPO)))
        self.assertEqual(r["domains"], [])


@unittest.skipUnless(CORPUS_PY.is_file(), "corpora corpus.py not present")
class DirectBindingComposeTest(unittest.TestCase):
    """The engine-plugin hop collapsed: compose straight through corpus.py, no praxis engine.py."""

    def test_feature_compose_via_direct_corpus_call(self):
        prov = adapters.corpora_provider(REPO, mode="features")
        r = prov.compose(_sit(task_kind="explore", subject="coding", root=str(REPO),
                              project_shape={"language": "python", "framework": "none"}))
        self.assertIn("prose-craft", r["domains"])
        self.assertIn("coding-general", r["domains"])
        self.assertNotIn("coding-nextjs", r["domains"])
        self.assertTrue(r["artifacts"])
        self.assertTrue(all(a["provenance"] == "corpora" for a in r["artifacts"]))

    def test_units_mode_composes_by_label(self):
        prov = adapters.corpora_provider(REPO, mode="units")
        r = prov.compose(_sit(subject="coding", label="scan-architecture", root=str(REPO)))
        self.assertIn("prose-craft", r["domains"])


if __name__ == "__main__":
    unittest.main()
