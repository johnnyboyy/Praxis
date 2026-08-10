---
subject: process
posture: guardrail
units-of-work: [retrospect]
universal: false
---

# Domain: retrospective

Judgment about reading a domain's accumulated corpus and gate history for what it's telling you —
which signal is real, which is noise, and what to propose from it. Distinct from `principle-judgment`
(whether one proposed or ratified principle is genuine, and lives in the right domain) and from
`ratify-gate`/`orchestrator-routing` (assembling and routing a single spawn): this domain's
principles apply at the retrospective's periodic, backward-looking pass across a domain's history,
not at any single spawn's forward-looking gate. Loaded explicitly by `praxis-plugin/phases/retrospective.md`'s own
procedure as part of the audit-mode bundle (the domains under review, plus `domains/audit.md`) —
not selected via `scripts/corpus.py select` the way a composed spawn's working domains are, the
same way `orchestrator-routing`/`ratify-gate`/`principle-judgment` are loaded unconditionally rather
than composed. Two signals that read as retrospective triggers — a misplaced principle, and a
ratified principle whose gate-time discipline may have lapsed — are already homed in
`principle-judgment` (`check-principle-against-consuming-lens-not-just-domain-topic` and
`reaudit-ratified-principles-against-genuine-fork-test`); they are not duplicated here. Audit
metadata lives in `domains/audit.md`, loaded only at ratify/retrospective time.

```yaml
last-retrospective: 2026-08-07

principles:

- id: contamination-detected-fix-routing-or-composition
  rule: "When retrospective review finds attention was spent on a domain outside a task's actual mode during a session, treat it as a routing or composition defect and propose a fix to the routing judgment or the composition rule itself — not a one-off correction to that session's output."
  condition: "During a retrospective, when a composed spawn's actual working attention (visible in its output or a handoff's Surfaced notes) touched a domain its composition did not include, or a domain outside its declared stance."
  reason: "A single contaminated session is a symptom; the routing or composition rule that let it happen is the disease. Fixing only the output leaves the same misrouting free to recur on the next similar task."

- id: domain-tension-partition-signals-split
  rule: "Propose splitting a domain when two ratified principles within it have conditions that partition the same decision space and give opposing advice under their respective conditions — never when they simply address different topics. Advisory only; the operator judges whether the partition is real, and execution of an approved split is a live conversation with the operator about naming and boundaries, not a scripted step (`domains/audit.md`, \"The coding-ts / coding-react split,\" is the precedent to weigh a new one against)."
  condition: "During a retrospective, reviewing a domain's active principles for conditions that repeatedly produce contradictory guidance rather than merely covering different subjects."
  reason: "The seam between two domains is only real once tension is observed, not assumed from how a team would organize the same subject. Two principles on different topics are just different subjects; the partition test is repeated, condition-triggered opposing advice, which is the only evidence a single container has actually become two decision classes."

- id: convergence-signals-explorer-pairing
  rule: "When a domain's principles have stopped changing and corrections have become rare, propose pairing every composition that loads it with an explorer, to prevent the domain calcifying around its current state."
  condition: "During a retrospective, for a domain whose ratify counts and corrections have been low across several recent gates."
  reason: "A domain that never gets corrected is either genuinely settled or has stopped being questioned — the two look identical from counters alone. An explorer reintroduces active challenge before settledness curdles into an unexamined default."

- id: composition-drift-fix-going-forward
  rule: "When a spawn's composed domain-subset consistently excludes a domain the work actually needed, or includes one it never draws from, propose correcting the composition rule itself, not just the affected task."
  condition: "During a retrospective, reading the co-occurrence tally `record-gate` maintains and any handoff `Surfaced` notes naming a gap between what was composed and what the work actually needed."
  reason: "A single spawn missing a relevant domain is a routing accident; a *pattern* of the same domain being consistently excluded or consistently idle for a given unit-of-work is evidence the composition rule itself is wrong, and only a retrospective's aggregated view across sessions can tell the two apart from a one-off."

- id: complementary-principles-signal-abstraction-candidate
  rule: "When two or more active principles — in the same domain or different ones, from this project or one already imported — are individually narrow but jointly imply a general test neither states alone, propose that shared abstraction as a new candidate: state what the two principles jointly require, then run it through the ordinary ratify gate like any other proposal. This is the only test for surfacing a principle as worth reusing elsewhere — there is no separate promotion pathway or privileged destination domains-dir; reuse elsewhere happens through the same import mechanism as any other candidate (`kernel.md`, \"Project corpora\"). Before proposing, check two things: whether one of the source principles' own condition already states the general case (making the abstraction redundant with what's already there), and whether the abstraction is genuinely non-obvious to a fresh spawn with no history in this domain rather than standard engineering practice restated in domain-specific language. Either check failing means reject the candidate, not just soften it."
  condition: "During a retrospective, or when reading a domain's principles side by side reveals two or more that are jointly load-bearing for a test none of them states individually — distinct from `structural-kinship-condensation-candidate`'s same-test-restated-differently case, and distinct from judging a single principle's condition wording alone."
  reason: "A single principle's condition reading as stack- or project-agnostic is weak evidence it actually generalizes — it may simply not have hit its edge case yet. Two or more principles that are jointly necessary for a shared underlying test are stronger evidence: the abstraction is directly visible in what they jointly require, not inferred from the absence of project-specific wording in one entry. But 'jointly imply a general test' is easy to assert and hard to verify without checking against what already exists: if one of the source principles already generalizes past its own originating instance, the new candidate may just be restating that principle's own scope in different words, and if the residual insight is only 'a fix isn't global just because you fixed it once,' that's closer to standard practice than an earned, domain-specific abstraction."
  see-also: structural-kinship-condensation-candidate, co-firing-cluster-signals-meta-principle

- id: structural-kinship-condensation-candidate
  rule: "When several active principles state the same underlying test in different words — visible from existing see-also links or from reading a domain's principles side by side rather than sequentially — propose condensing them into one umbrella statement with the specific cases named as instances, rather than leaving the shared test implicit across separate entries. Before proposing, draft the umbrella's rule/condition/reason without naming any of the specific instances it would cover. If the draft cannot stand as an operationally meaningful rule without re-enumerating the specific cases, the shared text is a coincidence worth cross-linking (see-also) between the existing entries, not a mergeable principle."
  condition: "During a retrospective, or when a domain's principle list has grown large enough that side-by-side reading becomes practical."
  reason: "Kinship is visible from the text alone and doesn't need firing history to accumulate first — it can surface a condensation candidate earlier than co-firing would. Leaving the shared test implicit across several worded-differently entries pays a reader tax every session that has to re-derive that they're the same test. But an umbrella that only reads as meaningful once a reader already knows the specific shapes it abstracts over isn't actually condensing anything — it's restating the same coincidence in vaguer language, so the draft-without-instances test is what tells a real merge apart from a description of one."
  see-also: co-firing-cluster-signals-meta-principle

- id: interpret-efficacy-counts-dont-act-on-them-raw
  rule: "Read idle-dominant efficacy counts across many gates as a retirement candidate or a too-narrowly-scoped condition; read recurring violated counts as either a load-bearing principle (still catching real drift) or a badly-conditioned one — the counts alone cannot distinguish either pair, so treat them as a question the retrospective must answer, never as evidence to act on directly."
  condition: "During a retrospective, reading a domain's efficacy block (fired/violated/idle counts) for any principle."
  reason: "Counts are inputs to judgment, not verdicts — that's why they're recorded at the audit layer instead of consumed automatically. A principle that is idle because nobody needs it and one that is idle because its condition never fires look identical in the counter; a violated principle that's badly conditioned and one that's correctly catching real drift look identical too. Only the retrospective's read of the actual instances can resolve either ambiguity."

- id: executor-model-change-triggers-redundancy-recheck
  rule: "Treat a change in the model that executes composed spawns — an upgrade, a swap, a new default — as a retrospective trigger: re-check the guardrail principles those spawns load against the new executor's baseline. A principle that was load-bearing for the old executor may now restate the new one's default behavior; retire or kill what the new baseline demonstrably covers, keep what observed output shows still binding."
  condition: "When the executing model for a project's spawns changes, at the next retrospective over any domain composed into those spawns."
  reason: "A guardrail's value is the gap between its rule and the executor's default, and a model upgrade silently moves the second term. Nothing in the audit layer detects that the gap closed — a principle followed because it's in context and one followed because the model now does it anyway produce identical fired/idle counts — so the model change itself has to be the trigger, not any counter. The re-check runs the same executor-relative test the gate applies to new candidates (principle-judgment's redundant-for-the-executing-model-is-baseline), pointed backward at the ratified set."
  see-also: interpret-efficacy-counts-dont-act-on-them-raw

- id: co-firing-cluster-signals-meta-principle
  rule: "When a cluster of principles consistently fire together across gates, propose a shared meta-principle, treating the co-firing as the empirical trace of one underlying justification the individual principles only state as separate instances."
  condition: "During a retrospective, reading the co-occurrence/efficacy data for principles that repeatedly fire in the same gates."
  reason: "Co-firing is the empirical, counted trace of the same shared-test pattern `structural-kinship-condensation-candidate` finds from reading the text alone — the two are complementary detection paths for the same underlying condensation opportunity, one needing accumulated firing history first and one visible immediately from the prose."
  see-also: structural-kinship-condensation-candidate

killed:
```
