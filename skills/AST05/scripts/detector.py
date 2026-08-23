"""AST05 -- Untrusted External Instructions detector.

**AST05's static-detectable tier is empty, and that is the finding.**
``scenarios/registry.yaml`` tiers none of AST05's six named scenarios
``static-detectable``: Author Rug-Pull needs the referenced document at two
points in time, Reviewer Bait-and-Switch needs several fetch vantage points,
Transitive Reference Chaining needs the chain followed, Relay-Node
Amplification needs the pipeline's per-node backbone models, DoS needs a
runtime budget, and Malicious Instructions Embedded in Documents is
agent-judgable. No check in this module therefore claims ``covers: full``, and
this module can never publish a scenario-level F1 -- ``F1_SCOPE`` is
``artifact-signal-only`` and travels with every number ``f1_report`` returns.

What it does ship is five mechanical checks over the *enabling preconditions*
the registry declares as ``artifact_signal`` for four of those scenarios. Each
is grounded in a preventive mitigation the whitepaper states for AST05:

``AST05-fetched-content-instruction-sink``
    "Separate Instructions from Data ... Retrieved information should be used
    only as reference data and must not override or modify the agent's system
    or developer instructions." The check follows fetched bytes through a
    bundled script to the instruction channel and fires when they arrive with
    no provenance wrapper or boundary delimiter.

``AST05-remote-response-executed``
    The same dataflow into an *executable* sink (``eval``/``exec``/``compile``,
    a shell, ``pickle.loads``, an unsafe YAML load).

``AST05-absent-instruction-boundary``
    For a package that demonstrably fetches, whether its decision rules declare
    an instruction-versus-data boundary at all. Gated on ingestion: a package
    that never fetches has no boundary to establish, and flagging it would make
    this an unconditional absence check that fires on everything.

``AST05-unrestricted-network-fetch`` / ``AST05-wildcard-domain-allowlist``
    "Allowlist permitted reference domains ... restrict the external hosts a
    skill may fetch from to a vetted allowlist." The two read how wide the
    declared fetch surface is; ``scenarios/registry.yaml`` names both by name as
    the readers of AST06-S02 Network Pivot's ``artifact_signal``.

The dataflow checks match ``ast.Call`` nodes, never source text. A regex for
``requests.get`` matches this module's own pattern tables and every fixture
literal quoted inside the test module beside it; ``ast.parse`` does not, which
is why ``scripts/dogfood.py`` can point these checks at this very file without
a suppression entry.
"""

from __future__ import annotations

import ast
import re
from typing import Callable, Iterator

from detectors import pysource
from detectors.scaffold import Finding, static_detectable
from detectors.scaffold import f1_report as _f1_report
from detectors.scaffold import f1_scope as _f1_scope
from detectors.scaffold import run_all as _run_all

SCENARIO_TIERS: dict[str, str] = {
    "AST05-fetched-content-instruction-sink": "static-detectable",
    "AST05-remote-response-executed": "static-detectable",
    "AST05-absent-instruction-boundary": "static-detectable",
    "AST05-unrestricted-network-fetch": "static-detectable",
    "AST05-wildcard-domain-allowlist": "static-detectable",
    # Whether a fetched instruction was actually *complied with* over the
    # skill's own stated task needs the transcript read with judgment. The
    # registry tiers the corresponding named scenario (AST05-S05) agent-judgable
    # for the same reason; nothing is implemented for it.
    "AST05-injected-instruction-compliance": "agent-judgable",
}

STATIC_DETECTABLE: set[str] = static_detectable(SCENARIO_TIERS)

# Not one of AST05's six named scenarios is static-detectable, so not one check
# here may claim `covers: full`. Every entry is a declared artifact_signal.
CHECK_COVERAGE: dict[str, dict] = {
    "AST05-fetched-content-instruction-sink": {
        "registry_ids": ["AST05-S01", "AST05-S05"],
        "covers": "artifact-signal-only",
        "reason": (
            "Computes the artifact_signal both scenarios declare -- 'bundled document or "
            "response handling that concatenates extracted content into an instruction or "
            "executable sink with no provenance tag or boundary delimiter' (AST05-S05), and "
            "the unpinned external reference routed into a sink (AST05-S01). It decides "
            "neither: AST05-S01's defining event is an edit to remote content after review, "
            "and AST05-S05 turns on whether the boundary a skill establishes is *adequate*, "
            "which is semantic. A skill can route fetched bytes into a prompt and never be "
            "rug-pulled, and can pin every reference and still mishandle a document."
        ),
    },
    "AST05-remote-response-executed": {
        "registry_ids": ["AST05-S05"],
        "covers": "artifact-signal-only",
        "reason": (
            "The executable half of AST05-S05's declared artifact_signal: a network response "
            "body reaching eval/exec/compile, a shell, or an unsafe deserializer. Package-"
            "decidable, and not coverage -- the malicious document arrives at runtime and is "
            "not in the package, so what the sink executes is never decided here."
        ),
    },
    "AST05-absent-instruction-boundary": {
        "registry_ids": ["AST05-S04", "AST05-S05"],
        "covers": "artifact-signal-only",
        "reason": (
            "Computes AST05-S04's declared artifact_signal -- 'decision rules that consume "
            "upstream skill output without re-establishing an instruction-versus-data "
            "boundary at the hop'. It cannot decide AST05-S04: the whitepaper states that a "
            "chain's injection resistance is the minimum over the backbone models on its "
            "path, and neither the path nor the models are package content. The presence of "
            "a declared delimiter convention is also weaker than the adequacy judgement "
            "AST05-S05 needs."
        ),
    },
    "AST05-unrestricted-network-fetch": {
        "registry_ids": ["AST06-S02"],
        "covers": "artifact-signal-only",
        "reason": (
            "A blanket egress grant -- `network: true`, an allow-all policy, or a network "
            "block that bounds no host set at all -- is decidable by inspecting the package "
            "alone and is verbatim the artifact_signal the registry declares on AST06-S02 "
            "Network Pivot. It does not decide that scenario, which turns on the host "
            "applying no network sandbox and on which services are co-located."
        ),
    },
    "AST05-wildcard-domain-allowlist": {
        "registry_ids": ["AST06-S02"],
        "covers": "artifact-signal-only",
        "reason": (
            "A '*' or bare-TLD entry in the declared allow-list is the same AST06-S02 "
            "artifact_signal read one field deeper -- an allowlist that is not an allowlist. "
            "Package-decidable, never coverage of the pivot."
        ),
    },
}

F1_SCOPE: str = _f1_scope(CHECK_COVERAGE)


# --------------------------------------------------------------------------- #
# Declared fetch surface
# --------------------------------------------------------------------------- #

#: Policy strings that grant egress without bounding a host set. USF v1 has no
#: spelling for any of them (`permissions.network` accepts only `allow`/`deny`),
#: which is exactly why they must still be read: they are what a *native*
#: manifest says before an AST10 port, and the port is where the property is
#: lost.
_ALLOW_ALL_POLICIES = frozenset({"allow-all", "allow_all", "allowall", "all", "any", "*", "unrestricted", "open"})

_RESTRICTIVE_POLICIES = frozenset({"deny-all", "deny_all", "denyall", "none", "off", "allow-list", "allow_list"})


def _network(pkg: dict) -> object:
    permissions = pkg.get("manifest", {}).get("permissions") or {}
    return permissions.get("network")


def _tools(pkg: dict) -> list[str]:
    permissions = pkg.get("manifest", {}).get("permissions") or {}
    return [t for t in (permissions.get("tools") or []) if isinstance(t, str)]


#: Tool names that imply the skill fetches. Mirrors validators/usf.py's own
#: `_NETWORK_CAPABLE_TOOLS` so "which tools reach the network" is decided in one
#: place for the validator and the detector alike.
_NETWORK_CAPABLE_TOOLS = frozenset({"web_fetch", "web_search", "fetch", "http_request", "http", "browser", "curl"})


def detect_unrestricted_network_fetch(pkg: dict) -> Finding:
    """Egress granted without any host set being bounded.

    Three shapes count, and a fourth deliberately does not. A bare boolean
    ``network: true`` counts -- it is the binary the whitepaper's "domain
    allowlists, not a binary ``network: true/false``" mitigation names. An
    allow-all policy string counts. A network block that declares neither an
    allowlist nor a restrictive policy, on a package that declares a
    network-capable tool, counts: it fetches and bounds nothing. An **empty**
    allowlist does not count -- USF v1 evaluates egress default-deny, so
    ``allow: []`` is no egress at all, and reading it as unrestricted would
    invert the policy.
    """
    network = _network(pkg)

    if network is True:
        return Finding(
            "AST05-unrestricted-network-fetch",
            True,
            "permissions.network is the bare boolean `true`: egress granted with no domain allowlist",
        )
    if not isinstance(network, dict):
        return Finding("AST05-unrestricted-network-fetch", False, f"no network block to widen (network={network!r})")

    policy = network.get("policy")
    if isinstance(policy, str) and policy.strip().lower() in _ALLOW_ALL_POLICIES:
        return Finding("AST05-unrestricted-network-fetch", True, f"network.policy={policy!r} bounds no host")

    if "allow" in network:
        return Finding(
            "AST05-unrestricted-network-fetch",
            False,
            f"egress bounded by an allowlist of {len(network.get('allow') or [])} host(s)",
        )
    if isinstance(policy, str) and policy.strip().lower() in _RESTRICTIVE_POLICIES:
        return Finding("AST05-unrestricted-network-fetch", False, f"network.policy={policy!r} is restrictive")

    fetching_tools = sorted(set(_tools(pkg)) & _NETWORK_CAPABLE_TOOLS)
    if fetching_tools:
        return Finding(
            "AST05-unrestricted-network-fetch",
            True,
            f"network-capable tool(s) {fetching_tools} declared with no allowlist and no policy",
        )
    return Finding("AST05-unrestricted-network-fetch", False, "network block declares no unbounded grant")


def _is_overly_broad_wildcard(entry: str) -> bool:
    """``*`` and bare-TLD wildcards. ``*.example.com`` bounds an organisation."""
    if entry == "*":
        return True
    if entry.startswith("*."):
        suffix = entry[2:]
        return suffix.count(".") < 1  # e.g. "*.com" -- a bare TLD wildcard, not a scoped subdomain
    return False


def detect_wildcard_domain_allowlist(pkg: dict) -> Finding:
    """An allowlist that is present but does not actually bound the host set.

    Distinct from ``unrestricted-network-fetch``, which fires when nothing is
    enumerated at all. Here the author wrote a list and the list happens to
    match everything -- ``"*"``, or a bare-TLD wildcard such as ``"*.com"``.
    ``validators/usf.py``'s ``host_errors`` rejects every wildcard under USF v1
    host-only matching; this check reports only the *over-broad* ones, because a
    scoped ``*.example.com`` reads wider than it grants without granting the
    internet.
    """
    network = _network(pkg)
    if not isinstance(network, dict):
        return Finding("AST05-wildcard-domain-allowlist", False, "no network block declares an allowlist")
    allow = [entry for entry in (network.get("allow") or []) if isinstance(entry, str)]
    if not allow:
        return Finding("AST05-wildcard-domain-allowlist", False, "no allowlist entries to over-broaden")
    broad = [entry for entry in allow if _is_overly_broad_wildcard(entry)]
    detected = bool(broad)
    evidence = f"overly broad allow-list entries: {broad}" if detected else f"allow-list scoped: {allow}"
    return Finding("AST05-wildcard-domain-allowlist", detected, evidence)


# --------------------------------------------------------------------------- #
# Fetched-content dataflow
# --------------------------------------------------------------------------- #

#: Receiver names whose `.get`/`.post`/... is an HTTP call rather than a dict
#: lookup. Restricting to these is what stops `pkg.get("manifest")` -- which
#: appears dozens of times in this repository's own detector modules -- from
#: being read as a network fetch.
_HTTP_ROOTS = frozenset({"requests", "httpx", "urllib", "urllib3", "aiohttp", "http", "session", "client"})
_HTTP_VERBS = frozenset({"get", "post", "put", "patch", "delete", "head", "options", "request", "send", "urlopen"})
#: Bare function calls that fetch, whatever they are imported from.
_BARE_FETCHERS = frozenset({"urlopen", "fetch", "web_fetch", "http_get", "urlretrieve", "get_url", "download_url"})

#: Attributes that carry a response's body. Reading one keeps the taint.
_BODY_ATTRS = frozenset({"text", "content", "body", "data", "raw", "json", "read", "decode", "iter_lines", "readlines"})

#: Names that are the agent's instruction channel. The whitepaper's control is
#: "maintain a clear separation between system prompts, user instructions, and
#: externally retrieved content"; these are the first two, and anything a skill
#: routes into them is instruction, not data.
#:
#: Deliberately narrow. An earlier draft also listed ``rules``, ``context``,
#: ``system`` and ``persona``, and it produced a false positive on this
#: category's own clean fixture ``fixtures/AST05/C4-eval-remote-response`` --
#: whose correct, data-only handler assigns ``rules = document.get("rules", [])``
#: after a ``json.loads``. Those four are ordinary variable names, not the model's
#: instruction channel, and including them made the check fire on well-written
#: code. The names kept below denote the channel itself and nothing else.
_INSTRUCTION_NAMES = frozenset(
    {
        "prompt",
        "prompts",
        "system_prompt",
        "systemprompt",
        "instruction",
        "instructions",
        "messages",
        "message_list",
        "directives",
        "preamble",
    }
)
_APPEND_ATTRS = frozenset({"append", "extend", "insert", "add", "update", "push"})
_INSTRUCTION_KWARGS = frozenset({"prompt", "system", "system_prompt", "instructions", "messages", "preamble"})

#: Wrappers that re-establish the instruction/data boundary before the value is
#: used. Naming one is the author declaring the control the whitepaper asks for.
_BOUNDARY_FNS = frozenset(
    {
        "quarantine",
        "tag",
        "tag_untrusted",
        "mark_untrusted",
        "as_data",
        "as_reference_data",
        "wrap_untrusted",
        "delimit",
        "fence",
        "sanitize",
        "sanitise",
        "escape",
        "provenance",
        "untrusted",
        "to_reference_data",
    }
)

#: A delimiter or provenance convention written into the text itself.
_BOUNDARY_MARKER = re.compile(
    r"(?i)(untrusted|reference[ _-]?data\b|do not follow (?:any )?instructions"
    r"|must not override|never as instructions?|treat(?:ed)? as data\b"
    r"|provenance|<\s*/?\s*(?:external|retrieved|fetched)[-_ ]?\w*\s*>)"
)

#: Executable sinks reached by a bare name call.
_BARE_EXEC_SINKS = frozenset({"eval", "exec", "compile", "__import__"})
#: Executable sinks reached by a dotted call.
_DOTTED_EXEC_SINKS = frozenset(
    {
        "os.system",
        "os.popen",
        "pickle.loads",
        "pickle.load",
        "marshal.loads",
        "yaml.unsafe_load",
        "dill.loads",
        "jsonpickle.decode",
    }
)
_SUBPROCESS_ROOTS = frozenset({"subprocess", "os"})
_SUBPROCESS_ATTRS = frozenset({"run", "call", "check_call", "check_output", "Popen", "system", "popen"})


def _is_remote_call(call: ast.Call) -> bool:
    if isinstance(call.func, ast.Name):
        return call.func.id in _BARE_FETCHERS
    name = pysource.call_name(call)
    if not name:
        return False
    if name.endswith(".urlopen") or name.endswith("request.urlopen"):
        return True
    return pysource.call_root(call) in _HTTP_ROOTS and pysource.call_attr(call) in _HTTP_VERBS


def _statements(node: ast.AST) -> Iterator[ast.stmt]:
    """Statements of one scope in source order, descending into compound bodies
    but NOT into nested function or class definitions (each gets its own pass)."""
    for child in getattr(node, "body", []):
        yield child
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        for attr in ("body", "orelse", "finalbody"):
            if hasattr(child, attr):
                yield from _statements_of_block(getattr(child, attr))
        for handler in getattr(child, "handlers", []):
            yield from _statements_of_block(handler.body)


def _statements_of_block(block: list) -> Iterator[ast.stmt]:
    for child in block or []:
        yield child
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        for attr in ("body", "orelse", "finalbody"):
            if hasattr(child, attr):
                yield from _statements_of_block(getattr(child, attr))
        for handler in getattr(child, "handlers", []):
            yield from _statements_of_block(handler.body)


def _scopes(tree: ast.Module) -> Iterator[ast.AST]:
    yield tree
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node


def _expression_is_tainted(node: ast.AST, tainted: set[str]) -> bool:
    for child in ast.walk(node):
        if isinstance(child, ast.Call) and _is_remote_call(child):
            return True
        if isinstance(child, ast.Name) and child.id in tainted:
            return True
    return False


def _is_boundaried(node: ast.AST) -> bool:
    """The value passes through a declared instruction/data boundary."""
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            attr = pysource.call_attr(child)
            if attr in _BOUNDARY_FNS:
                return True
        if isinstance(child, ast.Constant) and isinstance(child.value, str):
            if _BOUNDARY_MARKER.search(child.value):
                return True
    return False


def _target_names(target: ast.AST) -> list[str]:
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, ast.Attribute):
        return [target.attr]
    if isinstance(target, ast.Subscript):
        return _target_names(target.value)
    if isinstance(target, (ast.Tuple, ast.List)):
        out: list[str] = []
        for element in target.elts:
            out.extend(_target_names(element))
        return out
    return []


def _instruction_sink_hit(stmt: ast.stmt, tainted: set[str]) -> str | None:
    """Description of an instruction-channel sink this statement feeds, or None."""
    # `prompt += fetched`
    if isinstance(stmt, ast.AugAssign) and isinstance(stmt.op, ast.Add):
        names = _target_names(stmt.target)
        if any(n in _INSTRUCTION_NAMES for n in names) and _expression_is_tainted(stmt.value, tainted):
            if not _is_boundaried(stmt.value):
                return f"{names[0]} += <fetched content>"

    # `prompt = base + fetched` / `messages[-1] = fetched`
    if isinstance(stmt, ast.Assign) and _expression_is_tainted(stmt.value, tainted):
        for target in stmt.targets:
            names = _target_names(target)
            if any(n in _INSTRUCTION_NAMES for n in names) and not _is_boundaried(stmt.value):
                return f"{names[0]} = <fetched content>"

    # `prompt.append(fetched)` and `client.complete(prompt=fetched)`
    for node in ast.walk(stmt):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr in _APPEND_ATTRS:
            receiver = _target_names(func.value)
            if receiver and receiver[0] in _INSTRUCTION_NAMES:
                for arg in node.args:
                    if _expression_is_tainted(arg, tainted) and not _is_boundaried(arg):
                        return f"{receiver[0]}.{func.attr}(<fetched content>)"
        for kw in node.keywords:
            if kw.arg in _INSTRUCTION_KWARGS and _expression_is_tainted(kw.value, tainted):
                if not _is_boundaried(kw.value):
                    return f"{pysource.call_name(node) or 'call'}({kw.arg}=<fetched content>)"
    return None


def _executable_sink_hit(stmt: ast.stmt, tainted: set[str]) -> str | None:
    for node in ast.walk(stmt):
        if not isinstance(node, ast.Call):
            continue
        tainted_args = [a for a in node.args if _expression_is_tainted(a, tainted)]
        if not tainted_args:
            continue
        if isinstance(node.func, ast.Name) and node.func.id in _BARE_EXEC_SINKS:
            return f"{node.func.id}(<fetched content>)"
        name = pysource.call_name(node)
        if name in _DOTTED_EXEC_SINKS:
            return f"{name}(<fetched content>)"
        if name == "yaml.load" and not any(kw.arg == "Loader" for kw in node.keywords):
            return "yaml.load(<fetched content>) with no Loader"
        if (
            pysource.call_root(node) in _SUBPROCESS_ROOTS
            and pysource.call_attr(node) in _SUBPROCESS_ATTRS
            and (pysource.has_true_keyword(node, "shell") or pysource.call_attr(node) in {"system", "popen"})
        ):
            return f"{name}(<fetched content>, shell)"
    return None


def _scan_dataflow(pkg: dict) -> tuple[list[tuple[str, str]], list[tuple[str, str]], bool, list[str]]:
    """``(instruction_hits, executable_hits, fetches_anything, unparsed_paths)``.

    One forward pass per scope. A name assigned from a fetch (or from an
    attribute of one) is tainted; a name reassigned from anything else stops
    being tainted; a value that passes through a declared boundary wrapper is
    not reported.
    """
    instruction_hits: list[tuple[str, str]] = []
    executable_hits: list[tuple[str, str]] = []
    fetches = False
    unparsed: list[str] = []

    for path, source in sorted(pysource.python_files(pkg).items()):
        tree = pysource.parse(source)
        if tree is None:
            unparsed.append(path)
            continue
        if any(_is_remote_call(call) for call in pysource.iter_calls(tree)):
            fetches = True

        for scope in _scopes(tree):
            tainted: set[str] = set()
            for stmt in _statements(scope):
                hit = _instruction_sink_hit(stmt, tainted)
                if hit:
                    instruction_hits.append((path, hit))
                hit = _executable_sink_hit(stmt, tainted)
                if hit:
                    executable_hits.append((path, hit))

                if isinstance(stmt, (ast.Assign, ast.AnnAssign)):
                    value = stmt.value
                    if value is None:
                        continue
                    targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
                    names = [n for target in targets for n in _target_names(target)]
                    if _expression_is_tainted(value, tainted) and not _is_boundaried(value):
                        tainted.update(names)
                    else:
                        tainted.difference_update(names)
                elif isinstance(stmt, ast.AugAssign):
                    names = _target_names(stmt.target)
                    if _expression_is_tainted(stmt.value, tainted) and not _is_boundaried(stmt.value):
                        tainted.update(names)
                elif isinstance(stmt, ast.With):
                    for item in stmt.items:
                        if item.optional_vars is None:
                            continue
                        names = _target_names(item.optional_vars)
                        if _expression_is_tainted(item.context_expr, tainted):
                            tainted.update(names)
    return instruction_hits, executable_hits, fetches, unparsed


def detect_fetched_content_instruction_sink(pkg: dict) -> Finding:
    """Fetched bytes reach the instruction channel with no boundary.

    The whitepaper's control, verbatim: "Retrieved information should be used
    only as reference data and must not override or modify the agent's system or
    developer instructions." A value routed into a data structure named for
    reference data, or wrapped by a declared boundary function, is not reported.
    """
    instruction_hits, _executable, _fetches, unparsed = _scan_dataflow(pkg)
    if instruction_hits:
        path, hit = instruction_hits[0]
        return Finding(
            "AST05-fetched-content-instruction-sink",
            True,
            f"{path}: {hit} with no provenance tag or boundary delimiter",
        )
    note = f" (unparsed: {unparsed})" if unparsed else ""
    return Finding(
        "AST05-fetched-content-instruction-sink",
        False,
        f"no fetched value reaches the instruction channel unboundaried{note}",
    )


def detect_remote_response_executed(pkg: dict) -> Finding:
    """A network response body reaches an executable sink.

    ``json.loads(response.text)`` is deliberately not a sink: parsing a body as
    data is the correct handling, and calling it a finding would make the check
    fire on every well-written HTTP client in the corpus.
    """
    _instruction, executable_hits, _fetches, unparsed = _scan_dataflow(pkg)
    if executable_hits:
        path, hit = executable_hits[0]
        return Finding("AST05-remote-response-executed", True, f"{path}: {hit}")
    note = f" (unparsed: {unparsed})" if unparsed else ""
    return Finding("AST05-remote-response-executed", False, f"no fetched value reaches an executable sink{note}")


def _prose(pkg: dict) -> str:
    return "\n".join(text for path, text in sorted((pkg.get("files") or {}).items()) if path.endswith(".md"))


def detect_absent_instruction_boundary(pkg: dict) -> Finding:
    """A fetching package whose decision rules declare no instruction/data boundary.

    **Gated on ingestion.** A package with no fetch call site has no boundary to
    establish, and an ungated absence check would fire on every package in every
    corpus -- the exact non-discriminating shape this repository's detector
    review called out. The gate is a call-site fact, not a prose one, so the
    check cannot be talked into or out of firing by wording alone.
    """
    _instruction, _executable, fetches, _unparsed = _scan_dataflow(pkg)
    if not fetches:
        return Finding(
            "AST05-absent-instruction-boundary",
            False,
            "package declares no fetch call site, so there is no external-content hop to bound",
        )
    prose = _prose(pkg)
    match = _BOUNDARY_MARKER.search(prose)
    if match:
        return Finding(
            "AST05-absent-instruction-boundary",
            False,
            f"a boundary convention is declared in prose: {match.group(0)!r}",
        )
    return Finding(
        "AST05-absent-instruction-boundary",
        True,
        "package fetches external content but its prose declares no instruction-versus-data boundary convention",
    )


DETECTORS: dict[str, Callable[[dict], Finding]] = {
    "AST05-fetched-content-instruction-sink": detect_fetched_content_instruction_sink,
    "AST05-remote-response-executed": detect_remote_response_executed,
    "AST05-absent-instruction-boundary": detect_absent_instruction_boundary,
    "AST05-unrestricted-network-fetch": detect_unrestricted_network_fetch,
    "AST05-wildcard-domain-allowlist": detect_wildcard_domain_allowlist,
}


def run_all(pkg: dict) -> list[Finding]:
    return _run_all(DETECTORS, pkg)


def f1_report(fixtures: list[tuple[dict, set[str]]]) -> dict:
    """Always ``artifact-signal-only``. AST05 has no scenario-level F1 to publish."""
    return _f1_report(STATIC_DETECTABLE, DETECTORS, fixtures, F1_SCOPE)
