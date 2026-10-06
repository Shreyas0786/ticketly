"""Backlog integrity checks beyond JSON-schema validation.

The schema guarantees each ticket's *shape*. This module guarantees the backlog
hangs together as a whole: no duplicate IDs, no dependency pointing at a ticket
that doesn't exist, no ticket depending on itself, every Task parented to a real
Epic, epics sized at 0, no circular dependencies, and (the guardrail) every Task
carrying acceptance criteria unless it is explicitly flagged for clarification.

It also checks estimation: hours-based points match their inputs and frozen
rubric, changes to estimates, owners and status are recorded in each Task's
history, and split/takeover links never loop or count the same scope twice.

Problems are tagged ``error`` (the backlog is broken — rendering aborts) or
``warning`` (worth a look — likely duplicate tickets, or acceptance criteria that
aren't objectively checkable — but not fatal).

``build_order`` returns the Tasks topologically sorted by their dependencies, so
they can be worked one at a time; it returns ``None`` if a cycle makes ordering
impossible (``check_integrity`` reports the cycle as an error).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from ticketly import estimate as est


@dataclass(frozen=True)
class Problem:
    severity: str  # "error" or "warning"
    code: str
    message: str
    ticket_id: str | None = None

    def __str__(self) -> str:
        where = f" [{self.ticket_id}]" if self.ticket_id else ""
        return f"{self.severity.upper()}: {self.message}{where} ({self.code})"


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


# Acceptance criteria that can't be objectively ticked off: subjective quality
# words and bare completion words. Curated to stay quiet — only phrases that are
# almost always non-checkable — so a well-written backlog raises no false alarms.
_VAGUE_AC_PHRASES = (
    "works well", "work well", "works fine", "works correctly", "works properly",
    "works as expected", "as expected", "user-friendly", "user friendly",
    "easy to use", "intuitive", "seamless", "seamlessly", "gracefully",
    "looks good", "looks nice", "performs well", "fast enough",
    "and so on", "etc.",
)
_BARE_AC_WORDS = frozenset({
    "done", "works", "working", "complete", "completed", "finished",
    "good", "ok", "okay", "tested", "implemented",
})


def _uncheckable_ac(criterion: str) -> bool:
    """True if an acceptance criterion isn't objectively checkable — a bare
    completion word ('done', 'works') or a subjective quality phrase."""
    text = criterion.strip().lower()
    bare = re.sub(r"[^a-z0-9 ]", "", text).strip()
    if bare in _BARE_AC_WORDS:
        return True
    return any(phrase in text for phrase in _VAGUE_AC_PHRASES)


def _cycle_exists(tickets: list[dict], ids: set[str]) -> bool:
    """True if the dependency graph over existing ids has a cycle (Kahn's)."""
    deps = {
        t["id"]: [d for d in t.get("dependencies", []) if d in ids and d != t["id"]]
        for t in tickets
    }
    indeg = {tid: len(ds) for tid, ds in deps.items()}
    dependents: dict[str, list[str]] = {tid: [] for tid in deps}
    for tid, ds in deps.items():
        for d in ds:
            dependents[d].append(tid)
    ready = [tid for tid, n in indeg.items() if n == 0]
    placed = 0
    while ready:
        tid = ready.pop()
        placed += 1
        for dep_t in dependents[tid]:
            indeg[dep_t] -= 1
            if indeg[dep_t] == 0:
                ready.append(dep_t)
    return placed != len(deps)


def check_integrity(data: dict[str, Any]) -> list[Problem]:
    """Return all integrity problems in a (schema-valid) backlog. Empty == clean."""
    tickets = data["tickets"]
    problems: list[Problem] = []

    ids = [t["id"] for t in tickets]
    id_set = set(ids)
    epic_ids = {t["id"] for t in tickets if t["type"] == "Epic"}

    # duplicate IDs
    seen: set[str] = set()
    for tid in ids:
        if tid in seen:
            problems.append(Problem("error", "duplicate_id", f"duplicate ticket id {tid}", tid))
        seen.add(tid)

    for t in tickets:
        tid = t["id"]

        # dependencies
        for d in t.get("dependencies", []):
            if d == tid:
                problems.append(Problem("error", "self_dependency", "ticket depends on itself", tid))
            elif d not in id_set:
                problems.append(
                    Problem("error", "dangling_dependency", f"depends on unknown ticket {d}", tid)
                )

        # parent / type wiring
        if t["type"] == "Task":
            parent = t.get("parent")
            if parent is None:
                problems.append(
                    Problem("warning", "orphan_task", "Task has no parent epic", tid)
                )
            elif parent not in id_set:
                problems.append(
                    Problem("error", "missing_parent", f"parent {parent} does not exist", tid)
                )
            elif parent not in epic_ids:
                problems.append(
                    Problem("error", "parent_not_epic", f"parent {parent} is not an Epic", tid)
                )
            if not t.get("acceptance_criteria") and not t.get("needs_clarification"):
                problems.append(
                    Problem(
                        "error",
                        "missing_acceptance_criteria",
                        "Task has no acceptance criteria and is not flagged needs_clarification",
                        tid,
                    )
                )
            vague = [c for c in t.get("acceptance_criteria", []) if _uncheckable_ac(c)]
            if vague:
                preview = "; ".join(vague[:2])
                problems.append(
                    Problem(
                        "warning",
                        "vague_acceptance_criteria",
                        f"acceptance criteria may not be objectively checkable: {preview}",
                        tid,
                    )
                )
        else:  # Epic
            if t.get("parent") is not None:
                problems.append(
                    Problem("error", "epic_has_parent", "Epic must have a null parent", tid)
                )
            if t.get("effort") != 0:
                problems.append(
                    Problem("error", "epic_effort_nonzero", "Epic effort must be 0", tid)
                )

    # circular dependencies
    if _cycle_exists(tickets, id_set):
        problems.append(
            Problem("error", "circular_dependency", "dependency cycle detected among tickets")
        )

    problems += _estimation_problems(data)
    problems += _history_problems(data)
    problems += _split_problems(data)

    # likely duplicates (warning): same normalized title
    by_title: dict[str, list[str]] = {}
    for t in tickets:
        by_title.setdefault(_norm(t["title"]), []).append(t["id"])
    for title, group in by_title.items():
        if len(group) > 1:
            problems.append(
                Problem(
                    "warning",
                    "possible_duplicate",
                    f"tickets share the title '{title}': {', '.join(group)}",
                )
            )

    return problems


def _estimation_problems(data: dict[str, Any]) -> list[Problem]:
    """Hours model: calculated points match their inputs, breakdowns add up, every
    estimate's rubric is frozen in the backlog, completed legacy work isn't
    re-estimated, and Unestimated Tasks are visible."""
    if est.model_of(data) != est.MODEL_HOURS:
        return []
    problems: list[Problem] = []
    estimation = data.get("estimation") or {}
    rubrics = estimation.get("rubrics") or {}
    if estimation.get("rubric_version") not in rubrics:
        problems.append(Problem(
            "error", "unknown_rubric",
            f"current rubric {estimation.get('rubric_version')!r} is not recorded in estimation.rubrics"))

    for t in data["tickets"]:
        try:
            problems += _ticket_estimate_problems(t, data, rubrics)
        except est.EstimationError as exc:
            problems.append(Problem("error", "invalid_estimate", str(exc), t["id"]))
    return problems


def _ticket_estimate_problems(t: dict[str, Any], data: dict[str, Any],
                              rubrics: dict[str, Any]) -> list[Problem]:
    tid = t["id"]
    estimate = t.get("estimate")
    if t["type"] == "Epic":
        if estimate:
            return [Problem("error", "epic_has_estimate",
                            "Epic has no estimate of its own; its total is the sum of its Tasks", tid)]
        return []
    if est.is_legacy_completed(t):
        if estimate or t.get("effort") is not None:
            return [Problem("error", "completed_legacy_reestimated",
                            est.completed_legacy_message(t).split(": ", 1)[1], tid)]
        return []
    if not estimate:
        if t.get("effort") is not None:
            return [Problem("error", "effort_without_estimate",
                            "Task has points but no estimate; run `ticketly recalc`", tid)]
        if t.get("needs_clarification"):
            return [Problem("warning", "unestimated",
                            "Task is Unestimated and flagged for clarification; estimate it once "
                            "the open questions are answered", tid)]
        return [Problem("warning", "unestimated",
                        "Task is Unestimated; estimate it, or flag needs_clarification if it can't "
                        "be estimated responsibly", tid)]
    if estimate["rubric_version"] not in rubrics:
        return [Problem("error", "unknown_rubric",
                        f"estimate uses rubric {estimate['rubric_version']!r}, which is not recorded "
                        "in estimation.rubrics", tid)]
    total = est.breakdown_total(estimate["hours_breakdown"])
    if total != est.dec(estimate["estimated_hours"]):
        return [Problem("error", "hours_breakdown_mismatch",
                        f"hours breakdown adds up to {est.fmt_hours(total)}, not estimated_hours "
                        f"{est.fmt_hours(estimate['estimated_hours'])}", tid)]
    points = est.ticket_points(t, data)
    if t.get("effort") is None or est.dec(t["effort"]) != points:
        return [Problem("error", "effort_mismatch",
                        f"effort {t.get('effort')} does not match the calculated {points} points; "
                        "run `ticketly recalc`", tid)]
    return []


def _history_problems(data: dict[str, Any]) -> list[Problem]:
    """Every change to a tracked Task is recorded: its current estimate, owner and
    status match the latest history entries, and (hours model) every estimate has
    been recorded at least once."""
    model = est.model_of(data)
    problems: list[Problem] = []
    for t in data["tickets"]:
        if t["type"] != "Task":
            continue
        tid = t["id"]
        rec = est.recorded_state(t)
        rec_est = rec.get("estimate")
        if rec_est is not None and rec_est.get("model") != model:
            problems.append(Problem(
                "error", "history_model_mismatch",
                f"history records {rec_est.get('model')} estimates but the backlog uses "
                f"{model}; change models with `ticketly switch-model`", tid))
            continue
        changed = est.unrecorded_fields(t, model)
        if changed:
            problems.append(Problem(
                "error", "unrecorded_change",
                f"{', '.join(changed)} changed without a history entry; run `ticketly recalc` "
                "(with --reason for an estimate change)", tid))
        if model == est.MODEL_HOURS and t.get("estimate") and "estimate" not in rec:
            problems.append(Problem(
                "error", "estimate_not_recorded",
                "estimate has no history entry; run `ticketly recalc`", tid))
    return problems


def _split_cycle(splits: dict[str, str]) -> bool:
    for start in splits:
        seen = {start}
        node = splits[start]
        while node in splits:
            if node in seen:
                return True
            seen.add(node)
            node = splits[node]
        if node in seen:
            return True
    return False


def _split_problems(data: dict[str, Any]) -> list[Problem]:
    """Split/takeover links point at real Tasks, never loop, and never count the
    same scope twice.

    Each 'replaced' split must be matched by a recorded reduction of its parent's
    estimate that leaves the parent some work (a full takeover is a reassignment,
    not a split). Every chain of replaced splits forms a *family*; the family's
    current total may never exceed what its root was estimated at before the first
    split, plus any growth recorded with ``approved_by`` — so later re-estimates of
    any member, repeated splits and nested splits stay inside the original scope.
    """
    tickets = data["tickets"]
    by_id = {t["id"]: t for t in tickets}
    model = est.model_of(data)
    problems: list[Problem] = []
    splits: dict[str, str] = {}

    for t in tickets:
        split = t.get("split_from")
        if not split:
            continue
        tid, target = t["id"], split["ticket"]
        if t["type"] != "Task":
            problems.append(Problem("error", "split_on_epic", "only a Task can be split out", tid))
        elif target == tid:
            problems.append(Problem("error", "self_split", "Task is split from itself", tid))
        elif target not in by_id:
            problems.append(Problem("error", "dangling_split",
                                    f"split from unknown ticket {target}", tid))
        elif by_id[target]["type"] != "Task":
            problems.append(Problem("error", "split_from_epic",
                                    f"split from {target}, which is not a Task", tid))
        else:
            splits[tid] = target

    if _split_cycle(splits):
        problems.append(Problem("error", "circular_split", "split_from links form a cycle"))
        return problems

    # every split_to link points back at a matching 'replaced' split (a child that
    # was later dropped from the backlog simply no longer counts)
    for t in tickets:
        for event in t.get("history") or []:
            for child in event.get("split_to") or []:
                c = by_id.get(child)
                if c is None:
                    continue
                link = c.get("split_from") or {}
                if link.get("ticket") != t["id"] or link.get("scope") != "replaced":
                    problems.append(Problem(
                        "error", "split_link_mismatch",
                        f"history says {child} took over scope from this Task, but {child} "
                        "is not a 'replaced' split of it", t["id"]))

    replaced: dict[str, str] = {}
    for tid, target in splits.items():
        child, original = by_id[tid], by_id[target]
        split = child["split_from"]
        if split["scope"] == "additional":
            owner = child.get("assignee")
            if owner and owner == original.get("assignee") and not split.get("approved_by"):
                problems.append(Problem(
                    "warning", "same_owner_additional_scope",
                    f"additional scope split from {target} has the same owner; fixing your own "
                    "incomplete work doesn't add points. If this is approved new scope, record "
                    "approved_by", tid))
            continue
        replaced[tid] = target
        problems += _split_link_problems(tid, target, by_id, data)

    problems += _split_family_problems(replaced, by_id, data, model)
    return problems


def _split_link_problems(tid: str, target: str, by_id: dict[str, dict],
                         data: dict[str, Any]) -> list[Problem]:
    """One replaced split: the parent recorded handing this scope over, kept some
    work for itself, and both sides were estimated in the same model."""
    event = next((e for e in est.estimate_events(by_id[target])
                  if e["field"] == "estimate" and tid in (e.get("split_to") or [])), None)
    if event is None:
        return [Problem(
            "error", "split_not_reconciled",
            f"takes over scope from {target}, but {target}'s estimate was never reduced to "
            f"the work it keeps; reduce it and run `ticketly recalc --reason ...` so the "
            "scope isn't counted twice", tid)]
    if est.is_unestimated_snapshot(event["from"]):
        return [Problem(
            "error", "split_original_unestimated",
            f"{target} was Unestimated before the split, so the transferred scope "
            "can't be checked; estimate it first", tid)]
    if est.is_unestimated_snapshot(event["to"]):
        return [Problem(
            "error", "split_leaves_nothing",
            f"{target} keeps none of its work, so this is a full takeover: reassign {target} "
            "instead of splitting it (the reassignment is recorded in its history)", tid)]
    moved = est.first_estimate_snapshot(by_id[tid]) or {}
    if moved.get("model", event["from"].get("model")) != event["from"].get("model"):
        return [Problem(
            "error", "split_model_mismatch",
            f"split from {target} mixes estimation models; re-estimate both in one model", tid)]
    return []


def _first_estimate_index(history: list[dict[str, Any]]) -> int:
    return next((i for i, e in enumerate(history)
                 if e["field"] in ("baseline", "estimate", "model")), -1)


def _split_family_problems(replaced: dict[str, str], by_id: dict[str, dict],
                           data: dict[str, Any], model: str) -> list[Problem]:
    def link_model(child: str) -> str | None:
        event = next((e for e in est.estimate_events(by_id[replaced[child]])
                      if e["field"] == "estimate" and child in (e.get("split_to") or [])), None)
        return (event["from"] or {}).get("model") if event else None

    # Splits made before a model switch belong to the legacy points; families are
    # built only from splits recorded in the backlog's current model.
    replaced = {c: p for c, p in replaced.items() if link_model(c) == model}

    def root_of(tid: str) -> str:
        while tid in replaced:
            tid = replaced[tid]
        return tid

    families: dict[str, list[str]] = {}
    for child in sorted(replaced):
        families.setdefault(root_of(child), []).append(child)

    problems: list[Problem] = []
    for root, children in sorted(families.items()):
        members = [root, *children]
        history = by_id[root].get("history") or []
        first = next((i for i, e in enumerate(history)
                      if e["field"] == "estimate" and e.get("split_to")
                      and (e["from"] or {}).get("model") == model), None)
        if first is None:
            continue
        start = history[first]
        try:
            budget = est.snapshot_raw(start["from"], data)
            if budget is None:
                continue  # reported per child as split_original_unestimated
            approved = Decimal(0)
            for m in members:
                mh = by_id[m].get("history") or []
                begin = first + 1 if m == root else _first_estimate_index(mh) + 1
                for e in mh[begin:]:
                    if e["field"] == "estimate" and e.get("approved_by"):
                        grew = ((est.snapshot_raw(e["to"], data) or 0)
                                - (est.snapshot_raw(e["from"], data) or 0))
                        approved += max(grew, Decimal(0))
            current = sum((est.snapshot_raw(est.estimate_snapshot(by_id[m], model), data) or 0
                           for m in members), Decimal(0))
        except est.EstimationError as exc:
            problems.append(Problem("error", "invalid_estimate", str(exc), root))
            continue
        if current > budget + approved:
            # Fibonacci points aren't additive, so there it's a prompt to look, not a block
            severity = "error" if model == est.MODEL_HOURS else "warning"
            grown = f" plus {est.fmt_hours(approved)} approved growth" if approved else ""
            problems.append(Problem(
                severity, "split_duplicates_scope",
                f"{', '.join(members)} share the scope {root} was estimated at before it was "
                f"split ({est.fmt_hours(budget)} unrounded points{grown}) but now total "
                f"{est.fmt_hours(current)}, so the same work may be counted twice. If the work "
                "genuinely grew, re-estimate with `ticketly recalc --reason ... --approved-by "
                "NAME`; record new work as an 'additional' task", root))
    return problems


def _reject_constant(name: str) -> Any:
    raise ValueError(f"{name} is not allowed in a backlog; every number must be finite")


def read_json(path: str | Path) -> Any:
    """Read a backlog JSON file, refusing NaN / Infinity (which Python's json accepts)."""
    return json.loads(Path(path).read_text(), parse_constant=_reject_constant)


def non_finite_paths(value: Any, where: str = "") -> list[str]:
    """Locations of NaN / Infinity floats in an already-loaded backlog."""
    if isinstance(value, float):
        return [] if value == value and value not in (float("inf"), float("-inf")) else [where or "/"]
    if isinstance(value, dict):
        return [p for k, v in value.items() for p in non_finite_paths(v, f"{where}/{k}")]
    if isinstance(value, list):
        return [p for i, v in enumerate(value) for p in non_finite_paths(v, f"{where}/{i}")]
    return []


def errors(problems: list[Problem]) -> list[Problem]:
    return [p for p in problems if p.severity == "error"]


def warnings(problems: list[Problem]) -> list[Problem]:
    return [p for p in problems if p.severity == "warning"]


def build_order(tickets: list[dict]) -> list[str] | None:
    """Topologically sort Tasks by their (Task-to-Task) dependencies.

    Deterministic: ties break by ascending id. Returns None on a cycle.
    """
    tasks = [t for t in tickets if t["type"] == "Task"]
    ids = {t["id"] for t in tasks}
    deps = {
        t["id"]: sorted(d for d in t.get("dependencies", []) if d in ids and d != t["id"])
        for t in tasks
    }
    indeg = {tid: len(ds) for tid, ds in deps.items()}
    dependents: dict[str, list[str]] = {tid: [] for tid in ids}
    for tid, ds in deps.items():
        for d in ds:
            dependents[d].append(tid)

    ready = sorted(tid for tid, n in indeg.items() if n == 0)
    order: list[str] = []
    while ready:
        tid = ready.pop(0)
        order.append(tid)
        for dep_t in sorted(dependents[tid]):
            indeg[dep_t] -= 1
            if indeg[dep_t] == 0:
                ready.append(dep_t)
        ready.sort()
    return order if len(order) == len(ids) else None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ticketly.validate",
        description="Check a Ticketly backlog for integrity problems beyond the schema.",
    )
    parser.add_argument("backlog", help="Path to a backlog JSON file.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    from jsonschema import Draft202012Validator

    from ticketly.home import TICKET_SCHEMA

    try:
        data = read_json(args.backlog)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        print("\n1 error(s); backlog is not safe to ship.", file=sys.stderr)
        return 1
    schema_errors = list(Draft202012Validator(json.loads(TICKET_SCHEMA.read_text()))
                         .iter_errors(data))
    if schema_errors:
        for err in schema_errors[:10]:
            where = "/".join(str(p) for p in err.absolute_path) or "(top level)"
            print(f"ERROR: schema: {where}: {err.message}", file=sys.stderr)
        print(f"\n{len(schema_errors)} schema error(s); backlog is not safe to ship.",
              file=sys.stderr)
        return 1
    problems = check_integrity(data)
    for p in problems:
        print(p, file=sys.stderr)
    errs = errors(problems)
    if errs:
        print(f"\n{len(errs)} error(s); backlog is not safe to ship.", file=sys.stderr)
        return 1
    if problems:
        print(f"\n{len(problems)} warning(s); no errors.", file=sys.stderr)
    else:
        print("backlog is clean.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
