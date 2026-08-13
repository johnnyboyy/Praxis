"""uiux — a judgment plugin growing its PROCESS face.

Carries hand-authored design-judgment domain files for the corpora composer to
discover and inject (the JUDGMENT face — unchanged). Corpora finds this plugin via
`contributors_for(root)`, reads `*.md` from `domains_dir`, and stamps every domain
`owner = "uiux"`.

This module also registers the plugin's PROCESS face with praxis: the design
`phases()` and `workflows()` (real `workflow.Phase` / `workflow.Workflow` objects),
gated by a deterministic `library-state` phase whose `run` callable is
`library_state.evaluate`. The runtime behaviors that read that fact —
`contribute` (graduated disclosure keyed on the named phase), `hooks` (the
`unit-close` recorder: drift, screenshot staleness, decision filing, design-sync
recommendation), and `surface` (the docs-only design lease) — are all live.
"""

from __future__ import annotations

import re
from pathlib import Path

import config
import deferred_queue
import library_state
from contributors import Contribution, HookContext

PRAXIS_PLUGIN = True

from workflow import (
    CLOSE,
    IMPLEMENT,
    PLAN,
    VERIFY,
    EdgeType,
    Phase,
    Workflow,
)

LIBRARY_STATE = Phase(
    "library-state", stance="neutral", delivery="deterministic",
    intent="library eligibility + ordering fact for the root's design libraries",
    produces="library-state", run=library_state.evaluate)

UI_LIBRARY_INIT = Phase(
    "ui-library-init", stance="divergent", delivery="spawn",
    intent="found a project's UI identity from the rendered app",
    produces="ui-library")

UX_LIBRARY_INIT = Phase(
    "ux-library-init", stance="convergent", delivery="spawn",
    intent="found the UX flows cohering with the ratified UI identity",
    produces="ux-library")

UI_LIBRARY_SYNC = Phase(
    "ui-library-sync", stance="divergent", delivery="spawn",
    intent="bring the UI library back in line with drifted surfaces",
    produces="ui-library")

UX_LIBRARY_SYNC = Phase(
    "ux-library-sync", stance="convergent", delivery="spawn",
    intent="bring the UX library back in line with drifted flows",
    produces="ux-library")

SCREENSHOT_CAPTURE = Phase(
    "screenshot-capture", stance="neutral", delivery="spawn",
    intent="mechanical capture: drive the app, shoot each catalogued surface",
    produces="screenshots")

SCREENSHOT_LIBRARY_SYNC = Phase(
    "screenshot-library-sync", stance="neutral", delivery="spawn",
    intent="surgical recapture: reshoot ONLY the surfaces the manifest marks stale",
    produces="screenshots")

DESIGN_DECISION_REVIEW = Phase(
    "design-decision-review", stance="neutral", delivery="inline",
    intent="accept/revise/reject a divergent Artifact, file it into the library",
    produces="decision")

UIUX_PHASES = [
    LIBRARY_STATE, UI_LIBRARY_INIT, UX_LIBRARY_INIT, UI_LIBRARY_SYNC,
    UX_LIBRARY_SYNC, SCREENSHOT_CAPTURE, SCREENSHOT_LIBRARY_SYNC,
    DESIGN_DECISION_REVIEW,
]

def _facts(ev):
    return (ev.get("facts") or {}).get("library_state") or {}

def _libs(ev):
    return _facts(ev).get("libraries") or {}

def _needs_ui_init(ev):
    return not _libs(ev).get("ui", False)

def _needs_screenshots(ev):
    return _libs(ev).get("ui", False) and not _libs(ev).get("screenshots", False)

def _needs_ux_init(ev):
    return _libs(ev).get("ui", False) and not _libs(ev).get("ux", False)

def _screenshots_any_stale(ev):
    return bool((_facts(ev).get("screenshots") or {}).get("any_stale"))

def _ui_drift_over_threshold(ev):
    return (_libs(ev).get("ui", False)
            and _facts(ev).get("ui_drift", 0) >= library_state.DRIFT_THRESHOLD)

def _ux_drift_over_threshold(ev):
    return (_libs(ev).get("ux", False)
            and _facts(ev).get("ux_drift", 0) >= library_state.DRIFT_THRESHOLD)

DESIGN_BOOTSTRAP = Workflow(
    name="design-bootstrap",
    phases=[LIBRARY_STATE, UI_LIBRARY_INIT, UX_LIBRARY_INIT, SCREENSHOT_CAPTURE,
            DESIGN_DECISION_REVIEW, CLOSE],
    edges=[

        ("library-state", "ui-library-init", "fact", EdgeType.create, _needs_ui_init),
        ("library-state", "screenshot-capture", "fact", EdgeType.create, _needs_screenshots),
        ("library-state", "ux-library-init", "fact", EdgeType.create, _needs_ux_init),

        ("library-state", "close", "pass", EdgeType.carry),

        ("ui-library-init", "design-decision-review", "pass", EdgeType.carry),
        ("ux-library-init", "design-decision-review", "pass", EdgeType.carry),
        ("design-decision-review", "library-state", "pass", EdgeType.carry),

        ("screenshot-capture", "library-state", "pass", EdgeType.carry),
    ],
)

FEATURE_DESIGN = Workflow(
    name="feature-design",
    phases=[LIBRARY_STATE, PLAN, IMPLEMENT, VERIFY, CLOSE],
    edges=[

        ("library-state", "plan", "pass", EdgeType.carry),
        ("plan", "implement", "pass", EdgeType.carry),
        ("implement", "verify", "pass", EdgeType.carry),
        ("verify", "close", "pass", EdgeType.carry),
        ("verify", "implement", "fail", EdgeType.carry),
    ],
)

DESIGN_SYNC = Workflow(
    name="design-sync",
    phases=[LIBRARY_STATE, SCREENSHOT_LIBRARY_SYNC, UI_LIBRARY_SYNC,
            UX_LIBRARY_SYNC, DESIGN_DECISION_REVIEW, CLOSE],
    edges=[

        ("library-state", "screenshot-library-sync", "fact", EdgeType.create,
         _screenshots_any_stale),

        ("library-state", "ui-library-sync", "fact", EdgeType.create,
         _ui_drift_over_threshold),
        ("library-state", "ux-library-sync", "fact", EdgeType.create,
         _ux_drift_over_threshold),

        ("library-state", "close", "pass", EdgeType.carry),

        ("screenshot-library-sync", "library-state", "pass", EdgeType.carry),

        ("ui-library-sync", "design-decision-review", "pass", EdgeType.carry),
        ("ux-library-sync", "design-decision-review", "pass", EdgeType.carry),
        ("design-decision-review", "library-state", "pass", EdgeType.carry),
    ],
)

UIUX_WORKFLOWS = [DESIGN_BOOTSTRAP, FEATURE_DESIGN, DESIGN_SYNC]

DESIGN_PHASES = {
    "ui-library-init", "ux-library-init", "ui-library-sync", "ux-library-sync",
    "design-decision-review",
}

DIVERGENT_DESIGN_PHASES = {"ui-library-sync", "ux-library-sync"}
SYNC_PHASES = {"ui-library-sync", "ux-library-sync"}

DESIGN_LEASE = ["docs/*", "docs/**", "*.md", ".praxis/**"]

_INDEX_PRIORITY = 5
_PIN_PRIORITY = -5

def _read_text(path: Path) -> str:
    try:
        return Path(path).read_text()
    except OSError:
        return ""

def _section(text: str, name: str) -> str | None:
    if not text or not name:
        return None
    lines = text.splitlines()
    start = None
    level = 0
    for i, line in enumerate(lines):
        m = re.match(r"^(#+)\s+(.*)$", line)
        if m and name.strip().lower() in m.group(2).strip().lower():
            start = i
            level = len(m.group(1))
            break
    if start is None:
        return None
    out = [lines[start]]
    for line in lines[start + 1:]:
        m = re.match(r"^(#+)\s+", line)
        if m and len(m.group(1)) <= level:
            break
        out.append(line)
    return "\n".join(out).rstrip()

class UiuxJudgment:

    source = "uiux"

    domains_dir = Path(__file__).resolve().parent / "domains"

    def __init__(self, root):

        self.root = root

    def phases(self) -> list:
        return list(UIUX_PHASES)

    def workflows(self) -> list:
        return list(UIUX_WORKFLOWS)

    def _lib_paths(self):
        return library_state._lib_paths(self.root)

    def _index_body(self) -> str:
        s = library_state.build_state(self.root)
        ui_path, ux_path = self._lib_paths()
        libs = s["libraries"]
        lines = ["Design surface inventory (uiux) — an index, not the libraries."]
        lines.append(
            f"- ui-library · UI identity: components, tokens, patterns · "
            f"{ui_path} · {'present' if libs['ui'] else 'absent'}")
        lines.append(
            f"- ux-library · UX flows and patterns · "
            f"{ux_path} · {'present' if libs['ux'] else 'absent'}")
        entries = library_state.read_manifest(self.root)
        if entries:
            lines.append("screenshots (by reference — open on demand):")
            sdir = library_state.screenshots_dir(self.root)
            for e in entries:
                lines.append(f"- {e['screen']} · {sdir / (e.get('file') or '')} · "
                             f"{e.get('status', 'fresh')}")
        return "\n".join(lines)

    def _index_contribution(self) -> Contribution:
        return Contribution(source="uiux", title="Design surface inventory",
                            body=self._index_body(), priority=_INDEX_PRIORITY,
                            meta={"disclosure": "index"})

    def _screenshot_refs_contribution(self) -> Contribution | None:
        entries = library_state.read_manifest(self.root)
        if not entries:
            return None
        sdir = library_state.screenshots_dir(self.root)
        lines = ["Adjacent screenshots — paths only, open via vision on demand:"]
        for e in entries:
            lines.append(f"- {e['screen']} · {sdir / (e.get('file') or '')} · "
                         f"{e.get('status', 'fresh')}")
        return Contribution(source="uiux", title="Adjacent screenshots (by reference)",
                            body="\n".join(lines), priority=_INDEX_PRIORITY,
                            meta={"disclosure": "screenshots-by-reference"})

    def _consistency_pin(self, targets) -> Contribution:
        ui_path, _ = self._lib_paths()
        text = _read_text(ui_path)
        chunks = []
        for name in (targets or []):
            sec = _section(text, str(name))
            if sec:

                chunks.append("\n".join(sec.splitlines()[:8]))
        body = ("Consistency pins — constraints the new surface must NOT violate "
                "(curated, not the full library):\n")
        body += "\n\n".join(chunks) if chunks else "(no named targets — see the index for surfaces.)"
        return Contribution(source="uiux", title="Consistency pin (curated)", body=body,
                            priority=_PIN_PRIORITY, meta={"disclosure": "consistency-pin"})

    def _anti_mean(self) -> Contribution:
        return Contribution(
            source="uiux", title="Anti-mean (divergent design)",
            body=("This is a divergent pass: differentiate from the existing mean. Do NOT "
                  "converge on the current library — the pins above are the floor (what not "
                  "to violate), not an attractor. Push the identity forward."),
            priority=_PIN_PRIORITY, meta={"disclosure": "anti-mean"})

    def contribute(self, situation) -> list:
        name = getattr(situation, "phase_name", None)
        targets = getattr(situation, "targets", None) or []

        if name is None:
            return [self._index_contribution()]

        if name == "plan":
            return [self._index_contribution()]

        if name == "ui-library-init":

            return [Contribution(
                source="uiux", title="UI library init (author from the app)",
                body=("Catalog this project's UI identity — components, tokens, patterns — "
                      "from the RENDERED app, not from a library (there is none yet). "
                      "Unit of work: bootstrap-ui-surface."),
                priority=_INDEX_PRIORITY, meta={"disclosure": "instruction"})]

        if name == "ux-library-init":

            ui_path, _ = self._lib_paths()
            return [Contribution(source="uiux", title="UI library (full)",
                                 body=_read_text(ui_path), priority=_INDEX_PRIORITY,
                                 meta={"disclosure": "full", "surface": "ui-library"})]

        if name in DIVERGENT_DESIGN_PHASES:

            out = [self._index_contribution(), self._consistency_pin(targets),
                   self._anti_mean()]
            refs = self._screenshot_refs_contribution()
            if refs is not None:
                out.append(refs)
            return out

        if name == "implement":

            ui_path, _ = self._lib_paths()
            text = _read_text(ui_path)
            out = []
            for t in targets:
                sec = _section(text, str(t))
                if sec:
                    out.append(Contribution(
                        source="uiux", title=f"Surface spec: {t}", body=sec,
                        priority=_INDEX_PRIORITY,
                        meta={"disclosure": "named-few", "surface": str(t)}))
            return out or [self._index_contribution()]

        if name in ("screenshot-capture", "screenshot-library-sync"):

            entries = library_state.read_manifest(self.root)
            stale = [e["screen"] for e in entries if e.get("status") == "stale"]
            if name == "screenshot-library-sync":
                verb = ("Recapture ONLY these stale surfaces "
                        "(surgical — never a full recapture)")
                fallback = "(none stale)"
                title = "Screenshot recapture set"
            else:
                verb = "Stale set to (re)capture"
                fallback = "(none catalogued yet)"
                title = "Screenshot capture set"
            body = self._index_body() + f"\n\n{verb}: " + (
                ", ".join(stale) if stale else fallback)
            return [Contribution(source="uiux", title=title, body=body,
                                 priority=_INDEX_PRIORITY, meta={"disclosure": "manifest"})]

        return []

    def hooks(self) -> dict:
        return {"unit-close": self._on_close}

    def _on_close(self, ctx: HookContext) -> None:
        root = ctx.root
        receipt = ctx.receipt or {}

        ev = receipt.get("evidence") or {}
        situation = getattr(ctx.unit, "situation", None)
        phase_name = getattr(situation, "phase_name", None)
        targets = list(getattr(situation, "targets", None) or [])
        drift = ev.get("ui-drift") or {}
        screens = list(drift.get("screens") or [])
        components = list(drift.get("components") or [])

        decision = ev.get("decision") or {}
        accepted = bool(decision.get("accept"))

        ui_d, ux_d = library_state._drift_counts(root)
        if accepted and phase_name == "ui-library-sync":
            config.write(root, "uiux", {"library_drift": {"ui_drift": 0, "ux_drift": ux_d}})
        elif accepted and phase_name == "ux-library-sync":
            config.write(root, "uiux", {"library_drift": {"ui_drift": ui_d, "ux_drift": 0}})
        elif screens or components or targets:
            config.write(root, "uiux",
                         {"library_drift": {"ui_drift": ui_d + 1, "ux_drift": ux_d + 1}})

        if accepted and phase_name == "screenshot-library-sync":
            captured = list((ev.get("screenshots") or {}).get("captured") or [])
            library_state.mark_fresh(root, screens=captured or None)

        glob = bool(drift.get("global") or drift.get("tokens"))
        if screens or components or glob:
            library_state.mark_stale(root, screens=screens, components=components,
                                     all_surfaces=glob)

        if accepted and (phase_name == "design-decision-review"
                         or phase_name in DESIGN_PHASES):
            self._file_decision(root, decision)

        ui_d, ux_d = library_state._drift_counts(root)
        stale = [e["screen"] for e in library_state.read_manifest(root)
                 if e.get("status") == "stale"]
        th = library_state.DRIFT_THRESHOLD
        due = ([f"screenshots ({len(stale)} stale)"] if stale else [])\
            + ([f"ui ({ui_d}/{th})"] if ui_d >= th else [])\
            + ([f"ux ({ux_d}/{th})"] if ux_d >= th else [])
        body = ("design-sync due: " + "; ".join(due)) if due else\
               (f"design-sync cadence: screenshots {len(stale)} stale; "
                f"ui {ui_d}/{th}; ux {ux_d}/{th}")
        try:
            ctx.add_note("uiux", body,
                         screenshots_stale=len(stale),
                         ui_drift=ui_d, ux_drift=ux_d, threshold=th,
                         due=[d.split(" ")[0] for d in due])
        except Exception:
            pass

    def _file_decision(self, root, decision: dict) -> None:
        content = decision.get("content")
        if not content:
            return
        ui_path, ux_path = library_state._lib_paths(root)
        target = str(decision.get("target", "ui")).lower()
        path = ux_path if ("ux" in target) else ui_path
        section = decision.get("section")
        existing = _read_text(path)
        new_text = None
        if section and existing:
            old = _section(existing, str(section))
            if old:
                new_text = existing.replace(old, content.rstrip())
        if new_text is None:
            body = existing.rstrip() + "\n\n" + content.rstrip() + "\n" if existing else content.rstrip() + "\n"
            new_text = body
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(new_text if new_text.endswith("\n") else new_text + "\n")
        except OSError:
            return
        resolves = decision.get("resolves")
        if resolves:
            deferred_queue.resolve(str(root), resolves,
                                   decision.get("resolution", "Filed into the design library."))

    def surface(self, situation) -> list | None:
        if getattr(situation, "phase_name", None) in DESIGN_PHASES:
            return list(DESIGN_LEASE)
        return None

def make(root) -> "UiuxJudgment":
    return UiuxJudgment(root)
