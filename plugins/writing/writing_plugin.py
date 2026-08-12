"""writing — a PROCESS-ONLY praxis plugin.

Ships the writing PROCESS face and nothing else. It registers two phases —
`writing-draft` (divergent) and `writing-revision` (convergent) — and a
`writing` workflow that wires draft -> revision -> close, and it composes
per-stance drafting/revision guidance from `contribute()`.

It carries NO judgment: there is deliberately no `domains_dir`. A baked-in
"good fiction" or "good legal prose" rule is just the baseline craft an agent
already applies, and corpora only earns its keep with judgment that BEATS
baseline. Genre/style judgment is therefore not pre-authored here — it is born
later at the ratify gate, homed in the project doing the work. The genre axis
(fiction / nonfiction / copy / legal / documentation) is not a field on
`Situation`; it rides in each Contribution's body and `meta`, read as a hint
from `situation.label`.
"""

from __future__ import annotations

from contributors import Contribution
from workflow import CLOSE, EdgeType, Phase, Workflow

# Marker: identifies this module as a praxis plugin's main module (carries
# `source` + `make`). Layered discovery finds plugins by this constant.
PRAXIS_PLUGIN = True

# --- PROCESS face: the phase objects ---------------------------------------------
# Both phases are agent-driven `spawn` work (there is no deterministic craft to
# `run`). `writing-draft` is divergent — it opens the space and gets words down;
# `writing-revision` is convergent — it narrows an existing draft toward done.

WRITING_DRAFT = Phase(
    "writing-draft", stance="divergent", delivery="spawn",
    intent="produce a first draft of a prose product for a stated genre and style",
    produces="draft")

WRITING_REVISION = Phase(
    "writing-revision", stance="convergent", delivery="spawn",
    intent="revise a prose-product draft toward its finished form",
    produces="prose")

WRITING_PHASES = [WRITING_DRAFT, WRITING_REVISION]

# --- PROCESS face: the workflow object -------------------------------------------
# draft -> revision -> close. `close` is a seed phase (workflow.CLOSE); the
# registry merges the seed layer in, so validate_workflow resolves it against the
# merged phase table. A draft that turns out to need a different genre or a fresh
# direction loops revision -> draft (fail carry) rather than forcing forward.

WRITING = Workflow(
    name="writing",
    phases=[WRITING_DRAFT, WRITING_REVISION, CLOSE],
    edges=[
        ("writing-draft", "writing-revision", "pass", EdgeType.carry),
        ("writing-revision", "close", "pass", EdgeType.carry),
        ("writing-revision", "writing-draft", "fail", EdgeType.carry),
    ],
)

WRITING_WORKFLOWS = [WRITING]

# --- CONTRIBUTE face -------------------------------------------------------------
# The recognized genre axis (extensible — a genre the work needs but this set
# lacks is itself a finding, not a silent stretch of an ill-fitting one).
GENRES = ("fiction", "nonfiction", "copy", "legal", "documentation")

_PRIORITY = 0

_DRAFT_BODY = (
    "Divergent draft pass. Get a first, whole-enough draft of the prose product "
    "down to the genre's shape and hold the stated style (voice, formality, "
    "person, tense) throughout. One draft for revision to work on — not polished, "
    "not self-edited to death (that is writing-revision's job; over-converging "
    "here defeats the divergent stance). Keep scaffolding (outline, alternative "
    "openings, notes-to-self) if it helps the reviser see the choices. When a real "
    "writing decision beat baseline craft, surface it as a ratify-gate candidate — "
    "that is how a genre/style domain is born."
)

_REVISION_BODY = (
    "Convergent revision pass. Read the whole draft once for genre fit (does it do "
    "what this kind of writing is for) and once for reader fit (does its intended "
    "reader get what they came for), then revise: cut what does not serve the "
    "piece, sharpen what does, and hold the style contract throughout. Converge to "
    "done — a finished piece with its draft scaffolding removed. A draft that needs "
    "a different genre or a fresh direction goes back to writing-draft, not forward. "
    "A revision decision that beat baseline is a ratify-gate candidate; a real hole "
    "in the piece (missing content, not verbosity) is a finding, not something to "
    "invent here."
)


def _genre(situation) -> str | None:
    """Read the genre hint off `situation.label` (there is no genre field on
    Situation). Returns a recognized genre or None."""
    label = getattr(situation, "label", None)
    if not label:
        return None
    low = str(label).lower()
    return next((g for g in GENRES if g in low), None)


def _is_draft(situation) -> bool:
    """draft when the phase name says so, else fall back to the divergent stance."""
    name = getattr(situation, "phase_name", None)
    if name == "writing-draft":
        return True
    if name == "writing-revision":
        return False
    return getattr(situation, "phase", None) == "divergent"


class WritingProcess:
    """A PROCESS-ONLY writing source: phases, a workflow, per-stance guidance.

    No `domains_dir` — this plugin carries no judgment (that is the whole design).
    """

    # Non-empty source string. This plugin's namespace + precedence identity.
    source = "writing"

    def __init__(self, root):
        # `root` is the consuming praxis root praxis hands to the factory.
        self.root = root

    def phases(self) -> list:
        """The writing phases this plugin registers (real workflow.Phase objects)."""
        return list(WRITING_PHASES)

    def workflows(self) -> list:
        """The writing workflow. It references the seed `close` phase by name; the
        registry merges the seed layer in, so validation resolves against the
        merged phase table."""
        return list(WRITING_WORKFLOWS)

    def contribute(self, situation) -> list:
        """Per-stance drafting/revision guidance, keyed on a prose subject. Returns
        [] for any non-prose subject. The genre axis rides in the Contribution body
        and `meta` (there is no genre field on Situation)."""
        if getattr(situation, "subject", None) != "prose":
            return []

        draft = _is_draft(situation)
        genre = _genre(situation)
        genre_note = (f" Genre: {genre}." if genre
                      else " Genre: unspecified (name one in the brief; a genre the "
                           "work needs but the recognized set lacks is itself a finding).")
        meta = {
            "stance": "divergent" if draft else "convergent",
            "genre": genre,
            "genres": list(GENRES),
        }
        if draft:
            return [Contribution(
                source="writing", title="Writing: draft (divergent)",
                body=_DRAFT_BODY + genre_note, priority=_PRIORITY, meta=meta)]
        return [Contribution(
            source="writing", title="Writing: revision (convergent)",
            body=_REVISION_BODY + genre_note, priority=_PRIORITY, meta=meta)]


def make(root) -> "WritingProcess":
    """Factory. Register via `writing_plugin:make` in the root's config."""
    return WritingProcess(root)
