import os
import sys
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import isolation  # noqa: E402
import phase_walk  # noqa: E402
import run as R  # noqa: E402
import workflow as W  # noqa: E402
from situation import Situation  # noqa: E402

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

class SeedSynthWorktreeTest(unittest.TestCase):
    def test_seeds_spec_not_original_with_own_marker(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)

            original = base / "original"
            original.mkdir()
            (original / "calc.py").write_text(FAITHFUL_IMPL)

            specs = []
            for i in range(3):
                p = original / f"test_spec_{i}.py"
                p.write_text(f"def test_{i}():\n    assert True\n")
                specs.append(str(p))

            cfg = original / "pytest.ini"
            cfg.write_text("[pytest]\n")

            ir = _ir(specs, ["test_held_1"])
            dest = base / "synth"
            wt = isolation.seed_synth_worktree(ir, dest, extra=[str(cfg)])

            self.assertEqual(wt, dest)

            for i in range(3):
                self.assertTrue((dest / f"test_spec_{i}.py").is_file())
            self.assertTrue((dest / "pytest.ini").is_file())

            self.assertFalse((dest / "calc.py").exists())
            self.assertEqual(list(dest.rglob("calc.py")), [])

            self.assertTrue((dest / ".praxis" / "config.json").is_file())

    def test_marker_resolves_worktree_as_its_own_root(self):
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
            (site / "calc" / "__init__.py").write_text("")
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

        self.assertEqual(isolation.scan_tripwire(["calc.py"], self.wt), [])

    def test_relative_escape_flagged(self):
        v = isolation.scan_tripwire(["../original/calc.py"], self.wt)
        self.assertEqual(len(v), 1)

    def test_symlink_inside_pointing_out_flagged(self):
        link = self.wt / "sneaky.py"
        link.symlink_to(self.original)
        v = isolation.scan_tripwire([str(link)], self.wt)
        self.assertEqual(len(v), 1)
        self.assertEqual(Path(v[0]["resolved"]), self.original.resolve())

    def test_empty_log_passes(self):
        self.assertEqual(isolation.scan_tripwire([], self.wt), [])
        self.assertEqual(isolation.scan_tripwire(None, self.wt), [])

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

        clean = R.Receipt(outcome="result",
                          evidence={"produces": str(synth), "tool_log": []})
        self.assertTrue(gate.verify(None, clean, {"spec": ir}).verified)

        copied = R.Receipt(outcome="result",
                           evidence={"produces": str(synth),
                                     "tool_log": [str(original)]})
        v = gate.verify(None, copied, {"spec": ir})
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

        verifiers = {"does-it": R.adequacy_verifier(None),
                     "coverage-diff": isolation.synthesize_exit_gate(
                         R.coverage_diff_verifier())}
        unit = R.Unit("u1", _sit())
        wf = W.REBUILD_TRIPLE
        phase_walk.record_phase(self.root, unit, "extract", {"produces": ir},
                                verifiers=verifiers, workflow=wf)
        phase_walk.record_phase(self.root, unit, "synthesize",
                                {"produces": str(synth),
                                 "tool_log": tool_log(original)},
                                verifiers=verifiers, workflow=wf)

    def test_copy_read_halts_at_synthesize(self):
        self._walk(lambda orig: [str(orig)])
        exited = self._events("phase.exited")
        self.assertTrue(exited["extract"]["verified"])
        self.assertFalse(exited["synthesize"]["verified"])

    def test_clean_read_advances(self):
        self._walk(lambda orig: [])
        exited = self._events("phase.exited")
        self.assertTrue(exited["extract"]["verified"])
        self.assertTrue(exited["synthesize"]["verified"])

class ReadToolLogTest(unittest.TestCase):

    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _log(self, lines):
        p = self.dir / "tripwire.log"
        p.write_text("".join(l + "\n" for l in lines))
        return p

    def test_filters_to_agent_and_extracts_cat_and_excludes_parent(self):

        log = self._log([
            "agentA\tRead\t/repo/original/calc.py",
            "agentB\tBash\tcat /repo/original/secret.py",
            "\tRead\t/parent/only.py",
            "agentA\tBash\ttail /repo/original/calc.py",
        ])

        got_a = isolation.read_tool_log(log, agent_id="agentA")
        self.assertEqual(got_a, ["/repo/original/calc.py",
                                 "/repo/original/calc.py"])

        got_b = isolation.read_tool_log(log, agent_id="agentB")
        self.assertEqual(got_b, ["/repo/original/secret.py"])

        self.assertNotIn("/parent/only.py", got_a)
        self.assertNotIn("/parent/only.py", got_b)

    def test_no_agent_filter_returns_all_reads(self):
        log = self._log([
            "agentA\tRead\t/x/a.py",
            "agentB\tBash\tcat /x/b.py",
        ])
        self.assertEqual(isolation.read_tool_log(log),
                         ["/x/a.py", "/x/b.py"])

    def test_missing_log_is_fail_soft(self):
        self.assertEqual(isolation.read_tool_log(self.dir / "nope.log"), [])

    def test_grep_and_find_shell_reads_extracted(self):
        log = self._log([
            "agentA\tBash\tgrep -n needle /repo/original/calc.py",
            "agentA\tBash\tfind /repo/original -name '*.py'",
        ])
        got = isolation.read_tool_log(log, agent_id="agentA")
        self.assertIn("/repo/original/calc.py", got)
        self.assertIn("/repo/original", got)

class ReadToolLogEndToEndTest(unittest.TestCase):

    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.wt = self.base / "synth"
        self.wt.mkdir()
        (self.wt / "calc.py").write_text(FAITHFUL_IMPL)
        self.original = self.base / "original" / "calc.py"
        self.original.parent.mkdir()
        self.original.write_text(FAITHFUL_IMPL)

    def tearDown(self):
        self.tmp.cleanup()

    def _log(self, lines):
        p = self.base / "tripwire.log"
        p.write_text("".join(l + "\n" for l in lines))
        return p

    def test_out_of_worktree_bash_read_flagged(self):
        log = self._log([
            f"agentZ\tRead\t{self.wt / 'calc.py'}",
            f"agentZ\tBash\tcat {self.original}",
        ])
        reads = isolation.read_tool_log(log, agent_id="agentZ")
        violations = isolation.scan_tripwire(reads, self.wt)
        self.assertEqual(len(violations), 1)
        self.assertEqual(Path(violations[0]["resolved"]),
                         self.original.resolve())

    def test_in_worktree_only_log_passes(self):
        log = self._log([f"agentZ\tRead\t{self.wt / 'calc.py'}"])
        reads = isolation.read_tool_log(log, agent_id="agentZ")
        self.assertEqual(isolation.scan_tripwire(reads, self.wt), [])

class TripwireHookScriptTest(unittest.TestCase):

    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.log = self.dir / "tripwire.log"
        self.hook = (Path(__file__).resolve().parents[1] / "hooks"
                     / "tripwire_log.sh")

    def tearDown(self):
        self.tmp.cleanup()

    def _run(self, payload):
        import json
        import subprocess
        env = dict(os.environ, PRAXIS_TRIPWIRE_LOG=str(self.log))
        proc = subprocess.run(
            ["bash", str(self.hook)], input=json.dumps(payload),
            capture_output=True, text=True, env=env)
        return proc

    def test_only_subagent_read_is_logged(self):

        p1 = self._run({"agent_id": "sub-1", "agent_type": "synth",
                        "tool_name": "Read",
                        "tool_input": {"file_path": "/repo/original/calc.py"}})
        p2 = self._run({"tool_name": "Read",
                        "tool_input": {"file_path": "/parent/only.py"}})
        self.assertEqual(p1.returncode, 0)
        self.assertEqual(p2.returncode, 0)
        self.assertTrue(self.log.is_file())
        contents = self.log.read_text()
        self.assertIn("sub-1\tRead\t/repo/original/calc.py", contents)
        self.assertNotIn("/parent/only.py", contents)

        self.assertEqual(len([l for l in contents.splitlines() if l.strip()]), 1)

    def test_subagent_bash_command_is_logged(self):
        p = self._run({"agent_id": "sub-2", "agent_type": "synth",
                       "tool_name": "Bash",
                       "tool_input": {"command": "cat /repo/original/calc.py"}})
        self.assertEqual(p.returncode, 0)
        contents = self.log.read_text()
        self.assertIn("sub-2\tBash\tcat /repo/original/calc.py", contents)

    def test_replay_of_hook_output_feeds_tripwire(self):

        self._run({"agent_id": "sub-3", "tool_name": "Bash",
                   "tool_input": {"command": "cat /outside/original.py"}})
        reads = isolation.read_tool_log(self.log, agent_id="sub-3")
        self.assertEqual(reads, ["/outside/original.py"])

if __name__ == "__main__":
    unittest.main()
