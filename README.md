# Ticketly

**Turn a messy project idea into a clean, structured backlog — without leaving Claude Code.**

Describe what you're building, and Ticketly breaks it into professional tickets: big areas split
into individual tasks, each with a clear description, acceptance criteria, an effort estimate, and
dependencies — ready to drop into Notion or any tracker.

## Who it's for

Anyone planning a project who wants a real backlog instead of a blank page — **technical or not.**
It talks in plain language, explains anything it asks, and never makes you learn jargon. If you can
describe your idea, you can use it.

## What it does

- **Plans the whole project** — turns your idea or spec into epics (big areas) broken into tickets.
- **Asks, never guesses** — if something isn't decided (which database? which host?), it flags the
  ticket for clarification instead of making something up. Nothing is invented.
- **Matches a real PM's style** — short, clear titles; one-line descriptions; testable acceptance
  criteria; sensible effort sizing.
- **Full or MVP** — you choose whether to plan everything or just enough for a first version (it
  lists whatever it sets aside).
- **Works out of the box** — exports to Markdown (to review), CSV (any tracker), and Notion.

## How it works

Ticketly runs **inside Claude Code, using your existing subscription — no API key, no cost per run.**
You talk; it does the planning; a small local engine handles the exact, repeatable parts
(validation and exporting). A full run goes:

1. **Start** — you give your company and project. (It never guesses these.)
2. **Discuss** — you talk through what you're building and your tech stack, conversationally.
3. **Areas** — it proposes a few main areas for your project and you confirm or tweak them.
4. **Scope** — you pick a full backlog or a lean MVP.
5. **Generate** — it writes the tickets, checks them for problems, and exports the results into
   your project folder.

You can stop after any step and pick up later, and refine anything in plain English afterwards
("split this ticket", "add acceptance criteria", "we're using Postgres", "drop image upload").

## Install

Install once, from the Ticketly repo:

```bash
./install.sh
```

That's the whole setup. From then on, `/ticketly` works in **any** folder — even an empty new
project that doesn't contain this code.

**To update later, just `git pull` in this repo.** No reinstall.

> Requirements: [Claude Code](https://claude.com/claude-code) (logged in) and Python 3.10+.

## Using it

1. Open **any** folder in Claude Code — your project, even an empty one.
2. Type **`/ticketly`**.
3. Describe your project and answer its questions.

It writes everything into your current folder:

- `profiles/<project>.json` — what it learned about your project (reused on later runs).
- `backlogs/<project>.json` — the generated tickets.
- `build/<project>.md` — a readable backlog with a suggested build order.
- `build/<project>.csv` — import into any tracker. Add Notion with `--format notion`.

You can re-export a backlog any time:

```bash
python3 -m ticketly.render backlogs/<project>.json --format all --out-dir build/
```

## Safe by design

- Runs **entirely on your machine** — no network calls, no telemetry, nothing sent anywhere.
- Uses **no API keys** and never asks for secrets.
- Only reads/writes the folder you run it in. `install.sh` just installs a local Python package
  and links the skill — no `sudo`, no remote scripts.

---

_Development: run the test suite with `python3 -m pytest -q`._
