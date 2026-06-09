"""Phase 3 tests for the install-once / use-anywhere setup.

Covers the packaging (pyproject), the engine-locator (ticketly.home) and its
bundled-data paths, the profile validator, the install script's structure, and
the headline guarantee: the engine runs from a folder that does NOT contain the
Ticketly codebase (proving the editable install makes it cwd-independent).
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / ".claude" / "skills" / "ticketly" / "SKILL.md"


# --- packaging -----------------------------------------------------------

def test_pyproject_exists():
    assert (ROOT / "pyproject.toml").is_file()


@pytest.mark.skipif(tomllib is None, reason="tomllib needs Python 3.11+")
def test_pyproject_declares_ticketly_package():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert data["project"]["name"] == "ticketly"
    assert "jsonschema" in " ".join(data["project"]["dependencies"])
    assert data["tool"]["setuptools"]["packages"] == ["ticketly"]


# --- engine locator ------------------------------------------------------

def test_home_data_root_holds_the_bundled_data():
    from ticketly import home
    assert home.DATA_ROOT.is_dir()
    for p in (home.TICKET_SCHEMA, home.PROFILE_SCHEMA, home.HOUSE_STYLE_SCHEMA,
              home.HOUSE_STYLE_DEFAULT, home.FEW_SHOT_BACKLOG):
        assert p.is_file(), f"missing bundled data file {p}"


def test_home_cli_prints_data_root(capsys):
    from ticketly import home
    assert home.main([]) == 0
    assert capsys.readouterr().out.strip() == str(home.DATA_ROOT)


# --- profile validator ---------------------------------------------------

def test_profile_validator_accepts_sample():
    from ticketly import profile
    data = json.loads((ROOT / "ticketly" / "data" / "examples" / "sample-profile.json").read_text())
    profile.validate_profile(data)  # must not raise


def test_profile_validator_rejects_broken(tmp_path):
    from ticketly import profile
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"company": "X"}))  # missing required fields
    assert profile.main([str(bad)]) == 1


def test_profile_validator_cli_accepts_sample():
    from ticketly import profile
    assert profile.main([str(ROOT / "ticketly" / "data" / "examples" / "sample-profile.json")]) == 0


# --- install script ------------------------------------------------------

def test_install_script_exists_and_is_structured():
    text = (ROOT / "install.sh").read_text()
    assert "pip install -e" in text                 # editable engine install for contributors
    assert 'ticketly install "$MODE"' in text       # delegates agent wiring to the CLI


# --- the headline guarantee: works from a folder without the codebase ----

def test_engine_runs_from_a_foreign_directory(tmp_path):
    """`python3 -m ticketly.home` must work with cwd set to an empty folder that
    does not contain the Ticketly codebase — this is the whole point of the
    editable install."""
    result = subprocess.run(
        [sys.executable, "-m", "ticketly.home"],
        cwd=tmp_path, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    printed = Path(result.stdout.strip())
    assert (printed / "schema" / "ticket.schema.json").is_file()


def test_render_runs_from_a_foreign_directory(tmp_path):
    """Render the engine's own example backlog while cwd is an unrelated folder;
    output must be written into that folder."""
    engine = subprocess.run(
        [sys.executable, "-m", "ticketly.home"],
        cwd=tmp_path, capture_output=True, text=True,
    ).stdout.strip()
    backlog = str(Path(engine) / "examples" / "sample-release-backlog.json")
    result = subprocess.run(
        [sys.executable, "-m", "ticketly.render", backlog, "--format", "md",
         "--out-dir", "out"],
        cwd=tmp_path, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "out" / "demo-project.md").is_file()


# --- skill is global-ready ----------------------------------------------

def test_skill_uses_engine_locator_not_cwd_paths():
    text = SKILL.read_text()
    assert "ticketly home" in text
    assert "ENGINE" in text
    # writes go to the current folder
    assert "./profiles/" in text and "./backlogs/" in text and "./build/" in text


def test_skill_validates_profile_via_command():
    assert "ticketly profile" in SKILL.read_text()
