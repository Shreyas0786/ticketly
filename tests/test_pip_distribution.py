"""Phase 3 structural tests for the pip/pipx distribution.

This is what makes Ticketly installable as a package instead of a repo checkout:

  * the bundled data (schemas, house style, examples, archetypes, agent
    front-doors) lives *inside* the package, so it travels in a built wheel;
  * a single `ticketly` console script is the front door (robust to whichever
    python3 a calling agent resolves);
  * `ticketly install claude|codex|all` wires the agents idempotently;
  * `ticketly reset` removes ONLY a project's own generated files, never
    anything else — the safety contract is pinned here.
"""

import json
import shutil
import zipfile
from pathlib import Path

import pytest

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None

from ticketly import cli, home, render

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "ticketly" / "data"
SAMPLE_PROFILE = DATA / "examples" / "sample-profile.json"
SAMPLE_BACKLOG = DATA / "examples" / "sample-release-backlog.json"


# --- packaging: data ships inside the package ----------------------------

def test_bundled_data_lives_inside_the_package():
    # DATA_ROOT must be UNDER the ticketly package dir, or it won't ship in a wheel.
    pkg = Path(home.__file__).resolve().parent
    assert home.DATA_ROOT.resolve().is_relative_to(pkg)
    for p in (home.TICKET_SCHEMA, home.PROFILE_SCHEMA, home.HOUSE_STYLE_DEFAULT,
              home.FEW_SHOT_BACKLOG, home.ARCHETYPES, home.CLAUDE_SKILL,
              home.CODEX_AGENTS, home.CODEX_POINTER):
        assert p.is_file(), f"missing bundled data file {p}"


@pytest.mark.skipif(tomllib is None, reason="tomllib needs Python 3.11+")
def test_pyproject_declares_console_script():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert data["project"]["scripts"]["ticketly"] == "ticketly.cli:main"


@pytest.mark.skipif(tomllib is None, reason="tomllib needs Python 3.11+")
def test_pyproject_bundles_every_data_dir():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text())
    globs = data["tool"]["setuptools"]["package-data"]["ticketly"]
    for sub in ("schema", "profile", "house-style", "examples", "archetypes",
                "codex", "claude"):
        assert any(g.startswith(f"data/{sub}/") for g in globs), \
            f"pyproject does not bundle data/{sub}/"


@pytest.mark.slow
def test_built_wheel_contains_the_bundled_data(tmp_path):
    """The real proof: build a wheel and confirm the data is inside it."""
    import subprocess
    import sys

    pytest.importorskip("build")
    out = tmp_path / "dist"
    result = subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--outdir", str(out), str(ROOT)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        pytest.skip(f"wheel build unavailable in this env: {result.stderr[-300:]}")
    wheel = next(out.glob("*.whl"))
    names = zipfile.ZipFile(wheel).namelist()
    for needed in ("ticketly/data/schema/ticket.schema.json",
                   "ticketly/data/claude/SKILL.md",
                   "ticketly/data/codex/AGENTS.md"):
        assert needed in names, f"{needed} missing from the built wheel"


# --- the CLI front door --------------------------------------------------

def test_cli_home_prints_data_root(capsys):
    assert cli.main(["home"]) == 0
    assert capsys.readouterr().out.strip() == str(home.DATA_ROOT)


def test_cli_no_args_shows_usage(capsys):
    assert cli.main([]) == 0
    assert "ticketly" in capsys.readouterr().out.lower()


def test_cli_unknown_command_is_an_error(capsys):
    assert cli.main(["frobnicate"]) == 2


def test_cli_passes_through_to_render(tmp_path):
    assert cli.main(["render", str(SAMPLE_BACKLOG), "--format", "md",
                     "--out-dir", str(tmp_path)]) == 0
    assert (tmp_path / "backlog.md").is_file()


# --- install: wires agents idempotently ----------------------------------

def test_install_claude_copies_skill(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / ".claude"))
    assert cli.main(["install", "claude"]) == 0
    dest = tmp_path / ".claude" / "skills" / "ticketly" / "SKILL.md"
    assert dest.is_file()
    assert dest.read_text() == home.CLAUDE_SKILL.read_text()
    assert not dest.is_symlink()  # a real copy, not a repo symlink


def test_install_codex_appends_pointer_and_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / ".codex"))
    agents = tmp_path / ".codex" / "AGENTS.md"
    assert cli.main(["install", "codex"]) == 0
    assert cli.main(["install", "codex"]) == 0  # run twice
    text = agents.read_text()
    assert text.count(">>> ticketly (codex) >>>") == 1  # not duplicated
    assert text.count("<<< ticketly (codex) <<<") == 1
    assert "ENGINE/codex/AGENTS.md" in text  # the pointer body landed


def test_install_codex_preserves_user_content(tmp_path, monkeypatch):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / ".codex"))
    agents = tmp_path / ".codex" / "AGENTS.md"
    agents.parent.mkdir(parents=True)
    agents.write_text("# My own house rules\nAlways write tests.\n")
    assert cli.main(["install", "codex"]) == 0
    text = agents.read_text()
    assert "My own house rules" in text
    assert "Always write tests." in text


# --- reset: the safety contract ------------------------------------------

def _make_project(base: Path) -> None:
    """Create a full set of real Ticketly files in this folder's ./ticketly/."""
    out = base / "ticketly"
    data = out / ".data"
    data.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SAMPLE_PROFILE, data / "profile.json")
    (data / "backlog.json").write_text(
        json.dumps({"project": "demo", "tickets": []}))
    (out / "backlog.md").write_text("# demo backlog\n")
    (out / "tasks.md").write_text("# demo tasks\n")
    (out / "backlog.csv").write_text(",".join(render.CSV_COLUMNS) + "\n")


def test_reset_deletes_only_ticketly_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _make_project(tmp_path)
    # foreign files that must survive:
    (tmp_path / "ticketly" / "notes.md").write_text("# my real notes\n")
    (tmp_path / "secret.txt").write_text("do not touch")

    assert cli.main(["reset", "-y"]) == 0

    # the generated files are gone:
    for rel in (".data/profile.json", ".data/backlog.json",
                "backlog.md", "tasks.md", "backlog.csv"):
        assert not (tmp_path / "ticketly" / rel).exists(), rel
    # everything else is untouched:
    assert (tmp_path / "ticketly" / "notes.md").read_text() == "# my real notes\n"
    assert (tmp_path / "secret.txt").read_text() == "do not touch"


def test_reset_skips_a_foreign_file_with_a_matching_name(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "ticketly").mkdir()
    # named exactly like ours, but NOT our content -> must be preserved
    decoy = tmp_path / "ticketly" / "backlog.md"
    decoy.write_text("# my personal design doc\n")
    assert cli.main(["reset", "-y"]) == 0
    assert decoy.exists()
    assert decoy.read_text() == "# my personal design doc\n"


def test_reset_does_not_follow_symlinks(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    outside = tmp_path.parent / "outside_target.json"
    shutil.copyfile(SAMPLE_PROFILE, outside)
    data = tmp_path / "ticketly" / ".data"
    data.mkdir(parents=True)
    link = data / "profile.json"
    link.symlink_to(outside)  # a valid-looking, fingerprint-passing target
    try:
        assert cli.main(["reset", "-y"]) == 0
        assert outside.exists(), "reset must not delete a symlink's target"
        assert link.is_symlink(), "reset must not remove the symlink itself"
    finally:
        outside.unlink(missing_ok=True)


def test_reset_rejects_unexpected_arguments(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit):  # the slug/--all interface is gone
        cli.main(["reset", "myapp"])


def test_reset_removes_the_emptied_ticketly_folder(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _make_project(tmp_path)
    assert cli.main(["reset", "-y"]) == 0
    assert not (tmp_path / "ticketly").exists()  # emptied, then tidied away


def test_reset_aborts_when_not_confirmed(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _make_project(tmp_path)
    monkeypatch.setattr("builtins.input", lambda *_: "n")
    assert cli.main(["reset"]) == 1  # declined
    assert (tmp_path / "ticketly" / ".data" / "backlog.json").exists()  # nothing deleted


def test_reset_with_nothing_to_do_is_clean(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert cli.main(["reset", "-y"]) == 0  # no files, no error
