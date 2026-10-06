"""Recording estimates and changes, frozen rubrics, and switching models.

`ticketly recalc` (estimate.reconcile) calculates points and records history;
`ticketly switch-model` (estimate.switch_model) moves a Fibonacci backlog to
hours-based points while keeping legacy points, owners and completion apart.
"""

import json
from decimal import Decimal

import pytest

from ticketly import cli, render, validate
from ticketly import estimate as est
from estimation_builders import (ON, by_id, codes, epic, estimate, fib_backlog, hours_backlog,
                                 recorded, task)


def _tasks(data):
    return [t for t in data["tickets"] if t["type"] == "Task"]


# --- recalc ---------------------------------------------------------------------

def test_recalc_calculates_points_and_records_a_baseline():
    data = recorded(hours_backlog(epic(), task("API-001", estimate=estimate(), assignee="Person A")))
    t = by_id(data, "API-001")
    assert t["effort"] == 8.8
    [base] = t["history"]
    assert base["field"] == "baseline" and base["on"] == ON and base["source"] == "recalc"
    assert base["to"]["estimate"]["effort"] == 8.8
    assert base["to"]["assignee"] == "Person A" and base["to"]["status"] == "To Do"


def test_recalc_is_idempotent():
    data = recorded(hours_backlog(epic(), task("API-001", estimate=estimate())))
    again = est.reconcile(data, on="2026-10-02")
    assert again.changes == [] and again.errors == []
    assert again.data == data


def test_changed_estimate_requires_a_reason():
    data = recorded(hours_backlog(epic(), task("API-001", estimate=estimate())))
    by_id(data, "API-001")["estimate"] = estimate(level=3)
    result = est.reconcile(data, on="2026-10-02")
    assert result.errors and "--reason" in result.errors[0]


def test_reestimate_keeps_the_earlier_snapshot_with_reason_and_attribution():
    data = recorded(hours_backlog(epic(), task("API-001", estimate=estimate(), assignee="Person A",
                                               status="In Progress")))
    by_id(data, "API-001")["estimate"] = estimate(impl=7, level=3)
    data = recorded(data, on="2026-10-03", reason="Client added CSV export")
    t = by_id(data, "API-001")
    base, change = t["history"]
    assert base["field"] == "baseline"  # the original snapshot is still there
    assert change["field"] == "estimate"
    assert change["from"]["effort"] == 8.8 and change["to"]["effort"] == 12.5
    assert change["from"]["estimate"]["difficulty_level"] == 2
    assert change["reason"] == "Client added CSV export"
    assert change["assignee"] == "Person A" and change["status"] == "In Progress"
    assert t["effort"] == 12.5


def test_first_estimate_of_an_unestimated_task_needs_no_reason():
    data = recorded(hours_backlog(epic(), task("API-001", needs_clarification=True)))
    by_id(data, "API-001")["estimate"] = estimate()
    data = recorded(data, on="2026-10-03")
    change = by_id(data, "API-001")["history"][-1]
    assert change["field"] == "estimate" and change["reason"] == "first estimate"


def test_owner_and_status_changes_are_recorded():
    data = recorded(hours_backlog(epic(), task("API-001", estimate=estimate())))
    t = by_id(data, "API-001")
    t["assignee"] = "Person B"
    t["status"] = "In Review"
    data = recorded(data, on="2026-10-04")
    fields = [(e["field"], e["from"], e["to"]) for e in by_id(data, "API-001")["history"][1:]]
    assert ("assignee", None, "Person B") in fields
    assert ("status", "To Do", "In Review") in fields


def test_frozen_rubric_means_calibration_never_rescores_existing_work():
    data = recorded(hours_backlog(epic(), task("API-001", estimate=estimate(level=2))))
    data["estimation"]["rubrics"]["hours-v2"] = {"1": "1.00", "2": "1.20", "3": "1.30", "4": "1.50"}
    data["estimation"]["rubric_version"] = "hours-v2"
    result = est.reconcile(data, on="2026-10-05")
    assert result.changes == [] and not result.errors
    assert by_id(result.data, "API-001")["effort"] == 8.8  # still scored under hours-v1
    assert not validate.errors(validate.check_integrity(result.data))


def test_recalc_on_a_legacy_backlog_records_its_fibonacci_model():
    data = fib_backlog(epic(), task("API-001", effort=5))
    result = est.reconcile(data, on=ON)
    assert result.data["estimation"] == {"model": "fibonacci"}
    assert by_id(result.data, "API-001")["effort"] == 5
    render.validate_backlog(result.data)


def test_recalc_cli_dry_run_writes_nothing(tmp_path, capsys):
    p = tmp_path / "backlog.json"
    p.write_text(json.dumps(hours_backlog(epic(), task("API-001", estimate=estimate()))))
    before = p.read_text()
    assert cli.main(["recalc", str(p), "--dry-run", "--on", ON]) == 0
    assert p.read_text() == before
    assert cli.main(["recalc", str(p), "--on", ON]) == 0
    assert json.loads(p.read_text())["tickets"][1]["effort"] == 8.8


def test_recalc_cli_refuses_without_reason(tmp_path):
    data = recorded(hours_backlog(epic(), task("API-001", estimate=estimate())))
    by_id(data, "API-001")["estimate"] = estimate(level=4)
    p = tmp_path / "backlog.json"
    p.write_text(json.dumps(data))
    before = p.read_text()
    assert cli.main(["recalc", str(p)]) == 1
    assert p.read_text() == before


# --- switch-model -----------------------------------------------------------------

def _legacy():
    return fib_backlog(
        epic(),
        task("API-001", effort=5, status="Done", assignee="Person A"),
        task("API-002", effort=8, status="In Progress", assignee="Person B"),
        task("API-003", effort=3),
    )


def test_switch_requires_a_reason():
    assert est.switch_model(_legacy(), to="hours", reason=" ", on=ON).errors


def test_switch_to_the_same_model_is_refused():
    data = est.switch_model(_legacy(), to="hours", reason="adopt hours", on=ON).data
    assert est.switch_model(data, to="hours", reason="again", on=ON).errors


def test_switch_back_to_fibonacci_is_not_supported():
    data = est.switch_model(_legacy(), to="hours", reason="adopt hours", on=ON).data
    errors = est.switch_model(data, to="fibonacci", reason="undo", on=ON).errors
    assert errors and "not supported" in errors[0]


def test_switch_keeps_legacy_points_owner_and_completion():
    result = est.switch_model(_legacy(), to="hours", reason="Team adopts hours", on=ON)
    assert not result.errors
    data = result.data
    render.validate_backlog(data)
    assert not validate.errors(validate.check_integrity(data))
    assert data["estimation"]["model"] == "hours"
    assert data["estimation"]["history"] == [
        {"on": ON, "from": "fibonacci", "to": "hours", "reason": "Team adopts hours"}]
    done = by_id(data, "API-001")
    assert done["effort"] is None and done["estimate"] is None
    assert done["assignee"] == "Person A" and done["status"] == "Done"
    [legacy] = done["legacy_estimates"]
    assert legacy == {"model": "fibonacci", "effort": 5, "assignee": "Person A", "status": "Done",
                      "completed": True, "on": ON, "reason": "Team adopts hours"}
    model_event = done["history"][-1]
    assert model_event["field"] == "model" and model_event["from"]["effort"] == 5
    assert model_event["reason"] == "Team adopts hours"
    assert by_id(data, "API-002")["legacy_estimates"][0]["completed"] is False


def test_legacy_and_new_totals_stay_separate():
    data = est.switch_model(_legacy(), to="hours", reason="adopt hours", on=ON).data
    by_id(data, "API-002")["estimate"] = estimate()  # re-estimated in hours: 8.8
    data = recorded(data, on="2026-10-02", reason="Re-estimated in hours-based points")
    tot = est.summarize(_tasks(data), "hours")
    assert tot.points == Decimal("8.8")              # only the re-estimated task
    assert tot.legacy_points == {"fibonacci": Decimal("16")}  # 5 + 8 + 3, never added in
    assert tot.legacy_completed == 1
    # the completed legacy task is out of the new totals and doesn't make them partial
    assert tot.tickets == 2 and tot.unestimated == 1


def test_completed_legacy_tasks_do_not_mark_totals_partial():
    data = est.switch_model(_legacy(), to="hours", reason="adopt hours", on=ON).data
    for tid in ("API-002", "API-003"):
        by_id(data, tid)["estimate"] = estimate()
    data = recorded(data, on="2026-10-02", reason="Re-estimated")
    tot = est.summarize(_tasks(data), "hours")
    assert not tot.partial
    warnings = validate.warnings(validate.check_integrity(data))
    assert "unestimated" not in codes(warnings)


def test_switch_model_cli(tmp_path):
    p = tmp_path / "backlog.json"
    p.write_text(json.dumps(_legacy()))
    with pytest.raises(SystemExit):
        cli.main(["switch-model", str(p), "--to", "hours"])  # --reason is required
    before = p.read_text()
    assert cli.main(["switch-model", str(p), "--to", "hours", "--reason", "adopt", "--dry-run"]) == 0
    assert p.read_text() == before
    assert cli.main(["switch-model", str(p), "--to", "hours", "--reason", "adopt", "--on", ON]) == 0
    assert json.loads(p.read_text())["estimation"]["model"] == "hours"


def test_rejected_recalc_does_not_report_changes_as_recorded(tmp_path, capsys):
    data = recorded(hours_backlog(epic(), task("API-001", estimate=estimate(), assignee="Person A")))
    child = task("API-002", estimate=estimate(), assignee="Person B")
    child["split_from"] = {"ticket": "API-001", "scope": "replaced", "reason": "handover"}
    data["tickets"].append(child)  # the original was never reduced: invalid split
    p = tmp_path / "backlog.json"
    p.write_text(json.dumps(data))
    before = p.read_text()
    assert cli.main(["recalc", str(p), "--reason", "handover"]) == 1
    out = capsys.readouterr()
    assert "recorded" not in out.out
    assert "split_not_reconciled" in out.err and "nothing was written" in out.err
    assert p.read_text() == before


def test_unestimated_warning_wording_respects_the_clarification_flag():
    flagged = recorded(hours_backlog(epic(), task("API-001", needs_clarification=True)))
    plain = recorded(hours_backlog(epic(), task("API-001")))
    [w1] = validate.warnings(validate.check_integrity(flagged))
    [w2] = validate.warnings(validate.check_integrity(plain))
    assert "flagged for clarification" in w1.message
    assert "flag needs_clarification" in w2.message
