"""plugin_import — snapshot-import a plugin contribution into a project's praxis slots.

Praxis-core stays pure here: the fixtures use a SYNTHETIC engine named 'demo' and no real engine name,
so praxis's one-line purity check still returns nothing. The crux under test — freezing an engine
manifest's `cli.entry` to an absolute snapshot path — is exercised with a synthetic manifest that
carries a relative `cli.entry`, exactly the shape a real engine contribution has.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

PRAXIS_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(PRAXIS_SCRIPTS))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import plugin_import as pi  # noqa: E402
import engine  # noqa: E402  to prove an imported manifest loads through praxis's own resolver
from _stub_engine import write_stub, write_plugin_slot, IMPORT_POOL_CAP, ADOPT_CAP, read_log  # noqa: E402


def make_contribution(base: Path, *, phases=("alpha.md", "beta.md"), scripts=("tool.py",)) -> Path:
    """A synthetic 'demo' plugin contribution mirroring a real praxis-plugin's shape."""
    c = base / "demo-plugin"
    (c / "engine" / "plugins").mkdir(parents=True)
    (c / "handoff" / "plugins").mkdir(parents=True)
    (c / "phases").mkdir(parents=True)
    (c / "scripts").mkdir(parents=True)
    # A real CLI target sitting where the engine manifest's relative entry points (../../scripts/cli.py).
    (c / "scripts" / "cli.py").write_text("#!/usr/bin/env python3\nprint('{}')\n")
    (c / "plugin.json").write_text(json.dumps({
        "name": "demo",
        "provides": {"engine": "engine/plugins", "handoff": "handoff/plugins",
                     "phases": "phases", "scripts": "scripts"},
    }))
    (c / "engine" / "plugins" / "demo.json").write_text(json.dumps({
        "plugin": "demo",
        "cli": {"command": "python3", "entry": "../../scripts/cli.py"},
        "capabilities": [{"capability": "compose", "verb": "select",
                          "args": [{"param": "unit_of_work", "flag": "--unit-of-work", "required": True}]}],
    }))
    (c / "handoff" / "plugins" / "demo.json").write_text(json.dumps({
        "plugin": "demo",
        "frontmatter": [{"field": "domains-loaded", "required": True, "shape": "list"}],
        "sections": [],
    }))
    for name in phases:
        (c / "phases" / name).write_text(f"# phase {name}\n")
    for name in scripts:
        (c / "scripts" / name).write_text(f"# script {name}\n")
    return c


def make_root(base: Path) -> Path:
    root = base / "proj"
    (root / "praxis").mkdir(parents=True)
    (root / "praxis" / "config.md").write_text("## project-shape\nname: proj\n")
    return root


class PluginImport(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.contribution = make_contribution(self.tmp)
        self.root = make_root(self.tmp)

    def test_files_land_in_the_right_project_slots(self):
        pi.import_contribution(self.contribution, self.root)
        pp = self.root / "praxis"
        self.assertTrue((pp / "engine" / "plugins" / "demo.json").is_file())
        self.assertTrue((pp / "handoff" / "plugins" / "demo.json").is_file())
        self.assertTrue((pp / "phases" / "alpha.md").is_file())
        self.assertTrue((pp / "phases" / "beta.md").is_file())
        self.assertTrue((pp / "scripts" / "tool.py").is_file())

    def test_engine_manifest_cli_entry_is_frozen_to_absolute_snapshot(self):
        # The crux: relative ../../scripts/cli.py becomes the absolute path it pointed at, at import time.
        pi.import_contribution(self.contribution, self.root)
        imported = json.loads((self.root / "praxis" / "engine" / "plugins" / "demo.json").read_text())
        entry = Path(imported["cli"]["entry"])
        self.assertTrue(entry.is_absolute())
        self.assertEqual(entry, (self.contribution / "scripts" / "cli.py").resolve())

    def test_imported_manifest_loads_through_praxis_own_resolver(self):
        # An imported engine manifest is a real, loadable registration: praxis's generic loader finds
        # it in the project's slot and resolves its cli to the frozen absolute path.
        pi.import_contribution(self.contribution, self.root)
        slot = self.root / "praxis" / "engine" / "plugins"
        manifest = engine.load_registered(slot)
        self.assertIsNotNone(manifest)
        self.assertEqual(manifest["plugin"], "demo")
        self.assertEqual(Path(manifest["cli"][-1]), (self.contribution / "scripts" / "cli.py").resolve())

    def test_handoff_and_other_slot_files_are_copied_verbatim(self):
        pi.import_contribution(self.contribution, self.root)
        h = json.loads((self.root / "praxis" / "handoff" / "plugins" / "demo.json").read_text())
        self.assertEqual(h["plugin"], "demo")
        self.assertNotIn("cli", h)  # untouched — only the engine slot gets the freeze rule

    def test_lockfile_records_source_and_slots(self):
        pi.import_contribution(self.contribution, self.root)
        lock = json.loads((self.root / "praxis" / "plugins.lock.json").read_text())
        rec = lock["plugins"]["demo"]
        self.assertEqual(Path(rec["source"]), self.contribution.resolve())
        self.assertIn("alpha.md", rec["slots"]["phases"])
        self.assertIn("tool.py", rec["slots"]["scripts"])
        self.assertIn("imported_at", rec)

    def test_sync_repulls_and_prunes_files_the_plugin_no_longer_provides(self):
        pi.import_contribution(self.contribution, self.root)
        # Source changes: beta.md removed, gamma.md added.
        (self.contribution / "phases" / "beta.md").unlink()
        (self.contribution / "phases" / "gamma.md").write_text("# phase gamma\n")
        results = pi.sync(self.root, None)
        phases_dir = self.root / "praxis" / "phases"
        self.assertTrue((phases_dir / "gamma.md").is_file())      # new one pulled
        self.assertFalse((phases_dir / "beta.md").is_file())      # stale one pruned
        self.assertTrue((phases_dir / "alpha.md").is_file())      # unchanged one kept
        self.assertIn("praxis/phases/beta.md", results[0]["pruned"])

    def test_reimport_is_idempotent_and_prunes(self):
        pi.import_contribution(self.contribution, self.root)
        (self.contribution / "scripts" / "tool.py").unlink()
        r = pi.import_contribution(self.contribution, self.root)
        self.assertFalse((self.root / "praxis" / "scripts" / "tool.py").is_file())
        self.assertIn("praxis/scripts/tool.py", r["pruned"])

    def test_importing_into_a_non_root_is_rejected(self):
        notroot = self.tmp / "not-a-root"
        notroot.mkdir()
        with self.assertRaises(pi.ImportError_):
            pi.import_contribution(self.contribution, notroot)

    def test_unknown_slot_in_contribution_is_rejected(self):
        bad = self.tmp / "bad-plugin"
        bad.mkdir()
        (bad / "plugin.json").write_text(json.dumps({"name": "bad", "provides": {"nonsense": "x"}}))
        with self.assertRaises(pi.ImportError_):
            pi.import_contribution(bad, self.root)

    def test_contribution_without_plugin_json_is_rejected(self):
        bare = self.tmp / "bare"
        bare.mkdir()
        with self.assertRaises(pi.ImportError_):
            pi.load_contribution(bare)

    def test_sync_unknown_plugin_is_rejected(self):
        pi.import_contribution(self.contribution, self.root)
        with self.assertRaises(pi.ImportError_):
            pi.sync(self.root, "nope")


def make_judgment_plugin(base: Path) -> Path:
    """A judgment-only plugin: no praxis-face slots, just a judgment face (a domains-dir). The
    judgment_face path is arbitrary plugin data — praxis hardcodes no engine's layout — so the fixture
    uses a generic dir name, which also keeps praxis's one-line purity check clean. Two domains + an
    audit.md, to prove containers are adopted per-domain and audit.md is skipped."""
    c = base / "routing-plugin"
    dom = c / "judgment" / "domains"
    dom.mkdir(parents=True)
    (dom / "routing.md").write_text("---\nsubject: process\nunits-of-work: [route-work]\n---\n# routing\n")
    (dom / "spawn-integrity.md").write_text("---\nsubject: process\nuniversal: true\n---\n# spawn-integrity\n")
    (dom / "audit.md").write_text("provenance:\n")
    (c / "plugin.json").write_text(json.dumps({
        "name": "routing", "provides": {}, "judgment_face": "judgment/domains"}))
    return c


class JudgmentFaceImport(unittest.TestCase):
    """The judgment face is staged THROUGH the registered engine's gate — never a raw file copy."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.root = make_root(self.tmp)
        self.plugin = make_judgment_plugin(self.tmp)
        self.log = self.tmp / "engine.log"

    def _register_engine(self, *, with_import_cap: bool, with_adopt_cap: bool = True):
        stub = write_stub(self.tmp)
        caps = ([IMPORT_POOL_CAP] if with_import_cap else []) + ([ADOPT_CAP] if with_adopt_cap else [])
        slot = write_plugin_slot(self.tmp, stub, extra_caps=caps)
        # plugin_import reads the project's OWN engine slot at <root>/praxis/engine/plugins.
        target = self.root / "praxis" / "engine" / "plugins"
        target.mkdir(parents=True, exist_ok=True)
        (target / "stub.json").write_text((slot / "stub.json").read_text())
        # Point the stub at a shared log so we can assert the import verb actually ran.
        import os
        os.environ["STUB_LOG"] = str(self.log)

    def tearDown(self):
        import os
        os.environ.pop("STUB_LOG", None)

    def test_judgment_face_is_staged_through_the_engine_import_capability(self):
        self._register_engine(with_import_cap=True)
        r = pi.import_contribution(self.plugin, self.root)
        self.assertTrue(r["judgment"]["staged"], r["judgment"]["note"])
        calls = read_log(self.log)
        # A container is adopted per plugin domain first (audit.md skipped), then principles staged.
        adopt_calls = [c for c in calls if c and c[0] == "adopt-shell"]
        self.assertEqual(len(adopt_calls), 2)  # routing + spawn-integrity, not audit.md
        self.assertEqual(sorted(r["judgment"]["adopted"]), ["routing", "spawn-integrity"])
        adopted_sources = " ".join(" ".join(c) for c in adopt_calls)
        self.assertNotIn("audit.md", adopted_sources)
        # The engine's import verb ran, with the plugin's judgment dir as --source and the root global.
        pool_calls = [c for c in calls if c and c[0] == "import-pool"]
        self.assertEqual(len(pool_calls), 1)
        argv = " ".join(pool_calls[0])
        self.assertIn(str((self.plugin / "judgment" / "domains")), argv)
        self.assertIn("--root", argv)
        # Recorded in the lock.
        lock = json.loads((self.root / "praxis" / "plugins.lock.json").read_text())
        self.assertTrue(lock["plugins"]["routing"]["judgment_face"]["staged"])

    def test_no_engine_registered_degrades_not_crashes(self):
        # No engine in the slot: the judgment face can't be staged, but import doesn't fail.
        r = pi.import_contribution(self.plugin, self.root)
        self.assertFalse(r["judgment"]["staged"])
        self.assertIn("no judgment engine registered", r["judgment"]["note"])

    def test_engine_without_import_capability_degrades(self):
        self._register_engine(with_import_cap=False)  # engine has compose but not import-file-pool
        r = pi.import_contribution(self.plugin, self.root)
        self.assertFalse(r["judgment"]["staged"])
        self.assertIn("no judgment-import capability", r["judgment"]["note"])


if __name__ == "__main__":
    unittest.main()
