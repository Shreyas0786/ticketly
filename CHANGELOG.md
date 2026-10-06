# Changelog

All notable changes to Ticketly are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and Ticketly uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html): `MAJOR.MINOR.PATCH`
— patch for fixes, minor for new features, major for breaking changes.

## [Unreleased]

## [1.3.0] — 2026-10-06

### Added
- **Hours-based points.** A new backlog asks once whether to size work in hours-based points or
  Fibonacci points, saves the choice in its `estimation` block, and shows it in every export.
  Hours-based Tasks carry an `estimate` — a quarter-hour breakdown (implementation, testing,
  self-review, handoff), a difficulty level 1–4 with a reason, and a confidence — and `effort` is
  calculated as hours × multiplier (1.00 / 1.10 / 1.25 / 1.40), with Decimal arithmetic and half-up
  rounding to one decimal. Each backlog freezes the rubric its estimates were made under. Tasks that
  can't be estimated show as **Unestimated**, and totals that include them are marked partial.
- `ticketly recalc` — recalculates points with the one shared calculation and records each Task's
  baseline and every later estimate, owner and status change in its `history` (an estimate change
  needs `--reason`; `--approved-by` records approved growth).
- `ticketly switch-model --to hours --reason ...` — moves a Fibonacci backlog to hours-based points,
  keeping each Task's old points, owner and status as a legacy estimate. Legacy and new totals are
  reported separately. Tasks completed at the switch keep their legacy points, credited to the owner
  recorded at the switch, stay out of the new totals and partial flags, and can't be re-estimated.
- `ticketly import` — brings an edited standard or Notion CSV back into the backlog (owners, status,
  due dates, priority, estimate inputs), with per-field export baselines to separate untouched stale
  values from conflicting edits, `--dry-run`, all-or-nothing validation, and an atomic write.
- Ownership and progress: an **In Review** status (Done now means reviewed work that meets its
  acceptance criteria), per-person assigned-versus-Done totals with hours and points kept apart, and
  optional `work_kind` (cleanup, integration, client preparation, investigation) for explicit work.
- Split/takeover tracking with `split_from` (`replaced` or `additional` scope). A full takeover is a
  reassignment. The validator rejects dangling or circular splits and splits that leave the original
  nothing, and holds every chain of replaced splits — repeated and nested ones included — to the
  original estimate, even after later re-estimates, unless the growth was approved.
- Epic totals in `backlog.md` and both CSVs, kept separate from the Epics' internal `effort` of 0.
- A worked hours-based example (`examples/hours-backlog.json`) and an optional `hours_rubric` in the
  house style.

### Changed
- Both CSV exports gain estimation, tracking, total and baseline columns, appended after the
  existing columns, which keep their order. `ticketly reset` still recognises CSVs exported before
  this change.
- `ticketly validate` checks the backlog against the schema before its integrity checks, and every
  command refuses `NaN` / `Infinity` values. Difficulty levels written as whole decimals (`2.0`) are
  read as whole levels; fractional or out-of-range levels are refused.
- The CLI help shows the current `ticketly reset [-y]` usage.

Existing backlogs without an `estimation` block keep validating and rendering as Fibonacci backlogs.

## [1.2.2] — 2026-08-12

### Added
- README now opens with a plain summary of what Ticketly is, and closes with an
  FAQ covering specs, existing codebases, tracker imports, API keys, and handing
  the backlog to a coding agent.
- Links to the Ticketly website and guides from the README and the package
  metadata (`Homepage`, `Documentation`), with GitHub kept as `Source` and
  `Issues`.

### Changed
- Privacy wording now separates Ticketly's local validation and export engine —
  which adds no network calls or telemetry — from the repository inspection and
  conversational reasoning that happen inside Claude Code or Codex under that
  agent's own settings and policies. Previously the README and `SECURITY.md`
  claimed nothing was sent anywhere, which overlooked the host agent.

## [1.2.1] — 2026-07-04

### Added
- Brand assets in `assets/` (logo, icon, social card) and a logo header in the
  README that swaps between GitHub's light and dark themes, with a PyPI-safe
  fallback so it renders on the PyPI page too.

### Fixed
- Ticket references in the rendered Markdown now join the ticket ID and title with
  a plain ASCII hyphen (`ARC-001 - Freeze core status vocabulary`) instead of an em
  dash. Affects the Build order and Your plan sections and the `tasks.md` checklist,
  so references copy, paste, and parse cleanly in downstream tools. Section headings
  and page titles are unchanged.

## [1.2.0] — 2026-06-15

### Added
- `tasks.md` export — an agent-ready checklist: one checkbox per ticket (grouped by
  epic, dependency-ordered), with dependencies and acceptance criteria inline.
  `Done` renders as `- [x]`, in-progress as `- [ ]` + 🚧, so a coding agent can read
  the file and tick boxes as it works. New `--format tasks`, and a `core` format
  (md + csv + tasks) that the skill now generates by default.

### Changed
- Consolidated output into a single `ticketly/` folder: the readable exports
  (`backlog.md`, `tasks.md`, `backlog.csv`) at the top, and the machine
  source-of-truth JSONs in a hidden `ticketly/.data/`. Exports use fixed names
  (`backlog.md`) instead of `<project>.md`. Replaces the old `profiles/` +
  `backlogs/` + `build/` layout — new runs write to `ticketly/`; files already
  generated under the old layout are left untouched.
- `ticketly reset` now clears the current folder's `ticketly/` files (the `<project>`
  argument and `--all` flag are gone — one project per folder). Same safety
  contract: confirms first, only deletes files it can fingerprint as its own.

## [1.1.0] — 2026-06-13

### Added
- Plain-language "Your plan" overview at the top of the rendered Markdown: where
  to start, a "Start today" vs. "Comes after" split driven by dependencies, and
  each area's size in words (small/medium/large) rather than story-point numbers.
  Stays deterministic — no model calls. Optional `priority` nudges the start
  order to the top when set, but order is pure dependency order without it.
- Self-check step in the `/ticketly` skill: after generating, the model re-reads
  its own backlog against a concrete checklist (testable acceptance criteria,
  missing dependencies, gaps, sane effort, flagged unknowns) and fixes weak spots
  before showing the user — so a plan doesn't reach a non-technical builder with
  obvious holes.
- Checkability lint in `ticketly validate`: a non-blocking `vague_acceptance_criteria`
  **warning** flags acceptance criteria that can't be objectively ticked off —
  subjective quality words ("works well", "user-friendly") or a bare "done". Curated
  to stay quiet, so a well-written backlog raises no false alarms.

## [1.0.0] — 2026-06-08

First public release on PyPI: `pipx install ticketly`.

### Added
- Pip/pipx distribution — Ticketly is now an installable package; bundled data
  (schemas, house style, examples, archetypes, agent front-doors) ships inside
  the package so it works from any folder without a repo checkout.
- `ticketly` console command: `home`, `render`, `validate`, `profile`,
  `archetypes`, `install claude|codex|all`, and `reset`.
- `ticketly install` wires Ticketly into Claude Code (the `/ticketly` skill)
  and/or Codex (the AGENTS.md pointer), idempotently.
- `ticketly reset <project> [--all]` safely removes only a project's own
  generated files, with a confirmation prompt and a foreign-file safety check.

### Changed
- Agent front-doors call the `ticketly` command instead of `python3 -m ticketly.*`,
  so they run under the interpreter the package was installed into.
- License is now free-to-use with no copying/modifying/reselling (was fully
  proprietary/no-use).

[Unreleased]: https://github.com/Shreyas0786/ticketly/compare/v1.3.0...HEAD
[1.3.0]: https://github.com/Shreyas0786/ticketly/compare/v1.2.2...v1.3.0
[1.2.2]: https://github.com/Shreyas0786/ticketly/compare/v1.2.1...v1.2.2
[1.2.1]: https://github.com/Shreyas0786/ticketly/compare/v1.2.0...v1.2.1
[1.2.0]: https://github.com/Shreyas0786/ticketly/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/Shreyas0786/ticketly/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/Shreyas0786/ticketly/releases/tag/v1.0.0
