"""Server-side regressions. Finding 6: compose_spawn is a read path, so with build_frame's
marker-touch side effect removed (and `_preserved_markers` deleted) it must leave a pre-existing
JSON frame marker byte-identical. Finding 10: close_work/work_status resolve the governing root via
root_tree.governing_root_above's upward walk, so a search_base deep inside a root resolves even
though a downward find_roots(base) scan would not see the root above it. The server lives out of this
repo; skipped cleanly when it or its mcp dependency is unavailable.

Run: python3 -m unittest discover -s praxis/tests
"""

import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SERVER = Path(__file__).resolve().parent.parent / "front-door" / "server.py"
SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import frame  # noqa: E402  repo version, cached before server imports it
import root_tree  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "conductor"))
import journal  # noqa: E402
from _stub_engine import write_stub, write_plugin_slot, SPAWN_PARTS_CAP  # noqa: E402

server = None
if SERVER.is_file():
    try:
        spec = importlib.util.spec_from_file_location("praxis_front_door_server", SERVER)
        server = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(server)
    except Exception:
        server = None


@unittest.skipUnless(server is not None, "praxis-front-door server.py or its mcp dependency unavailable")
class ComposeSpawnMarkerPreserved(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.root = self.tmp / "app"
        (self.root / "praxis").mkdir(parents=True)
        (self.root / "praxis" / "config.md").write_text("## project-shape\nname: app\n")
        (self.root / "src").mkdir()
        (self.root / "src" / "x.ts").write_text("// x\n")
        stub = write_stub(self.tmp)
        write_plugin_slot(self.root / "praxis" / "engine", stub, extra_caps=[SPAWN_PARTS_CAP])
        os.environ["STUB_DOMAINS"] = "alpha,beta"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)
        os.environ.pop("STUB_DOMAINS", None)

    def test_compose_spawn_preserves_existing_json_marker(self):
        marker = root_tree.praxis_dir(self.root) / frame.FRAME_MARKER_NAME
        original = '{"timestamp": 99.0, "unit_of_work": "implement-feature", "surface": ["src/*"]}'
        marker.write_text(original)
        out = server.compose_spawn("implement-feature", target="src/x.ts", search_base=str(self.root))
        # compose_spawn must have run a real compose (payload written), not errored out early.
        self.assertIn('"composition"', out)
        self.assertEqual(marker.read_text(), original)


@unittest.skipUnless(server is not None, "praxis-front-door server.py or its mcp dependency unavailable")
class GoverningRootAboveResolution(unittest.TestCase):
    """Finding 10: a search_base DEEP inside a root resolves the root via the upward walk, where the
    old find_roots(base) + nearest_root pairing (a downward scan of base's subtree) saw no root."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.root = self.tmp / "app"
        (self.root / "praxis").mkdir(parents=True)
        (self.root / "praxis" / "config.md").write_text("## project-shape\nname: app\n")
        self.deep = self.root / "src" / "nested" / "leaf"
        self.deep.mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_work_status_resolves_root_above_a_deep_search_base(self):
        out = json.loads(server.work_status(search_base=str(self.deep)))
        self.assertEqual(out.get("root"), str(self.root.resolve()))

    def test_close_work_resolves_root_above_a_deep_search_base(self):
        out = json.loads(server.close_work(search_base=str(self.deep)))
        self.assertEqual(out.get("root"), str(self.root.resolve()))


@unittest.skipUnless(server is not None, "praxis-front-door server.py or its mcp dependency unavailable")
class BeginWorkToolFunction(unittest.TestCase):
    """Finding 16(b): begin_work's tool-function behaviors beyond the marker-preservation case —
    the spawn default, the no-engine inline degrade, and the lease out-of-surface warning."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.root = self.tmp / "app"
        (self.root / "praxis").mkdir(parents=True)
        (self.root / "praxis" / "config.md").write_text("## project-shape\nname: app\n")
        (self.root / "src").mkdir()
        (self.root / "src" / "x.ts").write_text("// x\n")
        (self.root / "docs").mkdir()
        (self.root / "docs" / "y.md").write_text("# y\n")
        self.marker = root_tree.praxis_dir(self.root) / frame.FRAME_MARKER_NAME

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)
        os.environ.pop("STUB_DOMAINS", None)

    def _register_engine(self):
        stub = write_stub(self.tmp)
        write_plugin_slot(self.root / "praxis" / "engine", stub)
        os.environ["STUB_DOMAINS"] = "alpha,beta"

    def _units(self, body: str):
        (root_tree.praxis_dir(self.root) / "units.md").write_text(body)

    def test_begin_work_defaults_to_spawn_and_records_marker_fields(self):
        self._register_engine()
        self._units("## implement-feature\nedit-surface: src/*\noutput: the working code\n")
        out = json.loads(server.begin_work("implement-feature", target="src/x.ts",
                                           search_base=str(self.root)))
        self.assertIn("spawn (defaulted)", out.get("execution", ""))
        self.assertIn("compose_spawn", out.get("delivery", ""))
        marker = json.loads(self.marker.read_text())
        self.assertEqual(marker["delivery"], "spawn")
        self.assertEqual(marker["surface"], ["src/*"])
        self.assertEqual(marker["output"], "the working code")
        self.assertEqual(marker["unit_of_work"], "implement-feature")
        self.assertEqual(marker["composition"], ["alpha", "beta"])

    def test_inline_without_engine_degrades_to_facts_with_open_gate(self):
        # No engine registered ⇒ no composition ⇒ delivery degrades to facts and the gate opens on
        # the journal's open unit alone (no payload read demanded that can never happen).
        out = json.loads(server.begin_work("implement-feature", target="src/x.ts",
                                           execution="inline", search_base=str(self.root)))
        self.assertEqual(out["delivery"], "facts — no composition available to deliver")
        self.assertIn("open for this unit", out["gate"])

    def test_lease_warning_lists_out_of_surface_given_paths(self):
        self._units("## scan-architecture\nedit-surface: docs/*\noutput: the report\n")
        out = json.loads(server.begin_work("scan-architecture", target="src/x.ts",
                                           search_base=str(self.root)))
        warnings = " ".join(out.get("warnings", []))
        self.assertIn("LEASE:", warnings)
        self.assertIn("src/x.ts", warnings)

    def test_lease_no_warning_when_given_paths_in_surface(self):
        self._units("## scan-architecture\nedit-surface: docs/*\noutput: the report\n")
        out = json.loads(server.begin_work("scan-architecture", target="docs/y.md",
                                           search_base=str(self.root)))
        self.assertNotIn("LEASE:", " ".join(out.get("warnings", [])))

    def test_marker_keys_match_MARKER_FIELDS_constant(self):
        # Gap 6, against the live system: begin_work's actual written marker keys must equal
        # frame.MARKER_FIELDS plus the timestamp every marker carries — a field added to
        # marker_data without updating the constant (or vice versa) fails this.
        self._register_engine()
        self._units("## implement-feature\nedit-surface: src/*\noutput: the working code\n")
        server.begin_work("implement-feature", target="src/x.ts", search_base=str(self.root))
        marker = json.loads(self.marker.read_text())
        self.assertEqual(set(marker.keys()), set(frame.MARKER_FIELDS) | {"timestamp"})


@unittest.skipUnless(server is not None, "praxis-front-door server.py or its mcp dependency unavailable")
class InlineRejectionRules(unittest.TestCase):
    """The two mechanical inline gates from the motors-and-controls run review: cross-root inline
    (a seat root never works inside another root) and the per-unit `execution: spawn` policy in
    units.md. Both reject at begin_work — no marker written, gate closed — because any per-call
    judgment about 'trivial enough for inline' loses to the always-available 'context already
    loaded' rationalization."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.parent = self.tmp / "mono"
        (self.parent / "praxis").mkdir(parents=True)
        (self.parent / "praxis" / "config.md").write_text("## project-shape\nname: mono\n")
        self.child = self.parent / "apps" / "app"
        (self.child / "praxis").mkdir(parents=True)
        (self.child / "praxis" / "config.md").write_text("## project-shape\nname: app\n")
        (self.child / "src").mkdir()
        (self.child / "src" / "x.ts").write_text("// x\n")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def child_marker(self):
        return root_tree.praxis_dir(self.child) / frame.FRAME_MARKER_NAME

    def test_cross_root_inline_rejected_no_marker_written(self):
        out = json.loads(server.begin_work(
            "implement-feature", target=str(self.child / "src" / "x.ts"),
            execution="inline", search_base=str(self.parent)))
        self.assertIn("execution_rejected", out)
        self.assertIn("seated in", out["execution_rejected"])
        self.assertIn("compose_spawn", out["execution_rejected"])
        self.assertIn("closed", out["gate"])
        self.assertFalse(self.child_marker().is_file())

    def test_cross_root_spawn_is_not_rejected(self):
        out = json.loads(server.begin_work(
            "implement-feature", target=str(self.child / "src" / "x.ts"),
            execution="spawn", search_base=str(self.parent)))
        self.assertNotIn("execution_rejected", out)
        self.assertTrue(self.child_marker().is_file())

    def test_reseating_search_base_in_child_root_allows_inline(self):
        out = json.loads(server.begin_work(
            "implement-feature", target=str(self.child / "src" / "x.ts"),
            execution="inline", search_base=str(self.child)))
        self.assertNotIn("execution_rejected", out)
        self.assertTrue(self.child_marker().is_file())

    def test_units_md_spawn_policy_rejects_inline_same_root(self):
        (root_tree.praxis_dir(self.child) / "units.md").write_text(
            "## implement-feature\nedit-surface: src/*\noutput: working code\nexecution: spawn\n")
        out = json.loads(server.begin_work(
            "implement-feature", target=str(self.child / "src" / "x.ts"),
            execution="inline", search_base=str(self.child)))
        self.assertIn("execution_rejected", out)
        self.assertIn("units.md", out["execution_rejected"])
        self.assertFalse(self.child_marker().is_file())

    def test_units_md_without_policy_leaves_inline_available(self):
        (root_tree.praxis_dir(self.child) / "units.md").write_text(
            "## implement-feature\nedit-surface: src/*\noutput: working code\n")
        out = json.loads(server.begin_work(
            "implement-feature", target=str(self.child / "src" / "x.ts"),
            execution="inline", search_base=str(self.child)))
        self.assertNotIn("execution_rejected", out)


@unittest.skipUnless(server is not None, "praxis-front-door server.py or its mcp dependency unavailable")
class UnclosedPriorFrameSurfaced(unittest.TestCase):
    """Close-ceremony debt is surfaced at the next begin_work instead of silently expiring by
    staleness (observed live: an implement-feature unit was never closed, its tree left dirty,
    and the next session's first act was mopping it up with no prompt from the front door)."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.root = self.tmp / "app"
        (self.root / "praxis").mkdir(parents=True)
        (self.root / "praxis" / "config.md").write_text("## project-shape\nname: app\n")
        (self.root / "src").mkdir()
        (self.root / "src" / "x.ts").write_text("// x\n")
        self.marker = root_tree.praxis_dir(self.root) / frame.FRAME_MARKER_NAME

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def begin(self, unit="implement-feature"):
        return json.loads(server.begin_work(
            unit, target=str(self.root / "src" / "x.ts"), search_base=str(self.root)))

    def test_stale_open_marker_surfaces_unclosed_prior(self):
        self.marker.write_text(json.dumps(
            {"timestamp": 99.0, "unit_of_work": "implement-feature"}))
        out = self.begin()
        self.assertIn("unclosed_prior", out)
        self.assertEqual(out["unclosed_prior"]["unit_of_work"], "implement-feature")
        self.assertTrue(any("UNCLOSED PRIOR UNIT" in w for w in out.get("warnings", [])))

    def test_fresh_open_marker_with_different_unit_surfaces_debt(self):
        import time as _t
        self.marker.write_text(json.dumps(
            {"timestamp": _t.time(), "unit_of_work": "design-ux-flow"}))
        out = self.begin("implement-feature")
        self.assertIn("unclosed_prior", out)
        self.assertEqual(out["unclosed_prior"]["unit_of_work"], "design-ux-flow")

    def test_fresh_same_unit_reframe_is_not_debt(self):
        import time as _t
        self.marker.write_text(json.dumps(
            {"timestamp": _t.time(), "unit_of_work": "implement-feature"}))
        out = self.begin("implement-feature")
        self.assertNotIn("unclosed_prior", out)

    def test_closed_marker_is_not_debt(self):
        self.marker.write_text(json.dumps(
            {"timestamp": 99.0, "closed": True, "prior_unit_of_work": "implement-feature"}))
        out = self.begin()
        self.assertNotIn("unclosed_prior", out)


@unittest.skipUnless(server is not None, "praxis-front-door server.py or its mcp dependency unavailable")
class CloseWorkToolFunction(unittest.TestCase):
    """Finding 16(b): close_work records the prior unit from a JSON marker and tolerates a
    bare-float marker (the plain frame.py CLI path) without crashing."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.root = self.tmp / "app"
        (self.root / "praxis").mkdir(parents=True)
        (self.root / "praxis" / "config.md").write_text("## project-shape\nname: app\n")
        self.marker = root_tree.praxis_dir(self.root) / frame.FRAME_MARKER_NAME

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_close_work_records_prior_unit_from_json_marker(self):
        self.marker.write_text(json.dumps({"timestamp": 1.0, "unit_of_work": "implement-feature"}))
        out = json.loads(server.close_work(search_base=str(self.root)))
        self.assertTrue(out["closed"])
        self.assertEqual(out["prior_unit_of_work"], "implement-feature")
        # Marker now carries the closed flag so the next edit forces a fresh begin_work.
        self.assertTrue(json.loads(self.marker.read_text())["closed"])

    def test_close_work_tolerates_bare_float_marker(self):
        self.marker.write_text("1234567890.0")
        out = json.loads(server.close_work(search_base=str(self.root)))
        self.assertTrue(out["closed"])
        self.assertIsNone(out["prior_unit_of_work"])


@unittest.skipUnless(server is not None, "praxis-front-door server.py or its mcp dependency unavailable")
class DecomposeWritesNoMarker(unittest.TestCase):
    """Finding 16(b): a two-root (spanning) begin_work decomposes — no single governing root, so no
    frame marker is written and the gate stays shut for each piece."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.base = self.tmp / "mono"
        self.a = self.base / "app"
        self.b = self.base / "admin"
        for r in (self.a, self.b):
            (r / "praxis").mkdir(parents=True)
            (r / "praxis" / "config.md").write_text("## project-shape\nname: r\n")
            (r / "src").mkdir()
            (r / "src" / "f.ts").write_text("// f\n")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_spanning_call_writes_no_marker(self):
        out = json.loads(server.begin_work(
            "implement-feature",
            files=[str(self.a / "src" / "f.ts"), str(self.b / "src" / "f.ts")],
            search_base=str(self.base)))
        self.assertIsNone(out["root"])
        self.assertIn("closed", out["gate"])
        self.assertFalse((root_tree.praxis_dir(self.a) / frame.FRAME_MARKER_NAME).exists())
        self.assertFalse((root_tree.praxis_dir(self.b) / frame.FRAME_MARKER_NAME).exists())


@unittest.skipUnless(server is not None, "praxis-front-door server.py or its mcp dependency unavailable")
class JournalBridge(unittest.TestCase):
    """P2 bridge (docs/CONDUCTOR-PLAN.md): begin_work writes a unit.framed event and close_work a
    unit.closed event, so conductor/journal.open_unit has state for the edit gate to read."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.root = self.tmp / "app"
        (self.root / ".praxis").mkdir(parents=True)
        (self.root / ".praxis" / "config.md").write_text("## project-shape\nname: app\n")
        (self.root / "src").mkdir()
        (self.root / "src" / "x.ts").write_text("// x\n")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_begin_work_opens_a_journal_unit(self):
        out = json.loads(server.begin_work("implement-feature", target="src/x.ts",
                                           execution="inline", search_base=str(self.root)))
        unit_id = out["unit"]
        opened = journal.open_unit(self.root)
        self.assertIsNotNone(opened)
        self.assertEqual(opened["unit"], unit_id)
        self.assertEqual(opened["state"], "framed")
        self.assertEqual(opened["last"]["unit_of_work"], "implement-feature")

    def test_close_work_closes_the_open_journal_unit(self):
        server.begin_work("implement-feature", target="src/x.ts", execution="inline",
                          search_base=str(self.root))
        self.assertIsNotNone(journal.open_unit(self.root))
        server.close_work(search_base=str(self.root))
        self.assertIsNone(journal.open_unit(self.root))


if __name__ == "__main__":
    unittest.main()
