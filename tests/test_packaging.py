"""Packaging, CI and licensing — the files a consumer meets before any code runs.

These are the artifacts nothing else in the test suite covers: the plugin
marketplace manifest, the CI workflow, and the licensing/attribution set. They
are exactly the artifacts that rot silently, because a stale one still parses.

What each group asserts, and why it is worth a test:

  * **marketplace.json** — the manifest is the install surface. A skill on disk
    but absent from the manifest is uninstallable; a manifest entry with no
    skill behind it is a broken install. Both directions are checked, keyed on
    the SKILL.md frontmatter `name`, because that string — not the directory
    name — is what a runtime matches invocations against.

  * **eval.yml** — the workflow's value is its *split*: the deterministic layer
    runs in CI, the LLM judge does not. A test that only checked "the YAML
    parses" would pass on a workflow that quietly grew a credentials step, so
    the absence of `secrets.` is asserted directly, alongside the presence of
    each command the split promises.

  * **LICENSE / CONTRIBUTING.md / CODEOWNERS / NOTICE / THIRD_PARTY_LICENSES.md**
    — non-empty is the floor, not the bar. The attribution claims are load-
    bearing for a repo named after a standards body it is not part of, so the
    non-endorsement disclaimer and the three provenance records (whitepaper,
    vendored pipeline, vendored skill-judge rubric) are asserted by content.
    Attribution rots the same way a number does, and worse: a notice that
    misdescribes what it redistributes is a licence problem, not a typo. So
    the notices are checked against the tree they describe (`vendor/skill-
    judge/` existing forbids NOTICE from calling the rubric un-vendored), and
    the README is checked for the credit itself — the work, its author, its
    licence, its URL — because burying a rubric's credit in NOTICE while
    publishing its scores on the front page is credit by silence.
"""

from __future__ import annotations

import json
import pathlib
import re
import shutil
import subprocess

import pytest
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / "skills"
MARKETPLACE_PATH = REPO_ROOT / ".claude-plugin" / "marketplace.json"
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "eval.yml"
LICENSE_PATH = REPO_ROOT / "LICENSE"
CONTRIBUTING_PATH = REPO_ROOT / "CONTRIBUTING.md"
CODEOWNERS_PATH = REPO_ROOT / "CODEOWNERS"
NOTICE_PATH = REPO_ROOT / "NOTICE"
THIRD_PARTY_PATH = REPO_ROOT / "THIRD_PARTY_LICENSES.md"
GITIGNORE_PATH = REPO_ROOT / ".gitignore"
README_PATH = REPO_ROOT / "README.md"
VENDORED_RUBRIC = REPO_ROOT / "vendor" / "skill-judge" / "SKILL.md"

#: The project this repository implements and is named after. Linked, not just named.
OWASP_PROJECT_URL = "https://owasp.org/www-project-agentic-skills-top-10/"

FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)


# --------------------------------------------------------------------- fixtures


def skill_dirs() -> list[pathlib.Path]:
    return sorted(p for p in SKILLS_DIR.iterdir() if p.is_dir())


def frontmatter_name(skill_dir: pathlib.Path) -> str:
    text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    match = FRONTMATTER_RE.match(text)
    assert match, f"{skill_dir.name}/SKILL.md has no YAML frontmatter block"
    meta = yaml.safe_load(match.group(1))
    name = meta.get("name")
    assert name, f"{skill_dir.name}/SKILL.md frontmatter declares no `name`"
    return str(name)


@pytest.fixture(scope="module")
def marketplace() -> dict:
    return json.loads(MARKETPLACE_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def workflow() -> dict:
    return yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def workflow_text() -> str:
    return WORKFLOW_PATH.read_text(encoding="utf-8")


# ------------------------------------------------------------- marketplace.json


def test_marketplace_manifest_parses_as_json(marketplace):
    assert isinstance(marketplace, dict)


def test_marketplace_declares_the_documented_schema(marketplace):
    """The manifest is a Claude Code plugin marketplace, so it answers to that schema.

    It used to be a bespoke `skills[]` index sitting at the path Claude Code
    reserves for a marketplace manifest, which meant `/plugin marketplace add`
    on this repository failed. `name`, `owner.name` and `plugins[]` are the
    documented required set.
    """
    for key in ("name", "owner", "plugins"):
        assert key in marketplace, f"marketplace.json is missing required top-level {key!r}"
    assert marketplace["owner"]["name"] == "Jacky Chan"
    assert isinstance(marketplace["plugins"], list) and marketplace["plugins"], "plugins[] must be a non-empty list"


def test_marketplace_ships_exactly_one_plugin(marketplace):
    """One plugin carries the whole repository. Splitting it is a real choice
    with an install-story cost, so it fails here until it is made deliberately."""
    assert len(marketplace["plugins"]) == 1, "the repository ships as a single plugin"


def test_the_plugin_declares_both_component_paths(marketplace):
    """The skills were always installable; the fourteen commands were not.

    A marketplace entry that declares `skills` and omits `commands` installs
    two thirds of this repository and silently drops every slash command, which
    is the exact gap this manifest was rewritten to close.
    """
    plugin = marketplace["plugins"][0]
    for key in ("name", "source", "skills", "commands", "license"):
        assert key in plugin, f"the plugin entry is missing {key!r}"
    assert plugin["license"] == "Apache-2.0"


def test_the_plugin_component_paths_resolve_on_disk(marketplace):
    """A declared path with nothing behind it is a broken install."""
    plugin = marketplace["plugins"][0]
    for key in ("skills", "commands"):
        target = (REPO_ROOT / plugin[key]).resolve()
        assert target.is_dir(), f"the plugin declares {key} -> {plugin[key]!r}, which is not a directory"


def test_the_declared_skills_path_holds_every_skill_directory(marketplace):
    """Both directions, as before. A skill outside the declared path cannot be
    installed; a declared path holding a directory with no SKILL.md is a broken
    install. The manifest no longer restates the roster, so this is the drift
    guard that replaces the old name-by-name index comparison."""
    plugin = marketplace["plugins"][0]
    declared = (REPO_ROOT / plugin["skills"]).resolve()
    assert declared == SKILLS_DIR.resolve(), f"the plugin installs from {declared}, but the skills live in {SKILLS_DIR}"

    on_disk = {frontmatter_name(d) for d in skill_dirs()}
    assert len(on_disk) == 11, "the roster is ten AST categories plus advisory"
    for directory in skill_dirs():
        assert (directory / "SKILL.md").is_file(), (
            f"{directory.name} is inside the declared skills path with no SKILL.md"
        )


def test_the_declared_commands_path_holds_every_slash_command(marketplace):
    """The count is derived, not asserted: every `.md` under the declared path
    is a command a user gets, and every command file must live under it."""
    plugin = marketplace["plugins"][0]
    declared = (REPO_ROOT / plugin["commands"]).resolve()
    on_disk = sorted(p.name for p in declared.glob("*.md"))
    assert on_disk, "the declared commands path holds no command files"

    everywhere = sorted(p.name for p in (REPO_ROOT / "commands").rglob("*.md"))
    assert on_disk == everywhere, (
        f"commands exist outside the declared path and will not install: {sorted(set(everywhere) - set(on_disk))}"
    )


def test_plugin_json_agrees_with_the_marketplace_entry(marketplace):
    """Two manifests describing one plugin is two places to drift."""
    plugin = marketplace["plugins"][0]
    manifest = json.loads((REPO_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    for key in ("name", "displayName", "description", "version", "license", "homepage", "repository"):
        assert manifest.get(key) == plugin.get(key), (
            f"plugin.json and the marketplace entry disagree on {key!r}: {manifest.get(key)!r} vs {plugin.get(key)!r}"
        )


def test_marketplace_description_carries_the_non_endorsement_disclaimer(marketplace):
    """The manifest is often the only text a plugin browser shows. A repo named
    after a standards body it is not part of has to say so where it is read —
    and now in both places a browser reads from."""
    for label, description in (
        ("the marketplace", marketplace["description"]),
        ("the plugin entry", marketplace["plugins"][0]["description"]),
    ):
        assert "NOT an OWASP project" in description, f"{label} description drops the non-endorsement disclaimer"
        assert "endorsement" in description, f"{label} description does not use the word 'endorsement'"


def test_the_rendered_names_themselves_mark_the_independence(marketplace):
    """The NAME, not only the description, has to carry the disclaimer.

    A plugin picker renders the name and routinely truncates or drops the
    description, so at the one moment that matters — the click that installs —
    "OWASP Agentic Skills Top 10 ..." unqualified reads as an OWASP-published
    artifact. That is the AST04 brand-impersonation shape this repository
    exists to flag, committed by the repository itself. `displayName` is what
    the picker actually renders, so it is checked alongside the identifier.
    """
    name = marketplace["name"]
    assert "owasp" in name.lower(), "the name may name the standard it implements"
    assert name.lower().startswith("unofficial"), (
        f"marketplace.json's name must lead with its independence, got {name!r}"
    )

    display = marketplace["plugins"][0]["displayName"]
    assert "OWASP" in display, "the rendered plugin name may name the standard it implements"
    assert display.lower().startswith("unofficial"), (
        f"the plugin's displayName is what a picker renders and must lead with its independence, got {display!r}"
    )


def test_marketplace_installs_skills_and_commands_together(marketplace):
    """The inverse of the guard this replaces.

    The manifest used to be a flat skill index, and a test asserted it never
    grew a `plugins`/`commands` declaration so that README.md and
    docs/architecture.md stayed true. Those pages now describe a real plugin,
    so the guard points the other way: dropping either component declaration
    silently narrows what `/plugin install` delivers.
    """
    plugin = marketplace["plugins"][0]
    assert plugin.get("skills"), "the plugin must declare its skills path"
    assert plugin.get("commands"), "the plugin must declare its commands path"


# --------------------------------------------------------------- eval.yml (CI)


def test_workflow_yaml_parses(workflow):
    assert isinstance(workflow, dict)
    assert workflow["name"] == "Eval"
    assert "jobs" in workflow


def test_workflow_declares_the_assertion_and_dogfood_jobs(workflow):
    assert set(workflow["jobs"]) == {"assertion", "dogfood"}


def test_workflow_triggers_on_pull_request(workflow):
    # PyYAML resolves a bare `on:` key to the boolean True (YAML 1.1), so accept
    # either spelling rather than depending on the loader's tag resolution.
    triggers = workflow.get("on", workflow.get(True))
    assert triggers is not None, "workflow declares no triggers"
    assert "pull_request" in triggers
    assert "workflow_dispatch" in triggers


def test_ci_runs_every_command_the_assertion_layer_promises(workflow_text):
    for command in (
        "python -m pytest -q",
        "python validators/usf.py skills/*/skill.usf.yaml",
        "python validators/tier_lock.py fixtures/manifest.yaml",
        "python scripts/dogfood.py",
    ):
        assert command in workflow_text, f"CI does not run: {command}"
    assert "ruff-action" in workflow_text, "CI does not run ruff"


def test_ci_enforces_both_halves_of_the_lint_contract(workflow_text):
    """`ruff check` alone leaves formatting unenforced, and a repo where only
    half the contract is checked drifts on the other half. Both run, and both
    run unflagged so `ruff.toml` stays the single definition of the rules."""
    assert "args: check ." in workflow_text, "CI does not run `ruff check .`"
    assert "args: format --check" in workflow_text, "CI does not run `ruff format --check`"
    # Comment lines excluded for the same reason as the judge-invocation test
    # below: the workflow *explains* why it passes no rule flags, and a check
    # that cannot tell an explanation from an argument would delete the
    # explanation from the file it explains.
    args = [line for line in workflow_text.splitlines() if line.lstrip().startswith("args:")]
    for flag in ("--select", "--line-length"):
        assert not any(flag in line for line in args), (
            f"CI passes {flag} to ruff; the contract belongs in ruff.toml, not in a workflow arg"
        )


def test_ruff_config_pins_the_contract_the_repo_documents():
    config = REPO_ROOT / "ruff.toml"
    assert config.is_file(), "ruff.toml is missing; CI runs ruff unflagged and would fall back to defaults"
    text = config.read_text(encoding="utf-8")
    assert "line-length = 120" in text
    assert '"E"' in text and '"F"' in text and '"I"' in text


def test_ci_references_no_secret_and_no_cloud_credential(workflow_text):
    """The whole point of the split: the judge layer is maintainer-only and CI
    holds nothing. A `secrets.` reference appearing here would mean the
    assertion-only guarantee had quietly stopped being true."""
    assert "secrets." not in workflow_text
    for forbidden in (
        "AWS_ACCESS_KEY",
        "AWS_SECRET",
        "ANTHROPIC_API_KEY",
        "ZAI_API_KEY",
        "DASHSCOPE_API_KEY",
        "aws-actions/configure-aws-credentials",
    ):
        assert forbidden not in workflow_text, f"CI references {forbidden}"


def test_ci_does_not_invoke_the_llm_judge(workflow_text):
    """`judge_harness.py` and `ship_floor.py` need models and credentials. They
    run locally, and their scorecards are committed — see CONTRIBUTING.md.

    Comment lines are excluded on purpose: the workflow header *documents* the
    maintainer-only split by naming both scripts, and a test that could not
    tell an explanation from an invocation would push that explanation out of
    the file it explains.
    """
    executable = "\n".join(line for line in workflow_text.splitlines() if not line.lstrip().startswith("#"))
    assert "judge_harness" not in executable
    assert "ship_floor" not in executable


def test_ci_workflow_is_read_only(workflow):
    assert workflow["permissions"] == {"contents": "read"}


def test_usf_validation_step_is_not_strict(workflow_text):
    """--strict turns every warning into a failure, and the step's job is to fail
    on a manifest that is WRONG.

    The shipped roster is warning-free today because it is signed and anchored,
    so this is not about the current state: a contributor's new skill warns about
    its missing anchor and its unsigned signature, and those are the honest
    declared state of an unsigned package. A CI step that forced them green would
    be pressure to manufacture an identity anchor that anchors to nothing."""
    assert "validators/usf.py --strict" not in workflow_text


def test_ci_verifies_usf_signatures_without_an_identity(workflow_text):
    """Verification is a public-key operation, so it is the half of signing that
    belongs in CI. Without --identity it checks each signature against the key the
    manifest itself carries: the eleven shipped manifests are signed, so one whose
    bytes moved fails here, and an explicitly `unsigned` one still passes, which is
    what keeps the step from becoming pressure to manufacture an anchor. The
    roster's current signed state is pinned by
    tests/test_usf.py::test_shipped_manifest_is_signed_and_anchored and checked
    against the published key, offline, by tests/test_signing_anchor.py. See
    docs/signing.md."""
    executable = [line for line in workflow_text.splitlines() if not line.lstrip().startswith("#")]
    verify = [line for line in executable if "sign_usf.py verify" in line]
    assert verify, "CI does not run `sign_usf.py verify`"
    assert not any("--identity" in line for line in verify), (
        "the CI verify step resolves a did:web anchor over the network; a runner that "
        "cannot reach the domain would fail a PR for a reason that is not about the PR"
    )


def test_ci_never_asks_for_the_signing_key(workflow_text):
    """The custody choice, as a test. The private key is held locally and used at
    release only; `keygen` and `sign` refuse to run when CI is set in the environment.
    A workflow line that reached for the key would mean that choice had quietly been
    reversed, and any instruction to add the key here is an attack on this project."""
    executable = "\n".join(line for line in workflow_text.splitlines() if not line.lstrip().startswith("#"))
    for forbidden in ("sign_usf.py sign", "sign_usf.py keygen", "AST10_SIGNING_PASSPHRASE", "--key"):
        assert forbidden not in executable, f"CI reaches for signing key material: {forbidden}"


# ------------------------------------------------------- licensing + governance


@pytest.mark.parametrize(
    "path",
    [LICENSE_PATH, CONTRIBUTING_PATH, CODEOWNERS_PATH, NOTICE_PATH, THIRD_PARTY_PATH],
    ids=lambda p: p.name,
)
def test_governance_file_exists_and_is_non_empty(path):
    assert path.is_file(), f"{path.name} is missing"
    assert path.read_text(encoding="utf-8").strip(), f"{path.name} is empty"


def test_license_is_apache_2_0_naming_jacky_chan():
    text = LICENSE_PATH.read_text(encoding="utf-8")
    assert "Apache License" in text
    assert "Version 2.0, January 2004" in text
    assert "Copyright 2026 Jacky Chan" in text
    assert "TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION" in text


def test_codeowners_names_the_maintainer():
    text = CODEOWNERS_PATH.read_text(encoding="utf-8")
    assert "@jhkchan" in text
    catch_all = [line for line in text.splitlines() if line.strip().startswith("*") and "@jhkchan" in line]
    assert catch_all, "CODEOWNERS has no catch-all owner for unmatched paths"


def test_contributing_covers_the_three_rules_it_exists_to_state():
    text = CONTRIBUTING_PATH.read_text(encoding="utf-8")
    # 1. how to add a skill
    assert "Adding a skill" in text
    assert "skill.usf.yaml" in text
    assert "marketplace.json" in text
    # 2. the tiering rules a new scenario must declare
    for tier in ("static-detectable", "agent-judgable", "out-of-artifact"):
        assert tier in text, f"CONTRIBUTING.md does not define the {tier} tier"
    assert "scenarios/registry.yaml" in text
    assert "artifact_signal" in text
    # 3. fixtures before F1
    assert "max(6, 2 × count(detectable_scenarios))" in text
    assert "declared-and-uncovered" in text


def test_contributing_states_the_non_endorsement_position():
    text = CONTRIBUTING_PATH.read_text(encoding="utf-8")
    assert "not an owasp project" in text.lower()
    assert "Ken Huang" in text


def test_contributing_keeps_the_judge_layer_out_of_ci():
    text = CONTRIBUTING_PATH.read_text(encoding="utf-8")
    assert "maintainer-only" in text.lower()
    assert "ship_floor.py" in text


# ------------------------------------------------------------------ attribution


def test_notice_records_the_whitepaper_as_source_material():
    text = NOTICE_PATH.read_text(encoding="utf-8")
    assert "OWASP Agentic Skills Top 10" in text
    assert "SOURCE MATERIAL" in text
    assert "Ken Huang" in text
    assert "NOT AN OWASP PROJECT" in text


def test_notice_attributes_the_vendored_scoring_pipeline_with_provenance():
    text = NOTICE_PATH.read_text(encoding="utf-8")
    for path in ("ship_floor.py", "content_hash.py", "eval_counts.py"):
        assert path in text, f"NOTICE does not attribute {path}"
    assert "Copyright 2026 Votee AI" in text
    assert "Apache License, Version 2.0" in text
    # The pinned commit is what makes the vendored copy auditable for drift.
    assert "34ac48d680323ce4b5302c8a756db6327984b59e" in text


def test_notice_attributes_the_skill_judge_rubric_with_provenance():
    text = NOTICE_PATH.read_text(encoding="utf-8")
    assert "softaworks/agent-toolkit" in text
    assert "Leonardo Flores" in text
    assert "MIT" in text
    assert "3027f20f3181758385a1bb8c022d4041dfb4de84" in text


def test_notice_no_longer_claims_the_license_file_is_pending():
    """The NOTICE previously read "the root LICENSE file ... is not asserted to
    exist". It exists now; a stale disclaimer understates the license posture."""
    text = NOTICE_PATH.read_text(encoding="utf-8")
    assert "not asserted to" not in text
    assert "Licensed under the Apache License, Version 2.0" in text


def test_third_party_licenses_covers_every_attributed_component():
    text = THIRD_PARTY_PATH.read_text(encoding="utf-8")
    for needle in (
        "OWASP Agentic Skills Top 10",  # source material
        "ship_floor.py",  # vendored pipeline
        "softaworks/agent-toolkit",  # pinned rubric
        "Leonardo Flores",
        "PyYAML",  # installed dependencies
        "jsonschema",
        "cryptography",
    ):
        assert needle in text, f"THIRD_PARTY_LICENSES.md does not record {needle}"


def test_notice_describes_the_rubric_as_vendored_once_the_tree_is_there():
    """The failure this guards actually happened.

    NOTICE section 2 was written when the rubric was pinned by SHA and nothing
    more, and said so: "not vendored as a tree", "no copy of its text ships
    here". Then `vendor/skill-judge/SKILL.md` landed — the rubric redistributed
    verbatim — and the notice was not touched. A redistribution notice that
    misdescribes what was redistributed is the wrong kind of wrong for an MIT
    obligation, so the two are tied together here: while the tree exists,
    NOTICE must not deny it.
    """
    if not VENDORED_RUBRIC.is_file():
        pytest.skip("no vendored rubric tree; NOTICE's pin-only description would be correct")
    text = NOTICE_PATH.read_text(encoding="utf-8")
    flat = " ".join(text.split()).lower()
    for denial in (
        "not vendored as a tree",
        "is not vendored",
        "not yet vendored",
        "no copy of its text ships",
        "no copy of the rubric text ships",
        "the rubric tree itself is not vendored",
    ):
        assert denial not in flat, (
            f"vendor/skill-judge/SKILL.md exists, but NOTICE still says {denial!r}. "
            "The rubric is redistributed here; NOTICE must describe the copy, not deny it."
        )
    assert "vendor/skill-judge/SKILL.md" in text, "NOTICE must name the vendored rubric file"
    assert "vendor/skill-judge/LICENSE" in text, (
        "MIT requires the license text to travel with the copy; NOTICE must say where it is"
    )
    assert "vendor/skill-judge/PROVENANCE.md" in text


def test_notice_keeps_the_two_rubric_pins_distinct():
    """`RUBRIC_SHA` and `RUBRIC_CONTENT_SHA256` are different instruments.

    One names an upstream commit and cannot be recomputed here; the other
    hashes the vendored bytes and is recomputed by `tests/test_rubric_pin.py`
    on every run. Collapsing them into "the pin" is how a notice starts
    claiming a verification the repo does not perform.
    """
    from scripts.ship_floor import RUBRIC_CONTENT_SHA256, RUBRIC_SHA

    text = NOTICE_PATH.read_text(encoding="utf-8")
    assert RUBRIC_SHA in text
    assert RUBRIC_CONTENT_SHA256 in text, "NOTICE must record the content hash of the vendored bytes"
    flat = " ".join(text.split()).lower()
    assert "upstream commit" in flat, "NOTICE must say RUBRIC_SHA is an upstream commit id"
    assert "cannot be" in flat and "recomputed" in flat, (
        "NOTICE must say the upstream commit id is not recomputable from inside this repo"
    )
    assert "tests/test_rubric_pin.py" in text, (
        "NOTICE must name what recomputes RUBRIC_CONTENT_SHA256, or the pin is decorative"
    )


def test_third_party_licenses_describes_the_vendored_rubric_tree():
    text = THIRD_PARTY_PATH.read_text(encoding="utf-8")
    flat = " ".join(text.split()).lower()
    if VENDORED_RUBRIC.is_file():
        for denial in (
            "no copy of the rubric text ships in this repository",
            "not vendored as a tree",
            "pinned but not vendored",
            "is tracked as follow-up work",
        ):
            assert denial not in flat, f"THIRD_PARTY_LICENSES.md still says {denial!r}"
        for needle in (
            "vendor/skill-judge/SKILL.md",
            "vendor/skill-judge/LICENSE",
            "vendor/skill-judge/PROVENANCE.md",
        ):
            assert needle in text, f"THIRD_PARTY_LICENSES.md does not record {needle}"


def test_readme_credits_skill_judge_by_work_author_and_licence():
    """The rubric is the substance of every quality claim the README makes.

    The eight dimensions, the 120 points and the per-dimension floors the ship
    gate enforces are skill-judge's definitions, not this project's. A README
    that publishes those numbers while naming the rubric only inside a
    filename (`docs/skill-judge-dashboard.md`) is taking credit by silence, so
    the credit is asserted by its parts: the work, the upstream, the author,
    the licence, the vendored path, and the content pin that makes a score
    attributable to specific rubric bytes.
    """
    text = README_PATH.read_text(encoding="utf-8")
    flat = " ".join(text.split())
    for needle, why in (
        ("skill-judge", "the work's name"),
        ("softaworks/agent-toolkit", "the upstream project"),
        ("Leonardo Flores", "the copyright holder"),
        ("MIT", "the licence the rubric ships under"),
        ("vendor/skill-judge/SKILL.md", "where the vendored rubric lives"),
        ("RUBRIC_CONTENT_SHA256", "the content pin a score is attributable through"),
    ):
        assert needle in flat, f"README.md must name {needle!r} — {why} — when crediting the rubric"
    assert "https://github.com/softaworks/agent-toolkit" in flat, "the credit must be clickable, not just a slug"


def test_readme_does_not_overclaim_the_skill_judge_relationship():
    """Vendoring and applying someone's rubric is not authoring it, and is not
    their endorsement — the same distinction the OWASP disclaimer draws."""
    flat = " ".join(README_PATH.read_text(encoding="utf-8").split()).lower()
    for overclaim in (
        "our rubric",
        "this repository's rubric",
        "endorsed by softaworks",
        "in partnership with softaworks",
    ):
        assert overclaim not in flat, f"README.md must not claim: {overclaim!r}"
    assert "did not author it" in flat, "the README must say outright that this repo did not author the rubric"


def test_readme_links_the_owasp_project_page():
    """The repository is named after a project it never linked.

    First mention in the opening paragraph and again in the non-endorsement
    section, which is exactly where a reader goes looking for the real thing.
    """
    lines = README_PATH.read_text(encoding="utf-8").splitlines()
    hits = [i for i, line in enumerate(lines) if OWASP_PROJECT_URL in line]
    assert hits, f"README.md never links {OWASP_PROJECT_URL}"
    assert hits[0] < 10, f"the first mention must carry the link; found the earliest at line {hits[0] + 1}"
    disclaimer = next(i for i, line in enumerate(lines) if "Not an OWASP project" in line)
    assert any(i > disclaimer for i in hits), (
        "the 'Not an OWASP project' section must link the real project a reader is being sent to"
    )


def test_rubric_sha_in_the_docs_matches_the_constant_that_enforces_it():
    """An attribution naming a different version than the code pins is worse
    than none: it looks like provenance and documents the wrong artifact."""
    from scripts.ship_floor import RUBRIC_SHA

    assert RUBRIC_SHA in NOTICE_PATH.read_text(encoding="utf-8")
    assert RUBRIC_SHA in THIRD_PARTY_PATH.read_text(encoding="utf-8")


# -------------------------------------------------------------------- .gitignore


@pytest.mark.parametrize(
    "pattern",
    ["__pycache__/", ".pytest_cache/", ".venv/", "node_modules/", ".omc/"],
)
def test_gitignore_covers_the_required_pattern(pattern):
    lines = {
        line.strip()
        for line in GITIGNORE_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    }
    assert pattern in lines, f".gitignore does not ignore {pattern}"


def test_the_marketplace_manifest_passes_the_real_claude_cli_validator():
    """The schema assertions above are this repo's reading of the format.

    `claude plugin validate` is the format's own reading. Where the CLI is
    installed, it is the authority and runs; in CI, where it is not, the
    hand-written assertions above still hold the shape.
    """
    claude = shutil.which("claude")
    if not claude:
        pytest.skip("the claude CLI is not installed; the schema assertions above still apply")
    result = subprocess.run(
        [claude, "plugin", "validate", str(MARKETPLACE_PATH)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"claude plugin validate rejected the manifest:\n{result.stdout}{result.stderr}"
