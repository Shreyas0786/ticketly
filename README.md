# Ticketly

Turn messy project requirements into clean, structured, PM-quality tickets — EPICs broken into child tickets, with dependencies, effort estimates, and acceptance criteria, ready to drop into any tracker.

Ticketly runs **inside Claude Code / Codex** — your team clones the repo and runs it with their existing subscription. **No API key, no setup.**

## Status

Early build. Foundation is in place:

- `schema/ticket.schema.json` — the single source of truth for every ticket. Lean **9 core fields** (id, title, type, parent, status, effort, dependencies, description, acceptance_criteria, plus a `needs_clarification` guardrail) and **3 optional fields** (assignee, due_date, priority) that stay hidden until a growing team needs them.
- `examples/sample-release-backlog.json` — a worked example backlog that validates against the schema.
- `tests/` — structural tests guarding the schema.

## Conventions

- **IDs:** epics are `EPIC-<PREFIX>` (e.g. `EPIC-REL`); tasks inherit the prefix as `<PREFIX>-NNN` (e.g. `REL-002`). The prefix groups a theme; `parent` links a task to its epic.
- **Effort:** Fibonacci story points (1, 2, 3, 5, 8, 13). Epics are `0` — they are sized by their children.
- **Guardrail:** Ticketly never invents requirements. If something is unspecified, the ticket is flagged `needs_clarification` instead of hallucinating scope.

## Roadmap

1. **Phase 1** — generator command + Markdown and CSV renderers.
2. **Phase 2** — per-project house-style config + few-shot examples.
3. **Phase 3** — dependency validation, build-order view, dedupe, plain-English refine loop.
4. **Phase 4** — tracker exports (Notion / Linear / Jira).
5. **Phase 5** — web UI for a public, open-source release.

## Tests

```bash
python3 -m pytest -q
```
