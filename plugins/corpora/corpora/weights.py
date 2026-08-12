"""Load facet-weights.yaml into an attribute-accessible namespace.

Gives access like:
    W.task_kind['create'].convention_weight
    W.stance['divergent'].anchor / .convention_multiplier / .suppress_posture
    W.workflow['tdd']['weight']
    W.label['*']['pin_weight']

Stance/task_kind inner dicts are wrapped so that a missing key returns None
(e.g. `suppress_posture` is absent on convergent/none stances). Workflow and
label rows stay as plain dicts.
"""

from __future__ import annotations

from pathlib import Path

import yaml

_DEFAULT_PATH = Path(__file__).resolve().parent / "facet_weights.yaml"


class _Facet:
    """Attribute access over a dict, with `.get`-style None fallback."""

    def __init__(self, data: dict):
        self._data = dict(data)

    def __getattr__(self, name: str):
        # __getattr__ only fires for names not found normally, so `_data`
        # (set via __dict__) is safe from recursion.
        return self._data.get(name)

    def get(self, name: str, default=None):
        return self._data.get(name, default)

    def __repr__(self) -> str:
        return f"_Facet({self._data!r})"


class Weights:
    """Namespace over the facet-weights table."""

    def __init__(self, data: dict):
        raw = data or {}
        self.task_kind = {
            k: _Facet(v) for k, v in (raw.get("task_kind") or {}).items()
        }
        self.stance = {k: _Facet(v) for k, v in (raw.get("stance") or {}).items()}
        # Workflow and label stay plain dicts.
        self.workflow = dict(raw.get("workflow") or {})
        self.label = dict(raw.get("label") or {})


def load_weights(path=None) -> Weights:
    """Load facet weights from `path` (defaults to the packaged file)."""
    path = Path(path) if path is not None else _DEFAULT_PATH
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return Weights(data)
