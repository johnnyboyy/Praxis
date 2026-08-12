---
id: forms-inputs
subject: design
applies-when:
  - has-ui: yes
universal: false
task-kinds: [create, change]
labels: [ui]
---

conventions: []

principles:
  - id: numeric-inputs-start-empty-not-zero
    rule: Numeric fields that require deliberate user input should start empty (null/blank), not pre-filled with 0.
    condition: When a numeric input controls a core calculation variable and 0 is indistinguishable from 'the user entered zero intentionally' vs. 'the user hasn't filled this in yet.'
    reason: A 0 in a rendered input looks like a completed field. Starting empty puts the field in an obviously-unfilled state that matches the user's mental model of what still needs to be done.
  - id: zero-count-orphan-rows
    rule: When a new row is added via 'Add X', it defaults to count 1 (or is visually marked as unconfigured) — never a 0-count orphan in the list.
    condition: When a list allows adding items with a quantity field.
    reason: A 0-count row contributes nothing and creates visual clutter; it implies the user forgot to fill it in.
  - id: unified-field-over-derived-dual-fields
    rule: When two fields are conceptually redundant — one derivable from the other — expose only the field that matches the user's mental model. Derive the internal value in the calculation layer.
    condition: When the data model has two fields representing the same user decision at different abstraction levels.
    reason: The data model is allowed to be verbose; the UI should not be. Forcing users to translate between their vocabulary and the system's internal model creates confusion and opens the risk of the two fields contradicting each other.
  - id: persistent-controls-not-conditional
    rule: A field that is always semantically meaningful must always be visible, even if its effect on the output varies by context. Do not confuse effect-level variation with concept-level inapplicability.
    condition: When a control disappears based on another field's value, but the underlying concept still applies regardless.
    reason: Hiding a control because its effect on a specific calculation varies is wrong — that's an internal implementation concern leaking into the UI. A control that disappears as the user changes a sibling field is disorienting.
  - id: forms-reveal-conditional-fields
    rule: In a form, reveal fields only when a prior answer makes them relevant. Do not show conditional fields disabled or grayed out; keep them hidden until the condition is met, then show them as active.
    condition: When a form has fields whose relevance depends on the value of a sibling field — for example, a billing-address section that only applies when 'different from shipping address' is selected, or a 'specify other' field that appears only when 'Other' is chosen.
    reason: A form that shows all conditional fields — even disabled — forces every user to parse and consciously skip irrelevant content. This creates confusion (why is this grayed out?), implies the field may later matter, and makes the form appear longer and more complex than the user's actual task requires. Revealing fields on demand minimizes apparent complexity and matches form length to the user's actual data-entry needs.
  - id: progressive-disclosure-for-primary-advanced-split
    rule: Use progressive disclosure — hiding secondary options behind a reveal mechanism — when there is a clear usage split between what most users need (primary tasks, essential fields) and what a smaller subset needs (advanced options, edge-case settings). Do not use it when all options are needed with similar frequency or when users cannot predict that hidden content exists.
    condition: When designing an interface — form, settings panel, feature area, or navigation — where controls have noticeably unequal usage frequency and the low-frequency set is large enough to create cognitive overhead.
    reason: Showing all options at once imposes equal cognitive cost on all users, including the majority who only ever need a subset. Progressive disclosure reduces visual complexity for the common case. The cost is discoverability — users who need the hidden options must be able to predict they exist and find the trigger. When that predictability cannot be ensured — because the label is ambiguous or the option is needed by most users — the disclosure mechanism becomes an obstacle.
  - id: validate-on-blur-then-on-change
    rule: Validate a field on `blur` the first time the user leaves it. Once the field is in an error state, switch to `change` events so corrections are acknowledged immediately. Never show validation errors while the user is still typing in a field that has not yet been in error.
    condition: When implementing inline form validation — specifically choosing which DOM event (`blur`, `change`, `input`, `submit`) triggers showing a field-level error message.
    reason: On-change validation that fires before a field has ever errored is accusatory — it flags the user as wrong before they have finished entering a value. On-blur waits for the user to declare they are done with a field, which is the earliest natural moment for a correctness check. Once an error has already been shown, on-change feedback is helpful rather than accusatory — the user is now attempting to fix a known problem and deserves immediate acknowledgment of their corrections. Research shows blur-first validation reduces error rates versus submit-time validation without increasing form completion time.
