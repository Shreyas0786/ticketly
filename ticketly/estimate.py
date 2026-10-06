"""Estimation models, the shared points calculation, estimate history, and totals.

A backlog uses one of two estimation models, recorded in its ``estimation`` block:

- ``fibonacci`` — the original model: each Task's ``effort`` is a Fibonacci story
  point (1, 2, 3, 5, 8, 13). A backlog with no ``estimation`` block is a legacy
  backlog and is always read as Fibonacci, so its points keep their meaning.
- ``hours`` — hours-based points: each Task carries an ``estimate`` (a standard-hour
  breakdown in quarter hours, a difficulty level with a reason, and a confidence),
  and ``effort`` is calculated from it::

      points = estimated_hours * difficulty_multiplier
      effort = round_half_up(points, 1 decimal place)

  ``calculate_points`` is the one shared calculation. It uses Decimal arithmetic
  and the multipliers frozen in the backlog under the estimate's rubric version,
  so a later calibration of the engine's rubric never rescored existing work.

Every change to a Task's estimate, owner, or status is recorded in its ``history``
(``reconcile`` records them; ``switch_model`` records a model change). Totals keep
the new model and any legacy Fibonacci points apart: they are never added together.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

MODEL_HOURS = "hours"
MODEL_FIBONACCI = "fibonacci"
MODELS = (MODEL_HOURS, MODEL_FIBONACCI)
MODEL_LABELS = {MODEL_HOURS: "Hours-based points", MODEL_FIBONACCI: "Fibonacci points"}

# The initial rubric. These multipliers are calibration parameters, not measured
# facts; a backlog stores the rubric it was estimated under, so changing this table
# later never changes points that were already calculated.
RUBRIC_VERSION = "hours-v1"
RUBRIC_V1: dict[str, str] = {"1": "1.00", "2": "1.10", "3": "1.25", "4": "1.40"}
LEVEL_NAMES = {1: "Basic", 2: "Standard", 3: "Complex", 4: "Advanced"}

# The standard-hour breakdown: implementation, testing, self-review and handoff.
BREAKDOWN_PARTS = ("implementation", "testing", "self_review", "handoff")
CONFIDENCE_LEVELS = ("high", "medium", "low")
FIBONACCI_POINTS = (1, 2, 3, 5, 8, 13)
WORK_KINDS = ("cleanup", "integration", "client_prep", "investigation")
WORK_KIND_LABELS = {
    "cleanup": "Cleanup",
    "integration": "Integration",
    "client_prep": "Client preparation",
    "investigation": "Investigation",
}
STATUSES = ("To Do", "In Progress", "In Review", "Done")

QUARTER_HOUR = Decimal("0.25")
ONE_DECIMAL = Decimal("0.1")
UNESTIMATED = "Unestimated"


class EstimationError(ValueError):
    """An estimate input is invalid (bad hours, unknown level or rubric, ...)."""


# --------------------------------------------------------------------------- #
# the shared calculation
# --------------------------------------------------------------------------- #
def dec(value: Any) -> Decimal:
    """Exact Decimal for a JSON number or numeric string (floats go via str)."""
    if isinstance(value, bool):
        raise EstimationError(f"not a number: {value!r}")
    if isinstance(value, Decimal):
        d = value
    else:
        try:
            d = Decimal(str(value).strip())
        except (InvalidOperation, ValueError) as exc:
            raise EstimationError(f"not a number: {value!r}") from exc
    if not d.is_finite():
        raise EstimationError(f"{value!r} is not a finite number")
    return d


def level_of(value: Any) -> int:
    """A difficulty level as an int: 2, 2.0 and "2.0" are level 2; 2.5, 0, 5 are not levels."""
    try:
        d = dec(value)
    except EstimationError:
        d = None
    if d is None or d != d.to_integral_value() or not 1 <= d <= 4:
        raise EstimationError(f"difficulty level {value!r} must be a whole number from 1 to 4")
    return int(d)


def is_quarter_hour(value: Any) -> bool:
    d = dec(value)
    return d >= 0 and d % QUARTER_HOUR == 0


def round_points(raw: Decimal) -> Decimal:
    """Half-up rounding to one decimal place (1.25 -> 1.3, 1.05 -> 1.1)."""
    return raw.quantize(ONE_DECIMAL, rounding=ROUND_HALF_UP)


def multiplier(level: Any, rubric: dict[str, Any]) -> Decimal:
    key = str(level_of(level))
    if key not in rubric:
        raise EstimationError(f"difficulty level {level!r} is not in the rubric (1-4)")
    return dec(rubric[key])


def raw_points(hours: Any, level: Any, rubric: dict[str, Any]) -> Decimal:
    return dec(hours) * multiplier(level, rubric)


def calculate_points(hours: Any, level: Any, rubric: dict[str, Any]) -> Decimal:
    """points = estimated_hours x difficulty multiplier, rounded half-up to 0.1."""
    h = dec(hours)
    if h <= 0 or not is_quarter_hour(h):
        raise EstimationError(f"estimated hours must be a positive quarter hour, got {hours!r}")
    return round_points(raw_points(h, level, rubric))


def breakdown_total(breakdown: dict[str, Any]) -> Decimal:
    return sum((dec(breakdown[p]) for p in BREAKDOWN_PARTS), Decimal(0))


def json_number(d: Decimal) -> int | float:
    """A Decimal as a JSON-friendly number (ints stay ints)."""
    return int(d) if d == d.to_integral_value() else float(d)


def points_number(d: Decimal) -> float:
    """Calculated points are always stored with one decimal (12.0, 8.8)."""
    return float(round_points(d))


def fmt_points(value: Any, model: str) -> str:
    if value is None:
        return UNESTIMATED
    if model == MODEL_HOURS:
        return str(round_points(dec(value)))
    d = dec(value)
    return str(int(d)) if d == d.to_integral_value() else str(d)


def fmt_hours(value: Any) -> str:
    """8 -> '8', 8.50 -> '8.5', 0.25 -> '0.25' (no exponent notation)."""
    return format(dec(value).normalize(), "f")


# --------------------------------------------------------------------------- #
# backlog model and rubric
# --------------------------------------------------------------------------- #
def model_of(data: dict[str, Any]) -> str:
    """The backlog's estimation model. No ``estimation`` block = legacy Fibonacci."""
    return (data.get("estimation") or {}).get("model", MODEL_FIBONACCI)


def is_marked(data: dict[str, Any]) -> bool:
    return "estimation" in data


def new_estimation_block(model: str) -> dict[str, Any]:
    """The ``estimation`` block a new backlog starts with."""
    if model == MODEL_HOURS:
        return {
            "model": MODEL_HOURS,
            "rubric_version": RUBRIC_VERSION,
            "rubrics": {RUBRIC_VERSION: dict(RUBRIC_V1)},
        }
    return {"model": MODEL_FIBONACCI}


def rubric_for(data: dict[str, Any], version: str) -> dict[str, Any]:
    rubrics = (data.get("estimation") or {}).get("rubrics") or {}
    if version not in rubrics:
        raise EstimationError(f"rubric {version!r} is not recorded in this backlog")
    return rubrics[version]


def current_rubric_version(data: dict[str, Any]) -> str:
    return (data.get("estimation") or {}).get("rubric_version", RUBRIC_VERSION)


def with_estimation(data: dict[str, Any], block: dict[str, Any]) -> dict[str, Any]:
    """A copy of ``data`` with its estimation block set, kept after ``project``."""
    out: dict[str, Any] = {}
    for key, value in data.items():
        if key == "estimation":
            continue
        if key == "tickets":
            out["estimation"] = block
        out[key] = value
    if "estimation" not in out:
        out["estimation"] = block
    return out


def ticket_points(ticket: dict[str, Any], data: dict[str, Any]) -> Decimal | None:
    """The calculated points for a Task's current estimate (None = Unestimated)."""
    est = ticket.get("estimate")
    if not est:
        return None
    rubric = rubric_for(data, est["rubric_version"])
    return calculate_points(est["estimated_hours"], est["difficulty_level"], rubric)


# --------------------------------------------------------------------------- #
# snapshots and history
# --------------------------------------------------------------------------- #
def estimate_snapshot(ticket: dict[str, Any], model: str) -> dict[str, Any]:
    snap: dict[str, Any] = {"model": model, "effort": ticket.get("effort")}
    if model == MODEL_HOURS:
        snap["estimate"] = copy.deepcopy(ticket.get("estimate"))
    return snap


def current_state(ticket: dict[str, Any], model: str) -> dict[str, Any]:
    return {
        "estimate": estimate_snapshot(ticket, model),
        "assignee": ticket.get("assignee"),
        "status": ticket["status"],
    }


def recorded_state(ticket: dict[str, Any]) -> dict[str, Any]:
    """The state the history says the ticket is in. Only recorded fields appear."""
    state: dict[str, Any] = {}
    for event in ticket.get("history") or []:
        fld = event["field"]
        if fld == "baseline":
            state.update(copy.deepcopy(event["to"]))
        elif fld in ("estimate", "model"):
            state["estimate"] = copy.deepcopy(event["to"])
        elif fld in ("assignee", "status"):
            state[fld] = event["to"]
    return state


def unrecorded_fields(ticket: dict[str, Any], model: str) -> list[str]:
    """Tracked fields whose current value differs from what the history records."""
    rec = recorded_state(ticket)
    cur = current_state(ticket, model)
    return [f for f in ("estimate", "assignee", "status") if f in rec and rec[f] != cur[f]]


def is_unestimated_snapshot(snap: dict[str, Any] | None) -> bool:
    return snap is None or (snap.get("effort") is None and not snap.get("estimate"))


def estimate_events(ticket: dict[str, Any]) -> list[dict[str, Any]]:
    return [e for e in ticket.get("history") or [] if e["field"] in ("baseline", "estimate", "model")]


def first_estimate_snapshot(ticket: dict[str, Any]) -> dict[str, Any] | None:
    for event in estimate_events(ticket):
        return event["to"]["estimate"] if event["field"] == "baseline" else event["to"]
    return None


def snapshot_raw(snap: dict[str, Any] | None, data: dict[str, Any]) -> Decimal | None:
    """Unrounded size of an estimate snapshot (hours x multiplier, or Fibonacci points)."""
    if is_unestimated_snapshot(snap):
        return None
    if snap.get("model") == MODEL_HOURS:
        est = snap["estimate"]
        return raw_points(est["estimated_hours"], est["difficulty_level"],
                          rubric_for(data, est["rubric_version"]))
    return dec(snap["effort"])


def _event(on: str, fld: str, before: Any, after: Any, reason: str | None,
           source: str, ticket: dict[str, Any], approved_by: str | None = None) -> dict[str, Any]:
    event: dict[str, Any] = {"on": on, "field": fld, "from": before, "to": after,
                             "reason": reason, "source": source}
    if fld in ("estimate", "model"):
        # attribution and completion at the time of the change
        event["assignee"] = ticket.get("assignee")
        event["status"] = ticket["status"]
    if fld == "estimate" and approved_by:
        # approved growth: lets a split family's total rise above its original estimate
        event["approved_by"] = approved_by
    return event


def replaced_split_children(data: dict[str, Any], original_id: str) -> list[str]:
    return sorted(
        t["id"] for t in data["tickets"]
        if (t.get("split_from") or {}).get("ticket") == original_id
        and t["split_from"].get("scope") == "replaced"
    )


def _already_linked(ticket: dict[str, Any]) -> set[str]:
    linked: set[str] = set()
    for event in ticket.get("history") or []:
        linked.update(event.get("split_to") or [])
    return linked


# --------------------------------------------------------------------------- #
# reconcile: recalculate points and record changes
# --------------------------------------------------------------------------- #
@dataclass
class Result:
    data: dict[str, Any]
    changes: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def reconcile(data: dict[str, Any], *, on: str, reason: str | None = None,
              source: str = "recalc", approved_by: str | None = None) -> Result:
    """Recalculate every Task's points and record unrecorded changes in its history.

    - Hours model: ``effort`` is set from the estimate via ``calculate_points``;
      a Task with no estimate gets ``effort: null`` (Unestimated).
    - A Task with no history gets a ``baseline`` event holding its estimate, owner
      and status, so every later change can be traced back to it.
    - A changed estimate needs a ``reason`` (a first estimate of an Unestimated
      Task does not). Owner and status changes are recorded with the reason, if any.
    - An estimate change on a Task that has new ``replaced`` split children links
      them (``split_to``) so the validator can check the scope wasn't counted twice.
    - ``approved_by`` marks the recorded estimate changes as approved growth (needed
      when re-estimating a split family above what it was estimated at before the split).
    - A Task completed under a previous model can't be re-estimated: its scope stays
      on legacy points, and new work belongs in a new Task.
    """
    out = copy.deepcopy(data)
    res = Result(out)
    model = model_of(out)
    tasks = [t for t in out["tickets"] if t["type"] == "Task"]

    if model == MODEL_HOURS:
        for t in tasks:
            est = t.get("estimate")
            if is_legacy_completed(t) and (est or t.get("effort") is not None):
                res.errors.append(completed_legacy_message(t))
                continue
            if not est:
                if t.get("effort") is not None:
                    res.changes.append(f"{t['id']}: no estimate, points cleared (Unestimated)")
                t["effort"] = None
                continue
            try:
                est["difficulty_level"] = level_of(est["difficulty_level"])  # 2.0 -> 2
                if breakdown_total(est["hours_breakdown"]) != dec(est["estimated_hours"]):
                    res.errors.append(
                        f"{t['id']}: hours breakdown adds up to "
                        f"{fmt_hours(breakdown_total(est['hours_breakdown']))}, "
                        f"not estimated_hours {fmt_hours(est['estimated_hours'])}")
                    continue
                pts = ticket_points(t, out)
            except EstimationError as exc:
                res.errors.append(f"{t['id']}: {exc}")
                continue
            if t.get("effort") is None or dec(t["effort"]) != pts:
                res.changes.append(f"{t['id']}: points set to {pts}")
            t["effort"] = points_number(pts)

    for t in tasks:
        cur = current_state(t, model)
        if not t.get("history"):
            base_reason = reason or "initial state"
            split = t.get("split_from")
            if split:
                base_reason = f"split from {split['ticket']} ({split['scope']}): {split['reason']}"
            t["history"] = [_event(on, "baseline", None, cur, base_reason, source, t)]
            res.changes.append(f"{t['id']}: baseline recorded")
            continue
        rec = recorded_state(t)
        rec_est = rec.get("estimate")
        if rec_est is not None and rec_est.get("model") != model:
            res.errors.append(
                f"{t['id']}: history is on {rec_est.get('model')} but the backlog is on "
                f"{model}; change models only with `ticketly switch-model`")
            continue
        if "estimate" in rec and rec_est != cur["estimate"]:
            first = is_unestimated_snapshot(rec_est)
            if not reason and not first:
                res.errors.append(
                    f"{t['id']}: estimate changed; give the reason with --reason")
                continue
            event = _event(on, "estimate", rec_est, cur["estimate"],
                           reason or "first estimate", source, t, approved_by)
            new_children = [c for c in replaced_split_children(out, t["id"])
                            if c not in _already_linked(t)]
            if new_children:
                event["split_to"] = new_children
            t["history"].append(event)
            res.changes.append(f"{t['id']}: estimate change recorded")
        elif "estimate" not in rec:
            t["history"].append(_event(on, "estimate", None, cur["estimate"],
                                       reason or "estimate recorded", source, t))
            res.changes.append(f"{t['id']}: estimate recorded")
        for fld in ("assignee", "status"):
            if fld in rec and rec[fld] == cur[fld]:
                continue
            t["history"].append(_event(on, fld, rec.get(fld), cur[fld], reason, source, t))
            res.changes.append(f"{t['id']}: {fld} change recorded")

    if res.changes and not is_marked(out):
        # touching a legacy backlog records its model explicitly; meaning is unchanged
        res.data = with_estimation(out, new_estimation_block(MODEL_FIBONACCI))
    return res


# --------------------------------------------------------------------------- #
# switching models
# --------------------------------------------------------------------------- #
def switch_model(data: dict[str, Any], *, to: str, reason: str, on: str) -> Result:
    """Move a backlog to another estimation model, explicitly and with a reason.

    Every Task keeps its old estimate in ``legacy_estimates`` (with its owner, its
    status and whether it was already completed) and records a ``model`` history
    event; its estimate in the new model starts as Unestimated until it is
    re-estimated. Completed legacy Tasks keep their original points and owner and
    stay out of the new model's totals.
    """
    current = model_of(data)
    if to not in MODELS:
        return Result(data, errors=[f"unknown estimation model {to!r}"])
    if to == current:
        return Result(data, errors=[f"the backlog already uses {MODEL_LABELS[to]}"])
    if to != MODEL_HOURS:
        return Result(data, errors=[
            "switching from hours-based points back to Fibonacci points is not supported"])
    if not (reason or "").strip():
        return Result(data, errors=["a reason is required to change estimation models"])

    base = reconcile(data, on=on, source="switch-model")
    if base.errors:
        return Result(data, errors=base.errors + [
            "record pending changes with `ticketly recalc --reason ...` before switching"])
    out = base.data
    changes = list(base.changes)

    for t in out["tickets"]:
        if t["type"] != "Task":
            continue
        before = estimate_snapshot(t, current)
        legacy = {
            "model": current,
            "effort": t.get("effort"),
            "assignee": t.get("assignee"),
            "status": t["status"],
            "completed": t["status"] == "Done",
            "on": on,
            "reason": reason,
        }
        t.setdefault("legacy_estimates", []).append(legacy)
        t["effort"] = None
        t["estimate"] = None
        t["history"].append(_event(on, "model", before, estimate_snapshot(t, to),
                                   reason, "switch-model", t))
        changes.append(f"{t['id']}: {MODEL_LABELS[current]} kept as legacy, now Unestimated")

    block = new_estimation_block(to)
    history = list(((out.get("estimation") or {}).get("history")) or [])
    history.append({"on": on, "from": current, "to": to, "reason": reason})
    block["history"] = history
    out = with_estimation(out, block)
    return Result(out, changes=changes)


# --------------------------------------------------------------------------- #
# totals
# --------------------------------------------------------------------------- #
def last_legacy(ticket: dict[str, Any]) -> dict[str, Any] | None:
    legacy = ticket.get("legacy_estimates") or []
    return legacy[-1] if legacy else None


def is_legacy_completed(ticket: dict[str, Any]) -> bool:
    """Completed under the previous model: it keeps its legacy points and the owner
    recorded at the switch, stays out of the new model's totals, and is never
    re-estimated (new work on it belongs in a new Task)."""
    legacy = last_legacy(ticket)
    return bool(legacy and legacy.get("completed"))


def completed_legacy_message(ticket: dict[str, Any]) -> str:
    legacy = last_legacy(ticket) or {}
    label = MODEL_LABELS.get(legacy.get("model"), "the previous model")
    return (f"{ticket['id']}: completed under {label} before the switch; its scope stays on "
            "legacy points and can't be re-estimated. Put any new work in a new task")


@dataclass
class Totals:
    tickets: int = 0
    estimated: int = 0
    unestimated: int = 0
    points: Decimal = Decimal(0)
    hours: Decimal = Decimal(0)
    legacy_tickets: int = 0
    legacy_completed: int = 0
    legacy_points: dict[str, Decimal] = field(default_factory=dict)

    @property
    def partial(self) -> bool:
        return self.unestimated > 0


def summarize(tasks: list[dict[str, Any]], model: str) -> Totals:
    """Totals for a set of Tasks. New-model points/hours and legacy points are kept
    apart; completed legacy Tasks count only toward the legacy figures."""
    tot = Totals()
    for t in tasks:
        legacy = last_legacy(t)
        if legacy is not None:
            tot.legacy_tickets += 1
            if legacy.get("effort") is not None:
                tot.legacy_points[legacy["model"]] = (
                    tot.legacy_points.get(legacy["model"], Decimal(0)) + dec(legacy["effort"]))
        if is_legacy_completed(t):
            tot.legacy_completed += 1
            continue
        tot.tickets += 1
        if t.get("effort") is None:
            tot.unestimated += 1
            continue
        tot.estimated += 1
        tot.points += dec(t["effort"])
        if model == MODEL_HOURS and t.get("estimate"):
            tot.hours += dec(t["estimate"]["estimated_hours"])
    return tot


def describe_totals(tot: Totals, model: str) -> str:
    """'24.5 points · 22 standard hours (partial: 1 of 4 tickets unestimated)'."""
    if model == MODEL_HOURS:
        text = f"{fmt_points(tot.points, model)} points · {fmt_hours(tot.hours)} standard hours"
    else:
        n = int(tot.points)
        text = f"{n} point" if n == 1 else f"{n} points"
    if tot.partial:
        text += f" (partial: {tot.unestimated} of {tot.tickets} tickets unestimated)"
    return text


def legacy_completed_by_person(tasks: list[dict[str, Any]]) -> list[tuple[str, int, dict[str, Decimal]]]:
    """Completed legacy work per person, attributed to the owner recorded in the
    legacy snapshot at the switch (not whoever owns the task now)."""
    people: dict[str, tuple[int, dict[str, Decimal]]] = {}
    for t in tasks:
        if not is_legacy_completed(t):
            continue
        legacy = last_legacy(t)
        person = legacy.get("assignee") or ""
        count, points = people.get(person, (0, {}))
        if legacy.get("effort") is not None:
            points[legacy["model"]] = points.get(legacy["model"], Decimal(0)) + dec(legacy["effort"])
        people[person] = (count + 1, points)
    order = sorted(p for p in people if p) + ([""] if "" in people else [])
    return [(p or "Unassigned", *people[p]) for p in order]


def person_totals(tasks: list[dict[str, Any]], model: str) -> list[tuple[str, Totals, Totals]]:
    """(person, assigned, done) per owner, Unassigned last. Done = status Done."""
    people: dict[str, list[dict[str, Any]]] = {}
    for t in tasks:
        people.setdefault(t.get("assignee") or "", []).append(t)
    rows = []
    for person in sorted(p for p in people if p) + ([""] if "" in people else []):
        owned = people[person]
        rows.append((person or "Unassigned", summarize(owned, model),
                     summarize([t for t in owned if t["status"] == "Done"], model)))
    return rows
