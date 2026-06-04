# Ticketly

Turn messy project requirements into clean, structured, PM-quality tickets — EPICs broken into child tickets, with dependencies, effort estimates, and acceptance criteria, ready to drop into any tracker.

Ticketly runs **inside Claude Code / Codex** — your team clones the repo and runs it with their existing subscription. **No API key, no setup.**

## Status

Early build. Foundation + Phase 1 (profile, generator skill, renderers) are in place:

- `schema/ticket.schema.json` — the single source of truth for every ticket. Lean **9 core fields** (id, title, type, parent, status, effort, dependencies, description, acceptance_criteria, plus a `needs_clarification` guardrail) and **3 optional fields** (assignee, due_date, priority) that stay hidden until a growing team needs them.
- `profile/profile.schema.json` — the per-project **profile**: the company, project, user-supplied tech stack and architecture, and the agreed ticket-ID prefix scheme. Gathered before any tickets are written, and reused across runs.
- `house-style/` — the **house style**: the effort rubric (what each Fibonacci point means), the default ID-prefix vocabulary, tone rules for titles/descriptions/acceptance criteria, and a pointer to a few-shot example backlog. Generated tickets match this voice; a project can override the default.
- `.claude/skills/ticketly/SKILL.md` — the **`/ticketly`** skill that drives generation inside Claude Code.
- `ticketly/render.py` — validates a backlog and renders it to **Markdown + CSV** (with a topologically sorted **Build order** section).
- `ticketly/validate.py` — **integrity checks** beyond the schema: duplicate IDs, dangling/circular dependencies, orphan or non-epic parents, oversized epics, and missing acceptance criteria. Rendering aborts on any error.
- `examples/` — a worked example backlog and profile that validate against their schemas.
- `tests/` — structural tests guarding the schemas, the renderers, and the skill.

## Setup

```bash
python3 -m pip install -r requirements.txt
```

`jsonschema` is the only runtime dependency (validation + rendering); `pytest` and `PyYAML` are for the tests.

## Using it

Run **`/ticketly`** in Claude Code. It walks a project through four stages — you can stop after any of them and resume later:

1. **Start** — give your company and project (Ticketly never invents these).
2. **Discuss** — talk through the stack and architecture, free-form. No interrogation; a few focused questions at a time.
3. **Distill** — when you're ready, it writes a `profiles/<project>.json` profile and **suggests an ID-prefix scheme** (`WEB`, `API`, `DB`, `AUTH`, …) from your stack for you to confirm or edit.
4. **Generate** — it writes epics, breaks them into tickets with dependencies, Fibonacci effort, and acceptance criteria, then renders them.

Render a backlog to review-ready output any time:

```bash
python3 -m ticketly.render backlogs/<project>.json --format both --out-dir build/
```

This validates the backlog against the schema **and runs the integrity checks** first, then writes `build/<project>.md` (epic-grouped table + Build order) and `build/<project>.csv` (universal tracker import). A backlog with any integrity error is refused. To check a backlog without rendering:

```bash
python3 -m ticketly.validate backlogs/<project>.json
```

## Conventions

- **IDs:** epics are `EPIC-<PREFIX>` (e.g. `EPIC-REL`); tasks inherit the prefix as `<PREFIX>-NNN` (e.g. `REL-002`). The prefix groups a theme; `parent` links a task to its epic.
- **Effort:** Fibonacci story points (1, 2, 3, 5, 8, 13). Epics are `0` — they are sized by their children.
- **Company & project are user-supplied.** Every backlog records the `company` and `project` it is for. Ticketly asks for these and never invents them.
- **Guardrail:** Ticketly never invents requirements. If something is unspecified, the ticket is flagged `needs_clarification` instead of hallucinating scope.

## Roadmap

1. **Phase 1** ✅ — generator command + Markdown and CSV renderers.
2. **Phase 2** ✅ — per-project house-style config + few-shot examples.
3. **Phase 3** ✅ — dependency validation, build-order view, dedupe, plain-English refine loop.
4. **Phase 4** — Notion export (CSV is already the universal path).
5. **Phase 5** — web UI for a public, open-source release.

## Tests

```bash
python3 -m pytest -q
```
