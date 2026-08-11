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


class _StubProvider:
    """A minimal composing provider for exercising the generic consult() seam without an engine."""

    def __init__(self, domains):
        self._domains = list(domains)

    def compose(self, situation):
        stance = situation.phase if situation.phase in ("divergent", "convergent") else None
        return {"artifacts": [], "stance": stance, "note": "ok",
                "domains": list(self._domains), "routed_kind": situation.routed_kind}

    def ratify(self, proposal):
        return {"verdict": "unavailable"}

    def retrospect(self, scope):
        return {"signals": []}

    def capabilities(self):
        return []


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


class ProviderForTest(unittest.TestCase):
    def test_defaults_to_null_provider(self):
        self.assertIsInstance(pv.provider_for("/any/root"), pv.NullProvider)


class ConsultTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".praxis").mkdir()
        self.prov = _StubProvider(["prose-craft"])

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


if __name__ == "__main__":
    unittest.main()
