# Hours-based points — release checkpoint

**Feature:** Hours-based points (estimation model choice, ownership and progress tracking, and the
CSV / Notion-layout round trip).
**Branch:** `codex/hours-based-points-develop` (from `develop` at `5f27c8a`) · **Target:** 1.3.0
(planned) · **Package version:** still 1.2.2.

## Status (Phase 4 snapshot)

As of the Phase 4 checkpoint: implementation, documentation and local validation were complete,
and the work was **uncommitted, unpushed, unmerged and unpublished**. Next step at that snapshot: a
separately approved local commit.

## Approved scope

- Choose hours-based points or Fibonacci points once per new backlog; existing Fibonacci backlogs
  keep their meaning.
- Hours-based points = standard hours × difficulty multiplier (1.00 / 1.10 / 1.25 / 1.40), Decimal
  arithmetic, half-up to one decimal; quarter-hour breakdown, difficulty reason, separate confidence,
  Unestimated tasks and partial totals; the rubric is frozen per estimate.
- Explicit, reasoned model switch (Fibonacci → hours) with legacy and new totals kept apart.
- Owners, In Review, per-person assigned versus Done totals (hours and points apart), explicit
  cleanup / integration / client-preparation / investigation tasks.
- Recorded history of estimate, owner, status and model changes; full takeovers as reassignment;
  partial takeovers as separately owned splits that never count the same scope twice.
- Edited standard or Notion-layout CSV → validate and recalculate → export, with dry run, stale-edit
  conflict detection and all-or-nothing writes.
- Out of scope: rates, budgets, invoicing, payments, live Notion sync.

## Local validation (Phase 3)

- Full suite: **519 passed, 0 failed, 0 skipped** on Python 3.11.1, including the wheel-build test,
  which built a wheel and was not skipped. A separate wheel build contained the new modules and the
  hours example.
- Tests and CLI runs used this checkout through `PYTHONPATH`; the `ticketly` command installed on the
  test machine is an older release and was not used.
- CLI scenarios run in disposable copies, all as expected:
  - rendered the hours example to all formats;
  - imported standard and Notion-layout edits (owner, status, breakdown, level, reason); dry runs and
    repeat imports left the backlog byte-for-byte unchanged;
  - stale conflicting edits, mixed valid/invalid rows (NaN, Infinity, a 2.5 level), unknown IDs and a
    missing baseline column were rejected with the backlog unchanged;
  - an untouched stale row kept the current backlog values;
  - the worked-example calculations matched, including half-up ties (0.75 h at level 4 = 1.1, 1.75 h = 2.5);
  - partial and nested takeovers validated; a later inflation of the split scope was rejected; the
    same change with `--approved-by` was accepted; full reassignment was recorded; a split leaving
    the original nothing was rejected;
  - a legacy switch kept completed work credited to its recorded owner after reassignment; its
    re-estimation was refused by `recalc` and both CSV layouts;
  - all packaged examples validate and render; `ticketly reset` removed only Ticketly's files and
    left an unrelated file in place.

**Ticketly Done:** not applicable — no owning release ticket exists. The packaged backlogs are examples.

## Not yet verified

- A round trip through the actual Notion application (only Notion-layout CSVs were checked locally).
- Hosted CI (Python 3.10–3.13); only local Python 3.11.1 was run.

## Known limitations

- Supported migration is Fibonacci → hours; hours → Fibonacci is refused.
- Approved growth for a split family is recorded only through `ticketly recalc --approved-by`, not
  through a CSV import; the approver is a recorded name, not a verified identity.
- Split scope is checked on unrounded points, so displayed rounded totals may differ by 0.1; within
  the original estimate, a reduced estimate can rise again without approval.
- Splits recorded before a model switch are not checked against the new model's estimates.
- A completed legacy task can be reopened by status but stays on legacy points.
- CSV `estimated_hours` is computed from the breakdown columns and is not directly editable.
