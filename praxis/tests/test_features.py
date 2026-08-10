import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import providers as pv  # noqa: E402
from situation import Situation  # noqa: E402


def _sit(**over):
    kw = dict(task_kind="change", intent="do the thing", subject="coding")
    kw.update(over)
    return Situation(**kw)


# A stub domain manifest in corpora's `manifest` output shape.
MANIFEST = [
    {"name": "prose-craft", "subject": "process", "universal": True, "applies_when": []},
    {"name": "coding-general", "subject": "coding", "universal": False, "applies_when": []},
    {"name": "coding-nextjs", "subject": "coding", "universal": False,
     "applies_when": [{"framework": ["nextjs"]}]},
    {"name": "coding-ts", "subject": "coding", "universal": False,
     "applies_when": [{"language": ["typescript", "javascript"]}]},
    {"name": "design-visual", "subject": "design", "universal": False, "applies_when": []},
]


class SelectByFeaturesTest(unittest.TestCase):
    def test_universal_always_selected(self):
        got = pv.select_by_features(MANIFEST, _sit(subject="prose", project_shape={}))
        self.assertIn("prose-craft", got)

    def test_subject_gates_non_universal(self):
        # subject=coding, python/none shape ⇒ universal + coding domains whose predicates hold.
        got = pv.select_by_features(
            MANIFEST, _sit(subject="coding", project_shape={"language": "python", "framework": "none"}))
        self.assertEqual(got, ["coding-general", "prose-craft"])
        self.assertNotIn("design-visual", got)     # wrong subject
        self.assertNotIn("coding-nextjs", got)      # framework predicate fails
        self.assertNotIn("coding-ts", got)          # language predicate fails

    def test_shape_predicate_admits_matching_domains(self):
        got = pv.select_by_features(
            MANIFEST, _sit(subject="coding", project_shape={"language": "typescript", "framework": "nextjs"}))
        self.assertEqual(set(got), {"prose-craft", "coding-general", "coding-nextjs", "coding-ts"})

    def test_design_subject_selects_design_domains(self):
        got = pv.select_by_features(MANIFEST, _sit(subject="design", project_shape={}))
        self.assertEqual(set(got), {"prose-craft", "design-visual"})

    def test_fit_none_is_universals_only(self):
        # unclassified ⇒ never a forced feature match, even though subject/shape would qualify.
        got = pv.select_by_features(
            MANIFEST, _sit(subject="coding", fit="none",
                           project_shape={"language": "python", "framework": "none"}))
        self.assertEqual(got, ["prose-craft"])


class FeatureProviderTest(unittest.TestCase):
    def test_compose_uses_features_not_unit_of_work(self):
        # No select_fn at all — feature mode must not touch the unit-of-work path.
        prov = pv.CorporaProvider(manifest_fn=lambda root: MANIFEST)
        r = prov.compose(_sit(subject="coding", label="implement-feature",
                              project_shape={"language": "python", "framework": "none"}))
        self.assertEqual(r["domains"], ["coding-general", "prose-craft"])

    def test_feature_mode_with_parts_builds_artifacts(self):
        prov = pv.CorporaProvider(
            manifest_fn=lambda root: MANIFEST,
            parts_fn=lambda root, doms: {"parts": [{"slot": "domains", "body": ",".join(doms)}],
                                         "problems": []})
        r = prov.compose(_sit(subject="design", project_shape={}))
        self.assertEqual(r["artifacts"][0]["provenance"], "corpora")
        self.assertIn("design-visual", r["artifacts"][0]["body"])

    def test_requires_a_selection_mode(self):
        with self.assertRaises(ValueError):
            pv.CorporaProvider()   # neither select_fn nor manifest_fn


# ── The real decoupling: feature selection over the actual corpora manifest ──────────────────────
def _corpora_manifest_fn():
    """Build a manifest_fn over the real corpora engine, or None if unavailable."""
    repo = Path(__file__).resolve().parents[2]
    manifest_path = repo / "corpora" / "praxis-plugin" / "engine" / "plugins" / "corpora.json"
    if not manifest_path.is_file():
        return None
    sys.path.insert(0, str(repo / "praxis" / "scripts"))
    try:
        import engine  # noqa: E402
    except Exception:
        return None
    m = engine.load_manifest(manifest_path)
    if "manifest" not in m.get("capabilities", {}):
        return None

    def manifest_fn(root):
        payload, _ = engine.call_json(m, "manifest", {"root": root, "json": True})
        return (payload or {}).get("domains", [])

    return manifest_fn


class RealFeatureSelectionTest(unittest.TestCase):
    def setUp(self):
        self.manifest_fn = _corpora_manifest_fn()
        if self.manifest_fn is None:
            self.skipTest("corpora manifest capability not loadable")
        self.repo = str(Path(__file__).resolve().parents[2])

    def test_feature_select_over_real_corpora(self):
        prov = pv.CorporaProvider(manifest_fn=self.manifest_fn)
        # subject=coding against the self-host shape (python / no framework): universal prose-craft
        # plus the framework-agnostic coding domains; NO design domains, NO framework-gated ones.
        r = prov.compose(_sit(subject="coding", root=self.repo,
                              project_shape={"language": "python", "framework": "none"}))
        self.assertIn("prose-craft", r["domains"])
        self.assertIn("coding-general", r["domains"])
        self.assertNotIn("coding-nextjs", r["domains"])   # framework predicate fails on this shape
        # no unit-of-work string was involved: selection is purely feature-driven.


if __name__ == "__main__":
    unittest.main()
