# Changelog

All notable changes to Ticketly are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and Ticketly uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html): `MAJOR.MINOR.PATCH`
— patch for fixes, minor for new features, major for breaking changes.

## [Unreleased]

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

[Unreleased]: https://github.com/Shreyas0786/ticketly/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/Shreyas0786/ticketly/releases/tag/v1.0.0
