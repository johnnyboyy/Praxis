"""general — a bare judgment plugin.

Carries hand-authored, stack-agnostic coding-judgment domain files for the
corpora composer to discover and inject. It does no composing itself:
`contribute` is a no-op. Corpora finds this plugin via `contributors_for(root)`,
reads `*.md` from `domains_dir`, and stamps every domain `owner = "general"`.
"""

from __future__ import annotations

from pathlib import Path

PRAXIS_PLUGIN = True

class GeneralJudgment:

    source = "general"

    domains_dir = Path(__file__).resolve().parent / "domains"

    def __init__(self, root):

        self.root = root

    def contribute(self, situation) -> list:
        return []

def make(root) -> "GeneralJudgment":
    return GeneralJudgment(root)
