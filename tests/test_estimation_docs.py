"""Structural contracts for the estimation release: documentation, planning
instructions, house style, packaged example, CLI help, reset recognition, and the
version/changelog state of this feature branch.
"""

import json
import re
from pathlib import Path

from jsonschema import Draft202012Validator

from ticketly import cli, render
from ticketly import estimate as est

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "ticketly" / "data"
README = (ROOT / "README.md").read_text()
SKILL = (DATA / "claude" / "SKILL.md").read_text()
AGENTS = (DATA / "codex" / "AGENTS.md").read_text()
CHANGELOG = (ROOT / "CHANGELOG.md").read_text()
HOUSE_STYLE = json.loads((DATA / "house-style" / "default.json").read_text())
HOURS_EXAMPLE = DATA / "examples" / "hours-backlog.json"


def _flat(text: str) -> str:
    """Whitespace-normalised text, so assertions don't depend on line wrapping."""
    return " ".join(text.split())
PYPROJECT = (ROOT / "pyproject.toml").read_text()  # read as text: tomllib needs Python 3.11+


# --- README ---------------------------------------------------------------------

def test_readme_has_the_estimation_guide_sections():
    for heading in ("## Sizing work: hours-based or Fibonacci points",
                    "### Moving an existing backlog to hours-based points",
                    "## Owners, progress and totals",
                    "## Editing in a spreadsheet or Notion"):
        assert heading in README


def test_readme_shows_the_worked_examples_and_rubric():
    for row in ("| 12 | 1 | 12.0 |", "| 8 | 2 | 8.8 |", "| 8 | 3 | 10.0 |", "| 4 | 4 | 5.6 |"):
        assert row in README
    for multiplier in ("1.00", "1.10", "1.25", "1.40"):
        assert multiplier in README
    assert "half-up" in README and "quarter-hour" in README


def test_readme_covers_unestimated_migration_tracking_and_import():
    lower = README.lower()
    for phrase in ("unestimated", "partial", "ticketly switch-model", "legacy",
                   "in review", "assigned", "ticketly import", "--dry-run", "conflicts",
                   "change_reason", "ticketly recalc"):
        assert phrase in lower, phrase


def test_readme_documents_the_notion_refresh_process():
    lower = README.lower()
    assert "only **adds** rows" in README
    assert "no live notion sync" in lower
    assert "new** notion database" in lower
    assert "appears twice" in lower


def test_readme_notion_guidance_is_accurate_and_non_destructive():
    lower = _flat(README).lower()
    assert "no notion edits are lost" not in lower
    assert "delete the old rows" not in lower
    assert "keep the original one" in lower
    assert "properties you added in notion are **not** imported" in lower


def test_readme_explains_computed_hours_takeovers_and_completed_legacy_work():
    lower = README.lower()
    assert "`estimated_hours` is computed from the breakdown" in README
    assert "--approved-by" in README
    assert "just reassign it" in lower
    assert "splits of splits" in lower
    assert "credited to the owner recorded at the switch" in _flat(README)
    assert "nan" in lower and "infinity" in lower


def test_readme_rules_out_financial_features():
    assert "no rates, budgets, invoices or payments" in README


def test_readme_anchor_link_resolves():
    assert "(#editing-in-a-spreadsheet-or-notion)" in README


# --- planning instructions ------------------------------------------------------------

def test_skill_asks_for_the_model_once_and_suggests_hours():
    assert "### 4b. Choose how to estimate — once per backlog" in SKILL
    assert "Hours-based points" in SKILL and "Fibonacci points" in SKILL
    assert "suggest **Hours-based points**" in SKILL
    assert "An existing backlog keeps its model" in SKILL


def test_skill_carries_the_estimation_rules():
    for phrase in ("quarter hours", "difficulty_reason", "estimate_confidence", "Unestimated",
                   "Estimate the work, not the person", "second complexity buffer",
                   "ticketly recalc", "work_kind", "never type `effort` yourself"):
        assert phrase in SKILL, phrase


def test_skill_covers_ownership_takeovers_migration_and_import():
    for phrase in ("In Review", "Done means the work was reviewed", "split_from",
                   '"replaced"', '"additional"', "approved_by", "ticketly switch-model",
                   "ticketly import", "--dry-run", "Notion refresh", "no\n  live Notion sync"):
        assert phrase in SKILL, phrase


def test_skill_covers_the_corrected_split_legacy_and_notion_rules():
    for phrase in ("Full takeover", "--approved-by", "splits of splits",
                   "Never give them an hours estimate", "keep the original one",
                   "`estimated_hours` is computed from the breakdown", "NaN"):
        assert phrase in _flat(SKILL), phrase
    assert "delete the old" not in SKILL
    for phrase in ("reassignment", "--approved-by", "never re-estimated",
                   "Refresh Notion into a new database"):
        assert phrase in _flat(AGENTS), phrase


def test_skill_links_resolve():
    for rel in re.findall(r"ENGINE/([A-Za-z0-9_./-]+\.(?:md|json))", SKILL):
        assert (DATA / rel).is_file(), rel


def test_codex_adapter_restates_the_estimation_rules():
    for phrase in ("Hours-based points", "Fibonacci points", "ticketly recalc",
                   "ticketly switch-model", "ticketly import", "Unestimated",
                   "Done means reviewed work"):
        assert phrase in AGENTS, phrase


def test_repo_skill_is_the_packaged_skill():
    assert (ROOT / ".claude" / "skills" / "ticketly" / "SKILL.md").read_text() == SKILL


# --- house style and example --------------------------------------------------------------

def test_house_style_rubric_matches_the_engine():
    rubric = HOUSE_STYLE["hours_rubric"]
    assert rubric["version"] == est.RUBRIC_VERSION
    assert {k: v["multiplier"] for k, v in rubric["levels"].items()} == est.RUBRIC_V1
    assert {int(k): v["name"] for k, v in rubric["levels"].items()} == est.LEVEL_NAMES
    schema = json.loads((DATA / "house-style" / "house-style.schema.json").read_text())
    Draft202012Validator(schema).validate(HOUSE_STYLE)


def test_hours_example_is_wired_packaged_and_neutral():
    assert (DATA / HOUSE_STYLE["hours_few_shot"]["backlog"]) == HOURS_EXAMPLE
    data = json.loads(HOURS_EXAMPLE.read_text())
    assert data["company"] == "Demo Company" and data["project"] == "Demo Project"
    assert '"data/examples/*"' in PYPROJECT  # the example ships in the wheel
    kinds = {t.get("work_kind") for t in data["tickets"]}
    assert {"integration", "client_prep", "investigation"} <= kinds
    assert any(t.get("split_from") for t in data["tickets"])
    assert any(t["type"] == "Task" and t["effort"] is None for t in data["tickets"])


def test_no_financial_fields_in_engine_or_schema():
    blob = " ".join([
        (ROOT / "ticketly" / "estimate.py").read_text(),
        (ROOT / "ticketly" / "csv_import.py").read_text(),
        (DATA / "schema" / "ticket.schema.json").read_text(),
        HOURS_EXAMPLE.read_text(),
    ]).lower()
    for word in ("invoice", "budget", "payment", "hourly rate", "currency"):
        # whole words: "concurrency" is a difficulty example, not a money field
        assert not re.search(rf"\b{word}", blob), word


# --- cli help and reset ----------------------------------------------------------------

def test_cli_help_lists_new_commands_and_correct_reset_usage(capsys):
    assert cli.main(["--help"]) == 0
    out = capsys.readouterr().out
    for cmd in ("ticketly recalc", "--approved-by", "ticketly switch-model", "ticketly import",
                "ticketly reset [-y]"):
        assert cmd in out
    assert "PROJECT [--all]" not in out
    assert "PROJECT [--all]" not in (ROOT / "ticketly" / "cli.py").read_text()


def _csv(tmp_path, header):
    p = tmp_path / "backlog.csv"
    p.write_text(",".join(header) + "\n")
    return p


def test_reset_recognises_current_and_legacy_exports(tmp_path):
    for header in (render.CSV_COLUMNS, render.LEGACY_CSV_COLUMNS,
                   [h for h, _ in render.NOTION_COLUMNS], render.LEGACY_NOTION_HEADERS):
        assert cli._is_ticketly_csv(_csv(tmp_path, header)), header


def test_reset_does_not_broaden_to_lookalike_csvs(tmp_path):
    for header in (render.CSV_COLUMNS + ["notes"], render.LEGACY_CSV_COLUMNS[:-1],
                   ["id", "title", "effort"]):
        assert not cli._is_ticketly_csv(_csv(tmp_path, header)), header


# --- release state ---------------------------------------------------------------------

def test_version_stays_at_1_2_2_on_the_feature_branch():
    assert re.search(r'^version = "1\.2\.2"$', PYPROJECT, re.M)


def test_changelog_records_the_feature_under_unreleased():
    unreleased = CHANGELOG.split("## [Unreleased]")[1].split("## [1.2.2]")[0]
    for phrase in ("1.3.0", "Hours-based points", "ticketly recalc", "ticketly switch-model",
                   "ticketly import", "In Review"):
        assert phrase in unreleased, phrase
