"""Phase 3 tests for the backlog integrity validator and build-order view.

Each integrity rule gets a focused case: a clean backlog is clean, and every
error/warning class is provoked and detected. Build order is asserted to respect
dependencies and to return None on a cycle. The render integration is covered in
test_phase3_render_integration.py.
"""

import copy
import json
from pathlib import Path

import pytest

from ticketly import validate

ROOT = Path(__file__).resolve().parent.parent
CLEAN = ROOT / "ticketly" / "data" / "examples" / "sample-release-backlog.json"


def _epic(tid="EPIC-API", **kw):
    base = dict(id=tid, title="API", type="Epic", parent=None, status="To Do",
               effort=0, dependencies=[], description="x", acceptance_criteria=[],
               needs_clarification=False)
    base.update(kw)
    return base


def _task(tid="API-001", parent="EPIC-API", **kw):
    base = dict(id=tid, title="A task", type="Task", parent=parent, status="To Do",
               effort=2, dependencies=[], description="x",
               acceptance_criteria=["done"], needs_clarification=False)
    base.update(kw)
    return base


def _backlog(*tickets):
    return {"company": "Demo Company", "project": "Demo Project", "tickets": list(tickets)}


def codes(problems):
    return {p.code for p in problems}


# --- clean ---------------------------------------------------------------

def test_shipped_example_is_clean():
    data = json.loads(CLEAN.read_text())
    assert validate.check_integrity(data) == []


def test_house_style_example_is_clean():
    data = json.loads((ROOT / "ticketly" / "data" / "examples" / "house-style-backlog.json").read_text())
    assert validate.errors(validate.check_integrity(data)) == []


# --- error classes -------------------------------------------------------

def test_duplicate_id():
    bl = _backlog(_epic(), _task("API-001"), _task("API-001"))
    assert "duplicate_id" in codes(validate.check_integrity(bl))


def test_dangling_dependency():
    bl = _backlog(_epic(), _task("API-001", dependencies=["API-999"]))
    assert "dangling_dependency" in codes(validate.check_integrity(bl))


def test_self_dependency():
    bl = _backlog(_epic(), _task("API-001", dependencies=["API-001"]))
    assert "self_dependency" in codes(validate.check_integrity(bl))


def test_missing_parent():
    bl = _backlog(_epic(), _task("API-001", parent="EPIC-GONE"))
    assert "missing_parent" in codes(validate.check_integrity(bl))


def test_parent_not_epic():
    bl = _backlog(_epic(), _task("API-001"), _task("API-002", parent="API-001"))
    assert "parent_not_epic" in codes(validate.check_integrity(bl))


def test_epic_with_parent():
    bl = _backlog(_epic(), _epic("EPIC-WEB", parent="EPIC-API"))
    assert "epic_has_parent" in codes(validate.check_integrity(bl))


def test_epic_effort_nonzero():
    bl = _backlog(_epic(effort=3), _task("API-001"))
    assert "epic_effort_nonzero" in codes(validate.check_integrity(bl))


def test_missing_acceptance_criteria_is_error():
    bl = _backlog(_epic(), _task("API-001", acceptance_criteria=[]))
    assert "missing_acceptance_criteria" in codes(validate.check_integrity(bl))


def test_missing_acceptance_criteria_allowed_when_flagged():
    bl = _backlog(_epic(), _task("API-001", acceptance_criteria=[], needs_clarification=True))
    assert "missing_acceptance_criteria" not in codes(validate.check_integrity(bl))


def test_circular_dependency():
    bl = _backlog(
        _epic(),
        _task("API-001", dependencies=["API-002"]),
        _task("API-002", dependencies=["API-001"]),
    )
    problems = validate.check_integrity(bl)
    assert "circular_dependency" in codes(problems)
    assert validate.errors(problems)  # it's an error


# --- warnings ------------------------------------------------------------

def test_orphan_task_is_warning_not_error():
    bl = _backlog(_epic(), _task("API-001", parent=None))
    problems = validate.check_integrity(bl)
    assert "orphan_task" in codes(problems)
    assert not any(p.code == "orphan_task" and p.severity == "error" for p in problems)


def test_possible_duplicate_title_is_warning():
    bl = _backlog(_epic(), _task("API-001", title="Same Thing"),
                  _task("API-002", title="same thing"))
    problems = validate.check_integrity(bl)
    dup = [p for p in problems if p.code == "possible_duplicate"]
    assert dup and dup[0].severity == "warning"


# --- vague acceptance criteria (checkability lint) -----------------------

def test_vague_phrase_acceptance_criterion_is_warning():
    bl = _backlog(_epic(), _task("API-001", acceptance_criteria=["the page works well"]))
    problems = validate.check_integrity(bl)
    vague = [p for p in problems if p.code == "vague_acceptance_criteria"]
    assert vague and vague[0].severity == "warning"


def test_bare_completion_word_is_flagged():
    bl = _backlog(_epic(), _task("API-001", acceptance_criteria=["Done."]))
    assert "vague_acceptance_criteria" in codes(validate.check_integrity(bl))


def test_vague_acceptance_criteria_never_an_error():
    # it must stay a warning so it never blocks rendering
    bl = _backlog(_epic(), _task("API-001", acceptance_criteria=["intuitive and easy to use"]))
    problems = validate.check_integrity(bl)
    assert not any(p.code == "vague_acceptance_criteria" and p.severity == "error"
                   for p in problems)


def test_checkable_criteria_not_flagged():
    bl = _backlog(_epic(), _task("API-001", acceptance_criteria=[
        "responds within 200ms at p95", "rejects files over 10MB with a 413"]))
    assert "vague_acceptance_criteria" not in codes(validate.check_integrity(bl))


def test_shipped_examples_have_no_vague_criteria():
    # the curated lint must be quiet on the hand-written example backlogs
    for name in ("sample-release-backlog.json", "house-style-backlog.json"):
        data = json.loads((ROOT / "ticketly" / "data" / "examples" / name).read_text())
        assert "vague_acceptance_criteria" not in codes(validate.check_integrity(data))


# --- build order ---------------------------------------------------------

def test_build_order_respects_dependencies():
    bl = _backlog(
        _epic(),
        _task("API-003", dependencies=["API-002"]),
        _task("API-002", dependencies=["API-001"]),
        _task("API-001"),
    )
    order = validate.build_order(bl["tickets"])
    assert order == ["API-001", "API-002", "API-003"]


def test_build_order_is_deterministic_tiebreak_by_id():
    bl = _backlog(_epic(), _task("API-002"), _task("API-001"))
    assert validate.build_order(bl["tickets"]) == ["API-001", "API-002"]


def test_build_order_none_on_cycle():
    bl = _backlog(
        _epic(),
        _task("API-001", dependencies=["API-002"]),
        _task("API-002", dependencies=["API-001"]),
    )
    assert validate.build_order(bl["tickets"]) is None


# --- cli -----------------------------------------------------------------

def test_cli_returns_zero_on_clean(capsys):
    assert validate.main([str(CLEAN)]) == 0


def test_cli_returns_one_on_errors(tmp_path):
    bad = _backlog(_epic(), _task("API-001", dependencies=["API-999"]))
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(bad))
    assert validate.main([str(p)]) == 1


# --- skill wiring --------------------------------------------------------

def test_skill_wires_in_validation_and_dedupe():
    skill = (ROOT / ".claude" / "skills" / "ticketly" / "SKILL.md").read_text()
    assert "ticketly validate" in skill
    assert "dedupe" in skill.lower()
    assert "build order" in skill.lower()
