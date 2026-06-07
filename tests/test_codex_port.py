"""Phase 3 structural tests for the Codex port.

The Codex port reuses the shared Python engine and re-expresses the /ticketly
flow as an AGENTS.md that Codex/GPT follows, plus an idempotent installer mode.
These tests pin the operator-facing artifacts so a careless edit fails loudly:
the Codex docs exist and carry their load-bearing instructions, their relative
links resolve to real files, the installer offers all three modes without losing
the Claude path, and the README documents the Codex install + trigger.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CODEX_AGENTS = ROOT / "codex" / "AGENTS.md"
CODEX_POINTER = ROOT / "codex" / "agents-pointer.md"
INSTALL = ROOT / "install.sh"
README = ROOT / "README.md"


# --- the Codex AGENTS.md (the on-demand full instructions) ---------------

def test_codex_agents_exists():
    assert CODEX_AGENTS.is_file()


def test_codex_agents_finds_engine_via_home():
    assert "python3 -m ticketly.home" in CODEX_AGENTS.read_text()


def test_codex_agents_points_at_the_canonical_skill():
    # the thin adapter must defer to SKILL.md as the single workflow source
    assert ".claude/skills/ticketly/SKILL.md" in CODEX_AGENTS.read_text()


def test_codex_agents_restates_never_invent():
    assert "Never invent" in CODEX_AGENTS.read_text()


def test_codex_agents_references_engine_modules():
    text = CODEX_AGENTS.read_text()
    for mod in ("profile", "validate", "render"):
        assert f"python3 -m ticketly.{mod}" in text


def test_codex_agents_relative_links_resolve():
    # every engine-relative path the doc names must point at a real file
    text = CODEX_AGENTS.read_text()
    for rel in re.findall(r"ENGINE/([A-Za-z0-9_./-]+\.(?:md|json))", text):
        assert (ROOT / rel).is_file(), f"codex/AGENTS.md links missing file: {rel}"


# --- the pointer installed into ~/.codex/AGENTS.md -----------------------

def test_pointer_exists():
    assert CODEX_POINTER.is_file()


def test_pointer_is_on_demand_and_points_back():
    text = CODEX_POINTER.read_text()
    assert "python3 -m ticketly.home" in text
    assert "ENGINE/codex/AGENTS.md" in text


# --- the installer: three modes, idempotent, Claude path intact ----------

def test_install_offers_all_three_modes():
    text = INSTALL.read_text()
    for mode in ("claude)", "codex)", "all)"):
        assert mode in text, f"install.sh missing mode: {mode}"


def test_install_keeps_the_shared_engine_step():
    assert "pip install -e" in INSTALL.read_text()


def test_install_keeps_the_claude_skill_path():
    text = INSTALL.read_text()
    assert ".claude/skills/ticketly/SKILL.md" in text
    assert "skills/ticketly" in text


def test_install_wires_the_codex_pointer():
    text = INSTALL.read_text()
    assert ".codex/AGENTS.md" in text
    assert "codex/agents-pointer.md" in text


def test_install_codex_block_is_idempotent_by_markers():
    # delimited markers are what make re-running safe; both must be present
    text = INSTALL.read_text()
    assert ">>> ticketly (codex) >>>" in text
    assert "<<< ticketly (codex) <<<" in text


def test_install_has_a_no_arg_menu():
    # bare invocation should hit the help/usage branch, not silently install
    text = INSTALL.read_text()
    assert "usage()" in text
    assert '""|-h|--help|help)' in text


# --- README documents the Codex path -------------------------------------

def test_readme_documents_all_three_install_modes():
    text = README.read_text()
    assert "./install.sh claude" in text
    assert "./install.sh codex" in text
    assert "./install.sh all" in text


def test_readme_documents_the_codex_trigger():
    assert "use Ticketly" in README.read_text()
