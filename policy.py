#!/usr/bin/env python3
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import journal

POLICY_NAME = "conductor.json"

@dataclass
class Policy:

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
    path = policy_path(root)
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return Policy()
    return Policy.from_dict(data) if isinstance(data, dict) else Policy()
