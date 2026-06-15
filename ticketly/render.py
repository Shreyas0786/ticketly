"""Render a validated Ticketly backlog to Markdown and CSV.

Deterministic, no model calls. A backlog JSON (conforming to
``schema/ticket.schema.json``) goes in; review-ready Markdown and
tracker-importable CSV come out. Validation always runs first, so a
malformed backlog fails loudly instead of producing junk output.

Usage:
    python -m ticketly.render BACKLOG.json --format core --out-dir ticketly/
    python -m ticketly.render BACKLOG.json --format notion --out-dir ticketly/
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from ticketly import validate as integrity
from ticketly.home import TICKET_SCHEMA as SCHEMA_PATH


class BacklogIntegrityError(ValueError):
    """Raised when a backlog is schema-valid but does not hang together
    (dangling/circular deps, orphan parents, duplicate ids, ...)."""

    def __init__(self, problems: list[integrity.Problem]):
        self.problems = problems
        joined = "\n".join(f"  - {p}" for p in problems)
        super().__init__(f"backlog has {len(problems)} integrity error(s):\n{joined}")

# CSV columns, in order. One row per ticket; list fields are joined with "; ".
CSV_COLUMNS = [
    "id",
    "title",
    "type",
    "parent",
    "status",
    "effort",
    "dependencies",
    "description",
    "acceptance_criteria",
    "needs_clarification",
    "assignee",
]

_LIST_FIELDS = {"dependencies", "acceptance_criteria"}


def load_schema() -> dict[str, Any]:
    """Load the ticket backlog schema."""
    return json.loads(SCHEMA_PATH.read_text())


def load_backlog(path: str | Path) -> dict[str, Any]:
    """Load, schema-validate, and integrity-check a backlog file.

    Raises ValidationError on a schema violation and BacklogIntegrityError on a
    structural problem (dangling/circular deps, orphan parent, duplicate id, ...).
    Integrity warnings are returned to the caller via ``check_backlog`` instead.
    """
    data = json.loads(Path(path).read_text())
    validate_backlog(data)
    problems = integrity.check_integrity(data)
    errs = integrity.errors(problems)
    if errs:
        raise BacklogIntegrityError(errs)
    return data


def validate_backlog(data: dict[str, Any]) -> None:
    """Validate a backlog dict against the schema. Raises ValidationError."""
    Draft202012Validator(load_schema()).validate(data)


def _epics(tickets: list[dict]) -> list[dict]:
    return [t for t in tickets if t["type"] == "Epic"]


def _tasks_for(epic_id: str, tickets: list[dict]) -> list[dict]:
    return [t for t in tickets if t["type"] == "Task" and t.get("parent") == epic_id]


def _orphan_tasks(tickets: list[dict]) -> list[dict]:
    epic_ids = {t["id"] for t in tickets if t["type"] == "Epic"}
    return [
        t
        for t in tickets
        if t["type"] == "Task" and t.get("parent") not in epic_ids
    ]


def _cell(value: Any, field: str) -> str:
    """Format a ticket field for a CSV cell."""
    if field in _LIST_FIELDS:
        return "; ".join(value or [])
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def render_csv(data: dict[str, Any]) -> str:
    """Render the backlog as CSV (one row per ticket)."""
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(CSV_COLUMNS)
    for t in data["tickets"]:
        writer.writerow([_cell(t.get(col), col) for col in CSV_COLUMNS])
    return buf.getvalue()


# Notion-import CSV. Notion makes the FIRST column the page title, so "Name"
# (the ticket title) leads. Dependencies are comma-separated so Notion can turn
# the column into a multi-select; acceptance criteria are newline-separated so
# each reads as its own line in the imported text property.
NOTION_COLUMNS: list[tuple[str, Any]] = [
    ("Name", lambda t: t["title"]),
    ("ID", lambda t: t["id"]),
    ("Type", lambda t: t["type"]),
    ("Status", lambda t: t["status"]),
    ("Effort", lambda t: "" if t["type"] == "Epic" else str(t["effort"])),
    ("Epic", lambda t: t.get("parent") or ""),
    ("Dependencies", lambda t: ", ".join(t.get("dependencies") or [])),
    ("Needs Clarification", lambda t: "Yes" if t.get("needs_clarification") else "No"),
    ("Description", lambda t: t.get("description") or ""),
    ("Acceptance Criteria", lambda t: "\n".join(t.get("acceptance_criteria") or [])),
    ("Assignee", lambda t: t.get("assignee") or ""),
    ("Due Date", lambda t: t.get("due_date") or ""),
    ("Priority", lambda t: t.get("priority") or ""),
]


def render_notion_csv(data: dict[str, Any]) -> str:
    """Render the backlog as a Notion-import CSV (one row per ticket)."""
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow([header for header, _ in NOTION_COLUMNS])
    for t in data["tickets"]:
        writer.writerow([fn(t) for _, fn in NOTION_COLUMNS])
    return buf.getvalue()


def _deps(ticket: dict) -> str:
    return ", ".join(ticket.get("dependencies") or []) or "—"


def _md_task_row(t: dict) -> str:
    flag = " ⚠️" if t.get("needs_clarification") else ""
    return (
        f"| {t['id']} | {t['title']}{flag} | {t['effort']} "
        f"| {_deps(t)} | {t['status']} |"
    )


def _md_epic_section(epic: dict, tickets: list[dict]) -> list[str]:
    lines = [f"## {epic['id']} — {epic['title']}", "", epic["description"], ""]
    tasks = _tasks_for(epic["id"], tickets)
    if not tasks:
        lines += ["_No child tickets yet._", ""]
        return lines
    lines += [
        "| ID | Title | Effort | Dependencies | Status |",
        "| --- | --- | --- | --- | --- |",
    ]
    lines += [_md_task_row(t) for t in tasks]
    lines.append("")
    for t in tasks:
        if t.get("acceptance_criteria"):
            lines.append(f"**{t['id']} acceptance criteria**")
            lines += [f"- {c}" for c in t["acceptance_criteria"]]
            lines.append("")
    return lines


def _count(n: int, noun: str) -> str:
    return f"{n} {noun}" if n == 1 else f"{n} {noun}s"


# Epic size buckets, keyed on summed child effort (Fibonacci points). We say the
# size in words — a non-technical reader gets the scale without learning story
# points, and we never claim a number of weeks the engine can't actually know.
_SIZE_SMALL_MAX = 5
_SIZE_MEDIUM_MAX = 15


def _size_word(points: int) -> str:
    if points <= _SIZE_SMALL_MAX:
        return "small"
    if points <= _SIZE_MEDIUM_MAX:
        return "medium"
    return "large"


# Priority is optional and hidden by default. When it's absent this ranks every
# ticket the same, so the start order stays driven purely by dependencies.
_PRIORITY_RANK = {"High": 0, "Medium": 1, "Low": 2}


def _md_your_plan(tickets: list[dict]) -> list[str]:
    """A plain-language overview above the detailed sections: where to start,
    what's doable now vs. later, and how big each area is. Deterministic."""
    order = integrity.build_order(tickets)
    if not order:  # no Tasks, or a cycle (an integrity error caught upstream)
        return []
    titles = {t["id"]: t["title"] for t in tickets}
    pos = {tid: i for i, tid in enumerate(order)}
    by_id = {t["id"]: t for t in tickets if t["type"] == "Task"}
    task_ids = set(by_id)

    def task_deps(t: dict) -> list[str]:
        return [d for d in t.get("dependencies", []) if d in task_ids and d != t["id"]]

    # Build order first; then float High-priority tickets up. With no priority
    # set anywhere, _PRIORITY_RANK.get(...) is constant and this is pure order.
    def sort_key(tid: str) -> tuple[int, int]:
        return (_PRIORITY_RANK.get(by_id[tid].get("priority"), 1), pos[tid])

    start_now = sorted([tid for tid in order if not task_deps(by_id[tid])], key=sort_key)
    started = set(start_now)
    later = [tid for tid in order if tid not in started]  # keeps dependency order

    lines = ["## Your plan", ""]
    if start_now:
        first = start_now[0]
        lines += [f"**Where to start:** {first} — {titles[first]}.", ""]
        lines += ["**Start today** — nothing is blocking these:", ""]
        lines += [f"- {tid} — {titles[tid]}" for tid in start_now]
        lines.append("")
    if later:
        lines += ["**Comes after** — each of these waits on something above:", ""]
        for tid in later:
            waits = ", ".join(task_deps(by_id[tid]))
            lines.append(f"- {tid} — {titles[tid]} (waits on {waits})")
        lines.append("")

    epics = _epics(tickets)
    if epics:
        lines += ["**How big each area is:**", ""]
        for epic in epics:
            child = _tasks_for(epic["id"], tickets)
            points = sum(t["effort"] for t in child)
            lines.append(
                f"- {epic['id']} — {epic['title']}: {_size_word(points)} "
                f"({_count(len(child), 'ticket')})"
            )
        lines.append("")
    return lines


def render_markdown(data: dict[str, Any]) -> str:
    """Render the backlog as a review-ready Markdown document."""
    tickets = data["tickets"]
    n_tasks = sum(1 for t in tickets if t["type"] == "Task")
    total_points = sum(t["effort"] for t in tickets if t["type"] == "Task")
    # Company is optional (omitted on existing-project runs); title by project alone then.
    company = data.get("company")
    title = f"{company} — {data['project']} backlog" if company else f"{data['project']} backlog"
    lines = [
        f"# {title}",
        "",
        f"{_count(len(_epics(tickets)), 'epic')} · "
        f"{_count(n_tasks, 'ticket')} · "
        f"{_count(total_points, 'point')}",
        "",
    ]
    lines += _md_your_plan(tickets)
    for epic in _epics(tickets):
        lines += _md_epic_section(epic, tickets)

    orphans = _orphan_tasks(tickets)
    if orphans:
        lines += ["## Unassigned tickets", ""]
        lines += [
            "| ID | Title | Effort | Dependencies | Status |",
            "| --- | --- | --- | --- | --- |",
        ]
        lines += [_md_task_row(t) for t in orphans]
        lines.append("")

    lines += _md_build_order(tickets)

    return "\n".join(lines).rstrip() + "\n"


def _md_build_order(tickets: list[dict]) -> list[str]:
    """A 'Build order' section: Tasks topologically sorted by dependency."""
    order = integrity.build_order(tickets)
    if not order:  # empty backlog or a cycle (the latter is an integrity error)
        return []
    titles = {t["id"]: t["title"] for t in tickets}
    lines = ["## Build order", "", "Work tickets top to bottom; each ticket's dependencies come before it.", ""]
    lines += [f"{i}. {tid} — {titles[tid]}" for i, tid in enumerate(order, 1)]
    lines.append("")
    return lines


def _tasks_md_marker(t: dict) -> str:
    """Trailing markers on a task line: in-progress, then needs-clarification."""
    bits = ""
    if t["status"] == "In Progress":
        bits += " 🚧"
    if t.get("needs_clarification"):
        bits += " ⚠️"
    return bits


def _tasks_md_block(t: dict) -> list[str]:
    """One checklist entry: a checkbox line anchored on the bold ticket id, an
    effort/dependencies line, then the acceptance criteria as plain sub-bullets."""
    box = "x" if t["status"] == "Done" else " "
    deps = ", ".join(t.get("dependencies") or []) or "nothing"
    lines = [
        f"- [{box}] **{t['id']} — {t['title']}**{_tasks_md_marker(t)}",
        f"  - Effort {t['effort']} · Depends on: {deps}",
    ]
    lines += [f"  - {c}" for c in t.get("acceptance_criteria") or []]
    return lines


def render_tasks_md(data: dict[str, Any]) -> str:
    """Render the backlog as an agent-ready task checklist, grouped by epic.

    One checkbox per Task — `Done` → ``- [x]``, otherwise ``- [ ]`` (an in-progress
    ticket keeps its box open and gains a 🚧 marker). Each line is anchored on its
    bold ticket id so an agent (or, later, the tracker app) can read this file AND
    flip the boxes as work completes: this file is the status source of truth.

    Tickets are grouped under their epic, and ordered within each epic by
    dependency (topological) so the list still reads safely top to bottom.
    """
    tickets = data["tickets"]
    order = integrity.build_order(tickets)
    pos = {tid: i for i, tid in enumerate(order)}

    def in_dep_order(tasks: list[dict]) -> list[dict]:
        return sorted(tasks, key=lambda t: pos.get(t["id"], len(order)))

    company = data.get("company")
    project = data["project"]
    title = f"{company} — {project} tasks" if company else f"{project} tasks"
    lines = [
        f"# {title}",
        "",
        "> Check a box when a ticket's acceptance criteria are all met.",
        "> Each ticket shows what it depends on — don't start one until its deps are done.",
        "",
    ]

    for epic in _epics(tickets):
        children = _tasks_for(epic["id"], tickets)
        if not children:  # a work checklist skips epics with nothing to do
            continue
        lines += [f"## {epic['id']} — {epic['title']}", ""]
        for t in in_dep_order(children):
            lines += _tasks_md_block(t)
        lines.append("")

    orphans = _orphan_tasks(tickets)
    if orphans:
        lines += ["## Unassigned", ""]
        for t in in_dep_order(orphans):
            lines += _tasks_md_block(t)
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ticketly.render",
        description="Validate a Ticketly backlog and render it to Markdown and/or CSV.",
    )
    parser.add_argument("backlog", help="Path to a backlog JSON file.")
    parser.add_argument(
        "--format",
        choices=["md", "csv", "notion", "tasks", "core", "both", "all"],
        default="core",
        help="Output format(s): single (md, csv, notion, tasks) or a set — "
        "core (md+csv+tasks), both (md+csv), all (everything). Default: core.",
    )
    parser.add_argument(
        "--out-dir",
        default=None,
        help="Directory to write the exports into (e.g. ticketly/): "
        "backlog.md, backlog.csv, tasks.md, backlog.notion.csv. "
        "If omitted, output is printed to stdout.",
    )
    return parser


# Each format key maps to (output filename, renderer). Filenames are fixed — one
# project per folder, so the project name lives in the folder, not the filename.
_RENDERERS: dict[str, tuple[str, Any]] = {
    "md": ("backlog.md", render_markdown),
    "csv": ("backlog.csv", render_csv),
    "notion": ("backlog.notion.csv", render_notion_csv),
    "tasks": ("tasks.md", render_tasks_md),
}

# Set formats expand to several single keys (kept in a stable, readable order).
_FORMAT_SETS: dict[str, list[str]] = {
    "core": ["md", "csv", "tasks"],
    "both": ["md", "csv"],
    "all": ["md", "csv", "notion", "tasks"],
}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    data = load_backlog(args.backlog)

    # load_backlog already aborts on integrity *errors*; surface any warnings.
    for w in integrity.warnings(integrity.check_integrity(data)):
        print(w, file=sys.stderr)

    keys = _FORMAT_SETS.get(args.format, [args.format])

    if args.out_dir is None:
        for i, key in enumerate(keys):
            if i:
                print()
            print(_RENDERERS[key][1](data), end="")
        return 0

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for key in keys:
        filename, renderer = _RENDERERS[key]
        path = out_dir / filename
        path.write_text(renderer(data))
        print(f"wrote {path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
