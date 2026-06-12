"""Phase 3 structural tests for the plain-language "Your plan" view.

The renderer stays deterministic (no model calls). These tests assert the
friendly overview that render_markdown adds above the detailed sections:
a "where to start" line, a "Start today" vs. "Comes after" split driven by
dependencies, and per-area sizes stated in WORDS (small/medium/large) rather
than story-point numbers or invented calendar time. Priority is optional and
must only nudge order when present.
"""

import pytest

from ticketly import render


def _epic(eid, title="Area"):
    return {
        "id": eid, "title": title, "type": "Epic", "parent": None,
        "status": "To Do", "effort": 0, "dependencies": [],
        "description": "d", "acceptance_criteria": [], "needs_clarification": False,
    }


def _task(tid, parent, effort=3, deps=None, title=None, priority=None):
    t = {
        "id": tid, "title": title or f"Do {tid}", "type": "Task", "parent": parent,
        "status": "To Do", "effort": effort, "dependencies": deps or [],
        "description": "d", "acceptance_criteria": ["it works"],
        "needs_clarification": False,
    }
    if priority is not None:
        t["priority"] = priority
    return t


def _backlog(tickets):
    return {"project": "Demo Project", "tickets": tickets}


@pytest.fixture
def simple():
    # ARC-001 is free; INF-001 waits on ARC-001.
    return _backlog([
        _epic("EPIC-ARC", "Architecture"),
        _epic("EPIC-INF", "Infra"),
        _task("ARC-001", "EPIC-ARC", effort=3),
        _task("INF-001", "EPIC-INF", effort=2, deps=["ARC-001"]),
    ])


# --- section presence & placement ---------------------------------------

def test_your_plan_section_present(simple):
    assert "## Your plan" in render.render_markdown(simple)


def test_your_plan_sits_above_first_epic(simple):
    md = render.render_markdown(simple)
    assert md.index("## Your plan") < md.index("## EPIC-ARC")


# --- start today vs. comes after ----------------------------------------

def test_start_today_lists_dependency_free_tasks(simple):
    md = render.render_markdown(simple)
    start_block = md.split("**Start today**")[1].split("**Comes after**")[0]
    assert "ARC-001" in start_block
    assert "INF-001" not in start_block


def test_comes_after_names_the_blocker(simple):
    md = render.render_markdown(simple)
    after_block = md.split("**Comes after**")[1].split("**How big")[0]
    assert "INF-001" in after_block
    assert "waits on ARC-001" in after_block


def test_where_to_start_points_at_first_free_task(simple):
    md = render.render_markdown(simple)
    line = next(l for l in md.splitlines() if l.startswith("**Where to start:**"))
    assert "ARC-001" in line


# --- sizes in words, never numbers --------------------------------------

def test_size_buckets():
    assert render._size_word(0) == "small"
    assert render._size_word(render._SIZE_SMALL_MAX) == "small"
    assert render._size_word(render._SIZE_SMALL_MAX + 1) == "medium"
    assert render._size_word(render._SIZE_MEDIUM_MAX) == "medium"
    assert render._size_word(render._SIZE_MEDIUM_MAX + 1) == "large"


def test_area_sizes_use_words_not_points(simple):
    md = render.render_markdown(simple)
    big_block = md.split("**How big each area is:**")[1].split("## EPIC")[0]
    assert "small" in big_block
    # the headline area lines must not leak a raw point count like "3 points"
    assert "point" not in big_block


def test_large_area_reported_as_large():
    # 8 + 8 = 16 points of children -> over the medium ceiling -> "large".
    data = _backlog([
        _epic("EPIC-BIG", "Big"),
        _task("BIG-001", "EPIC-BIG", effort=8),
        _task("BIG-002", "EPIC-BIG", effort=8),
    ])
    big_block = render.render_markdown(data).split("**How big each area is:**")[1]
    assert "Big: large" in big_block


# --- priority is optional ------------------------------------------------

def test_order_is_pure_dependency_when_no_priority(simple):
    # two free tasks, no priority anywhere -> ordered by id via build_order.
    data = _backlog([
        _epic("EPIC-A"), _epic("EPIC-B"),
        _task("AAA-001", "EPIC-A"), _task("BBB-001", "EPIC-B"),
    ])
    md = render.render_markdown(data)
    start_block = md.split("**Start today**")[1].split("**Comes after**")[0]
    assert start_block.index("AAA-001") < start_block.index("BBB-001")


def test_high_priority_floats_to_top_when_present():
    # BBB-001 sorts after AAA-001 by id, but High priority pulls it first.
    data = _backlog([
        _epic("EPIC-A"), _epic("EPIC-B"),
        _task("AAA-001", "EPIC-A"),
        _task("BBB-001", "EPIC-B", priority="High"),
    ])
    md = render.render_markdown(data)
    start_block = md.split("**Start today**")[1].split("**Comes after**")[0]
    assert start_block.index("BBB-001") < start_block.index("AAA-001")


# --- degenerate input ----------------------------------------------------

def test_epics_only_backlog_has_no_plan_section():
    data = _backlog([_epic("EPIC-A")])  # no Tasks -> empty build order
    md = render.render_markdown(data)
    assert "## Your plan" not in md
