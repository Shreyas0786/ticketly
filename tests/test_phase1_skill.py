"""Phase 3 structural tests for the /ticketly Claude Code skill.

The skill is an operator-facing artifact, so it gets structural tests: the file
exists at the expected path, has valid YAML frontmatter with name + description,
names itself 'ticketly', references the real schema/renderer paths it drives, and
encodes the locked conventions (never-invent guardrail, Fibonacci, prefix confirm).
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "ticketly" / "data"  # ENGINE = the bundled-data dir
SKILL_PATH = ROOT / ".claude" / "skills" / "ticketly" / "SKILL.md"


@pytest.fixture(scope="module")
def text():
    return SKILL_PATH.read_text()


@pytest.fixture(scope="module")
def frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    assert m, "skill is missing a YAML frontmatter block"
    return m.group(1)


def test_skill_file_exists():
    assert SKILL_PATH.is_file(), f"missing skill at {SKILL_PATH}"


def test_frontmatter_has_name_and_description(frontmatter):
    import yaml
    meta = yaml.safe_load(frontmatter)
    assert meta["name"] == "ticketly"
    assert isinstance(meta["description"], str) and meta["description"].strip()


def test_references_real_engine_data(text):
    # the skill points at engine data via ENGINE/<path>; those files must exist
    for rel in ["schema/ticket.schema.json", "house-style/default.json",
                "examples/house-style-backlog.json"]:
        assert rel in text, f"skill should reference {rel}"
        assert (DATA / rel).is_file(), f"skill references missing file {rel}"


def test_invokes_the_renderer_module(text):
    assert "ticketly render" in text


def test_encodes_locked_conventions(text):
    lower = text.lower()
    assert "never invent" in lower            # the core guardrail
    assert "needs_clarification" in text       # the guardrail field
    assert "fibonacci" in lower                # effort scale
    assert "confirm" in lower                  # prefixes: suggest, user confirms


def test_mentions_both_discussion_and_distill(text):
    lower = text.lower()
    assert "discuss" in lower
    assert "distill" in lower
