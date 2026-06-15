"""Phase 3 structural tests for the Ticketly Markdown / CSV renderers.

Asserts the renderer validates input, that Markdown carries the expected
structure (header, per-epic sections, task table columns, acceptance criteria),
that CSV has the pinned header and one row per ticket, and that the argparse CLI
rejects bad input. The CLI argv is checked without invoking a subprocess binary.
"""

import csv
import io
import json
from pathlib import Path

import pytest

from ticketly import render

ROOT = Path(__file__).resolve().parent.parent
BACKLOG_PATH = ROOT / "ticketly" / "data" / "examples" / "sample-release-backlog.json"


@pytest.fixture(scope="module")
def backlog():
    return render.load_backlog(BACKLOG_PATH)


# --- validation ----------------------------------------------------------

def test_load_backlog_validates_against_schema():
    # a clean load returns the parsed dict
    data = render.load_backlog(BACKLOG_PATH)
    assert data["project"]


def test_validate_rejects_malformed_backlog():
    bad = {"company": "Demo Company", "project": "Demo Project", "tickets": [
        {"id": "bad-id", "title": "x", "type": "Task", "parent": None,
         "status": "To Do", "effort": 4, "dependencies": [],
         "description": "x", "acceptance_criteria": [], "needs_clarification": False},
    ]}
    with pytest.raises(Exception):
        render.validate_backlog(bad)


# --- markdown ------------------------------------------------------------

def test_markdown_has_title_header(backlog):
    md = render.render_markdown(backlog)
    assert md.startswith(f"# {backlog['company']} — {backlog['project']} backlog")


def test_markdown_title_drops_company_when_absent(backlog):
    # existing-project backlogs omit company; the title is then project-only.
    no_company = {k: v for k, v in backlog.items() if k != "company"}
    md = render.render_markdown(no_company)
    assert md.startswith(f"# {backlog['project']} backlog")
    assert " — " not in md.splitlines()[0]


def test_markdown_title_keeps_company_when_present(backlog):
    md = render.render_markdown(backlog)
    assert md.splitlines()[0] == f"# {backlog['company']} — {backlog['project']} backlog"


def test_markdown_has_an_epic_section_per_epic(backlog):
    md = render.render_markdown(backlog)
    epics = [t for t in backlog["tickets"] if t["type"] == "Epic"]
    for epic in epics:
        assert f"## {epic['id']} — {epic['title']}" in md


def test_markdown_table_has_expected_columns(backlog):
    md = render.render_markdown(backlog)
    assert "| ID | Title | Effort | Dependencies | Status |" in md


def test_markdown_lists_every_task_id(backlog):
    md = render.render_markdown(backlog)
    for t in backlog["tickets"]:
        if t["type"] == "Task":
            assert t["id"] in md


def test_markdown_includes_acceptance_criteria(backlog):
    md = render.render_markdown(backlog)
    for t in backlog["tickets"]:
        for crit in t.get("acceptance_criteria", []):
            assert crit in md


def test_markdown_pluralizes_counts():
    assert render._count(1, "epic") == "1 epic"
    assert render._count(4, "ticket") == "4 tickets"


def test_markdown_flags_needs_clarification():
    data = {
        "company": "Demo Company", "project": "Demo Project",
        "tickets": [
            {"id": "EPIC-API", "title": "API", "type": "Epic", "parent": None,
             "status": "To Do", "effort": 0, "dependencies": [],
             "description": "Backend.", "acceptance_criteria": [],
             "needs_clarification": False},
            {"id": "API-001", "title": "Unclear thing", "type": "Task",
             "parent": "EPIC-API", "status": "To Do", "effort": 2,
             "dependencies": [], "description": "TBD.",
             "acceptance_criteria": ["something"], "needs_clarification": True},
        ],
    }
    md = render.render_markdown(data)
    assert "⚠️" in md


# --- csv -----------------------------------------------------------------

def test_csv_header_is_pinned(backlog):
    out = render.render_csv(backlog)
    rows = list(csv.reader(io.StringIO(out)))
    assert rows[0] == render.CSV_COLUMNS


def test_csv_has_one_row_per_ticket(backlog):
    out = render.render_csv(backlog)
    rows = list(csv.reader(io.StringIO(out)))
    assert len(rows) == 1 + len(backlog["tickets"])


def test_csv_joins_list_fields_with_semicolons(backlog):
    out = render.render_csv(backlog)
    rows = list(csv.DictReader(io.StringIO(out)))
    rel004 = next(r for r in rows if r["id"] == "REL-004")
    assert rel004["dependencies"] == "REL-002; REL-003"


def test_csv_renders_booleans_lowercase(backlog):
    out = render.render_csv(backlog)
    assert ",false" in out


# --- cli -----------------------------------------------------------------

def test_cli_defaults_to_core_format():
    args = render.build_parser().parse_args(["some.json"])
    assert args.format == "core"
    assert args.out_dir is None


def test_cli_rejects_bad_format():
    with pytest.raises(SystemExit):
        render.build_parser().parse_args(["some.json", "--format", "pdf"])


def test_cli_requires_a_backlog_argument():
    with pytest.raises(SystemExit):
        render.build_parser().parse_args([])


def test_cli_writes_files(tmp_path, backlog):
    out_dir = tmp_path / "ticketly"
    rc = render.main([str(BACKLOG_PATH), "--format", "core", "--out-dir", str(out_dir)])
    assert rc == 0
    files = {p.name for p in out_dir.iterdir()}
    assert files == {"backlog.md", "backlog.csv", "tasks.md"}
    # written files are non-empty and the CSV re-parses
    md_text = (out_dir / "backlog.md").read_text()
    assert md_text.startswith("# ")
    assert (out_dir / "tasks.md").read_text().startswith("# ")
    csv_rows = list(csv.reader((out_dir / "backlog.csv").open()))
    assert csv_rows[0] == render.CSV_COLUMNS
