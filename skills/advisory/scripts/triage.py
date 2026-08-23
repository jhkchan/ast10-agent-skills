"""Routing engine for the advisory/orchestrator triage skill.

Implements the whitepaper's own "Decision Tree: Which AST Does My Finding
Belong To?" (OWASP Agentic Skills Top 10, "Classifying and Triaging
Findings"):

  1. Is the skill itself malicious at publish time (hidden payload,
     credential theft, backdoor)?                                -> AST01
  2. Is the finding about how the skill reached the registry or pipeline -
     typosquatting, missing signatures, weak publisher vetting, a
     compromised publisher account?                               -> AST02
  3. Is the finding in the SKILL.md/manifest metadata itself - a deceptive
     description, understated permissions, spoofed risk_tier, or unsafe
     deserialization of frontmatter?                               -> AST04
  4. Did a scanner or reviewer control fail to catch a malicious or
     misdeclared skill it should have caught - natural-language bypass,
     obfuscated instructions, scanner impersonation?               -> AST08
  5. If more than one applies (e.g. a malicious skill that also evaded a
     scanner), record the primary root cause as the origin AST and the
     other match as a contributing control failure, never split the
     finding across categories.

Those four numbered branches are the whitepaper's own literal tree. This
module extends the same tree, in the same "record one primary root cause"
style, to route the remaining six categories using each category's own
Description / Attack Scenarios language from the source document rather than
a generic restatement:

  AST03 Over-Privileged Skills, AST05 Untrusted External Instructions,
  AST06 Weak Isolation, AST07 Update Drift, AST09 No Governance,
  AST10 Cross-Platform Reuse.

Scoring contract (spec.md S-002): this skill is judged on guidance
relevance and reasoning quality, never on detection accuracy, and never
contributes to a Gate B F1 denominator the way the ten AST detector skills
do.
"""

F1_ELIGIBLE = False  # advisory skill: guidance-quality judged only (S-002)

# (ast_id, category_name, phrases, guidance)
# `phrases` are lower-cased substrings drawn from the whitepaper's own
# terminology for that category, kept specific enough not to collide across
# categories (e.g. AST04 uses "manifest metadata" rather than bare
# "manifest", which AST03's permission-manifest language also uses).
#
# Rule order below is the routing priority: whitepaper-tree order first
# (AST01 -> AST02 -> AST04 -> AST08, branches 1-4), then the six extended
# categories in numeric order. The first rule whose phrase matches wins as
# the PRIMARY root cause (decision-tree branch 5); any further rule that
# also matches is recorded as a contributing control failure, never a
# second primary.
_RULES = [
    (
        "AST01",
        "Malicious Skills",
        (
            "hidden payload",
            "credential theft",
            "credential stealer",
            "malicious skill",
            "malicious at publish",
            "reverse shell",
            "c2 server",
            "trojan",
        ),
        (
            "AST01 — Malicious Skills. Treat this as a publish-time "
            "compromise: quarantine the skill, revoke any credentials it "
            "could have reached, and require cryptographic signatures "
            "(ed25519) bound to a resolvable, revocable publisher identity "
            "before trusting further skills from that publisher."
        ),
    ),
    (
        "AST02",
        "Supply Chain / Registry Trust",
        (
            "typosquat",
            "registry",
            "publisher account",
            "maintainer account",
            "missing signature",
            "no code signature",
            "unsigned",
            "weak vetting",
            "dependency confusion",
            "supply chain",
            "compromised publisher",
        ),
        (
            "AST02 — Supply Chain / Registry Trust. Root cause is the "
            "distribution path, not the skill's own code: require "
            "provenance tracking (a signature over a canonical digest of "
            "SKILL.md plus every declared resource file), pin dependency "
            "versions, and require transparency-log entries for publish, "
            "update, and delete on the registry."
        ),
    ),
    (
        "AST04",
        "Insecure Metadata",
        (
            "manifest metadata",
            "deceptive description",
            "understated permission",
            "spoofed risk_tier",
            "risk tier spoofing",
            "unsafe deserialization",
            "yaml injection",
            "json injection",
            "toml injection",
            "frontmatter",
            "brand impersonation",
        ),
        (
            "AST04 — Insecure Metadata. Root cause is the SKILL.md/"
            "manifest declaration itself: validate declared fields against "
            "observed runtime behavior in sandboxed testing, reject unsafe "
            "frontmatter deserialization (legacy yaml.UnsafeLoader-style "
            "parsing), and flag mismatches between declared and actual "
            "permissions or risk_tier before install."
        ),
    ),
    (
        "AST08",
        "Poor Scanning",
        (
            "scanner",
            "scanning",
            "reviewer control",
            "evaded scan",
            "obfuscated instruction",
            "natural-language bypass",
            "scanner impersonation",
            "bypassed the scanner",
        ),
        (
            "AST08 — Poor Scanning. The gap is in detection, not in "
            "the skill's declared metadata: pattern-matching/regex "
            "scanners cannot catch natural-language-only malicious intent, "
            "so pair deterministic checks with semantic/behavioral "
            "analysis, and canonicalize (decode, normalize Unicode) "
            "content before matching."
        ),
    ),
    (
        "AST03",
        "Over-Privileged Skills",
        (
            "overprivileged",
            "over-privileged",
            "over privileged",
            "excessive permission",
            "excessive access",
            "broader permission",
            "broader access",
            "write access",
            "admin credential",
            "least privilege",
            "blast radius",
            "scoped credential",
        ),
        (
            "AST03 — Over-Privileged Skills. Recommend rotating any "
            "credentials or secrets the skill could reach, then "
            "restricting the skill's permissions to read-only (or the "
            "minimum scope its stated function actually requires) instead "
            "of the broad access it was granted; require a declared "
            "permission manifest, enforce it at runtime rather than only "
            "declaratively, and bind authorization to the task the user "
            "approved."
        ),
    ),
    (
        "AST05",
        "Untrusted External Instructions",
        (
            "external url",
            "external document",
            "external instructions",
            "rug-pull",
            "rug pull",
            "fetched content",
            "remote file",
            "external reference",
            "bait-and-switch",
            "referenced documentation",
        ),
        (
            "AST05 — Untrusted External Instructions. The skill "
            "package itself may be clean; the risk is in what it fetches "
            "at runtime: hash- or version-pin every referenced external "
            "document, treat fetched content as untrusted data rather than "
            "instructions, and re-validate the reference on every run "
            "rather than only at initial review."
        ),
    ),
    (
        "AST06",
        "Weak Isolation",
        (
            "sandbox",
            "isolation",
            "host access",
            "full file system access",
            "shell access",
            "host escape",
            "network pivot",
            "co-located service",
        ),
        (
            "AST06 — Weak Isolation. This is a property of the "
            "execution environment, not of the skill's content: run "
            "skills in a sandboxed/containerized context rather than the "
            "host session, and remove default full file-system, shell, "
            "and unrestricted network egress."
        ),
    ),
    (
        "AST07",
        "Update Drift",
        (
            "rollback attack",
            "hot-reload",
            "hot reload",
            "auto-update",
            "auto-updating",
            "stale version",
            "outdated skill",
            "never patched",
            "drifted from the pinned version",
            "update drift",
        ),
        (
            "AST07 — Update Drift. Pin the installed skill to an "
            "immutable content hash (sha256:) rather than a version range, "
            "require signature verification on every update, and require "
            "human-in-the-loop approval for updates in production/"
            "enterprise environments."
        ),
    ),
    (
        "AST09",
        "No Governance",
        (
            "no inventory",
            "approval workflow",
            "shadow ai",
            "audit trail",
            "orphaned skill",
            "deprovision",
            "no soc visibility",
            "regulatory exposure",
            "compliance reporting",
        ),
        (
            "AST09 — No Governance. This is an organizational-process "
            "gap rather than an artifact defect: stand up a skill "
            "inventory with an approval workflow and a revocation/"
            "deprovisioning process, and require an audit trail sufficient "
            "for compliance reporting."
        ),
    ),
    (
        "AST10",
        "Cross-Platform Reuse",
        (
            "cross-platform",
            "ported to another platform",
            "porting",
            "platform translation",
            "manifest was stripped",
            "manifest stripping",
            "cross registry",
            "multi-platform",
        ),
        (
            "AST10 — Cross-Platform Reuse. Security properties "
            "encoded in one platform's manifest format do not survive "
            "translation to another: re-validate (don't assume) "
            "permission manifests, signatures, and risk_tier declarations "
            "whenever a skill is ported to a new host platform."
        ),
    ),
]

_NO_MATCH_GUIDANCE = (
    "No decision-tree branch matched this finding; escalate for manual triage rather than guessing a category."
)

# The four branches the whitepaper's own tree numbers, with the question each
# one asks. Everything else is an extended rule in the same style, derived
# from that category's Description / Attack Scenarios language rather than
# from a numbered branch -- the distinction is recorded, never blurred, so a
# reader can tell a literal branch from an extension of the tree.
TREE_BRANCHES: dict[str, tuple[int, str]] = {
    "AST01": (1, "the skill itself is malicious at publish time"),
    "AST02": (2, "how the skill reached the registry or pipeline"),
    "AST04": (3, "the SKILL.md / manifest metadata itself"),
    "AST08": (4, "a scanner or reviewer control failed"),
}

RULE_COUNT = len(_RULES)


def matched_rules(finding: str) -> list[dict]:
    """Every rule that matched, in decision-tree order, with its matched phrase.

    Element 0 is the primary root cause; the rest are contributing control
    failures (branch 5), never a second primary -- the same ordering
    :func:`triage` reports, from the same single pass, so the two can never
    disagree.

    Exposed because a routing decision has to be auditable, not merely
    correct: a caller (cli/bin/cli.js `route`) can print WHICH rule fired and
    on WHICH phrase, instead of asking the reader to trust a category label.
    """
    text = finding.lower()
    matches: list[dict] = []
    for order, (ast_id, category, phrases, guidance) in enumerate(_RULES, start=1):
        hit = next((phrase for phrase in phrases if phrase in text), None)
        if hit is None:
            continue
        branch, question = TREE_BRANCHES.get(ast_id, (None, None))
        matches.append(
            {
                "ast_id": ast_id,
                "category": category,
                "matched_phrase": hit,
                "rule_order": order,
                "branch": branch,
                "basis": question or f"extended rule — {category}'s own whitepaper category language",
                "guidance": guidance,
            }
        )
    return matches


def triage(finding: str) -> dict:
    """Route a free-text finding to its primary AST category.

    Returns a dict with `ast_id`, `category`, `guidance`, `reasoning`, and
    `contributing` (AST ids of other matched categories, per decision-tree
    branch 5 - recorded as contributing control failures, never split into
    a second primary).
    """
    matches = matched_rules(finding)

    if not matches:
        return {
            "ast_id": None,
            "category": None,
            "guidance": _NO_MATCH_GUIDANCE,
            "reasoning": ("No whitepaper-grounded phrase from any AST01-AST10 rule matched the finding text."),
            "contributing": [],
            "matched_phrase": None,
            "branch": None,
        }

    primary = matches[0]
    primary_ast = primary["ast_id"]
    primary_category = primary["category"]

    return {
        "ast_id": primary_ast,
        "category": primary_category,
        "guidance": primary["guidance"],
        "reasoning": (
            f"Routed to {primary_ast} ({primary_category}) as the primary "
            "root cause per the decision tree's rule order; "
            f"{len(matches)} total rule(s) matched."
        ),
        "contributing": [match["ast_id"] for match in matches[1:]],
        # Why it routed here, not just where -- the phrase that fired and the
        # whitepaper branch it belongs to (None for the six extended rules).
        "matched_phrase": primary["matched_phrase"],
        "branch": primary["branch"],
    }


if __name__ == "__main__":
    import json
    import sys

    finding_text = " ".join(sys.argv[1:]) or sys.stdin.read()
    print(json.dumps(triage(finding_text), indent=2))
