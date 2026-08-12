"""R3a — the rebuild-triple gate mechanics, proven on synthetic fixtures.

No model, no worktree, no isolation (R3b): synthetic IRs + synth trees in
tmp_path, verdicts derived purely from disk (ast surface set-diff + held-out
pytest exit code). Isolation is explicitly NOT exercised here — the synth path
is taken as given; R3b closes the absolute-path copy hole."""
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import rebuild_ir  # noqa: E402
import run as R  # noqa: E402
import workflow as W  # noqa: E402
from situation import Situation  # noqa: E402
from workflow_run import run_workflow  # noqa: E402


def _sit(**over):
    kw = dict(task_kind="change", intent="rebuild", subject="coding", workflow="rebuild-triple")
    kw.update(over)
    return Situation(**kw)


# ---- synthetic fixture builders --------------------------------------------

FAITHFUL_IMPL = textwrap.dedent("""
    def add(a, b):
        return a + b

    def sub(a, b):
        return a - b
""")


def _write_synth(tree: Path, impl: str) -> Path:
    tree.mkdir(parents=True, exist_ok=True)
    (tree / "calc.py").write_text(impl)
    return tree


def _held_out_test(dirpath: Path) -> str:
    """A held-out test file (never seen by synthesize) that binds to the synth."""
    dirpath.mkdir(parents=True, exist_ok=True)
    p = dirpath / "test_held.py"
    p.write_text(textwrap.dedent("""
        from calc import add, sub

        def test_add():
            assert add(2, 3) == 5

        def test_sub():
            assert sub(5, 2) == 3
    """))
    return str(p)


def _ir(held_path: str, **over) -> dict:
    ir = {
        "interface": [
            {"symbol": "add", "signature": "add(a, b)"},
            {"symbol": "sub", "signature": "sub(a, b)"},
        ],
        "allowed_surface": ["add", "sub"],
        "tests": {"spec": ["test_spec_1", "test_spec_2", "test_spec_3"],
                  "held_out": [held_path]},
    }
    ir.update(over)
    return ir


class RebuildIRValidationTest(unittest.TestCase):
    def _base(self):
        return _ir("some/test_held.py")

    def test_valid_ir_round_trips(self):
        self.assertIsInstance(rebuild_ir.validate_ir(self._base()), dict)

    def test_empty_held_out_rejected(self):
        ir = self._base()
        ir["tests"]["held_out"] = []
        with self.assertRaises(rebuild_ir.IRError):
            rebuild_ir.validate_ir(ir)

    def test_trivial_held_out_fraction_rejected(self):
        # 1 held-out of 10 total = 10% < 25% threshold.
        ir = self._base()
        ir["tests"]["spec"] = [f"t{i}" for i in range(9)]
        ir["tests"]["held_out"] = ["test_one"]
        with self.assertRaises(rebuild_ir.IRError):
            rebuild_ir.validate_ir(ir)

    def test_malformed_ir_fails_closed(self):
        for bad in (None, [], "not-json", {"interface": "x"},
                    {"interface": [], "allowed_surface": [], "tests": {}}):
            with self.assertRaises(rebuild_ir.IRError):
                rebuild_ir.validate_ir(bad)

    def test_parse_ir_accepts_json_string(self):
        import json
        self.assertIsInstance(rebuild_ir.parse_ir(json.dumps(self._base())), dict)


class CoverageDiffVerifierTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.verifier = R.coverage_diff_verifier()

    def tearDown(self):
        self.tmp.cleanup()

    def _run(self, impl, ir_over=None):
        synth = _write_synth(self.dir / "synth", impl)
        held = _held_out_test(self.dir / "held")
        ir = _ir(held, **(ir_over or {}))
        receipt = R.Receipt(outcome="result", evidence={"produces": str(synth)})
        return self.verifier.verify(None, receipt, {"ir": ir})

    def test_faithful_synth_passes(self):
        v = self._run(FAITHFUL_IMPL)
        self.assertTrue(v.verified, v.defects)
        self.assertEqual(v.evidence["check"], "all")

    def test_missing_interface_symbol_fails_completeness(self):
        impl = "def add(a, b):\n    return a + b\n"  # no `sub`
        v = self._run(impl)
        self.assertFalse(v.verified)
        self.assertEqual(v.evidence["check"], "interface")
        self.assertIn("sub", v.evidence["missing"])

    def test_signature_mismatch_fails_completeness(self):
        impl = "def add(a, b):\n    return a + b\n\ndef sub(x, y):\n    return x - y\n"
        v = self._run(impl)
        self.assertFalse(v.verified)
        self.assertEqual(v.evidence["check"], "interface")
        self.assertEqual(v.evidence["mismatch"][0]["symbol"], "sub")

    def test_extra_surface_fails_losslessness(self):
        impl = FAITHFUL_IMPL + "\ndef leak(z):\n    return z\n"
        v = self._run(impl)
        self.assertFalse(v.verified)
        self.assertEqual(v.evidence["check"], "surface")
        self.assertIn("leak", v.evidence["extra"])

    def test_failing_held_out_fails_generalization(self):
        impl = "def add(a, b):\n    return a * b\n\ndef sub(a, b):\n    return a - b\n"
        v = self._run(impl)
        self.assertFalse(v.verified)
        self.assertEqual(v.evidence["check"], "held_out")
        self.assertNotEqual(v.evidence["returncode"], 0)

    def test_malformed_ir_fails_closed(self):
        synth = _write_synth(self.dir / "synth", FAITHFUL_IMPL)
        receipt = R.Receipt(outcome="result", evidence={"produces": str(synth)})
        v = self.verifier.verify(None, receipt, {"ir": {"interface": "bad"}})
        self.assertFalse(v.verified)
        self.assertEqual(v.evidence["check"], "ir")

    def test_missing_synth_path_fails_closed(self):
        held = _held_out_test(self.dir / "held")
        receipt = R.Receipt(outcome="result", evidence={})
        v = self.verifier.verify(None, receipt, {"ir": _ir(held)})
        self.assertFalse(v.verified)
        self.assertEqual(v.evidence["check"], "synth-path")


class AdequacyVerifierTest(unittest.TestCase):
    """The does-it gate at extract-exit: IR split-enforcement + the R2 coverage
    verifier pointed at the ORIGINAL (reused, exit-code only)."""

    def _extract_receipt(self, ir):
        # extract phase emits the IR as its produced artifact.
        return R.Receipt(outcome="result", evidence={"produces": ir})

    def test_adequate_ir_passes_when_coverage_passes(self):
        cov = R.CommandVerifier(lambda u, r, c: ["true"])   # exit 0 against original
        v = R.adequacy_verifier(cov)
        out = v.verify(None, self._extract_receipt(_ir("t/test_held.py")), {})
        self.assertTrue(out.verified, out.defects)

    def test_ir_failing_adequacy_threshold_fails_at_extract(self):
        cov = R.CommandVerifier(lambda u, r, c: ["false"])  # exit 1: threshold not met
        v = R.adequacy_verifier(cov)
        out = v.verify(None, self._extract_receipt(_ir("t/test_held.py")), {})
        self.assertFalse(out.verified)
        self.assertEqual(out.evidence["check"], "adequacy")

    def test_trivial_split_rejected_at_extract(self):
        cov = R.CommandVerifier(lambda u, r, c: ["true"])
        v = R.adequacy_verifier(cov)
        bad = _ir("t/test_held.py")
        bad["tests"]["held_out"] = []
        out = v.verify(None, self._extract_receipt(bad), {})
        self.assertFalse(out.verified)
        self.assertEqual(out.evidence["check"], "ir-split")


class RebuildWalkTest(unittest.TestCase):
    """Walk-level: a rebuild-triple unit whose synthesize output passes the
    coverage-diff gate advances (verified); one that fails halts at synthesize."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".praxis").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def _events(self, event):
        import journal
        return {e["phase"]: e for e in journal.read(self.root)
                if e.get("event") == event}

    def _walk(self, impl):
        synth = _write_synth(self.root / "synth", impl)
        held = _held_out_test(self.root / "held")
        ir = _ir(held)

        def handler(unit, composed):
            if composed.get("phase") == "extract":
                return R.Receipt(outcome="result", evidence={"produces": ir})
            return R.Receipt(outcome="result", evidence={"produces": str(synth)})

        verifiers = {"does-it": R.adequacy_verifier(None),
                     "coverage-diff": R.coverage_diff_verifier()}
        return run_workflow(self.root, R.Unit("u1", _sit()), W.REBUILD_TRIPLE,
                            [], R.InlineExecutor(handler), verifiers=verifiers)

    def test_faithful_synth_advances(self):
        out = self._walk(FAITHFUL_IMPL)
        self.assertEqual(out["phases"], ["extract", "synthesize"])
        exited = self._events("phase.exited")
        self.assertEqual(exited["extract"]["gate"], "does-it")
        self.assertTrue(exited["extract"]["verified"])
        self.assertEqual(exited["synthesize"]["gate"], "coverage-diff")
        self.assertTrue(exited["synthesize"]["verified"])

    def test_leaky_synth_halts_at_synthesize(self):
        out = self._walk(FAITHFUL_IMPL + "\ndef leak(z):\n    return z\n")
        self.assertEqual(out["phases"], ["extract", "synthesize"])
        exited = self._events("phase.exited")
        self.assertTrue(exited["extract"]["verified"])
        self.assertFalse(exited["synthesize"]["verified"])  # preservation gate blocks


if __name__ == "__main__":
    unittest.main()


def test_held_out_runs_from_synth_tree_with_relative_paths(tmp_path):
    """Regression: held-out test files are named RELATIVE to the synth tree, so
    the runner must execute pytest from inside that tree. Guards the cwd bug where
    pytest inherited the caller's cwd and exit-4'd (usage error) on a faithful
    rebuild instead of actually running the generalization check."""
    from run import coverage_diff_verifier, Receipt
    IR = {"interface": [{"symbol": "add", "signature": "add(a, b)"}],
          "allowed_surface": ["add"],
          "tests": {"spec": ["test_spec.py"], "held_out": ["test_held.py"]}}

    def synth(name, src):
        d = tmp_path / name
        d.mkdir()
        (d / "mymod.py").write_text(src)
        (d / "test_held.py").write_text(
            "from mymod import add\ndef test_add():\n    assert add(2, 3) == 5\n")
        return str(d)

    v = coverage_diff_verifier()
    ok = v.verify(None, Receipt(outcome="result", status="complete",
                  evidence={"produces": synth("good", "def add(a, b):\n    return a + b\n")}),
                  {"ir": IR})
    assert ok.verified, ok.defects
    bad = v.verify(None, Receipt(outcome="result", status="complete",
                   evidence={"produces": synth("bad", "def add(a, b):\n    return a * b\n")}),
                   {"ir": IR})
    assert not bad.verified and bad.evidence.get("check") == "held_out"
