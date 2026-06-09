"""Phase 3 structural tests for the Assignee column.

Assignee is an optional ticket field (``string | null``, default null), surfaced
as an empty, fill-it-in-later column in both the plain CSV and the Notion-import
CSV. These tests pin the column's presence and position and assert that a
missing/null assignee renders as a blank cell while a set value renders verbatim.
"""

import csv
import io
from pathlib import Path

import pytest

from ticketly import render

ROOT = Path(__file__).resolve().parent.parent
BACKLOG_PATH = ROOT / "ticketly" / "data" / "examples" / "sample-release-backlog.json"


@pytest.fixture(scope="module")
def backlog():
    return render.load_backlog(BACKLOG_PATH)


def _ticket(**overrides):
    base = {
        "id": "API-001", "title": "A task", "type": "Task", "parent": "EPIC-API",
        "status": "To Do", "effort": 2, "dependencies": [], "description": "x.",
        "acceptance_criteria": ["does the thing"], "needs_clarification": False,
    }
    base.update(overrides)
    return base


def _backlog(ticket):
    return {"project": "Demo Project", "tickets": [
        {"id": "EPIC-API", "title": "API", "type": "Epic", "parent": None,
         "status": "To Do", "effort": 0, "dependencies": [], "description": "API.",
         "acceptance_criteria": [], "needs_clarification": False},
        ticket,
    ]}


# --- schema --------------------------------------------------------------

def test_schema_accepts_string_assignee():
    render.validate_backlog(_backlog(_ticket(assignee="Shreyas")))


def test_schema_accepts_null_assignee():
    render.validate_backlog(_backlog(_ticket(assignee=None)))


def test_schema_accepts_missing_assignee():
    # assignee is optional: a ticket without the key is still valid.
    render.validate_backlog(_backlog(_ticket()))


# --- plain csv -----------------------------------------------------------

def test_csv_columns_include_assignee():
    assert "assignee" in render.CSV_COLUMNS


def test_csv_assignee_is_last_column():
    assert render.CSV_COLUMNS[-1] == "assignee"


def test_csv_header_carries_assignee(backlog):
    rows = list(csv.reader(io.StringIO(render.render_csv(backlog))))
    assert "assignee" in rows[0]


def test_csv_blank_when_assignee_missing():
    out = render.render_csv(_backlog(_ticket()))
    row = next(r for r in csv.DictReader(io.StringIO(out)) if r["id"] == "API-001")
    assert row["assignee"] == ""


def test_csv_blank_when_assignee_null():
    out = render.render_csv(_backlog(_ticket(assignee=None)))
    row = next(r for r in csv.DictReader(io.StringIO(out)) if r["id"] == "API-001")
    assert row["assignee"] == ""


def test_csv_renders_assignee_value():
    out = render.render_csv(_backlog(_ticket(assignee="Shreyas")))
    row = next(r for r in csv.DictReader(io.StringIO(out)) if r["id"] == "API-001")
    assert row["assignee"] == "Shreyas"


# --- notion csv (pre-existing column, guarded against regression) --------

def test_notion_csv_has_assignee_column(backlog):
    rows = list(csv.reader(io.StringIO(render.render_notion_csv(backlog))))
    assert "Assignee" in rows[0]


def test_notion_csv_renders_assignee_value():
    out = render.render_notion_csv(_backlog(_ticket(assignee="Priya")))
    row = next(r for r in csv.DictReader(io.StringIO(out)) if r["ID"] == "API-001")
    assert row["Assignee"] == "Priya"
