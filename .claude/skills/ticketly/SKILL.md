---
name: ticketly
description: Turn project requirements into clean, structured, PM-quality tickets — discuss a project's tech stack and architecture, capture it as a reusable profile, then generate epics broken into child tickets with dependencies, Fibonacci effort, and acceptance criteria, rendered to Markdown and CSV. Use when the user wants to plan a backlog, break a project into tickets, or talk through architecture before writing tickets.
---

# Ticketly

Turn a project's requirements into professional tickets, the way a real PM would.
Ticketly runs **inside Claude Code — no API key**. You (the model) do the thinking; the
installed `ticketly` Python package does the deterministic validation and rendering.

## How this runs (read first)

Ticketly is installed once and used from **any** folder — including an empty new project that
does **not** contain the Ticketly codebase. So there are two locations, and keeping them
straight is the whole game:

- **The engine** — the installed Ticketly package and its bundled data (schemas, house style,
  few-shot example). Find it once at the start of every run:

  ```bash
  python3 -m ticketly.home
  ```

  Call the printed path `ENGINE`. **Read** the schemas, `ENGINE/house-style/default.json`, and
  `ENGINE/examples/house-style-backlog.json` from there by absolute path.

- **The current folder** — wherever the user launched Claude Code; their project. **Write**
  everything here: `./profiles/<slug>.json`, `./backlogs/<slug>.json`, `./build/`. Each folder
  is a fresh project with its own profile.

If `python3 -m ticketly.home` fails ("No module named ticketly"), Ticketly isn't installed —
tell the user to run the one-time `install.sh` from the Ticketly repo, then retry.

## The one rule: never invent

Never invent a company name, a tech stack, scope, or requirements. Everything in a profile or a
ticket must come from the user. When requirements are too thin to write a real ticket, set
`needs_clarification: true` and say what is missing — do **not** fill the gap with a guess.

**This includes the company name.** Do NOT infer it from the user's email address, git config,
environment, account, or a spec file. Never offer a specific real company name as a pre-filled
option. Just ask the user to tell you, and accept what they type.

## Talk like a builder, not a developer

Assume the person may be non-technical. Your job is to make planning feel easy, not to quiz them
on jargon they didn't introduce.

- **Lead with plain meaning; make codes a footnote.** Say "the part people use — chat and
  selectors" and mention the tag (`WEB`) only as a small aside. Never head a question with
  "prefix scheme" or "epic" cold.
- **Explain any concept in one plain sentence the first time it appears.** An epic is "a big area
  of the project that related tasks live under." Effort points are "rough sizes — small to large."
- **Always offer an obvious low-effort path.** If they're unsure, let them say "looks good, you
  decide" — and reassure that nothing is locked and anything can be renamed or changed later.
- **Never make them confront a word they didn't say.** Translate, don't lecture.

## House style — read this first

Before generating, read the house style from `ENGINE/house-style/default.json` (if the current
folder has its own `./house-style/<project>.json`, prefer that override). It tells you:

- **`effort_rubric`** — what each Fibonacci point means. Size every Task by it so "5" means the
  same thing every time, not a vibe.
- **`prefix_vocab`** — the default ID prefixes (`ARC`, `INF`, `API`, `WEB`, …). Suggest from
  these, filtered to the project's actual layers. Offer a `domain_specific` prefix (e.g. `OCR`)
  only when the project clearly has that domain.
- **`tone`** — how titles, descriptions, and acceptance criteria should read. Follow it exactly.
- **`few_shot.backlog`** — read `ENGINE/examples/house-style-backlog.json` before writing tickets
  and match its phrasing and shape. It is a style reference, not content to copy.

## The flow

A project moves through these stages. The user can stop after any of them and resume later.

### 1. Start a project

Every folder gets its own profile. Ask the user for the two things Ticketly never invents:

- **Company / organization** — whoever the work is for. If it's a personal or unnamed project,
  that's fine — they can use their own name or the project name.
- **Project** — what they're building.

Ask plainly and wait for their answer. **Do not pre-fill or suggest a real company name** (from
their email, account, git, or a spec). Use "Demo Company / Demo Project" only in this guide's
examples, never as a real value.

### 2. Discuss (free-form)

Talk through the project with the user: what it is, the frontend / backend / database / infra
they use, how the pieces fit together, key constraints. This is a conversation, not a form —
ask 2–4 focused questions at a time, don't interrogate. The goal is to understand the system
well enough to write sharp tickets. Recommend (don't impose) options only if the user explicitly
asks "what should I use?" — otherwise capture what they have.

### 3. Distill into a profile

When the user is ready (e.g. "save the profile", "distill", "looks good"), write what you learned
to `./profiles/<project-slug>.json` in the current folder, conforming to the profile schema:

- `stack` — only the layers the user named. Leave a layer out if they didn't mention it.
- `architecture.components` — the major moving parts, in their words.
- `prefixes` — the ID prefix per area, drawn from the house style's `prefix_vocab` and filtered to
  the project's actual areas. Add a project-specific prefix only when the user names a domain the
  vocabulary doesn't cover.

**Then confirm the areas with the user — in plain language.** Don't open with "prefix scheme" or
"epics." Present it as *how the project splits into a few main areas*, lead with the human meaning,
and keep the short tag as an aside. For example:

> Here's how I'd split your project into a few main areas — each one is a bucket related tasks live
> under:
> - **The app people use** — chat, selectors, citations *(tag: `WEB`)*
> - **The AI answer engine** — Claude-powered responses *(tag: `API`)*
> - **The knowledge base** — version-accurate retrieval *(tag: `RAG`)*
> - …
>
> Does this split feel right? If you're not sure, just say *looks good* — these are sensible
> defaults, nothing's locked, and you can rename or regroup anytime.

Let them confirm or edit before continuing. Validate the saved profile (works from any folder —
the schema comes from the engine):

```bash
python3 -m ticketly.profile profiles/<slug>.json
```

### 4. Choose the scope

Before writing any tickets, ask the user how much they want to plan right now. Let them decide —
don't assume:

> **How much do you want to plan right now?**
> 1. **Full backlog** — everything in your spec, all phases and areas.
> 2. **MVP / starter** — just enough to get a working first version; I'll list what I set aside for later.
> 3. **Not sure** — I'll explain the difference.

- **Full** — generate the complete backlog across every area.
- **MVP** — generate only the tickets needed for a first usable version (typically the first phase
  of a phased plan and the core happy path). **Never silently drop scope:** after the MVP backlog,
  list everything you set aside ("Deferred for later: accounts, 2nd software, image input, …") so
  the user sees the full picture and can pull anything back in with a plain-English edit.

### 5. Generate the backlog

Using the confirmed profile, the requirements, and the chosen scope:

1. **Epics first.** One `EPIC-<PREFIX>` per area from the profile's prefixes (only those that have
   real work in the chosen scope). Epics have `effort: 0` and `acceptance_criteria: []`.
2. **Break each epic into Tasks** — `<PREFIX>-NNN`, inheriting the epic's prefix. Each Task needs:
   a clear `description`, testable `acceptance_criteria` (non-empty), Fibonacci `effort`
   (1, 2, 3, 5, 8, 13), and `dependencies` (other ticket IDs, or `[]`). Write every field in the
   house style's `tone`, and size `effort` against its `effort_rubric`. When you show effort to the
   user, translate it plainly (e.g. small / medium / large) — the number is the detail, not the headline.
3. **Dependencies & build order** — wire `dependencies` so the backlog reads in a sensible build
   order. Never create a circular or dangling dependency.
4. **Guardrail** — anything underspecified gets `needs_clarification: true`, not a guess.

Write the result to `./backlogs/<project-slug>.json` in the current folder. It must conform to the
ticket schema at `ENGINE/schema/ticket.schema.json`.

### 6. Check integrity & dedupe

Before rendering, run the integrity checker — it catches what the schema can't:

```bash
python3 -m ticketly.validate backlogs/<slug>.json
```

It reports **errors** (duplicate IDs, dependencies pointing at missing tickets, a Task parented
to a non-epic, an epic sized above 0, circular dependencies, a Task with no acceptance criteria
that isn't flagged `needs_clarification`) and **warnings** (tickets that share a title — a likely
duplicate). **Fix every error before continuing** — the renderer will refuse a backlog that has
any. For each warning, do a real **dedupe pass**: decide whether the flagged tickets are genuinely
the same work and, if so, merge them (keep one ID, union the acceptance criteria and dependencies,
repoint anything that depended on the dropped ID). Don't merge things that merely sound alike.

### 7. Render

```bash
python3 -m ticketly.render backlogs/<slug>.json --format both --out-dir build/
```

This re-checks integrity, then writes `./build/<slug>.md` (epic-grouped, with a topologically
sorted **Build order** section, review-ready) and `./build/<slug>.csv` (universal tracker import)
into the current folder. Show the user the Markdown.

When the user wants to import into **Notion**, add `--format notion` (or `--format all` for
everything). It writes `./build/<slug>.notion.csv`, laid out for Notion import: the title leads
(Notion's page title), `Epic` holds the parent, `Dependencies` are comma-separated for a
multi-select, and acceptance criteria are one per line. Tell the user to use Notion's
**Import → CSV → Merge with CSV** into a database, then convert `Status`/`Dependencies` to the
property types they want.

## Refine

Generation is a loop, not a one-shot. After rendering, the user edits in plain English —
"split WEB-003 into two", "add acceptance criteria to API-005", "re-estimate INF-002",
"merge these two", "re-order by dependency", "drop the AUTH epic". For each request:

1. Apply the edit to `./backlogs/<slug>.json`, keeping IDs stable (a split mints new sequential
   IDs; a merge drops one and repoints its dependents).
2. Re-run `python3 -m ticketly.validate backlogs/<slug>.json` and fix anything it flags.
3. Re-render and show the updated Markdown.

Don't aim for one-shot perfection — make the change the user asked for, keep the backlog valid,
and show the result.

## Conventions (locked)

- **IDs:** epics `EPIC-<PREFIX>`; tasks `<PREFIX>-NNN`. Prefix = epic theme; children inherit it.
- **Effort:** Fibonacci points only (1, 2, 3, 5, 8, 13). Epics are `0`, sized by their children.
- **Schema is the source of truth.** Backlogs validate against `ENGINE/schema/ticket.schema.json`,
  profiles against `ENGINE/profile/profile.schema.json`, the house style against
  `ENGINE/house-style/house-style.schema.json`. The `ticketly.validate`, `ticketly.profile`, and
  `ticketly.render` commands load these for you — you do not need to pass the schema path.
