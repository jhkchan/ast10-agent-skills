"""AST06 -- Weak Isolation detector.

AST06 is the one category in this repository whose registry entry names a
scenario the package genuinely decides itself. ``scenarios/registry.yaml``
tiers ``AST06-S01`` (Host Escape) ``static-detectable`` and states its defining
condition as a disjunction:

    a shell-exec call site writing to a host persistence location (crontab,
    systemd unit, shell rc, launch agent) outside the skill's own tree, OR a
    declared write scope reaching filesystem root. Both are structural facts of
    the package.

Two checks implement one disjunct each --
:func:`detect_host_persistence_write` reads bundled scripts, and
:func:`detect_root_write_scope` reads the declared write policy -- and together
they decide the condition as written. Neither is a superset heuristic and
neither is a keyword scan: the script side matches only ``ast.Call`` nodes, and
the manifest side evaluates the declared policy through
``validators/usf.py``'s own ``write_allowed``, so a ``deny_write`` entry that
shadows a broad ``write`` entry is honoured here exactly as the validator
honours it.

The other three AST06 scenarios (Network Pivot, Skill Shadowing, Localhost
Attack Surface) and Cross-Agent Workspace Contamination are out-of-artifact;
``skills/AST06/coverage-matrix.md`` records why for each, and the two checks
below that touch them are declared non-coverage in ``CHECK_COVERAGE``.

TWO TABLES, TWO NAMESPACES
--------------------------
``SCENARIO_TIERS`` mirrors ``scenarios/registry.yaml``: all five canonical
scenario ids (``AST06-S01`` .. ``AST06-S05``) mapped to the tier the registry
assigns them, out-of-artifact ones included, never a tier of this module's own
invention. It used to be keyed by this module's CHECK slugs with five of them
written down as ``static-detectable``, which made ``STATIC_DETECTABLE`` five
checks deep and let ``cli/bin/cli.js list`` report AST06 as deciding five
scenarios in a category that decides exactly one.

Per-CHECK metadata lives in ``CHECK_COVERAGE``, keyed by check id -- the table
that answers "what does this check bear on, and how honestly", and the one
``scenarios/registry.yaml`` names checks into through
``artifact_signal_checks``. The join between the two runs through
``SCENARIO_DETECTORS`` at the foot of this file: ``AST06-S01`` is decided by
whichever of its two ``covers: full`` disjuncts fires, and the F1 denominator
stays the registry's tier -- one scenario -- rather than the module's check
count.

Package shape (the flat dict every detector in this repo consumes)::

    {
      "manifest": {
          "permissions": {
              "write": [...], "deny_write": [...], "read": [...],
              "shell": {"allowed": bool, "commands": [...]} | bool,
              "network": {...},
          },
      },
      "files": {"<relative/path>": "<text content>", ...},
    }

``detectors/fixture_loader.py`` and ``scripts/dogfood.py`` both produce it --
the first from a labeled fixture directory, the second from a shipped
``skill.usf.yaml`` -- so the corpus and the dogfood run read the same shape.
"""

from __future__ import annotations

import ast
import re
from typing import Callable

from detectors import pysource
from detectors.scaffold import Finding, scenario_detectors, static_detectable
from detectors.scaffold import f1_report as _f1_report
from detectors.scaffold import f1_scope as _f1_scope
from detectors.scaffold import run_all as _run_all
from validators import usf

#: Tiers keyed by ``scenarios/registry.yaml``'s canonical scenario ids, taken
#: verbatim from it. All five of AST06's named scenarios are here, including the
#: four out-of-artifact ones, so a reader of this module alone counts the same
#: five scenarios and the same tiers a reader of the registry does. The registry
#: is the authority; this restates it and may never disagree with it
#: (`skills/AST06/scripts/test_ast06_detector.py` pins the equality).
SCENARIO_TIERS: dict[str, str] = {
    "AST06-S01": "static-detectable",  # Host Escape
    "AST06-S02": "out-of-artifact",  # Network Pivot
    "AST06-S03": "out-of-artifact",  # Skill Shadowing
    "AST06-S04": "out-of-artifact",  # Localhost Attack Surface
    "AST06-S05": "out-of-artifact",  # Cross-Agent Workspace Contamination
}

#: One scenario: AST06-S01. The module ships five checks, which is a different
#: number about a different thing.
STATIC_DETECTABLE: set[str] = static_detectable(SCENARIO_TIERS)

# Per-CHECK metadata, keyed by check id -- a different namespace from
# SCENARIO_TIERS above, and the one `scenarios/registry.yaml` names checks into
# through `artifact_signal_checks`.
CHECK_COVERAGE: dict[str, dict] = {
    "AST06-host-persistence-write": {
        "registry_ids": ["AST06-S01"],
        "covers": "full",
        "reason": (
            "Decides the first disjunct of AST06-S01's defining condition verbatim: a "
            "shell-exec or file-write call site in a bundled script whose target is a host "
            "persistence location (crontab, systemd unit, shell rc, launch agent, rc.local, "
            "authorized_keys, Windows Run key) outside the skill's own tree. The whitepaper's "
            "scenario text is 'malicious skill executes os.system() to plant a cron job on "
            "the host, persisting beyond skill uninstall'; this matches that call site, not a "
            "capability that would merely permit it."
        ),
    },
    "AST06-root-write-scope": {
        "registry_ids": ["AST06-S01"],
        "covers": "full",
        "reason": (
            "Decides the second disjunct of AST06-S01's defining condition: a declared write "
            "scope reaching filesystem root, or an explicit declared write to a host "
            "persistence path. Effective scope only -- an entry that deny_write shadows is "
            "skipped, evaluated through validators/usf.py's own write_allowed so the "
            "deny_write-wins rule cannot mean one thing in the validator and another here."
        ),
    },
    "AST06-unrestricted-shell-exec": {
        "registry_ids": [],
        "covers": "category-precondition",
        "derivation": (
            "AST06's premise that isolation is an architectural default rather than a "
            "tunable policy, and its 'implement per-skill process isolation' mitigation. Not "
            "AST06-S01: a granted shell with no command allow-list is a capability, and the "
            "scenario's defining condition is an act -- which the two checks above decide."
        ),
        "reason": (
            "Reads only whether shell is granted with no bounding command allow-list (a "
            "wildcard entry does not bound). That flags a superset of packages, including "
            "many that never write outside their own tree, so it may not claim coverage of a "
            "named scenario. Retained because a granted-and-unbounded shell is the "
            "precondition every AST06 mitigation is written against."
        ),
    },
    "AST06-unscoped-shared-state-write": {
        "registry_ids": ["AST06-S05"],
        "covers": "artifact-signal-only",
        "reason": (
            "Computes AST06-S05's declared artifact_signal verbatim -- 'declared writes to "
            "shared workspace, memory, or credential paths with no agent-scoped namespace'. "
            "Package-decidable, and never coverage: whether a second agent is pointed at the "
            "same writable state, and whether it later treats the content as trusted, are "
            "deployment facts no package carries."
        ),
    },
    "AST06-missing-sandbox-declaration": {
        "registry_ids": ["AST10-S04"],
        "covers": "artifact-signal-only",
        "reason": (
            "An absent or empty permissions block is decidable by inspecting the package "
            "alone, and scenarios/registry.yaml names THIS CHECK as the reader of AST10-S04 "
            "Manifest Stripping's artifact_signal ('absent permission or risk metadata in a "
            "package whose format supports it -- the same signal AST06's "
            "missing-sandbox-declaration check reads'). It cannot decide AST10-S04: a ported "
            "package with no permission block is indistinguishable from one that never "
            "declared any without the pre-port manifest to diff against."
        ),
    },
    # Declared and deliberately NOT implemented. It kept its place when this
    # module's tier table was re-keyed onto registry ids rather than being
    # dropped: an id the category once declared, silently deleted, reads as a
    # check that never existed instead of one that was ruled out on purpose.
    "AST06-cross-skill-data-leak": {
        "registry_ids": ["AST06-S05"],
        "covers": "artifact-signal-only",
        "reason": (
            "No function ships for this id and none may: whether data actually crossed "
            "between two co-installed skills is an execution-trace property, which is why "
            "the registry tiers AST06-S05 out-of-artifact. The nearest package-decidable "
            "thing is that scenario's declared artifact_signal, and "
            "AST06-unscoped-shared-state-write above is the check that computes it; this "
            "id is recorded as the same proxy link and is absent from DETECTORS, so it "
            "enters no denominator anywhere."
        ),
    },
}

F1_SCOPE: str = _f1_scope(CHECK_COVERAGE)


# --------------------------------------------------------------------------- #
# Host persistence: what "outside the skill's own tree" concretely means.
#
# Each entry is (pattern, human label). The patterns are anchored on the
# platform locations that survive a skill uninstall, which is the property the
# whitepaper's Host Escape scenario turns on ("persisting beyond skill
# uninstall") -- not on a general "writes a file somewhere" notion.
# --------------------------------------------------------------------------- #

_HOST_PERSISTENCE: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bcrontab\b"), "cron table"),
    (re.compile(r"/etc/cron(?:tab|\.d|\.daily|\.hourly|\.weekly|\.monthly)\b"), "system cron directory"),
    (re.compile(r"/var/spool/cron\b"), "user cron spool"),
    (re.compile(r"/etc/systemd/system\b"), "systemd system unit"),
    (re.compile(r"/usr/lib/systemd/system\b"), "systemd vendor unit"),
    (re.compile(r"\.config/systemd/user\b"), "systemd user unit"),
    (re.compile(r"\bsystemctl\s+(?:--user\s+)?enable\b"), "systemd unit enablement"),
    (re.compile(r"/Library/LaunchAgents\b"), "launch agent"),
    (re.compile(r"/Library/LaunchDaemons\b"), "launch daemon"),
    (re.compile(r"\blaunchctl\s+(?:load|bootstrap|enable)\b"), "launchd registration"),
    (re.compile(r"(?:^|[/~])\.(?:bashrc|zshrc|profile|bash_profile|zprofile|zshenv|kshrc)\b"), "shell rc file"),
    (re.compile(r"/etc/profile\.d\b"), "system shell profile"),
    (re.compile(r"/etc/rc\.local\b"), "init script"),
    (re.compile(r"\.ssh/authorized_keys\b"), "ssh authorized_keys"),
    (re.compile(r"CurrentVersion\\+Run\b"), "Windows Run key"),
    (re.compile(r"(?i)shell:startup\b"), "Windows startup folder"),
)

#: Commands that are host-scoped by construction -- they do not name a path, so
#: the escapes-the-tree test below does not apply to them.
_HOST_SCOPED_COMMANDS = re.compile(
    r"\bcrontab\b"
    r"|\bsystemctl\s+(?:--user\s+)?enable\b"
    r"|\blaunchctl\s+(?:load|bootstrap|enable)\b"
)

#: A literal reaches outside the skill's tree when it is rooted at the
#: filesystem root, at a home directory, or at an environment-expanded home.
_ESCAPES_TREE = re.compile(r"(^|[\s\"'=:])(/|~/|~$|\$HOME|\$\{HOME\}|%USERPROFILE%|%APPDATA%|\.\./)")

_SHELL_EXEC_ROOTS = frozenset({"os", "subprocess", "commands", "pty", "asyncio"})
_SHELL_EXEC_ATTRS = frozenset(
    {
        "system",
        "popen",
        "run",
        "call",
        "check_call",
        "check_output",
        "Popen",
        "getoutput",
        "getstatusoutput",
        "spawn",
        "spawnl",
        "spawnv",
        "execl",
        "execv",
        "execvp",
        "create_subprocess_shell",
        "create_subprocess_exec",
    }
)
_WRITE_ATTRS = frozenset({"write_text", "write_bytes", "copy", "copyfile", "copy2", "move", "symlink", "link"})
_WRITE_MODE = re.compile(r"^[wax]")


def _persistence_hit(text: str) -> str | None:
    """The persistence location a literal names, or ``None``."""
    for pattern, label in _HOST_PERSISTENCE:
        if not pattern.search(text):
            continue
        if _HOST_SCOPED_COMMANDS.search(text) or _ESCAPES_TREE.search(text):
            return label
    return None


def _is_shell_exec(call: ast.Call) -> bool:
    root, attr = pysource.call_root(call), pysource.call_attr(call)
    if root in _SHELL_EXEC_ROOTS and attr in _SHELL_EXEC_ATTRS:
        return True
    return pysource.call_name(call) in {"system", "popen"} and root == attr


def _is_file_write(call: ast.Call) -> bool:
    name, attr = pysource.call_name(call), pysource.call_attr(call)
    if attr in _WRITE_ATTRS:
        return True
    if name in {"open", "io.open", "codecs.open"}:
        modes = [
            kw.value.value
            for kw in call.keywords
            if kw.arg == "mode" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str)
        ]
        if len(call.args) >= 2 and isinstance(call.args[1], ast.Constant) and isinstance(call.args[1].value, str):
            modes.append(call.args[1].value)
        return any(_WRITE_MODE.match(mode) for mode in modes)
    return False


def detect_host_persistence_write(pkg: dict) -> Finding:
    """AST06-S01, disjunct one: a call site that plants host persistence.

    Matches only ``ast.Call`` nodes in the package's bundled Python, so the
    pattern table above -- and any fixture source quoted inside a test module --
    is not itself a hit. A file that does not parse is reported as unparsed
    rather than as clean.
    """
    unparsed: list[str] = []
    for path, source in sorted(pysource.python_files(pkg).items()):
        tree = pysource.parse(source)
        if tree is None:
            unparsed.append(path)
            continue
        consts = pysource.module_string_constants(tree)
        for call in pysource.iter_calls(tree):
            if not (_is_shell_exec(call) or _is_file_write(call)):
                continue
            for text in pysource.call_argument_strings(call, consts):
                label = _persistence_hit(text)
                if label:
                    return Finding(
                        "AST06-host-persistence-write",
                        True,
                        f"{path}: {pysource.call_name(call)}() targets a {label} outside the skill tree: {text!r}",
                    )
    note = f" (unparsed: {unparsed})" if unparsed else ""
    return Finding(
        "AST06-host-persistence-write",
        False,
        f"no shell-exec or write call site targets a host persistence location{note}",
    )


# --------------------------------------------------------------------------- #
# Declared write scope
# --------------------------------------------------------------------------- #

#: Declared scopes that reach filesystem root (or a whole home directory).
_ROOT_SCOPES = frozenset({"/", "//", "/*", "/**", "/**/*", "*", "**", "~", "~/", "~/*", "~/**", "$HOME", "${HOME}"})


def _permissions(pkg: dict) -> dict:
    return pkg.get("manifest", {}).get("permissions") or {}


def _files_block(pkg: dict) -> dict:
    """The write policy in either shape: flat (translated) or USF-nested."""
    permissions = _permissions(pkg)
    nested = permissions.get("files")
    if isinstance(nested, dict):
        return nested
    return {
        "read": permissions.get("read") or [],
        "write": permissions.get("write") or [],
        "deny_write": permissions.get("deny_write") or [],
    }


def _effective_writes(pkg: dict) -> list[str]:
    """Declared write entries that ``deny_write`` does not shadow.

    Uses ``validators/usf.py``'s ``write_allowed`` rather than re-deriving the
    precedence rule, so "deny_write always wins over write" means the same thing
    to this detector as it does to the validator.
    """
    files = _files_block(pkg)
    manifest = {"permissions": {"files": files}}
    return [
        entry
        for entry in (files.get("write") or [])
        if isinstance(entry, str) and entry.strip() and usf.write_allowed(manifest, entry)
    ]


def _normalize_scope(entry: str) -> str:
    stripped = entry.strip()
    return stripped[2:] if stripped.startswith("./") and len(stripped) > 2 else stripped


def detect_root_write_scope(pkg: dict) -> Finding:
    """AST06-S01, disjunct two: a declared write scope reaching filesystem root.

    Also fires on an explicitly declared write to a host persistence path -- the
    same escape stated in the manifest instead of in a script. Entries fully
    shadowed by ``deny_write`` are not scope, so they are skipped.
    """
    for entry in _effective_writes(pkg):
        scope = _normalize_scope(entry)
        if scope in _ROOT_SCOPES:
            return Finding(
                "AST06-root-write-scope",
                True,
                f"permissions write scope {entry!r} reaches filesystem root and no deny_write shadows it",
            )
        label = _persistence_hit(scope)
        if label:
            return Finding(
                "AST06-root-write-scope",
                True,
                f"permissions write scope {entry!r} declares a {label} outside the skill tree",
            )
    return Finding("AST06-root-write-scope", False, "no effective write scope reaches root or host persistence")


# --------------------------------------------------------------------------- #
# Shared, unscoped writable state (AST06-S05's artifact_signal)
# --------------------------------------------------------------------------- #

_SHARED_STATE: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?:^|/)(?:SOUL|MEMORY|AGENTS)\.md$"), "agent identity/memory file"),
    (re.compile(r"\.aws/credentials\b"), "cloud credential store"),
    (re.compile(r"\.netrc\b"), "netrc credential store"),
    (re.compile(r"\.docker/config\.json\b"), "container registry credential store"),
    (re.compile(r"\.config/gh/hosts\.ya?ml\b"), "forge credential store"),
    (re.compile(r"(?:^|/)\.env$"), "environment secret file"),
    (re.compile(r"(?:^|/)(?:workspace|shared|scratch)(?:/|$)"), "shared workspace root"),
    (re.compile(r"\.(?:agent|claude|openclaw)/(?:memory|state|context)\b"), "shared agent memory"),
)

#: A path segment pair that scopes shared state to one agent, session or tenant.
_AGENT_SCOPED = re.compile(r"(?:^|/)(?:agent|agents|session|sessions|tenant|tenants|instance)/[^/]+/")


def detect_unscoped_shared_state_write(pkg: dict) -> Finding:
    """AST06-S05's artifact_signal: a declared write to shared state with no
    agent-scoped namespace. A precondition for contamination, never the
    contamination itself -- which needs a second agent this package cannot see."""
    for entry in _effective_writes(pkg):
        scope = _normalize_scope(entry)
        for pattern, label in _SHARED_STATE:
            if not pattern.search(scope):
                continue
            if _AGENT_SCOPED.search(scope):
                continue
            return Finding(
                "AST06-unscoped-shared-state-write",
                True,
                f"write scope {entry!r} targets a {label} with no agent-scoped path segment",
            )
    return Finding(
        "AST06-unscoped-shared-state-write",
        False,
        "no effective write scope targets unscoped shared workspace, memory, or credential state",
    )


# --------------------------------------------------------------------------- #
# Declared shell posture
# --------------------------------------------------------------------------- #


def _shell_declaration(pkg: dict) -> tuple[bool, list[str]]:
    """``(granted, bounding_commands)`` from any of the three shapes seen in the wild.

    USF v1 spells ``permissions.shell`` as a bare boolean with no command list;
    platform-native manifests use ``{"allowed": bool, "commands": [...]}`` or a
    single command string. Reading only one of the three is how this check used
    to raise ``AttributeError`` on a manifest that conforms to this repo's own
    schema.
    """
    shell = _permissions(pkg).get("shell")
    if isinstance(shell, dict):
        commands = [c for c in (shell.get("commands") or []) if isinstance(c, str)]
        return bool(shell.get("allowed")), commands
    if isinstance(shell, bool):
        return shell, []
    if isinstance(shell, str):
        text = shell.strip()
        if text.lower() in {"", "false", "no", "none", "off"}:
            return False, []
        return True, ([] if text in {"*", "all"} else [text])
    return False, []


def detect_unrestricted_shell_exec(pkg: dict) -> Finding:
    """Shell granted with nothing bounding it.

    A command allow-list bounds the grant only if its entries are literal
    commands: an entry containing a wildcard (``sudo *``) is a grant wearing an
    allow-list's clothes and does not bound anything.
    """
    granted, commands = _shell_declaration(pkg)
    bounding = [c for c in commands if c.strip() and "*" not in c]
    detected = granted and not bounding
    if detected:
        evidence = (
            f"shell granted with no bounding command allow-list (commands={commands})"
            if commands
            else "shell granted with no command allow-list"
        )
    else:
        evidence = f"shell granted={granted} bounding commands={bounding}"
    return Finding("AST06-unrestricted-shell-exec", detected, evidence)


def detect_missing_sandbox_declaration(pkg: dict) -> Finding:
    """No `permissions` block at all -- no isolation posture is declared,
    distinct from a broad-but-present one (unrestricted-shell-exec)."""
    permissions = pkg.get("manifest", {}).get("permissions")
    detected = not permissions
    evidence = "manifest.permissions is unset or empty" if detected else "permissions block present"
    return Finding("AST06-missing-sandbox-declaration", detected, evidence)


DETECTORS: dict[str, Callable[[dict], Finding]] = {
    "AST06-host-persistence-write": detect_host_persistence_write,
    "AST06-root-write-scope": detect_root_write_scope,
    "AST06-unrestricted-shell-exec": detect_unrestricted_shell_exec,
    "AST06-unscoped-shared-state-write": detect_unscoped_shared_state_write,
    "AST06-missing-sandbox-declaration": detect_missing_sandbox_declaration,
}


#: The registry-keyed view of the checks: every scenario in STATIC_DETECTABLE
#: mapped to the `covers: full` checks that decide it. For AST06 that is
#: ``{"AST06-S01": <host-persistence-write OR root-write-scope>}`` -- the
#: scenario's defining condition is a disjunction, so either disjunct firing
#: decides it. The three checks that are not `covers: full` are deliberately not
#: here: a proxy is never coverage, so it may not put a true positive in a
#: scenario's column.
SCENARIO_DETECTORS: dict[str, Callable[[dict], Finding]] = scenario_detectors(DETECTORS, CHECK_COVERAGE)


def run_all(pkg: dict) -> list[Finding]:
    return _run_all(DETECTORS, pkg)


def f1_report(fixtures: list[tuple[dict, set[str]]] | None = None) -> dict:
    """F1 over the registry's static-detectable tier for AST06 -- AST06-S01 alone.

    The denominator is one scenario, not five checks. ``fixtures`` label
    expected detections with registry scenario ids, and ``SCENARIO_DETECTORS``
    is what puts the module's findings into that same namespace; the three
    checks that decide no named scenario are measured per labeled pair by
    ``detectors/fixture_loader.py`` under their own ``covers`` labels instead.
    ``F1_SCOPE`` stays ``mixed-proxy`` -- the module as a whole is a mixture, and
    reporting the more conservative of the two available labels beside the
    number is the direction this repository errs in.
    """
    return _f1_report(STATIC_DETECTABLE, SCENARIO_DETECTORS, fixtures, F1_SCOPE)
