#!/usr/bin/env python3
from __future__ import annotations

import json

HELD_OUT_MIN_FRACTION = 0.25

class SpecError(ValueError):
    pass

def parse_spec(obj) -> dict:
    if isinstance(obj, str):
        try:
            obj = json.loads(obj)
        except json.JSONDecodeError as e:
            raise SpecError(f"spec is not valid JSON: {e}") from e
    return validate_spec(obj)

def validate_spec(spec) -> dict:
    if not isinstance(spec, dict):
        raise SpecError(f"spec must be an object, got {type(spec).__name__}")

    interface = spec.get("interface")
    if not isinstance(interface, list):
        raise SpecError("spec.interface must be a list")
    for i, entry in enumerate(interface):
        if not isinstance(entry, dict):
            raise SpecError(f"spec.interface[{i}] must be an object")
        if not isinstance(entry.get("symbol"), str) or not entry["symbol"]:
            raise SpecError(f"spec.interface[{i}].symbol must be a non-empty string")
        if not isinstance(entry.get("signature"), str):
            raise SpecError(f"spec.interface[{i}].signature must be a string")

    allowed = spec.get("allowed_surface")
    if not isinstance(allowed, list) or not all(isinstance(s, str) for s in allowed):
        raise SpecError("spec.allowed_surface must be a list of strings")

    tests = spec.get("tests")
    if not isinstance(tests, dict):
        raise SpecError("spec.tests must be an object")
    spec_tests = tests.get("spec")
    held = tests.get("held_out")
    if not isinstance(spec_tests, list) or not all(isinstance(s, str) for s in spec_tests):
        raise SpecError("spec.tests.spec must be a list of strings")
    if not isinstance(held, list) or not all(isinstance(s, str) for s in held):
        raise SpecError("spec.tests.held_out must be a list of strings")

    if not held:
        raise SpecError("spec.tests.held_out must be non-empty (a real split)")
    total = len(spec_tests) + len(held)
    if total and len(held) / total < HELD_OUT_MIN_FRACTION:
        raise SpecError(
            f"held-out split too small: {len(held)}/{total} "
            f"< {HELD_OUT_MIN_FRACTION:.0%}")

    return spec
