"""detectors/pysource.py -- call-site analysis over a package's bundled Python.

Shared by the AST05 and AST06 detectors. Both need the same primitive: find the
*call sites* in a bundled script and read the literal text that flows into them.

Why the parse and not a regex. A substring scan for ``os.system`` or
``requests.get`` matches four things that are not call sites -- a name in a
docstring, an entry in a detector's own pattern table, a fixture literal inside a
test module, and a comment. Three of those four occur in this repository, so a
regex-based version of these checks would fire on the very modules that
implement them (``scripts/dogfood.py`` runs every detector over every shipped
skill, including ``skills/*/scripts/detector.py``). Parsing to an AST and
matching only ``ast.Call`` nodes removes that entire class of self-match without
a single suppression entry: a string constant sitting in a ``frozenset`` literal
is not a call, and the parser knows it.

Nothing here executes the source. ``ast.parse`` builds a tree and stops.
"""

from __future__ import annotations

import ast
from typing import Iterator

#: Files this module will attempt to parse. Anything else is skipped rather
#: than scanned as text, so a check grounded in call sites never degrades into
#: a keyword grep on a file it could not parse.
PY_SUFFIXES = (".py",)


def python_files(pkg: dict) -> dict[str, str]:
    """The package's bundled Python sources, ``{path: text}``."""
    return {path: text for path, text in (pkg.get("files") or {}).items() if path.endswith(PY_SUFFIXES)}


def parse(source: str) -> ast.Module | None:
    """Parse, or ``None`` when the source does not compile.

    A file that does not parse is reported as *not analysed* by the callers
    rather than as clean; see each detector's evidence string.
    """
    try:
        return ast.parse(source)
    except (SyntaxError, ValueError):
        return None


def dotted_name(node: ast.AST) -> str:
    """``os.path.join`` for an Attribute/Name chain, ``""`` for anything else."""
    parts: list[str] = []
    current: ast.AST | None = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
    elif isinstance(current, ast.Call):
        # e.g. Path("~/.zshrc").expanduser().write_text(...) -- keep the tail.
        parts.append("()")
    else:
        return ""
    return ".".join(reversed(parts))


def call_name(call: ast.Call) -> str:
    """The dotted callee of a Call node (``subprocess.run``, ``eval``, ...)."""
    return dotted_name(call.func)


def call_root(call: ast.Call) -> str:
    """The leftmost Name of the callee chain (``subprocess`` for ``subprocess.run``)."""
    name = call_name(call)
    return name.split(".", 1)[0] if name else ""


def call_attr(call: ast.Call) -> str:
    """The final attribute of the callee chain (``run`` for ``subprocess.run``)."""
    name = call_name(call)
    return name.rsplit(".", 1)[-1] if name else ""


def iter_calls(tree: ast.AST) -> Iterator[ast.Call]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            yield node


def module_string_constants(tree: ast.AST) -> dict[str, str]:
    """``{name: value}`` for every ``name = "literal"`` assignment in the tree.

    Deliberately flow-insensitive and last-write-wins: this exists so a command
    built as ``CMD = "crontab -"`` then passed as ``os.system(CMD)`` is still
    readable at the call site. It is a convenience for reading literals, never a
    substitute for the call-site match itself.
    """
    out: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        value = node.value
        if value is None:
            continue
        text = _joined_literal(value, out)
        if text is None:
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            if isinstance(target, ast.Name):
                out[target.id] = text
    return out


def _joined_literal(node: ast.AST, consts: dict[str, str]) -> str | None:
    """A single string for a literal-ish expression, or ``None``.

    Handles string constants, f-strings (constant parts joined, interpolations
    rendered as ``{}``), ``+`` concatenation, ``os.path.join(...)``,
    ``"/".join([...])``, and ``Name`` lookups into ``consts``.
    """
    if isinstance(node, ast.Constant):
        return node.value if isinstance(node.value, str) else None
    if isinstance(node, ast.Name):
        return consts.get(node.id)
    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
            else:
                parts.append("{}")
        return "".join(parts)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _joined_literal(node.left, consts)
        right = _joined_literal(node.right, consts)
        if left is None and right is None:
            return None
        return (left or "{}") + (right or "{}")
    if isinstance(node, ast.Call):
        name = call_name(node)
        if name.endswith("path.join") or name.endswith(".joinpath"):
            parts = [_joined_literal(a, consts) or "{}" for a in node.args]
            return "/".join(parts)
        if name.endswith(".join") and node.args:
            sep = _joined_literal(node.func.value, consts) if isinstance(node.func, ast.Attribute) else None
            items = node.args[0]
            if isinstance(items, (ast.List, ast.Tuple)):
                parts = [_joined_literal(e, consts) or "{}" for e in items.elts]
                return (sep if sep is not None else "").join(parts)
        # Path("~/.zshrc").expanduser() and friends: keep the innermost literal.
        for arg in node.args:
            text = _joined_literal(arg, consts)
            if text is not None:
                return text
    return None


def literal_strings(node: ast.AST, consts: dict[str, str] | None = None) -> list[str]:
    """Every string the expression can be read as, outermost form first.

    Returns both the joined rendering (so ``"sudo cp x " + DEST`` is seen as one
    command) and each individual constant, so a check can match on either.
    """
    consts = consts or {}
    out: list[str] = []
    joined = _joined_literal(node, consts)
    if joined:
        out.append(joined)
    for child in ast.walk(node):
        if isinstance(child, ast.Constant) and isinstance(child.value, str) and child.value:
            out.append(child.value)
        elif isinstance(child, ast.Name) and child.id in consts:
            out.append(consts[child.id])
    seen: set[str] = set()
    unique: list[str] = []
    for text in out:
        if text not in seen:
            seen.add(text)
            unique.append(text)
    return unique


def call_argument_strings(call: ast.Call, consts: dict[str, str] | None = None) -> list[str]:
    """Every literal string reachable from a call's positional and keyword args."""
    out: list[str] = []
    for arg in list(call.args) + [kw.value for kw in call.keywords]:
        out.extend(literal_strings(arg, consts))
    seen: set[str] = set()
    unique: list[str] = []
    for text in out:
        if text not in seen:
            seen.add(text)
            unique.append(text)
    return unique


def has_true_keyword(call: ast.Call, name: str) -> bool:
    """``f(..., shell=True)``."""
    for kw in call.keywords:
        if kw.arg == name and isinstance(kw.value, ast.Constant) and kw.value.value is True:
            return True
    return False
