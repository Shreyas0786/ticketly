"""Structural tests for the README.

The README is the user-facing guide, not a build log. These assert it covers the
guide sections (what it does / who it's for / install / using), points at real
install + usage commands, and stays free of dev-status cruft (Status, Roadmap,
Phase checkboxes) so it can't drift back into a changelog.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = (ROOT / "README.md").read_text()
LOWER = README.lower()


def test_has_guide_sections():
    for heading in ("who it's for", "what it does", "how it works", "## install", "## using it"):
        assert heading in LOWER, f"README missing section: {heading}"


def test_documents_install_and_invocation():
    assert "pipx install ticketly" in README or "pip install ticketly" in README
    assert "ticketly install" in README   # wiring up an agent
    assert "/ticketly" in README


def test_usage_commands_reference_real_things():
    # every `ticketly <word>` the README names must be a real engine module or CLI subcommand
    subcommands = {"home", "install", "reset", "render", "validate", "profile", "archetypes"}
    # `(?<![/\w])` skips the `/ticketly` slash command and prose, matching only CLI usage.
    for word in set(re.findall(r"(?<![/\w])ticketly (\w+)", README)):
        if word == "install":  # `ticketly install` is followed by an agent name, skip the agent
            continue
        is_module = (ROOT / "ticketly" / f"{word}.py").is_file()
        assert word in subcommands or is_module, f"README references unknown `ticketly {word}`"


def test_no_dev_status_cruft():
    # it's a guide: no status/roadmap/phase-checkbox sections
    assert "## status" not in LOWER
    assert "## roadmap" not in LOWER
    assert "phase 1 ✅" not in LOWER
    assert "single source of truth" not in LOWER  # internal file-inventory language


def test_states_no_api_key():
    assert "no api key" in LOWER
