# Script alignment scan — praxis + corpora + plugins

unit-of-work: scan-architecture · workstream: script-alignment · stance: convergent · 2026-08-07

Scope read: `praxis/scripts/*.py` (16 files, ~3,150 lines), `corpora/scripts/` (corpus.py 3,282 lines + 3 sh hooks), `corpora/praxis-plugin/scripts/` (5 files), `plugins/uiux/praxis/scripts/` (2 files), the three `~/.claude/hooks/praxis-*.sh` hooks, `~/.claude/mcp-servers/praxis-front-door/server.py`, and both test trees. Churn-weighted per `scan-scope-by-recent-churn`: the lease/spawn-default work (units.py, server.py, gate/stamp hooks), the dot-dir sweep, and the import-sync machinery in corpus.py are the hot spots; findings concentrate there.

Vocabulary: findings use the codebase-design glossary (module / interface / implementation / depth / seam / leverage / locality). "Dot-dir sweep" below names the recent `.praxis/`/`.corpora/` state-dir migration (commits b0cefc6, a32b240, 5466f4c); "fail-open" names the hooks' recorded discipline of exiting 0 on any ambiguity.

Findings are proposals ranked by leverage (payoff per unit of change). No source was edited.

---

## Tier 1 — live breakage and drift the recent work left behind

### 1. stop-check.sh calls a subcommand that no longer exists — the Stop hook now blocks with an argparse error

- **Where:** `corpora/scripts/stop-check.sh:26` (`corpus.py --root . verify-chunks`); the removal notice is `corpora/scripts/corpus.py:74-75` ("verify-chunks — moved to praxis's chunk_ledger.py").
- **What's wrong:** dead interface. Verified live: `python3 corpora/scripts/corpus.py --root . verify-chunks` exits 2 with an argparse usage error. The hook treats any nonzero exit as drift and emits `{"decision": "block", ...}` with that usage text as the reason — so in any registered corpora project, *every* session Stop is blocked with a meaningless error. The chunk-bookkeeping migration to `praxis/scripts/chunk_ledger.py` (which has its own `verify` subcommand, `chunk_ledger.py:293-325`) never updated this consumer.
- **Proposed change:** either point the hook at `chunk_ledger.py verify --root . --engine-plugins <root slot>` (it needs the engine slot the corpora manifest registers), or delete the check and let the hook exit 0 — the reconciliation now lives praxis-side. Whichever way, add the smoke test in finding 15.
- **Cost/risk:** one-file change; low. Risk of the chunk_ledger route: the hook gains a praxis dependency — acceptable, the whole system already assumes praxis is provisioned (session-start.sh points at begin_work).

### 2. The uiux plugin's scripts missed the dot-dir sweep — wrong facts on any `.corpora/` project

- **Where:** `plugins/uiux/praxis/scripts/library_state.py:44-46` (`DEFAULT_UI = "corpora/ui-library.md"`, `MANIFEST = "corpora/screenshots/manifest.md"`) and `:56` (`config = root / "corpora" / "config.md"`); `plugins/uiux/praxis/scripts/deferred_queue.py:63` and `:123` (`os.path.join(root, "corpora", ...)`).
- **What's wrong:** drift. corpus.py resolves the state dir as `.corpora` first, legacy `corpora` second (`corpus.py:140-142`), and the corpora sh hooks check both (`session-start.sh:18-20`). These two scripts still hardcode the legacy name only. On a dot-dir project, `library_state state` reads no config → reports `has_ui: no` → "no library phase applies", and `deferred_queue lint` reports the queue absent. The plugin's own tests mask this: `plugins/uiux/praxis/tests/test_library_state.py:17-18` builds only the legacy `corpora/` layout, so they pass.
- **Proposed change:** give both scripts the same two-name resolution corpus.py uses (a shared `state_dir(root)` helper inside each script — cross-skill promotion is not warranted, see finding 12), and add a `.corpora/`-layout test case beside the legacy one.
- **Cost/risk:** small, mechanical; low risk. The manifest default paths (`DEFAULT_UI` etc.) also need the resolved base, not a literal prefix.

### 3. Stale prose the sweep left in docstrings — five spots where the words contradict the code

- **Where / what:**
  - `corpus.py:136-137` — comment says "bare `.corpora/` is recognized for existing projects"; the legacy fallback the code implements (`base = "corpora"`, line 140) is bare `corpora/`. The sweep inverted the sentence.
  - `corpus.py:976` — `has_root_config` docstring: "carries `.corpora/config.md` (standard) or `.corpora/config.md` (legacy)" — the same name twice; the second should be `corpora/config.md`.
  - `praxis/scripts/praxis_init.py:2-4,18-19` — docstring says init "writes its `praxis/config.md` marker"; `praxis_dir` lands a fresh root on `.praxis/config.md` (root_tree.py:40-48), which is what actually gets written.
  - `~/.claude/mcp-servers/praxis-front-door/server.py:357` (compose_spawn docstring) and `~/.claude/hooks/praxis-payload-read-stamp.sh:3` — both name `<root>/praxis/.frame-payload.md`; the write path is `.praxis/` on standard roots (server.py:119 via `praxis_dir`). The read-stamp hook's *code* handles both (line 22); only its header prose is stale.
- **What's wrong:** prose drift — each is a docstring stating "why/where" that no longer matches behavior, exactly the misdirection docstrings exist to prevent.
- **Proposed change:** wording fixes only, no behavior change.
- **Cost/risk:** trivial; none.

### 4. begin_work's LEASE warning fires on read targets — the fix belongs in server.py's warning, not in units.py or the gate

- **Where:** `server.py:292-298` (`out_of_surface = [p for p in ([target] if target else []) + file_list if _outside(p)]` → "LEASE: N given path(s) fall outside this unit's edit surface … this is the wrong unit of work").
- **What's wrong:** interface conflation. `begin_work`'s `files`/`target` are documented as "the paths the task *touches*" (server.py:231) — inputs and edit targets alike — but the warning interprets them all as edit targets. For a scan/review unit (edit-surface `docs/*, *.md`) whose given files are the code being *read*, the warning is guaranteed noise on every correctly-framed call. The lease machinery itself is sound at both other layers: `units.py` declares the surface correctly, and the gate hook (`praxis-frame-gate.sh:94-115`) checks *actual edits*, which is the ground truth. Only the advance-notice heuristic in begin_work lacks the read/write distinction.
- **Proposed change (in preference order):**
  1. Cheap: reword and downgrade — "N given path(s) are outside this unit's edit surface; fine if they are read inputs (the gate will deny any actual edit to them); wrong unit if they are the edit targets." Keeps the signal, removes the false accusation.
  2. Structural, if the noise persists: split the tool interface — an optional `edits:` parameter distinct from `files:`; warn only on declared edits. Costs every caller a new concept, so only worth it with evidence option 1 still misleads.
  - Not in `units.py` (surface semantics are per-unit declarations and correct), not in the gate (it already judges the real event).
- **Cost/risk:** option 1 is a string change; nil risk. Option 2 widens the tool interface — defer per two-adapters-before-a-real-seam.

### 5. server.py: redundant local imports and mid-file imports left by incremental edits

- **Where:** `server.py:93, 401, 428` re-`import root_tree` inside functions though it is imported at module top (line 47); `from contextlib import contextmanager` sits mid-file at line 86; `import re` inside `_phase_inventory` (line 154); `import hashlib/os/json` inside `work_status` (lines 425-427).
- **What's wrong:** accretion noise — each was added at the nearest indentation during the front-door build-out; none is a deliberate cycle-avoidance (root_tree is already loaded).
- **Proposed change:** hoist all to the top-of-file import block; delete the shadowing locals.
- **Cost/risk:** trivial; none.

---

## Tier 2 — structure: side effects, shallow modules, seams

### 6. build_frame's marker-touch side effect is the root cause of `_preserved_markers` — move the write to the write path

- **Where:** `praxis/scripts/frame.py:217` (`touch_frame_marker(root)` inside `build_frame`); the workaround: `server.py:89-107` (`_preserved_markers` snapshots every marker under base and restores after) guarding `compose_spawn`'s read at `server.py:367-368`.
- **What's wrong:** a read-path function with a write side effect — `build_frame` is the fact bundle ("facts only, no decision", its own docstring) yet it stamps the freshness marker as a side effect. Every read-only consumer must now know this (interface complexity leaking implementation), and server.py pays with a snapshot/restore context manager that walks all roots per compose_spawn call and has an inherent crash-window race (die between touch and restore → clobbered JSON marker → gate behavior changes).
- **Proposed change:** lift the touch out of `build_frame` into the callers that frame *for real*: `frame.main` (preserving the bare-timestamp CLI path the gate's backward-compat branch expects, gate hook lines 173-176) and `begin_work` (which already writes the richer JSON marker at server.py:337 — note today a begin_work call touches the marker **twice**: bare via build_frame, then JSON). Then delete `_preserved_markers` entirely — the deletion test passes: its complexity vanishes with the side effect, reappearing nowhere.
- **Cost/risk:** moderate — `route.build_route`, `front_door`, `frame_store.cmd_write` call `build_frame` too; each needs the explicit-touch decision made once (frame_store's write path should touch; route/front_door reads should not, which is itself a behavior *correction* — today `route --json` as a pure query silently refreshes the edit gate's freshness window). Tests: `praxis/tests/test_frame.py` has no marker assertions (verified), so the suite moves cleanly; add a regression test that read paths leave the marker untouched.

### 7. front_door.py fails the deletion test now that the MCP server is the front door

- **Where:** `praxis/scripts/front_door.py` (87 lines). `build_front_door` = `route.build_route` + `resolve_targets` + a `targets_known` bool (lines 32-38); the rest is an argparse mirror of route.py's.
- **What's wrong:** shallow module — its interface (all of route's flags plus `--ask`) is as large as route's while its added behavior is one tagged message for the zero-target case. Meanwhile the *actual* front door (`server.py`, which docs and hooks now point everything at — session-start.sh:23-25, SKILL.md) imports `frame` and `route` directly and never imports front_door.py, and has grown capabilities front_door.py lacks (target validation `_validate_targets`, phase inventory, lease relay). Two front doors, one drifting.
- **Real friction named (per dont-relitigate-adr): the no-MCP degraded path is a stated praxis discipline ("with no engine registered praxis still reports the deterministic facts"), so a CLI entry must survive.** The friction justifying change is the drift itself: the CLI front door no longer says what the tool front door says.
- **Proposed change:** fold the raw-ask degrade (accept zero targets, print "resolve to files + unit-of-work first") into route.py — it is one branch — and retire front_door.py, updating SKILL.md/framing.md pointers to `route.py`. Alternative if the separate raw-ask entry is judged load-bearing vocabulary: keep it but make it delegate its printing wholly to route and inherit `_validate_targets` so the two doors can't diverge further.
- **Cost/risk:** low-moderate; test_front_door.py (95 lines) migrates to route tests. Doc pointers must move in the same change.

### 8. The engine-call wrappers are triplicated — `engine.py` is the LCA

- **Where:** the `compose` capability call: `frame.py:50-78` (`engine_compose`) and `chunk_ledger.py:127-141` (`compose`) — same params, same three-way error taxonomy (not ran / nonzero / unparseable), independently maintained note strings. The `spawn-parts` call: `server.py:69-83` (`_spawn_parts`) and `spawn_prompt.py:45-64` (`engine_spawn_parts`) — same shape again.
- **What's wrong:** duplication within python with an obvious lowest common ancestor: every copy already imports `engine`, and the copies have started to diverge cosmetically (frame's returns `warnings`-joined notes; chunk_ledger's does not). A capability's JSON-decode-and-extract discipline is engine-binding knowledge, not frame or ledger knowledge.
- **Proposed change:** add `engine.call_json(manifest, capability, params, *, key=None, timeout=30) -> tuple[payload|None, note]` and collapse the four wrappers onto it. Depth improves: one interface, four call sites shed their implementation.
- **Cost/risk:** low; behavior-preserving if the note strings are kept verbatim where tests assert them (test_frame.py / test_chunk_ledger.py check "engine output not understood" phrasing).

### 9. CLI boilerplate: engine-slot resolution and file-list splitting repeated across every entry point

- **Where:** the three-line idiom `slot = Path(args.engine_plugins) if ... else auto_engine_slot(...); manifest = engine.load_registered(slot) if slot else None` at `frame.py:293-295`, `route.py:149-151`, `front_door.py:74-76`, `frame_store.py:152-154`; the comma-split `[f.strip() for f in args.files.split(",") if f.strip()]` at `frame.py:292`, `route.py:148`, `front_door.py:73`, `frame_store.py:151`, `root_tree.py:254,286-290`, and as `_norm_files` in `server.py:175-180`.
- **What's wrong:** repeated pattern whose LCA exists — all four CLIs already import `frame` (which owns `auto_engine_slot`). Not shallow-wrapper territory; just unpromoted commonality.
- **Proposed change:** `frame.manifest_for(base, target, files, override: str | None)` and `frame.split_files(s)` (or move `_norm_files` down from server.py — server keeps its str|list tolerance as the MCP-facing adapter). Six call sites shrink.
- **Cost/risk:** trivial; none.

### 10. The governing-root upward walk exists in bash twice and in python only by emulation

- **Where:** upward walk in bash: `praxis-frame-gate.sh:52-68` and `praxis-frame-stamp.sh:49-60`. In python, "the root above this path" is emulated by a full downward scan then filter: `server.py:402-404` and `:429-431` (`find_roots(base, ...)` then `nearest_root`), `spawn_prompt.py:35-42` (`governing_root`), `frame.auto_engine_slot:155-158`. `root_tree.py` — the module whose whole subject is roots — offers no upward primitive; the gate hook's header even documents working around that (lines 47-51: "root_tree.py's own `resolve` … walks DOWNWARD").
- **What's wrong:** the python side pays O(tree-walk) per call for an O(depth) question, and the system's most-used root question has no named python interface. The bash copies are **load-bearing duplication** (see finding 11) — but they should be transcriptions of a rule that exists in exactly one python place, and today that place doesn't exist.
- **Proposed change:** add `root_tree.governing_root_above(path) -> Path | None` (nearest ancestor carrying a marker, same `.praxis`-then-`praxis` order as the hooks); reimplement `spawn_prompt.governing_root`, server.py's close_work/work_status resolution, and (where the semantics allow — auto_engine_slot needs span detection, so it keeps find_roots) on it. Reference it from the hook comments as the rule of record.
- **Cost/risk:** low; one subtlety — `nearest_root` over `find_roots(base)` only sees roots *under base*, while an upward walk can escape base. For close_work/work_status that is a behavior improvement (a `search_base` deep inside a root currently still works only because find_roots(base) includes base's subtree — verify with a test); keep the existing semantics where tests pin them.

---

## Tier 3 — bash↔python verdicts (per case, with the tradeoff)

### 11. Gate/stamp/read-stamp hooks: keep bash; the duplication is load-bearing — but extract the shared bash, and test parity

- **The duplication:** root-walk loop (gate:59-68 ≡ stamp:51-60), stamp-path derivation `shasum` of root under `$TMPDIR/praxis-front-door/<session>/` (gate:122-123 ≡ stamp:63-65 ≡ read-stamp:31-33), `file_age`/mtime handling (gate:83-88, stamp:76-79), and the glob semantics stated twice (`units.py:13-15` fnmatch ↔ gate:92-94 bash `case`).
- **Verdict per the question asked:** a `--hook-mode` python entry point behind a thin bash shim is **not** more aligned here. The hooks' headers record the deliberate choices — fail-open on any ambiguity, dependency-light (jq-guarded, no python required on the deny path), and PostToolUse-on-Read fires on *every* Read — so python interpreter startup per tool call is real cost, and fail-open is structurally simpler when the whole program is "extract, compare, exit 0". No new friction contradicts that record; it stands.
- **What IS accidental:** the three files privately re-deriving the same walk and the same stamp path. They live in one directory; a sourced `praxis-hooks-lib.sh` (walk_to_root, stamp_path, file_age, deny) passes the deletion test in reverse — delete the copies and the complexity reappears at every hook, so the shared file earns its keep, and three copies means the seam is already proven (two-adapters rule satisfied).
- **And the parity risk:** the fnmatch↔bash-case agreement is asserted in comments on both sides but tested on neither side across the boundary. One cross-language test (a bash-driven fixture: write a stamp JSON with a surface, pipe a synthetic PreToolUse payload through the gate hook, assert allow/deny for the same cases `test_units.py` covers in python) closes the drift channel without merging languages.
- **Cost/risk:** lib extraction is mechanical but touches enforcement code — land it with the parity test in the same change. Note the hooks live outside this repo (`~/.claude/hooks/`); see Surfaced in the handoff about where their source of record should sit.

### 12. Marker/stamp schema: one writer, five readers, two languages, zero schema statements

- **Where:** written by `frame.touch_frame_marker` (frame.py:34-47: bare-float or JSON+timestamp) and enriched by `begin_work` (server.py:337-342: unit_of_work/workstream/composition/size_floor/execution/delivery/payload/surface/output) and `close_work` (server.py:413-414: closed/prior_unit_of_work). Read by the gate hook (jq, four fields), the stamp hook (jq projection `{root, unit_of_work, workstream, delivery, payload, surface, output}`, stamp.sh:84), and `work_status` (server.py:436-446, including bare-float normalization).
- **What's wrong:** an emergent grouping without a home — the marker *is* an interface (callers must know field names, the closed flag, the bare-float legacy form, the 30-minute freshness convention) but that interface is only discoverable by diffing five code sites. The stamp hook's jq projection is the sharpest edge: add a field to `marker_data` in server.py and the stamp silently drops it; the gate then can't see it.
- **Proposed change:** not a code seam (one writer per language boundary; a shim would be speculative) — a **schema-of-record comment block** in frame.py beside `touch_frame_marker`, enumerating fields, both forms, and every consumer by path; plus the stamp hook's projection listed there so the "add a field" checklist has one home. Fold the freshness window (1800s in the gate, 60s begin-work-recency in the stamp) into the same block.
- **Cost/risk:** prose only; none. Revisit as a real seam only if a third writer appears.

### 13. The corpora sh hooks and corpus.py's own root walk: right tool where they stand

- `session-start.sh` / `scope-checkpoint.sh`: correctly bash (SessionStart banner + a counter that must cost a few filesystem ops per tool call — the header states the discipline; no friction to reopen). `stop-check.sh` is right in bash too once finding 1 lands.
- `corpus.py`'s `find_root_config`/`find_all_root_configs` (corpus.py:975-1061) mirror root_tree's shape with corpora markers. This is **load-bearing duplication**: praxis-imports-no-engine is recorded, and the reverse dependency (engine importing praxis-core) would invert the plugin direction `_engine_link.py` documents. Keep; a one-line comment cross-referencing root_tree as the sibling implementation is enough. Same verdict for `project_debug` (handoff.py:129-138 ≡ corpus.py:122-128) and section extraction (excerpt.py:31-70 ≈ corpus.py `extract_section`:2525-2548) — cross-skill copies on opposite sides of the no-import boundary.

---

## Tier 4 — corpus.py size, remaining dedup, tests

### 14. corpus.py (3,282 lines): a full split is mostly decorative; the flat-parser scaffolding is the real extraction

- **Assessment:** the file has ~13 self-labeled sections (state block, gates, shortcut ledger, screenshots, root resolution, domain selection, import machinery, migration, queue, spawn-parts, kill graduation, relocate, init), each a parse/render/cmd family with low cross-section coupling — so natural boundaries *exist*. But the forces for one file are real: the engine manifest points `cli.entry` at this single file, hooks invoke it by path, and snapshot-import copies it as one artifact. A package split (`corpus/` + dispatcher) buys locality mainly for the sections that churn — recent history shows that is the import/sync machinery (f341e2e, dfa2520) and little else. Verdict: **don't split now**; if import/sync keeps churning, extract *that* section first and alone, keeping `corpus.py` as the entry that imports it.
- **The non-decorative extraction:** the hand-rolled flat fenced-YAML list parser appears six times inside corpus.py — `parse_state:197`, `parse_deterministic_shortcut_candidates:494`, `parse_screenshot_manifest:708`, `parse_import_candidates:1712`, `parse_queue:2222`, `parse_audit_entries:2624` — each re-implementing fence detection, `- key:` item starts, key/value splitting, inline lists. The no-YAML-dependency ADR is *why the pattern exists*, not why it must be six implementations: one internal `_parse_flat_list(lines, list_key, item_key)` (parameterized like the existing `_ids`/`_parse_inline_list` helpers) keeps the ADR and concentrates the format's bug surface. The praxis-side twins (`chunk_ledger.parse_chunks:70` / `frame_store.parse_frames:65`) and uiux's `parse_deferred` stay separate copies across skill boundaries — but within each file family the same consolidation applies (chunk_ledger + frame_store share a repo and an import path; a `ledger_common.py` in praxis/scripts is their LCA if either grows a third schema — two schemas today, so hold per two-adapters).
- **Cost/risk:** the parser unification is behavior-sensitive (each copy has small tolerances — quoted values, `[]` empties); land it schema-by-schema against the existing 152 tests in test_corpus.py, which cover these parsers well.

### 15. Small praxis-python dedup (do opportunistically, not as a project)

- `_parse_inline_list` ≡ `_inline_list` (chunk_ledger.py:62, frame_store.py:107, corpus.py:1103 — first two share the praxis scripts dir; third stays, cross-skill).
- `today()` (chunk_ledger.py:47, frame_store.py:36).
- `domain_import.py`'s docstring claims "the ordering discipline is the orchestration praxis keeps intact" (lines 8-12) while the code enforces no ordering — four independent capability dispatches. Either make browse-before-file a checked fact or trim the claim to what the script does deliver (capability indirection + read-only browse). As written it is a shallow module *advertising* depth it doesn't have.
- `plugin_scaffold.scaffold` (plugin_scaffold.py:50-54): `path.mkdir` after the subdir mkdirs is redundant (parents=True already created it); harmless, tidy on next touch.

### 16. Test coverage gaps — the enforcement layer is the untested layer

- **Zero automated tests:** all three `~/.claude/hooks/praxis-*.sh` (the gate is the system's only *deny* mechanism and its lease-surface logic changed in the recent work), `server.py` (begin_work's lease relay, warning hoisting, `_validate_targets` salvage logic, `_preserved_markers` — the hottest churn in the system), and all three corpora sh hooks — finding 1 is exactly the bug a one-line smoke test (`sh stop-check.sh` in a fixture project, assert empty output) would have caught the day verify-chunks was removed.
- **Well covered:** praxis python scripts (18 test files, ~2,600 lines, incl. e2e and a stub engine), corpus.py (152 tests), corpora praxis-plugin scripts (3 test files), uiux plugin scripts (2 files — but legacy-layout-only, see finding 2).
- **Proposed order:** (a) sh-hook smoke tests runnable from pytest via subprocess with fixture dirs — gate allow/deny matrix, stamp write/clear, read-stamp path match; (b) server.py tool-function tests importing it as a module (FastMCP tools are plain functions; point `PRAXIS_SCRIPTS` handling at the repo checkout); (c) the cross-language surface-glob parity test from finding 11. Per interface-is-the-test-surface, all three drive the real entry points (hook stdin JSON, tool call args) — no reaching past.
- **Cost/risk:** (a) and (c) are an afternoon; (b) needs a small refactor so server.py's script-path insert is overridable (env var or `PRAXIS_SCRIPTS` module constant already exists at server.py:43 — parameterize it).

---

## Summary table

| # | Finding | Kind | Leverage | Cost |
|---|---------|------|----------|------|
| 1 | stop-check.sh calls removed verify-chunks; Stop blocks with argparse error | dead interface (live bug) | very high | trivial |
| 2 | uiux scripts hardcode legacy `corpora/`; wrong facts on dot-dir projects | drift (live bug) | very high | small |
| 3 | Five stale docstrings from the dot-dir sweep | prose drift | high | trivial |
| 4 | LEASE warning treats read inputs as edit targets; fix in server.py wording | interface conflation | high | trivial |
| 5 | server.py redundant/mid-file imports | accretion noise | medium | trivial |
| 6 | build_frame marker-touch side effect → delete `_preserved_markers` | side effect in read path | high | moderate |
| 7 | front_door.py shallow vs the real (MCP) front door; drifting | shallow module | medium-high | low-mod |
| 8 | compose/spawn-parts wrappers ×4 → `engine.call_json` | duplication, LCA=engine.py | medium-high | low |
| 9 | slot-resolution + file-split boilerplate ×6 → frame.py helpers | duplication, LCA=frame.py | medium | trivial |
| 10 | No python upward-root-walk primitive; add to root_tree | missing interface | medium | low |
| 11 | Hooks stay bash (load-bearing); extract shared bash lib + parity test | load-bearing dup, tooling | medium | low |
| 12 | Marker/stamp schema has no schema-of-record; document at the writer | undocumented interface | medium | trivial |
| 13 | corpus.py root-walk/debug/extract copies are load-bearing; keep | (non-finding, recorded) | — | — |
| 14 | corpus.py: don't split; unify the ×6 flat parser internally | decorative vs real split | medium | moderate |
| 15 | Small dedup + domain_import docstring overclaim | duplication/prose | low-med | trivial |
| 16 | Enforcement layer (hooks, server.py) untested | test gap | high | moderate |
