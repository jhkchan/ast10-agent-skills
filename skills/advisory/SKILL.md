---
name: advisory
description: Routes a free-text agent-skill security finding to its primary OWASP Agentic Skills Top 10 (AST01-AST10) category using the whitepaper's own "Which AST Does My Finding Belong To?" decision tree, and returns actionable, category-specific remediation guidance.
permissions:
  network: false
  shell: false
  write: false
risk_tier: L0
---

# Advisory / Orchestrator Triage Skill

## What this is

A human or upstream detector hands this skill a finding written in plain
language — "overprivileged agent with write access to production secrets,"
"the scanner missed an obfuscated instruction" — and it names the primary
AST category the finding belongs to, plus a short, actionable remediation
recommendation. It is the orchestration layer that sits above the ten
per-category AST detector skills, not an eleventh detector: it never scans
a skill package itself, it triages a finding someone (or something) already
raised.

## Decision tree (the whitepaper's own)

The source document's "Classifying and Triaging Findings" section gives an
explicit four-branch tree for the categories that overlap most often in
practice, plus a fifth rule for resolving overlap:

1. Is the skill itself malicious at publish time (hidden payload, credential
   theft, backdoor)? → **AST01** (Malicious Skills).
2. Is the finding about how the skill *reached* the registry or pipeline —
   typosquatting, missing signatures, weak publisher vetting, a compromised
   publisher account? → **AST02** (Supply Chain / Registry Trust).
3. Is the finding in the SKILL.md/manifest metadata itself — a deceptive
   description, understated permissions, a spoofed `risk_tier`, or unsafe
   deserialization of frontmatter? → **AST04** (Insecure Metadata).
4. Did a scanner or reviewer control fail to catch a malicious or
   misdeclared skill it should have caught — natural-language bypass,
   obfuscated instructions, scanner impersonation? → **AST08** (Poor
   Scanning).
5. If more than one branch applies (e.g. a malicious skill that also evaded
   a scanner), record the **primary root cause** as the origin AST and the
   other match as a **contributing control failure** — never split one
   finding across two categories.

`scripts/triage.py` extends the same tree — same "one primary root cause,
others recorded as contributing" discipline — to the remaining six
categories, each keyed to that category's own Description/Attack-Scenarios
language rather than a generic industry restatement:

| Signal in the finding | AST |
| --- | --- |
| Broader permissions/access than the stated function needs; write access reaching secrets or admin scope | **AST03** Over-Privileged Skills |
| A referenced external URL/document (not the skill package) was rug-pulled, poisoned, or bait-and-switched | **AST05** Untrusted External Instructions |
| Skill ran with full host file-system/shell/network access, no sandbox | **AST06** Weak Isolation |
| A stale, un-pinned, rolled-back, or hot-reloaded version was the vector | **AST07** Update Drift |
| No inventory, approval workflow, audit trail, or deprovisioning process | **AST09** No Governance |
| Security properties (manifest, signature, `risk_tier`) were lost porting the skill to another platform | **AST10** Cross-Platform Reuse |

## What this skill does NOT do

- It does not run static or agent-judged detection against a skill package —
  that is the ten AST01–AST10 detector skills' job.
- It does not replace human review of an ambiguous finding: an unmatched
  finding is returned with `ast_id: null` and a request for manual triage,
  never a guessed category.
- It does not contribute to any category's Gate B F1 denominator. Per
  spec.md S-002, this skill is scored by the judge matrix on **guidance
  relevance and reasoning quality** — whether the routed AST and the
  recommendation make sense — not on whether it "detected" the finding's
  true root cause. Its pooled verdict is reported in its own section of the
  release report, separate from the ten detectors' F1 breakdown.

## Mechanism

All routing logic lives in `scripts/triage.py` — a single ordered rule list
of `(ast_id, category, whitepaper-grounded phrases, guidance)` tuples,
evaluated in the tree's priority order above. No mechanism lives in this
file; this file is knowledge (the decision rules and their whitepaper
grounding), the script is the implementation.

```python
from triage import triage

triage("overprivileged agent with write access to production secrets")
# {
#   "ast_id": "AST03",
#   "category": "Over-Privileged Skills",
#   "guidance": "AST03 — Over-Privileged Skills. Recommend rotating ...",
#   "reasoning": "Routed to AST03 (Over-Privileged Skills) as the primary ...",
#   "contributing": [],
# }
```

Run directly as a CLI: `python3 scripts/triage.py "<finding text>"` prints
the same result as JSON.
