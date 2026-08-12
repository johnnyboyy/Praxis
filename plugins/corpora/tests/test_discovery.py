"""Discovery & precedence tests. The precedence cases drive `merge_pool`
directly with populated (source, dir) pairs; `discover_domain_dirs` is checked
for the always-present project entry.
"""

import io
import tempfile
import textwrap
from contextlib import redirect_stderr
from pathlib import Path

from corpora import merge_pool
from corpora.discovery import discover_domain_dirs


def _domain_md(id_, subject="coding", posture="neutral"):
    return textwrap.dedent(
        f"""\
        ---
        id: {id_}
        subject: {subject}
        posture: {posture}
        ---

        conventions:
          - id: c1
            rule: rule for {id_}
        principles:
          - id: p1
            rule: principle for {id_}
            condition: always
            reason: because {id_}
        """
    )


def _mkdir(base: Path, name: str) -> Path:
    d = base / name
    d.mkdir(parents=True)
    return d


def _write(directory: Path, filename: str, content: str) -> Path:
    p = directory / filename
    p.write_text(content, encoding="utf-8")
    return p


def test_project_overrides_plugin_wholesale():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        plugin_dir = _mkdir(base, "uiux")
        project_dir = _mkdir(base, "project")
        _write(plugin_dir, "color.md", _domain_md("color", subject="design"))
        _write(project_dir, "color.md", _domain_md("color", subject="design"))

        pool = merge_pool([("uiux", plugin_dir), ("project", project_dir)])

        fqs = {d.fq for d in pool}
        assert fqs == {"project/color"}
        # plugin version fully dropped, not field-merged
        assert all(d.owner == "project" for d in pool)


def test_peer_plugins_same_id_coexist():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        uiux = _mkdir(base, "uiux")
        theme = _mkdir(base, "theme")
        _write(uiux, "color.md", _domain_md("color", subject="design"))
        _write(theme, "color.md", _domain_md("color", subject="design"))

        pool = merge_pool([("uiux", uiux), ("theme", theme)])

        fqs = sorted(d.fq for d in pool)
        assert fqs == ["theme/color", "uiux/color"]


def test_same_owner_id_twice_is_hard_error():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        d = _mkdir(base, "general")
        _write(d, "a.md", _domain_md("dup"))
        _write(d, "b.md", _domain_md("dup"))

        buf = io.StringIO()
        with redirect_stderr(buf):
            pool = merge_pool([("general", d)])

        # duplicate skipped (not last-wins): exactly one survivor
        assert [x.fq for x in pool] == ["general/dup"]
        # and the collision was reported
        assert "duplicate" in buf.getvalue()
        assert "general/dup" in buf.getvalue()


def test_different_bare_ids_coexist():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        d = _mkdir(base, "general")
        _write(d, "one.md", _domain_md("naming"))
        _write(d, "two.md", _domain_md("testing"))

        pool = merge_pool([("general", d)])
        assert sorted(x.fq for x in pool) == ["general/naming", "general/testing"]


def test_discover_always_includes_project_entry_even_when_absent():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        # no contributors registered, no .praxis/domains dir on disk
        dirs = discover_domain_dirs(root)
        assert ("project", root / ".praxis" / "domains") in dirs
        # with nothing registered, the project entry is the only one
        assert dirs == [("project", root / ".praxis" / "domains")]
