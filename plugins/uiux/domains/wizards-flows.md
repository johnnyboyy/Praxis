---
id: wizards-flows
subject: design
applies-when:
  - has-ui: yes
universal: false
task-kinds: [create, change]
labels: [ux]
---

conventions: []

principles:
  - id: origin-step-marked-visited-on-navigation
    rule: When a user navigates away from a step — via Next, Back, or direct tab click — the origin step is added to the visited set before the destination step becomes current.
    condition: When implementing step-wizard visited/completion tracking.
    reason: Adding only the destination to visited means the starting step is never marked as visited. The correct event is departure, not arrival.
  - id: wizard-output-consistent-regardless-of-path
    rule: A wizard's result or summary screen must present the same affordances — edit links, navigation shortcuts, warnings with their actions — regardless of whether the user stepped through sequentially or jumped directly via the progress tabs.
    condition: When a wizard has both linear (Next/Back) and non-linear (tab) navigation paths to the same output or summary screen.
    reason: Conditional capability based on how the user arrived creates an inconsistent experience. Users who discover non-linear navigation should not be penalized with a reduced feature set.
  - id: optional-step-must-be-labeled-optional
    rule: A wizard step that contributes zero to the result when left completely blank should display a brief note that skipping it is valid ('Skip if not applicable').
    condition: When any wizard step is genuinely optional and leaving it empty is a correct choice for a meaningful subset of users.
    reason: Without explicit permission to skip, users may feel they are making an error by proceeding without entering something.
