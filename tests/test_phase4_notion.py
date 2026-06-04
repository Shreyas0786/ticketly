"""Phase 3 tests for the Notion-import CSV renderer (Phase 4 feature).

Asserts the Notion CSV leads with the title column (Notion's page title), maps
fields the way Notion import expects (Epic = parent, comma-separated
Dependencies for a multi-select, Yes/No checkbox, newline-joined acceptance
criteria, blank epic effort), re-parses cleanly, and that the CLI exposes the
notion / all formats and writes <project>.notion.csv.
"""

import csv
import io
from pathlib import Path

import pytest

from ticketly import render

ROOT = Path(__file__).resolve().parent.parent
BACKLOG = ROOT / "examples" / "sample-release-backlog.json"


@pytest.fixture(scope="module")
def backlog():
    return render.load_backlog(BACKLOG)


@pytest.fixture(scope="module")
def rows(backlog):
    out = render.render_notion_csv(backlog)
    return list(csv.DictReader(io.StringIO(out)))


def test_first_column_is_name_with_the_title(backlog):
    out = render.render_notion_csv(backlog)
    header = out.splitlines()[0]
    assert header.startswith("Name,"), "Notion uses the first column as the page title"
    rows = list(csv.reader(io.StringIO(out)))
    epic = next(t for t in backlog["tickets"] if t["type"] == "Epic")
    assert rows[1][0] == epic["title"]


def test_one_row_per_ticket(backlog, rows):
    assert len(rows) == len(backlog["tickets"])


def test_epic_column_holds_parent(rows):
    rel002 = next(r for r in rows if r["ID"] == "REL-002")
    assert rel002["Epic"] == "EPIC-REL"


def test_dependencies_are_comma_separated_for_multiselect(rows):
    rel004 = next(r for r in rows if r["ID"] == "REL-004")
    assert rel004["Dependencies"] == "REL-002, REL-003"


def test_needs_clarification_is_yes_no(rows):
    assert all(r["Needs Clarification"] in ("Yes", "No") for r in rows)


def test_acceptance_criteria_are_newline_joined(rows):
    rel002 = next(r for r in rows if r["ID"] == "REL-002")
    assert "\n" in rel002["Acceptance Criteria"]
    assert "database backup and restore tested" in rel002["Acceptance Criteria"]


def test_epic_effort_is_blank(rows):
    epic = next(r for r in rows if r["Type"] == "Epic")
    assert epic["Effort"] == ""


def test_task_effort_is_the_number(rows):
    rel005 = next(r for r in rows if r["ID"] == "REL-005")
    assert rel005["Effort"] == "8"


def test_header_columns_are_exactly_the_spec():
    headers = [h for h, _ in render.NOTION_COLUMNS]
    assert headers[0] == "Name"
    assert set(headers) == {
        "Name", "ID", "Type", "Status", "Effort", "Epic", "Dependencies",
        "Needs Clarification", "Description", "Acceptance Criteria",
        "Assignee", "Due Date", "Priority",
    }


# --- cli -----------------------------------------------------------------

def test_cli_accepts_notion_and_all_formats():
    for fmt in ("notion", "all", "both", "md", "csv"):
        args = render.build_parser().parse_args(["b.json", "--format", fmt])
        assert args.format == fmt


def test_cli_rejects_unknown_format():
    with pytest.raises(SystemExit):
        render.build_parser().parse_args(["b.json", "--format", "linear"])


def test_cli_notion_writes_suffixed_file(tmp_path):
    out_dir = tmp_path / "build"
    assert render.main([str(BACKLOG), "--format", "notion", "--out-dir", str(out_dir)]) == 0
    assert {p.name for p in out_dir.iterdir()} == {"demo-project.notion.csv"}


def test_cli_all_writes_three_files(tmp_path):
    out_dir = tmp_path / "build"
    assert render.main([str(BACKLOG), "--format", "all", "--out-dir", str(out_dir)]) == 0
    assert {p.name for p in out_dir.iterdir()} == {
        "demo-project.md", "demo-project.csv", "demo-project.notion.csv",
    }


def test_skill_documents_notion_export():
    skill = (ROOT / ".claude" / "skills" / "ticketly" / "SKILL.md").read_text()
    assert "--format notion" in skill
    assert ".notion.csv" in skill


def test_notion_csv_reparses(tmp_path):
    out_dir = tmp_path / "build"
    render.main([str(BACKLOG), "--format", "notion", "--out-dir", str(out_dir)])
    text = (out_dir / "demo-project.notion.csv").read_text()
    reparsed = list(csv.DictReader(io.StringIO(text)))
    assert reparsed and reparsed[0]["Name"]
