import shutil
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import rebuild_spec  # noqa: E402
import run as R  # noqa: E402
import workflow as W  # noqa: E402
import phase_walk  # noqa: E402
from situation import Situation  # noqa: E402

def _sit(**over):
    kw = dict(task_kind="change", intent="rebuild", subject="coding", workflow="rebuild-triple")
    kw.update(over)
    return Situation(**kw)

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
        self.assertIsInstance(rebuild_spec.validate_spec(self._base()), dict)

    def test_empty_held_out_rejected(self):
        ir = self._base()
        ir["tests"]["held_out"] = []
        with self.assertRaises(rebuild_spec.SpecError):
            rebuild_spec.validate_spec(ir)

    def test_trivial_held_out_fraction_rejected(self):

        ir = self._base()
        ir["tests"]["spec"] = [f"t{i}" for i in range(9)]
        ir["tests"]["held_out"] = ["test_one"]
        with self.assertRaises(rebuild_spec.SpecError):
            rebuild_spec.validate_spec(ir)

    def test_malformed_ir_fails_closed(self):
        for bad in (None, [], "not-json", {"interface": "x"},
                    {"interface": [], "allowed_surface": [], "tests": {}}):
            with self.assertRaises(rebuild_spec.SpecError):
                rebuild_spec.validate_spec(bad)

    def test_parse_spec_accepts_json_string(self):
        import json
        self.assertIsInstance(rebuild_spec.parse_spec(json.dumps(self._base())), dict)

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
        return self.verifier.verify(None, receipt, {"spec": ir})

    def test_faithful_synth_passes(self):
        v = self._run(FAITHFUL_IMPL)
        self.assertTrue(v.verified, v.defects)
        self.assertEqual(v.evidence["check"], "all")

    def test_missing_interface_symbol_fails_completeness(self):
        impl = "def add(a, b):\n    return a + b\n"
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
        v = self.verifier.verify(None, receipt, {"spec": {"interface": "bad"}})
        self.assertFalse(v.verified)
        self.assertEqual(v.evidence["check"], "spec")

    def test_missing_synth_path_fails_closed(self):
        held = _held_out_test(self.dir / "held")
        receipt = R.Receipt(outcome="result", evidence={})
        v = self.verifier.verify(None, receipt, {"spec": _ir(held)})
        self.assertFalse(v.verified)
        self.assertEqual(v.evidence["check"], "synth-path")

class AdequacyVerifierTest(unittest.TestCase):

    def _extract_receipt(self, ir):

        return R.Receipt(outcome="result", evidence={"produces": ir})

    def test_adequate_ir_passes_when_coverage_passes(self):
        cov = R.CommandVerifier(lambda u, r, c: ["true"])
        v = R.adequacy_verifier(cov)
        out = v.verify(None, self._extract_receipt(_ir("t/test_held.py")), {})
        self.assertTrue(out.verified, out.defects)

    def test_ir_failing_adequacy_threshold_fails_at_extract(self):
        cov = R.CommandVerifier(lambda u, r, c: ["false"])
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
        self.assertEqual(out.evidence["check"], "spec-split")

class RebuildWalkTest(unittest.TestCase):

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

        verifiers = {"does-it": R.adequacy_verifier(None),
                     "coverage-diff": R.coverage_diff_verifier()}
        unit = R.Unit("u1", _sit())
        wf = W.REBUILD_TRIPLE
        phase_walk.record_phase(self.root, unit, "extract", {"produces": ir},
                                verifiers=verifiers, workflow=wf)
        phase_walk.record_phase(self.root, unit, "synthesize",
                                {"produces": str(synth)},
                                verifiers=verifiers, workflow=wf)
        return {"phases": ["extract", "synthesize"]}

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
        self.assertFalse(exited["synthesize"]["verified"])

_TS_TSC_CMD = ["npx", "--yes", "-p", "typescript", "tsc"]

_TS_HELD_CMD = ["node"]

def _ts_toolchain_ok() -> bool:
    if shutil.which("node") is None:
        return False
    try:
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "probe.ts"
            src.write_text("export function ping(): number { return 1; }\n")
            surface, _ = R._ts_surface(Path(td), _TS_TSC_CMD, 300)
        return "ping" in surface
    except Exception:
        return False

_TS_OK = _ts_toolchain_ok()

@unittest.skipUnless(_TS_OK, "tsc/node toolchain unavailable")
class TsCoverageDiffVerifierTest(unittest.TestCase):

    FAITHFUL = ("export function add(a: number, b: number): number { return a + b; }\n"
                "export function sub(a: number, b: number): number { return a - b; }\n")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.verifier = R.coverage_diff_verifier()

    def tearDown(self):
        self.tmp.cleanup()

    def _synth(self, name, impl):
        d = self.dir / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "calc.ts").write_text(impl)
        return d

    def _held(self, name, module_dir, body):
        p = self.dir / f"held_{name}.ts"
        rel = "./" + str(module_dir.relative_to(self.dir)) + "/calc.ts"
        p.write_text(f'import {{ add, sub }} from "{rel}";\n'
                     'import assert from "node:assert";\n' + body)
        return str(p)

    def _ir(self, held, **over):
        ir = {"language": "typescript", "surface_cmd": _TS_TSC_CMD,
              "held_out_cmd": _TS_HELD_CMD,
              "interface": [{"symbol": "add", "signature": "add(a, b)"},
                            {"symbol": "sub", "signature": "sub(a, b)"}],
              "allowed_surface": ["add", "sub"],
              "tests": {"spec": ["s1", "s2", "s3"], "held_out": [held]}}
        ir.update(over)
        return ir

    def _verify(self, synth, ir):
        receipt = R.Receipt(outcome="result", evidence={"produces": str(synth)})
        return self.verifier.verify(None, receipt, {"spec": ir})

    def test_faithful_ts_synth_passes(self):
        synth = self._synth("good", self.FAITHFUL)
        held = self._held("good", synth,
                          "assert.strictEqual(add(2, 3), 5);\n"
                          "assert.strictEqual(sub(5, 2), 3);\n")
        v = self._verify(synth, self._ir(held))
        self.assertTrue(v.verified, v.defects)
        self.assertEqual(v.evidence["check"], "all")
        self.assertEqual(v.evidence["surface"], ["add", "sub"])

    def test_missing_interface_symbol_fails_completeness(self):
        synth = self._synth("miss",
                            "export function add(a: number, b: number): number { return a + b; }\n")
        held = self._held("miss", synth, "assert.strictEqual(add(2, 3), 5);\n")
        v = self._verify(synth, self._ir(held))
        self.assertFalse(v.verified)
        self.assertEqual(v.evidence["check"], "interface")
        self.assertIn("sub", v.evidence["missing"])

    def test_extra_surface_fails_losslessness(self):
        synth = self._synth("extra", self.FAITHFUL
                            + "export function leak(z: number): number { return z; }\n")
        held = self._held("extra", synth,
                          "assert.strictEqual(add(2, 3), 5);\n"
                          "assert.strictEqual(sub(5, 2), 3);\n")
        v = self._verify(synth, self._ir(held))
        self.assertFalse(v.verified)
        self.assertEqual(v.evidence["check"], "surface")
        self.assertIn("leak", v.evidence["extra"])

    def test_failing_held_out_fails_generalization(self):

        synth = self._synth("bad",
                            "export function add(a: number, b: number): number { return a * b; }\n"
                            "export function sub(a: number, b: number): number { return a - b; }\n")
        held = self._held("bad", synth, "assert.strictEqual(add(2, 3), 5);\n")
        v = self._verify(synth, self._ir(held))
        self.assertFalse(v.verified)
        self.assertEqual(v.evidence["check"], "held_out")
        self.assertNotEqual(v.evidence["returncode"], 0)

class TsMutationAdapterTest(unittest.TestCase):

    def test_unwired_without_threshold(self):
        self.assertIsNone(R.ts_mutation_verifier("pnpm exec stryker run", None))

    def test_score_above_threshold_passes(self):
        v = R.ts_mutation_verifier("sh -c 'echo mutation score: 0.95'", 0.9)
        self.assertTrue(v.verify(None, None, {}).verified)

    def test_score_below_threshold_fails(self):
        v = R.ts_mutation_verifier("sh -c 'echo 0.50'", 0.9)
        self.assertFalse(v.verify(None, None, {}).verified)

    def test_exit_code_verdict_when_no_score(self):
        self.assertFalse(
            R.ts_mutation_verifier("this-stryker-does-not-exist-xyz", 0.9)
            .verify(None, None, {}).verified)

if __name__ == "__main__":
    unittest.main()

def test_held_out_runs_from_synth_tree_with_relative_paths(tmp_path):
    from run import coverage_diff_verifier, Receipt
    spec = {"interface": [{"symbol": "add", "signature": "add(a, b)"}],
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
                  {"spec": spec})
    assert ok.verified, ok.defects
    bad = v.verify(None, Receipt(outcome="result", status="complete",
                   evidence={"produces": synth("bad", "def add(a, b):\n    return a * b\n")}),
                   {"spec": spec})
    assert not bad.verified and bad.evidence.get("check") == "held_out"
