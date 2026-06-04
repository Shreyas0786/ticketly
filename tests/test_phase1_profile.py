"""Phase 3 structural tests for the Ticketly project-profile schema.

Asserts the profile schema exists, is a valid JSON Schema, encodes the locked
shape (company/project/stack/architecture/prefixes), that the shipped example
validates, and that malformed profiles are rejected.
"""

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.validators import validator_for

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "profile" / "profile.schema.json"
EXAMPLE_PATH = ROOT / "examples" / "sample-profile.json"

REQUIRED_TOP = {"company", "project", "stack", "architecture", "prefixes"}
STACK_LAYERS = {"frontend", "backend", "database", "infra", "other"}


@pytest.fixture(scope="module")
def schema():
    return json.loads(SCHEMA_PATH.read_text())


@pytest.fixture(scope="module")
def example():
    return json.loads(EXAMPLE_PATH.read_text())


def test_schema_file_exists():
    assert SCHEMA_PATH.is_file(), f"missing profile schema at {SCHEMA_PATH}"


def test_schema_is_itself_valid(schema):
    validator_for(schema).check_schema(schema)


def test_required_top_level_fields(schema):
    assert set(schema["required"]) == REQUIRED_TOP


def test_stack_layers_are_the_known_set(schema):
    assert set(schema["properties"]["stack"]["properties"]) == STACK_LAYERS


def test_prefix_pattern_matches_ticket_prefixes(schema):
    import re
    pattern = schema["properties"]["prefixes"]["items"]["properties"]["prefix"]["pattern"]
    rx = re.compile(pattern)
    for good in ("API", "WEB", "DB", "AUTH", "INFRA"):
        assert rx.fullmatch(good), f"{good} should match"
    for bad in ("api", "A", "TOOLONG", "WEB1"):
        assert not rx.fullmatch(bad), f"{bad} should NOT match"


def test_example_validates(schema, example):
    Draft202012Validator(schema).validate(example)


def test_example_uses_no_borrowed_company_name():
    blob = EXAMPLE_PATH.read_text().lower()
    assert "nexaone" not in blob


def test_example_prefixes_are_unique(example):
    prefixes = [p["prefix"] for p in example["prefixes"]]
    assert len(prefixes) == len(set(prefixes))


@pytest.mark.parametrize("mutate", [
    lambda p: p.pop("company"),                       # missing required
    lambda p: p.pop("prefixes"),                      # missing required
    lambda p: p.update(prefixes=[]),                  # prefixes must be non-empty
    lambda p: p["prefixes"].append({"prefix": "api", "domain": "x"}),  # lowercase prefix
    lambda p: p["prefixes"].append({"prefix": "API"}),  # missing domain
    lambda p: p["stack"].update(unknown=["x"]),       # unknown stack layer
    lambda p: p.update(extra="nope"),                 # additional top-level property
    lambda p: p.update(company=""),                   # empty company
])
def test_malformed_profiles_are_rejected(schema, example, mutate):
    bad = copy.deepcopy(example)
    mutate(bad)
    with pytest.raises(Exception):
        Draft202012Validator(schema).validate(bad)
