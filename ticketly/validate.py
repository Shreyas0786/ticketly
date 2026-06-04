"""Backlog integrity checks beyond JSON-schema validation.

The schema guarantees each ticket's *shape*. This module guarantees the backlog
hangs together as a whole: no duplicate IDs, no dependency pointing at a ticket
that doesn't exist, no ticket depending on itself, every Task parented to a real
Epic, epics sized at 0, no circular dependencies, and (the guardrail) every Task
carrying acceptance criteria unless it is explicitly flagged for clarification.

Problems are tagged ``error`` (the backlog is broken — rendering aborts) or
``warning`` (worth a look — e.g. likely duplicate tickets — but not fatal).

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
from pathlib import Path
from typing import Any


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
    data = json.loads(Path(args.backlog).read_text())
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
