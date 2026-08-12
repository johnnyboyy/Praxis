"""A minimal second praxis contributor used by test_unit_close_e2e.

Proves the `unit-close` seam is GENERAL — any config-registered contributor can
ride the same per-unit event, not just uiux. It has the required `source` +
`contribute`, and a `hooks()` table with a `unit-close` (and `close`) hook that
records exactly what core delivered into the module-level `RECEIVED` list, so the
driving test can assert the fire count + the received unit/receipt.

Registered from a throwaway root's config as `_close_recorder:make`; the test puts
this file's directory on sys.path so `contributors_for` can import it by name.
"""

from __future__ import annotations

# Module-level so the test (which imports this same cached module) sees what the
# live `contributors.fire` delivered. The test clears it at the start of each run.
RECEIVED: list[dict] = []


def reset() -> None:
    RECEIVED.clear()


class CloseRecorder:
    source = "recorder"

    def __init__(self, root):
        self.root = root

    def contribute(self, situation):
        return []

    def hooks(self) -> dict:
        return {"unit-close": self._on, "close": self._on}

    def _on(self, ctx) -> None:
        RECEIVED.append({
            "step": ctx.step,
            "unit": getattr(ctx.unit, "id", None),
            "receipt": ctx.receipt,
        })


def make(root) -> "CloseRecorder":
    return CloseRecorder(root)
