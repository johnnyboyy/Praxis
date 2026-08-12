"""Ported deferred_queue tests, retargeted to the plugin's `.praxis/uiux/` state dir (spec §6)."""

import os

import config
import deferred_queue as dq

VALID = """# Deferred decisions

```yaml
decisions:
  - id: results-empty-state
    stance: convergent
    domain: validation-feedback
    question: "Preserve filters or offer reset?"
    context: "Results panel."
    source-workstream: search
    created: 2026-07-14
    blocking: no
    provisional-treatment: "Preserve filters."
    status: queued
```
"""


def _write_queue(root, text=VALID):
    path = dq.queue_path(str(root))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)
    return path


def test_queue_path_under_praxis_uiux(tmp_path):
    p = dq.queue_path(str(tmp_path))
    assert p.endswith(os.path.join(".praxis", "uiux", "deferred-decisions.md"))


def test_parse_and_validate_clean(tmp_path):
    path = _write_queue(tmp_path)
    entries = dq.parse_deferred(path)
    assert len(entries) == 1
    assert dq.deferred_problems(entries) == []


def test_has_ui_reads_config_scope(tmp_path):
    config.ensure(str(tmp_path))
    config.write(str(tmp_path), "uiux", {"has_ui": "yes"})
    assert dq.has_ui(str(tmp_path)) is True
    config.write(str(tmp_path), "uiux", {"has_ui": "no"})
    assert dq.has_ui(str(tmp_path)) is False


def test_lint_missing_queue_ui_project_fails(tmp_path):
    config.ensure(str(tmp_path))
    config.write(str(tmp_path), "uiux", {"has_ui": "yes"})

    class A:
        root = str(tmp_path)
    assert dq.cmd_lint(A()) == 1


def test_lint_missing_queue_no_ui_ok(tmp_path):
    config.ensure(str(tmp_path))
    config.write(str(tmp_path), "uiux", {"has_ui": "no"})

    class A:
        root = str(tmp_path)
    assert dq.cmd_lint(A()) == 0


def test_resolve_keeps_entry_as_trace(tmp_path):
    path = _write_queue(tmp_path)
    assert dq.resolve(str(tmp_path), "results-empty-state", "Ratified: preserve filters.") is True
    entries = {e["id"]: e for e in dq.parse_deferred(path)}
    entry = entries["results-empty-state"]
    assert entry["status"] == "resolved"
    assert entry["resolution"] == "Ratified: preserve filters."
    assert entry.get("resolved")  # a date was stamped
    # kept, not deleted — still one entry, validates as a resolved trace
    assert dq.deferred_problems(dq.parse_deferred(path)) == []


def test_resolve_missing_queue_is_failsoft(tmp_path):
    assert dq.resolve(str(tmp_path), "x", "y") is False


def test_resolve_unknown_id_is_failsoft(tmp_path):
    _write_queue(tmp_path)
    assert dq.resolve(str(tmp_path), "nope", "y") is False
