"""Tests for the generic engine plugin loader + capability resolver.

Praxis-core never names an engine or a verb; it resolves a CAPABILITY against whatever manifest is
registered in the engine slot. These tests pin the mechanics with SYNTHETIC manifests (no real
engine): argv is built in the right shape (globals before the verb, positionals bare, booleans as a
lone flag, required params enforced), an undeclared capability is praxis's own error, a manifest's
`cli` (entry relative to the manifest file) resolves to an absolute command, and an empty slot yields
no engine so callers degrade. Run: python3 -m unittest discover -s praxis/tests
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import engine  # noqa: E402
from _stub_engine import write_stub, stub_manifest, write_plugin_slot, read_log, COMPOSE_CAP  # noqa: E402


SYN = {"plugin": "syn", "capabilities": {c["capability"]: c for c in [
    {"capability": "write", "verb": "do-write", "args": [
        {"param": "domain", "flag": "--domain", "required": True},
        {"param": "kind", "flag": "--kind"}]},
    {"capability": "mig", "verb": "migrate", "args": [
        {"param": "root", "flag": "--root", "global": True},
        {"param": "source", "flag": "--source"}]},
    {"capability": "pos", "verb": "vp", "args": [
        {"param": "file", "positional": True, "required": True}]},
    COMPOSE_CAP,
]}, "cli": None}


class BuildArgvTests(unittest.TestCase):
    def test_flag_value_pairs_follow_the_verb(self):
        argv = engine.build_argv(SYN, "write", {"domain": "d"})
        self.assertEqual(argv[0], "do-write")   # capability -> verb
        self.assertEqual(argv[1:], ["--domain", "d"])

    def test_optional_absent_param_is_omitted(self):
        argv = engine.build_argv(SYN, "write", {"domain": "d", "kind": ""})
        self.assertNotIn("--kind", argv)

    def test_positional_emits_value_alone(self):
        self.assertEqual(engine.build_argv(SYN, "pos", {"file": "h.md"}), ["vp", "h.md"])

    def test_global_option_precedes_the_verb(self):
        argv = engine.build_argv(SYN, "mig", {"root": "/proj", "source": "/seed"})
        self.assertEqual(argv[:2], ["--root", "/proj"])   # global BEFORE the subcommand
        self.assertEqual(argv[2], "migrate")
        self.assertIn("--source", argv[3:])

    def test_boolean_emits_a_lone_flag(self):
        argv = engine.build_argv(SYN, "compose", {"root": "/r", "unit_of_work": "u", "json": True})
        self.assertEqual(argv[-1], "--json")   # flag not followed by a value

    def test_missing_required_param_raises_before_engine(self):
        with self.assertRaises(engine.CapabilityError):
            engine.build_argv(SYN, "write", {})

    def test_unknown_capability_raises(self):
        with self.assertRaises(engine.CapabilityError):
            engine.build_argv(SYN, "no-such-capability", {})


class CliResolutionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_manifest_cli_entry_resolves_relative_to_the_manifest(self):
        # An engine that registers points `cli.entry` at itself, relative to the manifest file.
        slot = self.tmp / "engine" / "plugins"
        slot.mkdir(parents=True)
        (self.tmp / "engine" / "bin").mkdir()
        (self.tmp / "engine" / "bin" / "cli.py").write_text("# engine\n")
        (slot / "acme.json").write_text(json.dumps(
            {"plugin": "acme", "cli": {"command": "python3", "entry": "../bin/cli.py"},
             "capabilities": []}))
        m = engine.load_manifest(slot / "acme.json")
        self.assertEqual(m["cli"][0], "python3")
        self.assertEqual(Path(m["cli"][1]), (self.tmp / "engine" / "bin" / "cli.py").resolve())

    def test_empty_slot_registers_no_engine(self):
        empty = self.tmp / "plugins"
        empty.mkdir()
        self.assertIsNone(engine.discover_manifest(empty))
        self.assertIsNone(engine.load_registered(empty))

    def test_registered_engine_is_discovered_and_loaded(self):
        stub = write_stub(self.tmp)
        slot = write_plugin_slot(self.tmp, stub)
        m = engine.load_registered(slot)
        self.assertEqual(m["plugin"], "stub")
        self.assertIn("compose", m["capabilities"])


class ResolveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.stub = write_stub(self.tmp)
        self.log = self.tmp / "log.txt"
        os.environ["STUB_LOG"] = str(self.log)
        os.environ.pop("STUB_FAIL", None)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)
        os.environ.pop("STUB_LOG", None)

    def test_resolve_runs_the_resolved_verb(self):
        res = engine.resolve(stub_manifest(self.stub), "compose", {"unit_of_work": "u"})
        self.assertTrue(res.ok)
        self.assertEqual(read_log(self.log)[0][0], "compose")

    def test_resolve_no_engine_degrades(self):
        res = engine.resolve(None, "compose", {"unit_of_work": "u"})
        self.assertFalse(res.ran)   # praxis reports, does not crash

    def test_resolve_missing_cli_degrades(self):
        bad = {"plugin": "x", "capabilities": {"compose": COMPOSE_CAP},
               "cli": ["python3", str(self.tmp / "nope.py")]}
        res = engine.resolve(bad, "compose", {"unit_of_work": "u"})
        self.assertFalse(res.ran)


class SlotForRootTests(unittest.TestCase):
    """`slot_for_root` — where a governing root exposes its engine, so a task auto-resolves it instead
    of passing --engine-plugins by hand. A config-declared `engine-plugins:` wins; else the convention
    slot. praxis names no engine either way — it reads a path from its own marker or its own slot."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _mkroot(self, body: str) -> Path:
        (self.tmp / "praxis").mkdir(parents=True, exist_ok=True)
        (self.tmp / "praxis" / "config.md").write_text(body)
        return self.tmp

    def test_convention_slot_when_config_declares_nothing(self):
        root = self._mkroot("## project-shape\nname: p\n")
        self.assertEqual(engine.slot_for_root(root), root / "praxis" / "engine" / "plugins")

    def test_config_declared_relative_path_wins(self):
        # The self-host shape: the engine lives outside the (pristine) core slot; config points at it.
        root = self._mkroot("name: p\nengine-plugins: corpora/praxis-plugin/engine/plugins\n")
        self.assertEqual(engine.slot_for_root(root),
                         root / "corpora" / "praxis-plugin" / "engine" / "plugins")

    def test_config_declared_absolute_path_kept(self):
        root = self._mkroot("engine-plugins: /opt/eng/plugins\n")
        self.assertEqual(engine.slot_for_root(root), Path("/opt/eng/plugins"))

    def test_no_config_falls_back_to_convention(self):
        # A directory with no marker still resolves to the convention slot (caller finds it empty).
        self.assertEqual(engine.slot_for_root(self.tmp), self.tmp / ".praxis" / "engine" / "plugins")


if __name__ == "__main__":
    unittest.main()
