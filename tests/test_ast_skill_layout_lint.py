"""D5 progressive-disclosure layout lint for the ten AST detector SKILL.md bodies.

Covers T-3.2 (plan.md): "the layout lint fails any SKILL.md whose body exceeds the
D5 line budget or embeds executable detector logic" (S-001), plus a mechanical,
deterministic proxy for the S-006 failure shape ("SKILL.md restates generic
definitions ... with no whitepaper-specific decision rule"). The full D1 <= 5 /
Grade-A judge-matrix scoring in S-006's second half requires the live judge harness
(T-2.3), which is out of this task's scope (T-3.2 touches only the ten SKILL.md
files) and is exercised at Step 05, not here.
"""

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = REPO_ROOT / "skills"

# D5 progressive-disclosure body budget (vendor/skill-judge/SKILL.md:293-320 in the
# REDACTED-SIBLING-REPO sibling repo): "Ideal: < 500 lines".
D5_LINE_BUDGET = 500

# Mechanism must live in scripts/ and references/, never in SKILL.md prose
# (spec.md line 51-52: "No mechanism; all implementation detail lives in
# scripts/ and references/"). A fenced python/py block is the concrete signal
# of embedded detector logic.
EXECUTABLE_FENCE_RE = re.compile(r"^```(python|py)\b", re.MULTILINE)

# S-006 failure shape, verbatim from spec.md's own example of a generic-definition
# restatement ("privilege escalation is when an attacker gains higher permissions").
GENERIC_DEFINITION_RE = re.compile(r"\bis when an attacker\b", re.IGNORECASE)

# Deterministic, non-brittle proxy for whitepaper-specific knowledge delta: at least
# one of these category-distinctive, proper-noun-grade markers (real CVE ids, named
# campaigns/frameworks/papers from the whitepaper) must appear in the body. Generic
# definition prose cannot satisfy this by construction.
REQUIRED_MARKERS = {
    "AST01": ["ClawHavoc"],
    "AST02": ["CVE-2025-59536", "CVE-2026-21852"],
    "AST03": ["LPCI", "arXiv:2507.10457"],
    "AST04": ["UnsafeLoader"],
    "AST05": ["Rug-Pull", "rug-pull"],
    "AST06": ["ClawJacked", "CVE-2026-32025"],
    "AST07": ["Rollback Attack", "Hot-Reload Abuse"],
    "AST08": ["SkillSpector"],
    "AST09": ["attempt_id", "bilateral receipt", "Bilateral Receipt"],
    "AST10": ["Universal Skill Format", "deny_write"],
}

AST_IDS = sorted(REQUIRED_MARKERS.keys())


def _split_frontmatter(text: str):
    """Return (frontmatter_dict, body_text) or raise AssertionError on malformed frontmatter."""
    assert text.startswith(
        "---\n"
    ), "SKILL.md must open with YAML frontmatter delimited by ---"
    end = text.find("\n---\n", 4)
    assert end != -1, "SKILL.md frontmatter is not closed with a second --- delimiter"
    raw_fm = text[4:end]
    body = text[end + len("\n---\n") :]
    fm = yaml.safe_load(raw_fm)
    assert isinstance(fm, dict), "SKILL.md frontmatter must parse as a YAML mapping"
    return fm, body


@pytest.mark.parametrize("ast_id", AST_IDS)
def test_skill_md_exists(ast_id):
    path = SKILLS_DIR / ast_id / "SKILL.md"
    assert path.is_file(), f"{path} does not exist"


@pytest.mark.parametrize("ast_id", AST_IDS)
def test_frontmatter_has_name_and_description(ast_id):
    path = SKILLS_DIR / ast_id / "SKILL.md"
    fm, _ = _split_frontmatter(path.read_text(encoding="utf-8"))
    assert fm.get("name"), f"{path} frontmatter missing non-empty 'name'"
    description = fm.get("description")
    assert (
        description and len(description) >= 40
    ), f"{path} frontmatter 'description' must be a specific, non-placeholder string (>=40 chars)"


@pytest.mark.parametrize("ast_id", AST_IDS)
def test_body_within_d5_line_budget(ast_id):
    path = SKILLS_DIR / ast_id / "SKILL.md"
    _, body = _split_frontmatter(path.read_text(encoding="utf-8"))
    line_count = len(body.rstrip("\n").split("\n"))
    assert line_count <= D5_LINE_BUDGET, (
        f"{path} body is {line_count} lines, exceeds the D5 progressive-disclosure "
        f"budget of {D5_LINE_BUDGET} lines"
    )


@pytest.mark.parametrize("ast_id", AST_IDS)
def test_body_has_no_embedded_executable_detector_logic(ast_id):
    path = SKILLS_DIR / ast_id / "SKILL.md"
    _, body = _split_frontmatter(path.read_text(encoding="utf-8"))
    assert not EXECUTABLE_FENCE_RE.search(
        body
    ), f"{path} embeds a python/py fenced code block; mechanism belongs in scripts/, not SKILL.md"


@pytest.mark.parametrize("ast_id", AST_IDS)
def test_body_has_no_generic_definition_restatement(ast_id):
    path = SKILLS_DIR / ast_id / "SKILL.md"
    _, body = _split_frontmatter(path.read_text(encoding="utf-8"))
    assert not GENERIC_DEFINITION_RE.search(body), (
        f"{path} restates a generic industry definition (S-006 failure shape) instead of a "
        f"whitepaper-specific decision rule"
    )


@pytest.mark.parametrize("ast_id", AST_IDS)
def test_body_has_whitepaper_specific_knowledge_marker(ast_id):
    path = SKILLS_DIR / ast_id / "SKILL.md"
    _, body = _split_frontmatter(path.read_text(encoding="utf-8"))
    markers = REQUIRED_MARKERS[ast_id]
    assert any(m in body for m in markers), (
        f"{path} body contains none of the whitepaper-specific markers {markers}; "
        f"knowledge-delta content must anchor on the whitepaper's own evidence, not generic prose"
    )
