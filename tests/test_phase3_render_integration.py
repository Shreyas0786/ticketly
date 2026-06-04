"""Phase 3 tests for the renderer's integration with the integrity checker.

The renderer must refuse a backlog with integrity errors (not just schema
errors), and a clean render must include the topologically sorted Build order
section.
"""

import json
from pathlib import Path

import pytest

from ticketly import render

ROOT = Path(__file__).resolve().parent.parent
CLEAN = ROOT / "examples" / "sample-release-backlog.json"


def _epic(tid="EPIC-API", **kw):
    base = dict(id=tid, title="API", type="Epic", parent=None, status="To Do",
               effort=0, dependencies=[], description="x", acceptance_criteria=[],
               needs_clarification=False)
    base.update(kw)
    return base


def _task(tid="API-001", parent="EPIC-API", **kw):
    base = dict(id=tid, title="A task", type="Task", parent=parent, status="To Do",
               effort=2, dependencies=[], description="x",
               acceptance_criteria=["done"], needs_clarification=False)
    base.update(kw)
    return base


def _write(tmp_path, *tickets):
    bl = {"company": "Demo Company", "project": "Demo Project", "tickets": list(tickets)}
    p = tmp_path / "backlog.json"
    p.write_text(json.dumps(bl))
    return p


def test_load_backlog_raises_on_integrity_error(tmp_path):
    p = _write(tmp_path, _epic(), _task("API-001", dependencies=["API-999"]))
    with pytest.raises(render.BacklogIntegrityError) as exc:
        render.load_backlog(p)
    assert "dangling_dependency" in str(exc.value)


def test_load_backlog_passes_clean_backlog():
    data = render.load_backlog(CLEAN)
    assert data["project"]


def test_warnings_do_not_block_render(tmp_path):
    # duplicate titles are a warning, not an error — render should still work
    p = _write(tmp_path, _epic(),
               _task("API-001", title="Same"), _task("API-002", title="same"))
    data = render.load_backlog(p)  # does not raise
    assert render.render_markdown(data)


def test_markdown_has_build_order_section():
    data = render.load_backlog(CLEAN)
    md = render.render_markdown(data)
    assert "## Build order" in md


def test_build_order_section_lists_tasks_in_dependency_order():
    data = render.load_backlog(CLEAN)
    md = render.render_markdown(data)
    section = md.split("## Build order", 1)[1]
    # REL-002 has no deps; REL-005 depends transitively on it — must come later
    assert section.index("REL-002") < section.index("REL-005")
