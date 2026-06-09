"""Locate the Ticketly engine's bundled data directory.

Once Ticketly is installed (``pip install ticketly`` / ``pipx install ticketly``),
it can be run from any folder — a fresh project that does NOT contain the Ticketly
codebase. The engine still needs to find its own bundled data (the schemas, the
house style, the few-shot example, the agent front-doors). Those ship *inside* the
package under ``ticketly/data/``, resolved here via ``__file__`` so the location is
independent of the current working directory and travels inside a built wheel.

The ``ticketly home`` command prints this path; the ``/ticketly`` skill calls it,
then reads the data files by absolute path while writing its output (profile,
backlog, exports) into the user's current project folder.
"""

from __future__ import annotations

from pathlib import Path

# Bundled data ships inside the package, under ticketly/data/, so it travels in a
# built wheel. Resolved via __file__ (pip installs unpacked on disk), giving a real
# filesystem path the skill can read from any working directory.
DATA_ROOT = Path(__file__).resolve().parent / "data"

TICKET_SCHEMA = DATA_ROOT / "schema" / "ticket.schema.json"
PROFILE_SCHEMA = DATA_ROOT / "profile" / "profile.schema.json"
HOUSE_STYLE_SCHEMA = DATA_ROOT / "house-style" / "house-style.schema.json"
HOUSE_STYLE_DEFAULT = DATA_ROOT / "house-style" / "default.json"
FEW_SHOT_BACKLOG = DATA_ROOT / "examples" / "house-style-backlog.json"
ARCHETYPES = DATA_ROOT / "archetypes" / "archetypes.json"
ARCHETYPES_SCHEMA = DATA_ROOT / "archetypes" / "archetypes.schema.json"
# Agent front-doors deployed by `ticketly install`.
CLAUDE_SKILL = DATA_ROOT / "claude" / "SKILL.md"
CODEX_AGENTS = DATA_ROOT / "codex" / "AGENTS.md"
CODEX_POINTER = DATA_ROOT / "codex" / "agents-pointer.md"


def main(argv: list[str] | None = None) -> int:
    print(DATA_ROOT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
