"""coding-stack — a bare judgment plugin.

Carries hand-authored, stack-SPECIFIC coding-judgment domain files (TypeScript,
React, Next.js, Expo, CSS, and the Expo dependency/release domains) for the
corpora composer to discover and inject. It does no composing itself:
`contribute` is a no-op. Corpora finds this plugin via `contributors_for(root)`,
reads `*.md` from `domains_dir`, and stamps every domain `owner = "coding-stack"`.

Every domain here carries an `applies-when` clause so corpora only composes it
for a matching project shape (language / framework / styling).
"""

from __future__ import annotations

from pathlib import Path

# Marker: identifies this module as a praxis plugin's main module (carries
# `source` + `make`). Layered discovery finds plugins by this constant.
PRAXIS_PLUGIN = True


class CodingStackJudgment:
    """A bare judgment source: carries stack-specific domains, composes nothing."""

    # Non-empty source string. Becomes `owner` on every domain this plugin ships,
    # and this plugin's namespace + precedence identity.
    source = "coding-stack"

    # Absolute path to this plugin's own domains dir, derived from the module
    # file so it is portable — NOT derived from the consuming root.
    domains_dir = Path(__file__).resolve().parent / "domains"

    def __init__(self, root):
        # `root` is the consuming praxis root praxis hands to the factory. A bare
        # judgment plugin does not need it, but the signature must accept it.
        self.root = root

    def contribute(self, situation) -> list:
        """No-op: this plugin only carries judgment; corpora composes it."""
        return []


def make(root) -> "CodingStackJudgment":
    """Factory. Register via `coding_stack_plugin:make` in the root's config."""
    return CodingStackJudgment(root)
