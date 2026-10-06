"""Schema and integrity rules for estimation models.

Legacy backlogs (no estimation block) validate exactly as before; marked
Fibonacci and hours-based backlogs get their own ticket shapes; the validator
catches points that don't match their inputs, broken breakdowns, unknown rubrics,
unrecorded changes, and makes Unestimated Tasks visible.
"""

import copy
import json
from pathlib import Path

import pytest
from jsonschema import ValidationError

from ticketly import estimate as est
from ticketly import render, validate
from estimation_builders import (by_id, codes, epic, estimate, fib_backlog, hours_backlog,
                                 recorded, task)

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "ticketly" / "data" / "examples"


def _valid_hours():
    return recorded(hours_backlog(epic(), task("API-001", estimate=estimate())))


# --- schema -------------------------------------------------------------------

def test_shipped_hours_example_validates_cleanly():
    data = json.loads((EXAMPLES / "hours-backlog.json").read_text())
    render.validate_backlog(data)
    assert not validate.errors(validate.check_integrity(data))
    assert est.model_of(data) == "hours"


@pytest.mark.parametrize("name", ["sample-release-backlog.json", "house-style-backlog.json"])
def test_legacy_examples_still_validate_as_fibonacci(name):
    data = json.loads((EXAMPLES / name).read_text())
    assert "estimation" not in data
    render.validate_backlog(data)
    assert est.model_of(data) == "fibonacci"


def test_hours_backlog_accepts_decimal_points_and_unestimated():
    data = recorded(hours_backlog(epic(), task("API-001", estimate=estimate()),
                                  task("API-002", needs_clarification=True)))
    render.validate_backlog(data)
    assert by_id(data, "API-001")["effort"] == 8.8
    assert by_id(data, "API-002")["effort"] is None


def test_legacy_backlog_rejects_decimal_points():
    with pytest.raises(ValidationError):
        render.validate_backlog(fib_backlog(epic(), task("API-001", effort=8.8)))


def test_marked_fibonacci_backlog_rejects_hours_estimates():
    data = fib_backlog(epic(), task("API-001", effort=3, estimate=estimate()), marked=True)
    with pytest.raises(ValidationError):
        render.validate_backlog(data)


def test_in_review_status_is_valid_in_every_model():
    render.validate_backlog(fib_backlog(epic(), task("API-001", effort=3, status="In Review")))
    render.validate_backlog(recorded(hours_backlog(
        epic(), task("API-001", estimate=estimate(), status="In Review"))))


@pytest.mark.parametrize("mutate", [
    lambda e: e["hours_breakdown"].update(testing=0.3),     # not a quarter hour
    lambda e: e.update(difficulty_level=5),                  # outside 1-4
    lambda e: e.update(estimate_confidence="certain"),       # not high/medium/low
    lambda e: e.update(difficulty_reason=""),                # a reason is required
    lambda e: e.pop("rubric_version"),                       # rubric must be named
])
def test_malformed_estimates_are_rejected(mutate):
    data = _valid_hours()
    mutate(by_id(data, "API-001")["estimate"])
    with pytest.raises(ValidationError):
        render.validate_backlog(data)


def test_hours_model_requires_a_frozen_rubric():
    data = _valid_hours()
    del data["estimation"]["rubrics"]
    with pytest.raises(ValidationError):
        render.validate_backlog(data)


def test_unknown_work_kind_is_rejected():
    data = _valid_hours()
    by_id(data, "API-001")["work_kind"] = "meetings"
    with pytest.raises(ValidationError):
        render.validate_backlog(data)


def test_known_work_kinds_are_accepted():
    for kind in ("cleanup", "integration", "client_prep", "investigation"):
        data = recorded(hours_backlog(epic(), task("API-001", estimate=estimate(), work_kind=kind)))
        render.validate_backlog(data)


# --- integrity ----------------------------------------------------------------

def test_effort_that_disagrees_with_inputs_is_an_error():
    data = _valid_hours()
    by_id(data, "API-001")["effort"] = 9.0
    assert "effort_mismatch" in codes(validate.errors(validate.check_integrity(data)))


def test_breakdown_must_add_up_to_estimated_hours():
    data = _valid_hours()
    by_id(data, "API-001")["estimate"]["estimated_hours"] = 9
    assert "hours_breakdown_mismatch" in codes(validate.check_integrity(data))


def test_estimate_rubric_must_be_recorded():
    data = _valid_hours()
    by_id(data, "API-001")["estimate"]["rubric_version"] = "hours-v9"
    assert "unknown_rubric" in codes(validate.errors(validate.check_integrity(data)))


def test_points_without_an_estimate_is_an_error():
    data = recorded(hours_backlog(epic(), task("API-001")))
    by_id(data, "API-001")["effort"] = 3.0
    assert "effort_without_estimate" in codes(validate.check_integrity(data))


def test_epic_cannot_carry_an_estimate_and_keeps_zero_effort():
    data = _valid_hours()
    by_id(data, "EPIC-API")["estimate"] = estimate()
    assert "epic_has_estimate" in codes(validate.check_integrity(data))
    data = _valid_hours()
    by_id(data, "EPIC-API")["effort"] = 8.8
    assert "epic_effort_nonzero" in codes(validate.check_integrity(data))


def test_unestimated_task_is_a_visible_warning():
    data = recorded(hours_backlog(epic(), task("API-001", needs_clarification=True)))
    problems = validate.check_integrity(data)
    assert "unestimated" in codes(validate.warnings(problems))
    assert not validate.errors(problems)


def test_estimate_must_be_recorded_in_history():
    data = hours_backlog(epic(), task("API-001", effort=8.8, estimate=estimate()))
    assert "estimate_not_recorded" in codes(validate.check_integrity(data))


def test_unrecorded_owner_or_status_change_is_an_error():
    data = _valid_hours()
    by_id(data, "API-001")["assignee"] = "Person A"
    assert "unrecorded_change" in codes(validate.check_integrity(data))
    data = _valid_hours()
    by_id(data, "API-001")["status"] = "Done"
    assert "unrecorded_change" in codes(validate.check_integrity(data))


def test_editing_the_model_by_hand_is_caught():
    data = recorded(fib_backlog(epic(), task("API-001", effort=3), marked=True))
    data["estimation"] = est.new_estimation_block("hours")
    t = by_id(data, "API-001")
    t["effort"] = None
    assert "history_model_mismatch" in codes(validate.check_integrity(data))


def test_legacy_ticket_definition_is_unchanged():
    schema = render.load_schema()
    legacy = schema["$defs"]["ticket"]
    assert set(legacy["properties"]) == {
        "id", "title", "type", "parent", "status", "effort", "dependencies", "description",
        "acceptance_criteria", "needs_clarification", "assignee", "due_date", "priority"}
    assert legacy["properties"]["effort"]["enum"] == [0, 1, 2, 3, 5, 8, 13]


def test_validate_cli_reports_schema_errors(tmp_path):
    bad = copy.deepcopy(_valid_hours())
    by_id(bad, "API-001")["estimate"]["difficulty_level"] = 9
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(bad))
    assert validate.main([str(p)]) == 1
