"""Corpora — the compose layer, plus the surface/harvest half.

A pure praxis contributor: once per phase praxis calls `contribute(situation)`,
and Corpora discovers + merges the domain pool, does a coarse confident cut
(subject + shape), modulates weight/framing from the facet-weights table, and
emits a small set of `Contribution`s at four priority tiers. It ships no domains
and holds no `domains_dir`.

Corpora also runs the **surface** half via the per-unit `unit-close` hook: it
HARVESTS principle *proposals* a spawn reports at unit completion and records them
into a project-local, human-readable candidate store marked UNRATIFIED. Harvest
never ratifies and never writes into any `domains_dir` — the ratify/retrospective
engine is a separate concern. Everything on this path is fail-soft: a malformed
receipt is a no-op, never a raise.
"""

from __future__ import annotations

from datetime import date

from .discovery import discover_domain_dirs, merge_pool  # adds praxis to sys.path
from .weights import load_weights

from contributors import Contribution, HookContext  # noqa: E402 (praxis path added above)

# Marker: identifies this module as a praxis plugin's main module (carries
# `source` + `make`). Layered discovery finds plugins by this constant.
PRAXIS_PLUGIN = True


# ── applies-when mini-syntax ─────────────────────────────────────────────────

def shape_ok(applies_when, shape) -> bool:
    """Evaluate a domain's `applies-when` conditions against the project shape.

    Each entry is a single `{key: matcher}`. Matcher forms:
      - equals   `framework: react`   -> shape[key] == matcher
      - not-none `styling: not-none`  -> shape[key] set to something real
      - one-of   `language: [a, b]`   -> shape[key] in the list
    AND across all entries. An unset / None / 'none' shape value fails both
    equals and not-none. An empty `applies-when` always passes.
    """
    for cond in applies_when or []:
        for key, matcher in cond.items():
            value = shape.get(key) if isinstance(shape, dict) else None
            unset = value is None or value == "none"
            if isinstance(matcher, list):  # one-of
                if value not in matcher:
                    return False
            elif matcher == "not-none":
                if unset:
                    return False
            else:  # equals
                if unset or value != matcher:
                    return False
    return True


# ── rendering helpers ────────────────────────────────────────────────────────

_LENS_HEADERS = {
    "new-behavior": (
        "Framing (create): generative judgment for producing new behavior."
    ),
    "preservation": (
        "Framing (change): preservation judgment — don't break the anchor; "
        "keep existing behavior intact."
    ),
    "read-only": (
        "Framing (explore): read-only judgment — for comprehension, not "
        "prescription."
    ),
    "process": "Framing: process judgment — how to carry out this workflow.",
}


def render_principles(principles, lens) -> str:
    """Render principles as readable prose.

    Emits each principle's `rule`, `condition`, and `reason` verbatim. `lens`
    only prepends a one-line framing header and orders/frames the block; it
    NEVER filters on `condition` — relevance is the model's call.
    """
    lines: list[str] = []
    header = _LENS_HEADERS.get(lens)
    if header:
        lines.append(header)
        lines.append("")
    for p in principles:
        lines.append(f"- {p.rule}")
        if p.condition:
            lines.append(f"    when: {p.condition}")
        if p.reason:
            lines.append(f"    why: {p.reason}")
    return "\n".join(lines)


def terse_list(lines) -> str:
    """Render a compact imperative bullet list."""
    return "\n".join(f"- {line}" for line in lines)


ANTI_MEAN_ANCHOR_TEXT = (
    "The default, expected answer is a starting point to push against, not a "
    "target. Treat the obvious solution as the mean to differentiate from: "
    "interrogate it, and only settle there if it still wins after you have "
    "tried to beat it."
)


# ── the contributor ──────────────────────────────────────────────────────────

CONFIG_NAMESPACE = "corpora"


class Corpora:
    """Coarse mechanical composer over the discovered domain pool."""

    source = "corpora"
    # NOTE: no `domains_dir` attribute — Corpora ships no domains.

    def __init__(self, root, weights):
        self.root = root          # this praxis root; used to discover contributors
        self.weights = weights    # facet-weights.yaml

    def contribute(self, s) -> list[Contribution]:
        W = self.weights

        # ── 0. DISCOVER + MERGE ──────────────────────────────────────────────
        pool = merge_pool(discover_domain_dirs(self.root))

        # Corpora reads its own namespaced config section — everything it needs
        # is injected there. `project_shape` (language/framework/styling/has_ui)
        # gates domains' `applies-when`; absent => {} => all domains pass prune.
        import config
        settings = config.read(self.root, CONFIG_NAMESPACE) or {}
        shape = settings.get("project_shape") or {}

        # ── 1–2. CONFIDENT CUT: subject filter + shape prune ─────────────────
        admissible = [
            d
            for d in pool
            if (d.universal or d.subject == s.subject)
            and shape_ok(d.applies_when, shape)
        ]

        # ── 3–6. MODULATE: rank weight per domain ────────────────────────────
        tk = W.task_kind[s.task_kind]
        st = W.stance[s.phase]
        for d in admissible:
            d.weight = 1.0
            if s.task_kind in d.task_kinds:
                d.weight *= 1.5
            if s.workflow and s.workflow in d.workflows:
                d.weight *= W.workflow[s.workflow]["weight"]
            if s.label and s.label in d.labels:
                d.weight *= W.label["*"]["pin_weight"]
        admissible.sort(key=lambda d: (-d.weight, d.registration_index))

        out: list[Contribution] = []

        # ── anti-mean anchor: only when diverging (priority -10) ─────────────
        if st.anchor == "anti-mean":
            out.append(
                Contribution(
                    self.source,
                    "Resist the mean",
                    ANTI_MEAN_ANCHOR_TEXT,
                    priority=-10,
                )
            )

        # ── conventions preamble: tight filter (priority 0) ──────────────────
        if tk.convention_weight > 0 and st.convention_multiplier > 0:
            lines: list[str] = []
            for d in admissible:
                if getattr(st, "suppress_posture", None) == d.posture:
                    continue
                lines += [c.rule for c in d.conventions]
            if lines:
                out.append(
                    Contribution(
                        self.source,
                        "Conventions",
                        terse_list(lines),
                        priority=0,
                    )
                )

        # ── domain principles: generous, grouped, lensed (priority 10) ───────
        for d in admissible:
            out.append(
                Contribution(
                    self.source,
                    f"{d.owner}/{d.id} — principles",
                    render_principles(d.principles, lens=tk.principle_lens),
                    priority=10,
                )
            )

        # ── workflow process principles: only if workflow matched (20) ───────
        if s.workflow:
            for d in admissible:
                if s.workflow in d.workflows:
                    out.append(
                        Contribution(
                            self.source,
                            f"{d.owner}/{d.id} — {s.workflow} process",
                            render_principles(d.principles, lens="process"),
                            priority=20,
                        )
                    )

        return out

    # ── surface / harvest half (unit-close hook) ─────────────────────────────
    #
    # The receipt PROPOSAL shape. A spawn reports proposals at unit completion
    # under `receipt["evidence"]["proposals"]` — a list of dicts, each:
    #
    #     {
    #       "id":        str,   # a short slug the spawn assigns
    #       "rule":      str,   # the proposed principle (imperative)
    #       "condition": str,   # when it applies (optional prose)
    #       "reason":    str,   # why — load-bearing rationale (optional)
    #       "kind":      str,   # "judgment" | "knowledge"
    #       "provenance": {...} # OPTIONAL free-form origin the spawn attaches
    #     }
    #
    # `rule` is the only field harvest insists on; everything else is best-effort.
    # For a workflow unit `receipt["evidence"]` is the aggregate of the walked
    # phases' evidence, so a proposal reported by any phase surfaces here.
    #
    # Harvest stamps each proposal with harvest provenance (unit id + date),
    # appends it to a project-local candidate store marked UNRATIFIED, and drops a
    # journal note. It NEVER ratifies and NEVER touches a `domains_dir`.

    _KNOWN_KINDS = ("judgment", "knowledge")

    def hooks(self) -> dict:
        """Register the per-unit surface hook. Fires once per unit at close with
        the unit's final receipt (see `_harvest`)."""
        return {"unit-close": self._harvest}

    def _store_path(self, root):
        """The project-local candidate store — under this root's `.praxis`, in
        corpora's own subdir. Never a `domains_dir`."""
        from pathlib import Path
        return Path(root) / ".praxis" / "corpora" / "candidates.md"

    def _harvest(self, ctx: HookContext) -> None:
        """unit-close: harvest principle PROPOSALS off the receipt into the
        UNRATIFIED candidate store. Fail-soft by construction — any malformed
        receipt (missing/None/non-list proposals, bad entries) is a no-op."""
        try:
            receipt = ctx.receipt or {}
            evidence = receipt.get("evidence") or {}
            proposals = evidence.get("proposals")
            if not isinstance(proposals, list):
                return

            unit_id = getattr(ctx.unit, "id", None)
            stamped = []
            for p in proposals:
                if not isinstance(p, dict):
                    continue
                rule = str(p.get("rule") or "").strip()
                if not rule:
                    continue  # a proposal with no rule is nothing to record
                stamped.append(self._stamp(p, rule, unit_id))
            if not stamped:
                return

            self._append_candidates(ctx.root, stamped)

            try:
                ctx.add_note(
                    "corpora",
                    f"Surfaced {len(stamped)} unratified candidate principle(s) "
                    f"for review (NOT ratified) → {self._store_path(ctx.root)}",
                    candidates=len(stamped),
                    store=str(self._store_path(ctx.root)),
                )
            except Exception:
                pass
        except Exception:
            # Fail-soft: harvest must never raise into praxis' close ceremony.
            return

    def _stamp(self, proposal: dict, rule: str, unit_id) -> dict:
        """Normalize + provenance-stamp one proposal. Harvest provenance (unit id
        + harvest date) is recorded ALONGSIDE any provenance the spawn attached."""
        kind = str(proposal.get("kind") or "").strip().lower()
        if kind not in self._KNOWN_KINDS:
            kind = "unspecified"
        return {
            "id": str(proposal.get("id") or "").strip() or "(no id)",
            "rule": rule,
            "condition": str(proposal.get("condition") or "").strip(),
            "reason": str(proposal.get("reason") or "").strip(),
            "kind": kind,
            "origin": proposal.get("provenance"),
            "unit": unit_id,
            "harvested": date.today().isoformat(),
        }

    def _render_candidate(self, c: dict) -> str:
        lines = [f"## {c['id']} — {c['kind']} · UNRATIFIED"]
        lines.append(f"- rule: {c['rule']}")
        if c["condition"]:
            lines.append(f"- when: {c['condition']}")
        if c["reason"]:
            lines.append(f"- why: {c['reason']}")
        prov = f"unit={c['unit']}, harvested={c['harvested']}"
        if c["origin"] is not None:
            prov += f", origin={c['origin']}"
        lines.append(f"- provenance: {prov}")
        return "\n".join(lines)

    _STORE_HEADER = (
        "# Corpora candidate principles — UNRATIFIED\n\n"
        "These are principle PROPOSALS harvested from spawn receipts at unit\n"
        "close. They are FOR REVIEW ONLY — nothing here is ratified, and corpora\n"
        "does not compose from this file. Ratification is a separate, deliberate\n"
        "step handled by the retrospective engine, not by this surface pass.\n"
    )

    def _append_candidates(self, root, candidates: list[dict]) -> None:
        path = self._store_path(root)
        path.parent.mkdir(parents=True, exist_ok=True)
        existing = ""
        if path.exists():
            try:
                existing = path.read_text(encoding="utf-8")
            except OSError:
                existing = ""
        blocks = [self._render_candidate(c) for c in candidates]
        if existing.strip():
            body = existing.rstrip() + "\n\n" + "\n\n".join(blocks) + "\n"
        else:
            body = self._STORE_HEADER + "\n" + "\n\n".join(blocks) + "\n"
        path.write_text(body, encoding="utf-8")


def make(root) -> Corpora:
    """Factory: register via `corpora.injector:make`."""
    return Corpora(root, load_weights())
