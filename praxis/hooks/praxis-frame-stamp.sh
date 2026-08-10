#!/usr/bin/env bash
# praxis-frame-stamp.sh — RETIRED (P2 of docs/CONDUCTOR-PLAN.md).
#
# This PostToolUse hook used to project the frame marker onto a per-session tmp stamp file
# ($TMPDIR/praxis-front-door/<session>/<hash>) so the gate could tell "this session walked the
# front door." The conductor journal replaces that: begin_work / close_work now write
# `unit.framed` / `unit.closed` events directly (front_door_core.py's bridge), and the gate reads
# the open unit from the journal (gate.py → conductor/journal.open_unit) — root-scoped state, not a
# per-session tmp file with a freshness window.
#
# Kept as a no-op (rather than deleted) so its registration in ~/.claude/settings.json stays a
# valid, harmless reference; the settings entry can be dropped in a later de-cruft pass.

exit 0
