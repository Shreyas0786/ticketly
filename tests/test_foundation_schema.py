"""Phase 3 structural tests for the Ticketly ticket schema (Foundation / F2).

Asserts the schema file exists, is itself a valid JSON Schema, encodes the
locked decisions (lean 9 core + 3 optional fields, Fibonacci effort, ID scheme),
that the shipped example validates, and that malformed tickets are rejected.
"""

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.validators import validator_for

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schema" / "ticket.schema.json"
EXAMPLE_PATH = ROOT / "examples" / "sample-release-backlog.json"

CORE_FIELDS = {
    "id", "title", "type", "parent", "status",
    "effort", "dependencies", "description",
    "acceptance_criteria", "needs_clarification",
}
OPTIONAL_FIELDS = {"assignee", "due_date", "priority"}
FIBONACCI = [0, 1, 2, 3, 5, 8, 13]


@pytest.fixture(scope="module")
def schema():
    return json.loads(SCHEMA_PATH.read_text())


@pytest.fixture(scope="module")
def ticket_props(schema):
    return schema["$defs"]["ticket"]["properties"]


def test_schema_file_exists():
    assert SCHEMA_PATH.is_file(), f"missing schema at {SCHEMA_PATH}"


def test_schema_parses_as_json(schema):
    assert isinstance(schema, dict)


def test_schema_is_itself_valid(schema):
    # raises SchemaError if the schema is malformed
    validator_for(schema).check_schema(schema)


def test_top_level_requires_project_and_tickets(schema):
    # company is OPTIONAL (omitted on existing-project runs); project + tickets are required.
    assert set(schema["required"]) == {"project", "tickets"}


def test_company_is_an_optional_string_property(schema):
    # still a defined, validated field — just not required.
    assert "company" not in schema["required"]
    assert schema["properties"]["company"]["type"] == "string"
    assert schema["properties"]["company"]["minLength"] == 1


def test_ticket_has_exactly_core_plus_optional_fields(ticket_props):
    assert set(ticket_props) == CORE_FIELDS | OPTIONAL_FIELDS


def test_core_fields_are_required(schema):
    required = set(schema["$defs"]["ticket"]["required"])
    assert required == CORE_FIELDS


def test_optional_fields_are_not_required(schema):
    required = set(schema["$defs"]["ticket"]["required"])
    assert OPTIONAL_FIELDS.isdisjoint(required)


def test_effort_is_fibonacci(ticket_props):
    assert ticket_props["effort"]["enum"] == FIBONACCI


def test_type_enum_is_epic_task(ticket_props):
    assert ticket_props["type"]["enum"] == ["Epic", "Task"]


def test_no_tshirt_sizes_anywhere(schema):
    # guardrail: effort must be points, never S/M/L/XL
    blob = json.dumps(schema)
    assert '"S"' not in blob and '"XL"' not in blob


def test_id_pattern_accepts_epic_and_task_ids(schema):
    import re
    pattern = schema["$defs"]["id"]["pattern"]
    rx = re.compile(pattern)
    for good in ("EPIC-ARC", "ARC-001", "REL-005", "OCR-012"):
        assert rx.fullmatch(good), f"{good} should match"
    for bad in ("arc-001", "ARC-1", "ARC-0001", "EPIC-001", "1104"):
        assert not rx.fullmatch(bad), f"{bad} should NOT match"


def test_example_validates_against_schema(schema):
    data = json.loads(EXAMPLE_PATH.read_text())
    Draft202012Validator(schema).validate(data)


def test_example_uses_only_placeholder_company():
    # guardrail: shipped artifacts use neutral placeholders, never a real/prior company
    data = json.loads(EXAMPLE_PATH.read_text())
    assert data["company"] == "Demo Company"
    assert data["project"] == "Demo Project"


@pytest.fixture
def valid_ticket():
    data = json.loads(EXAMPLE_PATH.read_text())
    return copy.deepcopy(data["tickets"][1])  # a Task (REL-002)


@pytest.mark.parametrize("mutate", [
    lambda t: t.update(id="arc-001"),          # bad id case
    lambda t: t.update(effort=4),              # non-Fibonacci
    lambda t: t.update(type="Story"),          # bad type enum
    lambda t: t.update(status="Closed"),       # bad status enum
    lambda t: t.pop("acceptance_criteria"),    # missing required field
    lambda t: t.update(extra="nope"),          # additional property
    lambda t: t.update(dependencies=["nope"]),  # bad dependency id
])
def test_malformed_tickets_are_rejected(schema, valid_ticket, mutate):
    mutate(valid_ticket)
    doc = {"company": "Demo Company", "project": "Demo Project", "tickets": [valid_ticket]}
    with pytest.raises(Exception):
        Draft202012Validator(schema).validate(doc)
