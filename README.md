<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/Shreyas0786/ticketly/main/assets/ticketly-logo-dark.png">
  <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/Shreyas0786/ticketly/main/assets/ticketly-logo-light.png">
  <img alt="Ticketly" src="https://raw.githubusercontent.com/Shreyas0786/ticketly/main/assets/ticketly-logo-light.png" width="340">
</picture>

**Turn a messy project idea into a clean, structured backlog — without leaving Claude Code or Codex.**

[![PyPI downloads](https://static.pepy.tech/badge/ticketly)](https://pepy.tech/project/ticketly)

[Website](https://ticketly-growth.vercel.app/) ·
[Install guide](https://ticketly-growth.vercel.app/install) ·
[Codex guide](https://ticketly-growth.vercel.app/codex) ·
[Claude Code guide](https://ticketly-growth.vercel.app/claude-code) ·
[Post-MVP example](https://ticketly-growth.vercel.app/guides/post-mvp-codebase-to-next-release-backlog)

</div>

**Ticketly is a command-line tool that turns a project idea, spec, or existing codebase into a
structured backlog of tickets — epics broken into tasks, each with a description, acceptance
criteria, an effort estimate, and dependencies — exported to Markdown, CSV, or Notion.** It runs
inside Claude Code or Codex on your existing subscription: no API key, no cost per run.

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
- **Sizes work your way** — hours-based points (standard hours × a difficulty multiplier, calculated
  and explained) or Fibonacci points, with owners, review-before-Done, and per-person totals.
- **Full or MVP** — you choose whether to plan everything or just enough for a first version (it
  lists whatever it sets aside).
- **Works out of the box** — exports to Markdown (to review), CSV (any tracker), and Notion — and
  imports your edited CSV or Notion export back.

## How it works

Ticketly runs **inside your AI coding agent — Claude Code or Codex — using your existing
subscription, with no separate Ticketly API key or Ticketly usage charge.** You talk; the agent
does the reasoning; a small local engine handles the exact, repeatable parts (validation and
exporting). A full run goes:

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

It writes everything into a single `ticketly/` folder in your current directory:

- `ticketly/tasks.md` — an **agent-ready checklist**: one checkbox per ticket, grouped by epic, with
  dependencies and acceptance criteria inline. Hand this to a coding agent (Claude Code, Cursor) to
  work through, ticking boxes as it goes.
- `ticketly/backlog.md` — a readable backlog. Opens with a plain-language **Your plan** overview
  (where to start, what you can do now vs. later, and how big each area is), then the full tickets
  and a suggested build order.
- `ticketly/backlog.csv` — import into any tracker. Includes a blank **Assignee** column you fill
  in later (in the tracker or Notion), the estimate inputs, and Epic totals. Add Notion with
  `--format notion`. Edited copies can come back in with `ticketly import`.
- `ticketly/.data/` — the machine source-of-truth (`profile.json`, `backlog.json`), tucked away;
  you never need to open these.

You can re-export a backlog any time:

```bash
ticketly render ticketly/.data/backlog.json --format all --out-dir ticketly/
```

## Sizing work: hours-based or Fibonacci points

When a backlog is created, Ticketly asks **once** how to size it, saves the choice in the backlog,
and shows it at the top of every export. If you leave it to Ticketly, it suggests hours-based points.

- **Hours-based points** — every task gets *standard hours* and a *difficulty level*, and Ticketly
  calculates the points:

  ```text
  points = estimated hours × difficulty multiplier   (rounded half-up to one decimal)
  ```

  | Level | Technical requirements | Multiplier |
  | --- | --- | --- |
  | 1 Basic | Established pattern; local change; straightforward verification | 1.00 |
  | 2 Standard | Routine logic, coordination across components, or a well-defined integration | 1.10 |
  | 3 Complex | Complex state, permissions, data migration, compatibility, or recovery | 1.25 |
  | 4 Advanced | Architecture tradeoffs, concurrency, demanding performance, or complex security | 1.40 |

  | Task | Hours | Level | Points |
  | --- | --- | --- | --- |
  | Build three pages using an existing template | 12 | 1 | 12.0 |
  | Implement a conventional API integration | 8 | 2 | 8.8 |
  | Implement complex permission inheritance | 8 | 3 | 10.0 |
  | Fix a concurrency consistency defect | 4 | 4 | 5.6 |

  Standard hours are the active work for a developer who knows the stack and the project:
  implementation + testing + self-review + handoff, in quarter-hour steps (for example 5 + 2 + 0.5 +
  0.5 = 8). Difficulty comes from technical evidence and carries a short reason; a long task isn't
  automatically a hard one. Confidence (high / medium / low) is recorded separately and never
  changes points. Estimates describe the work, never the person doing it. One point is one standard
  hour at level 1 — points are difficulty-weighted, **not** elapsed time.
- **Fibonacci points** — quick relative sizes: 1, 2, 3, 5, 8, 13.

A task that can't be estimated responsibly shows as **Unestimated** and is flagged for
clarification; any total that includes it is marked **partial**. Epic totals are the sum of their
tasks' points (no extra multiplier). The multipliers are a starting calibration: each backlog keeps
the rubric it was estimated with, so a later calibration never quietly rescores existing work.

After Ticketly (or you) edits the backlog, recalculate and record the change:

```bash
ticketly recalc ticketly/.data/backlog.json                             # new or first estimates
ticketly recalc ticketly/.data/backlog.json --reason "Scope added CSV export"   # changed estimates
```

### Moving an existing backlog to hours-based points

Existing Fibonacci backlogs keep working exactly as before. Switching is explicit and needs a reason:

```bash
ticketly switch-model ticketly/.data/backlog.json --to hours --reason "Team adopts hours-based points"
```

Old points can't be converted reliably, so every task keeps its Fibonacci points as a **legacy**
estimate (with its owner and status) and starts Unestimated until it's re-estimated in hours. Legacy and
hours-based totals are always shown separately — never added together.

Tasks that were already **Done** at the switch stay on their legacy points: they're credited to the
owner recorded at the switch (even if the task is reassigned later), they stay out of the hours-based
totals and never make them partial, and they can't be re-estimated — `ticketly recalc` and
`ticketly import` both refuse. If more work turns up on one, add it as a new task.

## Owners, progress and totals

- **Owners** — the `assignee` on each task. Ticketly never invents owners; you set them (in a
  conversation, or in a CSV — see below).
- **Status** — To Do → In Progress → In Review → **Done**. Done means the work was reviewed and meets
  its acceptance criteria.
- **Team totals** — `backlog.md` shows, per person, what they're **assigned** and what is **Done**,
  with standard hours and points in separate columns.
- **Explicit work** — substantial cleanup, integration, client preparation, or a bounded
  investigation can be its own task, counted separately. Ordinary testing and self-review stay
  inside a task's own estimate.
- **History** — every change to an estimate, owner, status or estimation model is recorded on the
  task with its date and reason; earlier estimates are never erased.
- **Full takeovers** — if someone else takes over a task and none of the original owner's work is
  being kept, just reassign it. The change of owner is recorded in the task's history.
- **Partial work** — when someone takes over a task part-way, the finished part stays on the original
  task and the rest becomes a new task with its own owner (a *replaced* split). The original's
  estimate is reduced to the work it keeps; it must keep some, or it's a full takeover. Ticketly then
  holds the whole chain to the original estimate: the original plus every task split from it —
  including later splits and splits of splits — may never total more than the original was estimated
  at before the first split. That stays true after later re-estimates, so the same work is never
  counted twice. If the work genuinely grew, re-estimate with approval:
  `ticketly recalc ticketly/.data/backlog.json --reason "..." --approved-by "<who approved it>"`.
- **New scope** — genuinely new, approved work is recorded as an *additional* split (with who
  approved it when the same person owns both). Fixing your own unfinished work doesn't earn extra
  points.

Ticketly tracks sizes and progress only — there are no rates, budgets, invoices or payments.

## Editing in a spreadsheet or Notion

You can change **owners, status, due dates, priority and estimate inputs** in an exported CSV and
bring them back:

```bash
ticketly render ticketly/.data/backlog.json --format all --out-dir ticketly/
# ...edit ticketly/backlog.csv in a spreadsheet...
ticketly import ticketly/backlog.csv --dry-run     # preview — writes nothing
ticketly import ticketly/backlog.csv               # apply
ticketly render ticketly/.data/backlog.json --format all --out-dir ticketly/
```

- Rows are matched by ticket ID. Column order, extra columns and blank rows don't matter, but keep
  the **baseline** column (`ticketly_baseline`) — it's how Ticketly tells your edits apart from
  values that changed since the export. A CSV without it is refused with instructions.
- A changed estimate needs a short reason in the row's `change_reason` column.
- To change an estimate, edit the breakdown columns (`hours_implementation`, `hours_testing`,
  `hours_self_review`, `hours_handoff`), the difficulty level and reason, or the confidence.
  `estimated_hours` is computed from the breakdown, and points from the hours and level.
- Hours must be finite numbers in quarter hours; difficulty is a whole number from 1 to 4 (`2.0`
  reads as `2`). `NaN`, `Infinity`, fractional levels and other invalid values abort the import.
- Points, estimated hours and totals in a CSV are exported values; Ticketly recalculates them on
  import. Edits to them, or to protected fields such as titles, descriptions and dependencies, are
  ignored with a warning — change those by asking Ticketly.
- **Conflicts:** if you edited something that has also changed in Ticketly since you exported, the
  import stops. Values you didn't touch are simply left as Ticketly has them.
- Any error — an invalid value, an unknown or duplicate ID, a conflict — aborts the whole import and
  nothing is written. A successful import replaces the backlog only after the complete result
  validates; importing the same file again changes nothing.

**Notion.** Export with `--format notion` and import `ticketly/backlog.notion.csv` into Notion. To
bring Notion edits back, export the database from Notion as CSV and run `ticketly import` on it. Only
the same fields come back as from any CSV — owners, status, due dates, priority and estimate inputs.
Edits to protected fields (titles, descriptions, acceptance criteria, dependencies, …) and any
properties you added in Notion are **not** imported. There is no live Notion sync, and Notion's CSV
import only **adds** rows — it never updates existing ones. To refresh Notion after changes in
Ticketly:

1. Export the Notion database as CSV and `ticketly import` it, so its owner, status, date, priority
   and estimate edits are brought in first.
2. Re-render: `ticketly render ticketly/.data/backlog.json --format notion --out-dir ticketly/`.
3. Import the new `backlog.notion.csv` into a **new** Notion database, and keep the original one
   (rename or archive it) as your record of what was there. Never merge the new CSV onto the
   existing database, or every ticket appears twice.

## Starting a project over

Requirements changed and you want a clean slate? Reset this folder's generated files, then re-run
`/ticketly` with the new requirements:

```bash
ticketly reset      # asks before deleting
```

Reset is deliberately careful: it only ever removes Ticketly's own generated files in `ticketly/`
(`tasks.md`, `backlog.md`, `backlog.csv`, `backlog.notion.csv`, and the `.data/` JSONs — CSVs only
when their header is one Ticketly writes), confirms each one with you first,
never touches a file it can't verify as Ticketly's, and never reaches outside the current folder.
Your code and other files are never touched.

## Safe by design

- Ticketly's deterministic validation and export engine runs **entirely on your machine** and adds
  no network calls or telemetry.
- Repository inspection and conversational reasoning happen in Claude Code or Codex, so their data
  handling follows the settings and policies of the agent you use.
- Ticketly uses **no separate API key** and never asks for secrets.
- The local engine only reads/writes the folder you run it in. `ticketly install` just copies the
  Claude Code skill and/or appends a Codex pointer into your agent's config — no `sudo`, no remote
  scripts.

## FAQ

### How do I generate tickets from a PRD or spec?

Install Ticketly, open the folder with your spec, and run `/ticketly` in Claude Code (or say "use
Ticketly" in Codex). Describe or paste the spec, answer its questions, and it writes a full backlog
to `ticketly/` — epics, tickets, acceptance criteria, hours-based or Fibonacci points, and
dependencies.

### How do I turn an existing codebase into a backlog?

Run `/ticketly` inside the repo. It reads the code, infers the stack, and plans the work that's
*left* — TODOs, half-built features, missing tests — rather than re-planning what already exists.

### Can I import the tickets into Jira, Linear, or Notion?

Yes. Ticketly exports `ticketly/backlog.csv`, which imports into any tracker that accepts CSV
(Jira, Linear, Asana, Trello). For Notion, use `--format notion`. There's a blank **Assignee**
column you fill in on the tracker side, and edited CSVs (including Notion exports) can be imported
back with `ticketly import` — see [Editing in a spreadsheet or Notion](#editing-in-a-spreadsheet-or-notion).

### Does Ticketly need an API key or a paid plan?

No. It runs inside Claude Code or Codex using the subscription you already have — no separate
Ticketly API key, and no Ticketly usage charge. Ticketly's own engine adds no network calls; the
conversation runs through your coding agent and follows that agent's data handling.

### How is this different from just asking Claude to write tickets?

Ad-hoc prompting gives you a different shape of output every time, invents details it doesn't know,
and doesn't validate anything. Ticketly runs a fixed interview, refuses to guess (it flags
undecided things for clarification instead of making them up), validates the result against a
schema, and exports the same clean structure every run.

### Can a coding agent work through the tickets?

Yes — that's what `ticketly/tasks.md` is for. It's a checklist with one checkbox per ticket,
dependencies and acceptance criteria inline. Hand it to Claude Code or Cursor and it can tick them
off as it goes.

## Contributing & Feedback

**Ticketly does not accept outside code contributions.** It's source-visible so you can read and
use it, but it's developed solely by the author — **pull requests are not accepted and will be
closed unmerged.** Please don't open one.

What *is* genuinely welcome — and the best way to help — is **bug reports, feature requests, and
feedback**. Open a [GitHub Issue](https://github.com/Shreyas0786/ticketly/issues) (there are short
templates for bugs and features); see
[CONTRIBUTING.md](https://github.com/Shreyas0786/ticketly/blob/main/CONTRIBUTING.md) for the full
policy and the [LICENSE](https://github.com/Shreyas0786/ticketly/blob/main/LICENSE) for usage terms.

## Security

Found a security issue? **Please don't open a public issue** — report it privately via the
repository's **Security** tab ("Report a vulnerability"). See
[SECURITY.md](https://github.com/Shreyas0786/ticketly/blob/main/SECURITY.md) for details.

---

_Development: from a repo checkout, `./install.sh all` does an editable install and wires both
agents. Run the test suite with `python3 -m pytest -q`._
