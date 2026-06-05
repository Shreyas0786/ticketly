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
    assert "./install.sh" in README
    assert "/ticketly" in README


def test_usage_commands_reference_real_modules():
    # any `python3 -m ticketly.<mod>` mentioned must be an importable module file
    for mod in set(re.findall(r"python3 -m ticketly\.(\w+)", README)):
        assert (ROOT / "ticketly" / f"{mod}.py").is_file(), f"README references missing ticketly.{mod}"


def test_no_dev_status_cruft():
    # it's a guide: no status/roadmap/phase-checkbox sections
    assert "## status" not in LOWER
    assert "## roadmap" not in LOWER
    assert "phase 1 ✅" not in LOWER
    assert "single source of truth" not in LOWER  # internal file-inventory language


def test_states_no_api_key():
    assert "no api key" in LOWER
