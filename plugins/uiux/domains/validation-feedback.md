---
id: validation-feedback
subject: design
applies-when:
  - has-ui: yes
universal: false
task-kinds: [create, change]
labels: [ui]
---

conventions: []

principles:
  - id: warning-banner-must-locate-its-fix
    rule: A warning either scrolls/focuses to the offending field, or names the field precisely in the warning text. A generic warning banner with no location is not acceptable.
    condition: When a calculated result or validation error triggers a warning.
    reason: A warning without location forces the user to scan the entire form to find what to change.
  - id: warning-colocated-with-resolution
    rule: Warnings appear adjacent to the control that resolves them, not in a separate banner area.
    condition: When a calculated result triggers a warning that the user must act on.
    reason: Co-location eliminates the need to scan the page to find what to change.
  - id: filter-side-effects-are-surfaced
    rule: When an input narrows the results list, the results panel indicates what filter is active and why items were excluded.
    condition: When a tool has inputs that affect which results appear in a list.
    reason: Silent filtering looks like a bug — users see fewer options and don't know if they've misconfigured something.
