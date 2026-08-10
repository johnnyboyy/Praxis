import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import journal  # noqa: E402
import providers as pv  # noqa: E402
import run as R  # noqa: E402
import schedule as S  # noqa: E402
from situation import Situation  # noqa: E402


def _sit(**over):
    kw = dict(task_kind="change", intent="do the thing", subject="coding")
    kw.update(over)
    return Situation(**kw)


def _u(uid, deps=None, **sit):
    return R.Unit(uid, _sit(label="implement-feature", **sit), depends_on=deps or [])


def _ok(unit, composed):
    return R.Receipt(outcome="result")


class ValidationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".praxis").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def _run(self, plan, **kw):
        return S.run_dag(plan, pv.NullProvider(), R.InlineExecutor(_ok), self.root, **kw)

    def test_unknown_dependency_raises(self):
        with self.assertRaises(ValueError):
            self._run(R.Plan([_u("a", deps=["ghost"])]))

    def test_cycle_raises(self):
        with self.assertRaises(ValueError):
            self._run(R.Plan([_u("a", deps=["b"]), _u("b", deps=["a"])]))

    def test_duplicate_ids_raise(self):
        with self.assertRaises(ValueError):
            self._run(R.Plan([_u("a"), _u("a")]))

    def test_concurrency_floor(self):
        with self.assertRaises(ValueError):
            self._run(R.Plan([_u("a")]), concurrency=0)


class DagOrderTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".praxis").mkdir()
        self.order = []
        self.lock = threading.Lock()

    def tearDown(self):
        self.tmp.cleanup()

    def _record(self, unit, composed):
        with self.lock:
            self.order.append(unit.id)
        return R.Receipt(outcome="result")

    def test_dependent_runs_after_dependency(self):
        # a → b → c (chain), plus an independent d.
        plan = R.Plan([_u("c", deps=["b"]), _u("b", deps=["a"]), _u("a"), _u("d")])
        out = S.run_dag(plan, pv.NullProvider(), R.InlineExecutor(self._record), self.root,
                        concurrency=4)
        self.assertLess(self.order.index("a"), self.order.index("b"))
        self.assertLess(self.order.index("b"), self.order.index("c"))
        # results come back in plan order regardless of run order
        self.assertEqual([r["unit"] for r in out["results"]], ["c", "b", "a", "d"])
        self.assertTrue(all(r["outcome"] == "result" for r in out["results"]))

    def test_depends_on_edges_recorded(self):
        S.run_dag(R.Plan([_u("b", deps=["a"]), _u("a")]), pv.NullProvider(),
                  R.InlineExecutor(_ok), self.root)
        edges = [(e["unit"], e["depends_on"]) for e in journal.read(self.root)
                 if e["event"] == "unit.depends_on"]
        self.assertEqual(edges, [("b", "a")])


class BlockedCascadeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".praxis").mkdir()
        self.executed = []
        self.lock = threading.Lock()

    def tearDown(self):
        self.tmp.cleanup()

    def _handler(self, unit, composed):
        with self.lock:
            self.executed.append(unit.id)
        # 'a' stalls; everything else would deliver.
        return R.Receipt(outcome="stall", status="blocked") if unit.id == "a" \
            else R.Receipt(outcome="result")

    def test_stalled_dependency_blocks_and_cascades(self):
        # a (stalls) → b → c ; plus independent d that still delivers.
        plan = R.Plan([_u("a"), _u("b", deps=["a"]), _u("c", deps=["b"]), _u("d")])
        out = {r["unit"]: r for r in
               S.run_dag(plan, pv.NullProvider(), R.InlineExecutor(self._handler),
                         self.root, concurrency=4)["results"]}
        self.assertEqual(out["a"]["outcome"], "stall")
        self.assertEqual(out["b"]["status"], "blocked")
        self.assertEqual(out["c"]["status"], "blocked")
        self.assertEqual(out["d"]["outcome"], "result")
        self.assertEqual(out["b"]["blocked_on"], ["a"])
        self.assertEqual(out["c"]["blocked_on"], ["b"])
        # b and c were never executed — only a and d ran.
        self.assertEqual(sorted(self.executed), ["a", "d"])
        self.assertEqual(journal.state_of(self.root, "b"), "stalled")


class ConcurrencyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".praxis").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_independent_units_run_in_parallel(self):
        # A barrier of N only releases if N workers arrive together — proof of real parallelism.
        barrier = threading.Barrier(3, timeout=5)

        def handler(unit, composed):
            barrier.wait()
            return R.Receipt(outcome="result")

        plan = R.Plan([_u("a"), _u("b"), _u("c")])
        out = S.run_dag(plan, pv.NullProvider(), R.InlineExecutor(handler), self.root,
                        concurrency=3)
        self.assertEqual([r["outcome"] for r in out["results"]], ["result", "result", "result"])

    def test_concurrency_cap_is_enforced(self):
        active = [0]
        peak = [0]
        lock = threading.Lock()

        def handler(unit, composed):
            with lock:
                active[0] += 1
                peak[0] = max(peak[0], active[0])
            time.sleep(0.03)
            with lock:
                active[0] -= 1
            return R.Receipt(outcome="result")

        plan = R.Plan([_u(f"u{i}") for i in range(6)])
        S.run_dag(plan, pv.NullProvider(), R.InlineExecutor(handler), self.root, concurrency=2)
        self.assertLessEqual(peak[0], 2, f"peak concurrency {peak[0]} exceeded cap 2")

    def test_thread_safe_journal_under_parallelism(self):
        plan = R.Plan([_u(f"u{i}") for i in range(20)])
        S.run_dag(plan, pv.NullProvider(), R.InlineExecutor(_ok), self.root, concurrency=8)
        seqs = [e["seq"] for e in journal.read(self.root)]
        # No lost or duplicated seq under concurrent appends.
        self.assertEqual(seqs, list(range(len(seqs))))
        fold = journal.fold(self.root)
        self.assertEqual(sum(1 for u in fold["units"].values() if u["state"] == "done"), 20)


class VerificationInDagTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".praxis").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_verification_failure_blocks_dependents(self):
        # b's work delivers but never verifies ⇒ b stalls ⇒ its dependent c is blocked.
        def verify(unit, receipt, composed):
            return R.Verdict(verified=unit.id != "b", defects=["nope"] if unit.id == "b" else [])

        plan = R.Plan([_u("a"), _u("b", deps=["a"]), _u("c", deps=["b"])])
        out = {r["unit"]: r for r in
               S.run_dag(plan, pv.NullProvider(), R.InlineExecutor(_ok), self.root,
                         verifier=R.CallableVerifier(verify), concurrency=2, max_retries=1)["results"]}
        self.assertTrue(out["a"]["verified"])
        self.assertEqual(out["b"]["outcome"], "stall")
        self.assertFalse(out["b"]["verified"])
        self.assertEqual(out["c"]["status"], "blocked")


class ReflexiveRoutingTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".praxis").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_records_conductor_route(self):
        S.run_dag(R.Plan([_u("a"), _u("b", deps=["a"])]), pv.NullProvider(),
                  R.InlineExecutor(_ok), self.root)
        routes = [e for e in journal.read(self.root) if e["event"] == "conductor.route"]
        self.assertEqual(len(routes), 1)
        self.assertEqual(routes[0]["units"], 2)

    def test_reflexive_gap_surfaces_on_own_move(self):
        # The conductor's own routing move is subject to the same gap hook: a poor-fit routing
        # situation surfaces a conductor-level gap, just as a unit's would.
        routing = Situation(task_kind="change", subject="process",
                            intent="fan out and reconverge a build matrix",
                            suggested_kind="orchestrate-matrix", fit="none")
        S.run_dag(R.Plan([_u("a")]), pv.NullProvider(), R.InlineExecutor(_ok), self.root,
                  routing_situation=routing)
        gaps = journal.gaps(self.root)
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0]["suggested"], "orchestrate-matrix")
        self.assertEqual(journal.gap_candidates(self.root)[0]["suggested"], "orchestrate-matrix")


if __name__ == "__main__":
    unittest.main()
