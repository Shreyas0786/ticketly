"""Phase 3 structural tests for the /ticketly existing-project entry path.

The skill is an operator-facing artifact, so it gets structural tests. These lock
in the behaviors agreed for running Ticketly against an *existing* codebase (vs the
greenfield interview): read-the-folder-then-decide detection, skipping the company
question (and never scraping a company from the repo), auto-drafting the profile by
reading then confirming, and planning *forward-looking* work that still routes into
the same validate -> render pipeline. A future edit can't quietly regress these.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = (ROOT / ".claude" / "skills" / "ticketly" / "SKILL.md").read_text()
SKILL_LOWER = SKILL.lower()


# --- the section exists --------------------------------------------------

def test_existing_project_section_exists():
    assert "### 1b. existing project" in SKILL_LOWER


# --- read, then decide (detection) --------------------------------------

def test_detection_reads_before_deciding():
    # don't classify on a filename alone; look at what's actually there first.
    assert "read the folder, then decide" in SKILL_LOWER
    assert "don't classify on a filename alone" in SKILL_LOWER


def test_docs_only_folder_is_treated_as_new_not_existing():
    assert "docs alone are not an existing project" in SKILL_LOWER
    # a spec / md / txt is the normal greenfield input
    assert "greenfield input" in SKILL_LOWER


def test_existing_is_code_a_manifest_or_a_source_tree():
    assert "package.json" in SKILL_LOWER
    assert "source tree" in SKILL_LOWER


def test_ambiguous_folder_asks_instead_of_guessing():
    assert "unsure / mixed" in SKILL_LOWER
    assert "fresh start, or an existing codebase" in SKILL_LOWER


# --- company is skipped, never scraped ----------------------------------

def test_existing_path_skips_the_company_question():
    assert "skip the company question" in SKILL_LOWER
    assert "company` is now optional" in SKILL_LOWER


def test_existing_path_forbids_scraping_company_from_the_repo():
    assert "never scrape a *company* name" in SKILL_LOWER
    # the sources not to scrape are named
    for src in ("package.json", "license", "git config", "repo name"):
        assert src in SKILL_LOWER


# --- auto-draft by reading, then confirm --------------------------------

def test_profile_is_auto_drafted_by_reading_not_inventing():
    assert "auto-draft the profile by reading" in SKILL_LOWER
    assert "reading the repo is not inventing" in SKILL_LOWER


def test_drafted_profile_is_confirmed_with_the_user():
    assert "confirm the drafted profile with the user" in SKILL_LOWER
    # what the code can't say -> ask, don't guess
    assert "ask, don't guess" in SKILL_LOWER


# --- forward-looking, not a backfill ------------------------------------

def test_targets_forward_looking_signals():
    assert "find the forward-looking work" in SKILL_LOWER
    for marker in ("todo", "fixme"):
        assert marker in SKILL_LOWER
    assert "no corresponding tests" in SKILL_LOWER


def test_generates_next_work_not_a_catalogue_of_what_exists():
    assert "not a catalogue of what exists" in SKILL_LOWER


# --- still routes into the real pipeline --------------------------------

def test_existing_path_reuses_validate_and_render_pipeline():
    # it must rejoin the normal scope -> generate -> validate -> render flow,
    # not invent a separate output path.
    assert "step 4 (choose the scope)" in SKILL_LOWER
    assert "python3 -m ticketly.profile" in SKILL
    assert "python3 -m ticketly.render" in SKILL
