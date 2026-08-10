"""End-to-end: the whole conductor vertical composed together.

Each phase's own suite tests its layer in isolation; this exercises the full stack as one system —
a DAG plan run under an editable policy, through the provider seam (with gap surfacing) and the
verification gate, then read back as views, then the accreted vocabulary promoted. It doubles as a
worked example of how the pieces fit.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import accretion as acc  # noqa: E402
import journal  # noqa: E402
import policy as pol  # noqa: E402
import providers as pv  # noqa: E402
import run as R  # noqa: E402
import schedule as S  # noqa: E402
import views  # noqa: E402
from situation import Situation  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
CORPUS_PY = REPO / "corpora" / "scripts" / "corpus.py"


class FullStackNullProviderTest(unittest.TestCase):
    """The whole machine, no engine needed — mechanics only, so it always runs."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".praxis").mkdir()
        # Editable policy: cap concurrency, allow one defect retry.
        pol.policy_path(self.root).write_text(json.dumps({"concurrency": 2, "max_retries": 1}))

    def tearDown(self):
        self.tmp.cleanup()

    def test_dag_verify_views_accretion_compose(self):
        # A plan: scan → impl (chain); plus a stack of "provision-infra" units the model can't
        # classify (fit=none), which will surface a recurring gap.
        units = [
            R.Unit("scan", Situation(task_kind="explore", intent="map the code", subject="coding",
                                     label="scan-architecture")),
            R.Unit("impl", Situation(task_kind="change", intent="add the feature", subject="coding",
                                     label="implement-feature"), depends_on=["scan"]),
        ]
        for i in range(3):
            units.append(R.Unit(f"infra{i}",
                                Situation(task_kind="change", intent="stand up infra",
                                          subject="process", suggested_kind="provision-infra",
                                          fit="none")))

        # impl needs one defect loop before it verifies; everything else passes first try.
        seen = {}

        def verify(unit, receipt, composed):
            if unit.id == "impl" and seen.get("impl", 0) < 1:
                seen["impl"] = seen.get("impl", 0) + 1
                return R.Verdict(verified=False, defects=["missing test"])
            return R.Verdict(verified=True, evidence={"ok": unit.id})

        def work(unit, composed):
            # Each attempt costs; the retry sees the defect feedback.
            return R.Receipt(outcome="result", tool_calls=1, cost={"tokens": 10, "usd": 0.001})

        out = S.run_dag(R.Plan(units), pv.NullProvider(), R.InlineExecutor(work), self.root,
                        verifier=R.CallableVerifier(verify))

        # 1) Everything delivered and verified; the chain ran in order.
        self.assertTrue(all(r["outcome"] == "result" for r in out["results"]))
        self.assertEqual(journal.state_of(self.root, "impl"), "done")
        scan_receipt = next(e["seq"] for e in journal.read(self.root)
                            if e.get("unit") == "scan" and e["event"] == "unit.done")
        impl_dispatch = next(e["seq"] for e in journal.read(self.root)
                             if e.get("unit") == "impl" and e["event"] == "unit.dispatched")
        self.assertLess(scan_receipt, impl_dispatch)   # impl dispatched only after scan concluded

        # 2) The verification gate looped impl once (2 receipts, 1 verified).
        impl_h = views.handoff(self.root, "impl")
        self.assertEqual(impl_h["attempts"], 2)
        self.assertTrue(impl_h["verified"])

        # 3) Views over the log: a row per unit, and cost summed across every attempt.
        ledger = views.ledger(self.root)
        self.assertEqual(len(ledger), 5)
        # 5 units, 6 receipts total (impl ran twice) ⇒ 60 tokens, 6 tool calls.
        self.assertEqual(out["cost"]["tokens"], 60)
        self.assertEqual(out["cost"]["tool_calls"], 6)

        # 4) The gap mechanism: 3 provision-infra gaps surfaced during the run ⇒ promotable.
        self.assertEqual(len(journal.gaps(self.root)), 3)
        prom = acc.promotable(self.root, min_count=3)
        self.assertEqual([c["suggested"] for c in prom], ["provision-infra"])

        # 5) The ratify gate: promote it, and it becomes known and drops out of promotable.
        acc.mint_candidate(self.root, prom[0], note="operator: real devops verb")
        self.assertTrue(acc.is_known(self.root, "task_kind", "provision-infra"))
        self.assertEqual(acc.promotable(self.root, min_count=3), [])

        # 6) The whole run is reproducible from the log alone.
        self.assertEqual(journal.fold(self.root)["open_units"], [])


@unittest.skipUnless(CORPUS_PY.is_file(), "corpora corpus.py not present")
class FullStackRealCorporaTest(unittest.TestCase):
    """The same vertical, but composing real corpora domains through the direct adapter."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)      # journal lives here
        (self.root / ".praxis").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_real_composition_through_the_stack(self):
        import adapters
        provider = adapters.corpora_provider(REPO, mode="features")
        shape = {"language": "python", "framework": "none"}
        plan = R.Plan([
            R.Unit("scan", Situation(task_kind="explore", intent="map it", subject="coding",
                                     project_shape=shape, root=str(REPO))),
            R.Unit("verify", Situation(task_kind="change", intent="check it", subject="coding",
                                       project_shape=shape, root=str(REPO)), depends_on=["scan"]),
        ])
        out = S.run_dag(plan, provider, R.InlineExecutor(lambda u, c: R.Receipt(outcome="result")),
                        self.root, verifier=R.CallableVerifier(lambda u, r, c: R.Verdict(verified=True)))
        self.assertEqual([r["outcome"] for r in out["results"]], ["result", "result"])

        # scan's handoff carries the real composed domains and the verification result.
        h = views.handoff(self.root, "scan")
        self.assertIn("prose-craft", h["domains_loaded"])       # universal
        self.assertIn("coding-general", h["domains_loaded"])    # subject match on this shape
        self.assertTrue(h["verified"])
        self.assertEqual(h["state"], "done")


if __name__ == "__main__":
    unittest.main()
