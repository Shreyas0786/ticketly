"""Validate a project profile against the profile schema.

A profile (``profiles/<project>.json`` in the user's folder) captures the
user-supplied stack, architecture, and agreed prefix scheme. This module checks
one against ``profile/profile.schema.json`` from the installed engine, so the
``/ticketly`` skill can verify a profile from any working directory:

    python3 -m ticketly.profile profiles/<project>.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from ticketly.home import PROFILE_SCHEMA


def load_profile_schema() -> dict[str, Any]:
    return json.loads(PROFILE_SCHEMA.read_text())


def validate_profile(data: dict[str, Any]) -> None:
    """Validate a profile dict against the schema. Raises ValidationError."""
    Draft202012Validator(load_profile_schema()).validate(data)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ticketly.profile",
        description="Validate a Ticketly project profile against the profile schema.",
    )
    parser.add_argument("profile", help="Path to a profile JSON file.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    data = json.loads(Path(args.profile).read_text())
    try:
        validate_profile(data)
    except Exception as exc:  # jsonschema.ValidationError and friends
        print(f"profile is invalid: {exc}", file=sys.stderr)
        return 1
    print(f"profile is valid: {args.profile}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
