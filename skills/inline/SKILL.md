---
description: Do one small thing or answer a question in this conversation via praxis — frame a single unit, work in-context, close it. For questions, small carry-edge edits, and exploration.
disable-model-invocation: true
---

The task or question is: $ARGUMENTS

- If it is a question or needs no file edits, just answer/do it here — no unit needed.
- If it needs edits: call the praxis MCP `register_plan` with a single-unit tasklist, then `next_handoff` to open the edit gate, do the work in THIS conversation, then `close_unit` when finished.
