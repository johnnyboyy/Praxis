import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import journal  # noqa: E402
import providers as pv  # noqa: E402
from situation import Situation  # noqa: E402


def _sit(**over):
    kw = dict(task_kind="change", intent="do the thing", subject="coding")
    kw.update(over)
    return Situation(**kw)


class NullProviderTest(unittest.TestCase):
    def test_compose_degrades_to_facts(self):
        r = pv.NullProvider().compose(_sit())
        self.assertEqual(r["artifacts"], [])
        self.assertIsNone(r["stance"])
        self.assertIn("no provider", r["note"])
        self.assertEqual(r["routed_kind"], "change")

    def test_capabilities_and_housekeeping_degrade(self):
        n = pv.NullProvider()
        self.assertEqual(n.capabilities(), [])
        self.assertEqual(n.ratify({})["verdict"], "unavailable")
        self.assertEqual(n.retrospect({})["signals"], [])

    def test_satisfies_provider_protocol(self):
        self.assertIsInstance(pv.NullProvider(), pv.Provider)


class CorporaProviderComposeTest(unittest.TestCase):
    def test_keys_select_on_label_when_labeled(self):
        seen = {}

        def select(root, uow):
            seen["uow"] = uow
            return {"domains": ["testing"], "warnings": []}

        prov = pv.CorporaProvider(select)
        r = prov.compose(_sit(fit="clean", label="scaffold-tests", root="/r"))
        self.assertEqual(seen["uow"], "scaffold-tests")
        self.assertEqual(r["domains"], ["testing"])
        self.assertEqual(r["artifacts"], [])

    def test_falls_back_to_task_kind_when_unlabeled(self):
        seen = {}

        def select(root, uow):
            seen["uow"] = uow
            return {"domains": [], "warnings": []}

        pv.CorporaProvider(select).compose(_sit(fit="clean", label=None))
        self.assertEqual(seen["uow"], "change")

    def test_fit_none_routes_to_unclassified(self):
        seen = {}

        def select(root, uow):
            seen["uow"] = uow
            return {"domains": ["prose-craft"], "warnings": ["unit-of-work 'unclassified' matches no domain"]}

        r = pv.CorporaProvider(select).compose(_sit(fit="none", label="implement-feature"))
        self.assertEqual(seen["uow"], "unclassified")
        self.assertEqual(r["routed_kind"], "unclassified")
        self.assertIn("matches no domain", r["note"])

    def test_parts_become_artifacts(self):
        def select(root, uow):
            return {"domains": ["a", "b"], "warnings": []}

        def parts(root, domains):
            self.assertEqual(domains, ["a", "b"])
            return {"parts": [{"slot": "domains", "body": "BODY"}], "problems": []}

        r = pv.CorporaProvider(select, parts).compose(_sit(fit="clean", label="x"))
        self.assertEqual(len(r["artifacts"]), 1)
        self.assertEqual(r["artifacts"][0], {"slot": "domains", "body": "BODY", "provenance": "corpora"})

    def test_stance_from_phase(self):
        select = lambda root, uow: {"domains": [], "warnings": []}
        self.assertEqual(pv.CorporaProvider(select).compose(_sit(phase="divergent"))["stance"],
                         "divergent")
        self.assertIsNone(pv.CorporaProvider(select).compose(_sit(phase="none"))["stance"])

    def test_capabilities_reported(self):
        prov = pv.CorporaProvider(lambda r, u: {}, capabilities=["compose", "ratify", "retrospect"])
        self.assertEqual(prov.capabilities(), ["compose", "ratify", "retrospect"])


class ConsultTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".praxis").mkdir()
        self.prov = pv.CorporaProvider(lambda r, u: {"domains": ["prose-craft"], "warnings": []})

    def tearDown(self):
        self.tmp.cleanup()

    def test_clean_fit_composes_without_surfacing(self):
        r = pv.consult(self.prov, _sit(fit="clean", suggested_kind="change"), root=self.root)
        self.assertFalse(r["gap_surfaced"])
        self.assertEqual(journal.gaps(self.root), [])
        self.assertEqual(r["domains"], ["prose-craft"])

    def test_loose_fit_surfaces_and_composes(self):
        r = pv.consult(self.prov, _sit(fit="loose", suggested_kind="refactor"), root=self.root)
        self.assertTrue(r["gap_surfaced"])
        self.assertEqual(len(journal.gaps(self.root)), 1)
        self.assertEqual(r["domains"], ["prose-craft"])

    def test_none_fit_surfaces_and_routes_unclassified(self):
        r = pv.consult(self.prov, _sit(fit="none", suggested_kind="migrate"), root=self.root)
        self.assertTrue(r["gap_surfaced"])
        self.assertEqual(r["routed_kind"], "unclassified")

    def test_no_root_records_nothing_but_reflects_routing(self):
        r = pv.consult(self.prov, _sit(fit="none", suggested_kind="migrate"), root=None)
        self.assertFalse(r["gap_surfaced"])
        self.assertEqual(r["routed_kind"], "unclassified")


def _corpora_binding():
    """Build (select_fn, parts_fn, capabilities) over the real corpora engine, or None if
    unavailable. Imports praxis's engine binding — a cross-layer reach the TEST is allowed (the
    conductor core itself never does this)."""
    repo = Path(__file__).resolve().parents[2]
    manifest_path = repo / "corpora" / "praxis-plugin" / "engine" / "plugins" / "corpora.json"
    if not manifest_path.is_file():
        return None
    sys.path.insert(0, str(repo / "praxis" / "scripts"))
    try:
        import engine  # noqa: E402
    except Exception:
        return None
    manifest = engine.load_manifest(manifest_path)

    def select(root, uow):
        payload, _ = engine.call_json(manifest, "compose",
                                      {"root": root, "unit_of_work": uow, "json": True})
        if payload is None:
            return {"domains": [], "warnings": []}
        return {"domains": payload.get("domains", []), "warnings": payload.get("warnings", [])}

    def parts(root, domains):
        payload, _ = engine.call_json(manifest, "spawn-parts",
                                      {"root": root, "domains": ",".join(domains), "json": True})
        if payload is None:
            return {"parts": [], "problems": []}
        return {"parts": payload.get("parts", []), "problems": payload.get("problems", [])}

    caps = list(manifest.get("capabilities", {}).keys())
    return select, parts, caps


class RealCorporaWrapTest(unittest.TestCase):
    def setUp(self):
        binding = _corpora_binding()
        if binding is None:
            self.skipTest("corpora engine manifest not loadable")
        self.select, self.parts, self.caps = binding
        self.repo = str(Path(__file__).resolve().parents[2])

    def test_wraps_real_corpora_compose(self):
        prov = pv.CorporaProvider(self.select, self.parts, capabilities=self.caps)
        s = _sit(task_kind="explore", fit="clean", label="scan-architecture",
                 subject="coding", root=self.repo)
        r = prov.compose(s)
        self.assertIn("prose-craft", r["domains"], f"domains={r['domains']}")
        self.assertTrue(r["artifacts"], "expected composed domain bodies as artifacts")
        self.assertTrue(all(a["provenance"] == "corpora" for a in r["artifacts"]))
        self.assertIn("compose", self.caps)


if __name__ == "__main__":
    unittest.main()
