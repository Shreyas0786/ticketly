"""Structural tests for the CI workflow.

These keep .github/workflows/ci.yml honest without invoking GitHub Actions: the
file exists, parses as YAML, triggers on the right events, and tests the exact
Python range that pyproject.toml's requires-python promises — so the matrix and
the support claim can't silently drift apart.
"""

import re
from pathlib import Path

import yaml

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None

import pytest

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"

# Versions we expect the matrix to cover: every still-supported Python 3.
EXPECTED_VERSIONS = ["3.10", "3.11", "3.12", "3.13"]


@pytest.fixture(scope="module")
def workflow():
    assert WORKFLOW.is_file(), f"missing CI workflow at {WORKFLOW}"
    # YAML parses 'on:' as the boolean True; that's fine, we re-read the raw text
    # where we need the literal key.
    return yaml.safe_load(WORKFLOW.read_text())


def test_workflow_is_valid_yaml(workflow):
    assert isinstance(workflow, dict)


def test_triggers_on_push_and_pull_request(workflow):
    # PyYAML maps the bare key `on` to the boolean True.
    triggers = workflow.get(True) or workflow.get("on")
    assert triggers, "no triggers defined"
    assert "push" in triggers and "pull_request" in triggers
    assert triggers["push"]["branches"] == ["main"]
    assert triggers["pull_request"]["branches"] == ["main"]


def test_matrix_covers_expected_python_versions(workflow):
    matrix = workflow["jobs"]["test"]["strategy"]["matrix"]["python-version"]
    assert matrix == EXPECTED_VERSIONS


def test_matrix_matches_requires_python_floor():
    """The lowest matrix version must equal the requires-python floor, so the
    tested range and the published support claim stay in lockstep."""
    if tomllib is None:
        pytest.skip("tomllib needs Python 3.11+")
    requires = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"][
        "requires-python"
    ]
    floor = re.search(r"\d+\.\d+", requires).group()
    assert EXPECTED_VERSIONS[0] == floor, (
        f"CI matrix starts at {EXPECTED_VERSIONS[0]} but requires-python is {requires!r}"
    )


def test_workflow_runs_pytest(workflow):
    steps = workflow["jobs"]["test"]["steps"]
    assert any("pytest" in (step.get("run") or "") for step in steps)


def test_workflow_has_no_publish_step(workflow):
    """CD is intentionally out of scope — guard against an accidental upload step.

    Inspect the real step `run`/`uses` fields, not the raw text, so an explanatory
    comment mentioning twine doesn't trip the guard.
    """
    for job in workflow["jobs"].values():
        for step in job["steps"]:
            action = (step.get("run") or "") + " " + (step.get("uses") or "")
            assert "twine upload" not in action.lower()
            assert "pypi-publish" not in action.lower()
