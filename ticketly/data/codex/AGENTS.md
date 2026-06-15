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

The full detail — Discuss (with the archetype-driven, free-first stack recommendations), Distill,
choose scope, generate, check integrity, render, and refine — is in `SKILL.md`. Read it before you
start writing tickets.
