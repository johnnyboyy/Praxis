"""R3b — isolation + copy-detection for the rebuild seam, proven on fixtures.

No model, no real subagent: synthetic worktrees + read-logs in tmp_path. Proves
the three mechanical defenses (IR-only seed, dependency hygiene, copy tripwire)
and that a tripped wire fails a rebuild unit even when coverage-diff would pass.
Honest framing preserved: this is copy-DETECTION, not a capability boundary."""
import os
import sys
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import isolation  # noqa: E402
import run as R  # noqa: E402
import workflow as W  # noqa: E402
from situation import Situation  # noqa: E402
from workflow_run import run_workflow  # noqa: E402


FAITHFUL_IMPL = "def add(a, b):\n    return a + b\n\ndef sub(a, b):\n    return a - b\n"

HELD_TEST = textwrap.dedent("""
    from calc import add, sub
    def test_add():
        assert add(2, 3) == 5
    def test_sub():
        assert sub(5, 2) == 3
""")


def _sit(**over):
    kw = dict(task_kind="change", intent="rebuild", subject="coding",
              workflow="rebuild-triple")
    kw.update(over)
    return Situation(**kw)


def _ir(spec, held):
    return {
        "interface": [{"symbol": "add", "signature": "add(a, b)"},
                      {"symbol": "sub", "signature": "sub(a, b)"}],
        "allowed_surface": ["add", "sub"],
        "tests": {"spec": list(spec), "held_out": list(held)},
    }


# --- 1. seed_synth_worktree -------------------------------------------------

class SeedSynthWorktreeTest(unittest.TestCase):
    def test_seeds_spec_not_original_with_own_marker(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            # The ORIGINAL tree: source the synth must never receive.
            original = base / "original"
            original.mkdir()
            (original / "calc.py").write_text(FAITHFUL_IMPL)
            # Sanctioned spec test files (what synth is allowed to see).
            specs = []
            for i in range(3):
                p = original / f"test_spec_{i}.py"
                p.write_text(f"def test_{i}():\n    assert True\n")
                specs.append(str(p))
            # A shared config passed explicitly.
            cfg = original / "pytest.ini"
            cfg.write_text("[pytest]\n")

            ir = _ir(specs, ["test_held_1"])
            dest = base / "synth"
            wt = isolation.seed_synth_worktree(ir, dest, extra=[str(cfg)])

            self.assertEqual(wt, dest)
            # spec tests + shared config are present...
            for i in range(3):
                self.assertTrue((dest / f"test_spec_{i}.py").is_file())
            self.assertTrue((dest / "pytest.ini").is_file())
            # ...the original source is NOT...
            self.assertFalse((dest / "calc.py").exists())
            self.assertEqual(list(dest.rglob("calc.py")), [])
            # ...and the tree carries its OWN .praxis marker (its own root).
            self.assertTrue((dest / ".praxis" / "config.json").is_file())

    def test_marker_resolves_worktree_as_its_own_root(self):
        """The edit-lease gate walks up to the nearest .praxis; a seeded worktree
        under a parent praxis root must resolve to ITSELF, not the parent."""
        import tempfile
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
        import root_tree  # noqa: E402
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / ".praxis").mkdir()
            (base / ".praxis" / "config.json").write_text("{}")
            spec = base / "test_spec.py"
            spec.write_text("def test_x():\n    assert True\n")
            ir = _ir([str(spec), "s2", "s3"], ["held"])
            wt = isolation.seed_synth_worktree(ir, base / "synth")
            resolved = root_tree.resolve_root(wt / "test_spec.py")
            self.assertEqual(resolved.resolve(), wt.resolve())

    def test_malformed_ir_fails_closed(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(Exception):
                isolation.seed_synth_worktree({"interface": "bad"}, Path(tmp) / "s")


# --- 2. dep_hygiene_ok ------------------------------------------------------

class DepHygieneTest(unittest.TestCase):
    def test_clean_worktree_only_path_passes(self):
        env = {"PYTHONPATH": "/scratch/synth"}
        ok, problems = isolation.dep_hygiene_ok(
            "/scratch/synth", "/repo/original", env=env)
        self.assertTrue(ok, problems)
        self.assertEqual(problems, [])

    def test_original_root_on_pythonpath_flagged(self):
        env = {"PYTHONPATH": os.pathsep.join(["/scratch/synth", "/repo/original"])}
        ok, problems = isolation.dep_hygiene_ok(
            "/scratch/synth", "/repo/original", env=env)
        self.assertFalse(ok)
        self.assertTrue(any("original root" in p for p in problems))

    def test_worktree_absent_from_path_flagged(self):
        env = {"PYTHONPATH": "/somewhere/else"}
        ok, problems = isolation.dep_hygiene_ok(
            "/scratch/synth", "/repo/original", env=env)
        self.assertFalse(ok)
        self.assertTrue(any("not on PYTHONPATH" in p for p in problems))

    def test_installed_package_copy_outside_worktree_flagged(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            worktree = base / "synth"
            worktree.mkdir()
            site = base / "site-packages"
            (site / "calc").mkdir(parents=True)
            (site / "calc" / "__init__.py").write_text("")  # installed original
            env = {"PYTHONPATH": os.pathsep.join([str(worktree), str(site)])}
            ok, problems = isolation.dep_hygiene_ok(
                worktree, base / "original", env=env, package="calc")
            self.assertFalse(ok)
            self.assertTrue(any("calc" in p and "OUTSIDE" in p for p in problems))

    def test_package_inside_worktree_passes(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            worktree = base / "synth"
            (worktree / "calc").mkdir(parents=True)
            (worktree / "calc" / "__init__.py").write_text("")
            env = {"PYTHONPATH": str(worktree)}
            ok, problems = isolation.dep_hygiene_ok(
                worktree, base / "original", env=env, package="calc")
            self.assertTrue(ok, problems)


# --- 3. scan_tripwire -------------------------------------------------------

class ScanTripwireTest(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.wt = Path(self.tmp.name) / "synth"
        self.wt.mkdir()
        (self.wt / "calc.py").write_text(FAITHFUL_IMPL)
        self.original = Path(self.tmp.name) / "original" / "calc.py"
        self.original.parent.mkdir()
        self.original.write_text(FAITHFUL_IMPL)

    def tearDown(self):
        self.tmp.cleanup()

    def test_out_of_worktree_absolute_read_flagged(self):
        log = [str(self.wt / "calc.py"), str(self.original)]
        v = isolation.scan_tripwire(log, self.wt)
        self.assertEqual(len(v), 1)
        self.assertEqual(Path(v[0]["resolved"]), self.original.resolve())

    def test_in_worktree_reads_pass(self):
        log = [str(self.wt / "calc.py")]
        self.assertEqual(isolation.scan_tripwire(log, self.wt), [])

    def test_relative_in_worktree_read_passes(self):
        # relative paths resolve against the worktree.
        self.assertEqual(isolation.scan_tripwire(["calc.py"], self.wt), [])

    def test_relative_escape_flagged(self):
        v = isolation.scan_tripwire(["../original/calc.py"], self.wt)
        self.assertEqual(len(v), 1)

    def test_symlink_inside_pointing_out_flagged(self):
        link = self.wt / "sneaky.py"
        link.symlink_to(self.original)  # in-worktree name, out-of-worktree target
        v = isolation.scan_tripwire([str(link)], self.wt)
        self.assertEqual(len(v), 1)
        self.assertEqual(Path(v[0]["resolved"]), self.original.resolve())

    def test_empty_log_passes(self):
        self.assertEqual(isolation.scan_tripwire([], self.wt), [])
        self.assertEqual(isolation.scan_tripwire(None, self.wt), [])


# --- 4. the tripwire gate (a copy is caught even when coverage-diff passes) --

def _write_synth(tree: Path, impl: str) -> Path:
    tree.mkdir(parents=True, exist_ok=True)
    (tree / "calc.py").write_text(impl)
    return tree


def _held_out(dirpath: Path) -> str:
    dirpath.mkdir(parents=True, exist_ok=True)
    p = dirpath / "test_held.py"
    p.write_text(HELD_TEST)
    return str(p)


class TripwireVerifierTest(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_gate_fails_on_out_of_worktree_read_even_if_coverage_passes(self):
        synth = _write_synth(self.dir / "synth", FAITHFUL_IMPL)
        held = _held_out(self.dir / "held")
        original = self.dir / "original" / "calc.py"
        original.parent.mkdir()
        original.write_text(FAITHFUL_IMPL)
        ir = _ir(["s1", "s2", "s3"], [held])

        gate = isolation.synthesize_exit_gate(R.coverage_diff_verifier())
        # Control: faithful synth + clean log → the composed gate passes.
        clean = R.Receipt(outcome="result",
                          evidence={"produces": str(synth), "tool_log": []})
        self.assertTrue(gate.verify(None, clean, {"ir": ir}).verified)

        # A copy: the synth READ the original by absolute path → tripwire fails
        # the unit even though coverage-diff on the faithful tree would pass.
        copied = R.Receipt(outcome="result",
                           evidence={"produces": str(synth),
                                     "tool_log": [str(original)]})
        v = gate.verify(None, copied, {"ir": ir})
        self.assertFalse(v.verified)
        self.assertEqual(v.evidence["check"], "tripwire")

    def test_tool_log_source_from_composed(self):
        synth = _write_synth(self.dir / "synth", FAITHFUL_IMPL)
        original = self.dir / "outside.py"
        original.write_text("x = 1\n")
        v = isolation.tripwire_verifier().verify(
            None, R.Receipt(outcome="result", evidence={"produces": str(synth)}),
            {"synth_tool_log": [str(original)]})
        self.assertFalse(v.verified)


class RebuildWalkTripwireTest(unittest.TestCase):
    """Walk-level: a rebuild-triple unit whose synth read the original by
    absolute path HALTS at synthesize — the copy is caught by the wired gate."""

    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".praxis").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def _events(self, event):
        import journal
        return {e["phase"]: e for e in journal.read(self.root)
                if e.get("event") == event}

    def _walk(self, tool_log):
        synth = _write_synth(self.root / "synth", FAITHFUL_IMPL)
        held = _held_out(self.root / "held")
        original = self.root / "original" / "calc.py"
        original.parent.mkdir()
        original.write_text(FAITHFUL_IMPL)
        ir = _ir(["s1", "s2", "s3"], [held])

        def handler(unit, composed):
            if composed.get("phase") == "extract":
                return R.Receipt(outcome="result", evidence={"produces": ir})
            return R.Receipt(outcome="result",
                             evidence={"produces": str(synth),
                                       "tool_log": tool_log(original)})

        verifiers = {"does-it": R.adequacy_verifier(None),
                     "coverage-diff": isolation.synthesize_exit_gate(
                         R.coverage_diff_verifier())}
        out = run_workflow(self.root, R.Unit("u1", _sit()), W.REBUILD_TRIPLE,
                           [], R.InlineExecutor(handler), verifiers=verifiers)
        return out

    def test_copy_read_halts_at_synthesize(self):
        self._walk(lambda orig: [str(orig)])
        exited = self._events("phase.exited")
        self.assertTrue(exited["extract"]["verified"])
        self.assertFalse(exited["synthesize"]["verified"])  # tripwire blocks

    def test_clean_read_advances(self):
        self._walk(lambda orig: [])
        exited = self._events("phase.exited")
        self.assertTrue(exited["extract"]["verified"])
        self.assertTrue(exited["synthesize"]["verified"])


if __name__ == "__main__":
    unittest.main()
