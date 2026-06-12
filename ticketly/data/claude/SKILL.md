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
  ticketly home
  ```

  Call the printed path `ENGINE`. **Read** the schemas, `ENGINE/house-style/default.json`,
  `ENGINE/examples/house-style-backlog.json`, and `ENGINE/archetypes/archetypes.json` from there
  by absolute path.

- **The current folder** — wherever the user launched Claude Code; their project. **Write**
  everything here: `./profiles/<slug>.json`, `./backlogs/<slug>.json`, `./build/`. Each folder
  is a fresh project with its own profile.

If `ticketly home` fails ("command not found"), Ticketly isn't installed — tell the user to
run the one-time `pipx install ticketly && ticketly install claude` (or `pip install ticketly`),
then retry.

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

**First, read the folder, then decide.** Don't classify on a filename alone — look at what's
actually there, then pick the mode:

- **New / greenfield** — the folder is empty, or holds only docs/specs (a `.md`/`.txt`/`.pdf`
  requirements or README, planning notes). **Docs alone are not an existing project** — a spec is
  the normal greenfield input. Follow step 1 below, then Discuss → Distill (steps 2–3).
- **Existing project** — the folder contains real **code**: a manifest (`package.json`,
  `requirements.txt`, `pyproject.toml`, `go.mod`, `Cargo.toml`, `pom.xml`, …) **or** an actual
  source tree (a `src/`, modules, components — architecture you can read). Use **step 1b** instead —
  scan the repo rather than interrogating the user, and skip the company question.
- **Unsure / mixed** (e.g. a lone spec next to a stray script) — don't guess. Ask one plain
  question: *"Is this a fresh start, or an existing codebase you'd like tickets for?"* and let the
  answer pick the mode.

Every folder gets its own profile. For a **new** project, ask the user for the two things Ticketly
never invents:

- **Company / organization** — whoever the work is for. If it's a personal or unnamed project,
  that's fine — they can use their own name or the project name.
- **Project** — what they're building.

Ask plainly and wait for their answer. **Do not pre-fill or suggest a real company name** (from
their email, account, git, or a spec). Use "Demo Company / Demo Project" only in this guide's
examples, never as a real value.

### 1b. Existing project — scan, don't interrogate

When the current folder already has code, don't run the greenfield interview. Read the repo and
let it tell you what the project is, then plan **what's next** — not a re-description of what's
already built.

**Skip the company question entirely.** On an existing project, asking "what company is this for?"
is awkward and adds nothing — `company` is now optional, so leave it out. The backlog is titled by
its project name alone (`# <Project> backlog`). Take the project name from the repo (its folder
name, or the `name` field in a manifest) and confirm it in one line — that's the only identity
question. **Never scrape a *company* name** from `package.json`/`pyproject.toml` author fields,
`LICENSE`, git config, or the repo name; the never-invent rule applies harder here, not softer.

1. **Auto-draft the profile by reading, not guessing.** Reading the repo is not inventing:
   - `stack` — from the manifests and config: dependencies, language/runtime, framework, database
     drivers, infra files (`Dockerfile`, CI workflows, `fly.toml`, etc.). Record only what the
     files actually show.
   - `architecture.components` — from the directory layout and entrypoints (the web app, the API
     service, the worker, the shared package, …), in plain names.
   - `prefixes` — suggest from the house-style `prefix_vocab`, filtered to the areas the code
     actually has.
2. **Confirm the drafted profile with the user — in plain language.** Show what you inferred ("Looks
   like a Next.js web app + a FastAPI backend on Postgres — that right?") and let them correct it
   before you save. Anything the code can't tell you (intended scope, priorities, what's
   half-finished on purpose) → **ask, don't guess.** Then save and validate the profile exactly as
   in step 3 (`ticketly profile profiles/<slug>.json`).
3. **Find the forward-looking work.** Scan for real signals of what's left to do, and surface what
   you found before writing tickets:
   - `TODO` / `FIXME` / `HACK` / `XXX` markers in the code.
   - Stubbed or empty functions, `NotImplementedError`, placeholder/`pass`-only bodies, empty UI
     screens.
   - Modules or features with no corresponding tests; missing docs for a public surface.
   - Half-wired features (a route with no handler, a button with no action, a config flag never read).
4. **Generate tickets for what's next**, not a catalogue of what exists. Each ticket is real
   forward work: finish the half-built feature, add the missing tests, wire the stub, document the
   public API. Then continue with **step 4 (Choose the scope)** onward — for an existing project,
   frame the scope choice as *"just the TODOs and gaps"* vs *"everything I'd plan next"* — then
   generate, self-check, check integrity, and render exactly as in steps 5–8.

### 2. Discuss (free-form)

Talk through the project with the user: what it is, how the pieces fit together, key constraints.
This is a conversation, not a form — ask 2–4 focused questions at a time, don't interrogate. The
goal is to understand the system well enough to write sharp tickets.

**If the user already has a stack, capture it — don't second-guess it.** On an **existing project**
(§1b) the stack comes from the code; name the archetype if it helps frame the work, but never push a
different stack on a running app.

**When the user is building something new and hasn't settled on a stack, be a guide, not a stenographer.**
Most builders — especially non-technical ones — don't know what to ask for, so the generic default
("React and a backend later") wins by silence. Don't let it. Read `ENGINE/archetypes/archetypes.json`
and use it:

1. **Classify the archetype** from how they describe the project, using each entry's `signals`
   (e.g. "two kinds of users who exchange money" → `marketplace`). If it's genuinely unclear between
   two, ask one plain question to decide. Don't announce the jargon id — say "sounds like a marketplace."
2. **Ask only the forking question(s).** Each archetype lists `branch_questions` — the one or two
   things that actually change the recommendation (e.g. mobile: "iPhone only, or Android too?"). Ask
   those, nothing more. This is the intelligence: a couple of sharp questions, not an interrogation.
3. **Recommend free-first, with the reasoning and a real alternative.** Pick the `option` whose `when`
   matches their answers and present it in plain language: the `stack`, **why** it fits (`why`), and a
   genuine `alternative` with *when you'd choose it instead*. Lead with the cheapest path that works —
   honour the `cost` field: `free`/`freemium` are fine to present as "start at $0"; for `paid`, **say so
   plainly** ("this one isn't free — here's why, and the cheapest real alternative"). Never pretend a
   paid path is free.
4. **Never skip the backend.** Walk the archetype's `backend_checklist` even on the simplest tier —
   the data store, login, payments/payouts, jobs, storage. This is the gap that generic answers leave;
   surfacing it (in plain words, with the *why*) is the whole point.
5. **Keep it theirs.** Recommend, don't impose. Offer the low-effort path ("if you're unsure, this is a
   sensible default — nothing's locked"). If they want something different, capture what they choose.

The stack the user lands on (and the archetype id) flows into the profile in the next step.

### 3. Distill into a profile

When the user is ready (e.g. "save the profile", "distill", "looks good"), write what you learned
to `./profiles/<project-slug>.json` in the current folder, conforming to the profile schema:

- `stack` — only the layers the user named or accepted (including any you recommended in Discuss and
  they agreed to). Leave a layer out if there's nothing for it.
- `architecture.components` — the major moving parts, in their words.
- `archetype` — optional: the matched archetype id (e.g. `marketplace`, `ai-app`) when you recommended
  a stack during Discuss. Omit it on an existing-project run where the stack was read from the code.
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
ticketly profile profiles/<slug>.json
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

### 6. Self-check — re-read your own backlog before showing it

Before you check integrity or show anything, re-read the backlog you just wrote as if a skeptical
PM handed it to you, and **fix** what's weak — don't just note it. A non-technical builder can't
tell when a plan is missing something obvious; that blank-page fear is exactly what they came to
escape. Catching your own gaps is what makes the plan trustworthy, and trust is the product. Walk
this checklist:

1. **Every Task has at least one *testable* acceptance criterion** — a condition you could tick
   off, not a restatement of the title. Vague phrases ("works well", "is fast", "user-friendly",
   "handles errors gracefully") aren't checkable; rewrite them as something verifiable.
2. **No missing dependencies** — if Task B can't start until Task A is done, B must list A in
   `dependencies`. Read the actual work, not just the titles (login before profile editing, a
   schema before the API that reads it, infra before the service that runs on it).
3. **No obvious gaps** — a happy path usually implies setup, error/empty states, and a way to
   verify it. If the requirements clearly need a step you didn't write, add it.
4. **Effort is sane against the rubric** — a Task with five acceptance criteria sized `1`, or a
   one-line change sized `13`, is probably miscalibrated. Re-size against the `effort_rubric`.
5. **Every area has real work** — no empty epic, no Task orphaned from its epic.
6. **Anything still underspecified is flagged** `needs_clarification: true`, never quietly guessed.

Fix what you find before continuing. Don't show the user a draft you already know has holes.

### 7. Check integrity & dedupe

Before rendering, run the integrity checker — it catches what the schema can't:

```bash
ticketly validate backlogs/<slug>.json
```

It reports **errors** (duplicate IDs, dependencies pointing at missing tickets, a Task parented
to a non-epic, an epic sized above 0, circular dependencies, a Task with no acceptance criteria
that isn't flagged `needs_clarification`) and **warnings** (tickets that share a title — a likely
duplicate). **Fix every error before continuing** — the renderer will refuse a backlog that has
any. For each warning, do a real **dedupe pass**: decide whether the flagged tickets are genuinely
the same work and, if so, merge them (keep one ID, union the acceptance criteria and dependencies,
repoint anything that depended on the dropped ID). Don't merge things that merely sound alike.

### 8. Render

```bash
ticketly render backlogs/<slug>.json --format both --out-dir build/
```

This re-checks integrity, then writes `./build/<slug>.md` (epic-grouped, with a topologically
sorted **Build order** section, review-ready) and `./build/<slug>.csv` (universal tracker import)
into the current folder. Show the user the Markdown.

Both CSVs carry a blank **Assignee** column — Ticketly never invents owners; the user (or their
team) fills it in later in the tracker.

When the user wants to import into **Notion**, add `--format notion` (or `--format all` for
everything). It writes `./build/<slug>.notion.csv`, laid out for Notion import: the title leads
(Notion's page title), `Epic` holds the parent, `Dependencies` are comma-separated for a
multi-select, acceptance criteria are one per line, and `Assignee` is left empty to fill in. Tell the user to use Notion's
**Import → CSV → Merge with CSV** into a database, then convert `Status`/`Dependencies` to the
property types they want.

## Refine

Generation is a loop, not a one-shot. After rendering, the user edits in plain English —
"split WEB-003 into two", "add acceptance criteria to API-005", "re-estimate INF-002",
"merge these two", "re-order by dependency", "drop the AUTH epic". For each request:

1. Apply the edit to `./backlogs/<slug>.json`, keeping IDs stable (a split mints new sequential
   IDs; a merge drops one and repoints its dependents).
2. Re-run `ticketly validate backlogs/<slug>.json` and fix anything it flags.
3. Re-render and show the updated Markdown.

Don't aim for one-shot perfection — make the change the user asked for, keep the backlog valid,
and show the result.

## Conventions (locked)

- **IDs:** epics `EPIC-<PREFIX>`; tasks `<PREFIX>-NNN`. Prefix = epic theme; children inherit it.
- **Effort:** Fibonacci points only (1, 2, 3, 5, 8, 13). Epics are `0`, sized by their children.
- **Schema is the source of truth.** Backlogs validate against `ENGINE/schema/ticket.schema.json`,
  profiles against `ENGINE/profile/profile.schema.json`, the house style against
  `ENGINE/house-style/house-style.schema.json`, and the archetype library against
  `ENGINE/archetypes/archetypes.schema.json`. The `ticketly validate`, `ticketly profile`,
  `ticketly render`, and `ticketly archetypes` commands load these for you — you do not need to pass
  the schema path.
