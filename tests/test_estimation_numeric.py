"""Numeric input handling: non-finite values are refused everywhere with an
actionable error and no write; whole-number difficulty levels like 2.0 are
accepted, fractional or out-of-range levels are not.
"""

import csv
import io
import json
from decimal import Decimal

import pytest
from jsonschema import ValidationError

from ticketly import cli, csv_import, render, validate
from ticketly import estimate as est
from estimation_builders import by_id, epic, estimate, fib_backlog, hours_backlog, recorded, task

ON = "2026-10-06"


def _backlog():
    return recorded(hours_backlog(
        epic(),
        task("API-001", estimate=estimate(5, 2, 0.5, 0.5, level=2), assignee="Person A"),
        task("API-002", estimate=estimate(2.5, 1, 0.25, 0.25, level=4)),
    ))


def _edit(text, edits):
    rows = list(csv.reader(io.StringIO(text)))
    header = rows[0]
    for row in rows[1:]:
        for col, value in edits.get(row[0], {}).items():
            row[header.index(col)] = value
    buf = io.StringIO()
    csv.writer(buf, lineterminator="\n").writerows(rows)
    return buf.getvalue()


# --- the shared calculation ------------------------------------------------------------

@pytest.mark.parametrize("value", ["NaN", "nan", "Infinity", "-Infinity", "inf",
                                   float("nan"), float("inf"), float("-inf"),
                                   Decimal("NaN"), Decimal("sNaN"), Decimal("Infinity"),
                                   Decimal("-Infinity")])
def test_non_finite_numbers_are_refused(value):
    with pytest.raises(est.EstimationError, match="finite"):
        est.dec(value)
    with pytest.raises(est.EstimationError):
        est.calculate_points(value, 2, est.RUBRIC_V1)


@pytest.mark.parametrize("level", [2, 2.0, "2", "2.0", "2.00", Decimal("2"), Decimal("2.0")])
def test_whole_number_levels_are_accepted(level):
    assert est.level_of(level) == 2
    assert str(est.calculate_points(8, level, est.RUBRIC_V1)) == "8.8"


@pytest.mark.parametrize("level", [2.5, "2.5", 0, 5, -1, "two", "NaN", True, None,
                                   Decimal("2.5"), Decimal("NaN"), Decimal("Infinity")])
def test_fractional_or_out_of_range_levels_are_refused(level):
    with pytest.raises(est.EstimationError, match="whole number from 1 to 4"):
        est.level_of(level)


def test_json_level_written_as_2_point_0_validates_and_renders():
    data = _backlog()
    by_id(data, "API-001")["estimate"]["difficulty_level"] = 2.0
    render.validate_backlog(data)
    assert not validate.errors(validate.check_integrity(data))
    assert est.reconcile(data, on=ON).changes == []  # 2.0 is the same level, nothing to record
    assert "| 8 | 2 | 8.8 |" in render.render_markdown(data)
    row = next(r for r in csv.DictReader(io.StringIO(render.render_csv(data))) if r["id"] == "API-001")
    assert row["difficulty_level"] == "2"


# --- backlog files -----------------------------------------------------------------

def test_in_memory_nan_fails_schema_validation_with_its_location():
    data = _backlog()
    by_id(data, "API-001")["estimate"]["hours_breakdown"]["testing"] = float("nan")
    with pytest.raises(ValidationError, match="hours_breakdown/testing"):
        render.validate_backlog(data)


@pytest.mark.parametrize("token", ["NaN", "Infinity", "-Infinity"])
def test_backlog_files_with_non_finite_numbers_are_refused_without_writing(tmp_path, token):
    text = json.dumps(_backlog(), indent=2).replace('"testing": 2', f'"testing": {token}', 1)
    assert token in text
    path = tmp_path / "backlog.json"
    path.write_text(text)
    with pytest.raises(ValueError, match="finite"):
        render.load_backlog(path)
    assert validate.main([str(path)]) == 1
    assert cli.main(["recalc", str(path), "--reason", "x"]) == 1
    sheet = tmp_path / "edited.csv"
    sheet.write_text("id\n")
    assert csv_import.main([str(sheet), "--backlog", str(path)]) == 1
    assert path.read_text() == text


def test_recalc_refuses_an_in_file_level_that_is_not_whole(tmp_path):
    data = hours_backlog(epic(), task("API-001", estimate=estimate()))
    data["tickets"][1]["estimate"]["difficulty_level"] = 2.5
    path = tmp_path / "backlog.json"
    path.write_text(json.dumps(data))
    before = path.read_text()
    assert cli.main(["recalc", str(path)]) == 1
    assert path.read_text() == before


# --- csv import ----------------------------------------------------------------------

@pytest.mark.parametrize("value", ["NaN", "Infinity", "inf", "-Infinity"])
def test_non_finite_csv_hours_abort(value):
    data = _backlog()
    text = _edit(render.render_csv(data), {"API-001": {"hours_testing": value,
                                                       "change_reason": "x"}})
    with pytest.raises(csv_import.ImportAborted) as exc:
        csv_import.plan_import(data, text, on=ON)
    assert any("finite number of hours" in e for e in exc.value.errors), exc.value.errors


@pytest.mark.parametrize("value", ["2.5", "0", "5", "NaN", "two"])
def test_invalid_csv_difficulty_levels_abort(value):
    data = _backlog()
    text = _edit(render.render_csv(data), {"API-001": {"difficulty_level": value,
                                                       "change_reason": "x"}})
    with pytest.raises(csv_import.ImportAborted) as exc:
        csv_import.plan_import(data, text, on=ON)
    assert any("whole number from 1 to 4" in e for e in exc.value.errors), exc.value.errors


def test_csv_level_written_as_2_point_0_is_not_an_edit():
    data = _backlog()
    text = _edit(render.render_csv(data), {"API-001": {"difficulty_level": "2.0"}})
    assert not csv_import.plan_import(data, text, on=ON).changed


def test_csv_level_written_as_3_point_0_applies_as_level_3():
    data = _backlog()
    text = _edit(render.render_csv(data), {"API-001": {"difficulty_level": "3.0",
                                                       "change_reason": "Permissions involved"}})
    t = by_id(csv_import.plan_import(data, text, on=ON).data, "API-001")
    assert t["estimate"]["difficulty_level"] == 3 and t["effort"] == 10.0


def test_fibonacci_effort_written_as_a_whole_decimal_is_accepted():
    data = recorded(fib_backlog(epic(), task("API-001", effort=3), marked=True))
    text = _edit(render.render_csv(data), {"API-001": {"effort": "5.0", "change_reason": "more"}})
    assert by_id(csv_import.plan_import(data, text, on=ON).data, "API-001")["effort"] == 5
    bad = _edit(render.render_csv(data), {"API-001": {"effort": "NaN", "change_reason": "x"}})
    with pytest.raises(csv_import.ImportAborted):
        csv_import.plan_import(data, bad, on=ON)


def test_mixed_valid_and_invalid_rows_abort_without_writing(tmp_path):
    data = _backlog()
    text = _edit(render.render_csv(data), {
        "API-001": {"assignee": "Person C", "hours_testing": "3", "change_reason": "valid"},
        "API-002": {"hours_testing": "Infinity", "change_reason": "invalid"}})
    backlog = tmp_path / "backlog.json"
    backlog.write_text(json.dumps(data, indent=2))
    sheet = tmp_path / "edited.csv"
    sheet.write_text(text)
    before = backlog.read_bytes()
    assert csv_import.main([str(sheet), "--backlog", str(backlog)]) == 1
    assert backlog.read_bytes() == before
    with pytest.raises(csv_import.ImportAborted) as exc:
        csv_import.plan_import(data, text, on=ON)
    assert all("API-002" in e for e in exc.value.errors)
