import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import registry  # noqa: E402
from workflow import EdgeType, Phase, Workflow  # noqa: E402

class _PhaseContributor:
    source = "plug"

    def __init__(self, phases=None, workflows=None):
        self._phases = phases or []
        self._workflows = workflows or []

    def contribute(self, situation):
        return []

    def phases(self):
        return list(self._phases)

    def workflows(self):
        return list(self._workflows)

def _design_wf():
    design = Phase("design", stance="divergent")
    return Workflow(
        name="design-flow",
        phases=[design],
        edges=[("design", "design", "always", EdgeType.carry)],
    )

class ResolvePhasesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_seed_only_returns_seeds(self):
        out = registry.resolve_phases(self.root, [])
        self.assertIn("plan", out)
        self.assertIn("verify", out)

    def test_contributor_phase_merges(self):
        stub = _PhaseContributor(phases=[Phase("design", stance="divergent")])
        out = registry.resolve_phases(self.root, [stub])
        self.assertIn("plan", out)
        self.assertIn("design", out)
        self.assertEqual(out["design"].stance, "divergent")

    def test_seed_vs_plugin_collision_keeps_seed(self):
        seed_plan = registry.SEED_PHASES["plan"]
        stub = _PhaseContributor(phases=[Phase("plan", stance="convergent")])
        out = registry.resolve_phases(self.root, [stub])
        self.assertIs(out["plan"], seed_plan)

    def test_plugin_vs_plugin_collision_keeps_first(self):
        first = _PhaseContributor(phases=[Phase("design", stance="divergent")])
        second = _PhaseContributor(phases=[Phase("design", stance="convergent")])
        out = registry.resolve_phases(self.root, [first, second])
        self.assertEqual(out["design"].stance, "divergent")

    def test_invalid_phase_is_skipped(self):
        stub = _PhaseContributor(phases=[Phase("bad", stance="sideways")])
        out = registry.resolve_phases(self.root, [stub])
        self.assertNotIn("bad", out)

    def test_raising_provider_is_skipped_without_dropping_others(self):
        class _Boom:
            source = "boom"
            def contribute(self, situation):
                return []
            def phases(self):
                raise RuntimeError("nope")
        ok = _PhaseContributor(phases=[Phase("design", stance="divergent")])
        out = registry.resolve_phases(self.root, [_Boom(), ok])
        self.assertIn("design", out)
        self.assertIn("plan", out)

class ResolveWorkflowsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_seed_only_returns_seeds(self):
        out = registry.resolve_workflows(self.root, [])
        self.assertIn("build-verify", out)
        self.assertIn("build-verify", out)

    def test_contributor_workflow_merges(self):
        stub = _PhaseContributor(
            phases=[Phase("design", stance="divergent")],
            workflows=[_design_wf()],
        )
        out = registry.resolve_workflows(self.root, [stub])
        self.assertIn("build-verify", out)
        self.assertIn("design-flow", out)

    def test_workflow_naming_unknown_phase_is_dropped(self):
        ghost = Workflow(
            name="ghost-flow",
            phases=[Phase("ghost", stance="neutral")],
            edges=[("ghost", "nowhere", "always", EdgeType.carry)],
        )
        stub = _PhaseContributor(
            phases=[Phase("ghost", stance="neutral")],
            workflows=[ghost],
        )
        out = registry.resolve_workflows(self.root, [stub])
        self.assertNotIn("ghost-flow", out)

    def test_seed_vs_plugin_collision_keeps_seed(self):
        seed = registry.SEED_WORKFLOWS["build-verify"]
        clash = Workflow(
            name="build-verify",
            phases=[Phase("design", stance="divergent")],
            edges=[],
        )
        stub = _PhaseContributor(
            phases=[Phase("design", stance="divergent")],
            workflows=[clash],
        )
        out = registry.resolve_workflows(self.root, [stub])
        self.assertIs(out["build-verify"], seed)

    def test_plugin_vs_plugin_collision_keeps_first(self):
        p = Phase("design", stance="divergent")
        first = _PhaseContributor(
            phases=[p],
            workflows=[Workflow(name="dup", phases=[p], edges=[])],
        )
        second = _PhaseContributor(
            workflows=[Workflow(
                name="dup",
                phases=[Phase("design", stance="convergent")],
                edges=[])],
        )
        out = registry.resolve_workflows(self.root, [first, second])
        self.assertEqual(out["dup"].phases[0].stance, "divergent")

    def test_raising_provider_is_skipped_without_dropping_others(self):
        class _Boom:
            source = "boom"
            def contribute(self, situation):
                return []
            def workflows(self):
                raise RuntimeError("nope")
        ok = _PhaseContributor(
            phases=[Phase("design", stance="divergent")],
            workflows=[_design_wf()],
        )
        out = registry.resolve_workflows(self.root, [_Boom(), ok])
        self.assertIn("design-flow", out)
        self.assertIn("build-verify", out)

class ValidatePredicateEdgeTest(unittest.TestCase):
    def _phases(self):
        return {"a": Phase("a"), "b": Phase("b")}

    def test_valid_predicate_edge_validates_clean(self):
        w = Workflow(name="pw", phases=[Phase("a"), Phase("b")], edges=[
            ("a", "b", "fact", EdgeType.carry, lambda ev: True),
        ])
        self.assertEqual(registry.validate_workflow(w, self._phases()), [])

    def test_missing_predicate_is_flagged(self):
        w = Workflow(name="pw", phases=[Phase("a"), Phase("b")], edges=[
            ("a", "b", "fact", EdgeType.carry),
        ])
        problems = registry.validate_workflow(w, self._phases())
        self.assertTrue(any("must carry a callable predicate" in p for p in problems))

    def test_non_callable_predicate_is_flagged(self):
        w = Workflow(name="pw", phases=[Phase("a"), Phase("b")], edges=[
            ("a", "b", "fact", EdgeType.carry, "not-callable"),
        ])
        problems = registry.validate_workflow(w, self._phases())
        self.assertTrue(any("must carry a callable predicate" in p for p in problems))

    def test_predicate_edge_to_unknown_phase_still_flagged(self):
        w = Workflow(name="pw", phases=[Phase("a")], edges=[
            ("a", "ghost", "fact", EdgeType.carry, lambda ev: True),
        ])
        problems = registry.validate_workflow(w, {"a": Phase("a")})
        self.assertTrue(any("unknown phase" in p for p in problems))

    def test_4tuple_edges_unaffected(self):
        w = Workflow(name="pw", phases=[Phase("a"), Phase("b")], edges=[
            ("a", "b", "pass", EdgeType.carry),
        ])
        self.assertEqual(registry.validate_workflow(w, self._phases()), [])

if __name__ == "__main__":
    unittest.main()
