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

PRAXIS_PLUGIN = True

class CodingStackJudgment:

    source = "coding-stack"

    domains_dir = Path(__file__).resolve().parent / "domains"

    def __init__(self, root):

        self.root = root

    def contribute(self, situation) -> list:
        return []

def make(root) -> "CodingStackJudgment":
    return CodingStackJudgment(root)
