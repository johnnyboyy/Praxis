import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "forge_check.py"

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import forge_check  # noqa: E402

VALID_MODULE = textwrap.dedent("""
    from workflow import EdgeType, Phase, Workflow

    PRAXIS_PLUGIN = True

    A = Phase("fc-a", stance="divergent", intent="start", produces="thing-a")
    B = Phase("fc-b", stance="convergent", intent="finish", produces="thing-b")

    FC_LINEAR = Workflow(
        name="fc-linear",
        phases=[A, B],
        edges=[("fc-a", "fc-b", "pass", EdgeType.carry)],
    )
""")

INVALID_MODULE = textwrap.dedent("""
    from workflow import EdgeType, Phase, Workflow

    PRAXIS_PLUGIN = True

    A = Phase("fc-a", stance="divergent", intent="start", produces="thing-a")

    FC_BROKEN = Workflow(
        name="fc-broken",
        phases=[A],
        edges=[("fc-a", "fc-ghost", "pass", EdgeType.carry)],
    )
""")

FACT_GATED_MODULE = textwrap.dedent("""
    from workflow import EdgeType, Phase, Workflow

    PRAXIS_PLUGIN = True

    GATE = Phase("fc-gate", stance="neutral", intent="route by color",
                 produces="color-fact", delivery="deterministic")
    RED = Phase("fc-red", stance="convergent", intent="handle red", produces="red-thing")
    BLUE = Phase("fc-blue", stance="convergent", intent="handle blue", produces="blue-thing")

    def _is_red(evidence):
        return evidence.get("color") == "red"

    def _is_blue(evidence):
        return evidence.get("color") == "blue"

    FC_FACTS = Workflow(
        name="fc-facts",
        phases=[GATE, RED, BLUE],
        edges=[
            ("fc-gate", "fc-red", "fact", EdgeType.create, _is_red),
            ("fc-gate", "fc-blue", "fact", EdgeType.create, _is_blue),
        ],
    )
""")

CONTRIBUTOR_MODULE = textwrap.dedent("""
    from workflow import EdgeType, Phase, Workflow

    PRAXIS_PLUGIN = True

    P1 = Phase("fc-c1", stance="divergent", intent="start", produces="thing-1")
    P2 = Phase("fc-c2", stance="convergent", intent="finish", produces="thing-2")

    FC_CONTRIB = Workflow(
        name="fc-contrib",
        phases=[P1, P2],
        edges=[("fc-c1", "fc-c2", "pass", EdgeType.carry)],
    )

    class FCContributor:
        source = "fc-contrib-pack"

        def contribute(self, situation):
            return []

        def phases(self):
            return [P1, P2]

        def workflows(self):
            return [FC_CONTRIB]

    def make(root):
        return FCContributor()
""")


def _write(tmp: Path, name: str, source: str) -> Path:
    p = tmp / name
    p.write_text(source)
    return p


def _run_cli(*args) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *[str(a) for a in args]],
        capture_output=True, text=True,
    )


class ValidModuleTest(unittest.TestCase):
    def test_valid_module_exits_zero_and_reaches_terminal(self):
        with tempfile.TemporaryDirectory() as tmp:
            mod = _write(Path(tmp), "fc_valid.py", VALID_MODULE)
            proc = _run_cli(mod)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            report = json.loads(proc.stdout)
            self.assertEqual(report["problems"], [])
            self.assertEqual(len(report["workflows"]), 1)
            wf = report["workflows"][0]
            self.assertEqual(wf["name"], "fc-linear")
            self.assertTrue(wf["valid"])
            self.assertEqual(wf["terminal"], "fc-b")
            self.assertEqual(wf["walked"], ["fc-a", "fc-b"])


class InvalidModuleTest(unittest.TestCase):
    def test_unknown_edge_endpoint_reports_problem_and_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as tmp:
            mod = _write(Path(tmp), "fc_invalid.py", INVALID_MODULE)
            proc = _run_cli(mod)
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            report = json.loads(proc.stdout)
            self.assertTrue(report["problems"])
            self.assertTrue(any("fc-ghost" in p for p in report["problems"]))
            # an invalid workflow is not dry-walked at all
            self.assertEqual(report["workflows"], [])


class FactGatedModuleTest(unittest.TestCase):
    def test_without_facts_warns_and_does_not_reach_terminal(self):
        with tempfile.TemporaryDirectory() as tmp:
            mod = _write(Path(tmp), "fc_facts.py", FACT_GATED_MODULE)
            proc = _run_cli(mod)
            # chosen semantics: an unexercised fact-gated route is a FAILING
            # check (exit 1) — the walk did not prove any real route reaches
            # a terminal, so it cannot be honestly reported as green.
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            report = json.loads(proc.stdout)
            self.assertEqual(report["problems"], [])
            wf = report["workflows"][0]
            self.assertIsNone(wf["terminal"])
            self.assertTrue(any("fact-gated" in w for w in wf["warnings"]))

    def test_with_facts_routes_and_reaches_terminal(self):
        with tempfile.TemporaryDirectory() as tmp:
            mod = _write(Path(tmp), "fc_facts.py", FACT_GATED_MODULE)
            proc = _run_cli(mod, "--facts", '{"fc-gate": {"color": "red"}}')
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            report = json.loads(proc.stdout)
            wf = report["workflows"][0]
            self.assertEqual(wf["terminal"], "fc-red")
            self.assertEqual(wf["walked"], ["fc-gate", "fc-red"])


class ContributorModuleTest(unittest.TestCase):
    def test_make_root_contributor_is_used(self):
        with tempfile.TemporaryDirectory() as tmp:
            mod = _write(Path(tmp), "fc_contrib.py", CONTRIBUTOR_MODULE)
            proc = _run_cli(mod, "--root", tmp)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            report = json.loads(proc.stdout)
            self.assertEqual(sorted(report["phases"]), ["fc-c1", "fc-c2"])
            self.assertEqual(report["workflows"][0]["name"], "fc-contrib")
            self.assertEqual(report["workflows"][0]["terminal"], "fc-c2")


class WorkflowFilterTest(unittest.TestCase):
    def test_workflow_flag_walks_only_the_named_workflow(self):
        with tempfile.TemporaryDirectory() as tmp:
            mod = _write(Path(tmp), "fc_valid2.py", VALID_MODULE)
            proc = _run_cli(mod, "--workflow", "fc-linear")
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            report = json.loads(proc.stdout)
            self.assertEqual(len(report["workflows"]), 1)

    def test_unknown_workflow_name_is_a_problem(self):
        with tempfile.TemporaryDirectory() as tmp:
            mod = _write(Path(tmp), "fc_valid3.py", VALID_MODULE)
            proc = _run_cli(mod, "--workflow", "does-not-exist")
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            report = json.loads(proc.stdout)
            self.assertTrue(any("does-not-exist" in p for p in report["problems"]))


class RealPluginsSmokeTest(unittest.TestCase):
    def test_coding_process_plugin_passes(self):
        proc = _run_cli(ROOT / "plugins" / "coding-process" / "coding_process_plugin.py")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        report = json.loads(proc.stdout)
        self.assertEqual(report["workflows"][0]["terminal"], "test-cleanup")

    def test_rebuild_plugin_passes(self):
        proc = _run_cli(ROOT / "plugins" / "rebuild" / "rebuild_plugin.py")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        report = json.loads(proc.stdout)
        self.assertEqual(report["workflows"][0]["terminal"], "synthesize")


class DirectFunctionTest(unittest.TestCase):
    """Exercise the functions directly (not just via subprocess) to keep the
    CLI a thin wrapper honest — same module, same behavior."""

    def test_run_check_valid_module(self):
        with tempfile.TemporaryDirectory() as tmp:
            mod = _write(Path(tmp), "fc_direct.py", VALID_MODULE)
            report, ok = forge_check.run_check(mod, None, Path(tmp))
            self.assertTrue(ok)
            self.assertEqual(report["workflows"][0]["terminal"], "fc-b")


if __name__ == "__main__":
    unittest.main()
