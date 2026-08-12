"""general — a bare judgment plugin.

Carries hand-authored, stack-agnostic coding-judgment domain files for the
corpora composer to discover and inject. It does no composing itself:
`contribute` is a no-op. Corpora finds this plugin via `contributors_for(root)`,
reads `*.md` from `domains_dir`, and stamps every domain `owner = "general"`.
"""

from __future__ import annotations

from pathlib import Path

# Marker: identifies this module as a praxis plugin's main module (the file that
# carries `source` + `make`). Layered discovery finds plugins by this constant,
# statically, never by importing or by filename.
PRAXIS_PLUGIN = True


class GeneralJudgment:
    """A bare judgment source: carries domains, composes nothing."""

    # Non-empty source string. Becomes `owner` on every domain this plugin ships,
    # and this plugin's namespace + precedence identity.
    source = "general"

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


def make(root) -> "GeneralJudgment":
    """Factory. Register via `general_plugin:make` in the root's config."""
    return GeneralJudgment(root)
