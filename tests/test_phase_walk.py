"""B1 — the resumable, journal-driven phase-walk surface (next_phase/record_phase).

Proven WITHOUT a model: the cursor lives in the journal, gates run from disk, and
walking a workflow one phase at a time visits the same phases and reaches the same
terminal as run_workflow's synchronous loop (the shared-core did not drift)."""
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import journal  # noqa: E402
import phase_walk  # noqa: E402
import run as R  # noqa: E402
import workflow as W  # noqa: E402
from situation import Situation  # noqa: E402
from workflow_run import run_workflow  # noqa: E402


def _sit(**over):
    kw = dict(task_kind="change", intent="do the thing", subject="coding")
    kw.update(over)
    return Situation(**kw)


def _ab_workflow():
    """A two-phase carry workflow A -> B (B terminal), no fail edge."""
    a = W.Phase("A", stance="divergent")
    b = W.Phase("B", stance="convergent")
    return W.Workflow("ab", [a, b], edges=[
        ("A", "B", "pass", W.EdgeType.carry),
    ])


_PASS = R.CallableVerifier(lambda u, r, c: R.Verdict(verified=True))
_FAIL = R.CallableVerifier(lambda u, r, c: R.Verdict(verified=False, defects=["gate blocked"]))


class _Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".praxis").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def _events(self, event):
        return [e for e in journal.read(self.root) if e.get("event") == event]


class CarryWalkTest(_Base):
    def test_passing_walk_A_then_B_then_complete(self):
        unit = R.Unit("u1", _sit())
        wf = _ab_workflow()

        first = phase_walk.next_phase(self.root, unit, workflow=wf)
        self.assertEqual(first["status"], "phase")
        self.assertEqual(first["phase"], "A")
        self.assertEqual(first["edge_in"], "create")
        self.assertEqual(first["gate"], "does-it")          # GATES[create]

        rec = phase_walk.record_phase(self.root, unit, "A", {"produces": "artA"},
                                      verifiers={"does-it": _PASS}, workflow=wf)
        self.assertTrue(rec["verified"])
        self.assertTrue(rec["advance"])
        self.assertEqual(rec["next"], "B")

        second = phase_walk.next_phase(self.root, unit, workflow=wf)
        self.assertEqual(second["phase"], "B")
        self.assertEqual(second["edge_in"], "carry")
        self.assertEqual(second["gate"], "regression")      # GATES[carry]
        self.assertEqual(second["carry"], "artA")           # prior produces threaded
        self.assertEqual(second["inputs"], {"A": "artA"})

        phase_walk.record_phase(self.root, unit, "B", {"produces": "artB"},
                                verifiers={"regression": _PASS}, workflow=wf)
        done = phase_walk.next_phase(self.root, unit, workflow=wf)
        self.assertEqual(done["status"], "complete")
        self.assertEqual(done["terminal"], "B")

    def test_failing_gate_at_A_never_hands_out_B(self):
        unit = R.Unit("u1", _sit())
        wf = _ab_workflow()

        phase_walk.next_phase(self.root, unit, workflow=wf)
        rec = phase_walk.record_phase(self.root, unit, "A", {"produces": "artA"},
                                      verifiers={"does-it": _FAIL}, workflow=wf)
        self.assertFalse(rec["verified"])
        self.assertFalse(rec["advance"])
        self.assertIsNone(rec["next"])                      # no fail edge -> halt/re-hand

        # The gate blocked advance: the SAME phase A is re-handed, B is never handed out.
        again = phase_walk.next_phase(self.root, unit, workflow=wf)
        self.assertEqual(again["phase"], "A")
        self.assertNotEqual(again["phase"], "B")

    def test_next_phase_is_idempotent_without_recording(self):
        unit = R.Unit("u1", _sit())
        wf = _ab_workflow()
        a = phase_walk.next_phase(self.root, unit, workflow=wf)
        b = phase_walk.next_phase(self.root, unit, workflow=wf)
        self.assertEqual(a, b)                              # pure read, no mutation
        # ... and after recording A, the cursor is stable at B across repeat reads.
        phase_walk.record_phase(self.root, unit, "A", {"produces": "artA"},
                                verifiers={"does-it": _PASS}, workflow=wf)
        c = phase_walk.next_phase(self.root, unit, workflow=wf)
        d = phase_walk.next_phase(self.root, unit, workflow=wf)
        self.assertEqual(c["phase"], "B")
        self.assertEqual(c, d)


class _Capture:
    def __init__(self):
        self.seen = []

    def run(self, unit, composed):
        self.seen.append(dict(composed))
        return R.Receipt(outcome="result", evidence={"produces": composed.get("phase")})


class EquivalenceTest(_Base):
    """Walking via next_phase/record_phase visits the SAME phases and reaches the
    SAME terminal as run_workflow — the shared decide_step core did not drift."""

    def _walk_resumable(self, wf, verifiers):
        unit = R.Unit("u1", _sit())
        visited = []
        for _ in range(20):  # bounded
            step = phase_walk.next_phase(self.root, unit, workflow=wf)
            if step["status"] != "phase":
                return visited, step["status"]
            name = step["phase"]
            visited.append(name)
            phase_walk.record_phase(self.root, unit, name, {"produces": name},
                                    verifiers=verifiers, workflow=wf)
        raise AssertionError("resumable walk did not terminate")

    def test_tdd_unit_equivalence(self):
        # run_workflow reference
        sync_root = Path(tempfile.mkdtemp())
        (sync_root / ".praxis").mkdir()
        ref = run_workflow(sync_root, R.Unit("u1", _sit()), W.TDD_UNIT, [], _Capture())

        visited, status = self._walk_resumable(W.TDD_UNIT, verifiers={})
        self.assertEqual(status, "complete")
        self.assertEqual(visited, ref["phases"])
        self.assertEqual(visited,
                         ["write-tests", "implement", "refactor", "test-cleanup"])


def _faithful_synth(tree: Path) -> Path:
    tree.mkdir(parents=True, exist_ok=True)
    (tree / "calc.py").write_text(textwrap.dedent("""
        def add(a, b):
            return a + b

        def sub(a, b):
            return a - b
    """))
    return tree


def _held_out(dirpath: Path) -> str:
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


def _ir(held_path: str) -> dict:
    return {
        "interface": [{"symbol": "add", "signature": "add(a, b)"},
                      {"symbol": "sub", "signature": "sub(a, b)"}],
        "allowed_surface": ["add", "sub"],
        "tests": {"spec": ["t1", "t2", "t3"], "held_out": [held_path]},
    }


class RebuildWalkTest(_Base):
    """The rebuild-triple walk over the resumable surface, gates read from disk."""

    def _drive_to_synthesize(self, unit, wf):
        synth = _faithful_synth(self.root / "synth")
        held = _held_out(self.root / "held")
        ir = _ir(held)
        # extract passes (valid spec); rebuild verifiers are built from config (none).
        phase_walk.next_phase(self.root, unit, workflow=wf)
        phase_walk.record_phase(self.root, unit, "extract", {"produces": ir}, workflow=wf)
        return synth, ir

    def test_next_phase_at_synthesize_returns_isolation_directive(self):
        unit = R.Unit("u1", _sit(workflow="rebuild-triple"))
        wf = W.REBUILD_TRIPLE
        synth, ir = self._drive_to_synthesize(unit, wf)

        step = phase_walk.next_phase(self.root, unit, workflow=wf)
        self.assertEqual(step["phase"], "synthesize")
        self.assertEqual(step["edge_in"], "extract")
        self.assertEqual(step["gate"], "coverage-diff")
        self.assertEqual(step["spec"], ir)                    # spec threaded on the extract edge
        iso = step["isolation"]
        self.assertIsNotNone(iso)
        self.assertTrue(iso["seed_worktree"])
        self.assertEqual(iso["seam"], "extract->synthesize")
        self.assertEqual(iso["spec"], ir)

    def test_out_of_worktree_read_trips_wire_and_does_not_advance(self):
        unit = R.Unit("u1", _sit(workflow="rebuild-triple"))
        wf = W.REBUILD_TRIPLE
        synth, ir = self._drive_to_synthesize(unit, wf)

        rec = phase_walk.record_phase(
            self.root, unit, "synthesize",
            {"produces": str(synth), "tool_log": ["/etc/passwd"]}, workflow=wf)
        self.assertFalse(rec["verified"])                   # tripwire caught the copy
        self.assertFalse(rec["advance"])
        # cursor did NOT advance past synthesize — the same phase is re-handed.
        again = phase_walk.next_phase(self.root, unit, workflow=wf)
        self.assertEqual(again["phase"], "synthesize")

    def test_clean_synthesize_advances_to_complete(self):
        unit = R.Unit("u1", _sit(workflow="rebuild-triple"))
        wf = W.REBUILD_TRIPLE
        synth, ir = self._drive_to_synthesize(unit, wf)

        rec = phase_walk.record_phase(
            self.root, unit, "synthesize",
            {"produces": str(synth), "tool_log": [str(synth / "calc.py")]}, workflow=wf)
        self.assertTrue(rec["verified"], rec["defects"])
        self.assertTrue(rec["advance"])
        done = phase_walk.next_phase(self.root, unit, workflow=wf)
        self.assertEqual(done["status"], "complete")
        self.assertEqual(done["terminal"], "synthesize")


class NoWorkflowTest(_Base):
    def test_unit_without_workflow_returns_no_workflow(self):
        unit = R.Unit("u1", _sit())                         # no situation.workflow
        self.assertEqual(phase_walk.next_phase(self.root, unit)["status"], "no-workflow")
        self.assertEqual(
            phase_walk.record_phase(self.root, unit, "A", {})["status"], "no-workflow")


if __name__ == "__main__":
    unittest.main()
