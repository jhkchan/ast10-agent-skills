"""`scripts/dogfood.py` — this repo's detectors pointed at this repo's skills.

Two things need holding down, and they are different kinds of claim.

**The USF translation must not invent permissions.** The detectors were written
against a flatter package dict than the Universal Skill Format manifests that
actually ship, so `translate_permissions()` sits between them. A translator is
the easiest place in this repo to accidentally launder a security property:
read a key that isn't there and call it closed, or fail to find a key and call
it open. The tests below pin both directions — a USF `shell: true` must arrive
as shell-allowed-with-no-allowlist, an empty USF allowlist must arrive as
`deny-all` and never as `allow-all`, and a nested `files.deny_write` must
actually reach the detector that looks for `deny_write`.

**The waiver mechanism must not become a suppression list.** A waiver needs a
written reason and an evidence fragment that pins it to one file; a waiver that
matches nothing fails the run. Without that second half, `config/
dogfood_waivers.yml` would accumulate dead entries and the dogfood job would
degrade into a green light with a growing blind spot behind it.

The last test is the live one: the repo as it stands, dogfooded, clean.
"""

from __future__ import annotations

import pathlib
import textwrap

import pytest

from scripts import dogfood

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


# ---------------------------------------------------------- permission mapping


def test_absent_permissions_translate_to_empty_not_to_a_default():
    """AST06's missing-sandbox-declaration check must still fire. A translator
    that filled in a default posture here would hide the one case where "no
    posture declared" is itself the finding."""
    assert dogfood.translate_permissions(None) == {}
    assert dogfood.translate_permissions({}) == {}


def test_usf_shell_true_becomes_shell_allowed_with_no_command_allowlist():
    """USF v1 spells shell access as a bare boolean and carries no command
    allowlist, so `true` is exactly AST06's unrestricted-shell-exec shape."""
    translated = dogfood.translate_permissions({"files": {}, "network": {"allow": []}, "shell": True})
    assert translated["shell"] == {"allowed": True, "commands": []}


def test_usf_shell_false_stays_a_present_but_closed_declaration():
    translated = dogfood.translate_permissions({"files": {}, "network": {"allow": []}, "shell": False})
    assert translated["shell"] == {"allowed": False, "commands": []}
    assert translated, "a closed posture is a declared posture, not an absent one"


def test_empty_usf_allowlist_is_deny_all_never_allow_all():
    """USF v1 evaluates egress default-deny: an empty `allow` means no host is
    reachable. Translating it to "allow-all" would invert the policy."""
    translated = dogfood.translate_permissions({"files": {}, "network": {"allow": []}, "shell": False})
    assert translated["network"]["policy"] == "deny-all"


def test_populated_usf_allowlist_becomes_allow_list_with_entries_intact():
    translated = dogfood.translate_permissions(
        {
            "files": {},
            "network": {"allow": ["docs.example.com", "*"]},
            "shell": False,
        }
    )
    assert translated["network"]["policy"] == "allow-list"
    # The wildcard has to survive translation or AST05's check never sees it.
    assert "*" in translated["network"]["allow"]


def test_no_usf_input_can_produce_an_allow_all_policy():
    """USF v1 has no spelling for unrestricted egress. If the translator could
    emit "allow-all", it — not the manifest — would be deciding that."""
    for network in ({"allow": []}, {"allow": ["a.example"]}, {"deny": "*"}, {}):
        translated = dogfood.translate_permissions({"files": {}, "network": network, "shell": False})
        assert translated["network"]["policy"] != "allow-all"


def test_nested_deny_write_reaches_the_detector_that_looks_for_it():
    """The bug this adapter exists to prevent: AST03 reads
    `permissions.deny_write`, USF nests it at `permissions.files.deny_write`,
    and a missed key reads as "no write restriction at all"."""
    translated = dogfood.translate_permissions(
        {
            "files": {"read": ["./SKILL.md"], "write": [], "deny_write": ["SOUL.md"]},
            "network": {"allow": []},
            "shell": False,
        }
    )
    assert translated["deny_write"] == ["SOUL.md"]
    assert translated["read"] == ["./SKILL.md"]
    assert translated["write"] == []


# ------------------------------------------------------------- content hashing


def test_content_hash_string_splits_into_algorithm_and_value():
    assert dogfood.translate_content_hash("sha256:abc123") == {
        "algorithm": "sha256",
        "value": "abc123",
    }


@pytest.mark.parametrize("declared", [None, "", "abc123", "sha256:", ":abc123", 42])
def test_unusable_content_hash_reads_as_missing_not_as_mismatch(declared):
    """AST01 has two distinct findings. A malformed hash is the *missing* one:
    reporting a mismatch would assert a comparison nobody could have made."""
    assert dogfood.translate_content_hash(declared) is None


def test_the_dogfooded_surface_is_the_surface_the_content_hash_covers():
    """If the dogfooded file set diverged from `SURFACE_GLOBS`, AST01's
    re-derived digest would be comparing two different corpora, and every
    package would report a spurious content-hash mismatch."""
    from scripts.content_hash import content_sha256

    skill_dir = REPO_ROOT / "skills" / "AST01"
    pkg = dogfood.load_package(skill_dir)
    declared = pkg["manifest"]["content_hash"]

    assert declared is not None, "AST01 ships a declared content hash"
    assert declared["value"] == content_sha256(skill_dir)


def test_load_package_exposes_manifest_description_and_surface_files():
    pkg = dogfood.load_package(REPO_ROOT / "skills" / "AST01")
    assert pkg["name"] == "ast01-malicious-skills"
    assert pkg["manifest"]["description"].strip()
    assert "SKILL.md" in pkg["files"]
    assert "scripts/detector.py" in pkg["files"]
    # skill.usf.yaml is deliberately outside the hashed surface -- the field
    # carrying the hash cannot be an input to the hash.
    assert "skill.usf.yaml" not in pkg["files"]


def test_load_package_refuses_a_directory_with_no_manifest(tmp_path):
    (tmp_path / "orphan").mkdir()
    with pytest.raises(dogfood.DogfoodError, match="no skill.usf.yaml"):
        dogfood.load_package(tmp_path / "orphan")


# --------------------------------------------------------------------- waivers


def _write_waivers(tmp_path: pathlib.Path, body: str) -> pathlib.Path:
    path = tmp_path / "waivers.yml"
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    return path


def test_a_missing_waiver_file_means_no_waivers_not_an_error(tmp_path):
    assert dogfood.load_waivers(tmp_path / "absent.yml") == []


@pytest.mark.parametrize("omitted", ["skill", "scenario", "evidence_contains", "reason"])
def test_a_waiver_missing_any_required_field_is_rejected(tmp_path, omitted):
    fields = {
        "skill": "AST04",
        "scenario": "AST04-yaml-injection",
        "evidence_contains": "scripts/detector.py",
        "reason": "self-match on the detector's own evidence string",
    }
    del fields[omitted]
    body = "waivers:\n" + "".join(f"  {'- ' if i == 0 else '  '}{k}: {v}\n" for i, (k, v) in enumerate(fields.items()))
    with pytest.raises(dogfood.DogfoodError, match=omitted):
        dogfood.load_waivers(_write_waivers(tmp_path, body))


def test_a_waiver_only_applies_to_the_evidence_it_was_written_for():
    entry = {
        "skill": "AST04",
        "scenario": "AST04-yaml-injection",
        "evidence_contains": "scripts/detector.py",
        "reason": "self-match",
    }
    assert dogfood._waiver_matches(entry, "AST04", "AST04-yaml-injection", "scripts/detector.py: ... call")
    # Same skill, same scenario, DIFFERENT file -- a real finding, not covered.
    assert not dogfood._waiver_matches(entry, "AST04", "AST04-yaml-injection", "scripts/helper.py: ... call")
    assert not dogfood._waiver_matches(entry, "AST05", "AST04-yaml-injection", "scripts/detector.py: ... call")


def test_a_waiver_that_matches_nothing_fails_the_run(tmp_path):
    """The half that keeps the waiver file from rotting. Without it a stale
    entry sits there looking like due diligence and covering nothing."""
    waivers = _write_waivers(
        tmp_path,
        """\
        waivers:
          - skill: AST01
            scenario: AST01-does-not-exist
            evidence_contains: nowhere.py
            reason: a scenario no detector reports
        """,
    )
    report = dogfood.run(waivers_path=waivers)
    assert report.stale_waivers == ("AST01::AST01-does-not-exist",)
    assert not report.ok


def test_unwaived_findings_fail_the_run(tmp_path):
    """With waivers switched off, the known self-matches must resurface. If
    this passed, the dogfood pass would be finding nothing at all."""
    report = dogfood.run(waivers_path=tmp_path / "absent.yml")
    assert report.unwaived, "dogfood found nothing even with waivers disabled"
    assert not report.ok


# ------------------------------------------------------------------- live pass


def test_every_skill_and_detector_participates():
    report = dogfood.run()
    assert len(report.skills_scanned) == 11
    # advisory ships a triage script, not a detector -- ten detector modules.
    assert len(report.detectors_run) == 10
    assert "advisory" in report.skills_scanned
    assert "advisory" not in report.detectors_run


def test_the_repository_passes_its_own_dogfood():
    report = dogfood.run()
    assert report.unwaived == (), "unwaived dogfood findings: " + "; ".join(
        f"{f.skill} [{f.scenario}] {f.evidence}" for f in report.unwaived
    )
    assert report.stale_waivers == (), f"stale waivers: {report.stale_waivers}"
    assert report.ok


def test_every_shipped_waiver_carries_a_substantive_reason():
    """A waiver's reason is the whole reason a waiver is acceptable. One-word
    reasons ("known", "wontfix") are how a suppression list gets started."""
    for waiver in dogfood.load_waivers():
        assert len(waiver["reason"].split()) >= 15, (
            f"{waiver['skill']}::{waiver['scenario']}: reason is too thin to review"
        )


def test_cli_exits_zero_on_a_clean_repository(capsys):
    assert dogfood.main([]) == 0
    assert "no unwaived findings" in capsys.readouterr().out


def test_cli_json_output_is_machine_readable(capsys):
    import json

    assert dogfood.main(["--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert len(payload["skills_scanned"]) == 11
    assert all(f["waived"] for f in payload["findings"])


# ------------------------------------------------------- the published report

DOGFOOD_REPORT = REPO_ROOT / "docs" / "dogfood-report.md"


def test_the_committed_dogfood_report_is_up_to_date():
    """A report that no longer matches the run is worse than no report: it is the
    half a reader checks."""
    assert dogfood.main(["--markdown", "--out", str(DOGFOOD_REPORT), "--check"]) == 0, (
        "run `python3 scripts/dogfood.py --markdown --out docs/dogfood-report.md`"
    )


def test_the_report_lists_every_finding_the_run_produced():
    """No finding may be summarised away. Each one appears with its own evidence."""
    report = dogfood.run()
    text = DOGFOOD_REPORT.read_text(encoding="utf-8")
    for finding in report.findings:
        assert finding.skill in text and finding.scenario in text
        # The evidence itself, not a paraphrase (pipes are escaped for the table).
        assert finding.evidence.replace("\n", " ") in text.replace("\\|", "|"), finding


def test_the_report_states_the_check_denominator_not_only_the_numerator():
    """ "9 findings" is unanchored without "out of how many checks"."""
    text = DOGFOOD_REPORT.read_text(encoding="utf-8")
    executions = dogfood.check_executions()
    assert executions > 0
    assert f"{executions} individual check executions" in text


def test_an_unwaived_finding_renders_as_unwaived():
    """The report must be able to say the bad word, or its PASS means nothing."""
    doctored = dogfood.DogfoodReport(
        findings=(
            dogfood.DogfoodFinding(
                skill="AST03",
                detector="AST06",
                scenario="AST06-root-write-scope",
                evidence="write scope reaches /",
                waived=False,
            ),
        ),
        stale_waivers=("AST04::AST04-yaml-injection",),
        skills_scanned=("AST03",),
        detectors_run=("AST06",),
    )
    rendered = dogfood.render_markdown(doctored)
    assert "**UNWAIVED**" in rendered
    assert "Verdict: **FAIL**" in rendered
    assert "### Stale waivers" in rendered
    assert "AST04::AST04-yaml-injection" in rendered


def test_the_wider_scan_view_claim_in_the_report_is_recomputed_not_asserted():
    """The report says scanning `skill.usf.yaml` as text adds nothing. That is a
    measurable claim, so it is measured here rather than believed."""
    surface = {(f.skill, f.scenario, f.evidence) for f in dogfood.run().findings}
    scan = dogfood.scan_view_findings()
    only_in_scan = scan - surface
    text = DOGFOOD_REPORT.read_text(encoding="utf-8")
    if only_in_scan:
        assert "appear only when the manifests and prose are scanned as text" in text
        for skill, scenario, _evidence in only_in_scan:
            assert skill in text and scenario in text
    else:
        assert "The wider view finds exactly the same set" in text


def test_the_wider_scan_view_actually_reads_the_usf_manifests():
    """Guards the section above from passing vacuously: if the bridge stopped
    reading `skill.usf.yaml` the claim would be true and meaningless."""
    from cli.lib import bridge

    files, _skipped = bridge.read_scan_files(REPO_ROOT / "skills" / "AST01")
    assert "skill.usf.yaml" in files
    assert "coverage-matrix.md" in files


def test_markdown_to_stdout_needs_no_output_path(capsys):
    assert dogfood.main(["--markdown"]) == 0
    assert capsys.readouterr().out.startswith("# Dogfood report")
