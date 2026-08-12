"""The coding-stack plugin: a bare judgment source carrying stack-specific domains.

Covers the contributor contract (source + domains_dir + no-op contribute), that
every domain parses under the corpora schema, and — the property that makes this
plugin stack-*specific* — that every domain carries a non-empty `applies-when`
so corpora only composes it for a matching project shape.
"""

import glob
from pathlib import Path

import coding_stack_plugin
from corpora.parser import parse_domain_file

DOMAINS_DIR = Path(coding_stack_plugin.CodingStackJudgment.domains_dir)
DOMAIN_FILES = sorted(glob.glob(str(DOMAINS_DIR / "*.md")))

EXPECTED_IDS = {
    "coding-ts",
    "coding-react",
    "coding-nextjs",
    "coding-expo",
    "css",
    "dependency-management-expo",
    "release-readiness-expo",
}


# --- the contributor contract ---------------------------------------------------

def test_make_exposes_source_and_domains_dir():
    plugin = coding_stack_plugin.make("/some/root")
    assert plugin.source == "coding-stack"
    assert Path(plugin.domains_dir) == DOMAINS_DIR
    assert Path(plugin.domains_dir).is_dir()


def test_contribute_is_a_noop():
    plugin = coding_stack_plugin.make("/some/root")
    assert plugin.contribute(object()) == []


def test_contributor_validates():
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from contributors import validate_contributor

    assert validate_contributor(coding_stack_plugin.make("/some/root")) == []


# --- every domain parses --------------------------------------------------------

def test_expected_domain_set_present():
    ids = {parse_domain_file(f, owner="coding-stack").id for f in DOMAIN_FILES}
    assert ids == EXPECTED_IDS


def test_every_domain_parses_and_is_owned_and_coding():
    for f in DOMAIN_FILES:
        d = parse_domain_file(f, owner="coding-stack")
        assert d.owner == "coding-stack"
        assert d.subject == "coding"
        assert d.posture in {"convergent", "divergent", "neutral"}
        assert d.principles or d.conventions


# --- the stack-specific property: applies-when gates every domain ---------------

def test_every_domain_has_nonempty_applies_when():
    for f in DOMAIN_FILES:
        d = parse_domain_file(f, owner="coding-stack")
        assert d.applies_when, f"{d.id} must carry an applies-when clause"


def test_applies_when_axes_match_shape_model():
    by_id = {parse_domain_file(f, owner="coding-stack").id: parse_domain_file(
        f, owner="coding-stack") for f in DOMAIN_FILES}
    # Each domain gates on the expected shape axis.
    def axes(domain):
        return {k for cond in domain.applies_when for k in cond}

    assert axes(by_id["coding-ts"]) == {"language"}
    assert axes(by_id["coding-react"]) == {"framework"}
    assert axes(by_id["coding-nextjs"]) == {"framework"}
    assert axes(by_id["coding-expo"]) == {"framework"}
    assert axes(by_id["css"]) == {"styling"}
    assert axes(by_id["dependency-management-expo"]) == {"framework"}
    assert axes(by_id["release-readiness-expo"]) == {"framework"}
