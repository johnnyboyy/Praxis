#!/usr/bin/env python3
"""audit-cut — the audit-and-cut method, forged from lived capture.

LIVED capture (2026-08-13, via skills/forge-workflow) from three consecutive
runs of the method in one arc: the praxis engine cut, the corpora cut, and the
uiux breakout. The moves below are what actually happened, and the edge types
are empirical — stated from what each transition did to the prior artifact,
observed, not designed:

  audit      — created evidence where none existed (advertised model from docs;
               structure + import map; the RUNTIME RECORD — journals, ledgers,
               deposited artifacts; contract-consumer trace; the project's own
               self-criticism). Every claim grounded in a count or grep.
  cut-plan   — CARRIED the evidence (it stayed in context and was perturbed
               into dispositions): ordered laps, per-lap acceptance, an
               explicitly-kept list, sequencing against in-flight work. Exit in
               practice was the operator's approval — the plan is registered,
               not self-certified.
  execute    — CARRIED the plan through the laps: each lap implemented (in the
               observed runs, by dispatched executors), independently verified,
               committed, closed. Reworks happened inside laps, not by
               abandoning the plan.
  final-verify — full suite + the plan's observable-behavior acceptance
               (journal shapes, report output, live smoke tests). This is the
               phase whose regression gate refuses a hollow close.
  record     — the plan marked EXECUTED with deviations noted; discovered
               follow-ups became new units rather than silent scope.

Verdict (per skills/forge-workflow): a true workflow — five phases, typed
artifact transitions, and a gate that can refuse advance (final-verify's
regression gate; in the lived runs, the suite). The evidence-gathering detail
rides in the phase intents; the judgment that guides dispositions composes
from the domains bucket, not from this pack.

Home: bundled — the practice applies to any praxis root (it was run against
three different repos in its first arc).
"""
from __future__ import annotations

from workflow import EdgeType, Phase, Workflow

PRAXIS_PLUGIN = True

AUDIT = Phase(
    "audit", stance="divergent",
    intent=("establish the advertised model from the docs; map structure and the "
            "import graph; read the RUNTIME RECORD (journals, ledgers, deposited "
            "artifacts) — it, not the structure map, separates used from "
            "designed-for; trace every contract slot to a real consumer; mine the "
            "project's own self-criticism. Every claim grounded in a count/grep."),
    produces="evidence")

CUT_PLAN = Phase(
    "cut-plan", stance="convergent",
    intent=("perturb the evidence into dispositions: ordered laps, per-lap "
            "acceptance criteria, an explicitly-kept list, sequencing against "
            "in-flight work. Ends at operator approval and plan registration — "
            "never self-certified."),
    produces="plan")

EXECUTE = Phase(
    "execute", stance="convergent",
    intent=("drive the plan's laps: implement (dispatch executors where the work "
            "allows), verify each lap independently, commit per lap, close each "
            "unit; discovered defects become new units, not silent scope."),
    produces="changed-tree")

FINAL_VERIFY = Phase(
    "final-verify", stance="neutral",
    intent=("run the full verification once: the whole suite plus the plan's "
            "observable-behavior acceptance (journal/report shapes unchanged, "
            "live smoke tests)."),
    produces="verdict")

RECORD = Phase(
    "record", stance="neutral",
    intent=("mark the plan EXECUTED with deviations noted; file follow-ups as "
            "units; close."),
    produces="closure")

AUDIT_AND_CUT = Workflow(
    name="audit-and-cut",
    phases=[AUDIT, CUT_PLAN, EXECUTE, FINAL_VERIFY, RECORD],
    edges=[
        ("audit", "cut-plan", "pass", EdgeType.carry),
        ("cut-plan", "execute", "pass", EdgeType.carry),
        ("execute", "final-verify", "pass", EdgeType.carry),
        ("final-verify", "record", "pass", EdgeType.carry),
        ("final-verify", "execute", "fail", EdgeType.carry),
    ],
)


class AuditCutContributor:

    source = "audit-cut"

    def contribute(self, situation):
        return []

    def phases(self):
        return [AUDIT, CUT_PLAN, EXECUTE, FINAL_VERIFY, RECORD]

    def workflows(self):
        return [AUDIT_AND_CUT]


def make(root):
    return AuditCutContributor()
