---
id: motion
subject: design
applies-when:
  - has-ui: yes
universal: false
task-kinds: [create, change]
labels: [ui]
---

conventions: []

principles:
  - id: motion-as-accent
    rule: Use motion sparingly and purposefully when a state change benefits from a moment of legibility — a result appearing, a row being removed, a success state landing. Do not use motion decoratively or as a default on all interactive elements.
    condition: Any state change or element transition in UI. Richer motion only when explicitly requested.
    reason: Motion means something when used sparingly; it becomes noise when used everywhere. New motion should feel native to the existing register, not expressive for its own sake.
  - id: scrollytelling-must-always-react
    rule: In a scrollytelling section where scroll input drives animation, the experience must provide visible feedback that input is being received at all times — not only at major action moments. Between set-pieces, a subtle continuous effect must make clear that scrolling is doing something.
    condition: Any section that intercepts scroll to drive a narrative animation — sticky full-viewport sections, scroll-driven SVG animations, parallax-driven reveals.
    reason: When scroll is the primary input and nothing visibly reacts, users lose their mental model of control. They don't know if they've scrolled far enough, if something is broken, or if they should try something else.
  - id: back-navigation-is-faster-than-forward
    rule: Back navigation transitions run at 60–70% of the forward duration, with --ease-out replacing --ease-in-out on the shared element.
    condition: Any shared-element view transition with a defined forward direction.
    reason: Returning to a known context should feel like release, not a reversal of the forward arrival's intentional weight. The easing asymmetry — no front-weighted acceleration on back — signals return rather than deliberate arrival.
  - id: reduced-motion-instant-not-absent
    rule: When `prefers-reduced-motion` is active, make state-communicating animations instant (duration → 0) rather than absent. Remove only decorative or continuous motion (auto-playing loops, parallax, background animations) entirely.
    condition: "When adapting animations for the `prefers-reduced-motion` preference. The instant-vs-absent distinction applies to: instant for animations that communicate a state change (item appearing, being removed, reordering); remove entirely for animations that exist only for visual interest with no functional role."
    reason: An animation communicating a state change (an item appearing or being removed) conveys meaning through its endpoint, not its motion. Removing it entirely causes the UI to jump without context, which can be as disorienting as the motion itself. Setting duration to zero delivers the same endpoint with no motion. Decorative animations serve no function and add no clarity when instant — they should be removed.
