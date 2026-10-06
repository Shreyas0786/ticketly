"""Import an edited CSV back into the backlog: validate, recalculate, record.

The round trip is::

    ticketly render ... --format csv|notion     export (each row carries a baseline)
    ... edit owners, status, estimate inputs in a spreadsheet or Notion ...
    ticketly import ticketly/backlog.csv --dry-run   preview, writes nothing
    ticketly import ticketly/backlog.csv             apply
    ticketly render ...                         re-export the recalculated backlog

Rules:

- Rows match tickets by their stable ID. Column order, a UTF-8 BOM, blank rows and
  unrelated extra columns (Notion adds some) are tolerated.
- Only these fields can change: assignee, status, due date, priority, and the
  estimate inputs (the hours breakdown, difficulty level and reason, confidence —
  or, on a Fibonacci backlog, the Fibonacci effort). A change of estimate needs a
  ``change_reason``. Everything else is protected; calculated fields (points,
  estimated hours, Epic totals) are recalculated. Edits to either are ignored
  with a warning.
- Each row's baseline tells an untouched stale value (ignored) from an edited one.
  An edit to a field that also changed in Ticketly since the export is a conflict.
- Invalid values, unknown or duplicate IDs, missing baselines and conflicts abort
  the whole import. Nothing is written unless the complete result validates, and
  then the backlog is replaced atomically. An import with nothing to change
  leaves the file untouched, so repeating an import is harmless.
"""

from __future__ import annotations

import argparse
import copy
import csv
import io
import json
import sys
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from ticketly import baseline as bl
from ticketly import estimate as est
from ticketly import render
from ticketly import validate as integrity

_PART_KEYS = {f"hours_{p}": p for p in est.BREAKDOWN_PARTS}
_ESTIMATE_INPUTS = [*_PART_KEYS, "difficulty_level", "difficulty_reason", "estimate_confidence"]
_SIMPLE_EDITABLE = ["assignee", "status", "due_date", "priority"]
_DERIVED = {"estimated_hours", "points_total", "hours_total", "points_total_partial",
            "estimation_model", "rubric_version", "legacy_model", "legacy_effort"}

DEFAULT_BACKLOG = "ticketly/.data/backlog.json"


class ImportAborted(Exception):
    """The import found errors; nothing was written."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("\n".join(errors))


@dataclass
class ImportReport:
    data: dict[str, Any]
    changed: bool = False
    changes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    stale_untouched: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# reading the CSV
# --------------------------------------------------------------------------- #
def _detect_layout(headers: list[str]) -> str:
    stripped = [h.strip() for h in headers]
    for layout, columns in render.LAYOUTS.items():
        baseline_header = next(h for h, k in columns if k == render.BASELINE_KEY)
        if baseline_header in stripped:
            return layout
    raise ImportAborted([
        "This CSV has no Ticketly baseline column ('ticketly_baseline' or 'Ticketly Baseline'), "
        "so Ticketly can't tell which values you edited. Export a fresh copy with "
        "`ticketly render ticketly/.data/backlog.json --format csv` (or `--format notion`), "
        "make your edits in that file, keep the baseline column, and import it again."
    ])


def read_csv(text: str) -> tuple[str, list[dict[str, str]], list[str]]:
    """(layout, rows keyed by logical field, ignored extra headers)."""
    text = text.lstrip("﻿")
    reader = csv.reader(io.StringIO(text))
    try:
        headers = next(reader)
    except StopIteration:
        raise ImportAborted(["the CSV is empty"]) from None
    layout = _detect_layout(headers)
    key_for = {h: k for h, k in render.LAYOUTS[layout]}
    index: dict[str, int] = {}
    extras: list[str] = []
    for i, raw in enumerate(headers):
        h = raw.strip()
        if h in key_for and key_for[h] not in index:
            index[key_for[h]] = i
        elif h:
            extras.append(h)
    if "id" not in index:
        id_header = next(h for h, k in render.LAYOUTS[layout] if k == "id")
        raise ImportAborted([f"the CSV has no '{id_header}' column to match rows to tickets"])
    rows = []
    for raw_row in reader:
        if not any(c.strip() for c in raw_row):
            continue  # blank row (Notion and spreadsheets add these)
        rows.append({k: (raw_row[i] if i < len(raw_row) else "") for k, i in index.items()})
    return layout, rows, extras


# --------------------------------------------------------------------------- #
# parsing editable values
# --------------------------------------------------------------------------- #
def _parse_simple(key: str, text: str) -> Any:
    text = " ".join(text.split())
    if key == "assignee":
        return text or None
    if key == "status":
        for s in est.STATUSES:
            if s.lower() == text.lower():
                return s
        raise ValueError(f"status {text!r} is not one of {', '.join(est.STATUSES)}")
    if key == "due_date":
        return bl.parse_date(text)
    if key == "priority":
        if not text:
            return None
        for p in ("High", "Medium", "Low"):
            if p.lower() == text.lower():
                return p
        raise ValueError(f"priority {text!r} is not High, Medium or Low")
    raise KeyError(key)


def _parse_hours(text: str, label: str) -> Decimal:
    try:
        value = est.dec(text)
    except est.EstimationError:
        raise ValueError(f"{label} {text!r} must be a finite number of hours, "
                         "in quarter hours (e.g. 1.25)") from None
    if not est.is_quarter_hour(value):
        raise ValueError(f"{label} {text!r} must be zero or more, in quarter hours (0.25)")
    return value


def _estimate_inputs(t: dict[str, Any]) -> dict[str, str]:
    """A ticket's current estimate inputs, as cell text."""
    return {k: render._estimate_cell(t, k) for k in _ESTIMATE_INPUTS}


def _build_estimate(values: dict[str, str], rubric_version: str) -> dict[str, Any] | None:
    """An estimate from cell text: all blank = Unestimated (None)."""
    filled = {k: " ".join(v.split()) for k, v in values.items()}
    if not any(filled.values()):
        return None
    missing = [k for k, v in filled.items() if not v]
    if missing:
        raise ValueError("incomplete estimate inputs, missing: " + ", ".join(missing)
                         + " (fill them all in, or clear them all to mark the task Unestimated)")
    parts = {p: _parse_hours(filled[k], k) for k, p in _PART_KEYS.items()}
    total = sum(parts.values(), Decimal(0))
    if total <= 0:
        raise ValueError("estimate inputs add up to 0 hours")
    try:
        level = est.level_of(filled["difficulty_level"])  # "2" and "2.0" are both level 2
    except est.EstimationError:
        raise ValueError(f"difficulty_level {filled['difficulty_level']!r} must be a whole "
                         "number from 1 to 4") from None
    confidence = filled["estimate_confidence"].lower()
    if confidence not in est.CONFIDENCE_LEVELS:
        raise ValueError(f"estimate_confidence {filled['estimate_confidence']!r} must be high, medium or low")
    return {
        "estimated_hours": est.json_number(total),
        "hours_breakdown": {p: est.json_number(v) for p, v in parts.items()},
        "difficulty_level": level,
        "difficulty_reason": filled["difficulty_reason"],
        "estimate_confidence": confidence,
        "rubric_version": rubric_version,
    }


# --------------------------------------------------------------------------- #
# the import
# --------------------------------------------------------------------------- #
def plan_import(data: dict[str, Any], csv_text: str, *, on: str) -> ImportReport:
    """Work out the complete result of an import without writing anything.

    ``data`` must be a valid backlog. Raises ImportAborted on any error; otherwise
    returns the proposed backlog (``report.changed`` False when there is nothing
    to apply).
    """
    layout, rows, extras = read_csv(csv_text)
    report = ImportReport(copy.deepcopy(data))
    if extras:
        report.warnings.append("ignored columns Ticketly doesn't use: " + ", ".join(extras))

    model = est.model_of(data)
    keys = render.hashed_keys(layout)
    ctx = render._context(data, layout)
    by_id = {t["id"]: t for t in data["tickets"]}
    errors: list[str] = []
    seen: set[str] = set()
    plans: list[tuple[dict[str, Any], dict[str, Any], str | None]] = []

    for n, row in enumerate(rows, start=2):  # header is line 1
        tid = row.get("id", "").strip()
        where = f"line {n}" + (f" ({tid})" if tid else "")
        if not tid:
            errors.append(f"{where}: no ticket ID — rows can't create tickets; add new work "
                          "through Ticketly and re-export")
            continue
        if tid in seen:
            errors.append(f"{where}: ticket {tid} appears more than once (was the CSV imported "
                          "into Notion twice?)")
            continue
        seen.add(tid)
        if tid not in by_id:
            errors.append(f"{where}: unknown ticket {tid}; rows can't create or rename tickets")
            continue
        try:
            base = bl.parse_token(row.get(render.BASELINE_KEY, ""), layout, len(keys))
        except bl.BaselineError as exc:
            errors.append(f"{where}: {exc}; re-export and edit the fresh file")
            continue
        if base.ticket_id != tid:
            errors.append(f"{where}: baseline belongs to {base.ticket_id}, not {tid}; "
                          "a row was copied or reordered across cells")
            continue

        t = by_id[tid]
        edits: dict[str, Any] = {}
        moved_keys: set[str] = set()
        stale = False
        for key, base_hash in zip(keys, base.hashes):
            if key not in row:
                continue  # column removed in the spreadsheet: nothing edited there
            csv_val = row[key]
            cur_val = render.export_cell(t, key, ctx)
            edited = bl.field_hash(key, csv_val) != base_hash
            moved = bl.field_hash(key, cur_val) != base_hash
            if moved:
                moved_keys.add(key)
            if not edited:
                # calculated values move whenever inputs elsewhere change; only report
                # stored fields that changed in Ticketly since the export
                calculated = key in _DERIVED or (key == "effort" and model == est.MODEL_HOURS)
                stale = stale or (moved and not calculated)
                continue
            if bl.canonical(key, csv_val) == bl.canonical(key, cur_val):
                continue  # already the current value (e.g. imported before)
            if not _is_editable(key, t, model):
                kind = "calculated" if key in _DERIVED or key == "effort" else "protected"
                report.warnings.append(
                    f"{where}: ignored edit to {kind} field '{key}' — Ticketly keeps "
                    f"{cur_val or '(blank)'!r}" + (", recalculated from the estimate inputs"
                                                    if kind == "calculated" else ""))
                continue
            if key in _ESTIMATE_INPUTS and est.is_legacy_completed(t):
                errors.append(f"{where}: '{key}' can't change — "
                              + est.completed_legacy_message(t).split(": ", 1)[1])
                continue
            if key in _SIMPLE_EDITABLE:
                try:
                    _parse_simple(key, csv_val)  # report bad values with the row errors
                except ValueError as exc:
                    errors.append(f"{where}: {exc}")
                    continue
            if moved:
                errors.append(f"{where}: '{key}' was edited in the CSV and also changed in "
                              f"Ticketly since this export (now {cur_val or '(blank)'!r}); "
                              "re-export and redo this edit")
                continue
            edits[key] = csv_val
        estimate_group = set(_ESTIMATE_INPUTS) | {"effort"}
        if edits.keys() & estimate_group and moved_keys & estimate_group:
            # estimate inputs are judged together: don't merge a CSV edit into an
            # estimate that was re-estimated in Ticketly after this export
            errors.append(f"{where}: the estimate was edited in the CSV and also re-estimated in "
                          "Ticketly since this export; re-export and redo the estimate edit")
            continue
        if stale and not edits:
            report.stale_untouched.append(tid)
        if edits:
            plans.append((t, edits, " ".join(row.get(render.REASON_KEY, "").split()) or None))

    if errors:
        raise ImportAborted(errors)
    if not plans:
        return report

    # Baseline untracked tasks first, so every change below has a "from".
    base = est.reconcile(report.data, on=on, source="import")
    if base.errors:
        raise ImportAborted(base.errors + [
            "the backlog has changes that were never recorded; run "
            "`ticketly recalc --reason ...` first, then import"])
    proposed = base.data
    new_by_id = {t["id"]: t for t in proposed["tickets"]}

    for original, edits, reason in plans:
        t = new_by_id[original["id"]]
        try:
            _apply_edits(t, edits, reason, model, proposed, on, report)
        except (ValueError, est.EstimationError) as exc:
            errors.append(f"{t['id']}: {exc}")
    if errors:
        raise ImportAborted(errors)
    if not report.changes:
        return report  # every edit turned out to be a no-op: leave the backlog alone

    final = est.reconcile(proposed, on=on, source="import")
    if final.errors:
        raise ImportAborted(final.errors)
    proposed = final.data
    render.validate_backlog(proposed)
    problems = integrity.errors(integrity.check_integrity(proposed))
    if problems:
        raise ImportAborted([str(p) for p in problems])
    report.data = proposed
    report.changed = True
    return report


def _is_editable(key: str, t: dict[str, Any], model: str) -> bool:
    if key in _SIMPLE_EDITABLE:
        return True
    if t["type"] != "Task":
        return False
    if model == est.MODEL_HOURS:
        return key in _ESTIMATE_INPUTS
    return key == "effort"


def _record(t: dict[str, Any], fld: str, before: Any, after: Any, reason: str | None,
            on: str) -> None:
    t["history"].append(est._event(on, fld, before, after, reason, "import", t))


def _apply_edits(t: dict[str, Any], edits: dict[str, str], reason: str | None, model: str,
                 proposed: dict[str, Any], on: str, report: ImportReport) -> None:
    tid = t["id"]
    for key in _SIMPLE_EDITABLE:
        if key not in edits:
            continue
        value = _parse_simple(key, edits[key])
        if t.get(key) == value:
            continue
        before = t.get(key)
        t[key] = value
        if key in ("assignee", "status"):
            _record(t, key, before, value, reason, on)
        report.changes.append(f"{tid}: {key} {before!r} -> {value!r}")

    estimate_keys = [k for k in edits if k in _ESTIMATE_INPUTS or k == "effort"]
    if not estimate_keys:
        return
    before = est.estimate_snapshot(t, model)
    if model == est.MODEL_HOURS:
        # a changed estimate is made under the backlog's current rubric
        rubric_version = est.current_rubric_version(proposed)
        values = _estimate_inputs(t)
        values.update({k: edits[k] for k in estimate_keys})
        new_estimate = _build_estimate(values, rubric_version)
        if new_estimate is not None and t.get("estimate"):
            # an untouched estimate keeps the rubric it was made under
            same = {k: v for k, v in new_estimate.items() if k != "rubric_version"}
            old = {k: v for k, v in t["estimate"].items() if k != "rubric_version"}
            if same == old:
                return
        t["estimate"] = new_estimate
        t["effort"] = (None if new_estimate is None else est.points_number(
            est.calculate_points(new_estimate["estimated_hours"], new_estimate["difficulty_level"],
                                 est.rubric_for(proposed, rubric_version))))
    else:
        text = " ".join(edits["effort"].split())
        try:
            value = est.dec(text)
        except est.EstimationError:
            value = None
        if value is None or value != value.to_integral_value() or int(value) not in est.FIBONACCI_POINTS:
            raise ValueError(f"effort {text!r} must be a Fibonacci point (1, 2, 3, 5, 8, 13)")
        t["effort"] = int(value)
    after = est.estimate_snapshot(t, model)
    if after == before:
        return
    if not reason and not est.is_unestimated_snapshot(before):
        raise ValueError("estimate changed but change_reason is empty; say why in the "
                         "change_reason column")
    _record(t, "estimate", before, after, reason or "first estimate", on)
    report.changes.append(f"{tid}: estimate {_describe(before, model)} -> {_describe(after, model)}")


def _describe(snap: dict[str, Any], model: str) -> str:
    """'4h level 4 = 5.6 points', 'Unestimated', or '5 points' (Fibonacci)."""
    estimate = snap.get("estimate")
    if model == est.MODEL_HOURS and estimate:
        return (f"{est.fmt_hours(estimate['estimated_hours'])}h level "
                f"{est.level_of(estimate['difficulty_level'])} = "
                f"{est.fmt_points(snap['effort'], model)} points")
    if snap.get("effort") is None:
        return est.UNESTIMATED
    return f"{est.fmt_points(snap['effort'], model)} points"


# --------------------------------------------------------------------------- #
# command line
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ticketly import",
        description="Import an edited Ticketly CSV (standard or Notion layout) back into the "
        "backlog: owners, status, due dates, priority and estimate inputs. Points are "
        "recalculated and every change is recorded in the ticket's history.",
    )
    parser.add_argument("csv", help="The edited CSV (ticketly/backlog.csv, or a Notion export).")
    parser.add_argument("--backlog", default=DEFAULT_BACKLOG,
                        help=f"Backlog JSON to update (default: {DEFAULT_BACKLOG}).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would change and write nothing.")
    parser.add_argument("--on", type=date.fromisoformat, default=None,
                        help="Date to record on history entries (YYYY-MM-DD; default today).")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    on = args.on.isoformat() if args.on else bl.today()
    backlog_path = Path(args.backlog)
    try:
        data = render.load_backlog(backlog_path)
    except Exception as exc:  # schema or integrity problems in the backlog itself
        print(f"the backlog is not valid, fix it before importing:\n{exc}", file=sys.stderr)
        return 1
    try:
        report = plan_import(data, Path(args.csv).read_text(encoding="utf-8-sig"), on=on)
    except ImportAborted as exc:
        for err in exc.errors:
            print(f"ERROR: {err}", file=sys.stderr)
        print(f"\nimport aborted: {len(exc.errors)} error(s); nothing was written.",
              file=sys.stderr)
        return 1

    for w in report.warnings:
        print(f"WARNING: {w}", file=sys.stderr)
    if report.stale_untouched:
        print(f"note: {len(report.stale_untouched)} row(s) were unchanged in the CSV but changed "
              f"in Ticketly since the export; kept Ticketly's values: "
              f"{', '.join(report.stale_untouched)}", file=sys.stderr)
    for c in report.changes:
        print(c)
    if not report.changed:
        print("No changes to import; the backlog was left untouched.")
        return 0
    if args.dry_run:
        print(f"\ndry run: {len(report.changes)} change(s) would be applied; nothing was written.")
        return 0
    render.save_backlog(backlog_path, report.data)
    print(f"\nimported {len(report.changes)} change(s) into {backlog_path}. Re-export with "
          f"`ticketly render {backlog_path} --format all --out-dir ticketly/`.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
