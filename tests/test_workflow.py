import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import journal  # noqa: E402
import run as R  # noqa: E402
import workflow as W  # noqa: E402
from situation import Situation  # noqa: E402
from workflow_run import run_workflow  # noqa: E402


def _sit(**over):
    kw = dict(task_kind="change", intent="do the thing", subject="coding")
    kw.update(over)
    return Situation(**kw)


class SeedLibraryTest(unittest.TestCase):
    def test_seed_phases_present(self):
        for name in ("plan", "write-tests", "implement", "refactor", "test-cleanup",
                     "verify", "fix", "close", "extract", "synthesize"):
            self.assertIn(name, W.SEED_PHASES)
            self.assertIn(W.SEED_PHASES[name].stance, W.STANCES)

    def test_gate_mapping(self):
        self.assertEqual(W.GATES[W.EdgeType.create], "does-it")
        self.assertEqual(W.GATES[W.EdgeType.carry], "regression")
        self.assertEqual(W.GATES[W.EdgeType.extract], "coverage-diff")

    def test_tdd_workflow_shape(self):
        wf = W.TDD_UNIT
        self.assertEqual([p.name for p in wf.phases],
                         ["write-tests", "implement", "refactor", "test-cleanup"])
        self.assertEqual([p.name for p in W.next_phases(wf, "write-tests", "pass")],
                         ["implement"])
        self.assertEqual(W.next_phases(wf, "test-cleanup", "pass"), [])
        for (_f, _t, _w, et) in wf.edges:
            self.assertEqual(et, W.EdgeType.carry)

    def test_rebuild_triple_extract_edge(self):
        wf = W.REBUILD_TRIPLE
        # rebuild triple: 2-phase, synthesize terminal. The preservation gate is the
        # synthesize-exit edge-verifier keyed `coverage-diff`, not a phase.
        self.assertEqual([p.name for p in wf.phases], ["extract", "synthesize"])
        et = next(et for (f, t, w, et) in wf.edges if f == "extract" and t == "synthesize")
        self.assertEqual(et, W.EdgeType.extract)
        self.assertEqual(W.next_phases(wf, "synthesize", "pass"), [])  # terminal
        self.assertEqual(W.GATES[W.EdgeType.extract], "coverage-diff")  # gate unchanged


class _Capture:
    def __init__(self):
        self.seen = []

    def run(self, unit, composed):
        self.seen.append(dict(composed))
        return R.Receipt(outcome="result", evidence={"produces": f"art-{len(self.seen)}"})


class WalkTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".praxis").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def _phase_events(self, event):
        return [e for e in journal.read(self.root) if e.get("event") == event]

    def test_walks_tdd_in_order_with_increasing_index(self):
        out = run_workflow(self.root, R.Unit("u1", _sit()), W.TDD_UNIT, [], _Capture())
        self.assertEqual(out["phases"],
                         ["write-tests", "implement", "refactor", "test-cleanup"])
        entered = self._phase_events("phase.entered")
        self.assertEqual([e["phase"] for e in entered],
                         ["write-tests", "implement", "refactor", "test-cleanup"])
        self.assertEqual([e["phase_index"] for e in entered], [0, 1, 2, 3])
        exited = self._phase_events("phase.exited")
        self.assertEqual([e["phase_index"] for e in exited], [0, 1, 2, 3])

    def test_carry_edge_threads_prior_output_and_first_phase_is_fresh(self):
        cap = _Capture()
        run_workflow(self.root, R.Unit("u1", _sit()), W.TDD_UNIT, [], cap)
        first, second = cap.seen[0], cap.seen[1]
        self.assertNotIn("carry", first)
        self.assertNotIn("spec", first)
        self.assertEqual(second["carry"], "art-1")
        self.assertNotIn("spec", second)

    def test_extract_edge_puts_ir_not_carry(self):
        cap = _Capture()
        run_workflow(self.root, R.Unit("u1", _sit()), W.REBUILD_TRIPLE, [], cap)
        # 2-phase now: extract -> synthesize (terminal). The extract edge threads
        # the spec into composed["spec"] at synthesize, never as "carry".
        self.assertEqual(len(cap.seen), 2)
        synth = cap.seen[1]
        self.assertEqual(synth["spec"], "art-1")
        self.assertNotIn("carry", synth)

    def test_task_kind_gap_surfaces_once_not_per_phase(self):
        run_workflow(self.root, R.Unit("u1", _sit(fit="none", suggested_kind="provision")),
                     W.TDD_UNIT, [], _Capture())
        self.assertEqual(len(journal.gaps(self.root)), 1)

    def test_edge_in_recorded_on_entry(self):
        run_workflow(self.root, R.Unit("u1", _sit()), W.REBUILD_TRIPLE, [], _Capture())
        entered = self._phase_events("phase.entered")
        self.assertEqual([e["edge_in"] for e in entered], ["create", "extract"])

    def test_loose_fit_records_phase_gap(self):
        def handler(unit, composed):
            return R.Receipt(outcome="result",
                             evidence={"phase_fit": "loose", "suggested": "design-api"})

        run_workflow(self.root, R.Unit("u1", _sit()), W.TDD_UNIT, [],
                     R.InlineExecutor(handler))
        pg = journal.phase_gaps(self.root, unit="u1")
        self.assertTrue(pg)
        self.assertEqual(pg[0]["suggested"], "design-api")
        self.assertEqual(pg[0]["fit"], "loose")

    def test_gate_selected_by_edge_name_and_failure_recorded(self):
        failing = R.CallableVerifier(
            lambda unit, receipt, composed: R.Verdict(verified=False, defects=["dropped a symbol"]))
        out = run_workflow(self.root, R.Unit("u1", _sit()), W.REBUILD_TRIPLE, [],
                           _Capture(), verifiers={"coverage-diff": failing})
        exited = {e["phase"]: e for e in self._phase_events("phase.exited")}
        self.assertEqual(exited["synthesize"]["gate"], "coverage-diff")
        self.assertFalse(exited["synthesize"]["verified"])
        self.assertEqual(exited["extract"]["gate"], "does-it")
        self.assertTrue(exited["extract"]["verified"])
        self.assertEqual(out["phase_fits"]["synthesize"], "clean")


def _verify_after(fail_times):
    state = {"n": 0}

    def handler(unit, composed):
        if composed.get("phase") == "verify":
            state["n"] += 1
            return R.Receipt(outcome="result", evidence={"passed": state["n"] > fail_times})
        return R.Receipt(outcome="result", evidence={"produces": composed.get("phase")})

    return handler


class ConditionalTraversalTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".praxis").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_fix_loop_runs_until_verify_passes(self):
        out = run_workflow(self.root, R.Unit("u1", _sit()), W.BUILD_VERIFY, [],
                           R.InlineExecutor(_verify_after(fail_times=2)))
        self.assertEqual(out["phases"],
                         ["implement", "verify", "fix", "verify", "fix", "verify", "close"])

    def test_fix_loop_bounded_by_max_phase_loops(self):
        out = run_workflow(self.root, R.Unit("u1", _sit()), W.BUILD_VERIFY, [],
                           R.InlineExecutor(_verify_after(fail_times=99)), max_phase_loops=3)
        self.assertEqual(out["phases"].count("verify"), 3)
        stalled = [e for e in journal.read(self.root) if e.get("event") == "phase.stalled"]
        self.assertTrue(stalled)

    def test_failed_preservation_gate_forces_fail_route(self):
        wf = W.Workflow("gated", [W.PLAN, W.IMPLEMENT, W.REFACTOR], edges=[
            ("plan", "implement", "pass", W.EdgeType.carry),
            ("plan", "refactor", "fail", W.EdgeType.carry),
        ])
        failing = R.CallableVerifier(
            lambda unit, receipt, composed: R.Verdict(verified=False, defects=["gate"]))
        out = run_workflow(self.root, R.Unit("u1", _sit()), wf, [], _Capture(),
                           verifiers={"does-it": failing})
        self.assertEqual(out["phases"], ["plan", "refactor"])

    def test_verified_gate_takes_pass_route(self):
        wf = W.Workflow("gated", [W.PLAN, W.IMPLEMENT, W.REFACTOR], edges=[
            ("plan", "implement", "pass", W.EdgeType.carry),
            ("plan", "refactor", "fail", W.EdgeType.carry),
        ])
        passing = R.CallableVerifier(
            lambda unit, receipt, composed: R.Verdict(verified=True, defects=[]))
        out = run_workflow(self.root, R.Unit("u1", _sit()), wf, [], _Capture(),
                           verifiers={"does-it": passing})
        self.assertEqual(out["phases"], ["plan", "implement"])

    def test_failed_gate_overrides_agent_choice_next(self):
        wf = W.Workflow("gated-pick", [W.PLAN, W.IMPLEMENT, W.REFACTOR], edges=[
            ("plan", "implement", "agent-choice", W.EdgeType.carry),
            ("plan", "refactor", "fail", W.EdgeType.carry),
        ])
        failing = R.CallableVerifier(
            lambda unit, receipt, composed: R.Verdict(verified=False, defects=["gate"]))

        def handler(unit, composed):
            if composed.get("phase") == "plan":
                return R.Receipt(outcome="result",
                                 evidence={"next": "implement", "produces": "p"})
            return R.Receipt(outcome="result", evidence={"produces": composed.get("phase")})

        out = run_workflow(self.root, R.Unit("u1", _sit()), wf, [],
                           R.InlineExecutor(handler), verifiers={"does-it": failing})
        self.assertEqual(out["phases"], ["plan", "refactor"])

    def test_agent_choice_follows_receipt_next(self):
        wf = W.Workflow("pick", [W.PLAN, W.IMPLEMENT, W.REFACTOR], edges=[
            ("plan", "implement", "agent-choice", W.EdgeType.carry),
            ("plan", "refactor", "agent-choice", W.EdgeType.carry),
        ])

        def handler(unit, composed):
            if composed.get("phase") == "plan":
                return R.Receipt(outcome="result", evidence={"next": "refactor", "produces": "p"})
            return R.Receipt(outcome="result", evidence={"produces": composed.get("phase")})

        out = run_workflow(self.root, R.Unit("u1", _sit()), wf, [], R.InlineExecutor(handler))
        self.assertEqual(out["phases"], ["plan", "refactor"])


class _StanceRecorder:
    """A stance-only contributor: branches solely on situation.phase (stance)."""

    source = "stance"

    def __init__(self):
        self.stances = []

    def contribute(self, situation):
        self.stances.append(situation.phase)
        return []


class _NamedRecorder:
    """Reads situation.phase_name and emits phase-specific Contributions."""

    source = "named"

    def __init__(self):
        self.names = []
        self.stances = []

    def contribute(self, situation):
        self.names.append(situation.phase_name)
        self.stances.append(situation.phase)
        return []


class StanceNameSplitTest(unittest.TestCase):
    """Change 2c: phase = stance always; phase_name = the phase name or None."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".praxis").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def _wf(self):
        design = W.Phase("design", stance="divergent")
        build = W.Phase("build", stance="convergent")
        review = W.Phase("review", stance="neutral")
        return W.Workflow("mp", [design, build, review], edges=[
            ("design", "build", "pass", W.EdgeType.carry),
            ("build", "review", "pass", W.EdgeType.carry),
        ])

    def test_stance_only_contributor_sees_correct_stance_per_phase(self):
        rec = _StanceRecorder()
        run_workflow(self.root, R.Unit("u1", _sit()), self._wf(), [rec], _Capture())
        # divergent phase -> "divergent"; convergent -> "convergent"; neutral -> "none"
        self.assertEqual(rec.stances, ["divergent", "convergent", "none"])

    def test_gather_stance_derivation_unbroken_by_named_phase(self):
        # composed["stance"] must be the stance (None for neutral), never the phase name.
        cap = _Capture()
        run_workflow(self.root, R.Unit("u1", _sit()), self._wf(), [], cap)
        self.assertEqual([c["stance"] for c in cap.seen],
                         ["divergent", "convergent", None])
        # composed["phase"] remains the NAME (executors read it).
        self.assertEqual([c["phase"] for c in cap.seen], ["design", "build", "review"])

    def test_contributor_reads_phase_name_across_multi_phase_workflow(self):
        from contributors import Contribution

        class _PhaseSpecific:
            source = "ps"

            def contribute(self, situation):
                if situation.phase_name == "design":
                    return [Contribution(source="ps", title="design-ctx", body="diverge")]
                return []

        cap = _Capture()
        run_workflow(self.root, R.Unit("u1", _sit()), self._wf(), [_PhaseSpecific()], cap)
        # phase-specific injection: sources present only on the design phase
        self.assertIn("ps", cap.seen[0]["sources"])
        self.assertNotIn("ps", cap.seen[1]["sources"])
        self.assertNotIn("ps", cap.seen[2]["sources"])

    def test_phase_name_and_stance_both_visible_to_contributor(self):
        rec = _NamedRecorder()
        run_workflow(self.root, R.Unit("u1", _sit()), self._wf(), [rec], _Capture())
        self.assertEqual(rec.names, ["design", "build", "review"])
        self.assertEqual(rec.stances, ["divergent", "convergent", "none"])


class RunUnitWorkflowTest(unittest.TestCase):
    """Change 2a/2b: run_unit resolves situation.workflow via the registry."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".praxis").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def _events(self, event):
        return [e for e in journal.read(self.root) if e.get("event") == event]

    def test_registered_plugin_workflow_runs_via_run_unit(self):
        import textwrap

        import config
        from contributors import contributors_for
        modroot = self.root / "mod"
        modroot.mkdir()
        (modroot / "wf_plugin.py").write_text(textwrap.dedent("""
            from contributors import Contribution
            from workflow import Phase, Workflow, EdgeType

            class _C:
                source = "wfp"
                def contribute(self, situation):
                    if situation.phase_name == "design":
                        return [Contribution(source="wfp", title="design-ctx", body="d")]
                    return []
                def phases(self):
                    return [Phase("design", stance="divergent"),
                            Phase("build", stance="convergent")]
                def workflows(self):
                    d = Phase("design", stance="divergent")
                    b = Phase("build", stance="convergent")
                    return [Workflow("df", [d, b],
                                     edges=[("design", "build", "pass", EdgeType.carry)])]
            def make(root):
                return _C()
        """))
        config.write(self.root, "contributors", {"wfp": "wf_plugin:make"})
        sys.path.insert(0, str(modroot))
        try:
            contribs = contributors_for(self.root)
            cap = _Capture()
            out = R.run_unit(self.root, R.Unit("u1", _sit(workflow="df")), contribs, cap)
        finally:
            sys.path.remove(str(modroot))
            sys.modules.pop("wf_plugin", None)

        # ran the plugin workflow (not single-dispatch)
        self.assertEqual(out["workflow"], "df")
        self.assertEqual(out["phases"], ["design", "build"])
        # executor saw the phase NAME; contributor saw phase_name + stance split
        self.assertEqual([c["phase"] for c in cap.seen], ["design", "build"])
        self.assertIn("wfp", cap.seen[0]["sources"])       # design-ctx injected
        self.assertNotIn("wfp", cap.seen[1]["sources"])    # phase-specific: not on build
        self.assertEqual(cap.seen[0]["stance"], "divergent")
        self.assertEqual(cap.seen[1]["stance"], "convergent")
        self.assertFalse(self._events("workflow.unresolved"))

    def test_unknown_workflow_name_falls_back_and_journals_unresolved(self):
        cap = _Capture()
        out = R.run_unit(self.root, R.Unit("u1", _sit(workflow="nope")), [], cap)
        # single-dispatch result shape (not a workflow walk)
        self.assertEqual(out["outcome"], "result")
        self.assertNotIn("phases", out)
        unresolved = self._events("workflow.unresolved")
        self.assertEqual(len(unresolved), 1)
        self.assertEqual(unresolved[0]["workflow"], "nope")
        self.assertTrue(self._events("unit.done"))

    def test_no_workflow_runs_single_dispatch_unchanged(self):
        cap = _Capture()
        out = R.run_unit(self.root, R.Unit("u1", _sit()), [], cap)
        self.assertEqual(out["outcome"], "result")
        self.assertNotIn("phases", out)
        self.assertFalse(self._events("workflow.unresolved"))
        self.assertEqual(len(cap.seen), 1)  # one dispatch, no phase walk


class DeterministicRunTest(unittest.TestCase):
    """Change 3: delivery='deterministic' + Phase.run callable + fact-routing."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".praxis").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def _events(self, event):
        return [e for e in journal.read(self.root) if e.get("event") == event]

    def _router_wf(self, target):
        route = W.Phase(
            "route", stance="neutral", delivery="deterministic",
            run=lambda r, u, c: {"passed": True, "next": target,
                                 "facts": {"eligible": target}})
        a = W.Phase("a", stance="convergent")
        b = W.Phase("b", stance="convergent")
        return W.Workflow("router", [route, a, b], edges=[
            ("route", "a", "agent-choice", W.EdgeType.carry),
            ("route", "b", "agent-choice", W.EdgeType.carry),
        ])

    def test_run_callable_replaces_executor_and_routes_to_b(self):
        cap = _Capture()
        out = run_workflow(self.root, R.Unit("u1", _sit()), self._router_wf("b"), [], cap)
        self.assertEqual(out["phases"], ["route", "b"])
        # executor.run was NOT called for the deterministic 'route' phase;
        # only 'b' (an inline phase) reached the executor.
        self.assertEqual([c["phase"] for c in cap.seen], ["b"])

    def test_fact_drives_conditional_routing_to_a(self):
        cap = _Capture()
        out = run_workflow(self.root, R.Unit("u1", _sit()), self._router_wf("a"), [], cap)
        self.assertEqual(out["phases"], ["route", "a"])
        self.assertEqual([c["phase"] for c in cap.seen], ["a"])

    def test_facts_are_journaled(self):
        run_workflow(self.root, R.Unit("u1", _sit()), self._router_wf("b"), [], _Capture())
        facts = self._events("phase.facts")
        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0]["phase"], "route")
        self.assertEqual(facts[0]["facts"], {"eligible": "b"})

    def test_seed_deterministic_phase_without_run_uses_executor(self):
        # BUILD_VERIFY's 'verify' is delivery='deterministic' but has no run
        # callable -> behavior unchanged: the executor handles it.
        cap_seen = []

        def handler(unit, composed):
            cap_seen.append(composed.get("phase"))
            if composed.get("phase") == "verify":
                return R.Receipt(outcome="result", evidence={"passed": True})
            return R.Receipt(outcome="result", evidence={"produces": composed.get("phase")})

        out = run_workflow(self.root, R.Unit("u1", _sit()), W.BUILD_VERIFY, [],
                           R.InlineExecutor(handler))
        self.assertIn("verify", cap_seen)          # executor DID handle verify
        self.assertEqual(out["phases"], ["implement", "verify", "close"])
        self.assertFalse(self._events("phase.facts"))

    def test_deterministic_loop_bounded_by_max_phase_loops(self):
        # A deterministic phase that always routes back to itself must be
        # bounded by max_phase_loops.
        loop = W.Phase(
            "loop", stance="neutral", delivery="deterministic",
            run=lambda r, u, c: {"passed": True, "next": "loop"})
        wf = W.Workflow("looping", [loop], edges=[
            ("loop", "loop", "agent-choice", W.EdgeType.carry),
        ])
        out = run_workflow(self.root, R.Unit("u1", _sit()), wf, [], _Capture(),
                           max_phase_loops=3)
        self.assertEqual(out["phases"].count("loop"), 3)
        self.assertTrue(self._events("phase.stalled"))

    def test_run_callable_raising_stalls_cleanly(self):
        def boom(r, u, c):
            raise RuntimeError("kaboom")

        phase = W.Phase("route", stance="neutral", delivery="deterministic", run=boom)
        b = W.Phase("b", stance="convergent")
        wf = W.Workflow("err", [phase, b], edges=[
            ("route", "b", "pass", W.EdgeType.carry),
        ])
        out = run_workflow(self.root, R.Unit("u1", _sit()), wf, [], _Capture())
        # stalled: did not advance to 'b'
        self.assertEqual(out["phases"], ["route"])
        self.assertTrue(self._events("phase.error"))


class PredicateEdgeTest(unittest.TestCase):
    """Change 1: fact-predicate edges. A facts-only phase whose workflow carries
    predicate edges routes on those predicates (declaration order, first match)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".praxis").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def _events(self, event):
        return [e for e in journal.read(self.root) if e.get("event") == event]

    def _facts_wf(self, facts, edges):
        route = W.Phase("route", stance="neutral", delivery="deterministic",
                        run=lambda r, u, c: {"passed": True, "facts": facts})
        b = W.Phase("b", stance="convergent")
        c = W.Phase("c", stance="convergent")
        return W.Workflow("pred", [route, b, c], edges=edges)

    def test_predicate_edge_first_match_wins(self):
        facts = {"k": {"go_b": True, "go_c": False}}
        wf = self._facts_wf(facts, edges=[
            ("route", "c", "fact", W.EdgeType.carry, lambda ev: ev["facts"]["k"]["go_c"]),
            ("route", "b", "fact", W.EdgeType.carry, lambda ev: ev["facts"]["k"]["go_b"]),
        ])
        out = run_workflow(self.root, R.Unit("u1", _sit()), wf, [], _Capture())
        # declaration order: c-edge tests false, b-edge wins
        self.assertEqual(out["phases"], ["route", "b"])

    def test_true_predicate_before_false_still_ordered(self):
        facts = {"k": {"go_c": True, "go_b": True}}
        wf = self._facts_wf(facts, edges=[
            ("route", "c", "fact", W.EdgeType.carry, lambda ev: ev["facts"]["k"]["go_c"]),
            ("route", "b", "fact", W.EdgeType.carry, lambda ev: ev["facts"]["k"]["go_b"]),
        ])
        out = run_workflow(self.root, R.Unit("u1", _sit()), wf, [], _Capture())
        self.assertEqual(out["phases"], ["route", "c"])

    def test_false_predicate_falls_to_pass_default(self):
        facts = {"k": {"go_b": False}}
        wf = self._facts_wf(facts, edges=[
            ("route", "c", "fact", W.EdgeType.carry, lambda ev: ev["facts"]["k"]["go_b"]),
            ("route", "b", "pass", W.EdgeType.carry),
        ])
        out = run_workflow(self.root, R.Unit("u1", _sit()), wf, [], _Capture())
        self.assertEqual(out["phases"], ["route", "b"])
        self.assertFalse(self._events("phase.route_unmatched"))

    def test_raising_predicate_is_skipped(self):
        def boom(ev):
            raise KeyError("nope")
        facts = {"k": {"go_b": True}}
        wf = self._facts_wf(facts, edges=[
            ("route", "c", "fact", W.EdgeType.carry, boom),
            ("route", "b", "fact", W.EdgeType.carry, lambda ev: ev["facts"]["k"]["go_b"]),
        ])
        out = run_workflow(self.root, R.Unit("u1", _sit()), wf, [], _Capture())
        # raising predicate = no-match; next edge (b) wins
        self.assertEqual(out["phases"], ["route", "b"])

    def test_predicate_tier_beats_agent_choice(self):
        # phase emits BOTH facts and next; predicate tier is consulted first.
        route = W.Phase(
            "route", stance="neutral", delivery="deterministic",
            run=lambda r, u, c: {"passed": True, "next": "c",
                                 "facts": {"k": {"go_b": True}}})
        b = W.Phase("b", stance="convergent")
        c = W.Phase("c", stance="convergent")
        wf = W.Workflow("pred", [route, b, c], edges=[
            ("route", "b", "fact", W.EdgeType.carry, lambda ev: ev["facts"]["k"]["go_b"]),
            ("route", "c", "agent-choice", W.EdgeType.carry),
        ])
        out = run_workflow(self.root, R.Unit("u1", _sit()), wf, [], _Capture())
        self.assertEqual(out["phases"], ["route", "b"])
        # emitted next="c" matched no agent-choice? c IS an agent-choice edge, so
        # no unmatched-route event is expected.
        self.assertFalse(self._events("phase.route_unmatched"))

    def test_agent_choice_used_when_no_predicate_matches(self):
        route = W.Phase(
            "route", stance="neutral", delivery="deterministic",
            run=lambda r, u, c: {"passed": True, "next": "c",
                                 "facts": {"k": {"go_b": False}}})
        b = W.Phase("b", stance="convergent")
        c = W.Phase("c", stance="convergent")
        wf = W.Workflow("pred", [route, b, c], edges=[
            ("route", "b", "fact", W.EdgeType.carry, lambda ev: ev["facts"]["k"]["go_b"]),
            ("route", "c", "agent-choice", W.EdgeType.carry),
        ])
        out = run_workflow(self.root, R.Unit("u1", _sit()), wf, [], _Capture())
        self.assertEqual(out["phases"], ["route", "c"])

    def test_fail_route_overrides_predicate(self):
        # failure short-circuits: forward predicate branches are not consulted.
        route = W.Phase(
            "route", stance="neutral", delivery="deterministic",
            run=lambda r, u, c: {"passed": False, "facts": {"k": {"go_b": True}}})
        b = W.Phase("b", stance="convergent")
        f = W.Phase("fix", stance="convergent")
        wf = W.Workflow("pred", [route, b, f], edges=[
            ("route", "b", "fact", W.EdgeType.carry, lambda ev: ev["facts"]["k"]["go_b"]),
            ("route", "fix", "fail", W.EdgeType.carry),
        ])
        out = run_workflow(self.root, R.Unit("u1", _sit()), wf, [], _Capture())
        self.assertEqual(out["phases"], ["route", "fix"])

    def test_backward_compat_all_4tuple_workflow_unchanged(self):
        out = run_workflow(self.root, R.Unit("u1", _sit()), W.TDD_UNIT, [], _Capture())
        self.assertEqual(out["phases"],
                         ["write-tests", "implement", "refactor", "test-cleanup"])
        self.assertFalse(self._events("phase.route_unmatched"))


class UnmatchedRouteGuardTest(unittest.TestCase):
    """Guard the silent unmatched-route path: a phase emits `next` that no
    outgoing agent-choice edge targets."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".praxis").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def _events(self, event):
        return [e for e in journal.read(self.root) if e.get("event") == event]

    def _wf_emitting(self, target):
        # route emits `next=target`; the only outgoing edge is a plain pass edge
        # to `a` (no agent-choice edge, so any emitted `next` is unmatched).
        route = W.Phase(
            "route", stance="neutral", delivery="deterministic",
            run=lambda r, u, c: {"passed": True, "next": target})
        a = W.Phase("a", stance="convergent")
        return W.Workflow("emit", [route, a], edges=[
            ("route", "a", "pass", W.EdgeType.carry),
        ])

    def test_unknown_phase_name_journals_kind_unknown_and_falls_through(self):
        out = run_workflow(self.root, R.Unit("u1", _sit()),
                           self._wf_emitting("nonexistent"), [], _Capture())
        # behavior unchanged: falls through the pass edge to `a`
        self.assertEqual(out["phases"], ["route", "a"])
        ev = self._events("phase.route_unmatched")
        self.assertEqual(len(ev), 1)
        self.assertEqual(ev[0]["phase"], "route")
        self.assertEqual(ev[0]["next"], "nonexistent")
        self.assertEqual(ev[0]["kind"], "unknown")
        self.assertEqual(ev[0]["resolved"], "a")
        self.assertEqual(ev[0]["phase_index"], 0)
        self.assertFalse(self._events("phase.stalled"))

    def test_registered_but_unwired_phase_journals_kind_unwired(self):
        # "close" is a registered seed phase but has no edge from `route` here.
        out = run_workflow(self.root, R.Unit("u1", _sit()),
                           self._wf_emitting("close"), [], _Capture())
        self.assertEqual(out["phases"], ["route", "a"])
        ev = self._events("phase.route_unmatched")
        self.assertEqual(len(ev), 1)
        self.assertEqual(ev[0]["next"], "close")
        self.assertEqual(ev[0]["kind"], "unwired")
        self.assertEqual(ev[0]["resolved"], "a")

    def test_flag_on_stalls_instead_of_falling_through(self):
        import config
        config.write(self.root, None, {"stall-on-unmatched-route": "true"})
        out = run_workflow(self.root, R.Unit("u1", _sit()),
                           self._wf_emitting("nonexistent"), [], _Capture())
        # halted at `route`, never advanced to `a`
        self.assertEqual(out["phases"], ["route"])
        ev = self._events("phase.route_unmatched")
        self.assertEqual(len(ev), 1)
        self.assertEqual(ev[0]["resolved"], "stall")
        stalled = self._events("phase.stalled")
        self.assertEqual(len(stalled), 1)
        self.assertEqual(stalled[0]["phase"], "route")

    def test_flag_non_true_value_preserves_fall_through(self):
        import config
        config.write(self.root, None, {"stall-on-unmatched-route": "yes"})
        out = run_workflow(self.root, R.Unit("u1", _sit()),
                           self._wf_emitting("nonexistent"), [], _Capture())
        self.assertEqual(out["phases"], ["route", "a"])
        self.assertFalse(self._events("phase.stalled"))
        self.assertEqual(len(self._events("phase.route_unmatched")), 1)

    def test_matched_agent_choice_route_emits_no_event(self):
        route = W.Phase(
            "route", stance="neutral", delivery="deterministic",
            run=lambda r, u, c: {"passed": True, "next": "b"})
        a = W.Phase("a", stance="convergent")
        b = W.Phase("b", stance="convergent")
        wf = W.Workflow("router", [route, a, b], edges=[
            ("route", "a", "agent-choice", W.EdgeType.carry),
            ("route", "b", "agent-choice", W.EdgeType.carry),
        ])
        out = run_workflow(self.root, R.Unit("u1", _sit()), wf, [], _Capture())
        self.assertEqual(out["phases"], ["route", "b"])
        self.assertFalse(self._events("phase.route_unmatched"))

    def test_no_next_emitted_emits_no_event(self):
        out = run_workflow(self.root, R.Unit("u1", _sit()), W.TDD_UNIT, [], _Capture())
        self.assertEqual(out["phases"],
                         ["write-tests", "implement", "refactor", "test-cleanup"])
        self.assertFalse(self._events("phase.route_unmatched"))

    def _wf_facts_no_match(self):
        route = W.Phase("route", stance="neutral", delivery="deterministic",
                        run=lambda r, u, c: {"passed": True, "facts": {"k": 1}})
        a = W.Phase("a", stance="convergent")
        return W.Workflow("nomatch", [route, a], edges=[
            ("route", "a", "fact", W.EdgeType.carry, lambda ev: False),
        ])

    def test_facts_no_match_journals_kind_no_match_and_ends(self):
        out = run_workflow(self.root, R.Unit("u1", _sit()),
                           self._wf_facts_no_match(), [], _Capture())
        self.assertEqual(out["phases"], ["route"])          # nowhere to go
        ev = self._events("phase.route_unmatched")
        self.assertEqual(len(ev), 1)
        self.assertEqual(ev[0]["kind"], "no-match")
        self.assertIsNone(ev[0]["next"])
        self.assertIsNone(ev[0]["resolved"])
        self.assertFalse(self._events("phase.stalled"))     # flag off -> no stall

    def test_facts_no_match_stalls_when_flag_on(self):
        import config
        config.write(self.root, None, {"stall-on-unmatched-route": "true"})
        out = run_workflow(self.root, R.Unit("u1", _sit()),
                           self._wf_facts_no_match(), [], _Capture())
        self.assertEqual(out["phases"], ["route"])
        ev = self._events("phase.route_unmatched")
        self.assertEqual(len(ev), 1)
        self.assertEqual(ev[0]["kind"], "no-match")
        self.assertEqual(ev[0]["resolved"], "stall")
        stalled = self._events("phase.stalled")
        self.assertEqual(len(stalled), 1)
        self.assertEqual(stalled[0]["phase"], "route")

    def test_facts_matching_predicate_emits_no_event(self):
        route = W.Phase("route", stance="neutral", delivery="deterministic",
                        run=lambda r, u, c: {"passed": True, "facts": {"k": 1}})
        a = W.Phase("a", stance="convergent")
        wf = W.Workflow("match", [route, a], edges=[
            ("route", "a", "fact", W.EdgeType.carry, lambda ev: True),
        ])
        out = run_workflow(self.root, R.Unit("u1", _sit()), wf, [], _Capture())
        self.assertEqual(out["phases"], ["route", "a"])
        self.assertFalse(self._events("phase.route_unmatched"))

    def test_facts_with_pass_default_emits_no_event(self):
        # facts emitted, predicate misses, but a pass default catches it.
        route = W.Phase("route", stance="neutral", delivery="deterministic",
                        run=lambda r, u, c: {"passed": True, "facts": {"k": 1}})
        a = W.Phase("a", stance="convergent")
        b = W.Phase("b", stance="convergent")
        wf = W.Workflow("dflt", [route, a, b], edges=[
            ("route", "a", "fact", W.EdgeType.carry, lambda ev: False),
            ("route", "b", "pass", W.EdgeType.carry),
        ])
        out = run_workflow(self.root, R.Unit("u1", _sit()), wf, [], _Capture())
        self.assertEqual(out["phases"], ["route", "b"])
        self.assertFalse(self._events("phase.route_unmatched"))


class _UnitCloseRecorder:
    """Contributor whose only hook is unit-close; records the fired receipts."""

    source = "uc"

    def __init__(self):
        self.seen = []

    def contribute(self, situation):
        return []

    def hooks(self):
        return {"unit-close": lambda ctx: self.seen.append(
            (getattr(ctx.unit, "id", None), ctx.receipt, ctx.verdict))}


class WorkflowUnitCloseTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".praxis").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def _drift_wf(self):
        # early phase carries drift evidence; terminal 'close' phase carries none
        early = W.Phase("early", stance="convergent")
        close = W.Phase("close", stance="neutral")
        return W.Workflow("drift", [early, close], edges=[
            ("early", "close", "pass", W.EdgeType.carry),
        ])

    def test_fires_once_with_aggregate_receipt_from_midwalk_evidence(self):
        def handler(unit, composed):
            if composed.get("phase") == "early":
                return R.Receipt(outcome="result",
                                 evidence={"ui-drift": {"screens": ["s"]}})
            return R.Receipt(outcome="result", evidence={})  # terminal close: no drift

        rec = _UnitCloseRecorder()
        out = run_workflow(self.root, R.Unit("u1", _sit()), self._drift_wf(),
                           [rec], R.InlineExecutor(handler))
        # fired exactly once for the workflow unit
        self.assertEqual(len(rec.seen), 1)
        uid, receipt, verdict = rec.seen[0]
        self.assertEqual(uid, "u1")
        self.assertIsNone(verdict)
        # mid-walk signal survives the aggregate even though the terminal phase had none
        self.assertEqual(receipt["evidence"]["ui-drift"]["screens"], ["s"])
        # canonical 6-key Receipt.to_dict shape
        self.assertEqual(set(receipt),
                         {"outcome", "status", "surfaced", "evidence", "cost", "tool_calls"})
        # return exposes both "final" (superset) and the "receipt" alias
        self.assertEqual(out["final"], receipt)
        self.assertEqual(out["receipt"], receipt)

    def test_last_writer_wins_across_walk(self):
        def handler(unit, composed):
            if composed.get("phase") == "early":
                return R.Receipt(outcome="result", evidence={"k": "early", "only": 1})
            return R.Receipt(outcome="result", evidence={"k": "late"})

        rec = _UnitCloseRecorder()
        run_workflow(self.root, R.Unit("u1", _sit()), self._drift_wf(),
                     [rec], R.InlineExecutor(handler))
        ev = rec.seen[0][1]["evidence"]
        self.assertEqual(ev["k"], "late")   # terminal phase overwrote
        self.assertEqual(ev["only"], 1)     # untouched key persists


if __name__ == "__main__":
    unittest.main()
