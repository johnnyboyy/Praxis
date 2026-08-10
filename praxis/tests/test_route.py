"""Tests for route.py — the routing fact-sheet. Two layers:

  - the execution-shape signals against a fixture project as REAL subprocesses (frame-derived facts:
    single-root new work vs. a spanning task that must isolate), driven with a generic stub engine
    registered in an engine plugin slot; and
  - the resume-vs-new NATIVE ledger signal (a praxis-owned file, no engine call).

Zero real engine is involved. Run: python3 -m unittest discover -s praxis/tests
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PRAXIS = Path(__file__).resolve().parent.parent
ROUTE = PRAXIS / "scripts" / "route.py"

SCRIPTS = PRAXIS / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import route  # noqa: E402
import frame  # noqa: E402
import root_tree  # noqa: E402
from _stub_engine import write_stub, stub_manifest, write_plugin_slot  # noqa: E402


def run(*args: str, env=None) -> subprocess.CompletedProcess:
    e = dict(os.environ)
    if env:
        e.update(env)
    return subprocess.run([sys.executable, *args], capture_output=True, text=True, timeout=60, env=e)


def mkroot(base: Path, rel: str, name: str) -> Path:
    d = base / rel
    (d / "praxis").mkdir(parents=True, exist_ok=True)
    (d / "praxis" / "config.md").write_text(f"## project-shape\nname: {name}\n")
    return d


class RouteShapeE2E(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        mkroot(self.tmp, ".", "platform")
        mkroot(self.tmp, "app", "app")
        mkroot(self.tmp, "admin", "admin")
        self.stub = write_stub(self.tmp)
        self.slot = write_plugin_slot(self.tmp, self.stub)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_single_root_new_work_shape(self):
        r = run(str(ROUTE), "--from", str(self.tmp), "--target", "app/src/x.ts",
                "--unit-of-work", "implement-feature", "--engine-plugins", str(self.slot), "--json",
                env={"STUB_DOMAINS": "d1"})
        self.assertEqual(r.returncode, 0, r.stderr)
        es = json.loads(r.stdout)["execution_shape"]
        self.assertEqual(es["verdict"], "single-root")
        self.assertFalse(es["isolate_per_root"])       # one root → not isolate
        self.assertFalse(es["resume_candidate"])       # no workstream named → new
        self.assertEqual(es["ledger"], "unknown")
        self.assertTrue(es["composition_available"])   # generic engine returned a domain set

    def test_spanning_task_routes_to_isolate(self):
        r = run(str(ROUTE), "--from", str(self.tmp), "--files", "app/x.ts,admin/y.ts",
                "--unit-of-work", "implement-feature", "--engine-plugins", str(self.slot), "--json")
        d = json.loads(r.stdout)
        es = d["execution_shape"]
        self.assertEqual(es["verdict"], "decompose")
        self.assertTrue(es["isolate_per_root"])        # spanning → isolate per root
        self.assertTrue(any("isolate" in s for s in d["signals"]))


class RouteLedgerNative(unittest.TestCase):
    """resume-vs-new is a NATIVE ledger-file lookup — the ledger is a praxis-owned file
    (<root>/praxis/chunks/<workstream>.md), read directly, no engine call."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.stub = write_stub(self.tmp)
        self.manifest = stub_manifest(self.stub)
        os.environ.pop("STUB_LOG", None)
        self.root = mkroot(self.tmp, "proj", "proj")
        self.target = "proj/src/x.ts"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)
        os.environ.pop("STUB_LOG", None)

    def _route(self, workstream):
        return route.build_route(self.tmp, self.target, [], "implement-feature", workstream, self.manifest)

    def _make_ledger(self, workstream):
        cdir = self.root / "praxis" / "chunks"
        cdir.mkdir(parents=True, exist_ok=True)
        (cdir / f"{workstream}.md").write_text(
            f"# Chunks\n\nworkstream: {workstream}\n\n```yaml\nchunks:\n```\n")

    def test_named_workstream_with_ledger_is_resume(self):
        self._make_ledger("ws-1")
        es = self._route("ws-1")["execution_shape"]
        self.assertEqual(es["ledger"], "exists")
        self.assertTrue(es["resume_candidate"])

    def test_named_workstream_without_ledger_is_new(self):
        es = self._route("ws-1")["execution_shape"]
        self.assertEqual(es["ledger"], "absent")
        self.assertFalse(es["resume_candidate"])

    def test_no_workstream_is_unknown_and_new(self):
        es = self._route(None)["execution_shape"]
        self.assertEqual(es["ledger"], "unknown")
        self.assertFalse(es["resume_candidate"])

    def test_no_engine_still_reports_native_ledger_and_root_facts(self):
        # The ledger lookup does not depend on the engine; it stands even with no engine registered.
        self._make_ledger("ws-1")
        d = route.build_route(self.tmp, self.target, [], "implement-feature", "ws-1", None)
        es = d["execution_shape"]
        self.assertEqual(es["ledger"], "exists")
        self.assertEqual(d["frame"]["roots"][0]["name"], "proj")


class RouteMarkerReadOnly(unittest.TestCase):
    """route is a read path: build_route runs frame but must not disturb the freshness marker
    (a pure `route --json` query silently refreshing the edit gate was the observed disease)."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.root = mkroot(self.tmp, "proj", "proj")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_build_route_leaves_existing_marker_byte_identical(self):
        marker = root_tree.praxis_dir(self.root) / frame.FRAME_MARKER_NAME
        original = json.dumps({"timestamp": 42.0, "unit_of_work": "implement-feature"})
        marker.write_text(original)
        route.build_route(self.tmp, "proj/src/x.ts", [], "implement-feature", None, None)
        self.assertEqual(marker.read_text(), original)


class RawAskDegrade(unittest.TestCase):
    """route is also the CLI raw-ask entry (framing Stage 2, migrated from front_door.py): a task
    can enter with a sentence and no targets, and route degrades cleanly instead of crashing."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        mkroot(self.tmp, "app", "app")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_raw_ask_with_no_targets_degrades_cleanly(self):
        # No target/files: route must NOT require them and NOT crash.
        r = route.build_route(self.tmp, None, [], None, None, None, ask="make the thing better")
        self.assertFalse(r["targets_known"])
        f = r["frame"]
        self.assertEqual(f["size_floor"], "underspecified")
        self.assertEqual(f["size_signals"]["target_count"], 0)
        # The unresolved inputs are relayed as assumptions to settle.
        self.assertTrue(any("unit-of-work: undecided" in a for a in f["assumptions"]))

    def test_cli_raw_ask_prints_and_exits_zero(self):
        r = run(str(ROUTE), "--from", str(self.tmp), "--ask", "improve framing")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("raw ask", r.stdout)
        self.assertIn("underspecified", r.stdout)

    def test_cli_no_ask_no_target_still_ok(self):
        # The floor of the raw-ask entry: it runs even with nothing at all.
        r = run(str(ROUTE), "--from", str(self.tmp))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("(none given)", r.stdout)


class ResolvedAskFullReadout(unittest.TestCase):
    """A raw ask with targets + unit-of-work guessed → full route readout, engine auto-resolved."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.root = mkroot(self.tmp, "app", "app")
        stub = write_stub(self.tmp)
        write_plugin_slot(self.root / "praxis" / "engine", stub)  # convention slot, auto-resolved

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_ask_with_target_and_uow_gives_full_route_with_auto_engine(self):
        # Targets + uow guessed → full readout, engine auto-resolved (no --engine-plugins flag).
        r = run(str(ROUTE), "--from", str(self.tmp), "--ask", "add x", "--target", "app/src/x.ts",
                "--unit-of-work", "implement-feature", "--json", env={"STUB_DOMAINS": "d1,d2"})
        self.assertEqual(r.returncode, 0, r.stderr)
        d = json.loads(r.stdout)
        self.assertTrue(d["targets_known"])
        self.assertEqual(d["frame"]["composition"], ["d1", "d2"])
        self.assertEqual(d["execution_shape"]["verdict"], "single-root")


if __name__ == "__main__":
    unittest.main()
