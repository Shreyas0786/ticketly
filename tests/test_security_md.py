"""Structural tests for the security policy.

Going public ships a SECURITY.md that routes vulnerability reports through
GitHub's private advisories (no email exposed). These assert the file exists,
names a supported-versions policy and a private reporting channel, publishes no
contact email, and that the README points at it with links that resolve.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SECURITY = ROOT / "SECURITY.md"
README = ROOT / "README.md"

ADVISORY_URL = "https://github.com/Shreyas0786/ticketly/security"
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def test_security_file_exists():
    assert SECURITY.is_file(), "missing SECURITY.md"


def test_has_required_sections():
    low = SECURITY.read_text().lower()
    assert "supported versions" in low, "SECURITY.md missing a supported-versions section"
    assert "reporting a vulnerability" in low, "SECURITY.md missing a reporting section"


def test_routes_to_private_github_reporting():
    text = SECURITY.read_text()
    assert ADVISORY_URL in text, "SECURITY.md should link the repo Security tab"
    assert "report a vulnerability" in text.lower()


def test_directs_away_from_public_issues():
    # the whole point: security bugs go private, not into a public issue
    low = SECURITY.read_text().lower()
    assert "do not open a public issue" in low or "don't open a public issue" in low


def test_publishes_no_contact_email():
    # privacy decision: route through GitHub private reporting, never an address
    found = EMAIL_RE.findall(SECURITY.read_text())
    assert not found, f"SECURITY.md exposes an email address: {found}"


def test_readme_points_to_security_policy():
    text = README.read_text()
    assert "## security" in text.lower(), "README missing a Security section"
    assert "SECURITY.md" in text


def test_readme_marks_prs_not_accepted():
    # the sharpened no-contributions stance must stay explicit
    low = README.read_text().lower()
    assert "pull requests are not accepted" in low or "does not accept outside code" in low


def test_cross_links_resolve():
    # every relative .md link in SECURITY.md points to a real file
    text = SECURITY.read_text()
    for target in re.findall(r"\]\((?!https?://)([^)#]+\.md)", text):
        resolved = (SECURITY.parent / target).resolve()
        assert resolved.is_file(), f"SECURITY.md links to missing file: {target}"
