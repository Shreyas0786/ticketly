"""Phase 3 structural tests for the archetype library.

The archetype library (``archetypes/archetypes.json``) is curated data the
``/ticketly`` skill reads during Discuss to recommend a fitting, non-generic
stack. These tests pin its structure so a careless edit fails loudly: the file
parses and validates against its schema, every archetype carries the parts the
skill relies on (signals, branch questions, options, backend checklist), every
option carries a stack + valid cost + reasoning + a real alternative, and the
engine path constants resolve to real files.
"""

import json

import pytest
from jsonschema import Draft202012Validator, ValidationError

from ticketly import archetypes
from ticketly.home import ARCHETYPES, ARCHETYPES_SCHEMA, PROFILE_SCHEMA

EXPECTED_IDS = {
    "marketplace", "saas-web-app", "content-site", "online-store",
    "mobile-app", "social-community", "internal-tool", "ai-app",
}
VALID_COSTS = {"free", "freemium", "paid"}


@pytest.fixture(scope="module")
def library():
    return archetypes.load_library()


@pytest.fixture(scope="module")
def entries(library):
    return library["archetypes"]


# --- engine wiring -------------------------------------------------------

def test_library_and_schema_files_exist():
    assert ARCHETYPES.exists()
    assert ARCHETYPES_SCHEMA.exists()


def test_library_parses_as_json():
    json.loads(ARCHETYPES.read_text())


def test_library_validates_against_schema(library):
    # load_library validates on load; this asserts no exception escaped.
    assert library["archetypes"]


def test_schema_itself_is_a_valid_metaschema():
    Draft202012Validator.check_schema(archetypes.load_archetypes_schema())


# --- coverage ------------------------------------------------------------

def test_all_eight_archetypes_present(entries):
    assert {a["id"] for a in entries} == EXPECTED_IDS


def test_archetype_ids_are_unique(entries):
    ids = [a["id"] for a in entries]
    assert len(ids) == len(set(ids))


def test_archetype_ids_helper_matches(library):
    assert set(archetypes.archetype_ids(library)) == EXPECTED_IDS


# --- per-archetype shape -------------------------------------------------

def test_every_archetype_has_a_label(entries):
    for a in entries:
        assert a["label"].strip()


def test_every_archetype_has_signals(entries):
    for a in entries:
        assert a["signals"], f"{a['id']} has no signals"


def test_every_archetype_has_branch_questions(entries):
    for a in entries:
        assert a["branch_questions"], f"{a['id']} has no branch questions"


def test_every_archetype_has_options(entries):
    for a in entries:
        assert a["options"], f"{a['id']} has no options"


def test_every_archetype_has_a_backend_checklist(entries):
    for a in entries:
        assert a["backend_checklist"], f"{a['id']} has no backend checklist"


# --- per-option shape: stack + cost + why + alternative ------------------

def test_every_option_has_stack_why_and_when(entries):
    for a in entries:
        for opt in a["options"]:
            assert opt["when"].strip(), f"{a['id']} option missing 'when'"
            assert opt["stack"].strip(), f"{a['id']} option missing 'stack'"
            assert opt["why"].strip(), f"{a['id']} option missing 'why'"


def test_every_option_has_a_valid_cost(entries):
    for a in entries:
        for opt in a["options"]:
            assert opt["cost"] in VALID_COSTS, f"{a['id']}: bad cost {opt['cost']!r}"


def test_every_option_has_a_real_alternative(entries):
    # the alternative must name a different option AND say when to pick it.
    for a in entries:
        for opt in a["options"]:
            alt = opt["alternative"]
            assert alt["stack"].strip(), f"{a['id']} alternative missing 'stack'"
            assert alt["when_instead"].strip(), f"{a['id']} alternative missing 'when_instead'"


def test_at_least_one_free_or_freemium_starting_point(entries):
    # free-first promise: every archetype offers at least one no-upfront-cost path.
    for a in entries:
        costs = {opt["cost"] for opt in a["options"]}
        assert costs & {"free", "freemium"}, f"{a['id']} has no free/freemium option"


# --- schema rejects malformed entries ------------------------------------

def test_schema_rejects_unknown_cost():
    schema = archetypes.load_archetypes_schema()
    bad = {"archetypes": [{
        "id": "x", "label": "X", "signals": ["s"], "branch_questions": ["q"],
        "backend_checklist": ["b"],
        "options": [{"when": "w", "stack": "s", "cost": "cheap",
                     "why": "y", "alternative": {"stack": "a", "when_instead": "i"}}],
    }]}
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(bad)


def test_schema_rejects_option_missing_alternative():
    schema = archetypes.load_archetypes_schema()
    bad = {"archetypes": [{
        "id": "x", "label": "X", "signals": ["s"], "branch_questions": ["q"],
        "backend_checklist": ["b"],
        "options": [{"when": "w", "stack": "s", "cost": "free", "why": "y"}],
    }]}
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(bad)


# --- profile records the matched archetype -------------------------------

def test_profile_schema_accepts_archetype_field():
    schema = json.loads(PROFILE_SCHEMA.read_text())
    prof = {"project": "Demo Project", "archetype": "marketplace",
            "stack": {"backend": ["Supabase"]},
            "architecture": {"components": []},
            "prefixes": [{"prefix": "WEB", "domain": "Web app"}]}
    Draft202012Validator(schema).validate(prof)


def test_profile_schema_archetype_is_optional():
    schema = json.loads(PROFILE_SCHEMA.read_text())
    prof = {"project": "Demo Project",
            "stack": {"backend": ["Supabase"]},
            "architecture": {"components": []},
            "prefixes": [{"prefix": "WEB", "domain": "Web app"}]}
    Draft202012Validator(schema).validate(prof)
