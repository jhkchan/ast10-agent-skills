"""Tests for scripts/generate_badges.py and the badge row it publishes.

A badge is a published figure. This repository drift-guards every published
figure, because the alternative has bitten it four times — a dashboard banner
that said no judged run existed while four scorecards sat in the tree, run-2
figures surviving into run 3, an ``n=33`` that had become 32, and a README
claiming there were no scorecards. A badge is the most-read figure on the page
and the least likely to be re-checked by hand.

So ``--check`` passing is necessary but not sufficient here: it only proves the
generator agrees with itself, which a hard-coded literal inside the generator
would also satisfy. Every figure in the row is therefore RE-DERIVED in this file,
from the source artifact, without calling the generator's own derivation — and
compared against the text actually committed to README.md.
"""

from __future__ import annotations

import json
import re
import statistics
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import generate_badges as gen  # noqa: E402
from scripts.ship_floor import aggregate_verdict  # noqa: E402
from validators.usf import validate_manifest_file  # noqa: E402

README = REPO_ROOT / "README.md"

#: `[![alt](shields url)](link)` — the only shape a badge in this row may take.
BADGE_RE = re.compile(
    r"\[!\[(?P<alt>[^\]]*)\]\((?P<img>https://img\.shields\.io/badge/[^)\s]+)\)\]\((?P<link>[^)\s]+)\)"
)


def _readme() -> str:
    return README.read_text(encoding="utf-8")


def _badge_block() -> str:
    """The committed text between the badge markers, markers excluded."""
    text = _readme()
    start = text.find(gen.BEGIN)
    end = text.find(gen.END)
    assert start != -1 and end != -1 and start < end, "README.md has lost its badge markers"
    return text[start + len(gen.BEGIN) : end]


def _badges() -> list[re.Match[str]]:
    matches = list(BADGE_RE.finditer(_badge_block()))
    assert matches, "the badge block parsed to zero badges — the row shape changed"
    return matches


def _shield_fields(img_url: str) -> list[str]:
    """The decoded label/message fields of a shields.io badge URL, colour dropped."""
    from urllib.parse import unquote

    path = img_url.rsplit("/badge/", 1)[1]
    # Split on single hyphens only: shields doubles a literal `-` inside a field.
    fields = re.split(r"(?<!-)-(?!-)", path)
    return [unquote(field).replace("--", "-").replace("__", "_") for field in fields[:-1]]


def _colour(img_url: str) -> str:
    return img_url.rsplit("-", 1)[1]


def _badge_by_label(label: str) -> re.Match[str]:
    for match in _badges():
        fields = _shield_fields(match.group("img"))
        if len(fields) == 2 and fields[0] == label:
            return match
    raise AssertionError(f"the badge row has no {label!r} badge")


def _message(label: str) -> str:
    return _shield_fields(_badge_by_label(label).group("img"))[1]


# ---------------------------------------------------------------------------
# 1. The row is generated, and a stale badge fails the build
# ---------------------------------------------------------------------------


def test_the_committed_badge_row_is_the_one_its_sources_produce():
    assert gen.main(["--check"]) == 0, "README.md's badge row is out of date — run scripts/generate_badges.py"


@pytest.mark.parametrize(
    "stale,replacement",
    [
        ("111.3", "119.9"),  # a flattering pooled mean
        ("11%2F11%20SHIP", "12%2F12%20SHIP"),  # a ship count that outran the corpus
        # The coverage count and the delta moved off their pills into their alt
        # text when the row was reworded; both are still derived and still
        # hand-editable, so the case follows the figure rather than the pill.
        ("7 of 10", "10 of 10"),  # an F1 coverage claim that hides the boundary
        ("+0.52", "+0.90"),  # an inflated control delta
        ("62%20%C2%B7%20tiered", "58%20%C2%B7%20tiered"),  # the pre-registry scenario estimate
    ],
)
def test_check_fails_when_a_badge_outruns_its_source(tmp_path, stale, replacement):
    """The failure mode this whole file exists for: a figure edited by hand."""
    copy = tmp_path / "README.md"
    original = _readme()
    assert stale in original, f"{stale!r} is no longer in the badge row; this test is testing nothing"
    copy.write_text(original.replace(stale, replacement, 1), encoding="utf-8")

    assert gen.main(["--check", "--readme", str(copy)]) == 1, f"a hand-edited {stale!r} passed --check"
    assert gen.main(["--readme", str(copy)]) == 0
    assert copy.read_text(encoding="utf-8") == original, "regenerating did not restore the derived figure"


def test_the_generator_rewrites_the_marked_block_and_nothing_else(tmp_path):
    copy = tmp_path / "README.md"
    original = _readme()
    copy.write_text(original.replace(_badge_block(), "\nplaceholder\n", 1), encoding="utf-8")
    assert gen.main(["--readme", str(copy)]) == 0
    assert copy.read_text(encoding="utf-8") == original


def test_a_readme_without_markers_is_refused_rather_than_guessed_at():
    with pytest.raises(gen.BadgeError, match="markers"):
        gen.rewrite("# title\n\nno markers here\n", "block")


# ---------------------------------------------------------------------------
# 2. Every figure, re-derived from its source and compared to the committed text
# ---------------------------------------------------------------------------


def test_the_judged_badge_matches_a_recompute_over_the_scorecards():
    """Ship count, pooled mean and panel size, recomputed through the live gate."""
    shipped, judgments, panels = 0, [], set()
    for path in sorted((REPO_ROOT / "eval" / "scorecards").glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        aggregate = payload.get("aggregate")
        verdict, _ = aggregate_verdict(str(payload.get("skill", path.stem)), aggregate)
        shipped += verdict == "SHIP"
        judgments += list(aggregate.get("judgments") or [])
        panels.add(tuple(sorted(payload["providers"])))
    assert len(panels) == 1, f"the scorecards record more than one judge panel: {sorted(panels)}"
    roster = len([p for p in (REPO_ROOT / "skills").iterdir() if (p / "SKILL.md").is_file()])
    expected = (
        f"{shipped}/{roster} SHIP {gen.DOT} {round(statistics.fmean(judgments), 1):g}/120 "
        f"{gen.DOT} {len(panels.pop())}-model panel"
    )
    assert _message("judged") == expected


def test_the_f1_badge_matches_the_committed_f1_report():
    categories = json.loads((REPO_ROOT / "eval" / "f1-report.json").read_text(encoding="utf-8"))["categories"]
    published = [c for c in categories if c["status"] == "pass"]
    uncovered = [c for c in categories if c["status"] == "declared-and-uncovered"]
    assert not [c for c in categories if c["status"] == "fail"], (
        "a category now falls below the F1 floor; the badge must say so rather than reading clean"
    )
    scores = {c["scenario_level"]["f1"] for c in published}
    assert len(scores) == 1, (
        f"the categories that publish an F1 no longer share one score {sorted(scores)}; "
        "the badge must not show a single number as if they did"
    )
    assert _message("detector F1") == f"{scores.pop():.3f} {gen.DOT} where a package can decide it"
    alt = _badge_by_label("detector F1").group("alt")
    assert f"{len(published)} of {len(categories)}" in alt, f"the coverage count left the row entirely: {alt!r}"
    assert f"{len(uncovered)} publish none by rule" in alt, f"the by-rule count left the row entirely: {alt!r}"


def test_the_f1_badge_does_not_read_as_a_failure():
    """Three categories publish no F1 BY RULE. That is the honesty apparatus.

    The badge has to make the absence legible — a bare `7 of 10` invites a reader
    to supply the missing, wrong explanation — so the pill states the SCOPE of the
    number it shows, its alt text carries the rule in full, and it links the page
    that spells the rule out.
    """
    badge = _badge_by_label("detector F1")
    message = _shield_fields(badge.group("img"))[1]
    assert "where a package can decide it" in message, (
        f"the F1 badge reads {message!r}; the boundary of the number must be stated, not implied"
    )
    assert not re.search(r"\d+\s+of\s+\d+", message), (
        f"the F1 pill shows a ratio again ({message!r}); it invites exactly the subtraction the wording prevents"
    )
    assert "publish none by rule" in badge.group("alt"), (
        f"the by-rule clause left the pill; the row must still carry the rule: {badge.group('alt')!r}"
    )
    for loaded_word in ("fail", "missing", "gap", "incomplete", "0 of", "no coverage"):
        assert loaded_word not in message.lower(), f"the F1 badge must not read as a shortfall: {message!r}"
    assert badge.group("link") == "docs/f1-report.md"
    report = (REPO_ROOT / "docs" / "f1-report.md").read_text(encoding="utf-8")
    assert "publish no F1 at all" in report, "the page the badge links must explain the three that publish none"


def test_the_output_eval_badge_matches_the_control_arm_of_the_latest_iteration():
    iteration = gen._latest_iteration()
    payload = json.loads((iteration / "benchmark.json").read_text(encoding="utf-8"))
    controls = [c for c in payload["cases"] if "-control-" in c["eval"]]
    delta = statistics.fmean(c["with_skill"]["pass_rate"] for c in controls) - statistics.fmean(
        c["without_skill"]["pass_rate"] for c in controls
    )
    with_arm = statistics.fmean(c["with_skill"]["pass_rate"] for c in controls)
    without_arm = statistics.fmean(c["without_skill"]["pass_rate"] for c in controls)
    assert _message("output eval") == f"{round(with_arm, 2):.2f} with {gen.DOT} {round(without_arm, 2):.2f} without"
    alt = _badge_by_label("output eval").group("alt")
    assert f"+{round(delta, 2):.2f}" in alt, f"the measured delta left the row entirely: {alt!r}"
    assert controls, "the badge claims a blind control; the workspace must hold control cases"


def test_the_output_eval_badge_is_measured_over_the_control_arm_alone():
    """The whole-corpus arms are different, larger-n numbers. Publishing any of them
    under the words 'blind control' would badge the wrong measurement.

    The row shows two arms on the pill and the delta in the alt, so all three are
    checked against their whole-corpus look-alikes rather than the delta alone.
    """
    iteration = gen._latest_iteration()
    payload = json.loads((iteration / "benchmark.json").read_text(encoding="utf-8"))
    summary = payload["run_summary"]
    corpus_delta = round(summary["delta"]["pass_rate"], 2)
    corpus_with = round(summary["with_skill"]["pass_rate"]["mean"], 2)
    corpus_without = round(summary["without_skill"]["pass_rate"]["mean"], 2)
    control_delta, control_with, control_without = gen.control_delta()[:3]
    message = _message("output eval")
    alt = _badge_by_label("output eval").group("alt")
    assert f"{control_with:.2f} with" in message and f"{control_without:.2f} without" in message
    assert f"+{control_delta:.2f}" in alt
    if corpus_with != control_with:
        assert f"{corpus_with:.2f} with" not in message
    if corpus_without != control_without:
        assert f"{corpus_without:.2f} without" not in message
    if corpus_delta != control_delta:
        assert f"+{corpus_delta:.2f}" not in alt


def test_the_usf_badge_matches_the_validator_over_every_shipped_manifest():
    skills = sorted(p for p in (REPO_ROOT / "skills").iterdir() if (p / "SKILL.md").is_file())
    conformant = sum(
        1 for s in skills if (s / "skill.usf.yaml").is_file() and validate_manifest_file(s / "skill.usf.yaml").ok
    )
    assert _message("USF v1.0") == f"{conformant}/{len(skills)} skills {gen.DOT} schema-validated"


def test_the_usf_badge_says_something_a_reader_can_act_on():
    """The maintainer asked for USF explicitly. Naming the format is not enough:
    the badge has to say that every skill ships a v1.0 manifest and that it is
    validated, and link the schema it is validated against."""
    badge = _badge_by_label("USF v1.0")
    message = _shield_fields(badge.group("img"))[1]
    assert "skills" in message and "validated" in message, message
    assert badge.group("link") == "schemas/usf-v1.schema.json"
    assert (REPO_ROOT / "schemas" / "usf-v1.schema.json").is_file()


def test_the_scenario_badge_matches_the_registry():
    registry = yaml.safe_load((REPO_ROOT / "scenarios" / "registry.yaml").read_text(encoding="utf-8"))
    assert _message("scenarios") == f"{len(registry['scenarios'])} {gen.DOT} tiered by decidability"
    tiers = {s["tier"] for s in registry["scenarios"]}
    assert tiers <= set(registry["tier_doctrine"]), (
        f"the badge says the tiers are a decidability axis; {sorted(tiers - set(registry['tier_doctrine']))} "
        "has no tier_doctrine entry saying what it does or does not decide"
    )


def test_the_licence_badge_matches_the_licence_file():
    assert "Apache License" in (REPO_ROOT / "LICENSE").read_text(encoding="utf-8")
    assert _message("license") == "Apache-2.0"
    assert _badge_by_label("license").group("link") == "LICENSE"


def test_the_rubric_badge_credits_the_vendored_upstream():
    """The rubric badge doubles as attribution, so its slug is read from the
    provenance record rather than typed, and it links the upstream itself."""
    provenance = (REPO_ROOT / "vendor" / "skill-judge" / "PROVENANCE.md").read_text(encoding="utf-8")
    slug = re.search(r"Upstream\s*\|\s*`([\w.-]+/[\w.-]+)`", provenance).group(1)
    badge = _badge_by_label("rubric")
    assert _shield_fields(badge.group("img"))[1] == slug
    assert badge.group("link") == f"https://github.com/{slug}"


# ---------------------------------------------------------------------------
# 3. Posture: non-endorsement, scannability, colour meaning
# ---------------------------------------------------------------------------


def test_the_row_states_that_this_is_not_an_owasp_project():
    block = _badge_block()
    assert "NOT%20an%20OWASP%20project" in block, "the badge row must carry the non-endorsement notice"
    notice = _badges()[0]
    assert notice.group("link") == "NOTICE"
    assert "NOT AN OWASP PROJECT" in " ".join((REPO_ROOT / "NOTICE").read_text(encoding="utf-8").split()).upper()


def test_no_badge_implies_this_is_an_owasp_project():
    """The repository name already misleads. The row must not compound it."""
    for match in _badges():
        rendered = " ".join(_shield_fields(match.group("img")) + [match.group("alt")]).lower()
        if "owasp" not in rendered:
            continue
        assert "not an owasp project" in rendered, f"a badge names OWASP without disclaiming it: {rendered!r}"
    assert "owasp.org" not in _badge_block(), "no badge may link the OWASP project page as if it were this project's"


def test_the_row_stays_scannable():
    badges = _badges()
    assert len(badges) <= gen.MAX_BADGES, f"{len(badges)} badges is a wall, not a row"
    assert len(badges) >= 5, "a row this short is not carrying the evidence the repo is different for"


def test_the_row_sits_immediately_under_the_h1():
    lines = _readme().splitlines()
    assert lines[0].startswith("# "), "README.md must open with its H1"
    assert lines[1].strip() == ""
    assert lines[2] == gen.BEGIN, "the badge row must be the first thing under the H1, not buried below prose"


def test_the_badge_row_does_not_push_the_disclaimer_below_the_fold():
    """Two above-the-fold guarantees other tests enforce as line budgets.

    ``tests/test_docs.py::test_readme_disclaimer_is_prominent`` and
    ``tests/test_packaging.py::test_readme_links_the_owasp_project_page`` both
    assert on line numbers near the top of README.md. The badge row is the only
    thing that has ever sat between the H1 and them, so it owns the budget:
    growing the row past its line allowance breaks those two tests, and this
    assertion says so where a future editor of THIS file will read it.
    """
    lines = _readme().splitlines()
    block_lines = _badge_block().strip("\n").count("\n") + 1
    assert block_lines <= 3, f"the badge block is {block_lines} source lines; more than 3 breaks the fold budget"
    owasp = next(i for i, line in enumerate(lines) if "owasp.org/www-project-agentic-skills-top-10" in line)
    disclaimer = next(i for i, line in enumerate(lines) if "Not an OWASP project" in line)
    assert owasp < 10, f"the badge row pushed the OWASP project link to line {owasp + 1}"
    assert disclaimer < 40, f"the badge row pushed the non-endorsement heading to line {disclaimer + 1}"


def test_every_badge_links_something_that_substantiates_it():
    for match in _badges():
        link = match.group("link")
        if link.startswith("https://"):
            assert link.startswith("https://github.com/"), f"unexpected off-repo badge link: {link}"
            continue
        assert (REPO_ROOT / link).exists(), f"badge links {link}, which does not exist"


def test_the_three_evidence_badges_read_as_one_set():
    """Judged prose, detector accuracy, agent output: three questions, one set."""
    colours = {
        label: _colour(_badge_by_label(label).group("img")) for label in ("judged", "detector F1", "output eval")
    }
    assert len(set(colours.values())) == 1, f"the evidence badges have drifted apart: {colours}"
    assert set(colours.values()) == {gen.EVIDENCE}


def test_the_colours_are_the_four_declared_roles_and_nothing_else():
    roles = {gen.EVIDENCE, gen.STANDARD, gen.PROVENANCE_COLOUR, gen.CAUTION}
    used = {_colour(m.group("img")) for m in _badges()}
    assert used <= roles, f"the row uses colour(s) outside the declared roles: {sorted(used - roles)}"
    assert _colour(_badge_by_label("USF v1.0").group("img")) == gen.STANDARD, "USF is a standard, not a score"


def test_no_badge_in_the_clean_state_is_coloured_as_a_success():
    """Green is a pass claim. Not one figure in this row is a pass claim — the
    repo's own F1 page calls a perfect score over its corpus 'nearly
    uninformative' — so no badge may be painted as one."""
    success_greens = {"4c1", "brightgreen", "green", "success", "97ca00", "0e8a16", "2ea44f"}
    for match in _badges():
        assert _colour(match.group("img")).lower() not in success_greens, match.group("img")


# ---------------------------------------------------------------------------
# 4. The caveat states are not hard-coded to the clean state
# ---------------------------------------------------------------------------


def test_a_category_below_the_f1_floor_flips_the_badge_to_caution(monkeypatch):
    monkeypatch.setattr(gen, "f1_coverage", lambda: (["AST01"] * 6, ["AST04"], ["AST05", "AST07", "AST09"]))
    badge = next(b for b in gen.build_badges() if b.label == "detector F1")
    assert "below floor" in badge.message
    assert badge.colour == gen.CAUTION, "a category below the floor must not be coloured like a clean row"


def test_a_manifest_that_fails_validation_flips_the_usf_badge_to_caution(monkeypatch):
    monkeypatch.setattr(gen, "usf_conformance", lambda: (9, 11))
    badge = next(b for b in gen.build_badges() if b.label == "USF v1.0")
    assert badge.message == f"9/11 skills {gen.DOT} 2 not conformant"
    assert badge.colour == gen.CAUTION


def test_a_skill_with_no_manifest_counts_against_the_usf_numerator(tmp_path, monkeypatch):
    monkeypatch.setattr(gen, "SKILLS_DIR", tmp_path)
    for name in ("alpha", "beta"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "SKILL.md").write_text("---\nname: x\n---\n", encoding="utf-8")
    assert gen.usf_conformance() == (0, 2), "a missing manifest must not be silently excluded from the denominator"


def test_a_scorecard_for_a_skill_that_does_not_exist_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(gen, "SKILLS_DIR", tmp_path)
    (tmp_path / "alpha").mkdir()
    (tmp_path / "alpha" / "SKILL.md").write_text("---\nname: x\n---\n", encoding="utf-8")
    with pytest.raises(gen.BadgeError, match="do not exist"):
        gen.judged_figures()


def test_the_registry_count_is_cross_checked_against_its_own_rows(tmp_path, monkeypatch):
    fake = tmp_path / "registry.yaml"
    fake.write_text(yaml.safe_dump({"counts": {"total": 99}, "scenarios": [{"id": "A"}]}), encoding="utf-8")
    monkeypatch.setattr(gen, "REGISTRY", fake)
    with pytest.raises(gen.BadgeError, match="counts.total"):
        gen.scenario_count()


def test_an_iteration_with_no_control_case_is_refused(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    (workspace / "iteration-9").mkdir(parents=True)
    (workspace / "iteration-9" / "benchmark.json").write_text(
        json.dumps({"cases": [{"eval": "AST01-case-1", "with_skill": {}, "without_skill": {}}]}), encoding="utf-8"
    )
    monkeypatch.setattr(gen, "EVAL_WORKSPACE", workspace)
    with pytest.raises(gen.BadgeError, match="control"):
        gen.control_delta()


def test_the_latest_iteration_is_the_one_that_is_badged():
    assert gen._latest_iteration().name == "iteration-3", (
        "a newer iteration landed; the control-delta badge follows it automatically, "
        "but this assertion is the record that the move was noticed"
    )


# ---------------------------------------------------------------------------
# 5. shields.io escaping
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,encoded",
    [
        ("Apache-2.0", "Apache--2.0"),
        ("schema-validated", "schema--validated"),
        ("11/11 SHIP", "11%2F11%20SHIP"),
        ("+0.52 vs blind control", "%2B0.52%20vs%20blind%20control"),
        ("a_b", "a__b"),
        ("7 of 10 · 3 publish none by rule", "7%20of%2010%20%C2%B7%203%20publish%20none%20by%20rule"),
    ],
)
def test_shield_escaping_survives_the_round_trip(raw, encoded):
    assert gen._shield(raw) == encoded
    assert _shield_fields(f"https://img.shields.io/badge/{encoded}-colour") == [raw]
