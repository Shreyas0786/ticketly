# Ticketly

Turn messy project requirements into clean, structured, PM-quality tickets — EPICs broken into child tickets, with dependencies, effort estimates, and acceptance criteria, ready to drop into any tracker.

Ticketly runs **inside Claude Code / Codex** with your existing subscription. **No API key.** Install it once, then run `/ticketly` from **any** folder — including a brand-new empty project that doesn't contain this codebase.

## Status

Roadmap Phases 1–4 are in place, and Ticketly installs globally (run it from any folder):

- `schema/ticket.schema.json` — the single source of truth for every ticket. Lean **9 core fields** (id, title, type, parent, status, effort, dependencies, description, acceptance_criteria, plus a `needs_clarification` guardrail) and **3 optional fields** (assignee, due_date, priority) that stay hidden until a growing team needs them.
- `profile/profile.schema.json` — the per-project **profile**: the company, project, user-supplied tech stack and architecture, and the agreed ticket-ID prefix scheme. Gathered before any tickets are written, and reused across runs.
- `house-style/` — the **house style**: the effort rubric (what each Fibonacci point means), the default ID-prefix vocabulary, tone rules for titles/descriptions/acceptance criteria, and a pointer to a few-shot example backlog. Generated tickets match this voice; a project can override the default.
- `.claude/skills/ticketly/SKILL.md` — the **`/ticketly`** skill that drives generation inside Claude Code, from any folder.
- `install.sh` + `pyproject.toml` — one-time install: the `ticketly` engine (importable anywhere) and the skill (copied into your personal Claude Code skills dir). `ticketly/home.py` locates the engine's bundled data so it works regardless of where you run it.
- `ticketly/render.py` — validates a backlog and renders it to **Markdown + CSV** (with a topologically sorted **Build order** section).
- `ticketly/validate.py` — **integrity checks** beyond the schema: duplicate IDs, dangling/circular dependencies, orphan or non-epic parents, oversized epics, and missing acceptance criteria. Rendering aborts on any error.
- `examples/` — a worked example backlog and profile that validate against their schemas.
- `tests/` — structural tests guarding the schemas, the renderers, and the skill.

## Install once

From the Ticketly repo, run:

```bash
./install.sh
```

This installs the `ticketly` engine and symlinks the `/ticketly` skill into your personal Claude Code skills directory. You only do this once. **To update later, just `git pull` in this repo** — both the engine (editable install) and the skill (symlink) track it automatically, no reinstall needed.

## Using it (from any folder)

1. Open **any** folder in Claude Code — your real project, even an empty one.
2. Type **`/ticketly`**.
3. Describe your project — it asks fresh each time (company, project, stack, architecture) and builds a profile for *that* folder.
4. It generates the tickets and writes `profiles/`, `backlogs/`, and `build/` **into your current folder**.

The flow has stages you can stop and resume:

1. **Start** — give your company and project (Ticketly never invents these, and never guesses your company from your email).
2. **Discuss** — talk through the stack and architecture, free-form. No interrogation; a few focused questions at a time.
3. **Distill** — it writes a `profiles/<project>.json` profile and proposes a few **main areas** (with short tags like `WEB`, `API`, …) for you to confirm or edit — in plain language, no jargon required.
4. **Choose scope** — it asks whether you want the **full backlog** or a lean **MVP** (and if MVP, lists what it set aside for later).
5. **Generate** — it writes epics, breaks them into tickets with dependencies, effort, and acceptance criteria, then renders them.

Render a backlog to review-ready output any time:

```bash
python3 -m ticketly.render backlogs/<project>.json --format both --out-dir build/
```

This validates the backlog against the schema **and runs the integrity checks** first, then writes `build/<project>.md` (epic-grouped table + Build order) and `build/<project>.csv` (universal tracker import). A backlog with any integrity error is refused.

For **Notion**, add `--format notion` (or `--format all`) to also write `build/<project>.notion.csv`, laid out for Notion's CSV import (title-first, parent as `Epic`, dependencies as a multi-select). To check a backlog without rendering:

```bash
python3 -m ticketly.validate backlogs/<project>.json
```

## What it does and doesn't do

Ticketly is meant to be safe to run on any of your projects:

- **Runs entirely on your machine.** No network calls, no telemetry, nothing is sent anywhere.
- **No credentials.** It uses no API keys and never asks for any secrets.
- **Stays in your folder.** It only reads the engine's bundled data and reads/writes the folder you run it in (`profiles/`, `backlogs/`, `build/`).
- **`install.sh` is the whole setup** — it installs the Python package locally (`pip install -e .`) and copies the `/ticketly` skill into your Claude Code skills directory. No `sudo`, no remote scripts.

## Conventions

- **IDs:** epics are `EPIC-<PREFIX>` (e.g. `EPIC-REL`); tasks inherit the prefix as `<PREFIX>-NNN` (e.g. `REL-002`). The prefix groups a theme; `parent` links a task to its epic.
- **Effort:** Fibonacci story points (1, 2, 3, 5, 8, 13). Epics are `0` — they are sized by their children.
- **Company & project are user-supplied.** Every backlog records the `company` and `project` it is for. Ticketly asks for these and never invents them.
- **Guardrail:** Ticketly never invents requirements. If something is unspecified, the ticket is flagged `needs_clarification` instead of hallucinating scope.

## Roadmap

1. **Phase 1** ✅ — generator command + Markdown and CSV renderers.
2. **Phase 2** ✅ — per-project house-style config + few-shot examples.
3. **Phase 3** ✅ — dependency validation, build-order view, dedupe, plain-English refine loop.
4. **Phase 4** ✅ — Notion export (CSV is already the universal path).
5. **Phase 5** — web UI for a public, open-source release.

## Tests

```bash
python3 -m pytest -q
```
