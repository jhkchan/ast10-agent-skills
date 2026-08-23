---
name: triage-finding
description: >-
  Route a free-text agent-skill security finding to exactly one primary OWASP AST01-AST10
  category by walking the whitepaper's own "Decision Tree: Which AST Does My Finding Belong
  To?", record every other match as a contributing control failure rather than splitting the
  finding, and return category-specific remediation guidance.
nl_triggers:
  - "which AST is this"
  - "triage this finding"
  - "what category does this belong to"
  - "is this AST01 or AST08"
  - "classify this skill security finding"
  - "the scanner missed an obfuscated instruction"
  - "overprivileged agent with write access to production secrets"
  - "route this to the right OWASP agentic skills category"
  - "primary root cause vs contributing control failure"
  - "I have a finding but no category"
routes_to: advisory
---

# /ast:triage-finding

Activates the `advisory` skill (`skills/advisory/`) — the orchestration layer above the ten
per-category detector skills. It is **not** an eleventh detector: it never scans a package,
it names the category for a finding somebody (or something) already raised.

## The tree it walks

The whitepaper gives four numbered branches plus an overlap rule, and the advisory skill
runs them in that order:

1. Is the skill itself malicious at publish time — hidden payload, credential theft,
   backdoor? → **AST01** Malicious Skills.
2. Is the finding about how the skill *reached* the registry or pipeline — typosquatting,
   missing signatures, weak publisher vetting, a compromised publisher account? →
   **AST02** Supply Chain Compromise.
3. Is the finding in the SKILL.md/manifest metadata itself — a deceptive description,
   understated permissions, a spoofed `risk_tier`, unsafe deserialization of frontmatter? →
   **AST04** Insecure Metadata.
4. Did a scanner or reviewer control fail to catch something it should have — natural-
   language bypass, obfuscated instructions, scanner impersonation? → **AST08** Poor
   Scanning.
5. If more than one branch applies, record the **primary root cause** as the origin AST and
   every other match as a **contributing control failure**. Never split one finding across
   two categories.

`skills/advisory/scripts/triage.py` extends the same tree — same one-primary-root-cause
discipline — to the six categories the whitepaper's tree does not enumerate (AST03, AST05,
AST06, AST07, AST09, AST10), keyed to each category's own Description and Attack-Scenarios
language rather than a generic industry restatement.

**Why branch 5 is the load-bearing rule.** Most real findings match two or three branches.
A malicious skill that a scanner also missed is one AST01 finding with an AST08 contributing
failure — filing it twice inflates the category counts and loses the causal ordering that
tells you which control to fix first.

## Arguments

| Position | Argument | Required | Meaning |
| --- | --- | --- | --- |
| `$ARGUMENTS` | `<finding text>` | yes | The finding in plain language. A sentence is enough; a paste of a scanner row, ticket body, or incident note also works. Quote it if it contains shell metacharacters. |
| `$ARGUMENTS` | `--json` | no | Return the raw routing dict (`ast_id`, `category`, `guidance`, `reasoning`, `contributing`) instead of the formatted block. |
| `$ARGUMENTS` | `--explain` | no | Also print which phrase in the finding matched which rule, for auditing a routing you disagree with. |

The routing is phrase-matched against whitepaper terminology, so the finding's *wording*
matters. "Broad access to secrets" routes; "it can do too much" does not.

## Example invocation

```text
/ast:triage-finding a skill shipped a hidden payload and the obfuscated instruction slipped past the scanner
```

Equivalent deterministic run:

```bash
python3 skills/advisory/scripts/triage.py \
  "a skill shipped a hidden payload and the obfuscated instruction slipped past the scanner"
```

## Output

```json
{
  "ast_id": "AST01",
  "category": "Malicious Skills",
  "guidance": "AST01 — Malicious Skills. Treat this as a publish-time compromise: quarantine the skill, revoke any credentials it could have reached, and require cryptographic signatures (ed25519) bound to a resolvable, revocable publisher identity before trusting further skills from that publisher.",
  "reasoning": "Routed to AST01 (Malicious Skills) as the primary root cause per the decision tree's rule order; 2 total rule(s) matched.",
  "contributing": [
    "AST08"
  ]
}
```

Rendered by the command as:

```text
FINDING:      a skill shipped a hidden payload and the obfuscated instruction
              slipped past the scanner
PRIMARY:      AST01 - Malicious Skills
CONTRIBUTING: AST08 (Poor Scanning) - recorded as a control failure, not a
              second finding
REASONING:    Routed to AST01 as the primary root cause per the decision tree's
              rule order; 2 total rule(s) matched.
GUIDANCE:     Treat this as a publish-time compromise: quarantine the skill,
              revoke any credentials it could have reached, and require
              cryptographic signatures (ed25519) bound to a resolvable,
              revocable publisher identity before trusting further skills from
              that publisher.
NEXT:         /ast:audit-ast01 <package-path>
```

### When nothing matches

```json
{
  "ast_id": null,
  "category": null,
  "guidance": "No decision-tree branch matched this finding; escalate for manual triage rather than guessing a category.",
  "reasoning": "No whitepaper-grounded phrase from any AST01-AST10 rule matched the finding text.",
  "contributing": []
}
```

A null route is a real answer. The advisory skill will not invent a category to avoid
returning one, because a mis-filed finding is worse than an unfiled one.

## Scoring note

This skill is judged on guidance relevance and reasoning quality only. It never contributes
to any category's F1 denominator the way the ten detector skills do, and it publishes no
detection-accuracy number.

## Related

- `/ast:audit-ast01` … `/ast:audit-ast10` — once the category is named, audit the package
  against it.
- `/ast:audit-skill-package` — when you have a package but no finding yet.
- `/ast:check-coverage <ASTnn>` — when the route lands on a category and you need to know
  whether this repo can actually decide it from the artifact.
