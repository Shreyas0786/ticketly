"""Structural tests for the changelog.

These keep CHANGELOG.md honest: it exists, has an Unreleased section, and — the
load-bearing guard — carries a heading for the version currently declared in
pyproject.toml, so a release can't ship without a recorded entry.
"""

import re
from pathlib import Path

import pytest

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None

ROOT = Path(__file__).resolve().parent.parent
CHANGELOG = ROOT / "CHANGELOG.md"


def test_changelog_exists():
    assert CHANGELOG.is_file()


def test_changelog_has_unreleased_section():
    assert "## [Unreleased]" in CHANGELOG.read_text()


def test_version_headings_are_semver():
    # every released "## [x.y.z]" heading must be a valid MAJOR.MINOR.PATCH
    headings = re.findall(r"^## \[(\d+\.\d+\.\d+)\]", CHANGELOG.read_text(), re.M)
    assert headings, "no released version headings found"
    for v in headings:
        assert re.fullmatch(r"\d+\.\d+\.\d+", v), f"{v} is not semver"


@pytest.mark.skipif(tomllib is None, reason="tomllib needs Python 3.11+")
def test_current_pyproject_version_is_logged():
    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    assert f"## [{version}]" in CHANGELOG.read_text(), (
        f"pyproject is at {version} but CHANGELOG.md has no '## [{version}]' entry — "
        "add the release notes before publishing."
    )
