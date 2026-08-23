"""Tests for the AST03 detector.

Every check gets a true-positive AND a true-negative case, and the last section
runs the real labeled corpus in `fixtures/AST03/` through the real detector and
asserts each check SEPARATES its vulnerable case from its clean one. That last
part is the whole point: an independent review found AST01's substantive check
"fires identically on all six of its own labeled fixtures — vulnerable and clean
alike, F1 0.667, the coin flip". A per-function unit test cannot catch that
shape; only running the corpus can.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

_HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("ast03_detector", _HERE / "detector.py")
detector = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules[_spec.name] = detector
_spec.loader.exec_module(detector)

from detectors.fixture_loader import run_corpus  # noqa: E402
from validators.usf import IDENTITY_FILES as USF_IDENTITY_FILES  # noqa: E402


def usf(**overrides) -> dict:
    """A USF-shaped package with a conformant, closed permission posture."""
    permissions = {
        "files": {"read": ["./SKILL.md"], "write": [], "deny_write": ["SOUL.md", "MEMORY.md", "AGENTS.md"]},
        "network": {"allow": [], "deny": "*"},
        "shell": False,
    }
    for key, value in overrides.items():
        if key in ("read", "write", "deny_write"):
            permissions["files"][key] = value
        elif key == "allow":
            permissions["network"]["allow"] = value
        elif key == "shell":
            permissions["shell"] = value
        else:  # pragma: no cover - guards a typo in a test, not a code path
            raise KeyError(key)
    return {"manifest": {"permissions": permissions}, "files": {}}


def detector_shaped(**overrides) -> dict:
    """The flattened shape `scripts/dogfood.py` and `cli/lib/bridge.py` produce."""
    permissions = {
        "read": ["./SKILL.md"],
        "write": [],
        "deny_write": ["SOUL.md", "MEMORY.md", "AGENTS.md"],
        "shell": {"allowed": False, "commands": []},
        "network": {"policy": "deny-all", "allow": []},
    }
    permissions.update(overrides)
    return {"manifest": {"permissions": permissions}, "files": {}}


# --- registry / declaration shape ------------------------------------------


def test_s001_detector_registry_matches_declared_detectable_tier():
    declared_detectable = {s for s, tier in detector.SCENARIO_TIERS.items() if tier == "static-detectable"}
    assert set(detector.DETECTORS.keys()) == declared_detectable
    assert "AST03-task-scope-mismatch" not in detector.DETECTORS


def test_identity_file_list_does_not_drift_from_the_usf_validator():
    """Two lists of the same three names is one list too many if they can diverge."""
    assert detector.IDENTITY_FILES == USF_IDENTITY_FILES


def test_only_the_identity_check_claims_coverage_of_a_named_scenario():
    covers = {check: entry["covers"] for check, entry in detector.CHECK_COVERAGE.items()}
    assert covers["AST03-identity-file-write-grant"] == "full"
    assert detector.CHECK_COVERAGE["AST03-identity-file-write-grant"]["registry_ids"] == ["AST03-S03"]
    assert covers["AST03-unbounded-write-scope"] == "category-precondition"
    assert covers["AST03-shell-network-privilege-combo"] == "artifact-signal-only"
    assert covers["AST03-wildcard-network-egress"] == "artifact-signal-only"


# --- AST03-identity-file-write-grant (AST03-S03, covers: full) --------------


@pytest.mark.parametrize("identity_file", ["SOUL.md", "MEMORY.md", "AGENTS.md"])
def test_identity_write_grant_fires_on_each_identity_file(identity_file):
    pkg = usf(write=[identity_file], deny_write=["config/credentials.env"])
    finding = detector.detect_identity_file_write_grant(pkg)
    assert finding.detected is True
    assert identity_file in finding.evidence


def test_identity_write_grant_fires_when_deny_write_is_non_empty_but_omits_them():
    """The exact shape a length-only deny_write check waves through."""
    pkg = usf(write=["SOUL.md"], deny_write=["/etc/hosts", "config/credentials.env"])
    assert detector.detect_identity_file_write_grant(pkg).detected is True


def test_identity_write_grant_fires_on_a_root_recursive_glob():
    pkg = usf(write=["./**"], deny_write=["config/credentials.env"])
    assert detector.detect_identity_file_write_grant(pkg).detected is True


def test_identity_write_grant_clear_when_deny_write_shadows_the_grant():
    """USF precedence: deny_write beats write, so a shadowed grant is no grant."""
    pkg = usf(write=["SOUL.md", "notes/session.md"], deny_write=["SOUL.md", "MEMORY.md", "AGENTS.md"])
    assert detector.detect_identity_file_write_grant(pkg).detected is False


def test_identity_write_grant_clear_on_a_broad_but_scoped_write():
    """`/secrets/**` is a real over-privilege finding and is NOT this scenario."""
    pkg = usf(write=["/secrets/**"], deny_write=["config/credentials.env"])
    assert detector.detect_identity_file_write_grant(pkg).detected is False


def test_identity_write_grant_clear_when_a_similar_name_is_granted():
    pkg = usf(write=["docs/SOULFUL.md", "MEMORY.mdx"], deny_write=["config/credentials.env"])
    assert detector.detect_identity_file_write_grant(pkg).detected is False


def test_identity_write_grant_reads_the_flattened_detector_shape_too():
    """A check that only understands one vocabulary is dead against the other."""
    assert detector.detect_identity_file_write_grant(detector_shaped(write=["MEMORY.md"], deny_write=[])).detected
    assert not detector.detect_identity_file_write_grant(detector_shaped(write=["notes.md"])).detected


def test_identity_write_grant_is_clear_on_this_repositorys_own_ast03_manifest():
    """The regression the coverage matrix recorded: a false positive on every
    conformant USF manifest, because the check read `permissions.deny_write`
    while the schema spells it `permissions.files.deny_write`."""
    import yaml

    text = (REPO_ROOT / "skills" / "AST03" / "skill.usf.yaml").read_text(encoding="utf-8")
    manifest = yaml.safe_load(text.split("---\n", 1)[1])
    findings = detector.run_all({"manifest": manifest, "files": {}})
    assert not any(f.detected for f in findings), [f"{f.scenario}: {f.evidence}" for f in findings if f.detected]


# --- AST03-unbounded-write-scope (category precondition) --------------------


def test_unbounded_write_scope_fires_when_no_permissions_block_exists():
    finding = detector.detect_unbounded_write_scope({"manifest": {}, "files": {}})
    assert finding.detected is True
    assert "no permissions block" in finding.evidence


def test_unbounded_write_scope_fires_when_the_deny_write_key_is_absent():
    pkg = {"manifest": {"permissions": {"files": {"read": ["."], "write": []}, "shell": False}}, "files": {}}
    assert detector.detect_unbounded_write_scope(pkg).detected is True


def test_unbounded_write_scope_clear_on_an_explicitly_empty_floor():
    """`deny_write: []` is a stated floor. USF requires the key for exactly this
    reason, and treating an explicit empty list as an absent one is what made the
    old check fire on every conformant manifest."""
    assert detector.detect_unbounded_write_scope(usf(deny_write=[])).detected is False


def test_unbounded_write_scope_clear_when_paths_are_denied():
    assert detector.detect_unbounded_write_scope(usf()).detected is False


# --- AST03-shell-network-privilege-combo (artifact-signal-only) -------------


def test_shell_network_combo_fires_on_shell_plus_unbounded_egress():
    assert detector.detect_shell_network_privilege_combo(usf(shell=True, allow=["*"])).detected is True


def test_shell_network_combo_fires_on_the_legacy_allow_all_policy():
    pkg = detector_shaped(shell={"allowed": True}, network={"policy": "allow-all", "allow": []})
    assert detector.detect_shell_network_privilege_combo(pkg).detected is True


def test_shell_network_combo_clear_without_the_shell_conjunct():
    assert detector.detect_shell_network_privilege_combo(usf(shell=False, allow=["*"])).detected is False


def test_shell_network_combo_clear_without_the_egress_conjunct():
    assert detector.detect_shell_network_privilege_combo(usf(shell=True, allow=["api.example.com"])).detected is False


def test_shell_network_combo_clear_on_a_closed_posture():
    assert detector.detect_shell_network_privilege_combo(usf()).detected is False


# --- AST03-wildcard-network-egress (artifact-signal-only) -------------------


def test_wildcard_egress_fires_on_a_wildcard_host_entry():
    assert detector.detect_wildcard_network_egress(usf(allow=["*"])).detected is True


def test_wildcard_egress_fires_on_a_bare_boolean_network_grant():
    pkg = {"manifest": {"permissions": {"network": True}}, "files": {}}
    assert detector.detect_wildcard_network_egress(pkg).detected is True


def test_wildcard_egress_clear_on_an_enumerated_allowlist():
    assert detector.detect_wildcard_network_egress(usf(allow=["api.example.com", "cdn.example.com"])).detected is False


def test_wildcard_egress_clear_on_an_empty_allowlist():
    """USF default-deny: an empty allowlist is no egress, never unrestricted egress."""
    assert detector.detect_wildcard_network_egress(usf(allow=[])).detected is False


# --- the labeled corpus, run for real ---------------------------------------


@pytest.fixture(scope="module")
def corpus():
    return run_corpus("AST03")


def test_every_labeled_check_is_wired_to_an_implemented_detector(corpus):
    assert {c.corpus_check for c in corpus.checks} == {"AST03-S1", "AST03-S2", "AST03-S3"}
    for check in corpus.checks:
        assert check.detector_check in detector.DETECTORS


def test_each_check_separates_its_vulnerable_case_from_its_clean_case(corpus):
    """The anti-pattern this exists to catch: one verdict for the whole pair."""
    for check in corpus.checks:
        verdicts = {predicted for _case, predicted, _label in check.case_verdicts}
        assert verdicts == {True, False}, (
            f"{check.detector_check} returned {verdicts} across its own labeled pair "
            f"{[c for c, _p, _l in check.case_verdicts]} — it does not discriminate"
        )
        assert check.false_positives == 0 and check.false_negatives == 0, check


def test_the_scenario_level_and_proxy_figures_are_reported_separately(corpus):
    """AST03 mixes one covers: full pair with two proxies; blending them would
    report 1-of-5 named-scenario coverage as category coverage."""
    assert corpus.f1_scope == "mixed-proxy"
    assert corpus.cases("full") == 2
    assert corpus.cases("artifact-signal-only") == 4
    assert corpus.f1("full") == 1.0
    assert corpus.f1("artifact-signal-only") == 1.0


def test_no_check_fires_on_any_clean_case_in_the_whole_corpus(corpus):
    """Stronger than the per-pair check: run EVERY check over EVERY clean fixture.

    A check is allowed to cross-fire on another pair's *vulnerable* case when the
    predicate is genuinely true there (AST03-wildcard-network-egress does, on the
    combo pair's vulnerable case, which really does declare blanket egress). No
    check may fire on anything labeled clean.
    """
    from detectors.fixture_loader import load_category_cases

    for case in load_category_cases("AST03"):
        if case.is_vulnerable:
            continue
        fired = [f.scenario for f in detector.run_all(case.pkg) if f.detected]
        assert fired == [], f"{case.case_id} is labeled clean but fired {fired}"
