"""Edited CSV / Notion export -> validate and recalculate -> backlog.

Rows match by ticket ID; per-field export baselines tell untouched stale values
from conflicting edits; every error aborts the whole import with nothing written;
dry runs and no-op imports never touch the file; successful imports record history
and recalculate points.
"""

import csv
import io
import json

import pytest

from ticketly import cli, csv_import, render, validate
from ticketly import estimate as est
from estimation_builders import (by_id, epic, estimate, fib_backlog, hours_backlog, recorded,
                                 task)

ON = "2026-10-06"


def _backlog():
    return recorded(hours_backlog(
        epic(),
        task("API-001", estimate=estimate(5, 2, 0.5, 0.5, level=2), assignee="Person A"),
        task("API-002", estimate=estimate(2.5, 1, 0.25, 0.25, level=4), assignee="Person B"),
        task("API-003", needs_clarification=True),
    ))


def _edit(text, edits, notion=False):
    """Apply {ticket id: {column: value}} to an exported CSV's text."""
    rows = list(csv.reader(io.StringIO(text)))
    header = rows[0]
    id_col = header.index("ID" if notion else "id")
    for row in rows[1:]:
        for col, value in edits.get(row[id_col], {}).items():
            row[header.index(col)] = value
    buf = io.StringIO()
    csv.writer(buf, lineterminator="\n").writerows(rows)
    return buf.getvalue()


def _plan(data, text):
    return csv_import.plan_import(data, text, on=ON)


def _aborts(data, text, needle):
    with pytest.raises(csv_import.ImportAborted) as exc:
        _plan(data, text)
    assert any(needle in e for e in exc.value.errors), exc.value.errors


# --- round trips ----------------------------------------------------------------

@pytest.mark.parametrize("fmt", [render.render_csv, render.render_notion_csv])
def test_unedited_export_is_a_no_op(fmt):
    data = _backlog()
    report = _plan(data, fmt(data))
    assert not report.changed and report.changes == [] and report.warnings == []
    assert report.data == data


def test_standard_csv_edit_applies_records_and_recalculates():
    data = _backlog()
    text = _edit(render.render_csv(data), {"API-002": {
        "assignee": "Person C", "status": "In Progress", "hours_testing": "1.5",
        "change_reason": "A second regression scenario is needed"}})
    report = _plan(data, text)
    assert report.changed
    t = by_id(report.data, "API-002")
    assert t["assignee"] == "Person C" and t["status"] == "In Progress"
    assert t["estimate"]["hours_breakdown"]["testing"] == 1.5
    assert t["estimate"]["estimated_hours"] == 4.5
    assert t["effort"] == 6.3  # 4.5 x 1.40, recalculated
    fields = [e["field"] for e in t["history"]]
    assert fields == ["baseline", "assignee", "status", "estimate"]
    change = t["history"][-1]
    assert change["source"] == "import" and change["on"] == ON
    assert change["reason"] == "A second regression scenario is needed"
    assert change["from"]["effort"] == 5.6 and change["to"]["effort"] == 6.3
    render.validate_backlog(report.data)
    assert not validate.errors(validate.check_integrity(report.data))


def test_notion_export_with_bom_reordered_extra_columns_and_blank_rows():
    data = _backlog()
    text = _edit(render.render_notion_csv(data), {"API-001": {"Assignee": "Person C"}}, notion=True)
    rows = list(csv.reader(io.StringIO(text)))
    order = list(reversed(range(len(rows[0]))))  # Notion may reorder properties
    shuffled = [[r[i] for i in order] + ["2026-10-06 09:00"] for r in rows]
    shuffled[0][-1] = "Created time"  # an unrelated column Notion adds
    buf = io.StringIO()
    csv.writer(buf, lineterminator="\r\n").writerows(shuffled + [[""] * len(shuffled[0])])
    report = _plan(data, "﻿" + buf.getvalue())
    assert by_id(report.data, "API-001")["assignee"] == "Person C"
    assert any("Created time" in w for w in report.warnings)


def test_filling_in_an_unestimated_task_needs_no_reason():
    data = _backlog()
    text = _edit(render.render_csv(data), {"API-003": {
        "hours_implementation": "6", "hours_testing": "2", "hours_self_review": "0.5",
        "hours_handoff": "0.5", "difficulty_level": "3",
        "difficulty_reason": "Data migration with rollback", "estimate_confidence": "medium"}})
    t = by_id(_plan(data, text).data, "API-003")
    assert t["effort"] == 11.3  # 9 x 1.25 = 11.25, half-up
    assert t["estimate"]["rubric_version"] == "hours-v1"


def test_clearing_estimate_inputs_makes_a_task_unestimated():
    data = _backlog()
    blank = {k: "" for k in ("hours_implementation", "hours_testing", "hours_self_review",
                             "hours_handoff", "difficulty_level", "difficulty_reason",
                             "estimate_confidence")}
    text = _edit(render.render_csv(data), {"API-001": {**blank, "change_reason": "Scope unclear"}})
    t = by_id(_plan(data, text).data, "API-001")
    assert t["estimate"] is None and t["effort"] is None


def test_reimporting_the_same_edits_is_idempotent():
    data = _backlog()
    text = _edit(render.render_csv(data), {"API-001": {"assignee": "Person C"}})
    first = _plan(data, text)
    second = _plan(first.data, text)
    assert not second.changed and second.data == first.data


def test_fibonacci_backlog_effort_is_editable_with_a_reason():
    data = recorded(fib_backlog(epic(), task("API-001", effort=3), marked=True))
    text = _edit(render.render_csv(data), {"API-001": {"effort": "5", "change_reason": "More scope"}})
    assert by_id(_plan(data, text).data, "API-001")["effort"] == 5
    bad = _edit(render.render_csv(data), {"API-001": {"effort": "4", "change_reason": "x"}})
    _aborts(data, bad, "Fibonacci")


def test_legacy_backlog_import_records_its_model():
    data = fib_backlog(epic(), task("API-001", effort=3))
    text = _edit(render.render_csv(data), {"API-001": {"assignee": "Person A"}})
    report = _plan(data, text)
    assert report.data["estimation"] == {"model": "fibonacci"}
    assert by_id(report.data, "API-001")["effort"] == 3


# --- ignored fields -----------------------------------------------------------------

def test_protected_and_calculated_edits_are_ignored_with_warnings():
    data = _backlog()
    text = _edit(render.render_csv(data), {
        "API-001": {"title": "Renamed in a spreadsheet", "effort": "99", "estimated_hours": "20"},
        "EPIC-API": {"points_total": "100", "hours_implementation": "4"}})
    report = _plan(data, text)
    assert not report.changed
    assert by_id(report.data, "API-001")["title"] == "Task API-001"
    joined = "\n".join(report.warnings)
    assert "protected field 'title'" in joined
    assert "calculated field 'effort'" in joined and "recalculated" in joined
    assert "calculated field 'estimated_hours'" in joined
    assert "calculated field 'points_total'" in joined
    assert "'hours_implementation'" in joined  # an Epic has no estimate inputs


# --- aborts (nothing applied) ----------------------------------------------------------

def test_estimate_change_without_reason_aborts():
    data = _backlog()
    _aborts(data, _edit(render.render_csv(data), {"API-001": {"difficulty_level": "3"}}),
            "change_reason")


@pytest.mark.parametrize("col, value, needle", [
    ("status", "Closed", "status"),
    ("priority", "Urgent", "priority"),
    ("due_date", "next week", "not a date"),
    ("hours_testing", "1.1", "quarter hours"),
    ("hours_testing", "", "incomplete estimate"),
    ("difficulty_level", "7", "difficulty_level"),
    ("estimate_confidence", "certain", "estimate_confidence"),
])
def test_invalid_editable_values_abort(col, value, needle):
    data = _backlog()
    edits = {col: value, "change_reason": "testing invalid input"}
    _aborts(data, _edit(render.render_csv(data), {"API-001": edits}), needle)


def test_unknown_duplicate_and_missing_ids_abort():
    data = _backlog()
    text = render.render_csv(data)
    _aborts(data, _edit(text, {"API-001": {"id": "API-099"}}), "unknown ticket API-099")
    lines = text.splitlines()
    _aborts(data, "\n".join(lines + [lines[2]]) + "\n", "more than once")
    _aborts(data, _edit(text, {"API-001": {"id": ""}}), "no ticket ID")


def test_missing_baseline_column_aborts_with_instructions():
    data = _backlog()
    rows = list(csv.reader(io.StringIO(render.render_csv(data))))
    stripped = [r[:-1] for r in rows]
    buf = io.StringIO()
    csv.writer(buf).writerows(stripped)
    _aborts(data, buf.getvalue(), "ticketly render")


def test_tampered_or_moved_baseline_aborts():
    data = _backlog()
    text = render.render_csv(data)
    rows = {r["id"]: r for r in csv.DictReader(io.StringIO(text))}
    token = rows["API-001"]["ticketly_baseline"]
    flipped = token[:-1] + ("1" if token[-1] == "0" else "0")
    _aborts(data, _edit(text, {"API-001": {"ticketly_baseline": flipped}}), "altered")
    _aborts(data, _edit(text, {"API-002": {"ticketly_baseline": token}}), "belongs to API-001")


def test_a_bad_row_aborts_the_good_rows_too():
    data = _backlog()
    text = _edit(render.render_csv(data), {"API-001": {"assignee": "Person C"},
                                           "API-002": {"status": "Closed"}})
    _aborts(data, text, "Closed")


# --- stale exports ------------------------------------------------------------------

def test_untouched_stale_rows_are_kept_as_ticketly_has_them():
    data = _backlog()
    export = render.render_csv(data)
    by_id(data, "API-002")["assignee"] = "Person D"  # changed in Ticketly after export
    data = recorded(data, on="2026-10-05")
    text = _edit(export, {"API-001": {"assignee": "Person C"}})
    report = _plan(data, text)
    assert by_id(report.data, "API-001")["assignee"] == "Person C"
    assert by_id(report.data, "API-002")["assignee"] == "Person D"  # not reverted
    assert "API-002" in report.stale_untouched


def test_untouched_field_in_an_edited_stale_row_is_kept():
    data = _backlog()
    export = render.render_csv(data)
    by_id(data, "API-001")["assignee"] = "Person D"
    data = recorded(data, on="2026-10-05")
    report = _plan(data, _edit(export, {"API-001": {"status": "In Progress"}}))
    t = by_id(report.data, "API-001")
    assert t["status"] == "In Progress" and t["assignee"] == "Person D"


def test_conflicting_stale_edit_aborts():
    data = _backlog()
    export = render.render_csv(data)
    by_id(data, "API-001")["assignee"] = "Person D"
    data = recorded(data, on="2026-10-05")
    _aborts(data, _edit(export, {"API-001": {"assignee": "Person C"}}), "also changed in Ticketly")


def test_estimate_edit_after_a_reestimate_in_ticketly_aborts():
    data = _backlog()
    export = render.render_csv(data)
    by_id(data, "API-001")["estimate"] = estimate(5, 2, 0.5, 0.5, level=3)
    data = recorded(data, on="2026-10-05", reason="harder than thought")
    text = _edit(export, {"API-001": {"hours_testing": "3", "change_reason": "more tests"}})
    _aborts(data, text, "re-estimated")


def test_stale_edit_matching_the_current_value_is_not_a_conflict():
    data = _backlog()
    export = render.render_csv(data)
    by_id(data, "API-001")["assignee"] = "Person C"
    data = recorded(data, on="2026-10-05")
    report = _plan(data, _edit(export, {"API-001": {"assignee": "Person C"}}))
    assert not report.changed


# --- command line: dry run and atomic writes --------------------------------------------

def _files(tmp_path, data, text):
    backlog = tmp_path / "backlog.json"
    backlog.write_text(json.dumps(data, indent=2))
    sheet = tmp_path / "edited.csv"
    sheet.write_text(text)
    return backlog, sheet


def test_dry_run_writes_nothing(tmp_path, capsys):
    data = _backlog()
    backlog, sheet = _files(tmp_path, data, _edit(render.render_csv(data),
                                                  {"API-001": {"assignee": "Person C"}}))
    before = backlog.read_bytes()
    assert csv_import.main([str(sheet), "--backlog", str(backlog), "--dry-run", "--on", ON]) == 0
    assert backlog.read_bytes() == before
    assert "dry run" in capsys.readouterr().out


def test_failed_import_leaves_the_backlog_byte_for_byte(tmp_path):
    data = _backlog()
    backlog, sheet = _files(tmp_path, data, _edit(render.render_csv(data),
                                                  {"API-001": {"status": "Closed"}}))
    before = backlog.read_bytes()
    assert csv_import.main([str(sheet), "--backlog", str(backlog)]) == 1
    assert backlog.read_bytes() == before


def test_no_op_import_does_not_rewrite_the_file(tmp_path):
    data = _backlog()
    backlog, sheet = _files(tmp_path, data, render.render_csv(data))
    before = backlog.read_bytes()
    assert csv_import.main([str(sheet), "--backlog", str(backlog)]) == 0
    assert backlog.read_bytes() == before


def test_successful_import_writes_a_valid_backlog_atomically(tmp_path):
    data = _backlog()
    backlog, sheet = _files(tmp_path, data, _edit(render.render_csv(data),
                                                  {"API-001": {"assignee": "Person C"}}))
    assert cli.main(["import", str(sheet), "--backlog", str(backlog), "--on", ON]) == 0
    saved = render.load_backlog(backlog)
    assert by_id(saved, "API-001")["assignee"] == "Person C"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["backlog.json", "edited.csv"]


def test_save_backlog_refuses_an_invalid_result(tmp_path):
    data = _backlog()
    path = tmp_path / "backlog.json"
    path.write_text("original")
    by_id(data, "API-001")["effort"] = 99.0
    with pytest.raises(render.BacklogIntegrityError):
        render.save_backlog(path, data)
    assert path.read_text() == "original"


def test_import_refuses_an_invalid_backlog(tmp_path):
    data = _backlog()
    by_id(data, "API-001")["effort"] = 99.0
    backlog, sheet = _files(tmp_path, data, "id\n")
    assert csv_import.main([str(sheet), "--backlog", str(backlog)]) == 1


def test_points_in_external_tools_are_only_exported_values():
    data = _backlog()
    text = _edit(render.render_csv(data), {"API-001": {"effort": "1.0"}})
    report = _plan(data, text)
    assert by_id(report.data, "API-001")["effort"] == 8.8
    assert est.model_of(report.data) == "hours"


# --- reporting -------------------------------------------------------------------------

def test_estimate_change_summary_shows_hours_and_level():
    data = _backlog()
    text = _edit(render.render_csv(data), {"API-002": {
        "hours_testing": "1.5", "difficulty_level": "3.0", "change_reason": "permissions"}})
    report = _plan(data, text)
    # 4h at level 4 and 4.5h at level 3 are both 5.6 points; the summary must show why
    assert "API-002: estimate 4h level 4 = 5.6 points -> 4.5h level 3 = 5.6 points" in report.changes


def test_invalid_values_are_reported_together_with_row_errors():
    data = _backlog()
    text = _edit(render.render_csv(data), {"API-001": {"status": "Closed"},
                                           "API-002": {"id": "API-099"}})
    with pytest.raises(csv_import.ImportAborted) as exc:
        _plan(data, text)
    joined = "\n".join(exc.value.errors)
    assert "Closed" in joined and "unknown ticket API-099" in joined
