"""Structural tests for the contribution policy artifacts.

Making the repo public ships a no-PRs-but-issues-welcome policy across several
files. These assert the files exist, carry the policy language, that the issue
templates have valid front matter and the prompts a triager needs, and that the
README and CONTRIBUTING cross-links resolve to real files.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GITHUB = ROOT / ".github"

CONTRIBUTING = ROOT / "CONTRIBUTING.md"
PR_TEMPLATE = GITHUB / "PULL_REQUEST_TEMPLATE.md"
BUG_TEMPLATE = GITHUB / "ISSUE_TEMPLATE" / "bug_report.md"
FEATURE_TEMPLATE = GITHUB / "ISSUE_TEMPLATE" / "feature_request.md"
README = ROOT / "README.md"

ISSUES_URL = "https://github.com/Shreyas0786/ticketly/issues"


def test_policy_files_exist():
    for path in (CONTRIBUTING, PR_TEMPLATE, BUG_TEMPLATE, FEATURE_TEMPLATE):
        assert path.is_file(), f"missing policy file: {path.relative_to(ROOT)}"


def test_contributing_states_no_code_contributions():
    text = CONTRIBUTING.read_text().lower()
    assert "not" in text and "pull request" in text
    assert "source-visible" in text
    assert ISSUES_URL in CONTRIBUTING.read_text()


def test_pr_template_redirects_to_issues():
    text = PR_TEMPLATE.read_text()
    assert "aren't accepted" in text or "not accepted" in text or "not open" in text
    assert ISSUES_URL in text


def test_issue_templates_have_front_matter_and_prompts():
    bug = BUG_TEMPLATE.read_text()
    feature = FEATURE_TEMPLATE.read_text()

    # GitHub issue forms need name/about front matter delimited by ---
    for text in (bug, feature):
        assert text.startswith("---\n"), "issue template missing YAML front matter"
        front = text.split("---", 2)[1]
        assert "name:" in front and "about:" in front

    # bug template asks for the triage essentials
    low = bug.lower()
    for prompt in ("what happened", "expected", "version", "python", "os"):
        assert prompt in low, f"bug template missing prompt: {prompt}"

    # feature template asks for problem + proposed behavior
    flow = feature.lower()
    assert "problem" in flow
    assert "proposed behavior" in flow


def test_readme_has_contributing_section_and_badge():
    text = README.read_text()
    lower = text.lower()
    assert "## contributing & feedback" in lower
    assert ISSUES_URL in text
    assert "CONTRIBUTING.md" in text
    # PyPI downloads badge near the top
    assert "pepy.tech" in text or "img.shields.io/pypi/d" in text


def test_cross_links_resolve():
    # every relative .md link in CONTRIBUTING and the README's new section points to a real file
    for source in (CONTRIBUTING, README):
        text = source.read_text()
        for target in re.findall(r"\]\((?!https?://)([^)#]+\.md)\)", text):
            resolved = (source.parent / target).resolve()
            assert resolved.is_file(), f"{source.name} links to missing file: {target}"
