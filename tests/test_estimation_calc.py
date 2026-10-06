"""The shared hours-based points calculation.

points = estimated_hours x difficulty multiplier, Decimal arithmetic, rounded
half-up to one decimal. Pins the proposal's worked examples, the rubric, the
rounding rule, quarter-hour inputs, and that the rubric passed in is the one used.
"""

from decimal import Decimal

import pytest

from ticketly import estimate as est
from estimation_builders import epic, hours_backlog, recorded, task, estimate


@pytest.mark.parametrize("hours, level, points", [
    (12, 1, "12.0"),   # build three pages using an existing template
    (8, 2, "8.8"),     # conventional API integration
    (8, 3, "10.0"),    # complex permission inheritance
    (4, 4, "5.6"),     # concurrency consistency defect
    (1, 3, "1.3"),     # 1.25 raw -> 1.3
])
def test_proposal_worked_examples(hours, level, points):
    assert str(est.calculate_points(hours, level, est.RUBRIC_V1)) == points


def test_rubric_v1_multipliers():
    assert est.RUBRIC_V1 == {"1": "1.00", "2": "1.10", "3": "1.25", "4": "1.40"}
    assert est.LEVEL_NAMES == {1: "Basic", 2: "Standard", 3: "Complex", 4: "Advanced"}


@pytest.mark.parametrize("hours, level, points", [
    (0.75, 4, "1.1"),   # 1.05 -> 1.1 (banker's rounding would give 1.0)
    (1.75, 4, "2.5"),   # 2.45 -> 2.5 (banker's rounding would give 2.4)
    (0.75, 2, "0.8"),   # 0.825 -> 0.8
    (0.25, 3, "0.3"),   # 0.3125 -> 0.3
])
def test_half_up_rounding_to_one_decimal(hours, level, points):
    assert str(est.calculate_points(hours, level, est.RUBRIC_V1)) == points


def test_float_inputs_are_read_exactly():
    # 8.8 must not drift through binary floating point
    assert est.dec(8.8) == Decimal("8.8")
    assert est.calculate_points(2.25, 2, est.RUBRIC_V1) == Decimal("2.5")  # 2.475


@pytest.mark.parametrize("hours", [0, -1, 1.1, 0.2, "abc"])
def test_rejects_non_quarter_or_non_positive_hours(hours):
    with pytest.raises(est.EstimationError):
        est.calculate_points(hours, 2, est.RUBRIC_V1)


@pytest.mark.parametrize("level", [0, 5, "x"])
def test_rejects_unknown_levels(level):
    with pytest.raises(est.EstimationError):
        est.calculate_points(4, level, est.RUBRIC_V1)


def test_uses_the_rubric_it_is_given():
    recalibrated = {"1": "1.00", "2": "1.20", "3": "1.25", "4": "1.40"}
    assert est.calculate_points(8, 2, recalibrated) == Decimal("9.6")
    assert est.calculate_points(8, 2, est.RUBRIC_V1) == Decimal("8.8")


def test_quarter_hour_helper():
    assert est.is_quarter_hour(0.25) and est.is_quarter_hour(8) and est.is_quarter_hour("2.75")
    assert not est.is_quarter_hour(0.1) and not est.is_quarter_hour(-0.25)


def test_hours_formatting():
    assert est.fmt_hours(8) == "8"
    assert est.fmt_hours(8.5) == "8.5"
    assert est.fmt_hours(0.25) == "0.25"
    assert est.fmt_hours(80) == "80"


def test_points_formatting():
    assert est.fmt_points(12, "hours") == "12.0"
    assert est.fmt_points(None, "hours") == "Unestimated"
    assert est.fmt_points(5, "fibonacci") == "5"


def test_totals_sum_exactly_without_drift():
    tasks = [task(f"API-00{i}", estimate=estimate(0.25, 0, 0, 0, level=2)) for i in range(1, 4)]
    data = recorded(hours_backlog(epic(), *tasks))
    tot = est.summarize([t for t in data["tickets"] if t["type"] == "Task"], "hours")
    assert tot.points == Decimal("0.9")  # 3 x 0.3, no 0.30000000000000004
    assert tot.hours == Decimal("0.75")


def test_epic_total_is_a_plain_sum_with_no_extra_multiplier():
    data = recorded(hours_backlog(
        epic(),
        task("API-001", estimate=estimate(5, 2, 0.5, 0.5, level=2)),   # 8.8
        task("API-002", estimate=estimate(5, 2, 0.5, 0.5, level=3)),   # 10.0
    ))
    tot = est.summarize([t for t in data["tickets"] if t["type"] == "Task"], "hours")
    assert tot.points == Decimal("18.8")
    assert tot.hours == Decimal("16")
