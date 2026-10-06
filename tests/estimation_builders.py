"""Small backlog builders shared by the estimation tests (not a test module)."""

from __future__ import annotations

import copy

from ticketly import estimate as est

ON = "2026-10-01"


def estimate(impl=5, testing=2, review=0.5, handoff=0.5, level=2,
             reason="A conventional, well-documented integration.",
             confidence="high", rubric="hours-v1"):
    return {
        "estimated_hours": impl + testing + review + handoff,
        "hours_breakdown": {"implementation": impl, "testing": testing,
                            "self_review": review, "handoff": handoff},
        "difficulty_level": level,
        "difficulty_reason": reason,
        "estimate_confidence": confidence,
        "rubric_version": rubric,
    }


def epic(eid="EPIC-API", **kw):
    t = {"id": eid, "title": f"{eid} area", "type": "Epic", "parent": None, "status": "To Do",
         "effort": 0, "dependencies": [], "description": "An area.", "acceptance_criteria": [],
         "needs_clarification": False}
    t.update(kw)
    return t


def task(tid, parent="EPIC-API", effort=None, **kw):
    t = {"id": tid, "title": f"Task {tid}", "type": "Task", "parent": parent, "status": "To Do",
         "effort": effort, "dependencies": [], "description": "Do the thing.",
         "acceptance_criteria": ["returns 200 for a valid request"], "needs_clarification": False}
    t.update(kw)
    return t


def hours_backlog(*tickets):
    return {"project": "Demo Project", "estimation": est.new_estimation_block("hours"),
            "tickets": [copy.deepcopy(t) for t in tickets]}


def fib_backlog(*tickets, marked=False):
    data = {"project": "Demo Project", "tickets": [copy.deepcopy(t) for t in tickets]}
    if marked:
        data = est.with_estimation(data, est.new_estimation_block("fibonacci"))
    return data


def recorded(data, on=ON, reason=None, approved_by=None):
    """Run the engine's reconcile and insist it succeeded."""
    result = est.reconcile(data, on=on, reason=reason, approved_by=approved_by)
    assert not result.errors, result.errors
    return result.data


def by_id(data, tid):
    return next(t for t in data["tickets"] if t["id"] == tid)


def codes(problems):
    return {p.code for p in problems}
