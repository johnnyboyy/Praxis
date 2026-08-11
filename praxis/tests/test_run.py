import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import journal  # noqa: E402
import providers as pv  # noqa: E402
import run as R  # noqa: E402
from situation import Situation  # noqa: E402


def _sit(**over):
    kw = dict(task_kind="change", intent="do the thing", subject="coding")
    kw.update(over)
    return Situation(**kw)


def _result(unit, composed):
    return R.Receipt(outcome="result", status="complete", tool_calls=3)


class ReceiptTest(unittest.TestCase):
    def test_rejects_bad_outcome(self):
        with self.assertRaises(ValueError):
            R.Receipt(outcome="maybe")

    def test_roundtrip(self):
        r = R.Receipt(outcome="stall", status="blocked", surfaced=["q?"], tool_calls=2,
                      cost={"tokens": 10, "usd": 0.01})
        self.assertEqual(R.Receipt.from_dict(r.to_dict()).to_dict(), r.to_dict())

    def test_from_dict_defaults(self):
        r = R.Receipt.from_dict({})
        self.assertEqual(r.outcome, "result")
        self.assertEqual(r.status, "complete")
        self.assertEqual(r.surfaced, [])


class UnitTest(unittest.TestCase):
    def test_unit_of_work_defaults_to_label_then_task_kind(self):
        self.assertEqual(R.Unit("u", _sit(label="scaffold-tests")).unit_of_work, "scaffold-tests")
        self.assertEqual(R.Unit("u", _sit(label=None, task_kind="explore")).unit_of_work, "explore")

    def test_explicit_unit_of_work_wins(self):
        self.assertEqual(R.Unit("u", _sit(label="x"), unit_of_work="named").unit_of_work, "named")


class RunLifecycleTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".praxis").mkdir()
        self.provider = pv.CorporaProvider(lambda r, u: {"domains": ["prose-craft"], "warnings": []})

    def tearDown(self):
        self.tmp.cleanup()

    def _events(self, unit_id):
        return [e["event"] for e in journal.read(self.root) if e.get("unit") == unit_id]

    def test_result_unit_walks_full_lifecycle_to_done(self):
        R.run_unit(self.root, R.Unit("u1", _sit(fit="clean")), self.provider,
                   R.InlineExecutor(_result))
        self.assertEqual(self._events("u1"),
                         ["unit.proposed", "unit.framed", "unit.dispatched", "unit.running",
                          "unit.receipt", "unit.done"])
        self.assertEqual(journal.state_of(self.root, "u1"), "done")

    def test_stall_receipt_ends_stalled(self):
        stall = lambda unit, composed: R.Receipt(outcome="stall", status="questions-pending",
                                                 surfaced=["which db?"])
        res = R.run_unit(self.root, R.Unit("u1", _sit(fit="clean")), self.provider,
                         R.InlineExecutor(stall))
        self.assertEqual(res["outcome"], "stall")
        self.assertEqual(journal.state_of(self.root, "u1"), "stalled")
        u = journal.fold(self.root)["units"]["u1"]
        self.assertEqual(u["surfaced"], ["which db?"])

    def test_framed_event_carries_composed_domains(self):
        R.run_unit(self.root, R.Unit("u1", _sit(fit="clean")), self.provider,
                   R.InlineExecutor(_result))
        framed = next(e for e in journal.read(self.root)
                      if e["event"] == "unit.framed" and e["unit"] == "u1")
        self.assertEqual(framed["domains"], ["prose-craft"])
        self.assertFalse(framed["gap_surfaced"])

    def test_inline_executor_normalizes_dict_receipt(self):
        res = R.run_unit(self.root, R.Unit("u1", _sit(fit="clean")), self.provider,
                         R.InlineExecutor(lambda u, c: {"outcome": "result", "tool_calls": 9}))
        self.assertEqual(res["receipt"]["tool_calls"], 9)

    def test_gap_surfaces_during_run(self):
        R.run_unit(self.root, R.Unit("u1", _sit(fit="none", suggested_kind="provision-infra")),
                   self.provider, R.InlineExecutor(_result))
        self.assertEqual(len(journal.gaps(self.root)), 1)
        framed = next(e for e in journal.read(self.root)
                      if e["event"] == "unit.framed" and e["unit"] == "u1")
        self.assertTrue(framed["gap_surfaced"])
        self.assertEqual(framed["routed_kind"], "unclassified")


class RunPlanTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".praxis").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_plan_runs_in_order_and_summarizes(self):
        def handler(unit, composed):
            return R.Receipt(outcome="stall", status="blocked") if unit.id == "u2" \
                else R.Receipt(outcome="result")

        plan = R.Plan([R.Unit(f"u{i}", _sit(fit="clean", label="implement-feature")) for i in (1, 2, 3)])
        out = R.run(plan, pv.NullProvider(), R.InlineExecutor(handler), self.root)
        self.assertEqual([r["outcome"] for r in out["results"]], ["result", "stall", "result"])
        bucket = out["summary"]["by_phase"]["implement-feature"]
        self.assertEqual((bucket["runs"], bucket["result"], bucket["stall"]), (3, 2, 1))
        self.assertEqual(len(out["summary"]["recent_stalls"]), 1)


class SubprocessExecutorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".praxis").mkdir()
        self.unit = R.Unit("u1", _sit(fit="clean"))

    def tearDown(self):
        self.tmp.cleanup()

    def _exec(self, code):
        return R.SubprocessExecutor(lambda unit, composed: [sys.executable, "-c", code])

    def test_json_receipt_on_stdout_is_parsed(self):
        code = "import json;print(json.dumps({'outcome':'stall','status':'blocked','surfaced':['x']}))"
        r = self._exec(code).run(self.unit, {})
        self.assertEqual((r.outcome, r.status, r.surfaced), ("stall", "blocked", ["x"]))

    def test_clean_exit_without_json_is_a_result(self):
        r = self._exec("print('done, no structured receipt')").run(self.unit, {})
        self.assertEqual(r.outcome, "result")

    def test_nonzero_exit_becomes_blocked_stall(self):
        r = self._exec("import sys;sys.exit(3)").run(self.unit, {})
        self.assertEqual((r.outcome, r.status), ("stall", "blocked"))
        self.assertTrue(r.surfaced)

    def test_launch_failure_is_a_stall(self):
        ex = R.SubprocessExecutor(lambda unit, composed: ["/no/such/binary/xyzzy"])
        r = ex.run(self.unit, {})
        self.assertEqual(r.outcome, "stall")


def _corpora_binding():
    repo = Path(__file__).resolve().parents[2]
    manifest_path = repo / "corpora" / "praxis-plugin" / "engine" / "plugins" / "corpora.json"
    if not manifest_path.is_file():
        return None
    sys.path.insert(0, str(repo / "praxis" / "scripts"))
    try:
        import engine  # noqa: E402
    except Exception:
        return None
    manifest = engine.load_manifest(manifest_path)

    def select(root, uow):
        payload, _ = engine.call_json(manifest, "compose",
                                      {"root": root, "unit_of_work": uow, "json": True})
        return {"domains": (payload or {}).get("domains", []),
                "warnings": (payload or {}).get("warnings", [])}

    return select, list(manifest.get("capabilities", {}).keys())


class LiveConductorRunTest(unittest.TestCase):
    """tests + live: the conductor core driving a real plan through the real corpora provider and an
    inline executor, then reading the whole run back off the journal fold."""

    def setUp(self):
        binding = _corpora_binding()
        if binding is None:
            self.skipTest("corpora engine manifest not loadable")
        self.select, _ = binding
        self.repo = Path(__file__).resolve().parents[2]
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".praxis").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_real_provider_linear_run(self):
        provider = pv.CorporaProvider(self.select)
        plan = R.Plan([
            R.Unit("a", _sit(task_kind="explore", fit="clean", label="scan-architecture",
                             root=str(self.repo))),
            R.Unit("b", _sit(task_kind="change", fit="none", suggested_kind="provision-infra",
                             label="implement-feature", root=str(self.repo))),
        ])
        out = R.run(plan, provider, R.InlineExecutor(_result), self.root)
        self.assertEqual([r["outcome"] for r in out["results"]], ["result", "result"])
        framed_a = next(e for e in journal.read(self.root)
                        if e["event"] == "unit.framed" and e["unit"] == "a")
        self.assertIn("prose-craft", framed_a["domains"])
        self.assertEqual(journal.state_of(self.root, "a"), "done")
        self.assertEqual(len(journal.gaps(self.root)), 1)
        self.assertEqual(journal.gap_candidates(self.root)[0]["suggested"], "provision-infra")


if __name__ == "__main__":
    unittest.main()
