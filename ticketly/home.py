"""Locate the Ticketly engine's data directory.

Once Ticketly is installed (``pip install -e .``), it can be run from any folder
— a fresh project that does NOT contain the Ticketly codebase. The engine still
needs to find its own bundled data (the schemas, the house style, the few-shot
example). Those live next to the ``ticketly`` package, resolved here via
``__file__`` so the location is independent of the current working directory.

The ``/ticketly`` skill calls ``python3 -m ticketly.home`` to print this path,
then reads the data files by absolute path while writing its output (profile,
backlog, exports) into the user's current project folder.
"""

from __future__ import annotations

from pathlib import Path

# The data dirs (schema/, house-style/, examples/, profile/) sit one level above
# the package directory.
DATA_ROOT = Path(__file__).resolve().parent.parent

TICKET_SCHEMA = DATA_ROOT / "schema" / "ticket.schema.json"
PROFILE_SCHEMA = DATA_ROOT / "profile" / "profile.schema.json"
HOUSE_STYLE_SCHEMA = DATA_ROOT / "house-style" / "house-style.schema.json"
HOUSE_STYLE_DEFAULT = DATA_ROOT / "house-style" / "default.json"
FEW_SHOT_BACKLOG = DATA_ROOT / "examples" / "house-style-backlog.json"


def main(argv: list[str] | None = None) -> int:
    print(DATA_ROOT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
