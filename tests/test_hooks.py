import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import contributors as cb  # noqa: E402
import journal  # noqa: E402
import plan as P  # noqa: E402
import run as R  # noqa: E402
import schedule as S  # noqa: E402
from situation import Situation  # noqa: E402


def _sit(**over):
    kw = dict(task_kind="change", intent="do the thing", subject="coding")
    kw.update(over)
    return Situation(**kw)


def _u(uid="u1", **sit):
    return R.Unit(uid, _sit(label="implement-feature", **sit))


def _ok(unit, composed):
    return R.Receipt(outcome="result")


def _stall(unit, composed):
    return R.Receipt(outcome="stall", status="blocked")


def _verified(unit, receipt, composed):
    return R.Verdict(verified=True)


class _HookContributor:
    def __init__(self):
        self.fires = {"verify": 0, "close": 0}

    def contribute(self, situation):
        return [cb.Contribution(source="hookc", title="t", body="b")]

    def hooks(self):
        return {"verify": self._on_verify, "close": self._on_close}

    def _on_verify(self, ctx):
        self.fires["verify"] += 1
        ctx.add_note("hookc", "unit passed", kind="ratify")

    def _on_close(self, ctx):
        self.fires["close"] += 1
        ctx.add_note("hookc", f"saw {len(ctx.notes())} note(s)", scope="run")


class _ContributeOnly:
    def contribute(self, situation):
        return [cb.Contribution(source="plain", title="t", body="b")]


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".praxis").mkdir()

    def tearDown(self):
        self.tmp.cleanup()


class LedgerTest(Base):
    def test_note_and_notes_roundtrip_with_filter(self):
        journal.note(self.root, unit="u1", source="s", body="first", kind="x")
        journal.note(self.root, unit="u2", source="s", body="second")
        journal.note(self.root, source="s", body="run-wide")
        alln = journal.notes(self.root)
        self.assertEqual([n["body"] for n in alln], ["first", "second", "run-wide"])
        self.assertEqual(alln[0]["kind"], "x")
        u1 = journal.notes(self.root, unit="u1")
        self.assertEqual([n["body"] for n in u1], ["first"])
        self.assertEqual(journal.notes(self.root, unit="u2")[0]["body"], "second")

    def test_note_uses_distinct_event_name(self):
        journal.note(self.root, unit="u1", source="s", body="b")
        events = {e["event"] for e in journal.read(self.root)}
        self.assertIn("note", events)
        self.assertNotIn("unit.note", events)


class VerifyHookTest(Base):
    def test_fires_once_on_verified_pass_and_can_add_note(self):
        c = _HookContributor()
        R.run_unit(self.root, _u(), [c], R.InlineExecutor(_ok),
                   R.CallableVerifier(_verified))
        self.assertEqual(c.fires["verify"], 1)
        notes = journal.notes(self.root, unit="u1")
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["body"], "unit passed")
        self.assertEqual(notes[0]["kind"], "ratify")

    def test_does_not_fire_on_stall(self):
        c = _HookContributor()
        R.run_unit(self.root, _u(), [c], R.InlineExecutor(_stall),
                   R.CallableVerifier(_verified))
        self.assertEqual(c.fires["verify"], 0)
        self.assertEqual(journal.notes(self.root), [])

    def test_does_not_fire_without_verifier(self):
        c = _HookContributor()
        R.run_unit(self.root, _u(), [c], R.InlineExecutor(_ok), verifier=None)
        self.assertEqual(c.fires["verify"], 0)


class CloseHookTest(Base):
    def test_close_fires_once_at_end_of_run(self):
        c = _HookContributor()
        R.run(R.Plan([_u()]), [c], R.InlineExecutor(_ok), self.root,
              verifier=R.CallableVerifier(_verified))
        self.assertEqual(c.fires["close"], 1)
        # close hook read the verify note accumulated during the run
        run_notes = [n for n in journal.notes(self.root) if n.get("scope") == "run"]
        self.assertEqual(len(run_notes), 1)
        self.assertEqual(run_notes[0]["body"], "saw 1 note(s)")

    def test_close_fires_once_via_run_dag(self):
        c = _HookContributor()
        S.run_dag(R.Plan([_u()]), [c], R.InlineExecutor(_ok), self.root,
                  verifier=R.CallableVerifier(_verified))
        self.assertEqual(c.fires["close"], 1)

    def test_close_fires_once_via_plan_and_run(self):
        c = _HookContributor()
        P.plan_and_run(self.root, [P.TaskSpec(intent="do it", id="u1", label="impl")],
                       [c], R.InlineExecutor(_ok),
                       verifier=R.CallableVerifier(_verified))
        self.assertEqual(c.fires["close"], 1)


class _UnitCloseRecorder:
    """Contributor whose only hook is unit-close; records (unit_id, receipt, verdict)."""

    def __init__(self):
        self.seen = []

    def contribute(self, situation):
        return [cb.Contribution(source="uc", title="t", body="b")]

    def hooks(self):
        return {"unit-close": self._on_unit_close}

    def _on_unit_close(self, ctx):
        self.seen.append((getattr(ctx.unit, "id", None), ctx.receipt, ctx.verdict))


class _CloseOnlyRecorder:
    """Contributor whose only hook is the batch close."""

    def __init__(self):
        self.seen = []

    def contribute(self, situation):
        return []

    def hooks(self):
        return {"close": self._on_close}

    def _on_close(self, ctx):
        self.seen.append((getattr(ctx.unit, "id", None), ctx.receipt))


class UnitCloseHookTest(Base):
    def test_fires_once_on_verified_pass_with_receipt_and_verdict(self):
        rec = _UnitCloseRecorder()
        R.run_unit(self.root, _u(), [rec], R.InlineExecutor(_ok),
                   R.CallableVerifier(_verified))
        self.assertEqual(len(rec.seen), 1)
        uid, receipt, verdict = rec.seen[0]
        self.assertEqual(uid, "u1")
        self.assertEqual(receipt["outcome"], "result")
        # canonical 6-key Receipt.to_dict shape, payload reachable via evidence
        self.assertEqual(set(receipt),
                         {"outcome", "status", "surfaced", "evidence", "cost", "tool_calls"})
        self.assertTrue(verdict["verified"])

    def test_fires_once_on_stall_with_none_verdict(self):
        rec = _UnitCloseRecorder()
        R.run_unit(self.root, _u(), [rec], R.InlineExecutor(_stall),
                   R.CallableVerifier(_verified))
        self.assertEqual(len(rec.seen), 1)
        uid, receipt, verdict = rec.seen[0]
        self.assertEqual(receipt["outcome"], "stall")
        self.assertIsNone(verdict)

    def test_fires_once_without_verifier(self):
        rec = _UnitCloseRecorder()
        R.run_unit(self.root, _u(), [rec], R.InlineExecutor(_ok), verifier=None)
        self.assertEqual(len(rec.seen), 1)
        self.assertEqual(rec.seen[0][1]["outcome"], "result")
        self.assertIsNone(rec.seen[0][2])

    def test_no_unit_close_hook_is_unaffected(self):
        c = _CloseOnlyRecorder()
        # a contributor lacking unit-close must not raise / not be invoked
        R.run(R.Plan([_u()]), [c], R.InlineExecutor(_ok), self.root,
              verifier=R.CallableVerifier(_verified))
        self.assertEqual(len(c.seen), 1)  # only its close hook fired

    def test_fires_once_per_unit_on_dag_path_and_close_once(self):
        rec = _UnitCloseRecorder()
        closer = _CloseOnlyRecorder()
        plan = R.Plan([_u("u1"), R.Unit("u2", _sit(label="impl2"), depends_on=["u1"])])
        S.run_dag(plan, [rec, closer], R.InlineExecutor(_ok), self.root,
                  verifier=R.CallableVerifier(_verified))
        # exactly-once per unit, no duplicates
        self.assertEqual(sorted(uid for uid, _r, _v in rec.seen), ["u1", "u2"])
        self.assertEqual(len(rec.seen), 2)
        # batch close still fires exactly once per run
        self.assertEqual(len(closer.seen), 1)
        self.assertIsNone(closer.seen[0][0])   # empty context: no unit
        self.assertIsNone(closer.seen[0][1])   # empty context: no receipt


class FireNoOpTest(Base):
    def test_empty_contributors_is_noop(self):
        ctx = cb.HookContext(root=self.root, step="verify", unit=_u())
        cb.fire([], "verify", ctx)  # must not raise

    def test_contribute_only_contributor_is_noop(self):
        ctx = cb.HookContext(root=self.root, step="verify")
        cb.fire([_ContributeOnly()], "verify", ctx)  # must not raise
        cb.fire([_ContributeOnly()], "close", ctx)


if __name__ == "__main__":
    unittest.main()
