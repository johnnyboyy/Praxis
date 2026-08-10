#!/usr/bin/env python3
"""corpus.py — deterministic bookkeeping for a corpora project.

Judgment stays with the model; arithmetic and verification live here. The model
supplies its judgments (ratify counts, fired/violated/idle classifications) as
arguments; this script does all measuring, counting, threshold math, and writing.

Runs from a project root (the directory containing `.corpora/`), or pass --root.
State lives in a script-owned block inside `.corpora/domains/audit.md`, delimited
by markers — the script never touches anything outside its markers.

Commands:
  measure [--domains-dir --audit]  update working-file-tokens for every domain (defaults to the
                                   project layer; override to measure any domains-dir + audit.md
                                   pair — e.g. this skill's own domains/, same as kill-report)
  verify [--domains-dir --audit]   reconcile ledger against working files (detects
                                   unrecorded gates and gate-bypassing writes)
  record-gate --domain D [...]     record a ratify gate's outcomes (same --domains-dir/--audit
                                   override)
  add-principle [...]              write a principle/convention + its audit.md provenance entry
                                   and record the gate, atomically — no hand edits to either file
  ratify-import-candidate --id I   write a queued import-candidate entry to its destination domain
                                   + provenance, record the gate, and remove it from the source —
                                   the scripted write-back kernel.md's "Write-back format" describes
  triggers                         evaluate thresholds; print what fires
  lint-handoff FILE                validate a handoff artifact's envelope
  handoffs                         list lingering handoff files with age
  handoff-done FILE                close a ratified handoff: delete it, or archive it under
                                   .corpora/handoffs/archive/ when .corpora/config.md sets debug: yes
  lint-deterministic-shortcut-candidates          validate the persistent deterministic-shortcut-candidate ledger
  deterministic-shortcut-candidates               list candidates with status and sighting count
  record-deterministic-shortcut-candidate [...]   append dated evidence to a candidate
  set-deterministic-shortcut-status [...]         record the operator's candidate disposition
  retro-done --domain D [...]       reset counters after a retrospective (same --domains-dir/--audit
                                   override)
  sync-done [...]                  reset library-drift after a UI/UX-library sync (same
                                   --domains-dir/--audit override)
  emit-spawn-parts [...]           emit the engine-contributed parts of a spawn prompt (stance
                                   frame + full domain files, byte-for-byte, from this project's
                                   own .corpora/domains/ or --domains-dir + handoff schema) plus any
                                   composition problems, as JSON — praxis composes + saves them
                                   (spawn-prompt assembly moved to praxis with the split)
  screenshot-record [...]          register/update a captured screen variant in the manifest
  screenshot-mark-stale [...]      invalidate screens by direct id or shared-component ripple
  screenshot-status                list current/stale screens in the manifest
  screenshot-lookup --component C  which screens already show component C, and where
  lint-screenshots                 validate the screenshot manifest structurally
  lint-domains --domains-dir D     validate domain frontmatter (subject/posture/applies-when/
                                   units-of-work) — works on any domains-dir, same as kill-report
  resolve-root --file F             nearest-ancestor walk from a file to the corpora root
                                   (dir containing .corpora/config.md) that governs it
  check-root-boundary --files [...] fail (exit 2) if a task's touched files resolve to more than
                                   one corpora root — the monorepo split signal
  manifest [--json]                emit the machine-readable domain index for this project's own
                                   .corpora/domains/ (or --domains-dir): every domain's subject/
                                   posture/applies-when/units-of-work plus its principles' id+
                                   condition and conventions' ids — never rule/reason
  select --unit-of-work U [...]    deterministic domain selection for a unit-of-work, evaluated
                                   against .corpora/config.md's project-shape — no model in the loop
  import-list --source D           browse a source domains-dir's principles+conventions, flagging
                                   ids already present in the target; read-only, proposes nothing
  import-candidate --source D [...] propose one principle/convention from a source domains-dir as
                                   a candidate (.corpora/import-candidates.md), imported-from
                                   provenance, optional --as-domain/--as-id retargeting/rename
  import-default-pool [...]        propose every principle+convention whose applies-when already
                                   matches this project's shape, from every domain in the source
                                   (defaults to this skill's own domains/) — the bootstrap fast path.
                                   Re-running is a sync: source-side edits of ids already present
                                   queue as `change: update` candidates, source-side kills of
                                   entries still live here as `change: kill` — gate-mediated, and
                                   pending candidates are never re-queued
  check-composition --domains [...] fail (exit 2) if a domain list mixes subjects (coding/design)
                                   or includes a posture: generative domain
  (Chunk/unit-of-work bookkeeping — chunk-start/chunk-done/lint-chunks/close-workstream/
   verify-chunks — moved to praxis's chunk_ledger.py; it is no longer a corpora concern.)

Thresholds (kernel.md, "The retrospective"): retrospective when ratified >= 6,
or tokens grew >= 50% over baseline, or gate-violations >= 3; library sync when
since-last-sync >= 3.
"""
from __future__ import annotations

import argparse
import datetime
import os
import re
import shutil
import sys

MARK_BEGIN = "<!-- corpus-script:begin — maintained by scripts/corpus.py; do not edit by hand -->"
MARK_END = "<!-- corpus-script:end -->"

RETRO_RATIFIED = 6
RETRO_TOKEN_GROWTH = 0.5
RETRO_VIOLATIONS = 3
SYNC_DRIFT = 3

STATUS_ENUM = {"complete", "tradeoffs-pending", "questions-pending", "blocked"}
KIND_ENUM = {"judgment", "knowledge"}
STANCE_ENUM = {"convergent", "divergent"}
SHORTCUT_STATUS_ENUM = {"open", "deferred", "denied", "accepted", "implemented"}
SHORTCUT_STATUS_REQUIRES_REASON = {"deferred", "denied"}
SCREENSHOT_STATUS_ENUM = {"current", "stale"}
DOMAIN_SUBJECT_ENUM = {"coding", "design", "process"}
DOMAIN_POSTURE_ENUM = {"guardrail", "generative"}
CONFIG_SHAPE_FIELDS = {"language", "framework", "styling", "has-ui", "package-manager"}


def today() -> str:
    return datetime.date.today().isoformat()


def est_tokens(path: str) -> int:
    return os.path.getsize(path) // 4


def fail(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(2)


def project_debug(project: "Project") -> bool:
    """.corpora/config.md's `debug: yes` opt-in — gates audit-trail writes that have no
    functional role otherwise (saved session-prompt copies, retained ratified handoffs)."""
    if not os.path.exists(project.config_path):
        return False
    text = open(project.config_path).read()
    return re.search(r"^debug:\s*(yes|true)\s*$", text, re.MULTILINE | re.IGNORECASE) is not None


# ── project layout ──────────────────────────────────────────────────────────

class Project:
    def __init__(self, root: str, domains_dir: str = "", audit_path: str = ""):
        self.root = root
        # `.corpora/` is the standard project-state dir (dot-prefixed like other tooling state);
        # bare `corpora/` is recognized for existing projects. A repo that SHIPS a .corpora/ source
        # tree can self-host cleanly: its state lives in `.corpora/`, and a `domains-dir:` key in
        # config.md may point the pool anywhere (e.g. at the shipped source pool itself).
        base = "corpora"
        if os.path.isfile(os.path.join(root, ".corpora", "config.md")):
            base = ".corpora"
        self.config_path = os.path.join(root, base, "config.md")
        if not domains_dir:
            domains_dir = os.path.join(root, base, "domains")
            declared = self._declared_domains_dir()
            if declared:
                domains_dir = declared if os.path.isabs(declared) else os.path.join(root, declared)
        self.domains_dir = domains_dir
        self.audit_path = audit_path or os.path.join(self.domains_dir, "audit.md")
        self.deterministic_shortcut_candidates_path = os.path.join(root, base, "deterministic-shortcut-candidates.md")
        self.screenshots_dir = os.path.join(root, base, "screenshots")
        self.screenshot_manifest_path = os.path.join(self.screenshots_dir, "manifest.md")
        self.queue_path = os.path.join(root, base, "queue.md")
        self.import_candidates_path = os.path.join(root, base, "import-candidates.md")
        # No existence check here: `.corpora/domains/` only ever holds *ratified* project
        # principles, so a freshly-bootstrapped project with nothing ratified yet legitimately
        # has no such directory. A command that only reads (select, manifest, chunk-start/-done,
        # emit-spawn-parts) must work against a project with zero project-level domains —
        # domain_files() below returns {} rather than raising. A command that writes into this
        # layer (record-gate, retro-done, sync-done, via save()) creates the directory lazily on
        # first write instead. A command whose result is meaningless without it (e.g. record-gate
        # for a specific domain) still fails, but with a message naming what's actually missing,
        # not a blanket precondition every command pays for.

    def _declared_domains_dir(self) -> str | None:
        """Optional `domains-dir:` key in config.md — where this project's pool lives when it is
        not the default `<state-dir>/domains` (the self-hosting repo points it at its shipped
        source pool)."""
        if not os.path.isfile(self.config_path):
            return None
        m = re.search(r"^domains-dir:\s*(.+?)\s*$", open(self.config_path).read(), re.MULTILINE)
        return m.group(1) if m else None

    def domain_files(self) -> dict:
        out = {}
        if not os.path.isdir(self.domains_dir):
            return out
        audit_name = os.path.basename(self.audit_path)
        for name in sorted(os.listdir(self.domains_dir)):
            if name.endswith(".md") and name != audit_name:
                out[name[:-3]] = os.path.join(self.domains_dir, name)
        return out


# ── state block: parse / render ─────────────────────────────────────────────
# The block is flat, fixed-schema YAML the script alone writes, so a purpose-
# built parser is safe. Structure:
#   counters:      list of per-domain dicts
#   efficacy:      list of per-principle dicts
#   library-drift: one dict

def empty_state() -> dict:
    return {"counters": [], "efficacy": [], "co-occurrence": [], "library-drift": {"since-last-sync": 0}}


def parse_state(text: str) -> dict:
    state = empty_state()
    list_sections = ("counters", "efficacy", "co-occurrence")
    bodies = {name: [] for name in list_sections}
    section = None
    for raw in text.splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("```"):
            continue
        if not line.startswith(" "):
            key = line.rstrip(":")
            section = key if key in ("counters", "efficacy", "co-occurrence", "library-drift") else None
            continue
        if section is None:
            continue
        if section == "library-drift":
            if ":" in stripped:
                k, _, v = stripped.partition(":")
                k, v = k.strip(), v.strip()
                state[section][k] = int(v) if re.fullmatch(r"-?\d+", v) else v
            continue
        bodies[section].append(line)
    for name in list_sections:
        state[name] = _parse_flat_list(bodies[name], item_key=None,
                                       list_fields=("domains",), coerce_int=True)
    return state


COUNTER_FIELDS = ["domain", "since", "ratified", "killed", "graduated", "gate-violations",
                  "working-file-tokens", "baseline-tokens",
                  "principles-at-baseline", "kills-at-baseline", "conventions-at-baseline"]
COOCCURRENCE_FIELDS = ["domains", "count"]


def count_entries(path: str) -> tuple:
    """Count convention, principle, and kill entries in a domain working file.

    Ground truth for `verify`: entries are appended under `conventions:`, `principles:`, and
    `killed:` keys; each entry opens with `- id:`. Tolerant of indentation and
    of the keys appearing inside a yaml fence. The kill count should be zero everywhere since
    2026-08-07 (kill records live in audit.md); `verify` flags any working-file kill entry.
    """
    conventions = principles = kills = 0
    section = None
    for raw in open(path):
        line = raw.strip()
        if re.fullmatch(r"conventions:\s*", line):
            section = "c"
        elif re.fullmatch(r"principles:\s*", line):
            section = "p"
        elif re.fullmatch(r"killed:\s*", line):
            section = "k"
        elif re.match(r"-\s*id:", line):
            if section == "c":
                conventions += 1
            elif section == "p":
                principles += 1
            elif section == "k":
                kills += 1
    return principles, kills, conventions


EFFICACY_FIELDS = ["id", "fired", "violated", "idle"]


def render_state(state: dict) -> str:
    lines = ["```yaml", "counters:"]
    for c in state["counters"]:
        prefix = "  - "
        for f in COUNTER_FIELDS:
            lines.append(f"{prefix}{f}: {c.get(f, 0)}")
            prefix = "    "
    lines.append("efficacy:")
    for e in state["efficacy"]:
        prefix = "  - "
        for f in EFFICACY_FIELDS:
            lines.append(f"{prefix}{f}: {e.get(f, 0)}")
            prefix = "    "
    lines.append("co-occurrence:")
    for pair in state["co-occurrence"]:
        prefix = "  - "
        for f in COOCCURRENCE_FIELDS:
            if f == "domains":
                lines.append(f"{prefix}domains: [{', '.join(pair.get('domains', []))}]")
            else:
                lines.append(f"{prefix}{f}: {pair.get(f, 0)}")
            prefix = "    "
    lines.append("library-drift:")
    lines.append(f"  since-last-sync: {state['library-drift'].get('since-last-sync', 0)}")
    lines.append("```")
    return "\n".join(lines)


def load(project: Project) -> dict:
    if not os.path.exists(project.audit_path):
        return empty_state()
    text = open(project.audit_path).read()
    if MARK_BEGIN not in text:
        return empty_state()
    block = text.split(MARK_BEGIN, 1)[1].split(MARK_END, 1)[0]
    return parse_state(block)


def save(project: Project, state: dict) -> None:
    block = f"{MARK_BEGIN}\n\n## counters (script-maintained)\n\n{render_state(state)}\n\n{MARK_END}"
    os.makedirs(os.path.dirname(project.audit_path), exist_ok=True)
    if os.path.exists(project.audit_path):
        text = open(project.audit_path).read()
    else:
        text = "# Audit — project layer\n"
    if MARK_BEGIN in text:
        head = text.split(MARK_BEGIN, 1)[0]
        tail = text.split(MARK_END, 1)[1] if MARK_END in text else "\n"
        text = head + block + tail
    else:
        text = text.rstrip("\n") + "\n\n" + block + "\n"
    open(project.audit_path, "w").write(text)


def counter_for(state: dict, domain: str, tokens: int, path: str = "") -> dict:
    for c in state["counters"]:
        if c.get("domain") == domain:
            c.setdefault("graduated", 0)
            c.setdefault("conventions-at-baseline", 0)
            return c
    p, k, conv = count_entries(path) if path else (0, 0, 0)
    c = {"domain": domain, "since": today(), "ratified": 0, "killed": 0,
         "graduated": 0, "gate-violations": 0, "working-file-tokens": tokens, "baseline-tokens": tokens,
         "principles-at-baseline": p, "kills-at-baseline": k, "conventions-at-baseline": conv}
    state["counters"].append(c)
    return c


def co_occurrence_for(state: dict, domain_a: str, domain_b: str) -> dict:
    pair = sorted([domain_a, domain_b])
    for entry in state["co-occurrence"]:
        if sorted(entry.get("domains", [])) == pair:
            return entry
    entry = {"domains": pair, "count": 0}
    state["co-occurrence"].append(entry)
    return entry


def efficacy_for(state: dict, pid: str) -> dict:
    for e in state["efficacy"]:
        if e.get("id") == pid:
            return e
    e = {"id": pid, "fired": 0, "violated": 0, "idle": 0}
    state["efficacy"].append(e)
    return e


# ── commands ────────────────────────────────────────────────────────────────

def cmd_measure(project: Project, _args) -> None:
    state = load(project)
    for domain, path in project.domain_files().items():
        tokens = est_tokens(path)
        c = counter_for(state, domain, tokens, path)
        c["working-file-tokens"] = tokens
        print(f"{domain}: ~{tokens} tokens (baseline {c['baseline-tokens']})")
    save(project, state)


def cmd_verify(project: Project, _args) -> None:
    """Reconcile the ledger against the working files (the ground truth).

    Invariant: entries in each working file == entries at baseline + entries
    recorded since. A surplus means a gate ran off the books (or a write
    bypassed the gate entirely); a deficit means entries were removed without
    a retrospective reset. Read-and-report only — the operator decides.
    """
    # A pool without a config.md has nothing to stamp — the schema gate applies to real,
    # bootstrapped pools; bare domains-dirs are governed by the per-file checks alone.
    if os.path.exists(project.config_path):
        schema = read_schema_version(project.config_path)
        if schema < SCHEMA_VERSION:
            print(f"POOL SCHEMA STALE: schema-version {schema}, current {SCHEMA_VERSION} — "
                  "run `corpus.py migrate` first; the reconciliation below would only report "
                  "symptoms of the missing migration(s).")
            sys.exit(1)
    state = load(project)
    known = {c.get("domain"): c for c in state["counters"]}
    problems = []
    for domain, path in project.domain_files().items():
        c = known.get(domain)
        if c is None:
            problems.append(f"{domain}: not in ledger — run `measure` to register it")
            continue
        actual_p, actual_k, actual_conv = count_entries(path)
        expect_p = c.get("principles-at-baseline", 0) + c.get("ratified", 0) - c.get("graduated", 0)
        expect_conv = c.get("conventions-at-baseline", 0) + c.get("graduated", 0)
        if actual_p != expect_p:
            what = "UNRECORDED ratification(s)" if actual_p > expect_p else "entries REMOVED outside a retrospective"
            problems.append(f"{domain}: {abs(actual_p - expect_p)} {what} "
                            f"(file has {actual_p} principles; ledger accounts for {expect_p})")
        if actual_k:
            # Kill records live only in audit.md (2026-08-07): a working file's `killed:` list
            # stays empty — it is a structural anchor, not storage.
            problems.append(f"{domain}: {actual_k} kill entr{'y' if actual_k == 1 else 'ies'} in the "
                            "working file — kills belong in audit.md's kill log; move them there")
        if actual_conv != expect_conv:
            what = "UNRECORDED graduation(s) to convention" if actual_conv > expect_conv else "convention entries REMOVED outside a retrospective"
            problems.append(f"{domain}: {abs(actual_conv - expect_conv)} {what} "
                            f"(file has {actual_conv} conventions; ledger accounts for {expect_conv})")
    if problems:
        print("LEDGER RECONCILIATION FAILED — corpus changed off the books:")
        for p in problems:
            print(f"  - {p}")
        print("Fix: run `record-gate` retroactively for the unrecorded gate(s), or `measure`/`retro-done` to re-baseline knowingly.")
        sys.exit(1)
    print("ledger reconciled: every corpus entry is accounted for by a recorded gate")


def _ids(arg: str) -> list:
    return [s.strip() for s in (arg or "").split(",") if s.strip()]


def record_gate_core(project: Project, domain: str, domain_path: str, *, ratified: int = 0,
                      killed: int = 0, graduated: int = 0, violations: int = 0, removed: int = 0,
                      fired=(), violated=(), idle=(), ui_drift: bool = False,
                      co_occurs_with=()) -> None:
    """The bookkeeping core shared by `record-gate` and any other write path that ratifies,
    kills, or graduates a domain entry — `add-principle`/`ratify-import-candidate` call this
    directly instead of separately invoking `record-gate` as a second manual step, so a scripted
    write and its ledger entry can never drift apart the way a hand-edit-then-remember-to-run-
    record-gate sequence can."""
    state = load(project)
    tokens = est_tokens(domain_path)
    existed = any(c.get("domain") == domain for c in state["counters"])
    c = counter_for(state, domain, tokens, domain_path)
    if not existed:
        # First registration during a gate: the file already contains the entries this gate
        # ratified/killed/graduated (write-back precedes record-gate), so exclude them from the
        # baseline or verify would double-count them.
        c["principles-at-baseline"] = max(0, c["principles-at-baseline"] - ratified + graduated)
        c["kills-at-baseline"] = max(0, c["kills-at-baseline"] - killed)
        c["conventions-at-baseline"] = max(0, c["conventions-at-baseline"] - graduated)
    elif killed or removed:
        # A mid-cycle kill, move-out, or supersede removed a live principle from the file; drop
        # it from the recorded baseline so verify's principles invariant holds without waiting
        # for a retrospective re-baseline (`killed` is a pure event counter — the kill record
        # itself lands in audit.md's kill log, never back in the working file; `removed` is a
        # move/supersede departure with no kill record at all).
        c["principles-at-baseline"] = max(0, c["principles-at-baseline"] - killed - removed)
    c["working-file-tokens"] = tokens
    c["ratified"] += ratified
    c["killed"] += killed
    c["graduated"] += graduated
    c["gate-violations"] += violations
    for pid in fired:
        efficacy_for(state, pid)["fired"] += 1
    for pid in violated:
        efficacy_for(state, pid)["violated"] += 1
    for pid in idle:
        efficacy_for(state, pid)["idle"] += 1
    if ui_drift:
        state["library-drift"]["since-last-sync"] = state["library-drift"].get("since-last-sync", 0) + 1
    for other in co_occurs_with:
        co_occurrence_for(state, domain, other)["count"] += 1
    save(project, state)
    print(f"recorded gate for {domain}: +{ratified} ratified, +{killed} killed, "
          f"+{violations} violations, drift={'+1' if ui_drift else 'no'}")
    cmd_triggers(project, None)


def cmd_record_gate(project: Project, args) -> None:
    files = project.domain_files()
    if args.domain not in files:
        fail(f"unknown domain '{args.domain}' — have: {', '.join(files) or 'none'}")
    record_gate_core(project, args.domain, files[args.domain], ratified=args.ratified,
                      killed=args.killed, graduated=args.graduated, violations=args.violations,
                      fired=_ids(args.fired), violated=_ids(args.violated), idle=_ids(args.idle),
                      ui_drift=args.ui_drift, co_occurs_with=_ids(args.co_occurs_with))


def cmd_triggers(project: Project, _args) -> None:
    state = load(project)
    fired = []
    for c in state["counters"]:
        reasons = []
        if c.get("ratified", 0) >= RETRO_RATIFIED:
            reasons.append(f"ratified {c['ratified']} >= {RETRO_RATIFIED}")
        base = c.get("baseline-tokens", 0)
        cur = c.get("working-file-tokens", 0)
        if base and cur >= base * (1 + RETRO_TOKEN_GROWTH):
            reasons.append(f"tokens {cur} grew >= {int(RETRO_TOKEN_GROWTH*100)}% over baseline {base}")
        if c.get("gate-violations", 0) >= RETRO_VIOLATIONS:
            reasons.append(f"violations {c['gate-violations']} >= {RETRO_VIOLATIONS}")
        if reasons:
            fired.append(f"retrospective {c['domain']} — " + "; ".join(reasons))
    drift = state["library-drift"].get("since-last-sync", 0)
    if drift >= SYNC_DRIFT:
        fired.append(f"ui + ux library sync — drift {drift} >= {SYNC_DRIFT}")
    if fired:
        print("TRIGGERS FIRED (suggest to operator — never automatic):")
        for f in fired:
            print(f"  - {f}")
    else:
        print("triggers: none")


def parse_deterministic_shortcut_candidates(path: str) -> list:
    entries = []
    item = None
    evidence = None
    in_candidates = False
    in_evidence = False
    in_disposition = False
    for raw in open(path):
        line = raw.rstrip()
        stripped = line.strip()
        if in_candidates and stripped == "```":
            break
        if stripped in {"candidates:", "candidates: []"}:
            in_candidates = True
            continue
        if not in_candidates or not stripped or stripped.startswith(("#", "```")):
            continue
        if re.match(r"^\s{2}-\s+id:\s*", line):
            item = {"evidence": [], "disposition-reason": ""}
            entries.append(item)
            item["id"] = stripped.partition(":")[2].strip().strip('"').strip("'")
            in_evidence = False
            in_disposition = False
            continue
        if item is None:
            continue
        top = re.match(r"^\s{4}([a-z][a-z0-9-]*):\s*(.*)$", line)
        if top:
            key, value = top.groups()
            in_evidence = key == "evidence"
            in_disposition = key == "disposition"
            if in_evidence:
                evidence = None
                continue
            if in_disposition:
                continue
            item[key] = value.strip().strip('"').strip("'")
            continue
        if in_evidence and re.match(r"^\s{6}-\s+workstream:\s*\S+", line):
            # Legacy order is rejected by validation but parsed so the error is useful.
            evidence = {"workstream": stripped.partition(":")[2].strip().strip('"').strip("'")}
            item["evidence"].append(evidence)
        dated = re.match(r"^\s{6}-\s+date:\s*(.*)$", line)
        if in_evidence and dated:
            evidence = {"date": dated.group(1).strip().strip('"').strip("'")}
            item["evidence"].append(evidence)
            continue
        evidence_field = re.match(r"^\s{8}(workstream|burden):\s*(.*)$", line)
        if in_evidence and evidence is not None and evidence_field:
            key, value = evidence_field.groups()
            evidence[key] = value.strip().strip('"').strip("'")
        if in_disposition:
            reason = re.match(r"^\s{6}reason:\s*(.*)$", line)
            if reason:
                item["disposition-reason"] = reason.group(1).strip().strip('"').strip("'")
    return entries


def deterministic_shortcut_candidate_problems(entries: list) -> list:
    required = ("id", "operation-shape", "status")
    problems = []
    seen = set()
    for index, entry in enumerate(entries, 1):
        label = entry.get("id") or f"entry {index}"
        for field in required:
            if not entry.get(field):
                problems.append(f"{label}: missing {field}")
        if entry.get("id") in seen:
            problems.append(f"{label}: duplicate id")
        seen.add(entry.get("id"))
        if entry.get("status") not in SHORTCUT_STATUS_ENUM:
            problems.append(f"{label}: status must be one of {sorted(SHORTCUT_STATUS_ENUM)}")
        evidence_seen = set()
        if not entry.get("evidence"):
            problems.append(f"{label}: requires at least one evidence record")
        for evidence_index, evidence in enumerate(entry.get("evidence", []), 1):
            for field in ("date", "workstream", "burden"):
                if not evidence.get(field):
                    problems.append(f"{label}: evidence {evidence_index} missing {field}")
            value = evidence.get("date", "")
            try:
                datetime.date.fromisoformat(value)
            except ValueError:
                if value:
                    problems.append(f"{label}: evidence {evidence_index} date must be valid YYYY-MM-DD")
            signature = tuple(evidence.get(field, "") for field in ("date", "workstream", "burden"))
            if signature in evidence_seen:
                problems.append(f"{label}: duplicate evidence record {evidence_index}")
            evidence_seen.add(signature)
        if entry.get("status") in SHORTCUT_STATUS_REQUIRES_REASON and not entry.get("disposition-reason"):
            problems.append(f"{label}: {entry.get('status')} status requires disposition reason")
    return problems


def yaml_quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def yaml_unescape(value: str) -> str:
    """Inverse of `yaml_quote`'s escaping, applied to text captured from between quotes. Every
    parse that feeds a later `yaml_quote` write-back MUST unescape, or each parse→write cycle
    doubles the backslashes (the escaping-amplification bug that made import-default-pool
    re-propose already-applied updates forever)."""
    return re.sub(r"\\(.)", r"\1", value)


def save_deterministic_shortcut_candidates(path: str, entries: list) -> None:
    lines = ["# Deterministic shortcut candidates", "", "```yaml"]
    if not entries:
        lines.append("candidates: []")
    else:
        lines.append("candidates:")
        for entry in entries:
            lines.extend([
                f"  - id: {entry['id']}",
                f"    operation-shape: {yaml_quote(entry['operation-shape'])}",
                f"    status: {entry['status']}",
                "    evidence:",
            ])
            for evidence in entry["evidence"]:
                lines.extend([
                    f"      - date: {evidence['date']}",
                    f"        workstream: {evidence['workstream']}",
                    f"        burden: {yaml_quote(evidence['burden'])}",
                ])
            reason = entry.get("disposition-reason", "")
            if reason:
                lines.extend(["    disposition:", f"      reason: {yaml_quote(reason)}"])
    lines.extend(["```", ""])
    open(path, "w").write("\n".join(lines))


def cmd_lint_deterministic_shortcut_candidates(project: Project, _args) -> None:
    path = project.deterministic_shortcut_candidates_path
    if not os.path.exists(path):
        fail("no .corpora/deterministic-shortcut-candidates.md — create it from the kernel schema")
    entries = parse_deterministic_shortcut_candidates(path)
    problems = deterministic_shortcut_candidate_problems(entries)
    if problems:
        print(f"FAIL {path}")
        for problem in problems:
            print(f"  - {problem}")
        sys.exit(1)
    print(f"PASS {path} ({len(entries)} entries)")


def cmd_deterministic_shortcut_candidates(project: Project, _args) -> None:
    path = project.deterministic_shortcut_candidates_path
    if not os.path.exists(path):
        print("deterministic shortcut candidate ledger: absent")
        return
    entries = parse_deterministic_shortcut_candidates(path)
    if deterministic_shortcut_candidate_problems(entries):
        print("deterministic shortcut candidate ledger is invalid; run `lint-deterministic-shortcut-candidates`")
        sys.exit(1)
    if not entries:
        print("deterministic shortcut candidate ledger: empty")
        return
    print("deterministic shortcut candidates:")
    for entry in entries:
        dates = [evidence["date"] for evidence in entry["evidence"]]
        print(f"  - {entry['id']}  status={entry['status']}  sightings={len(dates)}  "
              f"first={min(dates)}  last={max(dates)}")
        print(f"    {entry['operation-shape']}")


def cmd_record_deterministic_shortcut_candidate(project: Project, args) -> None:
    path = project.deterministic_shortcut_candidates_path
    if not os.path.exists(path):
        fail("no .corpora/deterministic-shortcut-candidates.md — create it from the kernel schema")
    entries = parse_deterministic_shortcut_candidates(path)
    problems = deterministic_shortcut_candidate_problems(entries)
    if problems:
        fail("deterministic shortcut candidate ledger is invalid — run `lint-deterministic-shortcut-candidates`")
    entry = next((candidate for candidate in entries if candidate["id"] == args.id), None)
    if entry is None:
        entry = {"id": args.id, "operation-shape": args.operation_shape, "status": "open",
                 "evidence": [], "disposition-reason": ""}
        entries.append(entry)
    elif entry["operation-shape"] != args.operation_shape:
        fail(f"candidate '{args.id}' has a different operation-shape")
    evidence_date = args.date or today()
    try:
        datetime.date.fromisoformat(evidence_date)
    except ValueError:
        fail("--date must be a valid YYYY-MM-DD date")
    evidence = {"date": evidence_date, "workstream": args.workstream, "burden": args.burden}
    if evidence in entry["evidence"]:
        print(f"deterministic shortcut candidate {args.id}: identical evidence already recorded")
        return
    entry["evidence"].append(evidence)
    save_deterministic_shortcut_candidates(path, entries)
    sightings = len(entry["evidence"])
    print(f"deterministic shortcut candidate {args.id}: recorded sighting {sightings}")
    if sightings > 1 or entry["status"] in {"deferred", "denied"}:
        print(f"RESURFACE {args.id}: status={entry['status']} with {sightings} sightings")


def cmd_set_deterministic_shortcut_status(project: Project, args) -> None:
    path = project.deterministic_shortcut_candidates_path
    if not os.path.exists(path):
        fail("no .corpora/deterministic-shortcut-candidates.md — create it from the kernel schema")
    entries = parse_deterministic_shortcut_candidates(path)
    problems = deterministic_shortcut_candidate_problems(entries)
    if problems:
        fail("deterministic shortcut candidate ledger is invalid — run `lint-deterministic-shortcut-candidates`")
    entry = next((candidate for candidate in entries if candidate["id"] == args.id), None)
    if entry is None:
        fail(f"unknown deterministic shortcut candidate '{args.id}'")
    if args.status in SHORTCUT_STATUS_REQUIRES_REASON and not args.reason:
        fail(f"status '{args.status}' requires --reason")
    entry["status"] = args.status
    entry["disposition-reason"] = args.reason or ""
    save_deterministic_shortcut_candidates(path, entries)
    print(f"deterministic shortcut candidate {args.id}: status={args.status}")


# ── screenshot cache: manifest parse / render / commands ────────────────────
# `screens: [{..., variants: [{...}]}]` is two levels of nested lists — same depth as
# `candidates: [{..., evidence: [{...}]}]`, so the parser is modeled on
# `parse_deterministic_shortcut_candidates`, not the flat `parse_state`, which cannot represent it.

def parse_screenshot_manifest(path: str) -> list:
    entries = []
    item = None
    variant = None
    in_screens = False
    in_variants = False
    for raw in open(path):
        line = raw.rstrip()
        stripped = line.strip()
        if in_screens and stripped == "```":
            break
        if stripped in {"screens:", "screens: []"}:
            in_screens = True
            continue
        if not in_screens or not stripped or stripped.startswith(("#", "```")):
            continue
        if re.match(r"^\s{2}-\s+id:\s*", line):
            item = {"components": [], "variants": []}
            entries.append(item)
            item["id"] = stripped.partition(":")[2].strip().strip('"').strip("'")
            in_variants = False
            continue
        if item is None:
            continue
        top = re.match(r"^\s{4}([a-z][a-z0-9-]*):\s*(.*)$", line)
        if top:
            key, value = top.groups()
            in_variants = key == "variants"
            if in_variants:
                variant = None
                continue
            if key == "components":
                value = value.strip()
                if value.startswith("[") and value.endswith("]"):
                    item["components"] = [c.strip() for c in value[1:-1].split(",") if c.strip()]
                else:
                    item["components"] = []
                continue
            item[key] = value.strip().strip('"').strip("'")
            continue
        label_m = re.match(r"^\s{6}-\s+label:\s*(.*)$", line)
        if in_variants and label_m:
            variant = {"label": label_m.group(1).strip().strip('"').strip("'")}
            item["variants"].append(variant)
            continue
        field_m = re.match(r"^\s{8}(path|captured):\s*(.*)$", line)
        if in_variants and variant is not None and field_m:
            key, value = field_m.groups()
            variant[key] = value.strip().strip('"').strip("'")
    return entries


def screenshot_manifest_problems(entries: list, screenshots_dir: str) -> list:
    problems = []
    seen = set()
    referenced = set()
    for index, entry in enumerate(entries, 1):
        label = entry.get("id") or f"entry {index}"
        if not entry.get("id"):
            problems.append(f"{label}: missing id")
        if entry.get("id") in seen:
            problems.append(f"{label}: duplicate id")
        seen.add(entry.get("id"))
        if entry.get("status") not in SCREENSHOT_STATUS_ENUM:
            problems.append(f"{label}: status must be one of {sorted(SCREENSHOT_STATUS_ENUM)}")
        if not entry.get("last-touched"):
            problems.append(f"{label}: missing last-touched")
        if not entry.get("variants"):
            problems.append(f"{label}: requires at least one variant")
        for vindex, variant in enumerate(entry.get("variants", []), 1):
            vlabel = f"{label} variant {vindex}"
            if not variant.get("label"):
                problems.append(f"{vlabel}: missing label")
            path = variant.get("path", "")
            if not path:
                problems.append(f"{vlabel}: missing path")
            else:
                referenced.add(path)
                if not os.path.exists(os.path.join(screenshots_dir, path)):
                    problems.append(f"{vlabel}: path '{path}' does not exist on disk")
            captured = variant.get("captured", "")
            if not captured:
                problems.append(f"{vlabel}: missing captured date")
            else:
                try:
                    datetime.date.fromisoformat(captured)
                except ValueError:
                    problems.append(f"{vlabel}: captured must be valid YYYY-MM-DD")
    if os.path.isdir(screenshots_dir):
        for root, _dirs, files in os.walk(screenshots_dir):
            for name in files:
                if not name.endswith(".png"):
                    continue
                rel = os.path.relpath(os.path.join(root, name), screenshots_dir)
                if rel not in referenced:
                    problems.append(f"orphaned image not in manifest: {rel}")
    return problems


def save_screenshot_manifest(path: str, entries: list) -> None:
    lines = ["# Screenshot manifest", "", "```yaml"]
    if not entries:
        lines.append("screens: []")
    else:
        lines.append("screens:")
        for entry in entries:
            lines.extend([
                f"  - id: {entry['id']}",
                f"    components: [{', '.join(entry.get('components', []))}]",
                f"    status: {entry['status']}",
                f"    last-touched: {entry['last-touched']}",
                "    variants:",
            ])
            for variant in entry["variants"]:
                lines.extend([
                    f"      - label: {variant['label']}",
                    f"        path: {variant['path']}",
                    f"        captured: {variant['captured']}",
                ])
    lines.extend(["```", ""])
    open(path, "w").write("\n".join(lines))


def cmd_lint_screenshots(project: Project, _args) -> None:
    path = project.screenshot_manifest_path
    if not os.path.exists(path):
        fail("no .corpora/screenshots/manifest.md — create it (e.g. via bootstrap Phase 2's "
             "seeding step) before linting")
    entries = parse_screenshot_manifest(path)
    problems = screenshot_manifest_problems(entries, project.screenshots_dir)
    if problems:
        print(f"FAIL {path}")
        for problem in problems:
            print(f"  - {problem}")
        sys.exit(1)
    print(f"PASS {path} ({len(entries)} screens)")


def cmd_screenshot_status(project: Project, _args) -> None:
    path = project.screenshot_manifest_path
    if not os.path.exists(path):
        print("screenshot manifest: absent")
        return
    entries = parse_screenshot_manifest(path)
    if screenshot_manifest_problems(entries, project.screenshots_dir):
        print("screenshot manifest is invalid; run `lint-screenshots`")
        sys.exit(1)
    if not entries:
        print("screenshot manifest: empty")
        return
    current = sorted((e for e in entries if e.get("status") == "current"), key=lambda e: e["id"])
    stale = sorted((e for e in entries if e.get("status") == "stale"), key=lambda e: e["id"])
    print(f"screenshot manifest: {len(current)} current, {len(stale)} stale")
    if current:
        print("  current:")
        for entry in current:
            print(f"    - {entry['id']}  components=[{', '.join(entry.get('components', []))}]")
    if stale:
        print("  stale:")
        for entry in stale:
            print(f"    - {entry['id']}  components=[{', '.join(entry.get('components', []))}]")


def cmd_screenshot_lookup(project: Project, args) -> None:
    path = project.screenshot_manifest_path
    if not os.path.exists(path):
        print("screenshot manifest: absent")
        return
    entries = parse_screenshot_manifest(path)
    if screenshot_manifest_problems(entries, project.screenshots_dir):
        print("screenshot manifest is invalid; run `lint-screenshots`")
        sys.exit(1)
    matches = [e for e in entries if args.component in e.get("components", [])]
    if not matches:
        print(f"no screens tagged with component '{args.component}'")
        return
    print(f"screens showing '{args.component}':")
    for entry in matches:
        for variant in entry.get("variants", []):
            print(f"  - {entry['id']} ({variant['label']}): {variant['path']}  status={entry['status']}")


def cmd_screenshot_record(project: Project, args) -> None:
    path = project.screenshot_manifest_path
    entries = parse_screenshot_manifest(path) if os.path.exists(path) else []
    entry = next((e for e in entries if e["id"] == args.screen), None)
    if entry is None:
        entry = {"id": args.screen, "components": [], "status": "current",
                  "last-touched": today(), "variants": []}
        entries.append(entry)
    entry["components"] = _ids(args.components)
    entry["status"] = "current"
    entry["last-touched"] = today()
    variant = next((v for v in entry["variants"] if v["label"] == args.variant), None)
    if variant is None:
        entry["variants"].append({"label": args.variant, "path": args.path, "captured": today()})
    else:
        variant["path"] = args.path
        variant["captured"] = today()
    os.makedirs(project.screenshots_dir, exist_ok=True)
    save_screenshot_manifest(path, entries)
    print(f"screenshot recorded: {args.screen}/{args.variant} -> {args.path} "
          f"(status=current, components=[{', '.join(entry['components'])}])")


def cmd_screenshot_mark_stale(project: Project, args) -> None:
    path = project.screenshot_manifest_path
    if not os.path.exists(path):
        print("screenshot manifest: absent — nothing to mark stale")
        return
    entries = parse_screenshot_manifest(path)
    if screenshot_manifest_problems(entries, project.screenshots_dir):
        fail("screenshot manifest is invalid — run `lint-screenshots`")
    direct = set(_ids(args.screens))
    ripple_components = set(_ids(args.components))
    invalidated = []
    for entry in entries:
        rippled = bool(ripple_components & set(entry.get("components", [])))
        if entry["id"] in direct or rippled:
            if entry.get("status") != "stale":
                invalidated.append(entry["id"])
            entry["status"] = "stale"
    save_screenshot_manifest(path, entries)
    print(f"marked stale: {', '.join(invalidated) if invalidated else 'none'}")


def cmd_retro_done(project: Project, args) -> None:
    state = load(project)
    for c in state["counters"]:
        if c["domain"] == args.domain:
            files = project.domain_files()
            if args.domain in files:
                tokens = est_tokens(files[args.domain])
                p, k, conv = count_entries(files[args.domain])
            else:
                tokens = c["working-file-tokens"]
                p, k, conv = (c.get("principles-at-baseline", 0), c.get("kills-at-baseline", 0),
                               c.get("conventions-at-baseline", 0))
            c.update({"since": today(), "ratified": 0, "killed": 0, "graduated": 0, "gate-violations": 0,
                      "working-file-tokens": tokens, "baseline-tokens": tokens,
                      "principles-at-baseline": p, "kills-at-baseline": k, "conventions-at-baseline": conv})
            save(project, state)
            print(f"reset counters for {args.domain}; baseline-tokens={tokens}, principles={p}, kills={k}")
            return
    fail(f"no counters for domain '{args.domain}'")


def cmd_sync_done(project: Project, _args) -> None:
    state = load(project)
    state["library-drift"]["since-last-sync"] = 0
    save(project, state)
    print("library-drift reset to 0")


def skill_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ── monorepo root resolution: which corpora root governs a given file ────────────────────────
#
# proposals/domain-repo-import.md, "monorepo" section: a monorepo may have more than one
# `.corpora/config.md` (an app-scoped one, or a shared app-less root). Resolution is nearest-
# ancestor walk from a task's actual touched files up toward the filesystem root, stopping at the
# first `.corpora/config.md` found — the same model `tsconfig.json`/`package.json` already use. A
# task whose touched files resolve to more than one root is the mechanical split signal: one unit
# of work per root, not a single spawn straddling both.

def has_root_config(directory: str) -> bool:
    """A corpora root carries `.corpora/config.md` (standard) or `corpora/config.md` (legacy)."""
    return any(os.path.exists(os.path.join(directory, base, "config.md"))
               for base in (".corpora", "corpora"))


def find_root_config(start_path: str) -> str:
    """Nearest-ancestor walk from `start_path` up toward the filesystem root. Returns the
    directory containing the first corpora config found, or "" if none exists above it."""
    current = os.path.abspath(start_path)
    if not os.path.isdir(current):
        current = os.path.dirname(current)
    while True:
        if has_root_config(current):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            return ""
        current = parent


def cmd_resolve_root(args) -> None:
    if args.name:
        cmd_resolve_root_by_name(args)
        return
    if not args.file:
        fail("resolve-root requires --file (upward, from a touched file) or --name (downward, "
             "by a root's declared or directory name)")
    root = find_root_config(args.file)
    if not root:
        print(f"no corpora root found above {args.file}")
        return
    print(root)


def cmd_check_root_boundary(args) -> None:
    files = _ids(args.files)
    if not files:
        fail("--files requires at least one comma-separated file path")
    by_root: dict = {}
    unresolved = []
    for f in files:
        root = find_root_config(f)
        if root:
            by_root.setdefault(root, []).append(f)
        else:
            unresolved.append(f)
    if unresolved:
        print("no corpora root found for: " + ", ".join(unresolved))
    if len(by_root) > 1:
        print("error: task spans multiple corpora roots — split into one unit of work per root:",
              file=sys.stderr)
        for root, root_files in sorted(by_root.items()):
            print(f"  {root}: {', '.join(root_files)}", file=sys.stderr)
        sys.exit(2)
    if by_root:
        (root,) = by_root.keys()
        print(f"check-root-boundary: ok — single root {root}")
    else:
        print("check-root-boundary: ok — no touched file resolves to a corpora root")


# ── named root discovery: dispatching into a formalized section of the same project ──────────
#
# The above resolves a root from a file already known to touch it — upward, from inside that
# root's own tree. Dispatching *into* a sibling section deliberately (kernel.md, "a task spanning
# two corpora roots is two units of work, one per root") needs the opposite direction: given no
# file yet, which named roots exist to target at all. Purely mechanical — no judgment about
# whether to dispatch, only about resolving a name to a path once the decision is already made.

ROOT_WALK_SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "dist", "build", "__pycache__",
                        ".worktrees", "worktrees", ".next", "target"}


def find_all_root_configs(search_from: str) -> list:
    """Downward walk from `search_from`, collecting every directory containing a
    `.corpora/config.md` — the counterpart to `find_root_config`'s upward walk. Skips common
    vendor/build directories so this stays fast in a real repo; does not descend into a found
    root's own `.corpora/` directory (a root's config never nests another root)."""
    search_from = os.path.abspath(search_from)
    found = []
    for dirpath, dirnames, _filenames in os.walk(search_from):
        dirnames[:] = [d for d in dirnames if d not in ROOT_WALK_SKIP_DIRS and not d.startswith(".")]
        if has_root_config(dirpath):
            found.append(dirpath)
            dirnames[:] = [d for d in dirnames if d != "corpora"]
    return sorted(found)


def root_name_for(root_dir: str) -> str:
    """A root's declared `name:` (`## project-shape` in its config.md) if present, else its
    directory's own basename — every root is nameable without requiring the field."""
    shape = parse_config_shape(Project(root_dir).config_path)
    return shape.get("name") or os.path.basename(root_dir.rstrip(os.sep)) or root_dir


def cmd_list_roots(args) -> None:
    roots = find_all_root_configs(args.search_from)
    if not roots:
        print(f"no corpora roots found under {os.path.abspath(args.search_from)}")
        return
    for root in roots:
        print(f"{root_name_for(root)}: {root}")


def cmd_resolve_root_by_name(args) -> None:
    roots = find_all_root_configs(args.search_from)
    matches = [r for r in roots if root_name_for(r) == args.name]
    if not matches:
        available = ", ".join(root_name_for(r) for r in roots) or "none"
        fail(f"no corpora root named '{args.name}' under {os.path.abspath(args.search_from)} — "
             f"available: {available}")
    if len(matches) > 1:
        fail(f"'{args.name}' is ambiguous — matches {len(matches)} roots under "
             f"{os.path.abspath(args.search_from)}: {', '.join(matches)}. Disambiguate with "
             "--root/--for-file and the exact path instead.")
    print(matches[0])


# ── domain selection API: frontmatter, manifest, select, check-composition ──────────────────
#
# An external process layer selects domains by querying data instead of reading
# preambles — see `kernel.md`, "Spawns: stance + composition." Every load condition previously
# stated in prose is machine-evaluable already; this section is the seam.

FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)


def _parse_inline_list(value: str):
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        return [x.strip() for x in inner.split(",")] if inner else []
    return [value] if value else []


def _parse_flat_list(lines, *, item_key="id", list_fields=(), coerce_int=False, strip_quotes=False):
    """Parse the body lines of a flat fenced-YAML list into a list of dicts — the shared core of
    corpus.py's hand-rolled ledger parsers (parse_state's list sections, parse_queue's sections,
    parse_audit_entries). The caller owns fence extraction, section detection, header/scalar lines,
    dict-keying of the result, and any indent-scoping; this owns only item collection and field
    splitting, so nested-list schemas (screenshots, candidates, import) that cannot flatten to one
    dict per item stay on their own parsers.

    An item opens with `- <item_key>:` (or, when item_key is None, any `- ` line); subsequent
    `key: value` lines attach to the current item, the opening line's own field included. Fields
    named in list_fields parse an inline `[a, b]` via _parse_inline_list; coerce_int turns a bare
    integer value into an int; strip_quotes removes surrounding single/double quotes. Blank,
    comment (`#`), and fence (```` ``` ````) lines are skipped."""
    items = []
    item = None
    for raw in lines:
        stripped = raw.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("```"):
            continue
        starts_item = (stripped.startswith("- ") if item_key is None
                       else bool(re.match(rf"-\s+{re.escape(item_key)}:", stripped)))
        if starts_item:
            item = {}
            items.append(item)
            stripped = re.sub(r"^-\s+", "", stripped)
        if item is None or ":" not in stripped:
            continue
        key, _, value = stripped.partition(":")
        key = key.strip()
        value = value.strip()
        if strip_quotes:
            value = value.strip('"').strip("'")
        if key in list_fields:
            value = _parse_inline_list(value)
        elif coerce_int and re.fullmatch(r"-?\d+", value):
            value = int(value)
        item[key] = value
    return items


def parse_domain_frontmatter(path: str):
    """Parse a domain file's frontmatter block. Returns None if the file has none (not yet
    migrated to the schema in `kernel.md`, "Spawns: stance + composition")."""
    text = open(path).read()
    m = FRONTMATTER_RE.match(text)
    if not m:
        return None
    data = {"subject": None, "posture": None, "applies-when": [], "units-of-work": [], "universal": False}
    lines = m.group(1).split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("subject:"):
            data["subject"] = line.split(":", 1)[1].strip()
        elif line.startswith("posture:"):
            data["posture"] = line.split(":", 1)[1].strip()
        elif line.startswith("universal:"):
            data["universal"] = line.split(":", 1)[1].strip().lower() == "true"
        elif line.startswith("units-of-work:"):
            data["units-of-work"] = _parse_inline_list(line.split(":", 1)[1])
        elif re.fullmatch(r"applies-when:\s*", line):
            i += 1
            while i < len(lines) and lines[i].startswith("  - "):
                key, _, val = lines[i][4:].partition(":")
                data["applies-when"].append((key.strip(), _parse_inline_list(val)
                                              if val.strip().startswith("[") else val.strip()))
                i += 1
            continue
        i += 1
    return data


def parse_domain_conditions(path: str) -> list:
    """Extract `id` + `condition` (only — never `rule`/`reason`) for every active principle, so a
    routing layer can see when a principle applies without seeing what it says."""
    text = open(path).read()
    m = FRONTMATTER_RE.match(text)
    body = text[m.end():] if m else text
    section = None
    current_id = None
    conditions = []
    for raw in body.split("\n"):
        stripped = raw.strip()
        if re.fullmatch(r"conventions:", stripped):
            section = "c"
            continue
        if re.fullmatch(r"principles:", stripped):
            section = "p"
            continue
        if re.fullmatch(r"killed:", stripped):
            section = "k"
            continue
        if section != "p":
            continue
        m_id = re.match(r"-\s*id:\s*(\S+)", stripped)
        if m_id:
            current_id = m_id.group(1)
            continue
        m_cond = re.match(r'condition:\s*"(.*)"\s*$', stripped)
        if m_cond and current_id:
            conditions.append({"id": current_id, "condition": m_cond.group(1)})
            current_id = None
    return conditions


def parse_domain_conventions(path: str) -> list:
    """Extract every `conventions:` entry's `id` plus which of `rule`/`reason`/`condition` are
    present, for `lint-domains`'s shape check and `manifest`'s id listing. A convention is
    unconditioned by definition (kernel.md, 'Retired principle — graduated to a convention') — a
    `condition` field here is a shape error, not a valid variant of the schema."""
    text = open(path).read()
    m = FRONTMATTER_RE.match(text)
    body = text[m.end():] if m else text
    section = None
    current = None
    entries = []
    for raw in body.split("\n"):
        stripped = raw.strip()
        if re.fullmatch(r"conventions:", stripped):
            section = "c"
            current = None
            continue
        if re.fullmatch(r"principles:", stripped):
            section = "p"
            current = None
            continue
        if re.fullmatch(r"killed:", stripped):
            section = "k"
            current = None
            continue
        if section != "c":
            continue
        m_id = re.match(r"-\s*id:\s*(\S+)", stripped)
        if m_id:
            current = {"id": m_id.group(1), "rule": False, "reason": False, "condition": False}
            entries.append(current)
            continue
        if current is None:
            continue
        for field in ("rule", "reason", "condition"):
            if re.match(rf"{field}:\s*\S", stripped):
                current[field] = True
    return entries


def domain_lint_problems(domains_dir: str) -> list:
    problems = []
    for name in sorted(os.listdir(domains_dir)):
        if not name.endswith(".md") or name == "audit.md":
            continue
        domain = name[:-3]
        fm = parse_domain_frontmatter(os.path.join(domains_dir, name))
        if fm is None:
            problems.append(f"{domain}: no frontmatter block")
            continue
        if fm["subject"] not in DOMAIN_SUBJECT_ENUM:
            problems.append(f"{domain}: subject '{fm['subject']}' not in {sorted(DOMAIN_SUBJECT_ENUM)}")
        if fm["posture"] not in DOMAIN_POSTURE_ENUM:
            problems.append(f"{domain}: posture '{fm['posture']}' not in {sorted(DOMAIN_POSTURE_ENUM)}")
        if not fm["universal"] and not fm["units-of-work"]:
            problems.append(f"{domain}: units-of-work is empty and universal is not true")
        for key, _ in fm["applies-when"]:
            if key not in CONFIG_SHAPE_FIELDS:
                problems.append(f"{domain}: applies-when references unknown config field '{key}'")
        for conv in parse_domain_conventions(os.path.join(domains_dir, name)):
            label = conv["id"] or "(no id)"
            if not conv["rule"]:
                problems.append(f"{domain}: convention '{label}' missing rule")
            if not conv["reason"]:
                problems.append(f"{domain}: convention '{label}' missing reason")
            if conv["condition"]:
                problems.append(f"{domain}: convention '{label}' has a condition — "
                                 "conventions are unconditioned by definition")
    return problems


def cmd_lint_domains(args) -> None:
    problems = domain_lint_problems(args.domains_dir)
    if problems:
        for p in problems:
            print(f"error: {p}", file=sys.stderr)
        sys.exit(2)
    print(f"lint-domains: ok ({args.domains_dir})")


def parse_config_shape(config_path: str) -> dict:
    if not os.path.exists(config_path):
        return {}
    text = open(config_path).read()
    m = re.search(r"^## project-shape\s*\n(.*?)(?=\n## |\Z)", text, re.DOTALL | re.MULTILINE)
    if not m:
        return {}
    shape = {}
    for line in m.group(1).split("\n"):
        line = line.strip()
        if not line or line.startswith("<!--") or line.startswith("see:"):
            continue
        mm = re.match(r"([\w-]+):\s*(.*)$", line)
        if mm:
            shape[mm.group(1)] = mm.group(2).strip()
    return shape


def _normalize_shape_value(v: str) -> str:
    return re.sub(r"[^a-z0-9]", "", v.lower())


def applies_when_matches(applies_when: list, shape: dict) -> bool:
    for key, val in applies_when:
        actual = _normalize_shape_value(shape.get(key, ""))
        if val == "not-none":
            if actual in ("", "none"):
                return False
            continue
        options = val if isinstance(val, list) else [val]
        if actual not in {_normalize_shape_value(o) for o in options}:
            return False
    return True


def select_domains(sources: dict, shape: dict, unit_of_work: str) -> list:
    selected = []
    for name, path in sources.items():
        fm = parse_domain_frontmatter(path)
        if fm is None:
            continue
        if fm["universal"]:
            selected.append(name)
            continue
        if unit_of_work not in fm["units-of-work"]:
            continue
        if not applies_when_matches(fm["applies-when"], shape):
            continue
        selected.append(name)
    return sorted(selected)


def known_units_of_work(sources: dict) -> set:
    """Every unit-of-work value any non-universal domain in this pool declares — the vocabulary a
    `select` caller's own `--unit-of-work` is checked against, so an unrecognized value (a typo, a
    stale vocabulary from another engine) is reported instead of silently degrading to just the
    universal domains with no signal that anything was missed."""
    known = set()
    for path in sources.values():
        fm = parse_domain_frontmatter(path)
        if fm is not None:
            known.update(fm["units-of-work"])
    return known


def cmd_select(project: "Project", args) -> None:
    config_path = args.config or project.config_path
    shape = parse_config_shape(config_path)
    sources = project.domain_files()
    selected = select_domains(sources, shape, args.unit_of_work)
    warnings = []
    known = known_units_of_work(sources)
    if args.unit_of_work not in known:
        warnings.append(
            f"unit-of-work '{args.unit_of_work}' matches no domain in this pool — composition is "
            f"limited to universal domains only (known values: {', '.join(sorted(known))})"
        )
    if args.json:
        import json
        print(json.dumps({"unit-of-work": args.unit_of_work, "domains": selected, "warnings": warnings}))
    else:
        print(", ".join(selected) if selected else "(no domains selected)")
        for warning in warnings:
            print(f"warning: {warning}", file=sys.stderr)


def cmd_manifest(project: "Project", args) -> None:
    sources = project.domain_files()
    entries = []
    for name in sorted(sources):
        path = sources[name]
        fm = parse_domain_frontmatter(path)
        if fm is None:
            continue
        entries.append({
            "name": name,
            "subject": fm["subject"],
            "posture": fm["posture"],
            "applies_when": [{k: v} for k, v in fm["applies-when"]],
            "units_of_work": fm["units-of-work"],
            "universal": fm["universal"],
            "conditions": parse_domain_conditions(path),
            "conventions": [c["id"] for c in parse_domain_conventions(path)],
        })
    if args.json:
        import json
        print(json.dumps({"domains": entries}, indent=2))
    else:
        for e in entries:
            print(f"{e['name']}: subject={e['subject']} posture={e['posture']} "
                  f"units-of-work={e['units_of_work']} universal={e['universal']}")


def check_composition_problems(named_frontmatter: list) -> list:
    """named_frontmatter: list of (name, frontmatter-or-None). Fails on any `posture: generative`
    domain (kernel.md, 'The hard line' — no legitimate instance exists today) and on mixed
    coding/design subjects in one composition (subject separation), ignoring universal domains. A
    domain with no frontmatter (e.g. a project-only domain born fresh at the ratify gate, not yet
    carrying the schema) is not itself an error here — it contributes no subject and is skipped;
    `lint-domains` is the place that flags missing frontmatter as a structural problem."""
    problems = []
    subjects = set()
    for name, fm in named_frontmatter:
        if fm is None:
            continue
        if fm["posture"] == "generative":
            problems.append(f"{name}: posture 'generative' is a ratify-gate rejection, not a "
                             "valid domain to compose (kernel.md, 'The hard line')")
        if not fm["universal"]:
            subjects.add(fm["subject"])
    if len(subjects - {None}) > 1:
        problems.append(f"mixed subjects in one composition: {sorted(subjects - {None})}")
    return problems


def cmd_check_composition(project: "Project", args) -> None:
    domains = _ids(args.domains)
    if not domains:
        fail("--domains requires at least one comma-separated domain name")
    sources = project.domain_files()
    named = [(d, parse_domain_frontmatter(sources[d]) if d in sources else None) for d in domains]
    problems = check_composition_problems(named)
    if problems:
        for p in problems:
            print(f"error: {p}", file=sys.stderr)
        sys.exit(2)
    print(f"check-composition: ok ({', '.join(domains)})")


# ── import: propose principles/conventions from another domains-dir as candidates ────────────
#
# kernel.md, "Project corpora"/proposals/domain-repo-import.md §3: an import is a new *producer*
# of candidates, structurally the same relationship discovery-agent.md/session-harvest-agent.md
# already have to a candidates file and the gate — the operator still browses and picks, per
# principle, and the gate still ratifies. This never writes into a domain working file directly.

def collect_domain_ids(path: str) -> set:
    """Every id already present in a domain working file — conventions, principles, and killed
    entries alike — so import-candidate can refuse a collision regardless of which section an id
    already occupies."""
    ids = set()
    for raw in open(path):
        m = re.match(r"\s*-\s*id:\s*(\S+)", raw)
        if m:
            ids.add(m.group(1))
    return ids


def parse_domain_section_full(path: str, section_name: str) -> dict:
    """Extract every entry's full `rule`/`condition`/`reason` (whichever are present) from one
    section (`principles` or `conventions`) of a domain working file, keyed by `id` — the same
    tolerant flat-scan style as `parse_domain_conditions`/`parse_domain_conventions`, extended to
    capture `rule`/`reason` too since import-candidate needs the whole entry, not just its id."""
    text = open(path).read()
    m = FRONTMATTER_RE.match(text)
    body = text[m.end():] if m else text
    section = None
    current = None
    entries = {}
    for raw in body.split("\n"):
        stripped = raw.strip()
        if re.fullmatch(r"conventions:", stripped):
            section, current = "conventions", None
            continue
        if re.fullmatch(r"principles:", stripped):
            section, current = "principles", None
            continue
        if re.fullmatch(r"killed:", stripped):
            section, current = "killed", None
            continue
        if section != section_name:
            continue
        m_id = re.match(r"-\s*id:\s*(\S+)", stripped)
        if m_id:
            current = m_id.group(1)
            entries[current] = {}
            continue
        if current is None:
            continue
        for field in ("rule", "condition", "reason", "reason_killed"):
            fm_field = re.match(rf'{field}:\s*"(.*)"\s*$', stripped)
            if fm_field:
                entries[current][field] = yaml_unescape(fm_field.group(1))
        m_kill_type = re.match(r"kill_type:\s*(\S+)", stripped)
        if m_kill_type:
            entries[current]["kill_type"] = m_kill_type.group(1)
        m_see_also = re.match(r"see-also:\s*(\S.*)$", stripped)
        if m_see_also:
            entries[current]["see-also"] = m_see_also.group(1).strip()
    return entries


def find_import_entry(source_dir: str, domain: str, entry_id: str) -> tuple:
    """Locate `entry_id` in `source_dir/<domain>.md`, principles first then conventions. Returns
    (kind, fields) where kind is "principle" or "convention", or fails if not found in either."""
    path = os.path.join(source_dir, f"{domain}.md")
    if not os.path.exists(path):
        fail(f"no domain '{domain}' under {source_dir}")
    principles = parse_domain_section_full(path, "principles")
    if entry_id in principles:
        return "principle", principles[entry_id]
    conventions = parse_domain_section_full(path, "conventions")
    if entry_id in conventions:
        return "convention", conventions[entry_id]
    fail(f"no principle or convention '{entry_id}' in {path}")


def source_originally_ratified(source_dir: str, entry_id: str) -> str:
    """Best-effort: the source's own audit.md provenance date for this id, if the source layer has
    one. Returns "" when unavailable — never fabricated."""
    audit_path = os.path.join(source_dir, "audit.md")
    if not os.path.exists(audit_path):
        return ""
    entries = parse_audit_entries(audit_path)
    entry = entries.get(entry_id)
    return entry.get("provenance", "").strip('"') if entry else ""


def append_import_candidate(target_path: str, fields: dict) -> None:
    lines = []
    lines.append(f"- id: {fields['id']}")
    lines.append(f"  rule: {yaml_quote(fields['rule'])}")
    if "condition" in fields:
        lines.append(f"  condition: {yaml_quote(fields['condition'])}")
    lines.append(f"  reason: {yaml_quote(fields['reason'])}")
    lines.append(f"  domains: [{fields['domain']}]")
    lines.append("  kind: judgment")
    if fields.get("change"):
        lines.append(f"  change: {fields['change']}")
    if fields.get("kill-type"):
        lines.append(f"  kill-type: {fields['kill-type']}")
    if fields.get("from-domain"):
        lines.append(f"  from-domain: {fields['from-domain']}")
    if fields.get("successor"):
        lines.append(f"  successor: {fields['successor']}")
    lines.append("  provenance:")
    lines.append("    imported-from:")
    lines.append(f"      source: {yaml_quote(fields['source'])}")
    lines.append(f"      domain: {fields['source-domain']}")
    if fields.get("source-id") and fields["source-id"] != fields["id"]:
        lines.append(f"      id: {fields['source-id']}")
    if fields.get("originally-ratified"):
        lines.append(f"      originally-ratified: {yaml_quote(fields['originally-ratified'])}")
    lines.append(f"    extracted: {today()}")
    block = "\n".join(lines) + "\n"

    if os.path.exists(target_path):
        text = open(target_path).read()
    else:
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        text = "# Import candidates\n\nProposed at the ratify gate like any other candidate " \
               "(kernel.md, \"Domain assignment at the gate\") — the operator still browses and " \
               "picks the destination domain per entry.\n\n```yaml\ncandidates:\n```\n"
    if "```yaml" not in text or "candidates:" not in text:
        fail(f"{target_path} does not have a recognizable 'candidates:' block — fix by hand")
    before, _, rest = text.partition("```yaml")
    fence_body, _, after = rest.partition("\n```")
    if fence_body.rstrip().endswith("candidates: []"):
        fence_body = fence_body.rstrip()[: -len("candidates: []")] + "candidates:\n" + block.rstrip("\n")
    else:
        fence_body = fence_body.rstrip("\n") + "\n" + block.rstrip("\n")
    text = before + "```yaml" + fence_body + "\n```" + after
    open(target_path, "w").write(text)


# ── add-principle / ratify-import-candidate: scripted write-back, no hand edits ─────────────────
#
# Both write a principle (or convention) into a domain working file and its matching audit.md
# provenance entry, then call record_gate_core so the ledger and the files can never drift apart
# the way a hand-edit-then-separately-remember-record-gate sequence can. `add-principle` is the
# general path (freshly authored or mined content); `ratify-import-candidate` is the same write,
# sourced from an entry `import-candidate`/`import-default-pool` already queued in
# .corpora/import-candidates.md, consuming it from that file on success.

def format_principle_block(fields: dict) -> str:
    lines = [f"- id: {fields['id']}", f"  rule: {yaml_quote(fields['rule'])}",
              f"  condition: {yaml_quote(fields['condition'])}",
              f"  reason: {yaml_quote(fields['reason'])}"]
    if fields.get("see-also"):
        lines.append(f"  see-also: {fields['see-also']}")
    return "\n".join(lines) + "\n"


def remove_live_entry(domain_path: str, entry_id: str) -> bool:
    """Remove one entry block from the live part of a domain working file — the principles: or
    conventions: section, wherever the id sits. The trailing `killed:` marker is only the
    section anchor; kill records themselves live in audit.md's kill log."""
    text = open(domain_path).read()
    idx = text.find("\nkilled:")
    if idx == -1:
        return False
    head, tail = text[:idx], text[idx:]
    blocks = re.split(r"\n\s*\n", head)
    kept, removed = [], False
    for block in blocks:
        if re.search(rf"^\s*-\s*id:\s*{re.escape(entry_id)}\s*$", block, re.MULTILINE):
            removed = True
            continue
        kept.append(block)
    if not removed:
        return False
    open(domain_path, "w").write("\n\n".join(kept) + tail)
    return True


KILL_LOG_HEADER = ("\n# Kill log — killed principles' full records, one flat list. Consulted at "
                   "ratify/retrospective\n# time (audit load); never in a spawn's working context. "
                   "Working files keep an empty `killed:`\n# marker purely as a structural anchor.\n")


def append_audit_kill_entry(audit_path: str, block: str) -> None:
    """Append a fully-formed kill record to the audit file's kill-log fence (a `kills:` yaml
    list after the script-maintained counters block), scaffolding the section if the audit
    doesn't have one yet — the audit-side mirror of `append_domain_entry`."""
    _ensure_audit_scaffold(audit_path)
    text = open(audit_path).read()
    idx = text.find("\nkills:")
    if idx == -1:
        text = text.rstrip("\n") + "\n" + KILL_LOG_HEADER + "\n```yaml\nkills:\n```\n"
        idx = text.find("\nkills:")
    fence_idx = text.find("```", idx)
    if fence_idx == -1:
        fail(f"{audit_path} has no closing fence after 'kills:'")
    head, tail = text[:fence_idx], text[fence_idx:]
    open(audit_path, "w").write(head.rstrip("\n") + "\n\n" + block.rstrip("\n") + "\n" + tail)


def format_audit_kill_block(fields: dict) -> str:
    lines = [f"- id: {fields['id']}", f"  domain: {fields['domain']}",
             f"  rule: {yaml_quote(fields['rule'])}",
             f"  kill_type: {fields['kill_type']}",
             f"  reason_killed: {yaml_quote(fields['reason_killed'])}",
             f"  killed: {today()}"]
    return "\n".join(lines) + "\n"


def parse_audit_histories(audit_path: str) -> dict:
    """Reorg events from the hand-maintained `provenance:` list's `history:` sublists:
    {id: {"domain": <entry's current domain>, "events": [{"type": t, "successor": s?}]}}.
    Only `type:` and the machine-readable `successor:` field are read per event — `date`/`reason`
    stay prose. This is the wire format for import-default-pool's move/supersede sync: a `moved`
    event's destination is the entry's own current `domain:` field; a `consolidated`/`generalized`
    event names the id that absorbed it in `successor:`. Section boundaries mirror
    `parse_audit_entries`."""
    if not os.path.exists(audit_path):
        return {}
    section_boundaries = {"counters:", "efficacy:", "co-occurrence:", "library-drift:", "kills:"}
    in_provenance = False
    entries = {}
    current = None
    in_history = False
    event = None
    for raw in open(audit_path):
        line = raw.rstrip("\n")
        stripped = line.strip()
        if re.fullmatch(r"provenance:", stripped):
            in_provenance = True
            continue
        if in_provenance and stripped in section_boundaries and not line.startswith(" "):
            in_provenance = False
            continue
        if not in_provenance:
            continue
        m_id = re.match(r"-\s*id:\s*(\S+)$", stripped)
        if m_id and len(line) - len(line.lstrip()) <= 2:
            current = {"domain": "", "events": []}
            entries[m_id.group(1)] = current
            in_history = False
            event = None
            continue
        if current is None:
            continue
        m_domain = re.match(r"domain:\s*(\S+)$", stripped)
        if m_domain and not in_history:
            current["domain"] = m_domain.group(1)
            continue
        if re.fullmatch(r"history:", stripped):
            in_history = True
            continue
        if in_history:
            if re.match(r"-\s*date:", stripped):
                event = {}
                current["events"].append(event)
            elif event is not None:
                m_field = re.match(r"(type|successor):\s*(\S+)$", stripped)
                if m_field:
                    event[m_field.group(1)] = m_field.group(2)
    return {eid: rec for eid, rec in entries.items() if rec["events"]}


def parse_audit_kills(audit_path: str) -> dict:
    """Full kill records from an audit file's kill log (the `kills:` fence), keyed by id.
    The read side of the kill-log relocation: import-default-pool's kill sync and the
    ratify-time collision guard both consult this instead of working-file killed: sections."""
    if not os.path.exists(audit_path):
        return {}
    text = open(audit_path).read()
    idx = text.find("\nkills:")
    if idx == -1:
        return {}
    fence_idx = text.find("```", idx)
    section = text[idx:fence_idx if fence_idx != -1 else len(text)]
    entries = {}
    current = None
    for raw in section.split("\n"):
        stripped = raw.strip()
        m_id = re.match(r"-\s*id:\s*(\S+)", stripped)
        if m_id:
            current = {}
            entries[m_id.group(1)] = current
            continue
        if current is None:
            continue
        m_field = re.match(r"(domain|rule|kill_type|reason_killed|killed):\s*(.*)$", stripped)
        if m_field:
            current[m_field.group(1)] = yaml_unescape(m_field.group(2).strip().strip('"'))
    return entries


def audit_kill_ids(audit_path: str) -> set:
    """Ids in the audit file's kill log — the re-proposal/collision guard now that working
    files no longer carry kill entries."""
    if not os.path.exists(audit_path):
        return set()
    text = open(audit_path).read()
    idx = text.find("\nkills:")
    if idx == -1:
        return set()
    fence_idx = text.find("```", idx)
    section = text[idx:fence_idx if fence_idx != -1 else len(text)]
    return set(re.findall(r"^\s*-\s*id:\s*(\S+)", section, re.MULTILINE))


def append_domain_entry(domain_path: str, block: str) -> None:
    """Append a fully-formed principle entry to a domain working file's `principles:` list,
    immediately before `killed:` — every domain file's fixed section order (optional
    `conventions:`, then `principles:`, then always-last `killed:`) means that anchor holds
    regardless of how many principles already sit there. Conventions are out of scope here: a
    convention is graduated from an existing ratified principle (kernel.md, "Retired principle —
    graduated to a convention"), a distinct move-not-append operation with its own counter
    semantics (`graduated` means moved-out-of-principles, not freshly-authored) that this
    function's callers don't perform."""
    text = open(domain_path).read()
    idx = text.find("\nkilled:")
    if idx == -1:
        fail(f"{domain_path} has no 'killed:' marker to anchor the insertion — malformed or "
             "missing domain file; create its frontmatter + section shell first")
    head, tail = text[:idx], text[idx:]
    open(domain_path, "w").write(head.rstrip("\n") + "\n\n" + block.rstrip("\n") + "\n" + tail)


def format_audit_provenance_block(entry_id: str, domain: str, *, provenance: str = "",
                                   kind: str = "", imported_from: dict = None) -> str:
    lines = [f"- id: {entry_id}", f"  domain: {domain}"]
    if kind:
        lines.append(f"  kind: {kind}")
    if imported_from:
        lines.append("  provenance:")
        lines.append("    imported-from:")
        lines.append(f"      source: {yaml_quote(imported_from['source'])}")
        lines.append(f"      domain: {imported_from['domain']}")
        if imported_from.get("id"):
            lines.append(f"      id: {imported_from['id']}")
        if imported_from.get("originally-ratified"):
            lines.append(f"      originally-ratified: {yaml_quote(imported_from['originally-ratified'])}")
        lines.append(f"    extracted: {imported_from.get('extracted') or today()}")
    else:
        lines.append(f"  provenance: {yaml_quote(provenance)}")
    return "\n".join(lines) + "\n"


def append_audit_provenance(audit_path: str, block: str) -> None:
    """Append a provenance entry to a layer's audit.md, immediately before the closing fence that
    precedes the `<!-- corpus-script:begin -->` marker — the same place every entry lands
    regardless of which domain's earlier section it logically belongs near; audit.md's `# domain:
    X` headers are informal narrative dividers, not a structural requirement any parser depends
    on (`parse_audit_entries` scans the whole flat `provenance:` list by id).

    A freshly-bootstrapped project may have adopted domain containers (via `adopt-domain-shell`) but
    no audit.md yet — so scaffold one lazily rather than failing, the same tolerance record-gate
    already has for a missing domains-dir. Existing audits are left untouched."""
    _ensure_audit_scaffold(audit_path)
    text = open(audit_path).read()
    marker = "\n```\n\n<!-- corpus-script:begin"
    idx = text.find(marker)
    if idx == -1:
        fail(f"{audit_path} has no recognizable provenance-fence / corpus-script:begin boundary")
    head, tail = text[:idx], text[idx:]
    new_head = head.rstrip("\n") + "\n" + block.rstrip("\n") + "\n"
    open(audit_path, "w").write(new_head + tail)


def cmd_add_principle(project: "Project", args) -> None:
    files = project.domain_files()
    if args.domain not in files:
        fail(f"unknown domain '{args.domain}' under {project.domains_dir} — add-principle only "
             "appends into an existing domain file; create its frontmatter + empty "
             "principles:/killed: shell first for a brand-new domain")
    domain_path = files[args.domain]
    if args.id in collect_domain_ids(domain_path):
        fail(f"'{args.id}' already exists in {domain_path}")

    fields = {"id": args.id, "rule": args.rule, "condition": args.condition, "reason": args.reason}
    if args.see_also:
        fields["see-also"] = args.see_also
    append_domain_entry(domain_path, format_principle_block(fields))

    append_audit_provenance(project.audit_path, format_audit_provenance_block(
        args.id, args.domain, provenance=args.provenance, kind=args.kind))

    record_gate_core(project, args.domain, domain_path, ratified=1)
    print(f"added principle '{args.id}' to {domain_path}, provenance recorded in {project.audit_path}")


def cmd_adopt_domain_shell(project: "Project", args) -> None:
    """Create a container-only domain shell (frontmatter copied verbatim from a source domain file,
    plus an empty principles:/killed: body) so a brand-new domain's container exists before a
    candidate can be ratified into it. Writes NO principles and NO audit entries — the domain's
    judgment still enters through the ratify gate; this only makes the container the gate needs.
    Idempotent and non-destructive: if the target domain file already exists it does nothing (it may
    already hold ratified principles)."""
    source = args.source
    if not os.path.exists(source):
        fail(f"no such source domain file: {source}")
    m = FRONTMATTER_RE.match(open(source).read())
    if not m:
        fail(f"source domain file {source} has no YAML frontmatter (--- ... ---) block to copy")
    frontmatter = m.group(0).rstrip("\n")   # ---\n...\n--- (drop the trailing newline; re-added below)
    stem = os.path.basename(source)
    stem = stem[:-3] if stem.endswith(".md") else os.path.splitext(stem)[0]
    dest_dir = project.domains_dir
    dest_path = os.path.join(dest_dir, f"{stem}.md")
    if os.path.exists(dest_path):
        print(f"adopt-domain-shell: {dest_path} already exists — skipped (non-destructive)")
        return
    os.makedirs(dest_dir, exist_ok=True)
    shell = (f"{frontmatter}\n\n# Domain: {stem}\n\n"
             "```yaml\n"
             "last-retrospective: none\n\n"
             "principles:\n\n"
             "killed:\n"
             "```\n")
    open(dest_path, "w").write(shell)
    print(f"adopt-domain-shell: created container {dest_path} from {source}")


def parse_import_candidates(path: str) -> dict:
    """Tolerant, purpose-built parser (not a general YAML parser) for .corpora/import-candidates.md's
    `candidates:` list, matching exactly what `append_import_candidate` writes — a flat list of
    entries, each opening with a zero-indent `- id:` line."""
    if not os.path.exists(path):
        return {}
    text = open(path).read()
    if "```yaml" not in text:
        return {}
    _, _, rest = text.partition("```yaml")
    fence_body, _, _ = rest.partition("\n```")
    _, sep, body = fence_body.partition("candidates:")
    if not sep:
        return {}
    body = body.strip("\n")
    if not body or body.strip() == "[]":
        return {}
    entries = {}
    for block in re.split(r"\n(?=- id:)", body):
        block = block.strip("\n")
        m_id = re.match(r"-\s*id:\s*(\S+)", block)
        if not m_id:
            continue
        entry_id = m_id.group(1)
        entry = {"id": entry_id, "imported-from": {}}
        in_imported_from = False
        for raw in block.split("\n")[1:]:
            stripped = raw.strip()
            if stripped == "provenance:":
                continue
            if stripped == "imported-from:":
                in_imported_from = True
                continue
            m_extracted = re.match(r"extracted:\s*(\S+)", stripped)
            if m_extracted:
                entry["extracted"] = m_extracted.group(1)
                in_imported_from = False
                continue
            if in_imported_from:
                m_field = re.match(r"([\w-]+):\s*(.*)$", stripped)
                if m_field:
                    entry["imported-from"][m_field.group(1)] = yaml_unescape(m_field.group(2).strip().strip('"'))
                continue
            m_domains = re.match(r"domains:\s*\[(.*)\]", stripped)
            if m_domains:
                entry["domains"] = [d.strip() for d in m_domains.group(1).split(",") if d.strip()]
                continue
            m_field = re.match(r"(rule|condition|reason|kind|change|kill-type|from-domain|successor):\s*(.*)$", stripped)
            if m_field:
                entry[m_field.group(1)] = yaml_unescape(m_field.group(2).strip().strip('"'))
        entries[entry_id] = entry
    return entries


def remove_import_candidate(path: str, entry_id: str) -> bool:
    text = open(path).read()
    if "```yaml" not in text:
        return False
    before, _, rest = text.partition("```yaml")
    fence_body, _, after = rest.partition("\n```")
    head, sep, body = fence_body.partition("candidates:")
    if not sep:
        return False
    body = body.strip("\n")
    blocks = [] if not body or body.strip() == "[]" else re.split(r"\n(?=- id:)", body)
    kept, removed = [], False
    for block in blocks:
        block = block.strip("\n")
        if not block:
            continue
        if re.match(rf"-\s*id:\s*{re.escape(entry_id)}\s*$", block.split("\n")[0].strip()):
            removed = True
            continue
        kept.append(block)
    if not removed:
        return False
    new_body = "\n".join(kept)
    new_fence_body = head + "candidates:" + (("\n" + new_body) if new_body.strip() else " []")
    open(path, "w").write(before + "```yaml" + new_fence_body + "\n```" + after)
    return True


def cmd_ratify_import_candidate(project: "Project", args) -> None:
    source_path = args.source or project.import_candidates_path
    candidates = parse_import_candidates(source_path)
    entry = candidates.get(args.id)
    if entry is None:
        fail(f"no candidate '{args.id}' in {source_path}")
    dest_domain = args.as_domain or (entry.get("domains") or [None])[0]
    if not dest_domain:
        fail(f"candidate '{args.id}' has no destination domain recorded — pass --as-domain")
    dest_id = args.as_id or args.id
    files = project.domain_files()
    if dest_domain not in files:
        fail(f"unknown domain '{dest_domain}' under {project.domains_dir} — create its "
             "frontmatter + empty principles:/killed: shell first for a brand-new domain")
    domain_path = files[dest_domain]
    change = entry.get("change", "")
    if change == "move":
        from_domain = entry.get("from-domain", "")
        if from_domain not in files:
            fail(f"move candidate '{args.id}' names unknown from-domain '{from_domain}'")
        from_path = files[from_domain]
        was_removed = remove_live_entry(from_path, dest_id)
        if dest_id not in collect_domain_ids(domain_path):
            fields = {"id": dest_id, "rule": entry.get("rule", ""),
                      "condition": entry.get("condition", ""), "reason": entry.get("reason", "")}
            append_domain_entry(domain_path, format_principle_block(fields))
            record_gate_core(project, dest_domain, domain_path, ratified=1)
        if was_removed:
            record_gate_core(project, from_domain, from_path, removed=1)
        append_audit_provenance(project.audit_path, format_audit_provenance_block(
            dest_id, dest_domain,
            provenance=f"Pool sync {today()}: moved {from_domain} -> {dest_domain}, applying the "
                       "source pool's reorg (see the source audit's history entry for why)."))
        if not remove_import_candidate(source_path, args.id):
            fail(f"applied move of '{dest_id}' but could not remove '{args.id}' from "
                 f"{source_path} — fix that file by hand so it isn't re-applied")
        print(f"applied move candidate '{args.id}': {from_domain} -> {dest_domain}, "
              f"removed from {source_path}")
        return
    if change == "supersede":
        successor = entry.get("successor", "")
        if not remove_live_entry(domain_path, dest_id):
            fail(f"supersede candidate '{args.id}' names '{dest_id}', not live in {domain_path} — "
                 "nothing to supersede")
        record_gate_core(project, dest_domain, domain_path, removed=1)
        append_audit_provenance(project.audit_path, format_audit_provenance_block(
            dest_id, dest_domain,
            provenance=f"Pool sync {today()}: superseded by {successor} (source-pool "
                       "consolidation) and removed from this pool's working file."))
        if not remove_import_candidate(source_path, args.id):
            fail(f"applied supersede of '{dest_id}' but could not remove '{args.id}' from "
                 f"{source_path} — fix that file by hand so it isn't re-applied")
        print(f"applied supersede candidate '{args.id}': removed from {dest_domain} in favor of "
              f"'{successor}', removed from {source_path}")
        return
    if change in ("update", "kill"):
        live = parse_domain_section_full(domain_path, "principles")
        if dest_id not in live:
            fail(f"candidate '{args.id}' is a {change} for '{dest_id}', which is not a live "
                 f"principle in {domain_path} — nothing to {change}")
        if change == "kill":
            remove_live_entry(domain_path, dest_id)
            append_audit_kill_entry(project.audit_path, format_audit_kill_block({
                "id": dest_id, "domain": dest_domain, "rule": entry.get("rule", ""),
                "kill_type": entry.get("kill-type", "quality"),
                "reason_killed": entry.get("reason", "")}))
            record_gate_core(project, dest_domain, domain_path, killed=1)
        else:
            fields = {"id": dest_id, "rule": entry.get("rule", ""),
                      "condition": entry.get("condition", live[dest_id].get("condition", "")),
                      "reason": entry.get("reason", "")}
            if live[dest_id].get("see-also"):
                fields["see-also"] = live[dest_id]["see-also"]
            remove_live_entry(domain_path, dest_id)
            append_domain_entry(domain_path, format_principle_block(fields))
            record_gate_core(project, dest_domain, domain_path)
        if not remove_import_candidate(source_path, args.id):
            fail(f"applied {change} of '{dest_id}' in {domain_path}, but could not remove "
                 f"'{args.id}' from {source_path} — fix that file by hand so it isn't re-applied")
        print(f"applied {change} candidate '{args.id}' -> '{dest_id}' in {dest_domain}, "
              f"removed from {source_path}")
        return

    if dest_id in collect_domain_ids(domain_path):
        fail(f"'{dest_id}' already exists in {domain_path} — pass --as-id to rename on write-back")
    if dest_id in audit_kill_ids(project.audit_path):
        fail(f"'{dest_id}' was previously killed (see the kill log in {project.audit_path}) — "
             "re-ratifying it needs an explicit new id via --as-id, or a deliberate revival "
             "recorded against the kill entry")

    if "condition" not in entry:
        fail(f"candidate '{args.id}' is a convention (no condition) — ratify-import-candidate "
             "only writes back principles: for now; write this one back by hand into "
             "conventions:, matching kernel.md's write-back format, then remove it from "
             f"{source_path} yourself")
    fields = {"id": dest_id, "rule": entry.get("rule", ""), "condition": entry["condition"],
              "reason": entry.get("reason", "")}
    append_domain_entry(domain_path, format_principle_block(fields))

    imported_from = dict(entry.get("imported-from", {}))
    imported_from["extracted"] = entry.get("extracted", "")
    if entry.get("id") and entry["id"] != dest_id:
        imported_from.setdefault("id", entry["id"])
    append_audit_provenance(project.audit_path, format_audit_provenance_block(
        dest_id, dest_domain, kind=entry.get("kind", "judgment"), imported_from=imported_from))

    record_gate_core(project, dest_domain, domain_path, ratified=1)

    if not remove_import_candidate(source_path, args.id):
        fail(f"wrote '{dest_id}' to {domain_path} and recorded provenance, but could not remove "
             f"'{args.id}' from {source_path} — fix that file by hand so it isn't re-ratified")
    print(f"ratified candidate '{args.id}' as '{dest_id}' -> {dest_domain}, removed from {source_path}")


def cmd_import_list(project: "Project", args) -> None:
    target_domains_dir = args.target_domains_dir or project.domains_dir
    target_ids = set()
    if os.path.isdir(target_domains_dir):
        for name in os.listdir(target_domains_dir):
            if name.endswith(".md") and name != "audit.md":
                target_ids |= collect_domain_ids(os.path.join(target_domains_dir, name))
    printed = 0
    for name in sorted(os.listdir(args.source)):
        if not name.endswith(".md") or name == "audit.md":
            continue
        domain = name[:-3]
        path = os.path.join(args.source, name)
        for kind, section in (("principle", "principles"), ("convention", "conventions")):
            for entry_id, fields in sorted(parse_domain_section_full(path, section).items()):
                already = entry_id in target_ids
                rule = fields.get("rule", "")
                flag = " [already present]" if already else ""
                print(f"{domain}/{entry_id} ({kind}){flag}: {rule}")
                printed += 1
    if not printed:
        print(f"no principles or conventions found under {args.source}")


def cmd_import_candidate(project: "Project", args) -> None:
    kind, fields = find_import_entry(args.source, args.domain, args.id)
    dest_domain = args.as_domain or args.domain
    dest_id = args.as_id or args.id
    target_domains_dir = args.target_domains_dir or project.domains_dir
    existing = set()
    dest_path = os.path.join(target_domains_dir, f"{dest_domain}.md")
    if os.path.exists(dest_path):
        existing = collect_domain_ids(dest_path)
    if dest_id in existing:
        fail(f"'{dest_id}' already exists in {dest_path} — pass --as-id to import under a "
             "different id")
    entry = {
        "id": dest_id, "rule": fields.get("rule", ""), "reason": fields.get("reason", ""),
        "domain": dest_domain, "source": args.source, "source-domain": args.domain,
        "source-id": args.id if args.id != dest_id else "",
        "originally-ratified": source_originally_ratified(args.source, args.id),
    }
    if kind == "principle" and "condition" in fields:
        entry["condition"] = fields["condition"]
    target = args.output or project.import_candidates_path
    append_import_candidate(target, entry)
    print(f"proposed {kind} '{args.id}' from {args.source}/{args.domain} as candidate "
          f"'{dest_id}' -> {dest_domain} in {target}")


def default_pool_domains(source_dir: str, shape: dict) -> list:
    """Every domain in `source_dir` whose `applies-when` already matches this project's shape (or
    is universal) — the day-one bulk-import pool, independent of any one unit-of-work (kernel.md,
    'Project corpora')."""
    selected = []
    for name in sorted(os.listdir(source_dir)):
        if not name.endswith(".md") or name == "audit.md":
            continue
        fm = parse_domain_frontmatter(os.path.join(source_dir, name))
        if fm is None:
            continue
        if fm["universal"] or applies_when_matches(fm["applies-when"], shape):
            selected.append(name[:-3])
    return selected


def cmd_import_default_pool(project: "Project", args) -> None:
    source_dir = args.source or os.path.join(skill_root(), "domains")
    config_path = args.config or project.config_path
    shape = parse_config_shape(config_path)
    target_domains_dir = args.target_domains_dir or project.domains_dir
    target = args.output or project.import_candidates_path
    pending = set(parse_import_candidates(target))
    proposed = updates = kills = moves = supersedes = 0

    pool = default_pool_domains(source_dir, shape)

    # Reorg sync first, so its ids are pending before the add/update loop below can re-propose
    # them as plain new candidates. Source-audit history stanzas are the wire format: a `moved`
    # event whose entry now lives in domain D, while the target still holds the id in a different
    # domain, queues a `change: move`; a `consolidated`/`generalized` event with a `successor:`,
    # whose id the source no longer carries live but the target still does, queues a
    # `change: supersede`. Both are gate-mediated like everything else.
    target_locations = {}
    if os.path.isdir(target_domains_dir):
        for name in sorted(os.listdir(target_domains_dir)):
            if name.endswith(".md") and name != "audit.md":
                for entry_id in collect_domain_ids(os.path.join(target_domains_dir, name)):
                    target_locations.setdefault(entry_id, name[:-3])
    for entry_id, rec in sorted(parse_audit_histories(os.path.join(source_dir, "audit.md")).items()):
        if entry_id in pending or entry_id not in target_locations:
            continue
        old_domain = target_locations[entry_id]
        dest_domain = rec["domain"]
        source_live = {}
        dest_source_path = os.path.join(source_dir, f"{dest_domain}.md")
        if os.path.exists(dest_source_path):
            source_live = parse_domain_section_full(dest_source_path, "principles")
        for ev in reversed(rec["events"]):
            if ev.get("type") == "moved" and dest_domain in pool and old_domain != dest_domain \
                    and entry_id in source_live:
                fields = source_live[entry_id]
                entry = {
                    "id": entry_id, "rule": fields.get("rule", ""),
                    "reason": fields.get("reason", ""), "domain": dest_domain,
                    "from-domain": old_domain, "change": "move",
                    "source": source_dir, "source-domain": dest_domain, "source-id": "",
                    "originally-ratified": source_originally_ratified(source_dir, entry_id),
                }
                if "condition" in fields:
                    entry["condition"] = fields["condition"]
                append_import_candidate(target, entry)
                pending.add(entry_id)
                moves += 1
                break
            if ev.get("type") in ("consolidated", "generalized") and ev.get("successor") \
                    and entry_id not in source_live:
                entry = {
                    "id": entry_id, "rule": "",
                    "reason": f"superseded in the source pool by {ev['successor']} — removing "
                              "this entry applies that consolidation here; decline if this "
                              "project deliberately kept its own divergent copy",
                    "domain": old_domain, "successor": ev["successor"], "change": "supersede",
                    "source": source_dir, "source-domain": dest_domain, "source-id": "",
                    "originally-ratified": source_originally_ratified(source_dir, entry_id),
                }
                append_import_candidate(target, entry)
                pending.add(entry_id)
                supersedes += 1
                break

    # Ids in the target's own kill log are settled local rejections — the ratify guard would
    # refuse them anyway, so proposing them every sync only queues noise. Named once per run so
    # the operator sees the divergence exists without it becoming a recurring candidate.
    locally_killed = audit_kill_ids(os.path.join(target_domains_dir, "audit.md"))

    for domain in pool:
        dest_path = os.path.join(target_domains_dir, f"{domain}.md")
        target_exists = os.path.exists(dest_path)
        existing = collect_domain_ids(dest_path) if target_exists else set()
        source_path = os.path.join(source_dir, f"{domain}.md")
        for kind, section in (("principle", "principles"), ("convention", "conventions")):
            target_entries = parse_domain_section_full(dest_path, section) if target_exists else {}
            for entry_id, fields in sorted(parse_domain_section_full(source_path, section).items()):
                if entry_id in pending:
                    continue
                if entry_id not in existing and entry_id in locally_killed:
                    print(f"skipped (locally killed): {domain}/{entry_id} — live in the source, "
                          "killed in this pool; a deliberate local divergence, not re-proposed")
                    continue
                is_update = False
                if entry_id in existing:
                    live = target_entries.get(entry_id)
                    if live is None or all(fields.get(f, "") == live.get(f, "")
                                           for f in ("rule", "condition", "reason")):
                        continue
                    is_update = True
                entry = {
                    "id": entry_id, "rule": fields.get("rule", ""), "reason": fields.get("reason", ""),
                    "domain": domain, "source": source_dir, "source-domain": domain, "source-id": "",
                    "originally-ratified": source_originally_ratified(source_dir, entry_id),
                }
                if kind == "principle" and "condition" in fields:
                    entry["condition"] = fields["condition"]
                if is_update:
                    entry["change"] = "update"
                    updates += 1
                else:
                    proposed += 1
                append_import_candidate(target, entry)
        if not target_exists:
            continue
        # Kill records live in each pool's audit kill log (2026-08-07); the working-file killed:
        # reads survive only as fallback for a pool that predates migrate-kill-log.
        target_killed = set(parse_domain_section_full(dest_path, "killed")) \
            | audit_kill_ids(os.path.join(target_domains_dir, "audit.md"))
        live_ids = set(parse_domain_section_full(dest_path, "principles")) \
            | set(parse_domain_section_full(dest_path, "conventions"))
        source_kills = {eid: f for eid, f in
                        parse_audit_kills(os.path.join(source_dir, "audit.md")).items()
                        if f.get("domain") == domain}
        source_kills.update(parse_domain_section_full(source_path, "killed"))
        for entry_id, fields in sorted(source_kills.items()):
            if entry_id in pending or entry_id in target_killed or entry_id not in live_ids:
                continue
            entry = {
                "id": entry_id, "rule": fields.get("rule", ""),
                "reason": fields.get("reason_killed", ""),
                "domain": domain, "source": source_dir, "source-domain": domain, "source-id": "",
                "originally-ratified": source_originally_ratified(source_dir, entry_id),
                "change": "kill", "kill-type": fields.get("kill_type", ""),
            }
            append_import_candidate(target, entry)
            kills += 1
    print(f"proposed {proposed} candidate(s), {updates} update(s), {kills} kill(s), "
          f"{moves} move(s), {supersedes} supersede(s) "
          f"from {source_dir}'s default pool -> {target}")


# ── migration: materialize a pre-dissolution project's live-merged view once ─────────────────
#
# praxis-plugin/phases/domain-repo-migration.md: a project bootstrapped under the old live seed/project merge
# writes what was previously computed live into its own .corpora/domains/, once, so nothing it
# already relied on silently disappears when the merge stops. This bypasses the candidate/gate
# pipeline deliberately — it isn't proposing new judgment, it's making already-active judgment
# explicit; write-back's ordinary review would ask the operator to re-approve content the project
# was already running on. Scoped to `principles:`/`conventions:` only — the active guidance a spawn
# actually loads; a domain's `killed:` log is not migrated (documented gap,
# `praxis-plugin/phases/domain-repo-migration.md`; a re-proposed already-killed idea is a low-cost, self-correcting
# failure mode, not silent content loss).

def extract_preamble(path: str) -> str:
    """The free-prose scene-setting text between frontmatter (if any) and the ```yaml fence —
    domain description, load conditions stated in prose, shared vocabulary/glossary content.
    Distinct from a principle's `condition`: this is context a reader loads once for the whole
    domain, never an addressable/killable rule (LINEAGE.md's `fold-to-preamble` retirement was
    about dissolving *rules* into unstructured prose, not about this kind of scene-setting text,
    which was never a rule to begin with)."""
    text = open(path).read()
    m = FRONTMATTER_RE.match(text)
    rest = text[m.end():] if m else text
    fence_idx = rest.find("```yaml")
    before_fence = rest[:fence_idx] if fence_idx != -1 else rest
    header_match = re.match(r"\s*#\s*Domain:[^\n]*\n", before_fence)
    if header_match:
        before_fence = before_fence[header_match.end():]
    return before_fence.strip("\n")


def extract_killed_block(path: str) -> str:
    """The raw, verbatim text of an existing domain file's `killed:` list (everything after the
    `killed:` marker up to the closing fence) — preserved byte-for-byte across migrate-domains
    rewrites the same way frontmatter and the preamble already are. A kill exists specifically to
    stop the same rejected idea from being re-proposed; regenerating an empty `killed:` list on
    every rewrite (the prior behavior) silently erases that history instead of just reformatting it."""
    if not os.path.exists(path):
        return ""
    text = open(path).read()
    idx = text.find("\nkilled:")
    if idx == -1:
        return ""
    tail = text[idx + len("\nkilled:"):]
    fence_idx = tail.find("\n```")
    body = tail[:fence_idx] if fence_idx != -1 else tail
    return body.strip("\n")


def render_migrated_domain(domain: str, frontmatter: str, preamble: str, last_retrospective: str,
                            conventions: dict, principles: dict, killed_block: str = "") -> str:
    lines = ["```yaml", f"last-retrospective: {last_retrospective}", "", "conventions:", ""]
    for entry_id, fields in conventions.items():
        lines.append(f"- id: {entry_id}")
        lines.append(f"  rule: {yaml_quote(fields.get('rule', ''))}")
        lines.append(f"  reason: {yaml_quote(fields.get('reason', ''))}")
        if fields.get("see-also"):
            lines.append(f"  see-also: {fields['see-also']}")
        lines.append("")
    lines += ["principles:", ""]
    for entry_id, fields in principles.items():
        lines.append(f"- id: {entry_id}")
        lines.append(f"  rule: {yaml_quote(fields.get('rule', ''))}")
        lines.append(f"  condition: {yaml_quote(fields.get('condition', ''))}")
        lines.append(f"  reason: {yaml_quote(fields.get('reason', ''))}")
        if fields.get("see-also"):
            lines.append(f"  see-also: {fields['see-also']}")
        lines.append("")
    lines.append("killed:")
    if killed_block:
        lines.append("")
        lines.append(killed_block)
    lines.append("```")
    body = "\n".join(lines) + "\n"
    header = frontmatter if frontmatter else ""
    preamble_block = f"{preamble}\n\n" if preamble else ""
    return f"{header}\n# Domain: {domain}\n\n{preamble_block}{body}"


def append_migration_provenance(audit_path: str, domain: str, ids: list) -> None:
    if not ids:
        return
    lines = []
    for entry_id in ids:
        lines.append(f"- id: {entry_id}")
        lines.append(f"  domain: {domain}")
        lines.append(f"  provenance: \"Migrated from seed, {today()}.\"")
        lines.append("  history:")
        lines.append(f"    - date: {today()}")
        lines.append("      type: migrated-from-seed")
        lines.append(f"      reason: \"praxis-plugin/phases/domain-repo-migration.md: materialized from what "
                     f"the pre-dissolution live seed/project merge was already applying.\"")
        lines.append("")
    block = "\n".join(lines)
    if os.path.exists(audit_path):
        text = open(audit_path).read()
    else:
        os.makedirs(os.path.dirname(audit_path), exist_ok=True)
        text = "# Audit — project layer\n\n```yaml\nprovenance:\n```\n"
    if "```yaml" not in text or "provenance:" not in text:
        fail(f"{audit_path} does not have a recognizable 'provenance:' block — fix by hand")
    before, _, rest = text.partition("```yaml")
    fence_body, _, after = rest.partition("\n```")
    fence_body = fence_body.rstrip("\n") + "\n" + block.rstrip("\n")
    text = before + "```yaml" + fence_body + "\n```" + after
    open(audit_path, "w").write(text)


def cmd_migrate_domains(project: "Project", args) -> None:
    source_dir = args.source or os.path.join(skill_root(), "domains")
    config_path = args.config or project.config_path
    shape = parse_config_shape(config_path)
    domains = sorted(set(_ids(args.domains) or default_pool_domains(source_dir, shape))
                      | set(project.domain_files().keys()))
    os.makedirs(project.domains_dir, exist_ok=True)
    migrated = []
    for domain in domains:
        seed_path = os.path.join(source_dir, f"{domain}.md")
        project_path = os.path.join(project.domains_dir, f"{domain}.md")
        has_seed = os.path.exists(seed_path)
        has_project = os.path.exists(project_path)
        if not has_seed and not has_project:
            continue
        frontmatter = ""
        for candidate_path in (project_path if has_project else None, seed_path if has_seed else None):
            if candidate_path:
                m = FRONTMATTER_RE.match(open(candidate_path).read())
                if m:
                    frontmatter = m.group(0)
                    break
        last_retrospective = "none"
        for candidate_path in (project_path if has_project else None, seed_path if has_seed else None):
            if candidate_path:
                m = re.search(r"^last-retrospective:\s*(\S+)", open(candidate_path).read(), re.MULTILINE)
                if m:
                    last_retrospective = m.group(1)
                    break
        preamble = ""
        for candidate_path in (project_path if has_project else None, seed_path if has_seed else None):
            if candidate_path:
                p = extract_preamble(candidate_path)
                if p:
                    preamble = p
                    break
        killed_block = extract_killed_block(project_path) if has_project else ""
        newly_migrated_ids = []
        merged = {}
        for section in ("conventions", "principles"):
            entries = parse_domain_section_full(project_path, section) if has_project else {}
            if has_seed:
                for entry_id, fields in parse_domain_section_full(seed_path, section).items():
                    if entry_id not in entries:
                        entries[entry_id] = fields
                        newly_migrated_ids.append(entry_id)
            merged[section] = entries
        if not merged["conventions"] and not merged["principles"]:
            continue
        open(project_path, "w").write(render_migrated_domain(
            domain, frontmatter, preamble, last_retrospective, merged["conventions"], merged["principles"],
            killed_block))
        if newly_migrated_ids:
            append_migration_provenance(project.audit_path, domain, newly_migrated_ids)
            migrated.append(f"{domain}: +{len(newly_migrated_ids)} entries from seed")
    if migrated:
        print("migrated:")
        for line in migrated:
            print(f"  - {line}")
    else:
        print("nothing to migrate — every matching domain already fully materialized")
    print("Next: run `corpus.py measure` then `corpus.py verify` to register the new baseline "
          "(praxis-plugin/phases/domain-repo-migration.md, step 4).")


def cmd_sync_units_of_work(project: "Project", args) -> None:
    """`migrate-domains` merges principle *content* from seed but deliberately keeps a project's own
    frontmatter untouched once a domain file already exists — so a project's units-of-work list can
    drift behind the seed's (e.g. a domain gains `debug-issue` in the seed template after a project
    already materialized its own copy with only `implement-feature`). This is that sibling: it syncs
    only the `units-of-work:` list, additively (never removes a project-only entry the seed doesn't
    have), and is a mechanical composition-scope fix, not a principle — no ratify gate involved."""
    source_dir = args.source or os.path.join(skill_root(), "domains")
    domains = sorted(_ids(args.domains)) if args.domains else sorted(project.domain_files().keys())
    changes = []
    for domain in domains:
        seed_path = os.path.join(source_dir, f"{domain}.md")
        project_path = os.path.join(project.domains_dir, f"{domain}.md")
        if not os.path.exists(seed_path) or not os.path.exists(project_path):
            continue
        seed_fm = parse_domain_frontmatter(seed_path)
        proj_fm = parse_domain_frontmatter(project_path)
        if seed_fm is None or proj_fm is None:
            continue
        missing = [u for u in seed_fm["units-of-work"] if u not in proj_fm["units-of-work"]]
        if not missing:
            continue
        changes.append((domain, project_path, proj_fm["units-of-work"], missing))
    if not changes:
        print("no units-of-work drift found — every checked domain already matches its seed")
        return
    verb = "synced" if args.apply else "would sync (dry run — pass --apply to write)"
    print(f"{verb}:")
    for domain, project_path, existing, missing in changes:
        print(f"  - {domain}: +{','.join(missing)}")
        if args.apply:
            new_list = existing + missing
            text = open(project_path).read()
            new_text = re.sub(r"^units-of-work:\s*\[.*\]\s*$",
                               "units-of-work: [" + ", ".join(new_list) + "]",
                               text, count=1, flags=re.MULTILINE)
            open(project_path, "w").write(new_text)
    if args.apply:
        print("Next: run `corpus.py lint-domains` to confirm, and `corpus.py select` for any "
              "unit-of-work these domains now apply to, to confirm the wider composition.")


# ── queue: mechanical status transitions for .corpora/queue.md ────────────────────────────────
# Same reasoning as the chunk ledger (kernel.md, "bookkeeping done by attention is bookkeeping
# that silently stops"): `planning.md`'s queue schema states the orchestrator updates `status` on
# tasks and `resolved`/`answer` on questions "in-place," but nothing scripted ever did that
# in-place update — it was hand-edited, the same failure class the chunk ledger was built to
# close for domains-composed. This closes it for .corpora/queue.md.

TASK_STATUS_ENUM = {"pending", "in-progress", "complete", "blocked"}
QUEUE_LIST_FIELDS = {"blocked-by", "blocks"}
QUEUE_TASK_FIELDS = ("id", "title", "description", "context", "status", "blocked-by",
                     "parallel-ok", "concern", "judgment", "notes")
QUEUE_QUESTION_FIELDS = ("id", "question", "blocks", "resolved", "answer")
QUEUE_NYS_FIELDS = ("id", "note")
QUEUE_OOS_FIELDS = ("id", "gist", "reason")
QUEUE_HEADER_FIELDS = ("capability", "area", "status", "created", "updated")
QUEUE_SECTIONS = ("tasks", "open-questions", "not-yet-specified", "out-of-scope")


def parse_queue(path: str) -> tuple:
    """Deliberately flat parser, the same deliberately-flat inline-YAML parse style used across
    corpus.py's ledgers. Returns
    (header, tasks, questions, not_yet_specified, out_of_scope) — header is the top-level scalar
    fields; the four lists hold dicts, with blocked-by/blocks parsed into real lists via
    _parse_inline_list. not_yet_specified and out_of_scope carry no status/blocking fields —
    fog isn't a task yet, and a closed scope boundary never becomes one (domains/planning.md,
    'Fog or ticket?' / 'Out of scope')."""
    header = {}
    section_bodies = {name: [] for name in QUEUE_SECTIONS}
    section = None
    for raw in open(path):
        stripped = raw.strip()
        if stripped == "```":
            if section is not None:
                break
            continue
        matched = next((name for name in QUEUE_SECTIONS
                         if stripped in (f"{name}:", f"{name}: []")), None)
        if matched:
            section = matched
            continue
        if not stripped or stripped.startswith(("#", "```yaml")):
            continue
        if section is None:
            if ":" in stripped:
                key, _, value = stripped.partition(":")
                header[key.strip()] = value.strip()
            continue
        section_bodies[section].append(raw)
    parsed = {name: _parse_flat_list(section_bodies[name], list_fields=QUEUE_LIST_FIELDS)
              for name in QUEUE_SECTIONS}
    return (header, parsed["tasks"], parsed["open-questions"],
            parsed["not-yet-specified"], parsed["out-of-scope"])


def render_queue(header: dict, tasks: list, questions: list,
                  not_yet_specified: list = None, out_of_scope: list = None) -> str:
    not_yet_specified = not_yet_specified or []
    out_of_scope = out_of_scope or []
    lines = ["```yaml"]
    for key in QUEUE_HEADER_FIELDS:
        lines.append(f"{key}: {header.get(key, '')}")
    lines += ["", "tasks:"]
    for t in tasks:
        lines.append(f"  - id: {t.get('id', '')}")
        for key in QUEUE_TASK_FIELDS[1:]:
            value = t.get(key, "")
            if key in QUEUE_LIST_FIELDS:
                value = f"[{', '.join(value)}]" if isinstance(value, list) else (value or "[]")
            lines.append(f"    {key}: {value}")
        lines.append("")
    lines.append("open-questions:")
    for q in questions:
        lines.append(f"  - id: {q.get('id', '')}")
        for key in QUEUE_QUESTION_FIELDS[1:]:
            value = q.get(key, "")
            if key in QUEUE_LIST_FIELDS:
                value = f"[{', '.join(value)}]" if isinstance(value, list) else (value or "[]")
            lines.append(f"    {key}: {value}")
        lines.append("")
    lines.append("not-yet-specified:")
    for n in not_yet_specified:
        lines.append(f"  - id: {n.get('id', '')}")
        for key in QUEUE_NYS_FIELDS[1:]:
            lines.append(f"    {key}: {n.get(key, '')}")
        lines.append("")
    lines.append("out-of-scope:")
    for o in out_of_scope:
        lines.append(f"  - id: {o.get('id', '')}")
        for key in QUEUE_OOS_FIELDS[1:]:
            lines.append(f"    {key}: {o.get(key, '')}")
        lines.append("")
    lines.append("```")
    return "\n".join(lines) + "\n"


def queue_lint_problems(path: str) -> list:
    problems = []
    header, tasks, questions, not_yet_specified, out_of_scope = parse_queue(path)
    for field in ("capability", "area", "status"):
        if not header.get(field):
            problems.append(f"{path}: missing header field {field}")
    task_ids = set()
    for t in tasks:
        label = f"{path} task {t.get('id') or '(no id)'}"
        if not t.get("id"):
            problems.append(f"{label}: missing id")
        elif t["id"] in task_ids:
            problems.append(f"{label}: duplicate task id")
        task_ids.add(t.get("id"))
        if t.get("status") not in TASK_STATUS_ENUM:
            problems.append(f"{label}: status must be one of {sorted(TASK_STATUS_ENUM)}")
        for dep in t.get("blocked-by", []):
            if dep and dep not in {t2.get("id") for t2 in tasks}:
                problems.append(f"{label}: blocked-by references unknown task id '{dep}'")
    question_ids = set()
    for q in questions:
        label = f"{path} question {q.get('id') or '(no id)'}"
        if not q.get("id"):
            problems.append(f"{label}: missing id")
        elif q["id"] in question_ids:
            problems.append(f"{label}: duplicate question id")
        question_ids.add(q.get("id"))
        if q.get("resolved") not in ("true", "false"):
            problems.append(f"{label}: resolved must be true or false")
        for blocked in q.get("blocks", []):
            if blocked and blocked not in task_ids:
                problems.append(f"{label}: blocks references unknown task id '{blocked}'")
    all_ids = task_ids | question_ids
    for name, items, fields in (("not-yet-specified", not_yet_specified, QUEUE_NYS_FIELDS),
                                 ("out-of-scope", out_of_scope, QUEUE_OOS_FIELDS)):
        seen = set()
        for entry in items:
            label = f"{path} {name} {entry.get('id') or '(no id)'}"
            if not entry.get("id"):
                problems.append(f"{label}: missing id")
            elif entry["id"] in seen:
                problems.append(f"{label}: duplicate {name} id")
            elif entry["id"] in all_ids:
                problems.append(f"{label}: id collides with a task or question id — ids must be "
                                 "unique across the whole queue")
            seen.add(entry.get("id"))
            all_ids.add(entry.get("id"))
            for field in fields[1:]:
                if not entry.get(field):
                    problems.append(f"{label}: missing {field}")
    return problems


def cmd_lint_queue(project: "Project", _args) -> None:
    if not os.path.exists(project.queue_path):
        print("no .corpora/queue.md — nothing to lint")
        return
    problems = queue_lint_problems(project.queue_path)
    if problems:
        for p in problems:
            print(f"error: {p}", file=sys.stderr)
        sys.exit(2)
    print("lint-queue: ok")


def _task_startable(task: dict, tasks_by_id: dict, questions_by_id: dict) -> tuple:
    """Returns (startable, blockers) — blockers names every unresolved question and
    incomplete task still standing between this task and being routable."""
    blockers = []
    for dep_id in task.get("blocked-by", []):
        dep = tasks_by_id.get(dep_id)
        if dep and dep.get("status") != "complete":
            blockers.append(f"task {dep_id} ({dep.get('status')})")
    for q in questions_by_id.values():
        if task.get("id") in q.get("blocks", []) and q.get("resolved") != "true":
            blockers.append(f"question {q.get('id')} (unresolved)")
    return (not blockers, blockers)


def cmd_queue_status(project: "Project", _args) -> None:
    if not os.path.exists(project.queue_path):
        print("no .corpora/queue.md")
        return
    header, tasks, questions, not_yet_specified, out_of_scope = parse_queue(project.queue_path)
    tasks_by_id = {t.get("id"): t for t in tasks}
    questions_by_id = {q.get("id"): q for q in questions}
    print(f"capability: {header.get('capability', '')}")
    print(f"status: {header.get('status', '')}")
    for t in tasks:
        startable, blockers = _task_startable(t, tasks_by_id, questions_by_id)
        note = "" if t.get("status") == "complete" else (
            " — startable now" if startable else f" — blocked by: {', '.join(blockers)}")
        print(f"  {t.get('id')}: {t.get('status')}{note}")
    for q in questions:
        if q.get("resolved") != "true":
            print(f"  {q.get('id')}: unresolved — blocks {', '.join(q.get('blocks', [])) or '(nothing)'}")
    if not_yet_specified:
        print(f"not-yet-specified: {len(not_yet_specified)} — "
              f"{', '.join(n.get('id', '') for n in not_yet_specified)}")
    if out_of_scope:
        print(f"out-of-scope: {len(out_of_scope)} — "
              f"{', '.join(o.get('id', '') for o in out_of_scope)}")


def _save_queue(project: "Project", header: dict, tasks: list, questions: list,
                 not_yet_specified: list = None, out_of_scope: list = None) -> None:
    header["updated"] = today()
    if tasks and questions is not None:
        all_tasks_complete = all(t.get("status") == "complete" for t in tasks)
        all_questions_resolved = all(q.get("resolved") == "true" for q in questions)
        if all_tasks_complete and all_questions_resolved:
            header["status"] = "complete"
    text = open(project.queue_path).read()
    block = render_queue(header, tasks, questions, not_yet_specified, out_of_scope)
    if "```yaml" in text and "```" in text:
        before = text.split("```yaml", 1)[0]
        after = text.split("```yaml", 1)[1].split("```", 1)[1] if "```" in text.split("```yaml", 1)[1] else ""
        open(project.queue_path, "w").write(before + block + after)
    else:
        open(project.queue_path, "w").write(block)


def cmd_queue_set_status(project: "Project", args) -> None:
    if not os.path.exists(project.queue_path):
        fail(f"no queue at {project.queue_path}")
    if args.status not in TASK_STATUS_ENUM:
        fail(f"status must be one of {sorted(TASK_STATUS_ENUM)}")
    header, tasks, questions, not_yet_specified, out_of_scope = parse_queue(project.queue_path)
    task = next((t for t in tasks if t.get("id") == args.id), None)
    if task is None:
        fail(f"unknown task id '{args.id}' — have: {', '.join(t.get('id', '') for t in tasks) or 'none'}")
    task["status"] = args.status
    _save_queue(project, header, tasks, questions, not_yet_specified, out_of_scope)
    tasks_by_id = {t.get("id"): t for t in tasks}
    unblocked = [t.get("id") for t in tasks
                 if t.get("id") != args.id and t.get("status") == "pending"
                 and args.id in t.get("blocked-by", [])
                 and _task_startable(t, tasks_by_id, {q.get("id"): q for q in questions})[0]]
    print(f"{args.id}: status -> {args.status}")
    if unblocked:
        print(f"now startable: {', '.join(unblocked)}")


def cmd_queue_resolve_question(project: "Project", args) -> None:
    if not os.path.exists(project.queue_path):
        fail(f"no queue at {project.queue_path}")
    header, tasks, questions, not_yet_specified, out_of_scope = parse_queue(project.queue_path)
    question = next((q for q in questions if q.get("id") == args.id), None)
    if question is None:
        fail(f"unknown question id '{args.id}' — have: {', '.join(q.get('id', '') for q in questions) or 'none'}")
    question["resolved"] = "true"
    question["answer"] = args.answer
    _save_queue(project, header, tasks, questions, not_yet_specified, out_of_scope)
    tasks_by_id = {t.get("id"): t for t in tasks}
    unblocked = [t.get("id") for t in tasks
                 if t.get("id") in question.get("blocks", []) and t.get("status") == "pending"
                 and _task_startable(t, tasks_by_id, {q.get("id"): q for q in questions})[0]]
    print(f"{args.id}: resolved")
    if unblocked:
        print(f"now startable: {', '.join(unblocked)}")


def cmd_queue_graduate(project: "Project", args) -> None:
    """Fog-into-task is authorship, not a mechanical rename: the caller (planning spawn) writes
    the real task into `tasks:` by hand first, exactly like any other task's initial authorship,
    then this command deletes the now-graduated fog entry and validates the pointer isn't
    dangling — same 'bookkeeping done by attention is bookkeeping that silently stops' concern
    this file's queue commands already close for status transitions."""
    if not os.path.exists(project.queue_path):
        fail(f"no queue at {project.queue_path}")
    header, tasks, questions, not_yet_specified, out_of_scope = parse_queue(project.queue_path)
    entry = next((n for n in not_yet_specified if n.get("id") == args.id), None)
    if entry is None:
        fail(f"unknown not-yet-specified id '{args.id}' — have: "
             f"{', '.join(n.get('id', '') for n in not_yet_specified) or 'none'}")
    if not any(t.get("id") == args.task_id for t in tasks):
        fail(f"--task-id '{args.task_id}' is not in tasks — add the task to the queue file first, "
             "then graduate the fog entry it resolves")
    not_yet_specified.remove(entry)
    _save_queue(project, header, tasks, questions, not_yet_specified, out_of_scope)
    print(f"{args.id}: graduated -> {args.task_id}")


def cmd_queue_mark_out_of_scope(project: "Project", args) -> None:
    """A scope boundary, not a route step (domains/planning.md, 'Out of scope'): moves a task or
    a not-yet-specified entry to the out-of-scope ledger with a one-line reason, so the boundary
    stays legible without becoming a task that could ever graduate back in."""
    if not os.path.exists(project.queue_path):
        fail(f"no queue at {project.queue_path}")
    header, tasks, questions, not_yet_specified, out_of_scope = parse_queue(project.queue_path)
    task = next((t for t in tasks if t.get("id") == args.id), None)
    nys = next((n for n in not_yet_specified if n.get("id") == args.id), None)
    if task is None and nys is None:
        fail(f"unknown id '{args.id}' — not found in tasks or not-yet-specified")
    gist = (task or nys).get("title") or (task or nys).get("note") or ""
    if task is not None:
        tasks.remove(task)
    else:
        not_yet_specified.remove(nys)
    out_of_scope.append({"id": args.id, "gist": gist, "reason": args.reason})
    _save_queue(project, header, tasks, questions, not_yet_specified, out_of_scope)
    print(f"{args.id}: out of scope -> {args.reason}")


# ── emit-spawn-parts: the corpora side of spawn-prompt composition (parts + judgment) ────────
#
# Fix for the exercise's most serious finding: hand-assembled spawn prompts drifted toward
# summarizing or truncating inlined domain content as a session went on. The fix removes the
# judgment call by emitting full working files byte-for-byte — nothing here decides what's
# relevant, so there is nowhere for compression to sneak in. With the process/judgment split, the
# assembly + save lifecycle moved to praxis (spawn_prompt.py); corpora keeps only the parts it
# injects (stance frame, domain bodies, handoff schema) and the composition-validity judgment,
# emitted as JSON through the `spawn-parts` engine hook praxis composes.

def extract_section(text: str, heading_pattern: str, source: str) -> str:
    lines = text.split("\n")
    start = None
    for i, line in enumerate(lines):
        if re.match(heading_pattern, line):
            start = i
            break
    if start is None:
        fail(f"could not find a section matching {heading_pattern!r} in {source}")
    end = len(lines)
    in_fence = False
    for i in range(start + 1, len(lines)):
        if lines[i].strip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            # A bare "---" (e.g. a YAML document separator) inside a fenced
            # code block is section content, not a boundary marker — only a
            # heading or "---" outside any fence ends the section.
            continue
        if re.match(r"^#{1,6}\s", lines[i]) or lines[i].strip() == "---":
            end = i
            break
    return "\n".join(lines[start:end]).rstrip("\n")


def cmd_emit_spawn_parts(project: Project, args) -> None:
    """Emit the engine-contributed PARTS of a spawn prompt as JSON, for praxis to compose into its
    prompt skeleton. Corpora owns the judgment (composition validity) and the content — the stance
    frame + domain bodies + handoff-read schema, all byte-for-byte, so nothing here summarizes; praxis
    owns the assembly and the save lifecycle. This is the spawn-prompt HOOK: praxis injects whatever an
    engine returns here into its skeleton without knowing what a 'part' means (the handoff-plugin
    pattern, one level up). Composition problems are reported as data — praxis gates on them, corpora
    only judges that they exist."""
    import json
    domains = _ids(args.domains)
    if not domains:
        fail("--domains requires at least one comma-separated domain name")

    sources = project.domain_files()
    named = [(d, parse_domain_frontmatter(sources[d]) if d in sources else None) for d in domains]
    problems = check_composition_problems(named)

    missing = [d for d in domains if d not in sources]
    if missing:
        fail(f"domain(s) not found in {project.domains_dir}: {', '.join(missing)} — nothing to compose")

    kernel_text = open(os.path.join(skill_root(), "kernel.md")).read()
    stance_frame = extract_section(kernel_text, r"^### Generative stance\s*$", "kernel.md")
    handoff_schema = extract_section(kernel_text, r"^## What corpora reads from a handoff\s*$", "kernel.md")

    dparts = ["## Domains"]
    for domain in domains:
        dparts.append(f"\n### Domain: {domain}\n")
        dparts.append(open(sources[domain]).read().rstrip("\n"))
    domains_block = "\n".join(dparts)

    parts = [
        {"slot": "stance-frame", "body": stance_frame},
        {"slot": "domains", "body": domains_block},
        {"slot": "handoff-schema", "body": handoff_schema},
    ]
    # "Every composition reads .corpora/config.md" (SKILL.md) — delivered mechanically, not left
    # to the spawn to remember: the config carries the project shape, the deterministic project
    # utilities and verification commands, and the UI/UX library locations a coding spawn must
    # consult before touching a surface. Without this part, that contract held only when a
    # prompt-assembler thought to include it.
    if os.path.isfile(project.config_path):
        parts.append({"slot": "project-config",
                      "body": open(project.config_path).read().rstrip("\n")})
    payload = {"problems": problems, "parts": parts}
    print(json.dumps(payload, indent=2) if args.json else json.dumps(payload))


# ── kill-log graduation: age out killed entries with a recorded, stale kill date ─────────────
#
# Works on any domains-dir + its audit.md pair — a project's own <root>/.corpora/domains, this
# skill's own domains/, or any other corpora-managed location — since retrospective consolidation
# happens in this skill repo's own domain pool too, not only in downstream projects.

def parse_audit_entries(audit_path: str) -> dict:
    """Tolerant parser for the hand-maintained `provenance:` list in a layer's audit.md.

    Extracts an entry's own top-level scalar fields — id, domain, killed, graduated — accepting
    either indentation convention actually seen in the wild: a flat 2-space style (id and its
    fields all siblings at 2 spaces, kernel.md's own documented example) or the more common nested
    style (id at 2 spaces, its fields at 4). Both read as "this entry's own field," since neither
    depth ever collides with `history:`'s own sub-list items (6+ spaces) or their fields (8+) —
    those are deliberately not parsed; this reads just enough structure for kill-age accounting,
    not a general YAML parser. The `provenance:` list runs until the next top-level (no
    indentation) *section* key — `counters:`, `efficacy:`, `co-occurrence:`, `library-drift:` —
    which also use `- id:` for their own, unrelated entries; without that boundary, a later
    same-named field silently overwrites the real provenance entry for any id those sections also
    track. A bare `killed:` line at zero indentation is not one of these — it is a purely visual
    divider inside the provenance list itself (ratified entries above, killed-entry provenance
    below), still carrying the same id/domain/killed/reason_killed schema, so it must not end the
    scan.
    """
    section_boundaries = {"counters:", "efficacy:", "co-occurrence:", "library-drift:"}
    in_provenance = False
    flat_lines = []
    for raw in open(audit_path):
        line = raw.rstrip("\n")
        stripped = line.strip()
        if re.fullmatch(r"provenance:", stripped):
            in_provenance = True
            continue
        if in_provenance and stripped in section_boundaries and not line.startswith(" "):
            in_provenance = False
            continue
        if not in_provenance:
            continue
        # An entry's own fields live at indent 2-5; its `- id:` opener is read indent-agnostically.
        # Deeper lines (a `history:` sub-list's items at 6+, or a bare zero-indent divider) are not
        # this entry's fields, so they are filtered out before the flat parser sees them.
        indent = len(line) - len(line.lstrip(" "))
        if re.match(r"-\s*id:", stripped) or 2 <= indent <= 5:
            flat_lines.append(line)
    entries = {}
    for item in _parse_flat_list(flat_lines, item_key="id", strip_quotes=True):
        entries[item["id"]] = item
    return entries


# ---- relocate-domain: move a domain's working file + its whole audit trail between domains-dirs ----
# The scripted form of a plugin extraction's hand-done audit surgery (a deterministic shortcut: pure
# file mechanics, no judgment about WHICH domain should move). Reuses the counter helpers
# (parse_state/render_state) for the script-maintained region and a block-level splitter for the
# hand-maintained `provenance:` list, so an entry's full text — history stanzas, kill logs, section
# comments — travels verbatim.

def _audit_fences(text: str):
    lines = text.splitlines(keepends=True)
    fences = [i for i, l in enumerate(lines) if l.lstrip().startswith("```")]
    return lines, fences


def _split_provenance(body: list) -> tuple:
    """body: the lines after the `provenance:` line up to (not including) its closing fence. Returns
    (entries, trailing) where entries is [(text, domain)]. A run of blank/comment lines between
    entries attaches to the FOLLOWING entry, so a `# domain: X` divider travels with its group."""
    entries, pending, cur, tail, dom = [], [], [], [], [None]

    def flush():
        if cur:
            entries.append(("".join(pending) + "".join(cur), dom[0]))
            keep = tail[:]                       # after an entry, its trailing run leads the next one
        else:
            keep = pending + tail                # nothing emitted yet — carry a leading run forward
        pending.clear(); pending.extend(keep)
        tail.clear(); cur.clear(); dom[0] = None

    for line in body:
        if re.match(r"^- id:", line):
            flush()
            cur.append(line)
            dom[0] = None                       # a provenance id-line carries no domain; a later field does
        elif not cur:
            pending.append(line)
        elif line.strip() == "" or line.lstrip().startswith("#"):
            tail.append(line)                   # provisional: may belong to the next entry
        else:
            cur.extend(tail); tail.clear(); cur.append(line)
            m = re.match(r"\s*domain:\s*(\S+)", line)
            if m and dom[0] is None:
                dom[0] = m.group(1)
    flush()
    return entries, "".join(pending)


def _read_script_state(audit_path: str) -> dict:
    if not os.path.exists(audit_path):
        return empty_state()
    text = open(audit_path).read()
    if MARK_BEGIN not in text:
        return empty_state()
    return parse_state(text.split(MARK_BEGIN, 1)[1].split(MARK_END, 1)[0])


def _write_script_state(audit_path: str, state: dict) -> None:
    block = f"{MARK_BEGIN}\n\n## counters (script-maintained)\n\n{render_state(state)}\n\n{MARK_END}"
    text = open(audit_path).read() if os.path.exists(audit_path) else ""
    if MARK_BEGIN in text:
        head = text.split(MARK_BEGIN, 1)[0]
        tail = text.split(MARK_END, 1)[1] if MARK_END in text else "\n"
        open(audit_path, "w").write(head + block + tail)
    else:                                       # no region yet — append one after existing content
        open(audit_path, "w").write(text.rstrip("\n") + ("\n\n" if text.strip() else "") + block + "\n")


def _ensure_audit_scaffold(audit_path: str) -> None:
    """Guarantee the destination audit has a `provenance:` block AND a corpus-script region, creating a
    minimal file if absent and adding the region to a provenance-only audit — without destroying any
    existing content."""
    if not os.path.exists(audit_path):
        os.makedirs(os.path.dirname(audit_path) or ".", exist_ok=True)
        open(audit_path, "w").write("# Audit record\n\n```yaml\nprovenance:\n```\n\n")
    if MARK_BEGIN not in open(audit_path).read():
        _write_script_state(audit_path, empty_state())
    text = open(audit_path).read()
    if "\n```\n\n<!-- corpus-script:begin" not in text:
        # A script region without a provenance fence before it (a container-only bootstrap):
        # append_audit_provenance anchors on that fence, so insert an empty provenance block.
        idx = text.find(MARK_BEGIN)
        open(audit_path, "w").write(
            text[:idx].rstrip("\n") + "\n\n```yaml\nprovenance:\n```\n\n" + text[idx:])


def relocate_domain(domain: str, from_dir: str, to_dir: str, from_audit: str, to_audit: str) -> dict:
    """Move <domain>.md from from_dir to to_dir and carry its audit trail (provenance entries, counter,
    and efficacy rows for its principles) from from_audit to to_audit. Pure mechanics; refuses to
    overwrite an existing destination working file."""
    src_file = os.path.join(from_dir, f"{domain}.md")
    dst_file = os.path.join(to_dir, f"{domain}.md")
    if not os.path.exists(src_file):
        fail(f"no domain file to relocate: {src_file}")
    if os.path.exists(dst_file):
        fail(f"destination already exists: {dst_file} — refusing to overwrite")
    if not os.path.exists(from_audit):
        fail(f"no source audit: {from_audit}")

    pids = collect_domain_ids(src_file)         # principle ids, for efficacy matching (before the move)

    os.makedirs(to_dir, exist_ok=True)
    shutil.move(src_file, dst_file)

    # provenance — pull the domain's blocks out of the source's hand-maintained list
    text = open(from_audit).read()
    lines, fences = _audit_fences(text)
    if len(fences) < 2:
        fail(f"{from_audit} has no provenance fence pair")
    prov = lines[fences[0] + 1:fences[1]]
    hdr = 0
    while hdr < len(prov) and prov[hdr].strip() != "provenance:":
        hdr += 1
    entries, trailing = _split_provenance(prov[hdr + 1:])
    moved_prov = [t for t, d in entries if d == domain]
    kept_prov = [t for t, d in entries if d != domain]
    new_prov = prov[:hdr + 1] + kept_prov + ([trailing] if trailing else [])
    open(from_audit, "w").write("".join(lines[:fences[0] + 1] + new_prov + lines[fences[1]:]))

    # counter + efficacy — pull from the source's script-maintained region
    s = _read_script_state(from_audit)
    moved_counters = [c for c in s["counters"] if c.get("domain") == domain]
    s["counters"] = [c for c in s["counters"] if c.get("domain") != domain]
    moved_eff = [e for e in s["efficacy"] if e.get("id") in pids]
    s["efficacy"] = [e for e in s["efficacy"] if e.get("id") not in pids]
    _write_script_state(from_audit, s)

    # destination — scaffold if needed, then append provenance + counter + efficacy
    _ensure_audit_scaffold(to_audit)
    if moved_prov:
        append_audit_provenance(to_audit, "".join(moved_prov))
    d = _read_script_state(to_audit)
    d["counters"].extend(moved_counters)
    d["efficacy"].extend(moved_eff)
    _write_script_state(to_audit, d)

    return {"provenance": len(moved_prov), "counters": len(moved_counters), "efficacy": len(moved_eff),
            "src": src_file, "dst": dst_file}


def cmd_relocate_domain(project: "Project", args) -> None:
    from_dir, to_dir = args.from_dir, args.to_dir
    r = relocate_domain(
        args.domain, from_dir, to_dir,
        args.from_audit or os.path.join(from_dir, "audit.md"),
        args.to_audit or os.path.join(to_dir, "audit.md"),
    )
    print(f"relocated domain '{args.domain}': {r['src']} -> {r['dst']}  "
          f"(provenance {r['provenance']}, counter {r['counters']}, efficacy {r['efficacy']} moved)")


def migrate_kill_log(domains_dir: str, audit_path: str) -> None:
    """Move every working file's `killed:` entries into the audit file's kill log (operator
    decision 2026-08-07 — see kernel.md, "Killed entries"). Leaves each working file's `killed:`
    marker empty; `verify` flags any kill entry that reappears. Idempotent: a pool with no
    working-file kills is a no-op. Registered as schema migration 001; also runnable directly
    via `migrate-kill-log` for a pool with no config to stamp (a plugin's own domains-dir)."""
    # Phase 1 — read-only: parse every working file's killed section before touching anything,
    # so a malformed file aborts with the whole pool still intact. A file whose yaml fence never
    # closes after `killed:` (seen in the wild) is treated as running to end-of-file.
    relocated = []
    rewrites = []
    for name in sorted(os.listdir(domains_dir)):
        if not name.endswith(".md") or name == "audit.md":
            continue
        path = os.path.join(domains_dir, name)
        text = open(path).read()
        idx = text.find("\nkilled:")
        if idx == -1:
            continue
        fence_idx = text.find("```", idx)
        boundary = fence_idx if fence_idx != -1 else len(text)
        section = text[idx + len("\nkilled:"):boundary]
        blocks = [b.rstrip() for b in re.split(r"\n(?=- id:)", section.strip("\n"))
                  if b.strip().startswith("- id:")]
        if not blocks:
            continue
        rewrites.append((path, text[:idx] + "\nkilled:\n" + text[boundary:]))
        for block in blocks:
            lines = block.split("\n")
            relocated.append("\n".join([lines[0], f"  domain: {name[:-3]}"] + lines[1:]))
        print(f"{name[:-3]}: relocating {len(blocks)} kill entr{'y' if len(blocks) == 1 else 'ies'}")
    if not relocated:
        print("nothing to migrate — no working file carries kill entries")
        return
    # Phase 2 — audit first, then strip. If a strip fails midway, kills exist in both places:
    # `verify` flags the leftover working-file entries and a re-run strips them without
    # re-appending (already-logged ids are skipped below).
    already_logged = audit_kill_ids(audit_path)
    appended = 0
    for block in relocated:
        entry_id = re.match(r"- id:\s*(\S+)", block).group(1)
        if entry_id in already_logged:
            continue
        append_audit_kill_entry(audit_path, block + "\n")
        appended += 1
    for path, new_text in rewrites:
        open(path, "w").write(new_text)
    print(f"{audit_path}: kill log grew by {appended} entr{'y' if appended == 1 else 'ies'} "
          f"({len(relocated) - appended} already logged)")


def cmd_migrate_kill_log(args) -> None:
    migrate_kill_log(args.domains_dir, args.audit)


# ── pool schema migrations ───────────────────────────────────────────────────
#
# Storage-format changes to a pool (working files + audit) register here as numbered, idempotent,
# ordered migrations. A pool records the last migration applied as `schema-version: N` in its
# config.md (absent = 0, pre-versioning); `migrate` runs everything between the pool's stamp and
# SCHEMA_VERSION and re-stamps, and `verify` refuses to reconcile a stale pool so the fix is one
# named command instead of a symptom hunt. Content changes never go through here — they flow
# through import-default-pool's candidate queue and the ratify gate.

MIGRATIONS = [
    (1, "kill-log relocation: working-file killed: entries move to the audit kill log",
     migrate_kill_log),
]
SCHEMA_VERSION = MIGRATIONS[-1][0]


def read_schema_version(config_path: str) -> int:
    if not os.path.exists(config_path):
        return 0
    m = re.search(r"^schema-version:\s*(\d+)\s*$", open(config_path).read(), re.MULTILINE)
    return int(m.group(1)) if m else 0


def stamp_schema_version(config_path: str, version: int) -> None:
    text = open(config_path).read()
    if re.search(r"^schema-version:\s*\d+\s*$", text, re.MULTILINE):
        text = re.sub(r"^schema-version:\s*\d+\s*$", f"schema-version: {version}", text,
                      count=1, flags=re.MULTILINE)
    else:
        text = text.rstrip("\n") + f"\n\nschema-version: {version}\n"
    open(config_path, "w").write(text)


def cmd_migrate(project: Project, _args) -> None:
    current = read_schema_version(project.config_path)
    if current >= SCHEMA_VERSION:
        print(f"schema-version {current} — already current, nothing to migrate")
        return
    for version, desc, fn in MIGRATIONS:
        if version <= current:
            continue
        print(f"migration {version:03d}: {desc}")
        fn(project.domains_dir, project.audit_path)
        stamp_schema_version(project.config_path, version)
    print(f"pool migrated: schema-version {current} -> {SCHEMA_VERSION} ({project.config_path})")


def init_config_body(name, language, framework, package_manager, has_ui, styling,
                     lint, check, build, test) -> str:
    """The `.corpora/config.md` a fresh project starts from — the engine's own bootstrap output, the
    symmetric counterpart to praxis_init's root marker. Structure, not judgment (the shape values are
    detected by the bootstrap phase's judgment and passed in); this just writes the schema."""
    name_line = f"name: {name}\n" if name else ""
    ui_block = "\n## ui-library\npath: .corpora/ui-library.md\n" if has_ui == "yes" else ""
    return (
        "# Config\n\n"
        "Read this file at the start of any spawn's session. It declares the project's shape,\n"
        "registered project utilities, libraries, and verification commands. Generated by\n"
        "`corpus.py init` (corpora:bootstrap); edit by hand as the project changes.\n\n"
        "## project-shape\n"
        f"{name_line}"
        f"language: {language}\n"
        f"framework: {framework}\n"
        f"package-manager: {package_manager}\n"
        f"has-ui: {has_ui}\n"
        f"styling: {styling}\n\n"
        "## utilities\nutilities: []\n"
        f"{ui_block}\n"
        "## verification-commands\n"
        f"lint: {lint}\n"
        f"check: {check}\n"
        f"build: {build}\n"
        f"test: {test}\n\n"
        f"schema-version: {SCHEMA_VERSION}\n"
    )


def cmd_init(args) -> None:
    root = os.path.abspath(args.root)
    # New bootstraps land on the standard `.corpora/`; an existing legacy `.corpora/config.md` is
    # rewritten in place under --force rather than growing a second config beside it.
    config = Project(root).config_path
    if not os.path.exists(config):
        config = os.path.join(root, ".corpora", "config.md")
    if os.path.exists(config) and not args.force:
        fail(f"{config} already exists — this project is already bootstrapped (use --force to rewrite)")
    os.makedirs(os.path.dirname(config), exist_ok=True)
    with open(config, "w") as f:
        f.write(init_config_body(args.name, args.language, args.framework, args.package_manager,
                                 args.has_ui, args.styling, args.lint, args.check, args.build, args.test))
    ledger = os.path.join(os.path.dirname(config), "deterministic-shortcut-candidates.md")
    if not os.path.exists(ledger):
        with open(ledger, "w") as f:
            f.write("# Deterministic shortcut candidates\n\n```yaml\ncandidates: []\n```\n")
    print(f"corpora bootstrapped: {config}")
    if args.has_ui == "yes":
        print("has-ui: yes — next, run the uiux plugin's library-init phase to stand up the design libraries.")
    print("consider `corpus.py import-default-pool` to seed the domain corpus from matching defaults.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=".", help="project root (contains .corpora/)")
    ap.add_argument("--for-file", default="",
                     help="resolve --root automatically from this file's nearest-ancestor "
                          ".corpora/config.md (kernel.md, 'Monorepo root resolution') instead of "
                          "passing --root explicitly — the standard way to invoke corpus.py for "
                          "an actual task, so no session has to work out which root governs it")
    ap.add_argument("--root-name", default="",
                     help="resolve --root by a sibling root's declared or directory name, found "
                          "by a downward walk from cwd (use the standalone `resolve-root --name "
                          "--search-from` for a different starting point) — for deliberately "
                          "dispatching into a formalized section of the same project rather than "
                          "the root a touched file happens to resolve to (kernel.md, 'Monorepo "
                          "root resolution'); mutually exclusive with --for-file")
    sub = ap.add_subparsers(dest="cmd", required=True)
    layer_help = "override to work on any domains-dir + audit.md pair — a project's own " \
                 ".corpora/domains or this skill's own domains/ — not only a project's own corpora"
    m = sub.add_parser("measure")
    m.add_argument("--domains-dir", default="", help=layer_help)
    m.add_argument("--audit", default="", help=layer_help)
    v = sub.add_parser("verify")
    v.add_argument("--domains-dir", default="", help=layer_help)
    v.add_argument("--audit", default="", help=layer_help)
    g = sub.add_parser("record-gate")
    g.add_argument("--domains-dir", default="", help=layer_help)
    g.add_argument("--audit", default="", help=layer_help)
    g.add_argument("--domain", required=True)
    g.add_argument("--ratified", type=int, default=0)
    g.add_argument("--killed", type=int, default=0)
    g.add_argument("--graduated", type=int, default=0,
                   help="principles moved from principles: to conventions: this gate")
    g.add_argument("--violations", type=int, default=0)
    g.add_argument("--ui-drift", action="store_true")
    g.add_argument("--fired", default="", help="comma-separated principle ids")
    g.add_argument("--violated", default="", help="comma-separated principle ids")
    g.add_argument("--idle", default="", help="comma-separated principle ids")
    g.add_argument("--co-occurs-with", default="",
                   help="comma-separated domain names loaded alongside --domain in the same spawn")
    sub.add_parser("triggers")
    sub.add_parser("lint-deterministic-shortcut-candidates")
    sub.add_parser("deterministic-shortcut-candidates")
    uc = sub.add_parser("record-deterministic-shortcut-candidate")
    uc.add_argument("--id", required=True)
    uc.add_argument("--operation-shape", required=True)
    uc.add_argument("--workstream", required=True)
    uc.add_argument("--burden", required=True)
    uc.add_argument("--date", default="", help="YYYY-MM-DD; defaults to today")
    us = sub.add_parser("set-deterministic-shortcut-status")
    us.add_argument("--id", required=True)
    us.add_argument("--status", required=True, choices=sorted(SHORTCUT_STATUS_ENUM))
    us.add_argument("--reason", default="")
    r = sub.add_parser("retro-done")
    r.add_argument("--domain", required=True)
    r.add_argument("--domains-dir", default="", help=layer_help)
    r.add_argument("--audit", default="", help=layer_help)
    sd = sub.add_parser("sync-done")
    sd.add_argument("--domains-dir", default="", help=layer_help)
    sd.add_argument("--audit", default="", help=layer_help)
    esp = sub.add_parser("emit-spawn-parts",
                         help="emit the engine-contributed parts of a spawn prompt (stance frame, "
                              "domain bodies, handoff schema) + composition problems as JSON, for "
                              "praxis to compose into its prompt skeleton")
    esp.add_argument("--domains", required=True, help="comma-separated domain names")
    esp.add_argument("--domains-dir", default="", help=layer_help)
    esp.add_argument("--json", action="store_true", help="pretty-print the JSON payload")
    sr = sub.add_parser("screenshot-record")
    sr.add_argument("--screen", required=True)
    sr.add_argument("--variant", required=True)
    sr.add_argument("--path", required=True)
    sr.add_argument("--components", default="", help="comma-separated component names")
    sm = sub.add_parser("screenshot-mark-stale")
    sm.add_argument("--screens", default="", help="comma-separated screen ids touched directly")
    sm.add_argument("--components", default="", help="comma-separated shared components changed")
    sub.add_parser("screenshot-status")
    sl = sub.add_parser("screenshot-lookup")
    sl.add_argument("--component", required=True)
    sub.add_parser("lint-screenshots")
    mkl = sub.add_parser("migrate-kill-log", help="one-time per pool: move working-file killed: "
                                                  "entries into the audit file's kill log — works on "
                                                  "any domains-dir + audit.md pair (schema migration "
                                                  "001's body; prefer `migrate` for a pool with a config)")
    mkl.add_argument("--domains-dir", required=True)
    mkl.add_argument("--audit", required=True)
    sub.add_parser("migrate", help="run every schema migration between this pool's "
                                   "schema-version stamp and current, in order, and re-stamp "
                                   "config.md — idempotent; verify refuses a stale pool until this runs")
    ld = sub.add_parser("lint-domains", help="works on any domains-dir, not only a project's .corpora/domains — "
                                              "validates frontmatter (subject/posture/applies-when/units-of-work)")
    ld.add_argument("--domains-dir", required=True)
    rr = sub.add_parser("resolve-root", help="--file: nearest-ancestor walk from a file to the "
                                              "corpora root that governs it (upward). --name: "
                                              "the named root's path (downward, from --search-from) "
                                              "— for deliberately dispatching into a sibling section")
    rr.add_argument("--file", default="", help="upward lookup — resolves the root governing this file")
    rr.add_argument("--name", default="", help="downward lookup — resolves a root by its declared "
                                                 "or directory name; use instead of --file")
    rr.add_argument("--search-from", default=".", help="where the downward walk for --name starts "
                                                         "(defaults to cwd)")
    crb = sub.add_parser("check-root-boundary", help="fail (exit 2) if a task's touched files resolve "
                                                       "to more than one corpora root — the monorepo "
                                                       "split signal (proposals/domain-repo-import.md)")
    crb.add_argument("--files", required=True, help="comma-separated file paths")
    lr = sub.add_parser("list-roots", help="downward walk from --search-from, listing every corpora "
                                            "root found (name: path) — discovery for dispatching "
                                            "into a formalized section of the same project")
    lr.add_argument("--search-from", default=".", help="defaults to cwd")
    mf = sub.add_parser("manifest", help="emit the machine-readable domain index for this project's own "
                                          ".corpora/domains/ (or --domains-dir), for a process layer to "
                                          "select against without reading prose")
    mf.add_argument("--json", action="store_true")
    mf.add_argument("--domains-dir", default="", help=layer_help)
    sel = sub.add_parser("select", help="deterministic domain selection for a unit-of-work, evaluated "
                                         "against .corpora/config.md — no model in the loop")
    sel.add_argument("--unit-of-work", required=True)
    sel.add_argument("--config", default="", help="defaults to .corpora/config.md under --root")
    sel.add_argument("--json", action="store_true")
    sel.add_argument("--domains-dir", default="", help=layer_help)
    cc = sub.add_parser("check-composition", help="fail if a domain list mixes subjects or includes "
                                                    "a posture: generative domain (kernel.md, 'The hard line')")
    cc.add_argument("--domains", required=True, help="comma-separated domain names")
    cc.add_argument("--domains-dir", default="", help=layer_help)
    il = sub.add_parser("import-list", help="browse a source domains-dir's principles+conventions, "
                                              "flagging which ids already exist in the target — "
                                              "read-only, proposes nothing")
    il.add_argument("--source", required=True, help="path to the source domains-dir")
    il.add_argument("--target-domains-dir", default="", help="defaults to this project's own .corpora/domains")
    ic = sub.add_parser("import-candidate", help="propose one principle or convention from a source "
                                                   "domains-dir as a candidate, with imported-from provenance")
    ic.add_argument("--source", required=True, help="path to the source domains-dir")
    ic.add_argument("--domain", required=True, help="the entry's domain in the source")
    ic.add_argument("--id", required=True, help="the entry's id in the source")
    ic.add_argument("--as-domain", default="", help="propose into a different destination domain")
    ic.add_argument("--as-id", default="", help="propose under a different id (e.g. on collision)")
    ic.add_argument("--target-domains-dir", default="", help="defaults to this project's own .corpora/domains")
    ic.add_argument("--output", default="", help="candidates file; defaults to .corpora/import-candidates.md")
    idp = sub.add_parser("import-default-pool", help="propose every principle+convention from every "
                                                       "domain in the source whose applies-when already "
                                                       "matches this project's shape — the bootstrap fast path")
    idp.add_argument("--source", default="", help="defaults to this skill's own domains/")
    idp.add_argument("--config", default="", help="defaults to .corpora/config.md under --root")
    idp.add_argument("--target-domains-dir", default="", help="defaults to this project's own .corpora/domains")
    idp.add_argument("--output", default="", help="candidates file; defaults to .corpora/import-candidates.md")
    ap_ = sub.add_parser("add-principle", help="write a freshly-authored or mined principle into "
                                                "a domain working file plus its audit.md "
                                                "provenance entry, and record the gate in one "
                                                "atomic, scripted step — no hand edits to either "
                                                "file. Principles only — a convention is graduated "
                                                "from an existing ratified principle, not authored "
                                                "fresh (kernel.md, write-back format)")
    ap_.add_argument("--domains-dir", default="", help=layer_help)
    ap_.add_argument("--audit", default="", help=layer_help)
    ap_.add_argument("--domain", required=True)
    ap_.add_argument("--id", required=True)
    ap_.add_argument("--rule", required=True)
    ap_.add_argument("--condition", required=True)
    ap_.add_argument("--reason", required=True)
    ap_.add_argument("--see-also", default="")
    ap_.add_argument("--provenance", required=True, help="free text: date, source, context")
    ap_.add_argument("--kind", default="", choices=["", "judgment", "knowledge"])
    ads = sub.add_parser("adopt-domain-shell", help="create an empty domain container (frontmatter "
                                                     "copied verbatim from a source domain file) so a "
                                                     "plugin's judgment face can be staged into a "
                                                     "project that doesn't have the domain yet — "
                                                     "container only, no principles, no audit entries; "
                                                     "idempotent and non-destructive")
    ads.add_argument("--source", required=True, help="path to a source domain file whose frontmatter "
                                                     "to copy; the shell is named after its file stem")
    ads.add_argument("--domains-dir", default="", help=layer_help)
    ric = sub.add_parser("ratify-import-candidate", help="write an entry already queued by "
                                                           "import-candidate/import-default-pool "
                                                           "into its destination domain plus "
                                                           "audit.md provenance, record the gate, "
                                                           "and remove it from the candidates file "
                                                           "— the scripted counterpart to kernel.md's "
                                                           "'Write-back format'")
    ric.add_argument("--domains-dir", default="", help=layer_help)
    ric.add_argument("--audit", default="", help=layer_help)
    ric.add_argument("--source", default="", help="defaults to .corpora/import-candidates.md")
    ric.add_argument("--id", required=True, help="the candidate's id in the source candidates file")
    ric.add_argument("--as-domain", default="", help="overrides the candidate's own recorded domains:")
    ric.add_argument("--as-id", default="", help="write back under a different id (e.g. on collision)")
    rd = sub.add_parser("relocate-domain", help="move a domain's working file AND its whole audit "
                                                 "trail (provenance + counter + efficacy) from one "
                                                 "domains-dir to another — the scripted form of a "
                                                 "plugin extraction's hand-done audit surgery. Pure "
                                                 "mechanics: it moves what is there, it does not decide "
                                                 "what should move (that judgment stays at the gate)")
    rd.add_argument("--domain", required=True, help="the domain name (its file is <domain>.md)")
    rd.add_argument("--from-dir", required=True, help="source domains-dir holding <domain>.md")
    rd.add_argument("--to-dir", required=True, help="destination domains-dir (created if absent)")
    rd.add_argument("--from-audit", default="", help="defaults to <from-dir>/audit.md")
    rd.add_argument("--to-audit", default="", help="defaults to <to-dir>/audit.md (scaffolded if absent)")
    md = sub.add_parser("migrate-domains", help="one-time: materialize a pre-dissolution project's "
                                                  "live seed/project merge into its own .corpora/domains/ "
                                                  "(praxis-plugin/phases/domain-repo-migration.md)")
    md.add_argument("--source", default="", help="defaults to this skill's own domains/")
    md.add_argument("--config", default="", help="defaults to .corpora/config.md under --root")
    md.add_argument("--domains", default="", help="comma-separated domain names; defaults to the "
                                                    "default-pool match plus every domain the project already has")
    suw = sub.add_parser("sync-units-of-work", help="additively sync each domain's units-of-work "
                                                      "list from the seed template — migrate-domains "
                                                      "merges principle content but leaves an "
                                                      "already-materialized domain's own frontmatter "
                                                      "untouched, so this list can drift behind the "
                                                      "seed (e.g. a domain gains debug-issue in the "
                                                      "seed after a project's own copy was made). "
                                                      "Mechanical composition-scope fix, not a "
                                                      "principle — no ratify gate involved.")
    suw.add_argument("--source", default="", help="defaults to this skill's own domains/")
    suw.add_argument("--domains", default="", help="comma-separated domain names; defaults to "
                                                     "every domain the project already has")
    suw.add_argument("--apply", action="store_true", help="write the changes; omit for a dry-run report")
    sub.add_parser("lint-queue", help="validate .corpora/queue.md structurally")
    sub.add_parser("queue-status", help="read-only: each task's status and startability, each "
                                         "question's resolution state")
    qss = sub.add_parser("queue-set-status", help="set a task's status in-place — the mechanical "
                                                   "half of planning.md's 'orchestrator updates "
                                                   "status in-place' rule")
    qss.add_argument("--id", required=True)
    qss.add_argument("--status", required=True, choices=sorted(TASK_STATUS_ENUM))
    qrq = sub.add_parser("queue-resolve-question", help="resolve an open question in-place")
    qrq.add_argument("--id", required=True)
    qrq.add_argument("--answer", required=True)
    qg = sub.add_parser("queue-graduate", help="remove a not-yet-specified entry once the real "
                                                "task it resolves has been added to tasks:")
    qg.add_argument("--id", required=True, help="the not-yet-specified entry's id")
    qg.add_argument("--task-id", required=True, help="the task id it graduated into")
    qmo = sub.add_parser("queue-mark-out-of-scope", help="close a task or not-yet-specified "
                                                           "entry into the out-of-scope ledger")
    qmo.add_argument("--id", required=True, help="a task id or a not-yet-specified entry's id")
    qmo.add_argument("--reason", required=True)
    ini = sub.add_parser("init", help="bootstrap a project: write .corpora/config.md (the engine's own "
                                       "bootstrap, symmetric to praxis_init's root marker). Uses the "
                                       "global --root, e.g. `corpus.py --root DIR init --has-ui yes`.")
    ini.add_argument("--name", default="", help="optional label for this corpora root")
    ini.add_argument("--language", default="none")
    ini.add_argument("--framework", default="none")
    ini.add_argument("--package-manager", default="none", dest="package_manager")
    ini.add_argument("--has-ui", default="no", choices=["yes", "no"], dest="has_ui")
    ini.add_argument("--styling", default="none")
    ini.add_argument("--lint", default="none")
    ini.add_argument("--check", default="none")
    ini.add_argument("--build", default="none")
    ini.add_argument("--test", default="none")
    ini.add_argument("--force", action="store_true", help="overwrite an existing config.md")

    args = ap.parse_args()

    no_project = {"migrate-kill-log": cmd_migrate_kill_log,
                  "lint-domains": cmd_lint_domains, "resolve-root": cmd_resolve_root,
                  "check-root-boundary": cmd_check_root_boundary, "list-roots": cmd_list_roots,
                  "init": cmd_init}
    if args.cmd in no_project:
        no_project[args.cmd](args)
        return

    if args.for_file and args.root_name:
        fail("--for-file and --root-name are mutually exclusive — pick one")
    root = args.root
    if args.for_file:
        resolved = find_root_config(args.for_file)
        if not resolved:
            fail(f"no corpora root found above {args.for_file} — pass --root explicitly if this "
                 "is a brand-new root not yet bootstrapped")
        root = resolved
    elif args.root_name:
        roots = find_all_root_configs(".")
        matches = [r for r in roots if root_name_for(r) == args.root_name]
        if not matches:
            available = ", ".join(root_name_for(r) for r in roots) or "none"
            fail(f"no corpora root named '{args.root_name}' under cwd — available: {available}")
        if len(matches) > 1:
            fail(f"'{args.root_name}' is ambiguous — matches {len(matches)} roots: "
                 f"{', '.join(matches)}. Use --root with the exact path instead.")
        root = matches[0]

    project = Project(os.path.abspath(root),
                      domains_dir=getattr(args, "domains_dir", "") or "",
                      audit_path=getattr(args, "audit", "") or "")
    {"measure": cmd_measure, "verify": cmd_verify, "record-gate": cmd_record_gate, "triggers": cmd_triggers,
     "lint-deterministic-shortcut-candidates": cmd_lint_deterministic_shortcut_candidates,
     "deterministic-shortcut-candidates": cmd_deterministic_shortcut_candidates,
     "record-deterministic-shortcut-candidate": cmd_record_deterministic_shortcut_candidate,
     "set-deterministic-shortcut-status": cmd_set_deterministic_shortcut_status,
     "retro-done": cmd_retro_done, "sync-done": cmd_sync_done, "migrate": cmd_migrate,
     "emit-spawn-parts": cmd_emit_spawn_parts,
     "screenshot-record": cmd_screenshot_record,
     "screenshot-mark-stale": cmd_screenshot_mark_stale,
     "screenshot-status": cmd_screenshot_status,
     "screenshot-lookup": cmd_screenshot_lookup,
     "lint-screenshots": cmd_lint_screenshots,
     "manifest": cmd_manifest, "select": cmd_select,
     "check-composition": cmd_check_composition,
     "add-principle": cmd_add_principle, "adopt-domain-shell": cmd_adopt_domain_shell,
     "ratify-import-candidate": cmd_ratify_import_candidate,
     "import-list": cmd_import_list, "import-candidate": cmd_import_candidate,
     "import-default-pool": cmd_import_default_pool, "migrate-domains": cmd_migrate_domains,
     "relocate-domain": cmd_relocate_domain,
     "sync-units-of-work": cmd_sync_units_of_work,
     "lint-queue": cmd_lint_queue, "queue-status": cmd_queue_status,
     "queue-set-status": cmd_queue_set_status,
     "queue-resolve-question": cmd_queue_resolve_question,
     "queue-graduate": cmd_queue_graduate,
     "queue-mark-out-of-scope": cmd_queue_mark_out_of_scope}[args.cmd](project, args)


if __name__ == "__main__":
    main()
