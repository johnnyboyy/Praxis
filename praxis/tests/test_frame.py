"""Tests for frame. Run with: python3 -m unittest discover -s praxis/tests -v

Composition is the engine's job; these tests cover praxis's deterministic parts — root resolution,
the span/decompose verdict, and graceful degradation when NO engine is registered — plus one check
that a registered (generic stub) engine's domain set is relayed. Zero real engine is involved.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import frame  # noqa: E402
import engine  # noqa: E402
import root_tree  # noqa: E402
from _stub_engine import write_stub, stub_manifest, write_plugin_slot  # noqa: E402


def mkroot(base: Path, rel: str, name: str | None = None) -> Path:
    d = base / rel
    (d / "praxis").mkdir(parents=True, exist_ok=True)
    body = "## project-shape\n" + (f"name: {name}\n" if name else "")
    (d / "praxis" / "config.md").write_text(body)
    return d


class FrameTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_single_root_resolves(self):
        mkroot(self.tmp, "app", name="app")
        f = frame.build_frame(self.tmp, "app/src/x.ts", [], "implement-feature", None)
        self.assertEqual(f["verdict"], "single-root")
        self.assertEqual(len(f["roots"]), 1)
        self.assertEqual(f["roots"][0]["name"], "app")

    def test_spanning_roots_says_decompose_and_skips_composition(self):
        mkroot(self.tmp, "apps/a", name="a")
        mkroot(self.tmp, "apps/b", name="b")
        f = frame.build_frame(self.tmp, None,
                              ["apps/a/src/x.ts", "apps/b/src/y.ts"], "implement-feature", None)
        self.assertTrue(f["spans_multiple_roots"])
        self.assertEqual(f["verdict"], "decompose")
        self.assertIsNone(f["composition"])  # never compose a cross-root task as one

    def test_no_engine_registered_degrades_gracefully(self):
        # Root facts must survive an empty engine slot — praxis does not depend on an engine.
        mkroot(self.tmp, "app", name="app")
        f = frame.build_frame(self.tmp, "app/src/x.ts", [], "implement-feature", None)
        self.assertEqual(f["roots"][0]["name"], "app")
        self.assertIsNone(f["composition"])
        self.assertIn("no engine registered", f["composition_note"])

    def test_no_unit_of_work_defers_composition(self):
        mkroot(self.tmp, "app", name="app")
        f = frame.build_frame(self.tmp, "app/src/x.ts", [], None, None)
        self.assertIsNone(f["composition"])
        self.assertIn("unit-of-work not given", f["composition_note"])

    def test_registered_engine_composition_is_relayed(self):
        # A generic stub engine returns a domain set; frame relays it verbatim.
        mkroot(self.tmp, "app", name="app")
        stub = write_stub(self.tmp)
        os.environ["STUB_DOMAINS"] = "alpha,beta"
        try:
            f = frame.build_frame(self.tmp, "app/src/x.ts", [], "implement-feature",
                                  stub_manifest(stub))
            self.assertEqual(f["composition"], ["alpha", "beta"])
            self.assertEqual(f["composition_note"], "ok")
        finally:
            os.environ.pop("STUB_DOMAINS", None)


class MarkerSideEffectTests(unittest.TestCase):
    """build_frame is facts-only: it must never touch the freshness marker. The write side of
    framing lives in the CLI main (bare marker) and the MCP server's begin_work (JSON marker)."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _marker(self, root: Path) -> Path:
        return root_tree.praxis_dir(root) / frame.FRAME_MARKER_NAME

    def test_build_frame_leaves_existing_marker_byte_identical(self):
        root = mkroot(self.tmp, "app", name="app")
        marker = self._marker(root)
        original = json.dumps({"timestamp": 123.0, "unit_of_work": "implement-feature"})
        marker.write_text(original)
        frame.build_frame(self.tmp, "app/src/x.ts", [], "implement-feature", None)
        self.assertEqual(marker.read_text(), original)

    def test_build_frame_creates_no_marker_where_absent(self):
        root = mkroot(self.tmp, "app", name="app")
        marker = self._marker(root)
        self.assertFalse(marker.exists())
        frame.build_frame(self.tmp, "app/src/x.ts", [], "implement-feature", None)
        self.assertFalse(marker.exists())

    def test_cli_main_writes_bare_marker(self):
        root = mkroot(self.tmp, "app", name="app")
        marker = self._marker(root)
        r = subprocess.run(
            [sys.executable, str(SCRIPTS / "frame.py"), "--from", str(self.tmp),
             "--target", "app/src/x.ts", "--unit-of-work", "implement-feature"],
            capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(marker.is_file())
        # Bare-timestamp form the gate hook's backward-compat branch reads: a plain float.
        self.assertIsInstance(json.loads(marker.read_text()), float)


class SizingTests(unittest.TestCase):
    """Stage-1 framing front door: the deterministic sizing signals, the size floor, and the
    assumption-relay list — the facts the framing phase sizes and relays on top of."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_single_root_known_uow_is_by_judgment(self):
        mkroot(self.tmp, "app", name="app")
        f = frame.build_frame(self.tmp, "app/src/x.ts", [], "implement-feature", None)
        self.assertEqual(f["size_floor"], "by-judgment")   # facts don't force the size; phase decides
        s = f["size_signals"]
        self.assertEqual((s["target_count"], s["roots_spanned"], s["unit_of_work_known"]), (1, 1, True))
        self.assertEqual(s["unrouted_count"], 0)
        self.assertTrue(any("governing root: app" in a for a in f["assumptions"]))
        self.assertTrue(any("unit-of-work: implement-feature" in a for a in f["assumptions"]))

    def test_spanning_roots_size_floor_is_decompose(self):
        mkroot(self.tmp, "apps/a", name="a")
        mkroot(self.tmp, "apps/b", name="b")
        f = frame.build_frame(self.tmp, None, ["apps/a/x.ts", "apps/b/y.ts"], "implement-feature", None)
        self.assertEqual(f["size_floor"], "decompose")
        self.assertEqual(f["size_signals"]["roots_spanned"], 2)
        self.assertTrue(any("decomposing into 2" in a for a in f["assumptions"]))

    def test_no_unit_of_work_is_underspecified(self):
        mkroot(self.tmp, "app", name="app")
        f = frame.build_frame(self.tmp, "app/src/x.ts", [], None, None)
        self.assertEqual(f["size_floor"], "underspecified")
        self.assertFalse(f["size_signals"]["unit_of_work_known"])
        self.assertTrue(any("unit-of-work: undecided" in a for a in f["assumptions"]))

    def test_unrouted_target_is_underspecified_and_surfaced(self):
        mkroot(self.tmp, "app", name="app")
        # a file under no root → unrouted; the trivial/execute path can't be reached on facts alone
        f = frame.build_frame(self.tmp, "loose/file.ts", [], "implement-feature", None)
        self.assertEqual(f["size_floor"], "underspecified")
        self.assertEqual(f["size_signals"]["unrouted_count"], 1)
        self.assertTrue(any("outside any root" in a for a in f["assumptions"]))

    def test_composition_size_reflects_engine_result(self):
        mkroot(self.tmp, "app", name="app")
        stub = write_stub(self.tmp)
        os.environ["STUB_DOMAINS"] = "alpha,beta,gamma"
        try:
            f = frame.build_frame(self.tmp, "app/src/x.ts", [], "implement-feature", stub_manifest(stub))
            self.assertEqual(f["size_signals"]["composition_size"], 3)
        finally:
            os.environ.pop("STUB_DOMAINS", None)


class CloseFrameMarkerStampClearing(unittest.TestCase):
    """Gap 5: close_frame_marker clears every session's stamp for the root — not just one — since
    the gate checks the stamp BEFORE it ever looks at the marker, so a closed marker with a
    surviving stamp from another (or even the same) session left the gate open regardless."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.tmpdir_env = self.tmp / "tmpdir"
        self.tmpdir_env.mkdir()
        self._orig_tmpdir = os.environ.get("TMPDIR")
        os.environ["TMPDIR"] = str(self.tmpdir_env)
        self.root = mkroot(self.tmp, "app", name="app")

    def tearDown(self):
        if self._orig_tmpdir is None:
            os.environ.pop("TMPDIR", None)
        else:
            os.environ["TMPDIR"] = self._orig_tmpdir
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_stamp(self, session: str, read: bool = False) -> Path:
        stamp_hash = frame.stamp_hash_for_root(self.root)
        p = self.tmpdir_env / "praxis-front-door" / session / stamp_hash
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("{}")
        if read:
            (p.parent / (p.name + ".read")).write_text("1")
        return p

    def test_close_clears_stamps_across_all_sessions(self):
        self._write_stamp("sess-A", read=True)
        self._write_stamp("sess-B", read=True)
        result = frame.close_frame_marker(self.root)
        self.assertEqual(result["stamps_cleared"], 4)
        remaining = list((self.tmpdir_env / "praxis-front-door").glob("*/*"))
        self.assertEqual(remaining, [])

    def test_close_with_no_stamp_dir_returns_zero_no_crash(self):
        result = frame.close_frame_marker(self.root)
        self.assertEqual(result["stamps_cleared"], 0)


class AutoEngineSlotTests(unittest.TestCase):
    """Auto-resolving the engine slot from the task's own governing root, so --engine-plugins need not
    be passed by hand (the ergonomics gap the FAMOUS + self-host trials hit)."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_slot_resolves_from_single_governing_root(self):
        root = mkroot(self.tmp, "app", name="app").resolve()
        slot = frame.auto_engine_slot(self.tmp, "app/src/x.ts", [])
        self.assertEqual(slot, root / "praxis" / "engine" / "plugins")

    def test_slot_honors_config_declared_engine_plugins(self):
        # A root whose config points its engine outside the convention slot (the self-host shape).
        d = self.tmp / "app"
        (d / "praxis").mkdir(parents=True)
        (d / "praxis" / "config.md").write_text("name: app\nengine-plugins: eng/slot\n")
        slot = frame.auto_engine_slot(self.tmp, "app/src/x.ts", [])
        self.assertEqual(slot, d.resolve() / "eng" / "slot")

    def test_spanning_targets_have_no_single_slot(self):
        mkroot(self.tmp, "apps/a", name="a")
        mkroot(self.tmp, "apps/b", name="b")
        self.assertIsNone(frame.auto_engine_slot(self.tmp, None, ["apps/a/x.ts", "apps/b/y.ts"]))

    def test_unrouted_target_has_no_slot(self):
        mkroot(self.tmp, "app", name="app")
        self.assertIsNone(frame.auto_engine_slot(self.tmp, "loose/file.ts", []))

    def test_cli_composes_via_auto_resolved_slot_without_flag(self):
        # End-to-end: an engine registered in the root's CONVENTION slot is picked up with NO
        # --engine-plugins flag, and its domain set is composed.
        root = mkroot(self.tmp, "app", name="app")
        stub = write_stub(self.tmp)
        write_plugin_slot(root / "praxis" / "engine", stub)  # → app/praxis/engine/plugins
        r = subprocess.run(
            [sys.executable, str(SCRIPTS / "frame.py"), "--from", str(self.tmp),
             "--target", "app/src/x.ts", "--unit-of-work", "implement-feature", "--json"],
            capture_output=True, text=True, timeout=60,
            env={**os.environ, "STUB_DOMAINS": "alpha,beta"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["composition"], ["alpha", "beta"])


if __name__ == "__main__":
    unittest.main()
