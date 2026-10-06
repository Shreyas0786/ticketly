"""How the estimation model, totals, owners and legacy points are displayed.

Markdown and tasks.md show the model, hours and points separately, Unestimated
tasks and partial totals, per-person assigned versus Done, explicit work, and
legacy points kept apart. Both CSV layouts keep their original columns in place
and append the estimation, tracking, total and baseline columns.
"""

import csv
import io
import json
from pathlib import Path

from ticketly import estimate as est
from ticketly import render
from estimation_builders import (ON, by_id, epic, estimate, fib_backlog, hours_backlog,
                                 recorded, task)

ROOT = Path(__file__).resolve().parent.parent
HOURS_EXAMPLE = ROOT / "ticketly" / "data" / "examples" / "hours-backlog.json"


def _team():
    return recorded(hours_backlog(
        epic(),
        task("API-001", estimate=estimate(5, 2, 0.5, 0.5, level=2), assignee="Person A",
             status="Done"),
        task("API-002", estimate=estimate(5, 2, 0.5, 0.5, level=3), assignee="Person A",
             status="In Review"),
        task("API-003", assignee="Person B", needs_clarification=True),
        task("API-004", estimate=estimate(2, 0.5, 0.25, 0.25, level=1), work_kind="client_prep"),
    ))


def _rows(text):
    return list(csv.DictReader(io.StringIO(text)))


# --- markdown -----------------------------------------------------------------

def test_markdown_states_the_model_and_separates_points_from_hours():
    md = render.render_markdown(_team())
    assert "**Estimation:** Hours-based points" in md
    assert "not elapsed hours" in md
    # 8.8 + 10.0 + 3.0 points; 8 + 8 + 3 standard hours; one Unestimated task
    assert "21.8 points · 19 standard hours (partial: 1 of 4 tickets unestimated)" in md


def test_markdown_epic_total_is_displayed_separately_from_internal_effort():
    data = _team()
    md = render.render_markdown(data)
    assert "**Total:** 21.8 points · 19 standard hours (partial" in md
    assert by_id(data, "EPIC-API")["effort"] == 0


def test_markdown_shows_unestimated_and_the_estimate_basis():
    md = render.render_markdown(_team())
    assert "**API-003 estimate:** Unestimated." in md
    assert ("5 implementation + 2 testing + 0.5 self-review + 0.5 handoff = 8 standard hours "
            "· level 2 Standard (×1.10) = 8.8 points") in md


def test_team_totals_separate_assigned_from_done():
    md = render.render_markdown(_team())
    assert "## Team totals" in md
    assert "| Person A | 2 | 16 | 18.8 | 1 | 8 | 8.8 |" in md
    assert "| Person B | 1 | 0 | 0.0 (partial) | 0 | 0 | 0.0 |" in md
    assert "| Unassigned | 1 | 3 | 3.0 | 0 | 0 | 0.0 |" in md
    assert "reviewed and meets its acceptance criteria" in md


def test_explicit_work_is_counted_on_its_own():
    md = render.render_markdown(_team())
    assert "## Explicit work" in md
    assert "| Client preparation | 1 | 3 | 3.0 |" in md


def test_hours_model_does_not_use_fibonacci_size_words():
    block = render.render_markdown(_team()).split("**How big each area is:**")[1].split("## EPIC")[0]
    assert "21.8 points · 19 standard hours (4 tickets, 1 unestimated)" in block
    for word in ("small", "medium", "large"):
        assert word not in block


def test_fibonacci_markdown_is_unchanged_in_kind():
    data = fib_backlog(epic(), task("API-001", effort=3), task("API-002", effort=5))
    md = render.render_markdown(data)
    assert "1 epic · 2 tickets · 8 points" in md
    assert "**Estimation:** Fibonacci points (1, 2, 3, 5, 8, 13)." in md
    assert "| ID | Title | Effort | Dependencies | Status |" in md
    assert ": medium (2 tickets)" in md
    assert "## Team totals" not in md  # nobody assigned yet


def test_fibonacci_team_totals_when_owners_exist():
    data = recorded(fib_backlog(epic(), task("API-001", effort=3, assignee="Person A", status="Done"),
                                task("API-002", effort=5, assignee="Person A"), marked=True))
    md = render.render_markdown(data)
    assert "| Person A | 2 | 8 | 1 | 3 |" in md


def test_legacy_points_are_reported_separately_after_a_switch():
    data = fib_backlog(epic(), task("API-001", effort=5, status="Done", assignee="Person A"),
                       task("API-002", effort=8))
    data = est.switch_model(data, to="hours", reason="adopt hours", on=ON).data
    md = render.render_markdown(data)
    assert "**Legacy Fibonacci points:** 13 points across 2 tickets (1 completed before the switch)" in md
    assert "never added to the totals above" in md
    assert "Legacy 5" in md  # the completed task keeps its legacy points
    assert "completed under Fibonacci points" in md
    assert "Previously 8 Fibonacci points (legacy)" in md


def test_shipped_example_renders():
    data = render.load_backlog(HOURS_EXAMPLE)
    md = render.render_markdown(data)
    assert "**WEB-004 split:** takes over scope from WEB-002" in md
    assert "Unestimated" in md


# --- tasks.md -----------------------------------------------------------------

def test_tasks_md_shows_points_hours_owner_and_review():
    md = render.render_tasks_md(_team())
    assert "> Check a box only when the work has been reviewed and meets all its acceptance criteria." in md
    assert "> Estimation: Hours-based points." in md
    assert "- [x] **API-001 - Task API-001**" in md
    assert "**API-002 - Task API-002** 🔎" in md
    assert "  - 8.8 points (8 standard hours, level 2) · Depends on: nothing · Owner: Person A" in md
    assert "  - Unestimated · Depends on: nothing · Owner: Person B" in md


# --- csv layouts ----------------------------------------------------------------

def test_standard_csv_keeps_original_columns_and_appends_new_ones():
    assert render.CSV_COLUMNS[:11] == render.LEGACY_CSV_COLUMNS
    assert render.LEGACY_CSV_COLUMNS[-1] == "assignee"
    assert render.CSV_COLUMNS[-1] == "ticketly_baseline"
    rows = list(csv.reader(io.StringIO(render.render_csv(_team()))))
    assert rows[0] == render.CSV_COLUMNS


def test_standard_csv_cells():
    rows = {r["id"]: r for r in _rows(render.render_csv(_team()))}
    epic_row, done, unest = rows["EPIC-API"], rows["API-001"], rows["API-003"]
    assert epic_row["effort"] == "0"                      # internal Epic effort
    assert epic_row["points_total"] == "21.8"             # displayed total, separate
    assert epic_row["hours_total"] == "19"
    assert epic_row["points_total_partial"] == "true"
    assert done["effort"] == "8.8" and done["estimated_hours"] == "8"
    assert done["hours_implementation"] == "5" and done["hours_self_review"] == "0.5"
    assert done["difficulty_level"] == "2" and done["estimate_confidence"] == "high"
    assert done["estimation_model"] == "hours" and done["rubric_version"] == "hours-v1"
    assert done["assignee"] == "Person A" and done["status"] == "Done"
    assert unest["effort"] == "Unestimated" and unest["estimated_hours"] == ""
    assert rows["API-004"]["work_kind"] == "client_prep"
    assert all(r["ticketly_baseline"].startswith("tb1:s:") for r in rows.values())
    assert all(r["change_reason"] == "" for r in rows.values())


def test_notion_csv_keeps_original_columns_first():
    headers = [h for h, _ in render.NOTION_COLUMNS]
    assert headers[:13] == render.LEGACY_NOTION_HEADERS
    assert headers[0] == "Name"
    rows = {r["ID"]: r for r in _rows(render.render_notion_csv(_team()))}
    assert rows["EPIC-API"]["Effort"] == ""
    assert rows["EPIC-API"]["Points Total"] == "21.8"
    assert rows["EPIC-API"]["Total Partial"] == "Yes"
    assert rows["API-001"]["Effort"] == "8.8"
    assert rows["API-001"]["Testing Hours"] == "2"
    assert rows["API-003"]["Effort"] == "Unestimated"
    assert rows["API-001"]["Ticketly Baseline"].startswith("tb1:n:")


def test_legacy_columns_in_csv_after_a_switch():
    data = est.switch_model(fib_backlog(epic(), task("API-001", effort=5, status="Done")),
                            to="hours", reason="adopt", on=ON).data
    row = {r["id"]: r for r in _rows(render.render_csv(data))}["API-001"]
    assert row["legacy_model"] == "fibonacci" and row["legacy_effort"] == "5"
    assert row["effort"] == ""  # completed legacy task: not part of the new points


def test_exports_are_deterministic():
    data = _team()
    assert render.render_csv(data) == render.render_csv(json.loads(json.dumps(data)))
    assert render.render_notion_csv(data) == render.render_notion_csv(data)
