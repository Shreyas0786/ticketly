"""Phase 3 structural tests for the agent-ready tasks.md export.

tasks.md is the keystone the future tracker reads and an agent ticks off, so its
shape is a contract: one checkbox per Task anchored on the ticket id, status
mapped to the box, dependencies and acceptance criteria inline, grouped by epic
in dependency order. These tests pin that contract.
"""

import csv as csvmod
from pathlib import Path

from ticketly import render

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / "ticketly" / "data" / "examples" / "house-style-backlog.json"


def _epic(tid, title="An area", **kw):
    base = dict(id=tid, title=title, type="Epic", parent=None, status="To Do",
                effort=0, dependencies=[], description="x",
                acceptance_criteria=[], needs_clarification=False)
    base.update(kw)
    return base


def _task(tid, parent, title="A task", **kw):
    base = dict(id=tid, title=title, type="Task", parent=parent, status="To Do",
                effort=2, dependencies=[], description="x",
                acceptance_criteria=["a thing is true"], needs_clarification=False)
    base.update(kw)
    return base


def _backlog(*tickets, project="Demo Project", company="Demo Company"):
    data = {"project": project, "tickets": list(tickets)}
    if company is not None:
        data["company"] = company
    return data


# --- heading and title ---------------------------------------------------

def test_starts_with_a_tasks_heading():
    md = render.render_tasks_md(_backlog(_epic("EPIC-API"), _task("API-001", "EPIC-API")))
    first = md.splitlines()[0]
    assert first.startswith("# ") and first.rstrip().endswith("tasks")


def test_company_optional_in_title():
    with_co = render.render_tasks_md(_backlog(_epic("EPIC-API"), _task("API-001", "EPIC-API")))
    assert with_co.splitlines()[0] == "# Demo Company — Demo Project tasks"
    without = render.render_tasks_md(
        _backlog(_epic("EPIC-API"), _task("API-001", "EPIC-API"), company=None))
    assert without.splitlines()[0] == "# Demo Project tasks"


# --- one checkbox per Task, anchored on the id ---------------------------

def test_one_checkbox_per_task_none_for_epics():
    data = _backlog(
        _epic("EPIC-API"), _task("API-001", "EPIC-API"), _task("API-002", "EPIC-API"),
        _epic("EPIC-INF"), _task("INF-001", "EPIC-INF"),
    )
    md = render.render_tasks_md(data)
    checkboxes = [ln for ln in md.splitlines() if ln.startswith("- [")]
    assert len(checkboxes) == 3  # three Tasks, zero Epics
    for tid in ("API-001", "API-002", "INF-001"):
        assert f"**{tid} — " in md
    # epic ids appear only as headings, never as checkboxes
    assert "- [ ] **EPIC-API" not in md


def test_status_maps_to_the_checkbox():
    data = _backlog(
        _epic("EPIC-API"),
        _task("API-001", "EPIC-API", status="Done"),
        _task("API-002", "EPIC-API", status="In Progress"),
        _task("API-003", "EPIC-API", status="To Do"),
    )
    md = render.render_tasks_md(data)
    assert "- [x] **API-001 — " in md
    assert "- [ ] **API-002 — " in md and "🚧" in md
    todo_line = next(ln for ln in md.splitlines() if "API-003" in ln)
    assert todo_line.startswith("- [ ]") and "🚧" not in todo_line


def test_needs_clarification_is_flagged():
    data = _backlog(_epic("EPIC-API"), _task("API-001", "EPIC-API", needs_clarification=True))
    line = next(ln for ln in render.render_tasks_md(data).splitlines() if "API-001" in ln)
    assert "⚠️" in line


# --- inline detail -------------------------------------------------------

def test_dependencies_and_effort_render():
    data = _backlog(
        _epic("EPIC-API"),
        _task("API-001", "EPIC-API"),
        _task("API-002", "EPIC-API", dependencies=["API-001"], effort=5),
    )
    md = render.render_tasks_md(data)
    assert "Effort 5 · Depends on: API-001" in md
    assert "Depends on: nothing" in md  # API-001 has no deps


def test_acceptance_criteria_render_as_sub_bullets():
    data = _backlog(
        _epic("EPIC-API"),
        _task("API-001", "EPIC-API", acceptance_criteria=["alpha holds", "beta holds"]),
    )
    md = render.render_tasks_md(data)
    assert "  - alpha holds" in md and "  - beta holds" in md


# --- grouping and ordering -----------------------------------------------

def test_grouped_under_epic_headings():
    data = _backlog(_epic("EPIC-API", title="Backend"), _task("API-001", "EPIC-API"))
    assert "## EPIC-API — Backend" in render.render_tasks_md(data)


def test_empty_epics_are_skipped():
    data = _backlog(
        _epic("EPIC-API"), _task("API-001", "EPIC-API"),
        _epic("EPIC-NIL", title="Nothing here"),  # no children
    )
    assert "EPIC-NIL" not in render.render_tasks_md(data)


def test_within_epic_dependency_order():
    # API-002 is listed first but depends on API-001 — it must render second.
    data = _backlog(
        _epic("EPIC-API"),
        _task("API-002", "EPIC-API", dependencies=["API-001"]),
        _task("API-001", "EPIC-API"),
    )
    md = render.render_tasks_md(data)
    assert md.index("API-001") < md.index("API-002")


def test_orphan_tasks_land_under_unassigned():
    data = _backlog(
        _epic("EPIC-API"), _task("API-001", "EPIC-API"),
        _task("ZZZ-001", "EPIC-GONE"),  # parent is not a real epic
    )
    md = render.render_tasks_md(data)
    assert "## Unassigned" in md
    unassigned = md.split("## Unassigned", 1)[1]
    assert "ZZZ-001" in unassigned


# --- CLI wiring ----------------------------------------------------------

def test_format_tasks_writes_only_tasks_md(tmp_path):
    out = tmp_path / "ticketly"
    assert render.main([str(EXAMPLE), "--format", "tasks", "--out-dir", str(out)]) == 0
    assert {p.name for p in out.iterdir()} == {"tasks.md"}


def test_core_and_all_include_tasks_md(tmp_path):
    for fmt in ("core", "all"):
        out = tmp_path / fmt
        assert render.main([str(EXAMPLE), "--format", fmt, "--out-dir", str(out)]) == 0
        assert (out / "tasks.md").is_file()


def test_rendered_tasks_md_reparses_checkboxes(tmp_path):
    """Every checkbox line is well-formed GFM and carries a bold ticket id."""
    out = tmp_path / "ticketly"
    render.main([str(EXAMPLE), "--format", "tasks", "--out-dir", str(out)])
    lines = (out / "tasks.md").read_text().splitlines()
    boxes = [ln for ln in lines if ln.startswith("- [")]
    assert boxes, "no checkboxes rendered"
    for ln in boxes:
        assert ln.startswith(("- [ ]", "- [x]"))
        assert "**" in ln  # the bold id anchor
