#!/usr/bin/env python3
"""policy — the conductor's guardrails as editable data, not hardcoded (P9 of docs/CONDUCTOR-PLAN.md).

The concurrency cap, the retry bound, and whether verification is mandatory are operator guards.
Rather than bake them into the run loop as constants, they live in a `Policy` the operator can edit
at `<root>/.praxis/conductor.json`; `run`/`run_dag` read their defaults from it. A missing or corrupt
file degrades to the built-in defaults, so a project with no policy file still runs.

Example `<root>/.praxis/conductor.json`:
    { "concurrency": 8, "max_retries": 1, "verify_required": true }
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import journal

POLICY_NAME = "conductor.json"


@dataclass
class Policy:
    """Editable conductor guardrails. Defaults match the loop's historical hardcoded values, so
    adopting the policy file changes nothing until the operator edits it."""

    concurrency: int = 4
    max_retries: int = 2
    verify_required: bool = False

    @classmethod
    def from_dict(cls, d: dict) -> "Policy":
        base = cls()
        return cls(
            concurrency=int(d.get("concurrency", base.concurrency)),
            max_retries=int(d.get("max_retries", base.max_retries)),
            verify_required=bool(d.get("verify_required", base.verify_required)),
        )


def policy_path(root: Path) -> Path:
    return journal.journal_path(root).parent / POLICY_NAME


def load_policy(root: Path) -> Policy:
    """The root's conductor policy, or the built-in defaults when no readable/parseable file exists."""
    path = policy_path(root)
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return Policy()
    return Policy.from_dict(data) if isinstance(data, dict) else Policy()
