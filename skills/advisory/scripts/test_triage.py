"""Tests for the advisory/orchestrator triage skill (skills/advisory).

Covers S-002 (spec.md): a finding routed through the whitepaper's own
"Which AST Does My Finding Belong To?" decision tree must land on the right
primary AST category with actionable guidance, must record any additional
matching category as a contributing control failure rather than a second
primary (decision-tree branch 5), and must never claim to contribute to a
Gate B F1 denominator.
"""

from triage import F1_ELIGIBLE, triage


def test_ast03_overprivileged_write_access_to_secrets():
    # The exact S-002 acceptance-scenario finding from spec.md.
    result = triage("overprivileged agent with write access to production secrets")
    assert result["ast_id"] == "AST03"
    assert result["category"] == "Over-Privileged Skills"
    assert "rotat" in result["guidance"].lower()
    assert "read-only" in result["guidance"].lower()
    assert result["contributing"] == []


def test_ast01_hidden_payload_at_publish_time():
    result = triage(
        "the published skill contained a hidden payload that steals credentials"
    )
    assert result["ast_id"] == "AST01"
    assert result["category"] == "Malicious Skills"


def test_ast02_typosquatting_and_missing_signature():
    result = triage(
        "a typosquatted skill with no code signature was accepted by a "
        "compromised publisher account on the registry"
    )
    assert result["ast_id"] == "AST02"
    assert result["category"] == "Supply Chain / Registry Trust"


def test_ast04_insecure_metadata_spoofed_risk_tier():
    result = triage(
        "the SKILL.md frontmatter has a deceptive description and spoofed "
        "risk_tier value"
    )
    assert result["ast_id"] == "AST04"
    assert result["category"] == "Insecure Metadata"


def test_ast08_scanner_missed_obfuscated_instruction():
    result = triage(
        "the scanner failed to catch an obfuscated instruction that bypassed "
        "natural-language detection"
    )
    assert result["ast_id"] == "AST08"
    assert result["category"] == "Poor Scanning"


def test_overlap_records_primary_and_contributing_not_split():
    # Decision-tree branch 5: a finding matching more than one branch records
    # the primary root cause and lists the rest as contributing, never a
    # second primary.
    result = triage(
        "a malicious skill with a hidden payload also evaded the scanner's "
        "natural-language detection"
    )
    assert result["ast_id"] == "AST01"
    assert "AST08" in result["contributing"]
    assert result["ast_id"] not in result["contributing"]


def test_extended_categories_route_beyond_the_four_literal_branches():
    # AST03/05/06/07/09/10 are not in the whitepaper's four literal branches
    # but the advisory skill extends the same tree to cover all ten.
    assert (
        triage(
            "skills execute with full host file system and shell access, no sandbox"
        )["ast_id"]
        == "AST06"
    )
    assert (
        triage(
            "an installed skill was never patched and drifted from the pinned version"
        )["ast_id"]
        == "AST07"
    )
    assert (
        triage("no inventory or approval workflow exists for installed skills")[
            "ast_id"
        ]
        == "AST09"
    )
    assert (
        triage(
            "the skill's permission manifest was stripped when ported to another platform"
        )["ast_id"]
        == "AST10"
    )


def test_unmatched_finding_falls_back_without_guessing():
    result = triage("the office printer is out of toner")
    assert result["ast_id"] is None
    assert result["contributing"] == []
    assert result["guidance"]


def test_advisory_skill_never_contributes_to_f1():
    # S-002: "it does not contribute to any Gate B F1 denominator"
    assert F1_ELIGIBLE is False
