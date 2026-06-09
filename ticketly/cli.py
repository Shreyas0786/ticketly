"""Ticketly command-line entry point — the single ``ticketly`` front door.

Installed on PATH via ``pip``/``pipx``, so it always runs under the exact
interpreter Ticketly was installed into. That is what makes it robust where
``python3 -m ticketly...`` is not: a calling agent's shell may resolve a
different ``python3`` (a venv, conda, the system one) that has no ``ticketly``
installed. A console script carries its own interpreter and sidesteps that trap.

Subcommands::

    ticketly home                       print the engine's bundled-data path (ENGINE)
    ticketly render   BACKLOG [opts]    render a backlog to Markdown/CSV/Notion
    ticketly validate BACKLOG           integrity-check a backlog
    ticketly profile  PROFILE           validate a project profile
    ticketly archetypes [LIBRARY]       validate the archetype library
    ticketly install  claude|codex|all  wire Ticketly into your AI coding agent
    ticketly reset    PROJECT [--all]   safely remove a project's generated files
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

from ticketly import archetypes, profile, render, validate
from ticketly.home import CLAUDE_SKILL, CODEX_POINTER, DATA_ROOT

# Idempotency markers for the Codex AGENTS.md block. Exact-line matched (never
# regex) so a user's own AGENTS.md content is never disturbed.
_CODEX_MARKER_START = "# >>> ticketly (codex) >>>"
_CODEX_MARKER_END = "# <<< ticketly (codex) <<<"

# Generated-file layout, relative to the project folder. The reset command only
# ever touches files matching these exact (folder, suffix) shapes.
_PROFILE_DIR = "profiles"
_BACKLOG_DIR = "backlogs"
_BUILD_DIR = "build"
_BUILD_SUFFIXES = (".md", ".csv", ".notion.csv")


# --------------------------------------------------------------------------- #
# home
# --------------------------------------------------------------------------- #
def cmd_home(argv: list[str]) -> int:
    print(DATA_ROOT)
    return 0


# --------------------------------------------------------------------------- #
# install — wire Ticketly into an agent
# --------------------------------------------------------------------------- #
def _claude_skill_dir() -> Path:
    base = os.environ.get("CLAUDE_CONFIG_DIR") or str(Path.home() / ".claude")
    return Path(base) / "skills" / "ticketly"


def _codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME") or str(Path.home() / ".codex"))


def install_claude() -> None:
    dest_dir = _claude_skill_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "SKILL.md"
    # Copy (not symlink): after a wheel/pipx install there is no repo to point at.
    shutil.copyfile(CLAUDE_SKILL, dest)
    print(f"[claude] installed skill -> {dest}")


def install_codex() -> None:
    home = _codex_home()
    home.mkdir(parents=True, exist_ok=True)
    agents = home / "AGENTS.md"
    existing = agents.read_text().splitlines() if agents.exists() else []

    # Idempotent: drop any previous Ticketly block, then append a fresh one.
    cleaned: list[str] = []
    skip = False
    for line in existing:
        if line == _CODEX_MARKER_START:
            skip = True
            continue
        if line == _CODEX_MARKER_END:
            skip = False
            continue
        if not skip:
            cleaned.append(line)

    pointer = CODEX_POINTER.read_text().rstrip("\n")
    block = [_CODEX_MARKER_START, pointer, _CODEX_MARKER_END]
    body = "\n".join(cleaned).rstrip("\n")
    new_text = (body + "\n\n" if body else "") + "\n".join(block) + "\n"
    agents.write_text(new_text)
    print(f"[codex]  installed pointer -> {agents}")


def cmd_install(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="ticketly install")
    parser.add_argument("agent", choices=["claude", "codex", "all"])
    args = parser.parse_args(argv)
    if args.agent in ("claude", "all"):
        install_claude()
    if args.agent in ("codex", "all"):
        install_codex()
    print("Done. Use /ticketly in Claude Code, or say \"use Ticketly\" in Codex.")
    return 0


# --------------------------------------------------------------------------- #
# reset — safely remove a project's generated files
# --------------------------------------------------------------------------- #
def _is_ticketly_profile(path: Path) -> bool:
    """A profile we generated validates against the profile schema."""
    try:
        profile.validate_profile(json.loads(path.read_text()))
        return True
    except Exception:
        return False


def _is_ticketly_backlog(path: Path) -> bool:
    """A backlog we generated has a project name and a list of tickets."""
    try:
        data = json.loads(path.read_text())
    except Exception:
        return False
    return (
        isinstance(data, dict)
        and isinstance(data.get("project"), str)
        and isinstance(data.get("tickets"), list)
    )


def _is_ticketly_markdown(path: Path) -> bool:
    """A rendered backlog starts with a '# <...> backlog' heading."""
    try:
        first = next((ln for ln in path.read_text().splitlines() if ln.strip()), "")
    except Exception:
        return False
    return first.startswith("# ") and first.rstrip().endswith("backlog")


def _is_ticketly_csv(path: Path) -> bool:
    """A rendered CSV's header row is exactly one of our known headers."""
    try:
        header = path.read_text().splitlines()[0] if path.read_text() else ""
    except Exception:
        return False
    plain = ",".join(render.CSV_COLUMNS)
    notion = ",".join(h for h, _ in render.NOTION_COLUMNS)
    return header == plain or header == notion


def _looks_like_ours(path: Path) -> bool:
    """Fingerprint a candidate file. Unknown/foreign files are never deleted."""
    name = path.name
    if name.endswith(".notion.csv") or name.endswith(".csv"):
        return _is_ticketly_csv(path)
    if name.endswith(".md"):
        return _is_ticketly_markdown(path)
    parent = path.parent.name
    if parent == _PROFILE_DIR:
        return _is_ticketly_profile(path)
    if parent == _BACKLOG_DIR:
        return _is_ticketly_backlog(path)
    return False


def _candidate_paths(base: Path, slug: str) -> list[Path]:
    """The exact files Ticketly may have generated for one project slug."""
    paths = [
        base / _PROFILE_DIR / f"{slug}.json",
        base / _BACKLOG_DIR / f"{slug}.json",
    ]
    paths += [base / _BUILD_DIR / f"{slug}{suffix}" for suffix in _BUILD_SUFFIXES]
    return paths


def _safe_targets(base: Path, slug: str) -> tuple[list[Path], list[str]]:
    """Resolve which of a slug's candidate files are safe to delete.

    Returns (deletable, skipped_messages). A file is deletable ONLY if it
    exists, is a regular file (not a symlink), lives strictly inside ``base``,
    and passes the Ticketly fingerprint. Anything else is skipped with a note —
    the command never deletes more than this list, only ever less.
    """
    deletable: list[Path] = []
    skipped: list[str] = []
    for path in _candidate_paths(base, slug):
        if not path.exists():
            continue
        if path.is_symlink() or not path.is_file():
            skipped.append(f"skip (not a regular file): {path}")
            continue
        try:
            path.resolve().relative_to(base)
        except ValueError:
            skipped.append(f"skip (outside project folder): {path}")
            continue
        if not _looks_like_ours(path):
            skipped.append(f"skip (not a Ticketly file): {path}")
            continue
        deletable.append(path)
    return deletable, skipped


def _discover_slugs(base: Path) -> list[str]:
    """Project slugs that have a backlog or profile JSON in this folder."""
    slugs: set[str] = set()
    for sub in (_PROFILE_DIR, _BACKLOG_DIR):
        d = base / sub
        if d.is_dir():
            slugs.update(p.stem for p in d.glob("*.json") if p.is_file())
    return sorted(slugs)


def cmd_reset(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="ticketly reset")
    parser.add_argument(
        "project",
        nargs="?",
        help="Project slug to reset (the <name> in profiles/<name>.json).",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Reset every Ticketly project found in this folder.",
    )
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Skip the confirmation prompt.",
    )
    args = parser.parse_args(argv)

    if not args.project and not args.all:
        parser.error("name a project to reset, or pass --all")
    if args.project and args.all:
        parser.error("pass a project OR --all, not both")

    base = Path.cwd().resolve()
    slugs = _discover_slugs(base) if args.all else [args.project]

    deletable: list[Path] = []
    skipped: list[str] = []
    for slug in slugs:
        d, s = _safe_targets(base, slug)
        deletable += d
        skipped += s

    for msg in skipped:
        print(msg, file=sys.stderr)

    if not deletable:
        print("Nothing to reset — no Ticketly files matched.")
        return 0

    print("These files will be deleted:")
    for path in deletable:
        print(f"  {path}")

    if not args.yes:
        try:
            answer = input("Delete these files? [y/N] ").strip().lower()
        except EOFError:
            answer = ""
        if answer not in ("y", "yes"):
            print("Aborted. Nothing deleted.")
            return 1

    for path in deletable:
        path.unlink()
        print(f"deleted {path}")
    return 0


# --------------------------------------------------------------------------- #
# dispatch
# --------------------------------------------------------------------------- #
_PASSTHROUGH = {
    "render": render.main,
    "validate": validate.main,
    "profile": profile.main,
    "archetypes": archetypes.main,
}
_COMMANDS = {
    "home": cmd_home,
    "install": cmd_install,
    "reset": cmd_reset,
}

_USAGE = """\
ticketly — turn project requirements into clean, structured tickets.

Usage:
  ticketly home                       print the engine's data path
  ticketly install claude|codex|all   wire Ticketly into your AI coding agent
  ticketly reset PROJECT [--all]      safely remove a project's generated files
  ticketly render   BACKLOG [opts]    render a backlog to Markdown/CSV/Notion
  ticketly validate BACKLOG           integrity-check a backlog
  ticketly profile  PROFILE           validate a project profile
  ticketly archetypes [LIBRARY]       validate the archetype library
"""


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(_USAGE)
        return 0
    cmd, rest = argv[0], argv[1:]
    if cmd in _COMMANDS:
        return _COMMANDS[cmd](rest)
    if cmd in _PASSTHROUGH:
        return _PASSTHROUGH[cmd](rest)
    print(f"unknown command: {cmd}\n", file=sys.stderr)
    print(_USAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
