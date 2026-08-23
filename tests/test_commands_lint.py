"""Lint for the `commands/ast/` slash-command surface.

Three invariants, in the order the task states them:

1. Every command file has valid YAML frontmatter carrying a non-empty `name` and
   a specific (non-placeholder) `description`.
2. Every skill directory a command references exists -- both the `routes_to`
   target (resolved through each skill's own frontmatter `name`) and every
   literal `skills/<dir>` path written in the body.
3. Every one of AST01..AST10 has exactly one audit command -- no category left
   without a targeted command, and no category with two competing ones.

Plus the guards that keep the surface honest rather than merely well-formed: a
command's `name` must match its filename (the slash command is addressed by
filename, so a drifting `name` silently mislabels it), and every repo-relative
artifact path a command cites in backticks must exist, so a command can never
send a reader to a file this repo does not ship.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
COMMANDS_DIR = REPO_ROOT / "commands" / "ast"
SKILLS_DIR = REPO_ROOT / "skills"

AST_IDS = [f"AST{n:02d}" for n in range(1, 11)]

#: Same floor the SKILL.md layout lint applies to its own frontmatter: a
#: description shorter than this is a placeholder, not a routing signal.
MIN_DESCRIPTION_CHARS = 40

#: Literal `skills/<dir>` references in a command body.
SKILL_PATH_RE = re.compile(r"\bskills/([A-Za-z0-9][A-Za-z0-9._-]*)")

#: Repo-relative artifact paths cited inside backticks. Restricted to the
#: top-level directories this repo actually ships so prose like `scripts/` in a
#: sentence about a generic package layout is not mistaken for a repo path.
CITED_PATH_RE = re.compile(
    r"`((?:adapters|config|detectors|docs|fixtures|scenarios|schemas|scripts|skills|validators)"
    r"/[A-Za-z0-9][A-Za-z0-9._/-]*)`"
)

#: Paths a command names as belonging to the *audited* package, not to this
#: repo. They are deliberately relative and must not be resolved here.
EXTERNAL_PATH_PREFIXES = ("./",)


def _command_files() -> list[Path]:
    assert COMMANDS_DIR.is_dir(), f"{COMMANDS_DIR} does not exist"
    files = sorted(COMMANDS_DIR.glob("*.md"))
    assert files, f"{COMMANDS_DIR} contains no command files"
    return files


COMMAND_FILES = _command_files()
COMMAND_IDS = [p.name for p in COMMAND_FILES]


def _split_frontmatter(path: Path) -> tuple[dict, str]:
    """Return (frontmatter_mapping, body). Raises AssertionError if malformed."""
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{path.name} must open with YAML frontmatter delimited by ---"
    end = text.find("\n---\n", 4)
    assert end != -1, f"{path.name} frontmatter is not closed with a second --- delimiter"
    fm = yaml.safe_load(text[4:end])
    assert isinstance(fm, dict), f"{path.name} frontmatter must parse as a YAML mapping"
    return fm, text[end + len("\n---\n") :]


def _skill_name_to_dir() -> dict[str, Path]:
    """Map each skill's frontmatter `name` to the directory that declares it."""
    mapping: dict[str, Path] = {}
    for skill_md in sorted(SKILLS_DIR.glob("*/SKILL.md")):
        fm, _ = _split_frontmatter(skill_md)
        name = fm.get("name")
        assert name, f"{skill_md} frontmatter is missing a `name`"
        assert name not in mapping, (
            f"skill name {name!r} is declared by both {mapping[name].name} and "
            f"{skill_md.parent.name}; `routes_to` could not resolve unambiguously"
        )
        mapping[str(name)] = skill_md.parent
    return mapping


SKILL_NAME_TO_DIR = _skill_name_to_dir()


def _routes(fm: dict) -> list[str]:
    """`routes_to` is a single skill name or a list of them."""
    raw = fm.get("routes_to")
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, list):
        return [str(item) for item in raw]
    return []


# ---------------------------------------------------------------------------
# 1. Valid frontmatter with name + description
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", COMMAND_FILES, ids=COMMAND_IDS)
def test_frontmatter_parses(path: Path) -> None:
    fm, body = _split_frontmatter(path)
    assert fm, f"{path.name} has empty frontmatter"
    assert body.strip(), f"{path.name} has frontmatter but no body"


@pytest.mark.parametrize("path", COMMAND_FILES, ids=COMMAND_IDS)
def test_frontmatter_has_name_and_description(path: Path) -> None:
    fm, _ = _split_frontmatter(path)

    name = fm.get("name")
    assert name, f"{path.name} frontmatter missing a non-empty `name`"
    assert isinstance(name, str), f"{path.name} frontmatter `name` must be a string"

    description = fm.get("description")
    assert description, f"{path.name} frontmatter missing a non-empty `description`"
    assert isinstance(description, str), f"{path.name} frontmatter `description` must be a string"
    assert len(description.strip()) >= MIN_DESCRIPTION_CHARS, (
        f"{path.name} frontmatter `description` must be a specific, non-placeholder "
        f"string (>={MIN_DESCRIPTION_CHARS} chars)"
    )


@pytest.mark.parametrize("path", COMMAND_FILES, ids=COMMAND_IDS)
def test_frontmatter_name_matches_filename(path: Path) -> None:
    """The slash command is addressed by filename; a drifting `name` mislabels it."""
    fm, _ = _split_frontmatter(path)
    assert fm["name"] == path.stem, (
        f"{path.name} declares name={fm['name']!r} but is invoked as /ast:{path.stem}; the two must agree"
    )


@pytest.mark.parametrize("path", COMMAND_FILES, ids=COMMAND_IDS)
def test_command_documents_its_contract(path: Path) -> None:
    """Every command states its arguments, a worked invocation, and its output."""
    _, body = _split_frontmatter(path)
    for heading in ("## Arguments", "## Example invocation", "## Output"):
        assert heading in body, f"{path.name} is missing a `{heading}` section"


@pytest.mark.parametrize("path", COMMAND_FILES, ids=COMMAND_IDS)
def test_command_names_the_skill_it_activates(path: Path) -> None:
    """The body must name at least one `routes_to` skill, not just declare it."""
    fm, body = _split_frontmatter(path)
    routes = _routes(fm)
    assert routes, f"{path.name} frontmatter declares no `routes_to` skill"
    assert any(skill in body for skill in routes), (
        f"{path.name} body never names any of its routes_to skills {routes}; a reader "
        f"cannot tell which skill the command activates"
    )


# ---------------------------------------------------------------------------
# 2. Every referenced skill directory exists
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", COMMAND_FILES, ids=COMMAND_IDS)
def test_routes_to_resolves_to_an_existing_skill_directory(path: Path) -> None:
    fm, _ = _split_frontmatter(path)
    for skill in _routes(fm):
        assert skill in SKILL_NAME_TO_DIR, (
            f"{path.name} routes_to {skill!r}, which no skills/*/SKILL.md declares as its "
            f"`name`. Known skills: {sorted(SKILL_NAME_TO_DIR)}"
        )
        skill_dir = SKILL_NAME_TO_DIR[skill]
        assert skill_dir.is_dir(), f"{path.name} routes to missing directory {skill_dir}"
        assert (skill_dir / "SKILL.md").is_file(), f"{skill_dir} has no SKILL.md to activate"


@pytest.mark.parametrize("path", COMMAND_FILES, ids=COMMAND_IDS)
def test_body_skill_directory_references_exist(path: Path) -> None:
    _, body = _split_frontmatter(path)
    for skill_dir_name in sorted(set(SKILL_PATH_RE.findall(body))):
        skill_dir = SKILLS_DIR / skill_dir_name
        assert skill_dir.is_dir(), (
            f"{path.name} references skills/{skill_dir_name}, which does not exist. "
            f"Known skill directories: {sorted(p.name for p in SKILLS_DIR.iterdir() if p.is_dir())}"
        )


@pytest.mark.parametrize("path", COMMAND_FILES, ids=COMMAND_IDS)
def test_cited_repo_paths_exist(path: Path) -> None:
    """A command must never send a reader to a file this repo does not ship."""
    _, body = _split_frontmatter(path)
    for cited in sorted(set(CITED_PATH_RE.findall(body))):
        if cited.startswith(EXTERNAL_PATH_PREFIXES):
            continue
        target = REPO_ROOT / cited
        assert target.exists(), f"{path.name} cites `{cited}`, which does not exist"


# ---------------------------------------------------------------------------
# 3. Exactly one audit command per AST01..AST10
# ---------------------------------------------------------------------------


def _audit_commands_by_category() -> dict[str, list[Path]]:
    by_cat: dict[str, list[Path]] = {}
    for path in COMMAND_FILES:
        fm, _ = _split_frontmatter(path)
        category = fm.get("ast_category")
        if category is None:
            continue
        by_cat.setdefault(str(category), []).append(path)
    return by_cat


AUDIT_COMMANDS = _audit_commands_by_category()


@pytest.mark.parametrize("ast_id", AST_IDS)
def test_exactly_one_audit_command_per_category(ast_id: str) -> None:
    matches = AUDIT_COMMANDS.get(ast_id, [])
    assert matches, (
        f"{ast_id} has no audit command; every category must be addressable on its own "
        f"(expected commands/ast/audit-{ast_id.lower()}.md)"
    )
    assert len(matches) == 1, (
        f"{ast_id} has {len(matches)} audit commands ({[p.name for p in matches]}); exactly one must claim the category"
    )


def test_no_audit_command_claims_an_unknown_category() -> None:
    unknown = sorted(set(AUDIT_COMMANDS) - set(AST_IDS))
    assert not unknown, f"commands/ast declares ast_category value(s) {unknown} outside AST01..AST10"


@pytest.mark.parametrize("ast_id", AST_IDS)
def test_audit_command_filename_and_routing_agree(ast_id: str) -> None:
    """audit-astNN.md must be the file that claims ASTNN, and route to its skill."""
    matches = AUDIT_COMMANDS.get(ast_id, [])
    if len(matches) != 1:
        pytest.skip(
            f"{ast_id} has {len(matches)} audit commands; test_exactly_one_audit_command_per_category owns that failure"
        )
    (path,) = matches
    assert path.name == f"audit-{ast_id.lower()}.md", (
        f"{ast_id}'s audit command is {path.name}; expected audit-{ast_id.lower()}.md so "
        f"the slash command reads /ast:audit-{ast_id.lower()}"
    )
    fm, _ = _split_frontmatter(path)
    routes = _routes(fm)
    assert len(routes) == 1, f"{path.name} targets a single category and must route to exactly one skill, got {routes}"
    assert SKILL_NAME_TO_DIR[routes[0]].name == ast_id, (
        f"{path.name} claims {ast_id} but routes to {routes[0]!r}, which lives in "
        f"skills/{SKILL_NAME_TO_DIR[routes[0]].name}"
    )


# ---------------------------------------------------------------------------
# Capability commands: the four non-per-category commands must all be present
# ---------------------------------------------------------------------------

REQUIRED_CAPABILITY_COMMANDS = {
    "audit-skill-package",
    "triage-finding",
    "validate-usf-manifest",
    "check-coverage",
}


def test_capability_commands_present() -> None:
    present = {p.stem for p in COMMAND_FILES}
    missing = sorted(REQUIRED_CAPABILITY_COMMANDS - present)
    assert not missing, f"commands/ast is missing capability command(s): {missing}"


def test_capability_commands_carry_no_ast_category() -> None:
    """A capability command spans categories; claiming one would break the 1:1 map."""
    for path in COMMAND_FILES:
        if path.stem not in REQUIRED_CAPABILITY_COMMANDS:
            continue
        fm, _ = _split_frontmatter(path)
        assert "ast_category" not in fm, (
            f"{path.name} is a capability command and must not declare `ast_category`; "
            f"that key is reserved for the ten per-category audit commands"
        )


def test_command_set_is_exactly_ten_audits_plus_four_capabilities() -> None:
    expected = REQUIRED_CAPABILITY_COMMANDS | {f"audit-{ast_id.lower()}" for ast_id in AST_IDS}
    assert {p.stem for p in COMMAND_FILES} == expected
