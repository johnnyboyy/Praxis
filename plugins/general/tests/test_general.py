"""The general plugin: a bare judgment source carrying stack-agnostic domains.

A judgment plugin's whole contract is to expose a `domains_dir` of domain files;
discovering and parsing those domains is corpora's job, so this suite imports
corpora zero times. All that remains is a contributor smoke test.
"""

from pathlib import Path

import general_plugin


def test_contributor_smoke():
    plugin = general_plugin.make("/some/root")
    assert plugin.source
    domains = Path(plugin.domains_dir)
    assert domains.is_dir()
    assert list(domains.glob("*.md")), f"no domain files under {domains}"
