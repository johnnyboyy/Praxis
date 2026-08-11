---
description: Drive a whole task autonomously through praxis — decompose it into a unit DAG and run it as a detached cascade (spawn per unit, barrier full-verify, fix-loop, escalation). Use for multi-step work you want to hand off and walk away from.
disable-model-invocation: true
---

The task to drive is: $ARGUMENTS

1. Decompose it into a praxis tasklist — a JSON array of unit objects, each with `intent`, `task_kind` (create|change|explore), `subject`, `fit`, and `depends_on` edges. Fill `suggested_kind`/`fit` honestly (a loose/none fit surfaces a vocabulary gap).
2. Call the praxis MCP `plan` tool with `dry_run=false` (and `allow_edits=true`) to run it as a DETACHED cascade — barrier full-verify + fix-units + escalation.
3. Report the plan and that it is running detached. Tell the user they can drop out; poll `plan_status` to report progress until complete.
