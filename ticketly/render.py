"""Render a validated Ticketly backlog to Markdown and CSV.

Deterministic, no model calls. A backlog JSON (conforming to
``schema/ticket.schema.json``) goes in; review-ready Markdown and
tracker-importable CSV come out. Validation always runs first, so a
malformed backlog fails loudly instead of producing junk output.

Both CSV layouts (standard and Notion) carry the estimate inputs and a per-row
export baseline, so an edited copy can come back through ``ticketly import``.
Points shown in a CSV are exported values; Ticketly recalculates them on import.

Usage:
    python -m ticketly.render BACKLOG.json --format core --out-dir ticketly/
    python -m ticketly.render BACKLOG.json --format notion --out-dir ticketly/
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from jsonschema import Draft202012Validator, ValidationError

from ticketly import baseline as bl
from ticketly import estimate as est
from ticketly import validate as integrity
from ticketly.home import TICKET_SCHEMA as SCHEMA_PATH


class BacklogIntegrityError(ValueError):
    """Raised when a backlog is schema-valid but does not hang together
    (dangling/circular deps, orphan parents, duplicate ids, ...)."""

    def __init__(self, problems: list[integrity.Problem]):
        self.problems = problems
        joined = "\n".join(f"  - {p}" for p in problems)
        super().__init__(f"backlog has {len(problems)} integrity error(s):\n{joined}")


# Standard CSV columns, in order. One row per ticket; list fields are joined with
# "; ". The first eleven are the original columns, unchanged and in place; the
# estimation and tracking columns are appended after them.
LEGACY_CSV_COLUMNS = [
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
CSV_COLUMNS = LEGACY_CSV_COLUMNS + [
    "estimation_model",
    "estimated_hours",
    "hours_implementation",
    "hours_testing",
    "hours_self_review",
    "hours_handoff",
    "difficulty_level",
    "difficulty_reason",
    "estimate_confidence",
    "rubric_version",
    "work_kind",
    "split_from",
    "split_scope",
    "legacy_model",
    "legacy_effort",
    "points_total",
    "hours_total",
    "points_total_partial",
    "due_date",
    "priority",
    "change_reason",
    "ticketly_baseline",
]

_LIST_FIELDS = {"dependencies", "acceptance_criteria"}

# Notion-import CSV. Notion makes the FIRST column the page title, so "Name"
# (the ticket title) leads. Dependencies are comma-separated so Notion can turn
# the column into a multi-select; acceptance criteria are newline-separated so
# each reads as its own line in the imported text property. Each header maps to
# the logical field it carries; the original thirteen come first, unchanged.
NOTION_COLUMNS: list[tuple[str, str]] = [
    ("Name", "title"),
    ("ID", "id"),
    ("Type", "type"),
    ("Status", "status"),
    ("Effort", "effort"),
    ("Epic", "parent"),
    ("Dependencies", "dependencies"),
    ("Needs Clarification", "needs_clarification"),
    ("Description", "description"),
    ("Acceptance Criteria", "acceptance_criteria"),
    ("Assignee", "assignee"),
    ("Due Date", "due_date"),
    ("Priority", "priority"),
    ("Estimation Model", "estimation_model"),
    ("Estimated Hours", "estimated_hours"),
    ("Implementation Hours", "hours_implementation"),
    ("Testing Hours", "hours_testing"),
    ("Self-Review Hours", "hours_self_review"),
    ("Handoff Hours", "hours_handoff"),
    ("Difficulty Level", "difficulty_level"),
    ("Difficulty Reason", "difficulty_reason"),
    ("Confidence", "estimate_confidence"),
    ("Rubric", "rubric_version"),
    ("Work Kind", "work_kind"),
    ("Split From", "split_from"),
    ("Split Scope", "split_scope"),
    ("Legacy Model", "legacy_model"),
    ("Legacy Points", "legacy_effort"),
    ("Points Total", "points_total"),
    ("Hours Total", "hours_total"),
    ("Total Partial", "points_total_partial"),
    ("Change Reason", "change_reason"),
    ("Ticketly Baseline", "ticketly_baseline"),
]
LEGACY_NOTION_HEADERS = [h for h, _ in NOTION_COLUMNS[:13]]

# Each export layout: (header, logical field) in column order.
LAYOUTS: dict[str, list[tuple[str, str]]] = {
    "standard": [(c, c) for c in CSV_COLUMNS],
    "notion": NOTION_COLUMNS,
}
BASELINE_KEY = "ticketly_baseline"
REASON_KEY = "change_reason"


def hashed_keys(layout: str) -> list[str]:
    """Fields covered by a row's baseline token, in column order."""
    return [k for _, k in LAYOUTS[layout] if k not in (BASELINE_KEY, REASON_KEY)]


def load_schema() -> dict[str, Any]:
    """Load the ticket backlog schema."""
    return json.loads(SCHEMA_PATH.read_text())


def load_backlog(path: str | Path) -> dict[str, Any]:
    """Load, schema-validate, and integrity-check a backlog file.

    Raises ValidationError on a schema violation and BacklogIntegrityError on a
    structural problem (dangling/circular deps, orphan parent, duplicate id, ...).
    Integrity warnings are returned to the caller via ``check_backlog`` instead.
    """
    data = integrity.read_json(path)
    validate_backlog(data)
    problems = integrity.check_integrity(data)
    errs = integrity.errors(problems)
    if errs:
        raise BacklogIntegrityError(errs)
    return data


def validate_backlog(data: dict[str, Any]) -> None:
    """Validate a backlog dict against the schema. Raises ValidationError.

    NaN and Infinity are refused first: JSON Schema's number checks can't judge them.
    """
    bad = integrity.non_finite_paths(data)
    if bad:
        raise ValidationError(f"{bad[0]}: not a finite number (NaN and Infinity aren't allowed)")
    Draft202012Validator(load_schema()).validate(data)


def save_backlog(path: str | Path, data: dict[str, Any]) -> None:
    """Validate a complete backlog, then replace the file atomically.

    Nothing is written unless the whole backlog passes the schema and has no
    integrity errors; the old file is swapped out in one ``os.replace``, so a
    crash never leaves a half-written backlog behind.
    """
    validate_backlog(data)
    errs = integrity.errors(integrity.check_integrity(data))
    if errs:
        raise BacklogIntegrityError(errs)
    path = Path(path)
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    fd, tmp = tempfile.mkstemp(prefix=".backlog-", suffix=".json", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _epics(tickets: list[dict]) -> list[dict]:
    return [t for t in tickets if t["type"] == "Epic"]


def _tasks(tickets: list[dict]) -> list[dict]:
    return [t for t in tickets if t["type"] == "Task"]


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


# --------------------------------------------------------------------------- #
# export cells (shared by both CSV layouts)
# --------------------------------------------------------------------------- #
@dataclass
class _Ctx:
    data: dict[str, Any]
    model: str
    epic_totals: dict[str, est.Totals]
    layout: str


def _context(data: dict[str, Any], layout: str) -> _Ctx:
    model = est.model_of(data)
    totals = {e["id"]: est.summarize(_tasks_for(e["id"], data["tickets"]), model)
              for e in _epics(data["tickets"])}
    return _Ctx(data, model, totals, layout)


def _bool_cell(value: bool, layout: str) -> str:
    if layout == "notion":
        return "Yes" if value else "No"
    return "true" if value else "false"


def _effort_cell(t: dict, ctx: _Ctx) -> str:
    if t["type"] == "Epic":
        # Epic effort stays 0 internally; its displayed total is a separate column.
        return "" if ctx.layout == "notion" else _cell(t.get("effort"), "effort")
    if ctx.model == est.MODEL_HOURS:
        if est.is_legacy_completed(t):
            return ""
        return est.fmt_points(t.get("effort"), ctx.model)
    return _cell(t.get("effort"), "effort")


def _estimate_cell(t: dict, key: str) -> str:
    estimate = t.get("estimate") or {}
    if not estimate:
        return ""
    if key == "estimated_hours":
        return est.fmt_hours(estimate["estimated_hours"])
    if key.startswith("hours_") and key[6:] in est.BREAKDOWN_PARTS:
        return est.fmt_hours(estimate["hours_breakdown"][key[6:]])
    if key == "difficulty_level":
        return str(est.level_of(estimate["difficulty_level"]))
    return str(estimate.get(key) or "")


def export_cell(t: dict, key: str, ctx: _Ctx) -> str:
    """The text a CSV cell holds for one logical field of one ticket."""
    notion = ctx.layout == "notion"
    if key == "dependencies":
        return (", " if notion else "; ").join(t.get("dependencies") or [])
    if key == "acceptance_criteria":
        return ("\n" if notion else "; ").join(t.get("acceptance_criteria") or [])
    if key == "needs_clarification":
        return _bool_cell(bool(t.get("needs_clarification")), ctx.layout)
    if key == "effort":
        return _effort_cell(t, ctx)
    if key == "estimation_model":
        return ctx.model
    if key in ("estimated_hours", "difficulty_level", "difficulty_reason",
               "estimate_confidence", "rubric_version") or key.startswith("hours_"):
        if key == "hours_total":
            if t["type"] != "Epic" or ctx.model != est.MODEL_HOURS:
                return ""
            return est.fmt_hours(ctx.epic_totals[t["id"]].hours)
        return _estimate_cell(t, key)
    if key in ("split_from", "split_scope"):
        split = t.get("split_from") or {}
        return split.get("ticket" if key == "split_from" else "scope", "")
    if key in ("legacy_model", "legacy_effort"):
        legacy = est.last_legacy(t)
        if not legacy:
            return ""
        if key == "legacy_model":
            return legacy["model"]
        return "" if legacy["effort"] is None else est.fmt_points(legacy["effort"], legacy["model"])
    if key == "points_total":
        if t["type"] != "Epic":
            return ""
        return est.fmt_points(ctx.epic_totals[t["id"]].points, ctx.model)
    if key == "points_total_partial":
        if t["type"] != "Epic":
            return ""
        return _bool_cell(ctx.epic_totals[t["id"]].partial, ctx.layout)
    if key in (REASON_KEY, BASELINE_KEY):
        return ""
    if key == "parent":
        return t.get("parent") or ""
    return _cell(t.get(key), key)


def export_rows(data: dict[str, Any], layout: str) -> list[list[str]]:
    """Header plus one row per ticket, each row ending with its baseline token."""
    ctx = _context(data, layout)
    columns = LAYOUTS[layout]
    exp_id = bl.export_id(data)
    rows = [[header for header, _ in columns]]
    for t in data["tickets"]:
        cells = {key: export_cell(t, key, ctx) for _, key in columns}
        cells[BASELINE_KEY] = bl.make_token(
            layout, exp_id, t["id"], [(k, cells[k]) for k in hashed_keys(layout)])
        rows.append([cells[key] for _, key in columns])
    return rows


def _write_rows(rows: list[list[str]]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerows(rows)
    return buf.getvalue()


def render_csv(data: dict[str, Any]) -> str:
    """Render the backlog as CSV (one row per ticket)."""
    return _write_rows(export_rows(data, "standard"))


def render_notion_csv(data: dict[str, Any]) -> str:
    """Render the backlog as a Notion-import CSV (one row per ticket)."""
    return _write_rows(export_rows(data, "notion"))


# --------------------------------------------------------------------------- #
# Markdown
# --------------------------------------------------------------------------- #
def _deps(ticket: dict) -> str:
    return ", ".join(ticket.get("dependencies") or []) or "—"


def _kind_tag(t: dict) -> str:
    kind = t.get("work_kind")
    return f" _({est.WORK_KIND_LABELS[kind].lower()})_" if kind else ""


def _md_task_row(t: dict) -> str:
    flag = " ⚠️" if t.get("needs_clarification") else ""
    return (
        f"| {t['id']} | {t['title']}{flag}{_kind_tag(t)} | {t['effort']} "
        f"| {_deps(t)} | {t['status']} |"
    )


_HOURS_TABLE_HEAD = [
    "| ID | Title | Owner | Standard hours | Level | Points | Confidence | Dependencies | Status |",
    "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
]


def _md_hours_row(t: dict) -> str:
    flag = " ⚠️" if t.get("needs_clarification") else ""
    estimate = t.get("estimate") or {}
    if est.is_legacy_completed(t):
        legacy = est.last_legacy(t)
        points = f"Legacy {est.fmt_points(legacy['effort'], legacy['model'])}"
    else:
        points = est.fmt_points(t.get("effort"), est.MODEL_HOURS)
    hours = est.fmt_hours(estimate["estimated_hours"]) if estimate else "—"
    level = str(est.level_of(estimate["difficulty_level"])) if estimate else "—"
    confidence = estimate.get("estimate_confidence", "—") if estimate else "—"
    return (
        f"| {t['id']} | {t['title']}{flag}{_kind_tag(t)} | {t.get('assignee') or '—'} "
        f"| {hours} | {level} | {points} | {confidence} | {_deps(t)} | {t['status']} |"
    )


def _md_estimate_line(t: dict, data: dict[str, Any]) -> list[str]:
    """The hours-model basis for one Task: breakdown, level, points, confidence."""
    estimate = t.get("estimate")
    legacy = est.last_legacy(t)
    if est.is_legacy_completed(t):
        label = est.MODEL_LABELS[legacy["model"]]
        return [f"**{t['id']} estimate:** completed under {label} — "
                f"{est.fmt_points(legacy['effort'], legacy['model'])} legacy points, kept out of "
                "the hours-based totals.", ""]
    previously = ""
    if legacy and legacy.get("effort") is not None:
        previously = (f" Previously {est.fmt_points(legacy['effort'], legacy['model'])} "
                      f"{est.MODEL_LABELS[legacy['model']]} (legacy).")
    if not estimate:
        return [f"**{t['id']} estimate:** Unestimated.{previously}", ""]
    parts = estimate["hours_breakdown"]
    level = est.level_of(estimate["difficulty_level"])
    rubric = est.rubric_for(data, estimate["rubric_version"])
    breakdown = " + ".join(
        f"{est.fmt_hours(parts[p])} {p.replace('_', '-')}" for p in est.BREAKDOWN_PARTS)
    return [
        f"**{t['id']} estimate:** {breakdown} = {est.fmt_hours(estimate['estimated_hours'])} "
        f"standard hours · level {level} {est.LEVEL_NAMES[level]} (×{rubric[str(level)]}) "
        f"= {est.fmt_points(t.get('effort'), est.MODEL_HOURS)} points · confidence "
        f"{estimate['estimate_confidence']}. Reason: {estimate['difficulty_reason']}{previously}",
        "",
    ]


def _md_split_line(t: dict) -> list[str]:
    split = t.get("split_from")
    if not split:
        return []
    if split["scope"] == "replaced":
        text = f"takes over scope from {split['ticket']} (its estimate was reduced to match)"
    else:
        approved = f", approved by {split['approved_by']}" if split.get("approved_by") else ""
        text = f"adds new scope alongside {split['ticket']}{approved}"
    return [f"**{t['id']} split:** {text} — {split['reason']}", ""]


def _md_epic_section(epic: dict, tickets: list[dict], data: dict[str, Any] | None = None) -> list[str]:
    data = data if data is not None else {"tickets": tickets}
    model = est.model_of(data)
    lines = [f"## {epic['id']} — {epic['title']}", "", epic["description"], ""]
    tasks = _tasks_for(epic["id"], tickets)
    if not tasks:
        lines += ["_No child tickets yet._", ""]
        return lines
    tot = est.summarize(tasks, model)
    lines += [f"**Total:** {est.describe_totals(tot, model)}{_legacy_note(tot)}", ""]
    if model == est.MODEL_HOURS:
        lines += _HOURS_TABLE_HEAD
        lines += [_md_hours_row(t) for t in tasks]
    else:
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
        if model == est.MODEL_HOURS:
            lines += _md_estimate_line(t, data)
        lines += _md_split_line(t)
    return lines


def _legacy_note(tot: est.Totals) -> str:
    if not tot.legacy_points:
        return ""
    parts = [f"{est.fmt_points(v, m)} {est.MODEL_LABELS[m]}" for m, v in sorted(tot.legacy_points.items())]
    return f" · legacy: {', '.join(parts)} (separate, not added)"


def _count(n: int, noun: str) -> str:
    return f"{n} {noun}" if n == 1 else f"{n} {noun}s"


# Epic size buckets, keyed on summed child effort (Fibonacci points). We say the
# size in words — a non-technical reader gets the scale without learning story
# points, and we never claim a number of weeks the engine can't actually know.
# The hours model shows its points and standard hours instead of size words.
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


def _md_your_plan(tickets: list[dict], model: str = est.MODEL_FIBONACCI) -> list[str]:
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
        lines += [f"**Where to start:** {first} - {titles[first]}.", ""]
        lines += ["**Start today** — nothing is blocking these:", ""]
        lines += [f"- {tid} - {titles[tid]}" for tid in start_now]
        lines.append("")
    if later:
        lines += ["**Comes after** — each of these waits on something above:", ""]
        for tid in later:
            waits = ", ".join(task_deps(by_id[tid]))
            lines.append(f"- {tid} - {titles[tid]} (waits on {waits})")
        lines.append("")

    epics = _epics(tickets)
    if epics:
        lines += ["**How big each area is:**", ""]
        for epic in epics:
            child = _tasks_for(epic["id"], tickets)
            if model == est.MODEL_HOURS:
                tot = est.summarize(child, model)
                partial = f", {tot.unestimated} unestimated" if tot.partial else ""
                lines.append(
                    f"- {epic['id']} - {epic['title']}: {est.fmt_points(tot.points, model)} points "
                    f"· {est.fmt_hours(tot.hours)} standard hours "
                    f"({_count(len(child), 'ticket')}{partial})")
                continue
            points = sum(t["effort"] for t in child)
            lines.append(
                f"- {epic['id']} - {epic['title']}: {_size_word(points)} "
                f"({_count(len(child), 'ticket')})"
            )
        lines.append("")
    return lines


def _md_estimation_lines(data: dict[str, Any], tasks: list[dict]) -> list[str]:
    model = est.model_of(data)
    if model == est.MODEL_HOURS:
        version = est.current_rubric_version(data)
        rubric = est.rubric_for(data, version)
        levels = ", ".join(f"{lvl} ×{rubric[str(lvl)]}" for lvl in range(1, 5))
        lines = [
            f"**Estimation:** {est.MODEL_LABELS[model]} (rubric {version}: level {levels}). "
            "One point is one standard hour at level 1; points are difficulty-weighted, "
            "not elapsed hours.",
            "",
        ]
    else:
        lines = [f"**Estimation:** {est.MODEL_LABELS[model]} (1, 2, 3, 5, 8, 13).", ""]
    tot = est.summarize(tasks, model)
    for legacy_model, points in sorted(tot.legacy_points.items()):
        lines += [
            f"**Legacy {est.MODEL_LABELS[legacy_model]}:** "
            f"{est.fmt_points(points, legacy_model)} points across "
            f"{_count(tot.legacy_tickets, 'ticket')} "
            f"({tot.legacy_completed} completed before the switch). Kept separate — never "
            "added to the totals above.",
            "",
        ]
    return lines


def _md_team_totals(tasks: list[dict], model: str) -> list[str]:
    """Per person: what they own (assigned) versus what is Done, hours and points apart."""
    if not any(t.get("assignee") or (est.last_legacy(t) or {}).get("assignee") for t in tasks):
        return []
    counted = [t for t in tasks if not est.is_legacy_completed(t)]
    lines = ["## Team totals", ""]
    if model == est.MODEL_HOURS:
        lines += [
            "| Person | Assigned | Assigned hours | Assigned points | Done | Done hours | Done points |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    else:
        lines += [
            "| Person | Assigned | Assigned points | Done | Done points |",
            "| --- | --- | --- | --- | --- |",
        ]

    def pts(tot: est.Totals) -> str:
        text = est.fmt_points(tot.points, model)
        return f"{text} (partial)" if tot.partial else text

    for person, assigned, done in est.person_totals(counted, model):
        if model == est.MODEL_HOURS:
            lines.append(
                f"| {person} | {assigned.tickets} | {est.fmt_hours(assigned.hours)} | {pts(assigned)} "
                f"| {done.tickets} | {est.fmt_hours(done.hours)} | {pts(done)} |")
        else:
            lines.append(
                f"| {person} | {assigned.tickets} | {pts(assigned)} | {done.tickets} | {pts(done)} |")
    lines += [
        "",
        "Assigned counts every ticket a person owns, finished or not; Done counts only work "
        "that was reviewed and meets its acceptance criteria. Standard hours are estimates, "
        "not time logged.",
        "",
    ]
    legacy_rows = est.legacy_completed_by_person(tasks)
    if legacy_rows:
        lines += [
            "**Completed under the previous model** (legacy points, kept separate, credited to "
            "the owner recorded at the switch):",
            "",
            "| Person | Tickets | Legacy points |",
            "| --- | --- | --- |",
        ]
        for person, count, points in legacy_rows:
            shown = ", ".join(f"{est.fmt_points(v, m)} {est.MODEL_LABELS[m]}"
                              for m, v in sorted(points.items())) or "—"
            lines.append(f"| {person} | {count} | {shown} |")
        lines.append("")
    return lines


def _md_explicit_work(tasks: list[dict], model: str) -> list[str]:
    """Substantial cleanup, integration, client preparation and investigation,
    counted as their own tasks."""
    kinds = [k for k in est.WORK_KINDS if any(t.get("work_kind") == k for t in tasks)]
    if not kinds:
        return []
    lines = ["## Explicit work", ""]
    if model == est.MODEL_HOURS:
        lines += ["| Kind | Tickets | Standard hours | Points |", "| --- | --- | --- | --- |"]
    else:
        lines += ["| Kind | Tickets | Points |", "| --- | --- | --- |"]
    for kind in kinds:
        tot = est.summarize([t for t in tasks if t.get("work_kind") == kind], model)
        points = est.fmt_points(tot.points, model) + (" (partial)" if tot.partial else "")
        label = est.WORK_KIND_LABELS[kind]
        if model == est.MODEL_HOURS:
            lines.append(f"| {label} | {tot.tickets} | {est.fmt_hours(tot.hours)} | {points} |")
        else:
            lines.append(f"| {label} | {tot.tickets} | {points} |")
    lines.append("")
    return lines


def render_markdown(data: dict[str, Any]) -> str:
    """Render the backlog as a review-ready Markdown document."""
    tickets = data["tickets"]
    model = est.model_of(data)
    tasks = _tasks(tickets)
    totals = est.summarize(tasks, model)
    # Company is optional (omitted on existing-project runs); title by project alone then.
    company = data.get("company")
    title = f"{company} — {data['project']} backlog" if company else f"{data['project']} backlog"
    lines = [
        f"# {title}",
        "",
        f"{_count(len(_epics(tickets)), 'epic')} · "
        f"{_count(len(tasks), 'ticket')} · "
        f"{est.describe_totals(totals, model)}",
        "",
    ]
    lines += _md_estimation_lines(data, tasks)
    lines += _md_your_plan(tickets, model)
    for epic in _epics(tickets):
        lines += _md_epic_section(epic, tickets, data)

    orphans = _orphan_tasks(tickets)
    if orphans:
        lines += ["## Unassigned tickets", ""]
        if model == est.MODEL_HOURS:
            lines += _HOURS_TABLE_HEAD
            lines += [_md_hours_row(t) for t in orphans]
        else:
            lines += [
                "| ID | Title | Effort | Dependencies | Status |",
                "| --- | --- | --- | --- | --- |",
            ]
            lines += [_md_task_row(t) for t in orphans]
        lines.append("")

    lines += _md_team_totals(tasks, model)
    lines += _md_explicit_work(tasks, model)
    lines += _md_build_order(tickets)

    return "\n".join(lines).rstrip() + "\n"


def _md_build_order(tickets: list[dict]) -> list[str]:
    """A 'Build order' section: Tasks topologically sorted by dependency."""
    order = integrity.build_order(tickets)
    if not order:  # empty backlog or a cycle (the latter is an integrity error)
        return []
    titles = {t["id"]: t["title"] for t in tickets}
    lines = ["## Build order", "", "Work tickets top to bottom; each ticket's dependencies come before it.", ""]
    lines += [f"{i}. {tid} - {titles[tid]}" for i, tid in enumerate(order, 1)]
    lines.append("")
    return lines


# --------------------------------------------------------------------------- #
# tasks.md
# --------------------------------------------------------------------------- #
def _tasks_md_marker(t: dict) -> str:
    """Trailing markers on a task line: in-progress or in-review, then needs-clarification."""
    bits = ""
    if t["status"] == "In Progress":
        bits += " 🚧"
    if t["status"] == "In Review":
        bits += " 🔎"
    if t.get("needs_clarification"):
        bits += " ⚠️"
    return bits


def _tasks_md_size(t: dict, model: str) -> str:
    if model != est.MODEL_HOURS:
        return f"Effort {t['effort']}"
    if est.is_legacy_completed(t):
        legacy = est.last_legacy(t)
        return (f"Legacy {est.fmt_points(legacy['effort'], legacy['model'])} "
                f"{est.MODEL_LABELS[legacy['model']]} (completed before the switch)")
    estimate = t.get("estimate")
    if not estimate:
        return est.UNESTIMATED
    return (f"{est.fmt_points(t.get('effort'), model)} points "
            f"({est.fmt_hours(estimate['estimated_hours'])} standard hours, "
            f"level {est.level_of(estimate['difficulty_level'])})")


def _tasks_md_block(t: dict, model: str = est.MODEL_FIBONACCI) -> list[str]:
    """One checklist entry: a checkbox line anchored on the bold ticket id, an
    effort/dependencies line, then the acceptance criteria as plain sub-bullets."""
    box = "x" if t["status"] == "Done" else " "
    deps = ", ".join(t.get("dependencies") or []) or "nothing"
    owner = f" · Owner: {t['assignee']}" if t.get("assignee") else ""
    lines = [
        f"- [{box}] **{t['id']} - {t['title']}**{_tasks_md_marker(t)}",
        f"  - {_tasks_md_size(t, model)} · Depends on: {deps}{owner}",
    ]
    lines += [f"  - {c}" for c in t.get("acceptance_criteria") or []]
    return lines


def render_tasks_md(data: dict[str, Any]) -> str:
    """Render the backlog as an agent-ready task checklist, grouped by epic.

    One checkbox per Task — `Done` → ``- [x]``, otherwise ``- [ ]`` (an in-progress
    ticket keeps its box open and gains a 🚧 marker; one waiting for review gains
    🔎). Each line is anchored on its bold ticket id so an agent (or, later, the
    tracker app) can read this file AND flip the boxes as work completes.

    Tickets are grouped under their epic, and ordered within each epic by
    dependency (topological) so the list still reads safely top to bottom.
    """
    tickets = data["tickets"]
    model = est.model_of(data)
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
        "> Check a box only when the work has been reviewed and meets all its acceptance criteria.",
        "> Each ticket shows what it depends on — don't start one until its deps are done.",
        f"> Estimation: {est.MODEL_LABELS[model]}.",
        "",
    ]

    for epic in _epics(tickets):
        children = _tasks_for(epic["id"], tickets)
        if not children:  # a work checklist skips epics with nothing to do
            continue
        lines += [f"## {epic['id']} — {epic['title']}", ""]
        for t in in_dep_order(children):
            lines += _tasks_md_block(t, model)
        lines.append("")

    orphans = _orphan_tasks(tickets)
    if orphans:
        lines += ["## Unassigned", ""]
        for t in in_dep_order(orphans):
            lines += _tasks_md_block(t, model)
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
_RENDERERS: dict[str, tuple[str, Callable[[dict[str, Any]], str]]] = {
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
