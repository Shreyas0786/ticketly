# Ticketly

**Turn a messy project idea into a clean, structured backlog — without leaving Claude Code or Codex.**

Describe what you're building, and Ticketly breaks it into professional tickets: big areas split
into individual tasks, each with a clear description, acceptance criteria, an effort estimate, and
dependencies — ready to drop into Notion or any tracker.

## Who it's for

Anyone planning a project who wants a real backlog instead of a blank page — **technical or not.**
It talks in plain language, explains anything it asks, and never makes you learn jargon. If you can
describe your idea, you can use it.

## What it does

- **Plans the whole project** — turns your idea or spec into epics (big areas) broken into tickets.
- **Works on existing codebases too** — point it at a repo and it reads the code, infers the stack,
  and plans the work that's *left* (TODOs, half-built features, missing tests) instead of starting
  from a blank page. No company name needed for these — the backlog is titled by your project.
- **Suggests a tech stack that fits — not the same generic answer every time** — if you're not sure
  what to build with, it works out *what kind* of project yours is (marketplace, mobile app, online
  store, AI app…) and recommends a fitting stack, **free options first**, with plain-language reasons
  and a real alternative for each — and it never quietly skips the backend (database, logins,
  payments, storage). Already have a stack? It just uses yours.
- **Asks, never guesses** — if something isn't decided (which database? which host?), it flags the
  ticket for clarification instead of making something up. Nothing is invented.
- **Matches a real PM's style** — short, clear titles; one-line descriptions; testable acceptance
  criteria; sensible effort sizing.
- **Full or MVP** — you choose whether to plan everything or just enough for a first version (it
  lists whatever it sets aside).
- **Works out of the box** — exports to Markdown (to review), CSV (any tracker), and Notion.

## How it works

Ticketly runs **inside your AI coding agent — Claude Code or Codex — using your existing
subscription, no API key, no cost per run.** You talk; it does the planning; a small local engine
handles the exact, repeatable parts (validation and exporting). A full run goes:

1. **Start** — you give your project (and company, if you want one in the title). It never guesses
   these. **On an existing repo it skips this and reads the code instead** — no company needed.
2. **Discuss** — you talk through what you're building and your tech stack, conversationally. If you
   don't have a stack in mind, it recommends one that fits your kind of project (free options first,
   with reasons and alternatives). (For an existing repo it drafts this from the code and just asks
   you to confirm.)
3. **Areas** — it proposes a few main areas for your project and you confirm or tweak them.
4. **Scope** — you pick a full backlog or a lean MVP.
5. **Generate** — it writes the tickets, checks them for problems, and exports the results into
   your project folder.

You can stop after any step and pick up later, and refine anything in plain English afterwards
("split this ticket", "add acceptance criteria", "we're using Postgres", "drop image upload").

## Install

Install Ticketly once from PyPI, then wire up the agent you use. **pipx** is recommended — it keeps
Ticketly isolated and always on your PATH, so it works no matter which Python your agent runs:

```bash
pipx install ticketly        # (or: pip install ticketly)
ticketly install all         # wire up Claude Code and/or Codex
```

Pick just one agent if you prefer:

```bash
ticketly install claude      # Claude Code (the /ticketly skill)
ticketly install codex       # Codex ("use Ticketly" in any session)
ticketly install all         # both
```

That's the whole setup. From then on, Ticketly works in **any** folder — even an empty new project.
Install both agents if you like; they don't clash.

> Requirements: Python 3.10+, and either [Claude Code](https://claude.com/claude-code) or
> [Codex](https://developers.openai.com/codex/cli) (logged in). **No API key.**

## Updating

```bash
pipx upgrade ticketly         # or: pip install -U ticketly
```

That's it — the bundled skill and Codex pointer update with the package. (Re-run
`ticketly install all` only if you want to refresh the agent front-doors immediately.)

## Using it

1. Open **any** folder — a blank one to plan from scratch, or an existing repo to plan the work
   that's left.
2. Start Ticketly:
   - **In Claude Code** — type **`/ticketly`**.
   - **In Codex** — run `codex`, then say **"use Ticketly"**.
3. Describe your project and answer its questions — or, on an existing repo, just confirm what it
   read from the code.

It writes everything into your current folder:

- `profiles/<project>.json` — what it learned about your project (reused on later runs).
- `backlogs/<project>.json` — the generated tickets.
- `build/<project>.md` — a readable backlog with a suggested build order.
- `build/<project>.csv` — import into any tracker. Includes a blank **Assignee** column you fill
  in later (in the tracker or Notion). Add Notion with `--format notion`.

You can re-export a backlog any time:

```bash
ticketly render backlogs/<project>.json --format all --out-dir build/
```

## Starting a project over

Requirements changed and you want a clean slate? Reset a project's generated files, then re-run
`/ticketly` with the new requirements:

```bash
ticketly reset <project>      # asks before deleting; --all resets every project here
```

Reset is deliberately careful: it only ever removes Ticketly's own generated files for that project
(`profiles/<project>.json`, `backlogs/<project>.json`, and `build/<project>.*`), confirms each one
with you first, never touches a file it can't verify as Ticketly's, and never reaches outside the
current folder. Your code and other files are never touched.

## Safe by design

- Runs **entirely on your machine** — no network calls, no telemetry, nothing sent anywhere.
- Uses **no API key** and never asks for secrets.
- Only reads/writes the folder you run it in. `ticketly install` just copies the Claude Code skill
  and/or appends a Codex pointer into your agent's config — no `sudo`, no remote scripts.

---

_Development: from a repo checkout, `./install.sh all` does an editable install and wires both
agents. Run the test suite with `python3 -m pytest -q`._
