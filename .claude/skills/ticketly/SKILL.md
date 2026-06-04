---
name: ticketly
description: Turn project requirements into clean, structured, PM-quality tickets — discuss a project's tech stack and architecture, capture it as a reusable profile, then generate epics broken into child tickets with dependencies, Fibonacci effort, and acceptance criteria, rendered to Markdown and CSV. Use when the user wants to plan a backlog, break a project into tickets, or talk through architecture before writing tickets.
---

# Ticketly

Turn a project's requirements into professional tickets, the way a real PM would.
Ticketly runs **inside Claude Code — no API key, no setup**. You (the model) do the
thinking; the repo's Python core (`ticketly/render.py`) does the deterministic
validation and rendering.

## The one rule: never invent

Never invent a company name, a tech stack, scope, or requirements. Everything in a
profile or a ticket must come from the user. When requirements are too thin to write
a real ticket, set `needs_clarification: true` and say what is missing — do **not**
fill the gap with a guess.

## The flow

A project moves through four stages. The user can stop after any of them and resume later.

### 1. Start a project

Every project gets its own profile. Ask for the two things Ticketly never invents:

- **Company** — the organization the work is for.
- **Project** — the project name.

Use placeholders like "Demo Company / Demo Project" only in examples, never as a real value.

### 2. Discuss (free-form)

Talk through the project with the user: what it is, the frontend / backend / database /
infra they use, how the pieces fit together, key constraints. This is a conversation, not
a form — ask 2–4 focused questions at a time, don't interrogate. The goal is to understand
the system well enough to write sharp tickets. Recommend (don't impose) options only if the
user explicitly asks "what should I use?" — otherwise capture what they have.

### 3. Distill into a profile

When the user is ready (e.g. "save the profile", "distill", "looks good"), write what you
learned to `profiles/<project-slug>.json`, conforming to `profile/profile.schema.json`:

- `stack` — only the layers the user named. Leave a layer out if they didn't mention it.
- `architecture.components` — the major moving parts, in their words.
- `prefixes` — **suggest** a ticket-ID prefix per domain/layer from the stack, then **show
  the user and let them confirm or edit before continuing.** Typical: `WEB`/`FE` for the
  frontend, `API`/`BE` for the backend, `DB` for data, `AUTH` for accounts, `INFRA` for
  ops. Suggest only prefixes that match the project's actual layers.

Validate before saving:

```bash
python3 -c "import json,jsonschema; jsonschema.Draft202012Validator(json.load(open('profile/profile.schema.json'))).validate(json.load(open('profiles/<slug>.json')))"
```

### 4. Generate the backlog

Using the confirmed profile + the requirements:

1. **Epics first.** One `EPIC-<PREFIX>` per domain from the profile's prefixes (only those
   that have real work). Epics have `effort: 0` and `acceptance_criteria: []`.
2. **Break each epic into Tasks** — `<PREFIX>-NNN`, inheriting the epic's prefix.
   Each Task needs: a clear `description`, testable `acceptance_criteria` (non-empty),
   Fibonacci `effort` (1, 2, 3, 5, 8, 13), and `dependencies` (other ticket IDs, or `[]`).
3. **Dependencies & build order** — wire `dependencies` so the backlog reads in a sensible
   build order. Never create a circular or dangling dependency.
4. **Guardrail** — anything underspecified gets `needs_clarification: true`, not a guess.

Write the result to `backlogs/<project-slug>.json`, conforming to `schema/ticket.schema.json`.

### 5. Render

```bash
python3 -m ticketly.render backlogs/<slug>.json --format both --out-dir build/
```

This validates the backlog, then writes `build/<slug>.md` (epic-grouped, review-ready) and
`build/<slug>.csv` (universal tracker import). Show the user the Markdown.

## Refine

After generating, the user edits in plain English — "split WEB-003", "add acceptance
criteria to API-005", "re-estimate", "re-order by dependency". Re-emit the backlog JSON,
re-validate, re-render. Don't aim for one-shot perfection.

## Conventions (locked)

- **IDs:** epics `EPIC-<PREFIX>`; tasks `<PREFIX>-NNN`. Prefix = epic theme; children inherit it.
- **Effort:** Fibonacci points only (1, 2, 3, 5, 8, 13). Epics are `0`, sized by their children.
- **Schema is the source of truth.** Every backlog validates against `schema/ticket.schema.json`;
  every profile against `profile/profile.schema.json`.
