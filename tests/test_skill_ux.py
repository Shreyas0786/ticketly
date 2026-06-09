"""Structural tests for the /ticketly skill's UX guarantees.

These lock in the builder-friendly behaviors so a future edit can't quietly
regress them: never guess the company, talk in plain language, ask MVP-vs-full
before generating (and never silently drop MVP scope), and the symlink install
that makes updates a plain `git pull`.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = (ROOT / ".claude" / "skills" / "ticketly" / "SKILL.md").read_text()
SKILL_LOWER = SKILL.lower()
INSTALL = (ROOT / "install.sh").read_text()


# --- never guess the company --------------------------------------------

def test_skill_forbids_inferring_company_from_email():
    assert "do not infer it from the user's email" in SKILL_LOWER
    assert "never offer a specific real company name" in SKILL_LOWER


def test_skill_company_rule_names_the_sources_not_to_use():
    # email, git, environment/account must all be called out
    for src in ("email", "git", "account"):
        assert src in SKILL_LOWER


# --- plain language ------------------------------------------------------

def test_skill_has_plain_language_principle():
    assert "talk like a builder" in SKILL_LOWER
    assert "lead with plain meaning" in SKILL_LOWER


def test_prefix_step_is_framed_in_plain_language():
    # the confirmation must talk about "areas", not open with jargon
    assert "main areas" in SKILL_LOWER
    assert "looks good" in SKILL_LOWER  # the easy path is offered


def test_effort_is_translated_plainly():
    assert "small / medium / large" in SKILL_LOWER


# --- MVP vs full scope ---------------------------------------------------

def test_skill_asks_mvp_vs_full_before_generating():
    assert "how much do you want to plan" in SKILL_LOWER
    assert "full backlog" in SKILL_LOWER
    assert "mvp" in SKILL_LOWER


def test_mvp_never_silently_drops_scope():
    assert "never silently drop scope" in SKILL_LOWER
    assert "deferred for later" in SKILL_LOWER


def test_scope_choice_comes_before_generation():
    # the "choose the scope" step must appear before the "generate the backlog" step
    assert SKILL_LOWER.index("choose the scope") < SKILL_LOWER.index("generate the backlog")


# --- dev install delegates to the CLI ------------------------------------

def test_install_delegates_to_the_ticketly_command():
    assert "pip install -e" in INSTALL              # editable engine for contributors
    assert 'ticketly install "$MODE"' in INSTALL    # wiring is the CLI's job, not the script's


def test_skill_steps_are_numbered_without_collision():
    # the renumbered flow must have one each of these headers
    for header in ("### 4. choose the scope", "### 5. generate the backlog",
                   "### 6. check integrity", "### 7. render"):
        assert header in SKILL_LOWER, f"missing {header}"
