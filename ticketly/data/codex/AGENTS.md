# Ticketly for Codex

This is the Codex front door to Ticketly. The Python engine and the full planning workflow are
shared with the Claude Code version — this file only adapts them for Codex/GPT. The canonical,
detailed flow lives in `SKILL.md`; read it and follow it.

## How to run it

1. **Find the engine.** Run `ticketly home`; it prints the engine path. Call it `ENGINE`.
   If it errors with "command not found", Ticketly isn't installed — tell the user to run
   `pipx install ticketly && ticketly install codex` (or `pip install ticketly`), then retry.
2. **Read the canonical workflow** at `ENGINE/claude/SKILL.md` and follow it end to
   end. Everything there applies to Codex unchanged **except** the Codex deltas below.
3. **Read the bundled data by absolute path from `ENGINE`** as the workflow directs: the schemas,
   `ENGINE/house-style/default.json`, `ENGINE/archetypes/archetypes.json`, and
   `ENGINE/examples/house-style-backlog.json`.

## Codex deltas (the only differences from SKILL.md)

- **You — Codex / GPT — are the model doing the thinking.** Wherever SKILL.md says "you (the model)"
  or refers to running "inside Claude Code", that means you, running inside Codex. The deterministic
  work (validate, render, profile) is the `ticketly` Python package, exactly as before.
- **Trigger:** there is no `/ticketly` slash command in Codex. You begin this flow whenever the user
  asks to plan a backlog, break a project into tickets, or says "use Ticketly".
- **No extra API key for Ticketly itself.** Ticketly runs locally on your machine; the model is
  whatever you're already signed into in Codex.

## The non-negotiables (restated so this file stands alone)

- **Never invent.** No company name, tech stack, scope, or requirements the user did not give. When
  requirements are too thin to write a real ticket, set `needs_clarification: true` and say what's
  missing — do not fill the gap with a guess.
- **Talk like a builder, not a developer.** Assume the user may be non-technical: explain any concept
  in one plain sentence the first time it appears, and always offer an obvious low-effort default.
- **Read engine data from `ENGINE`; write project output into the user's current folder** under a
  single `./ticketly/` — exports (`backlog.md`, `tasks.md`, `backlog.csv`) at the top, source JSONs
  in `./ticketly/.data/` (`profile.json`, `backlog.json`).
- **Validate and render through the engine, never by hand:** `ticketly profile`,
  `ticketly validate`, `ticketly render`.
- **Ask the estimation model once per new backlog:** Hours-based points or Fibonacci points
  (suggest Hours-based if the user leaves it to you), save it in the backlog's `estimation` block,
  and never ask again for an existing backlog. For hours-based points propose only the inputs — a
  quarter-hour breakdown (implementation, testing, self-review, handoff), a difficulty level 1–4
  with a technical reason, and a confidence — and let `ticketly recalc` calculate the points and
  record history. Estimate the work, never the person. A task that can't be estimated responsibly
  stays Unestimated with `needs_clarification: true`. The rubric and rules are in
  `ENGINE/house-style/default.json` (`hours_rubric`); a worked example is
  `ENGINE/examples/hours-backlog.json`.
- **Record every change through the engine:** `ticketly recalc` (with `--reason` when an estimate
  changes), `ticketly switch-model ticketly/.data/backlog.json --to hours --reason ...` to change models, and `ticketly import`
  for an edited CSV or Notion export. Never hand-edit `history`, `legacy_estimates` or calculated
  points. Done means reviewed work that meets its acceptance criteria. A full takeover is a
  reassignment; partial work becomes a separately owned `replaced` split, and the original plus all
  its splits may never total more than the original estimate unless the growth is approved
  (`ticketly recalc ticketly/.data/backlog.json --reason ... --approved-by NAME`). Tasks completed before a model switch keep
  their legacy points and owner and are never re-estimated — new work goes in a new task.
- **CSV / Notion round trip:** only owners, status, due dates, priority and estimate inputs come back
  (`estimated_hours` is computed from the breakdown); protected fields and extra Notion properties are
  not imported. Refresh Notion into a new database and keep the original.

The full detail — Discuss (with the archetype-driven, free-first stack recommendations), Distill,
choose scope, choose the estimation model, generate, check integrity, render, refine, ownership and
takeovers, and the CSV/Notion round trip — is in `SKILL.md`. Read it before you
start writing tickets.
