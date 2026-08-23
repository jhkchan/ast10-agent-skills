"""The pinned rubric must be verifiable from inside the repository.

A judged total is only comparable to another judged total if both were graded
against the same rubric bytes. RUBRIC_SHA names an upstream commit and cannot be
recomputed locally, so RUBRIC_CONTENT_SHA256 is the pin that can be -- and this
test is what makes it a pin rather than a decorative constant.
"""

import hashlib

from scripts import ship_floor


def test_vendored_rubric_exists():
    assert ship_floor.RUBRIC_PATH.is_file(), f"vendored rubric missing at {ship_floor.RUBRIC_PATH}"


def test_vendored_rubric_matches_the_pinned_content_hash():
    digest = hashlib.sha256(ship_floor.RUBRIC_PATH.read_bytes()).hexdigest()
    assert digest == ship_floor.RUBRIC_CONTENT_SHA256, (
        "vendor/skill-judge/SKILL.md does not match RUBRIC_CONTENT_SHA256. Either the "
        "rubric was edited (it must not be -- it is vendored verbatim) or the pin is "
        "stale. Scores graded against different rubric bytes are not comparable."
    )


def test_rubric_declares_all_eight_dimensions_summing_to_120():
    text = ship_floor.RUBRIC_PATH.read_text(encoding="utf-8")
    for dim in ship_floor.DIM_KEYS:
        assert f"### {dim}:" in text, f"{dim} not defined in the vendored rubric"
    assert "120 points total" in text


def test_upstream_commit_sha_is_recorded_in_provenance():
    prov = ship_floor.RUBRIC_PATH.parent / "PROVENANCE.md"
    body = prov.read_text(encoding="utf-8")
    assert ship_floor.RUBRIC_SHA in body
    assert ship_floor.RUBRIC_CONTENT_SHA256 in body
