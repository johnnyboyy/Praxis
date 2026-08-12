"""The general plugin: a bare judgment source carrying stack-agnostic domains.

Covers the contributor contract (source + domains_dir + no-op contribute), that
every domain parses under the corpora schema, and — the property that makes this
plugin stack-*agnostic* — that every domain carries an empty `applies-when` so
corpora composes it for every project shape.
"""

import glob
from pathlib import Path

import general_plugin
from corpora.parser import parse_domain_file

DOMAINS_DIR = Path(general_plugin.GeneralJudgment.domains_dir)
DOMAIN_FILES = sorted(glob.glob(str(DOMAINS_DIR / "*.md")))


# --- the contributor contract ---------------------------------------------------

def test_make_exposes_source_and_domains_dir():
    plugin = general_plugin.make("/some/root")
    assert plugin.source == "general"
    assert Path(plugin.domains_dir) == DOMAINS_DIR
    assert Path(plugin.domains_dir).is_dir()


def test_contribute_is_a_noop():
    plugin = general_plugin.make("/some/root")
    assert plugin.contribute(object()) == []


def test_contributor_validates():
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from contributors import validate_contributor

    assert validate_contributor(general_plugin.make("/some/root")) == []


# --- every domain parses --------------------------------------------------------

def test_domain_glob_is_nonempty():
    assert DOMAIN_FILES, "expected at least one domain under domains/*.md"


def test_every_domain_parses_and_is_coding():
    for f in DOMAIN_FILES:
        d = parse_domain_file(f, owner="general")
        assert d.subject == "coding"


# --- the stack-agnostic property: applies-when is empty on every domain ----------

def test_every_domain_has_empty_applies_when():
    for f in DOMAIN_FILES:
        d = parse_domain_file(f, owner="general")
        assert not d.applies_when, f"{d.id} must be stack-agnostic (empty applies-when)"
