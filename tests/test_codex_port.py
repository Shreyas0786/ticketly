"""Phase 3 structural tests for the Codex port.

The Codex port reuses the shared Python engine and re-expresses the /ticketly
flow as an AGENTS.md that Codex/GPT follows, plus the `ticketly install codex`
wiring. These tests pin the operator-facing artifacts so a careless edit fails
loudly: the Codex docs exist and carry their load-bearing instructions, their
relative links resolve to real bundled files, the dev install script offers all
three modes, and the README documents the Codex install + trigger.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "ticketly" / "data"  # ENGINE = the bundled-data dir
CODEX_AGENTS = ROOT / "ticketly" / "data" / "codex" / "AGENTS.md"
CODEX_POINTER = ROOT / "ticketly" / "data" / "codex" / "agents-pointer.md"
INSTALL = ROOT / "install.sh"
README = ROOT / "README.md"


# --- the Codex AGENTS.md (the on-demand full instructions) ---------------

def test_codex_agents_exists():
    assert CODEX_AGENTS.is_file()


def test_codex_agents_finds_engine_via_home():
    assert "ticketly home" in CODEX_AGENTS.read_text()


def test_codex_agents_points_at_the_canonical_skill():
    # the thin adapter must defer to the bundled SKILL.md as the single workflow source
    assert "ENGINE/claude/SKILL.md" in CODEX_AGENTS.read_text()


def test_codex_agents_restates_never_invent():
    assert "Never invent" in CODEX_AGENTS.read_text()


def test_codex_agents_references_engine_commands():
    text = CODEX_AGENTS.read_text()
    for cmd in ("profile", "validate", "render"):
        assert f"ticketly {cmd}" in text


def test_codex_agents_relative_links_resolve():
    # every engine-relative path the doc names must point at a real bundled file
    text = CODEX_AGENTS.read_text()
    for rel in re.findall(r"ENGINE/([A-Za-z0-9_./-]+\.(?:md|json))", text):
        assert (DATA / rel).is_file(), f"codex/AGENTS.md links missing file: {rel}"


# --- the pointer installed into ~/.codex/AGENTS.md -----------------------

def test_pointer_exists():
    assert CODEX_POINTER.is_file()


def test_pointer_is_on_demand_and_points_back():
    text = CODEX_POINTER.read_text()
    assert "ticketly home" in text
    assert "ENGINE/codex/AGENTS.md" in text


# --- the dev install script: three modes, delegates to `ticketly install` -

def test_install_offers_all_three_modes():
    assert "claude|codex|all)" in INSTALL.read_text(), "install.sh must accept all three modes"


def test_install_keeps_the_shared_engine_step():
    assert "pip install -e" in INSTALL.read_text()


def test_install_delegates_wiring_to_the_ticketly_command():
    assert 'ticketly install "$MODE"' in INSTALL.read_text()


def test_install_has_a_no_arg_menu():
    # bare invocation should hit the help/usage branch, not silently install
    text = INSTALL.read_text()
    assert "usage()" in text
    assert '""|-h|--help|help)' in text


# --- README documents the Codex path -------------------------------------

def test_readme_documents_codex_install():
    text = README.read_text()
    assert "ticketly install codex" in text or "ticketly install all" in text


def test_readme_documents_the_codex_trigger():
    assert "use Ticketly" in README.read_text()
