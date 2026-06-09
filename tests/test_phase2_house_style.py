"""Phase 3 structural tests for the Ticketly house-style config (Phase 2 feature).

Asserts the house-style schema exists and is valid, that the shipped default
conforms to it, that the effort rubric covers every non-epic Fibonacci point,
that the prefix vocab uses valid prefixes, that the few-shot backlog it points
at exists and validates against the ticket schema (and stays scrubbed of any
borrowed company name), and that malformed house-style configs are rejected.
"""

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.validators import validator_for

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "ticketly" / "data"  # ENGINE = the bundled-data dir; few_shot paths are relative to it
HS_SCHEMA = ROOT / "ticketly" / "data" / "house-style" / "house-style.schema.json"
HS_DEFAULT = ROOT / "ticketly" / "data" / "house-style" / "default.json"
TICKET_SCHEMA = ROOT / "ticketly" / "data" / "schema" / "ticket.schema.json"

FIBONACCI_NONZERO = {"1", "2", "3", "5", "8", "13"}


@pytest.fixture(scope="module")
def schema():
    return json.loads(HS_SCHEMA.read_text())


@pytest.fixture(scope="module")
def default():
    return json.loads(HS_DEFAULT.read_text())


def test_schema_exists_and_is_valid(schema):
    assert HS_SCHEMA.is_file()
    validator_for(schema).check_schema(schema)


def test_required_top_level_fields(schema):
    assert set(schema["required"]) == {"effort_rubric", "prefix_vocab", "tone", "few_shot"}


def test_default_validates(schema, default):
    Draft202012Validator(schema).validate(default)


def test_effort_rubric_covers_every_nonzero_fibonacci(default):
    assert set(default["effort_rubric"]) == FIBONACCI_NONZERO


def test_effort_rubric_excludes_epic_zero(default):
    assert "0" not in default["effort_rubric"]


def test_prefix_vocab_prefixes_are_valid_and_unique(schema, default):
    import re
    pattern = schema["properties"]["prefix_vocab"]["items"]["properties"]["prefix"]["pattern"]
    rx = re.compile(pattern)
    prefixes = [p["prefix"] for p in default["prefix_vocab"]]
    assert prefixes, "vocab must not be empty"
    assert len(prefixes) == len(set(prefixes)), "prefixes must be unique"
    for p in prefixes:
        assert rx.fullmatch(p), f"{p} is not a valid prefix"


def test_tone_has_all_three_fields(default):
    assert set(default["tone"]) == {"title", "description", "acceptance_criteria"}


def test_few_shot_backlog_exists_and_validates(default):
    backlog_path = DATA / default["few_shot"]["backlog"]
    assert backlog_path.is_file(), f"missing few-shot backlog {backlog_path}"
    ticket_schema = json.loads(TICKET_SCHEMA.read_text())
    Draft202012Validator(ticket_schema).validate(json.loads(backlog_path.read_text()))


def test_few_shot_backlog_uses_placeholder_company(default):
    backlog = json.loads((DATA / default["few_shot"]["backlog"]).read_text())
    assert backlog["company"] == "Demo Company"
    assert backlog["project"] == "Demo Project"


def test_few_shot_uses_house_vocab_prefixes(default):
    """Every ticket ID prefix in the few-shot backlog is a known vocab prefix."""
    vocab = {p["prefix"] for p in default["prefix_vocab"]}
    backlog = json.loads((DATA / default["few_shot"]["backlog"]).read_text())
    for t in backlog["tickets"]:
        prefix = t["id"].split("-")[1] if t["id"].startswith("EPIC-") else t["id"].split("-")[0]
        assert prefix in vocab, f"{t['id']} uses prefix {prefix} not in the vocab"


def test_requirements_declares_runtime_dep():
    req = (ROOT / "requirements.txt").read_text().lower()
    assert "jsonschema" in req, "requirements.txt must declare the runtime dependency"


def test_skill_wires_in_house_style():
    skill = (ROOT / ".claude" / "skills" / "ticketly" / "SKILL.md").read_text()
    assert "house-style/default.json" in skill
    assert "house-style/house-style.schema.json" in skill
    assert "effort_rubric" in skill and "prefix_vocab" in skill and "few_shot" in skill


@pytest.mark.parametrize("mutate", [
    lambda d: d.pop("effort_rubric"),                     # missing required block
    lambda d: d["effort_rubric"].pop("13"),               # incomplete rubric
    lambda d: d.update(prefix_vocab=[]),                  # empty vocab
    lambda d: d["prefix_vocab"].append({"prefix": "api", "domain": "x"}),  # bad prefix case
    lambda d: d["tone"].pop("title"),                     # missing tone field
    lambda d: d.update(extra="nope"),                     # additional property
    lambda d: d.update(few_shot={}),                      # few_shot missing backlog
])
def test_malformed_house_style_rejected(schema, default, mutate):
    bad = copy.deepcopy(default)
    mutate(bad)
    with pytest.raises(Exception):
        Draft202012Validator(schema).validate(bad)
