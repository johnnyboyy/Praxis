---
id: recoverability
subject: design
applies-when:
  - has-ui: yes
universal: false
task-kinds: [create, change]
labels: [ui]
---

conventions: []

principles:
  - id: recovery-path-replaces-confirmation
    rule: A destructive action that would cost meaningful re-entry to undo (roughly 30+ seconds of work) needs either a recovery path (undo, saved history, restore) or a confirmation step — never neither, and the trigger button's styling doesn't count as the gate. A visible recovery path (undo toast, restore link) replaces confirmation; confirmation is for actions with no recovery path. Trivial actions below that bar need neither.
    condition: When designing a destructive action that discards user-entered state worth roughly 30+ seconds to re-enter, or where a recovery mechanism already exists or could be built.
    reason: Confirmation adds friction for every user; an undo mechanism only costs the one who errs. An ungated loss of substantial work breaks trust, and a recovery path that isn't visible produces the same anxiety as no recovery at all.
  - id: destructive-inline-confirmation
    rule: Low-stakes destructive actions (remove an item) use an inline row transformation to confirm — not a modal. The row shows the confirmation prompt with confirm and cancel in place of normal content.
    condition: When designing remove/delete actions on list items.
    reason: Modals interrupt flow and feel heavy for reversible, low-consequence actions. Inline confirmation keeps the user in context.
