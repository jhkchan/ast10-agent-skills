"""AST02 -- Supply Chain Compromise detector.

`scenarios/registry.yaml` names four AST02 attack scenarios and tiers exactly
one of them ``static-detectable``. This module implements that one and no
more, and declares the other three so a reader of the module -- not only a
reader of the coverage matrix -- sees why the category's surface is this
small.

======================  =========================================================
Registry scenario       State
======================  =========================================================
AST02-S01 Registry      out-of-artifact. "Coordinated" and "hundreds" are
Flooding                properties of the registry's publication corpus over
                        time. One package is indistinguishable from one member
                        of a flood and from one honest publication. The registry
                        records no artifact_signal at all.
AST02-S02 Dependency    out-of-artifact. The defining condition is which package
Confusion               the resolver SELECTS at install time, which needs the
                        resolution namespace and the registry's contents.
                        Pin posture is the registry's declared artifact_signal
                        and is a proxy, never coverage; no check here computes
                        it, so nothing here may be labeled against it.
AST02-S03 Config-File   static-detectable. ``detect_config_file_hijacking``.
Hijacking
AST02-S04 Maintainer    out-of-artifact. A release pushed by an attacker holding
Account Takeover        the legitimate signing key verifies exactly as an honest
                        release does. The registry records no in-package signal.
======================  =========================================================

THE ONE CHECK
-------------
AST02-S03's defining condition, in the whitepaper's own words, is "execution
instructions in repository config files (hooks, MCP settings, environment
overrides) that trigger at project open" -- the trigger CVE-2025-59536 and
CVE-2026-21852 anchor, where "simply cloning and opening a malicious repo
triggers RCE and API key exfiltration before the user sees any dialog".

Two things follow, and both are load-bearing:

1. The check is keyed on the CONFIG SURFACE, not on the presence of a command
   string. A shell command inside a bundled script is ordinary; the same
   command inside ``.claude/settings.json`` is an execution path the host
   enters without the user acting. So the scan runs only over the paths a
   host auto-reads at project open, and a package that ships none of them is
   clear no matter what its scripts contain.

2. Within those files it is keyed on the AUTO-EXECUTED KEY. A settings file
   that carries permissions, a model name, or a benign editor variable is the
   normal case and does not fire; a hook entry carrying a command, an MCP
   server entry that spawns a process, an environment override that redirects
   the agent's API endpoint or preloads code into every child process, and a
   task declared to run on folder-open, are the four shapes the whitepaper
   names.

The whitepaper's mitigation is the same predicate read forward: "Treat
repository configuration files (hooks, .claude/settings.json,
ANTHROPIC_BASE_URL) as executable code and apply trust gates accordingly."
"""

from __future__ import annotations

import json
import re
from typing import Callable

from detectors.scaffold import Finding, static_detectable
from detectors.scaffold import f1_report as _f1_report
from detectors.scaffold import f1_scope as _f1_scope
from detectors.scaffold import run_all as _run_all

SCENARIO_TIERS: dict[str, str] = {
    "AST02-config-file-hijacking": "static-detectable",
    "AST02-registry-flooding": "out-of-artifact",
    "AST02-dependency-confusion": "out-of-artifact",
    "AST02-maintainer-account-takeover": "out-of-artifact",
}

STATIC_DETECTABLE: set[str] = static_detectable(SCENARIO_TIERS)

CHECK_COVERAGE: dict[str, dict] = {
    "AST02-config-file-hijacking": {
        "registry_ids": ["AST02-S03"],
        "covers": "full",
        "reason": (
            "AST02-S03 is tiered static-detectable because 'those config files ship inside "
            "the package. A command-bearing value under a key the host auto-executes at "
            "project open (a hook entry, .claude/settings.json, an ANTHROPIC_BASE_URL "
            "override) is a structural key-and-value match.' This check is that match: it "
            "reads only the config paths a host auto-reads at project open and fires only on "
            "the auto-executed keys within them, so a package with no such config file, or "
            "one whose settings carry no execution path, is decided clear rather than "
            "unexamined."
        ),
    },
}

F1_SCOPE: str = _f1_scope(CHECK_COVERAGE)


# --------------------------------------------------------------------------
# The auto-read config surface
# --------------------------------------------------------------------------
#
# Matched on the tail of the package-relative path so a config shipped in a
# subdirectory of the package counts, and a file merely NAMED settings.json
# somewhere unrelated does not.

_AUTO_EXEC_CONFIG_SUFFIXES: tuple[str, ...] = (
    ".claude/settings.json",
    ".claude/settings.local.json",
    ".claude/hooks.json",
    ".mcp.json",
    ".cursor/mcp.json",
    ".cursor/settings.json",
    ".vscode/tasks.json",
    ".vscode/settings.json",
)

#: Environment variables whose value changes where the agent sends traffic,
#: what credential it presents, or what code is loaded into every child
#: process. Setting one of these from a repository config file is the
#: "environment overrides" half of the whitepaper's scenario; setting EDITOR
#: is not.
_CONTROL_PLANE_ENV_RE = re.compile(
    r"^(?:"
    r"ANTHROPIC_(?:BASE_URL|AUTH_TOKEN|API_KEY|MODEL)"
    r"|OPENAI_(?:BASE_URL|API_KEY)"
    r"|AWS_(?:ACCESS_KEY_ID|SECRET_ACCESS_KEY|ENDPOINT_URL)"
    r"|NODE_OPTIONS"
    r"|LD_PRELOAD|LD_LIBRARY_PATH|DYLD_INSERT_LIBRARIES"
    r"|PYTHONSTARTUP|PYTHONPATH"
    r"|BASH_ENV|ENV"
    r"|GIT_SSH_COMMAND|GIT_PROXY_COMMAND"
    r"|npm_config_[A-Za-z0-9_]+"
    r"|HTTPS?_PROXY|ALL_PROXY"
    r")$",
    re.IGNORECASE,
)

#: Keys whose value a host hands to a shell or process spawner.
_COMMAND_KEYS = ("command", "cmd", "script", "exec", "run", "shellcmd")


def _config_files(pkg: dict) -> dict[str, str]:
    files = pkg.get("files") or {}
    out: dict[str, str] = {}
    for path, content in files.items():
        if not isinstance(content, str):
            continue
        # removeprefix, never lstrip: `lstrip("./")` strips every leading `.`
        # and `/` character, which silently turns `.claude/settings.json` into
        # `claude/settings.json` and makes the whole check dead.
        normalized = path.replace("\\", "/").removeprefix("./").lower()
        if normalized.endswith(_AUTO_EXEC_CONFIG_SUFFIXES) or normalized in _AUTO_EXEC_CONFIG_SUFFIXES:
            out[path] = content
    return out


def _command_value(node) -> str | None:
    """A command-bearing scalar directly under a command key of ``node``."""
    if not isinstance(node, dict):
        return None
    for key in _COMMAND_KEYS:
        for actual, value in node.items():
            if actual.lower() != key:
                continue
            if isinstance(value, str) and value.strip():
                return value.strip()
            if isinstance(value, list) and value and all(isinstance(v, str) for v in value):
                return " ".join(value).strip()
    return None


def _walk(node, trail: tuple[str, ...] = ()):
    """Every (key-trail, mapping) in a parsed config document."""
    if isinstance(node, dict):
        yield trail, node
        for key, value in node.items():
            yield from _walk(value, trail + (str(key),))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _walk(value, trail + (f"[{index}]",))


def _hook_finding(path: str, document) -> str | None:
    for trail, node in _walk(document):
        if not any(part.lower() in {"hooks", "hook"} for part in trail):
            continue
        command = _command_value(node)
        if command:
            return f"{path}: hook entry at {'.'.join(trail) or '<root>'} carries a command: {command!r}"
    return None


def _mcp_finding(path: str, document) -> str | None:
    for trail, node in _walk(document):
        if not trail or trail[-1] in {"mcpServers", "servers"}:
            continue
        if not any(part in {"mcpServers", "servers"} for part in trail):
            continue
        command = _command_value(node)
        if command:
            return f"{path}: MCP server {'.'.join(trail)} spawns a process at project open: {command!r}"
    return None


def _env_finding(path: str, document) -> str | None:
    for trail, node in _walk(document):
        if not trail or trail[-1].lower() not in {"env", "environment", "envvars"}:
            continue
        for name, value in node.items():
            if _CONTROL_PLANE_ENV_RE.match(str(name)):
                return (
                    f"{path}: environment override {'.'.join(trail)}.{name}={value!r} "
                    f"redirects the agent's control plane at project open"
                )
    return None


def _folder_open_task_finding(path: str, document) -> str | None:
    for _trail, node in _walk(document):
        run_options = node.get("runOptions") if isinstance(node, dict) else None
        if not isinstance(run_options, dict):
            continue
        if str(run_options.get("runOn", "")).lower() != "folderopen":
            continue
        command = _command_value(node)
        if command:
            return f"{path}: task declared runOn=folderOpen executes {command!r} on project open"
    return None


_CONFIG_RULES = (
    _hook_finding,
    _mcp_finding,
    _env_finding,
    _folder_open_task_finding,
)


def detect_config_file_hijacking(pkg: dict) -> Finding:
    """AST02-S03: an execution path in a config file the host reads at project open."""
    scenario = "AST02-config-file-hijacking"
    configs = _config_files(pkg)
    if not configs:
        return Finding(scenario, False, "package ships no config file a host auto-reads at project open")
    for path, content in sorted(configs.items()):
        try:
            document = json.loads(content)
        except json.JSONDecodeError as exc:
            # Malformed config is AST04's parsing surface, not an execution
            # path; recorded rather than silently treated as clean.
            return Finding(scenario, False, f"{path}: unparseable JSON ({exc.msg}); no execution path decided")
        for rule in _CONFIG_RULES:
            evidence = rule(path, document)
            if evidence:
                return Finding(scenario, True, evidence)
    return Finding(
        scenario,
        False,
        f"auto-read config file(s) {sorted(configs)} carry no hook command, MCP spawn, "
        f"control-plane environment override, or folder-open task",
    )


DETECTORS: dict[str, Callable[[dict], Finding]] = {
    "AST02-config-file-hijacking": detect_config_file_hijacking,
}


def run_all(pkg: dict) -> list[Finding]:
    return _run_all(DETECTORS, pkg)


def f1_report(fixtures: list[tuple[dict, set[str]]] | None = None) -> dict:
    return _f1_report(STATIC_DETECTABLE, DETECTORS, fixtures, F1_SCOPE)
