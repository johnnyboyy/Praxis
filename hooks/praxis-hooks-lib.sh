#!/usr/bin/env bash
# praxis-hooks-lib.sh — shared primitives for the three praxis enforcement hooks
# (praxis-frame-gate.sh, praxis-frame-stamp.sh, praxis-payload-read-stamp.sh). Sourced, never run.
#
# The three hooks are reached through symlinks (~/.claude/hooks/… → this repo), so each sources
# this file via its OWN resolved real path: ${BASH_SOURCE[0]} must be readlink-resolved to the
# repo copy BEFORE dirname, or the sibling lib can't be found. See each hook's guarded source block.
#
# Each primitive transcribes a rule whose Python source of record lives in root_tree.py / server.py:
#   praxis_walk_to_root  ← root_tree.resolve_root (nearest ancestor carrying .praxis/config.json, then
#                          praxis/config.json — `.praxis` wins; the same order as praxis_dir and
#                          DEFAULT_MARKERS), GIT-BOUNDED and opt-in: it never rises above the git root
#                          (or, no repo, above the start dir), and returns 1 when nothing is marked.
#   praxis_stamp_path    ← the session-stamp path server.py.work_status globs:
#                          $TMPDIR/praxis-front-door/<session>/<sha1 of root path>.
#   praxis_file_age      ← mtime delta in seconds (BSD `stat -f %m` then GNU `stat -c %Y`).
#
# Discipline these hooks record and this lib preserves: FAIL OPEN on any ambiguity. These functions
# never exit the process — they return non-zero and let the calling hook decide. A missing or
# unreadable copy of this lib must likewise NOT hard-fail a hook: each hook's source block degrades
# to `exit 0` (gate ⇒ allow, stamps ⇒ write nothing), the same fail-open its own body already takes.

# mtime of a file in epoch seconds on stdout, or empty + return 1 on failure. BSD then GNU stat.
praxis_mtime() {
  local mtime
  mtime=$(stat -f %m "$1" 2>/dev/null || stat -c %Y "$1" 2>/dev/null)
  [ -z "$mtime" ] && return 1
  printf '%s' "$mtime"
}

# Age of a file in seconds (now - mtime) on stdout; returns 1 (prints nothing) when mtime is
# unavailable, so callers can `AGE=$(praxis_file_age f) || AGE=0` / `|| exit 0` exactly as before.
praxis_file_age() {
  local mtime
  mtime=$(praxis_mtime "$1") || return 1
  echo $(( $(date +%s) - mtime ))
}

# Walk upward from a starting directory to the nearest praxis root, GIT-BOUNDED and OPT-IN. On a hit
# sets two globals and returns 0; returns 1 when no marker is found within the bound (an unmarked
# repo is not managed — the gate hook turns this return-1 into `exit 0`/allow, keeping such repos
# UNGATED). The bound is the git repo root ($git_root); outside a git repo the walk never rises above
# `dir` itself. Same rule as root_tree.resolve_root (the Python source of record). Globals set:
#   PRAXIS_ROOT_PATH — the governing root directory
#   PRAXIS_DIR       — its state dir ($root/.praxis, or legacy $root/praxis)
praxis_walk_to_root() {
  local dir="$1" p git_root
  PRAXIS_ROOT_PATH=""
  PRAXIS_DIR=""
  git_root=$(git -C "$dir" rev-parse --show-toplevel 2>/dev/null)
  while [ "$dir" != "/" ] && [ -n "$dir" ]; do
    for p in .praxis praxis; do
      if [ -f "$dir/$p/config.json" ]; then
        PRAXIS_ROOT_PATH="$dir"
        PRAXIS_DIR="$dir/$p"
        return 0
      fi
    done
    # Stop at the bound: the git root, or (no git repo) `dir` itself — never walk above it.
    if [ -z "$git_root" ] || [ "$dir" = "$git_root" ]; then
      break
    fi
    dir=$(dirname "$dir")
  done
  return 1
}

# The session stamp path for a root: sha1 of the root path under
# $TMPDIR/praxis-front-door/<session>/<hash>, printed on stdout. The read-stamp hook appends `.read`.
praxis_stamp_path() {
  local root_path="$1" session_id="$2" root_hash
  root_hash=$(printf '%s' "$root_path" | shasum | cut -d' ' -f1)
  printf '%s/praxis-front-door/%s/%s' "${TMPDIR:-/tmp}" "$session_id" "$root_hash"
}
