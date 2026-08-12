#!/usr/bin/env python3
"""rebuild_ir — the structured IR the rebuild-triple's `extract` phase emits.

    IR = {
        "interface":       [{"symbol": str, "signature": str}, ...],
        "allowed_surface": [symbol, ...],
        "tests":           {"spec": [path, ...], "held_out": [path, ...]},
    }

`interface` is the contract synthesize must reproduce (symbol + signature);
`allowed_surface` is the ceiling on the synth's public surface (losslessness);
`tests.spec` are the tests synthesize is allowed to see, `tests.held_out` are
kept back to prove generalization at the preservation gate.

`validate_ir` is FAIL-CLOSED: any malformed IR raises `IRError`. It also enforces
that the held-out split is real — non-empty AND a non-trivial fraction of the
whole (>= `HELD_OUT_MIN_FRACTION`) — so an `extract` that keeps nothing back
cannot pass the adequacy gate.
"""
from __future__ import annotations

import json

# The held-out tests must be at least this fraction of the total test count.
HELD_OUT_MIN_FRACTION = 0.25


class IRError(ValueError):
    """Raised when an IR is malformed or its held-out split is inadequate."""


def parse_ir(obj) -> dict:
    """Accept a dict or a JSON string, return a validated IR dict (fail-closed)."""
    if isinstance(obj, str):
        try:
            obj = json.loads(obj)
        except json.JSONDecodeError as e:
            raise IRError(f"IR is not valid JSON: {e}") from e
    return validate_ir(obj)


def validate_ir(ir) -> dict:
    """Validate structure + split. Returns the IR unchanged, or raises IRError."""
    if not isinstance(ir, dict):
        raise IRError(f"IR must be an object, got {type(ir).__name__}")

    interface = ir.get("interface")
    if not isinstance(interface, list):
        raise IRError("IR.interface must be a list")
    for i, entry in enumerate(interface):
        if not isinstance(entry, dict):
            raise IRError(f"IR.interface[{i}] must be an object")
        if not isinstance(entry.get("symbol"), str) or not entry["symbol"]:
            raise IRError(f"IR.interface[{i}].symbol must be a non-empty string")
        if not isinstance(entry.get("signature"), str):
            raise IRError(f"IR.interface[{i}].signature must be a string")

    allowed = ir.get("allowed_surface")
    if not isinstance(allowed, list) or not all(isinstance(s, str) for s in allowed):
        raise IRError("IR.allowed_surface must be a list of strings")

    tests = ir.get("tests")
    if not isinstance(tests, dict):
        raise IRError("IR.tests must be an object")
    spec = tests.get("spec")
    held = tests.get("held_out")
    if not isinstance(spec, list) or not all(isinstance(s, str) for s in spec):
        raise IRError("IR.tests.spec must be a list of strings")
    if not isinstance(held, list) or not all(isinstance(s, str) for s in held):
        raise IRError("IR.tests.held_out must be a list of strings")

    if not held:
        raise IRError("IR.tests.held_out must be non-empty (a real split)")
    total = len(spec) + len(held)
    if total and len(held) / total < HELD_OUT_MIN_FRACTION:
        raise IRError(
            f"held-out split too small: {len(held)}/{total} "
            f"< {HELD_OUT_MIN_FRACTION:.0%}")

    return ir
