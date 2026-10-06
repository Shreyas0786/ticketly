"""Partial completion and takeovers as separately owned tasks.

A 'replaced' split must be matched by a recorded reduction of the original's
estimate, and the kept plus handed-over work may not exceed the original
estimate; 'additional' scope is allowed but flagged when the same owner adds it
without an approver. Links must be real and must not loop.
"""

from decimal import Decimal

from ticketly import estimate as est
from ticketly import validate
from estimation_builders import (by_id, codes, epic, estimate, fib_backlog, hours_backlog,
                                 recorded, task)

REASON = "Person A moved on; Person B finishes the editor"


def _original():
    # API-001: 8 standard hours at level 3 = 10.0 points, owned by Person A
    return recorded(hours_backlog(
        epic(), task("API-001", estimate=estimate(5, 2, 0.5, 0.5, level=3), assignee="Person A")))


def _split(data, kept, moved, scope="replaced", owner="Person B", **split_kw):
    by_id(data, "API-001")["estimate"] = kept
    child = task("API-002", estimate=moved, assignee=owner)
    child["split_from"] = {"ticket": "API-001", "scope": scope, "reason": REASON, **split_kw}
    data["tickets"].append(child)
    return est.reconcile(data, on="2026-10-05", reason=REASON)


def _check(data):
    return validate.check_integrity(data)


def test_valid_takeover_keeps_points_equal_to_the_original():
    result = _split(_original(), estimate(2.5, 1, 0.25, 0.25, level=3),
                    estimate(2.5, 1, 0.25, 0.25, level=3))
    assert not result.errors
    data = result.data
    assert not validate.errors(_check(data))
    event = by_id(data, "API-001")["history"][-1]
    assert event["field"] == "estimate" and event["split_to"] == ["API-002"]
    assert event["from"]["effort"] == 10.0 and event["to"]["effort"] == 5.0
    tot = est.summarize([t for t in data["tickets"] if t["type"] == "Task"], "hours")
    assert tot.points == Decimal("10.0")  # 5.0 kept + 5.0 handed over, never 15
    # each owner keeps their own work
    rows = {p: a for p, a, _ in est.person_totals(
        [t for t in data["tickets"] if t["type"] == "Task"], "hours")}
    assert rows["Person A"].points == Decimal("5.0") and rows["Person B"].points == Decimal("5.0")


def test_replaced_split_without_reducing_the_original_is_rejected():
    data = _original()
    child = task("API-002", estimate=estimate(2.5, 1, 0.25, 0.25, level=3), assignee="Person B")
    child["split_from"] = {"ticket": "API-001", "scope": "replaced", "reason": REASON}
    data["tickets"].append(child)
    data = recorded(data, on="2026-10-05")  # only the child's baseline is recorded
    assert "split_not_reconciled" in codes(validate.errors(_check(data)))


def test_changing_the_original_is_not_enough_if_scope_is_counted_twice():
    # the original only drops to 6h (7.5 pts) yet hands over 4h (5.0 pts): 12.5 > 10.0
    result = _split(_original(), estimate(4, 1, 0.5, 0.5, level=3),
                    estimate(2.5, 1, 0.25, 0.25, level=3))
    assert "split_duplicates_scope" in codes(validate.errors(_check(result.data)))


def test_conservation_uses_unrounded_points():
    # 0.5h at level 4 = 0.7 points; two halves round to 0.4 + 0.4 = 0.8 but are 0.35 + 0.35 raw
    data = recorded(hours_backlog(
        epic(), task("API-001", estimate=estimate(0.25, 0.25, 0, 0, level=4), assignee="Person A")))
    result = _split(data, estimate(0.25, 0, 0, 0, level=4), estimate(0.25, 0, 0, 0, level=4))
    assert not validate.errors(_check(result.data))


def test_additional_scope_by_the_same_owner_needs_an_approver():
    result = _split(_original(), estimate(5, 2, 0.5, 0.5, level=3), estimate(1, 0.5, 0.25, 0.25),
                    scope="additional", owner="Person A")
    problems = _check(result.data)
    assert not validate.errors(problems)
    assert "same_owner_additional_scope" in codes(validate.warnings(problems))


def test_approved_additional_scope_by_the_same_owner_is_legitimate():
    result = _split(_original(), estimate(5, 2, 0.5, 0.5, level=3), estimate(1, 0.5, 0.25, 0.25),
                    scope="additional", owner="Person A", approved_by="Person C")
    assert "same_owner_additional_scope" not in codes(_check(result.data))


def test_additional_scope_by_another_owner_is_not_flagged():
    result = _split(_original(), estimate(5, 2, 0.5, 0.5, level=3), estimate(1, 0.5, 0.25, 0.25),
                    scope="additional", owner="Person B")
    problems = _check(result.data)
    assert not validate.errors(problems)
    assert "same_owner_additional_scope" not in codes(problems)


def _with_link(target, tid="API-002", scope="additional"):
    data = _original()
    child = task(tid, estimate=estimate(), assignee="Person B")
    child["split_from"] = {"ticket": target, "scope": scope, "reason": REASON}
    data["tickets"].append(child)
    return recorded(data, on="2026-10-05")


def test_dangling_split_is_rejected():
    assert "dangling_split" in codes(_check(_with_link("API-099")))


def test_self_split_is_rejected():
    assert "self_split" in codes(_check(_with_link("API-002")))


def test_split_from_an_epic_is_rejected():
    assert "split_from_epic" in codes(_check(_with_link("EPIC-API")))


def test_circular_split_is_rejected():
    data = _with_link("API-001")
    by_id(data, "API-001")["split_from"] = {"ticket": "API-002", "scope": "additional",
                                           "reason": REASON}
    assert "circular_split" in codes(validate.errors(_check(data)))


def test_tampered_split_link_is_rejected():
    result = _split(_original(), estimate(2.5, 1, 0.25, 0.25, level=3),
                    estimate(2.5, 1, 0.25, 0.25, level=3))
    data = result.data
    by_id(data, "API-002")["split_from"]["scope"] = "additional"
    assert "split_link_mismatch" in codes(validate.errors(_check(data)))


def test_fibonacci_double_counting_is_a_warning_not_an_error():
    data = recorded(fib_backlog(epic(), task("API-001", effort=5, assignee="Person A"), marked=True))
    by_id(data, "API-001")["effort"] = 3
    child = task("API-002", effort=3, assignee="Person B")
    child["split_from"] = {"ticket": "API-001", "scope": "replaced", "reason": REASON}
    data["tickets"].append(child)
    data = recorded(data, on="2026-10-05", reason=REASON)
    problems = _check(data)
    assert "split_duplicates_scope" in codes(validate.warnings(problems))
    assert not validate.errors(problems)


# --- allocation stays enforced after later changes ---------------------------------------

def _valid_split():
    """API-001 (10.0 pts) split: API-001 keeps 4h (5.0), API-002 takes 4h (5.0)."""
    result = _split(_original(), estimate(2.5, 1, 0.25, 0.25, level=3),
                    estimate(2.5, 1, 0.25, 0.25, level=3))
    assert not result.errors
    return result.data


def _reestimate(data, tid, new_estimate, on="2026-10-07", reason="re-estimated", approved_by=None):
    by_id(data, tid)["estimate"] = new_estimate
    return recorded(data, on=on, reason=reason, approved_by=approved_by)


def test_later_increase_of_the_original_cannot_recount_handed_over_scope():
    data = _reestimate(_valid_split(), "API-001", estimate(5, 2, 0.5, 0.5, level=3))
    assert "split_duplicates_scope" in codes(validate.errors(_check(data)))


def test_later_increase_of_the_transferred_task_cannot_recount_kept_scope():
    data = _reestimate(_valid_split(), "API-002", estimate(5, 2, 0.5, 0.5, level=3))
    assert "split_duplicates_scope" in codes(validate.errors(_check(data)))


def test_downward_and_within_budget_reestimates_stay_legitimate():
    data = _reestimate(_valid_split(), "API-001", estimate(1.5, 0.5, 0, 0, level=3))  # 2h
    assert not validate.errors(_check(data))
    data = _reestimate(data, "API-002", estimate(4, 1.5, 0.25, 0.25, level=3),  # 6h: total 8h
                       on="2026-10-08")
    assert not validate.errors(_check(data))


def test_approved_growth_allows_the_family_to_exceed_the_original():
    data = _reestimate(_valid_split(), "API-002", estimate(5, 2, 0.5, 0.5, level=3),
                       approved_by="Person C")
    assert not validate.errors(_check(data))
    assert by_id(data, "API-002")["history"][-1]["approved_by"] == "Person C"


def test_approved_growth_is_bounded_by_what_was_approved():
    data = _reestimate(_valid_split(), "API-002", estimate(5, 2, 0.5, 0.5, level=3),
                       approved_by="Person C")  # +5.0 approved
    data = _reestimate(data, "API-001", estimate(5, 2, 0.5, 0.5, level=3), on="2026-10-08")
    assert "split_duplicates_scope" in codes(validate.errors(_check(data)))


def test_repeated_splits_from_the_same_task_share_one_budget():
    data = _valid_split()
    by_id(data, "API-001")["estimate"] = estimate(1, 0.5, 0.25, 0.25, level=3)   # keeps 2h
    third = task("API-003", estimate=estimate(1, 0.5, 0.25, 0.25, level=3), assignee="Person C")
    third["split_from"] = {"ticket": "API-001", "scope": "replaced", "reason": REASON}
    data["tickets"].append(third)
    data = recorded(data, on="2026-10-07", reason=REASON)
    assert not validate.errors(_check(data))
    # handing a third task more than API-001 gave up counts the scope twice
    data = _reestimate(data, "API-003", estimate(4, 1, 0.5, 0.5, level=3), on="2026-10-08")
    assert "split_duplicates_scope" in codes(validate.errors(_check(data)))


def _nested():
    data = _valid_split()
    by_id(data, "API-002")["estimate"] = estimate(1, 0.5, 0.25, 0.25, level=3)   # keeps 2h
    grandchild = task("API-003", estimate=estimate(1, 0.5, 0.25, 0.25, level=3),
                      assignee="Person C")
    grandchild["split_from"] = {"ticket": "API-002", "scope": "replaced", "reason": REASON}
    data["tickets"].append(grandchild)
    return recorded(data, on="2026-10-07", reason=REASON)


def test_nested_split_is_checked_against_the_root_estimate():
    data = _nested()
    assert not validate.errors(_check(data))
    assert by_id(data, "API-002")["history"][-1]["split_to"] == ["API-003"]
    tot = est.summarize([t for t in data["tickets"] if t["type"] == "Task"], "hours")
    assert tot.points == Decimal("10.0")


def test_later_increase_inside_a_nested_family_is_caught():
    data = _reestimate(_nested(), "API-003", estimate(5, 2, 0.5, 0.5, level=3), on="2026-10-08")
    problems = validate.errors(_check(data))
    assert "split_duplicates_scope" in codes(problems)
    assert any(p.ticket_id == "API-001" for p in problems)  # reported on the family root


def test_dropped_child_no_longer_counts():
    data = _valid_split()
    data["tickets"] = [t for t in data["tickets"] if t["id"] != "API-002"]
    assert not validate.errors(_check(data))


# --- full takeover -------------------------------------------------------------------

def test_full_takeover_is_a_reassignment_not_a_split():
    data = _original()
    by_id(data, "API-001")["assignee"] = "Person B"
    data = recorded(data, on="2026-10-05", reason=REASON)
    t = by_id(data, "API-001")
    assert t["history"][-1]["field"] == "assignee"
    assert (t["history"][-1]["from"], t["history"][-1]["to"]) == ("Person A", "Person B")
    tasks = [x for x in data["tickets"] if x["type"] == "Task"]
    tot = est.summarize(tasks, "hours")
    assert tot.points == Decimal("10.0") and not tot.partial
    rows = {p: a for p, a, _ in est.person_totals(tasks, "hours")}
    assert set(rows) == {"Person B"}
    assert not validate.errors(_check(data))


def test_split_that_leaves_the_original_nothing_is_rejected():
    data = _original()
    by_id(data, "API-001")["estimate"] = None
    child = task("API-002", estimate=estimate(5, 2, 0.5, 0.5, level=3), assignee="Person B")
    child["split_from"] = {"ticket": "API-001", "scope": "replaced", "reason": REASON}
    data["tickets"].append(child)
    data = est.reconcile(data, on="2026-10-05", reason=REASON).data
    problems = validate.errors(_check(data))
    assert "split_leaves_nothing" in codes(problems)
    assert any("reassign" in p.message for p in problems)
