"""Export baselines: how an edited CSV is matched back to the backlog safely.

Every exported CSV row carries a ``ticketly_baseline`` (``Ticketly Baseline`` in
the Notion layout) token. It records, for that row's ticket, a short fingerprint
of every exported field *as it was at export time*. On import that gives a
three-way comparison per field:

- CSV value == baseline     -> the user did not touch this field (an untouched
                               stale value is simply ignored);
- current backlog == baseline -> nothing changed in Ticketly since the export,
                               so a CSV edit applies cleanly;
- both differ (and the CSV value isn't already the current one) -> a conflicting
                               stale edit, and the import aborts.

A single whole-ticket fingerprint could not tell an untouched stale row from an
edited one; per-field fingerprints can. Values are canonicalised first, so the
re-formatting a spreadsheet or Notion applies ("8" vs "8.0", reordered
dependencies, CRLF line breaks) does not look like an edit.

Token format (version 1)::

    tb1:<layout>:<export id>:<ticket id>:<field hashes joined by '.'>:<check>

``layout`` is ``s`` (standard CSV) or ``n`` (Notion); ``check`` guards against a
truncated or hand-edited token.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

TOKEN_VERSION = "tb1"
LAYOUT_CODES = {"standard": "s", "notion": "n"}
_HASH_LEN = 6

# How each logical field is canonicalised before hashing / comparing.
NUMBER_FIELDS = {
    "effort", "estimated_hours", "hours_implementation", "hours_testing",
    "hours_self_review", "hours_handoff", "difficulty_level", "legacy_effort",
    "points_total", "hours_total",
}
BOOL_FIELDS = {"needs_clarification", "points_total_partial"}
CHOICE_FIELDS = {
    "type", "status", "priority", "estimate_confidence", "work_kind",
    "estimation_model", "split_scope", "legacy_model",
}
ID_LIST_FIELDS = {"dependencies"}
DATE_FIELDS = {"due_date"}

_DATE_FORMATS = ("%Y-%m-%d", "%B %d, %Y", "%b %d, %Y", "%Y/%m/%d")


def parse_date(text: str) -> str | None:
    """ISO date from the formats a spreadsheet or Notion export produces."""
    text = text.strip()
    if not text:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    raise ValueError(f"not a date: {text!r} (use YYYY-MM-DD)")


def canonical(key: str, value: str | None) -> str:
    text = "" if value is None else str(value)
    text = " ".join(text.split())  # trims, and folds CRLF / repeated spaces
    if not text:
        return ""
    if key in NUMBER_FIELDS:
        if text.lower() == "unestimated":
            return "unestimated"
        try:
            return format(Decimal(text).normalize(), "f")
        except InvalidOperation:
            return text.lower()
    if key in BOOL_FIELDS:
        low = text.lower()
        if low in ("true", "yes", "y", "1"):
            return "true"
        if low in ("false", "no", "n", "0"):
            return "false"
        return low
    if key in CHOICE_FIELDS:
        return text.lower()
    if key in ID_LIST_FIELDS:
        return ",".join(sorted(p for p in re.split(r"[;,\s]+", text) if p))
    if key in DATE_FIELDS:
        try:
            return parse_date(text) or ""
        except ValueError:
            return text
    return text


def field_hash(key: str, value: str | None) -> str:
    digest = hashlib.sha256(f"{key}\x1f{canonical(key, value)}".encode()).hexdigest()
    return digest[:_HASH_LEN]


def export_id(data: dict[str, Any]) -> str:
    """A short, deterministic id for the backlog content being exported."""
    blob = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode()).hexdigest()[:10]


def _check(body: str) -> str:
    return hashlib.sha256(body.encode()).hexdigest()[:_HASH_LEN]


def make_token(layout: str, exp_id: str, ticket_id: str, cells: list[tuple[str, str]]) -> str:
    """Token for one row. ``cells`` = (field key, exported cell text), in layout order."""
    hashes = ".".join(field_hash(k, v) for k, v in cells)
    body = f"{TOKEN_VERSION}:{LAYOUT_CODES[layout]}:{exp_id}:{ticket_id}:{hashes}"
    return f"{body}:{_check(body)}"


@dataclass(frozen=True)
class Baseline:
    layout: str
    export_id: str
    ticket_id: str
    hashes: tuple[str, ...]


class BaselineError(ValueError):
    pass


def parse_token(token: str, layout: str, n_fields: int) -> Baseline:
    parts = (token or "").strip().split(":")
    if len(parts) != 6 or parts[0] != TOKEN_VERSION:
        raise BaselineError("baseline token is missing or not a Ticketly export token")
    version, code, exp_id, ticket_id, hashes, check = parts
    body = ":".join(parts[:5])
    if _check(body) != check:
        raise BaselineError("baseline token was altered or truncated")
    if code != LAYOUT_CODES[layout]:
        raise BaselineError("baseline token comes from the other CSV layout")
    split = tuple(hashes.split(".")) if hashes else ()
    if len(split) != n_fields:
        raise BaselineError("baseline token does not match this Ticketly version's columns")
    return Baseline(layout, exp_id, ticket_id, split)


def today() -> str:
    return date.today().isoformat()
