"""Completed legacy work after a model switch.

Completed legacy scope keeps its legacy points, credited to the owner recorded at
the switch; it stays out of the new model's totals and partial flags, and neither
recalc nor either CSV layout can re-estimate it into the new model.
"""

import csv
import io
from decimal import Decimal

import pytest

from ticketly import csv_import, render, validate
from ticketly import estimate as est
from estimation_builders import (ON, by_id, codes, epic, estimate, fib_backlog, recorded, task)


def _migrated():
    data = fib_backlog(
        epic(),
        task("API-001", effort=5, status="Done", assignee="Person A"),
        task("API-002", effort=8, assignee="Person B"),
    )
    result = est.switch_model(data, to="hours", reason="Team adopts hours", on=ON)
    assert not result.errors
    return result.data


def _tasks(data):
    return [t for t in data["tickets"] if t["type"] == "Task"]


def _reassigned():
    data = _migrated()
    by_id(data, "API-001")["assignee"] = "Person Z"
    return recorded(data, on="2026-10-02")


def test_reassignment_after_migration_keeps_legacy_attribution():
    data = _reassigned()
    assert by_id(data, "API-001")["legacy_estimates"][-1]["assignee"] == "Person A"
    assert est.legacy_completed_by_person(_tasks(data)) == [
        ("Person A", 1, {"fibonacci": Decimal("5")})]
    md = render.render_markdown(data)
    assert "| Person A | 1 | 5 Fibonacci points |" in md
    assert "| Person Z |" not in md.split("**Completed under the previous model**")[1]


def test_reassigned_completed_legacy_work_stays_out_of_new_totals():
    data = _reassigned()
    tot = est.summarize(_tasks(data), "hours")
    assert tot.tickets == 1 and tot.legacy_completed == 1  # only API-002 is in the new totals
    rows = {p: a for p, a, _ in est.person_totals(
        [t for t in _tasks(data) if not est.is_legacy_completed(t)], "hours")}
    assert "Person Z" not in rows


def test_completed_legacy_work_never_marks_new_totals_partial():
    data = _migrated()
    by_id(data, "API-002")["estimate"] = estimate()
    data = recorded(data, on="2026-10-02", reason="Re-estimated in hours")
    tot = est.summarize(_tasks(data), "hours")
    assert not tot.partial and tot.points == Decimal("8.8")
    assert "unestimated" not in codes(validate.check_integrity(data))


def test_recalc_refuses_to_reestimate_completed_legacy_work():
    data = _migrated()
    by_id(data, "API-001")["estimate"] = estimate()
    result = est.reconcile(data, on="2026-10-02", reason="count it again")
    assert result.errors and "new task" in result.errors[0]


def test_validator_rejects_completed_legacy_work_with_new_points():
    data = _migrated()
    t = by_id(data, "API-001")
    t["estimate"] = estimate()
    t["effort"] = 8.8
    assert "completed_legacy_reestimated" in codes(validate.errors(validate.check_integrity(data)))


_INPUTS = {"hours_implementation": "5", "hours_testing": "2", "hours_self_review": "0.5",
           "hours_handoff": "0.5", "difficulty_level": "2", "difficulty_reason": "Routine",
           "estimate_confidence": "high", "change_reason": "count it again"}
_NOTION = {"hours_implementation": "Implementation Hours", "hours_testing": "Testing Hours",
           "hours_self_review": "Self-Review Hours", "hours_handoff": "Handoff Hours",
           "difficulty_level": "Difficulty Level", "difficulty_reason": "Difficulty Reason",
           "estimate_confidence": "Confidence", "change_reason": "Change Reason"}


@pytest.mark.parametrize("notion", [False, True])
def test_csv_import_refuses_to_reestimate_completed_legacy_work(notion):
    data = _migrated()
    text = render.render_notion_csv(data) if notion else render.render_csv(data)
    rows = list(csv.reader(io.StringIO(text)))
    header = rows[0]
    id_col = header.index("ID" if notion else "id")
    for row in rows[1:]:
        if row[id_col] == "API-001":
            for key, value in _INPUTS.items():
                row[header.index(_NOTION[key] if notion else key)] = value
    buf = io.StringIO()
    csv.writer(buf).writerows(rows)
    with pytest.raises(csv_import.ImportAborted) as exc:
        csv_import.plan_import(data, buf.getvalue(), on="2026-10-02")
    assert any("legacy" in e and "new task" in e for e in exc.value.errors)


def test_status_and_owner_of_completed_legacy_work_can_still_be_edited_by_csv():
    data = _migrated()
    rows = list(csv.DictReader(io.StringIO(render.render_csv(data))))
    for r in rows:
        if r["id"] == "API-001":
            r["assignee"] = "Person Z"
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=render.CSV_COLUMNS)
    writer.writeheader()
    writer.writerows(rows)
    report = csv_import.plan_import(data, buf.getvalue(), on="2026-10-02")
    t = by_id(report.data, "API-001")
    assert t["assignee"] == "Person Z" and t["effort"] is None
    assert t["legacy_estimates"][-1]["assignee"] == "Person A"
