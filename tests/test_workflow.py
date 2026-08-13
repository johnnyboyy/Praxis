import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "plugins" / "rebuild"))
import journal  # noqa: E402
import rebuild_plugin  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "plugins" / "coding-process"))
import coding_process_plugin  # noqa: E402
import run as R  # noqa: E402
import workflow as W  # noqa: E402
from phase_walk import decide_step, gate_for, incoming  # noqa: E402
from situation import Situation  # noqa: E402
import phase_walk  # noqa: E402
import plan as plan_mod  # noqa: E402

def _sit(**over):
    kw = dict(task_kind="change", intent="do the thing", subject="coding")
    kw.update(over)
    return Situation(**kw)

def _receipt(passed=True, **evidence):
    evidence.setdefault("passed", passed)
    return R.Receipt(outcome="result", evidence=evidence)

def _decide(wf, name, receipt, edge_in=None, verifiers=None):
    return decide_step(wf, R.Unit("u1", _sit()), name, edge_in, receipt, {},
                       verifiers or {})

class SeedLibraryTest(unittest.TestCase):
    def test_seed_phases_present(self):
        for name in ("plan", "implement", "verify", "fix", "close"):
            self.assertIn(name, W.SEED_PHASES)
            self.assertIn(W.SEED_PHASES[name].stance, W.STANCES)

    def test_rebuild_phases_live_in_the_plugin_not_the_seed(self):
        self.assertNotIn("extract", W.SEED_PHASES)
        self.assertNotIn("synthesize", W.SEED_PHASES)
        self.assertNotIn("rebuild-triple", W.SEED_WORKFLOWS)

    def test_tdd_lives_in_the_plugin_not_the_seed(self):
        self.assertNotIn("write-tests", W.SEED_PHASES)
        self.assertNotIn("tdd-unit", W.SEED_WORKFLOWS)
        self.assertEqual(list(W.SEED_WORKFLOWS), ["build-verify"])

    def test_gate_mapping(self):
        self.assertEqual(W.GATES[W.EdgeType.create], "does-it")
        self.assertEqual(W.GATES[W.EdgeType.carry], "regression")
        self.assertEqual(W.GATES[W.EdgeType.extract], "coverage-diff")

    def test_tdd_workflow_shape(self):
        wf = coding_process_plugin.TDD_UNIT
        self.assertEqual([p.name for p in wf.phases],
                         ["write-tests", "implement", "refactor", "test-cleanup"])
        self.assertEqual([p.name for p in W.next_phases(wf, "write-tests", "pass")],
                         ["implement"])
        self.assertEqual(W.next_phases(wf, "test-cleanup", "pass"), [])
        for (_f, _t, _w, et) in wf.edges:
            self.assertEqual(et, W.EdgeType.carry)

    def test_rebuild_triple_extract_edge(self):
        wf = rebuild_plugin.REBUILD_TRIPLE

        self.assertEqual([p.name for p in wf.phases], ["extract", "synthesize"])
        et = next(et for (f, t, w, et) in wf.edges if f == "extract" and t == "synthesize")
        self.assertEqual(et, W.EdgeType.extract)
        self.assertEqual(W.next_phases(wf, "synthesize", "pass"), [])
        self.assertEqual(W.GATES[W.EdgeType.extract], "coverage-diff")

class GateSelectionTest(unittest.TestCase):
    def test_gate_follows_incoming_edge(self):
        self.assertEqual(gate_for(None), "does-it")
        self.assertEqual(gate_for(W.EdgeType.carry), "regression")
        self.assertEqual(gate_for(W.EdgeType.extract), "coverage-diff")

    def test_failed_preservation_gate_forces_non_advance(self):
        wf = W.Workflow("gated", [W.PLAN, W.IMPLEMENT, W.FIX], edges=[
            ("plan", "implement", "pass", W.EdgeType.carry),
            ("plan", "fix", "fail", W.EdgeType.carry),
        ])
        failing = R.CallableVerifier(
            lambda unit, receipt, composed: R.Verdict(verified=False, defects=["gate"]))
        d = _decide(wf, "plan", _receipt(), verifiers={"does-it": failing})
        self.assertFalse(d["advance"])
        self.assertEqual(d["next"], ("fix", W.EdgeType.carry))

    def test_verified_gate_takes_pass_route(self):
        wf = W.Workflow("gated", [W.PLAN, W.IMPLEMENT, W.FIX], edges=[
            ("plan", "implement", "pass", W.EdgeType.carry),
            ("plan", "fix", "fail", W.EdgeType.carry),
        ])
        passing = R.CallableVerifier(
            lambda unit, receipt, composed: R.Verdict(verified=True, defects=[]))
        d = _decide(wf, "plan", _receipt(), verifiers={"does-it": passing})
        self.assertTrue(d["advance"])
        self.assertEqual(d["next"], ("implement", W.EdgeType.carry))

    def test_no_verifier_defaults_verified(self):
        d = _decide(coding_process_plugin.TDD_UNIT, "write-tests", _receipt())
        self.assertTrue(d["verified"])
        self.assertEqual(d["gate"], "does-it")
        self.assertEqual(d["next"], ("implement", W.EdgeType.carry))

class EdgeRoutingTest(unittest.TestCase):
    def _pick_wf(self):
        return W.Workflow("pick", [W.PLAN, W.IMPLEMENT, W.FIX], edges=[
            ("plan", "implement", "agent-choice", W.EdgeType.carry),
            ("plan", "fix", "agent-choice", W.EdgeType.carry),
        ])

    def test_agent_choice_follows_receipt_next(self):
        d = _decide(self._pick_wf(), "plan", _receipt(next="fix"))
        self.assertEqual(d["next"], ("fix", W.EdgeType.carry))

    def test_failed_gate_overrides_agent_choice_next(self):
        wf = W.Workflow("gated-pick", [W.PLAN, W.IMPLEMENT, W.FIX], edges=[
            ("plan", "implement", "agent-choice", W.EdgeType.carry),
            ("plan", "fix", "fail", W.EdgeType.carry),
        ])
        failing = R.CallableVerifier(
            lambda unit, receipt, composed: R.Verdict(verified=False, defects=["gate"]))
        d = _decide(wf, "plan", _receipt(next="implement"),
                    verifiers={"does-it": failing})
        self.assertEqual(d["next"], ("fix", W.EdgeType.carry))

    def test_terminal_phase_has_no_next(self):
        d = _decide(coding_process_plugin.TDD_UNIT, "test-cleanup", _receipt(), edge_in=W.EdgeType.carry)
        self.assertIsNone(d["next"])

class PredicateEdgeTest(unittest.TestCase):
    def _facts_wf(self, edges):
        route = W.Phase("route", stance="neutral", delivery="deterministic")
        b = W.Phase("b", stance="convergent")
        c = W.Phase("c", stance="convergent")
        return W.Workflow("pred", [route, b, c], edges=edges)

    def test_predicate_edge_declaration_order_first_truthy_wins(self):
        wf = self._facts_wf(edges=[
            ("route", "c", "fact", W.EdgeType.carry, lambda ev: ev["facts"]["k"]["go_c"]),
            ("route", "b", "fact", W.EdgeType.carry, lambda ev: ev["facts"]["k"]["go_b"]),
        ])
        d = _decide(wf, "route", _receipt(facts={"k": {"go_b": True, "go_c": False}}))
        self.assertEqual(d["next"], ("b", W.EdgeType.carry))
        d = _decide(wf, "route", _receipt(facts={"k": {"go_b": True, "go_c": True}}))
        self.assertEqual(d["next"], ("c", W.EdgeType.carry))

    def test_false_predicate_falls_to_pass_default(self):
        wf = self._facts_wf(edges=[
            ("route", "c", "fact", W.EdgeType.carry, lambda ev: ev["facts"]["k"]["go_b"]),
            ("route", "b", "pass", W.EdgeType.carry),
        ])
        d = _decide(wf, "route", _receipt(facts={"k": {"go_b": False}}))
        self.assertEqual(d["next"], ("b", W.EdgeType.carry))

    def test_raising_predicate_is_skipped(self):
        def boom(ev):
            raise KeyError("nope")
        wf = self._facts_wf(edges=[
            ("route", "c", "fact", W.EdgeType.carry, boom),
            ("route", "b", "fact", W.EdgeType.carry, lambda ev: ev["facts"]["k"]["go_b"]),
        ])
        d = _decide(wf, "route", _receipt(facts={"k": {"go_b": True}}))
        self.assertEqual(d["next"], ("b", W.EdgeType.carry))

    def test_predicate_tier_beats_agent_choice(self):
        wf = self._facts_wf(edges=[
            ("route", "b", "fact", W.EdgeType.carry, lambda ev: ev["facts"]["k"]["go_b"]),
            ("route", "c", "agent-choice", W.EdgeType.carry),
        ])
        d = _decide(wf, "route", _receipt(next="c", facts={"k": {"go_b": True}}))
        self.assertEqual(d["next"], ("b", W.EdgeType.carry))

    def test_agent_choice_used_when_no_predicate_matches(self):
        wf = self._facts_wf(edges=[
            ("route", "b", "fact", W.EdgeType.carry, lambda ev: ev["facts"]["k"]["go_b"]),
            ("route", "c", "agent-choice", W.EdgeType.carry),
        ])
        d = _decide(wf, "route", _receipt(next="c", facts={"k": {"go_b": False}}))
        self.assertEqual(d["next"], ("c", W.EdgeType.carry))

    def test_fail_route_overrides_predicate(self):
        route = W.Phase("route", stance="neutral", delivery="deterministic")
        b = W.Phase("b", stance="convergent")
        f = W.Phase("fix", stance="convergent")
        wf = W.Workflow("pred", [route, b, f], edges=[
            ("route", "b", "fact", W.EdgeType.carry, lambda ev: ev["facts"]["k"]["go_b"]),
            ("route", "fix", "fail", W.EdgeType.carry),
        ])
        d = _decide(wf, "route", _receipt(passed=False, facts={"k": {"go_b": True}}))
        self.assertEqual(d["next"], ("fix", W.EdgeType.carry))

    def test_no_match_at_all_is_none(self):
        wf = self._facts_wf(edges=[
            ("route", "b", "fact", W.EdgeType.carry, lambda ev: False),
        ])
        d = _decide(wf, "route", _receipt(facts={"k": 1}))
        self.assertIsNone(d["next"])

class IncomingTest(unittest.TestCase):
    def test_two_input_phase_sees_both_incoming_edges(self):
        ext = W.Phase("extract", stance="convergent")
        syn = W.Phase("synthesize", stance="convergent")
        cd = W.Phase("coverage-diff", stance="neutral", delivery="deterministic")
        wf = W.Workflow("triple", [ext, syn, cd], edges=[
            ("extract", "synthesize", "pass", W.EdgeType.extract),
            ("synthesize", "coverage-diff", "pass", W.EdgeType.carry),
            ("extract", "coverage-diff", "feeds", W.EdgeType.carry),
        ])
        froms = sorted(f for (f, _et) in incoming(wf, "coverage-diff"))
        self.assertEqual(froms, ["extract", "synthesize"])

class WalkFactRoutingTest(unittest.TestCase):
    """Fact/carry routing driven through the resumable walk (register_plan +
    record_phase), the surviving execution path."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".praxis").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def _unit(self, workflow):
        specs = [plan_mod.TaskSpec(intent="walk", id="u1", workflow=None)]
        units = plan_mod.plan_tasks(self.root, specs)
        u = units[0]
        u.situation.workflow = workflow.name
        return u

    def _router_wf(self):
        route = W.Phase("route", stance="neutral", delivery="deterministic")
        a = W.Phase("a", stance="convergent")
        b = W.Phase("b", stance="convergent")
        return W.Workflow("router", [route, a, b], edges=[
            ("route", "a", "fact", W.EdgeType.carry, lambda ev: ev["facts"]["go"] == "a"),
            ("route", "b", "fact", W.EdgeType.carry, lambda ev: ev["facts"]["go"] == "b"),
        ])

    def test_recorded_facts_route_the_cursor(self):
        wf = self._router_wf()
        unit = self._unit(wf)
        out = phase_walk.record_phase(self.root, unit, "route",
                                      {"passed": True, "facts": {"go": "b"}},
                                      workflow=wf)
        self.assertEqual(out["next"], "b")
        nxt = phase_walk.next_phase(self.root, unit, workflow=wf)
        self.assertEqual(nxt["phase"], "b")

    def test_carry_edge_threads_prior_produces(self):
        wf = W.Workflow("two", [W.PLAN, W.IMPLEMENT], edges=[
            ("plan", "implement", "pass", W.EdgeType.carry),
        ])
        unit = self._unit(wf)
        phase_walk.record_phase(self.root, unit, "plan",
                                {"passed": True, "produces": "the-plan"}, workflow=wf)
        nxt = phase_walk.next_phase(self.root, unit, workflow=wf)
        self.assertEqual(nxt["phase"], "implement")
        self.assertEqual(nxt["carry"], "the-plan")
        self.assertEqual(nxt["gate"], "regression")

    def test_extract_edge_hands_spec_not_carry(self):
        wf = rebuild_plugin.REBUILD_TRIPLE
        unit = self._unit(wf)
        phase_walk.record_phase(self.root, unit, "extract",
                                {"passed": True, "produces": {"interface": []}},
                                verifiers={}, workflow=wf)
        nxt = phase_walk.next_phase(self.root, unit, workflow=wf)
        self.assertEqual(nxt["phase"], "synthesize")
        self.assertEqual(nxt["spec"], {"interface": []})
        self.assertNotIn("carry", nxt)
        self.assertIsNotNone(nxt["isolation"])

    def test_failed_gate_rehands_same_phase(self):
        wf = W.Workflow("two", [W.PLAN, W.IMPLEMENT], edges=[
            ("plan", "implement", "pass", W.EdgeType.carry),
        ])
        unit = self._unit(wf)
        failing = R.CallableVerifier(
            lambda u, r, c: R.Verdict(verified=False, defects=["nope"]))
        out = phase_walk.record_phase(self.root, unit, "plan", {"passed": True},
                                      verifiers={"does-it": failing}, workflow=wf)
        self.assertFalse(out["advance"])
        nxt = phase_walk.next_phase(self.root, unit, workflow=wf)
        self.assertEqual(nxt["phase"], "plan")

    def test_loose_fit_records_phase_gap(self):
        wf = W.Workflow("two", [W.PLAN, W.IMPLEMENT], edges=[
            ("plan", "implement", "pass", W.EdgeType.carry),
        ])
        unit = self._unit(wf)
        phase_walk.record_phase(self.root, unit, "plan",
                                {"passed": True, "phase_fit": "loose",
                                 "suggested": "design-api"}, workflow=wf)
        pg = journal.phase_gaps(self.root, unit="u1")
        self.assertTrue(pg)
        self.assertEqual(pg[0]["suggested"], "design-api")
        self.assertEqual(pg[0]["fit"], "loose")

if __name__ == "__main__":
    unittest.main()
