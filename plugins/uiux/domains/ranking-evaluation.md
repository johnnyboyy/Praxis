---
id: ranking-evaluation
subject: design
applies-when:
  - has-ui: yes
universal: false
task-kinds: [create, change]
labels: [ui]
---

conventions: []

principles:
  - id: triage-and-ranking-are-independent-signals
    rule: "In any tool that captures both a fast triage judgment (like/dislike, initial reaction) and a deliberate comparative ranking, keep them separate end-to-end: named differently, entered through different affordances, and never aggregated — triage judgments must not influence ranking scores."
    condition: When designing any tool that mixes quick triage with comparative evaluation.
    reason: Triage is reflexive, coarse, and low-stakes; ranking is deliberate, precise, and high-stakes. If they appear to feed one output, users either hesitate during intake or discount the ranking — and the resulting score is ambiguous.
  - id: category-scope-is-visible-on-ranked-items
    rule: When displaying a ranking or score on an item, always show the scope in which that ranking applies (e.g., 'ranked #1 in Dashboards', not just 'ranked #1').
    condition: When items belong to categories and rankings are per-category, not global.
    reason: A rank without scope is ambiguous. The user may misread a per-category rank as a global quality signal, which inflates or deflates their confidence in the output.
  - id: choice-prompt-anchors-on-usefulness-not-preference
    rule: When presenting a head-to-head comparison for the purpose of building a reference library, frame the question around usefulness ('Which is the stronger reference?') rather than personal preference ('Which do you prefer?').
    condition: When the tool's output is meant to inform future decisions, not simply record taste.
    reason: Preference language makes rankings feel arbitrary. Usefulness language reminds the user they are curating a working resource, which produces more consistent and actionable judgments.
  - id: callout-label-describes-property-not-judgment
    rule: When a callout annotates one item in a results list as commonly stocked or frequently used, the label must describe a factual property ('Common stock', 'Most common') rather than imply a tool endorsement ('Recommended', 'Best fit').
    condition: When a list of passing or qualifying options includes a highlighted item the tool wants to surface as notable.
    reason: Without context, a callout label is read as an endorsement. Users applying field judgment need to know whether the callout reflects a tool decision or a data fact. 'Recommended' transfers false authority; 'Common stock' describes reality.
  - id: out-of-order-callout-requires-sort-explanation
    rule: When a callout item is not first in a sorted list, the annotation must explain why — either inline or via tooltip/popover. The explanation should describe the sort basis, not justify skipping the items ranked above.
    condition: When a highlighted row appears below one or more non-highlighted rows in a sorted results list.
    reason: Out-of-order callouts imply something is wrong with the items ranked above them. Without explanation, the user may distrust the higher-ranked items even though they are legally valid.
