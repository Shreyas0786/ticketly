"""Load and validate the Ticketly archetype library.

The archetype library (``archetypes/archetypes.json`` in the engine) is a curated
reference of common project types — for each, how to recognize it, the one or two
questions that change the stack, a free-first recommendation per branch with
reasoning and an honest alternative, and the backend pieces it must not skip. The
``/ticketly`` skill reads it during Discuss to recommend a fitting, non-generic
stack instead of defaulting to the same trendy answer for every project.

This module validates the library against its schema and offers a tiny lookup, so
the skill (and the tests) can rely on it from any working directory:

    python3 -m ticketly.archetypes          # validate the bundled library
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from ticketly.home import ARCHETYPES, ARCHETYPES_SCHEMA


def load_archetypes_schema() -> dict[str, Any]:
    return json.loads(ARCHETYPES_SCHEMA.read_text())


def load_library(path: str | Path | None = None) -> dict[str, Any]:
    """Load and validate the archetype library. Defaults to the bundled file.

    Raises ValidationError if the library does not conform to its schema.
    """
    data = json.loads(Path(path or ARCHETYPES).read_text())
    validate_library(data)
    return data


def validate_library(data: dict[str, Any]) -> None:
    """Validate a library dict against the schema. Raises ValidationError."""
    Draft202012Validator(load_archetypes_schema()).validate(data)


def archetype_ids(data: dict[str, Any] | None = None) -> list[str]:
    """The list of archetype ids in the library (bundled library by default)."""
    data = data or load_library()
    return [a["id"] for a in data["archetypes"]]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ticketly.archetypes",
        description="Validate the Ticketly archetype library against its schema.",
    )
    parser.add_argument(
        "library",
        nargs="?",
        default=None,
        help="Path to an archetype library JSON. Defaults to the bundled library.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    target = args.library or ARCHETYPES
    try:
        data = load_library(target)
    except Exception as exc:  # jsonschema.ValidationError and friends
        print(f"archetype library is invalid: {exc}", file=sys.stderr)
        return 1
    print(
        f"archetype library is valid: {target} "
        f"({len(data['archetypes'])} archetypes)",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
