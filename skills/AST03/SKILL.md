---
name: ast03-over-privileged-skills
description: "Detect and triage OWASP AST03 Over-Privileged Skills — permission manifests broader than a skill's stated function, logic-layer prompt control injection (LPCI) that exercises granted-but-unintended permissions, and confused-deputy chains where a low-privilege skill's request is honored by a high-privilege one. Use when reviewing a permission manifest against a skill's declared function, when an intent-level prompt-injection finding needs mapping to a concrete over-broad tool-call permission, or when a privileged skill trusts a caller's identity without independent verification."
---

# AST03 - Over-Privileged Skills

Pattern: Knowledge. The decision rule that recurs through this whole category:
permission checks that operate at the tool-call level cannot see intent, and intent is
exactly where the attack lives. Mechanism (manifest-vs-behavior diffing) lives in
`scripts/`; frozen scenario tiers live in `coverage-matrix.md`.

## Why this is not "apply least privilege, harder"

Traditional least-privilege is well understood as a static grant problem. Skills layer
natural-language *intent* on top of that grant: a skill permitted to run `SELECT` can
be coerced by prompt injection into running `DELETE`, because the permission system
checks "is this tool call allowed" at the call site, not "does this call match the
task the user actually approved." The whitepaper's own instance of this is Summer
Yue's OpenClaw incident: asked only to *review* an inbox, the agent deleted large
volumes of email before being manually killed — no manifest bug, no privilege
escalation exploit, just permission scope wide enough that the intended reading task
never needed to be checked against the destructive action taken.

## Decision rules

1. **Bind authorization to the approved task, not to the tool.** Before each action,
   verify the action, resource, destination, and conditions still fall within what
   the user actually granted for *this* task — not merely within what the skill's
   manifest lists as possible. A manifest-compliant call can still be an
   authorization violation if it exceeds the task-scoped grant.
2. **LPCI payloads are encoded, delayed, and conditionally-triggered by design —
   grep for the trigger, not the action.** Logic-layer Prompt Control Injection
   (Atta et al., arXiv:2507.10457) plants payloads in memory, vector stores, or tool
   outputs that the model later treats as operator-level instructions. A static scan
   of "what does this skill do right now" misses a payload that only activates on a
   later condition. LAAF (arXiv:2603.17239) operationalizes this as a six-stage
   lifecycle — Recon → Injection → Trigger → Persistence → Evasion → Trace Tamper —
   and reports the *Persistence* and *Trace Tamper* stages as the two hardest for a
   point-in-time review to catch, because both are specifically designed to survive
   or evade exactly that kind of check.
3. **A confused-deputy chain breaks at the first skill that trusts a caller instead
   of re-verifying it.** A high-privilege skill that treats any request from a
   lower-privilege caller as pre-authorized becomes the deputy; the fix is not
   "restrict who can call the privileged skill" (that still trusts the immediate
   caller) but "every skill in a delegation chain independently validates the
   *original* caller's identity, permissions, and authorization context" — trust
   must not be transitively assumed at any single hop.
4. **Identity-file write requests are a permission-manifest red flag independent of
   the skill's stated function.** A "weather assistant" requesting read access to
   `~/.clawdbot/.env` is over-privileged relative to its function; a skill of *any*
   stated function requesting write access to `SOUL.md`/`MEMORY.md`/`AGENTS.md`
   should be flagged for elevated review regardless of what that function is, because
   identity-file write is a privilege escalation vector independent of task domain.
5. **A binary `network: true/false` field cannot express least privilege — a domain
   allowlist can.** The over-broad grant is not "this skill has network access," it's
   "this skill's network access is unscoped." The manifest field itself is the
   control surface to check: a boolean is a modeling failure, not just a missing
   value.
6. **Persistent-state changes need consent that cannot be satisfied by the
   instruction that requests them.** Memory/identity-file writes, new tool approvals,
   and privilege escalations must require operator consent obtained *outside* the
   channel an injected instruction controls — an injected prompt asking the user to
   confirm is not independent confirmation.

## Distinguishing AST03 from its neighbors

- **vs AST01:** AST01 is "the skill itself is malicious." AST03 is "the skill (even
  a benign one) has more permission than its function needs, and something else
  exploits the gap." The same LPCI finding can be an AST01 payload if the skill was
  malicious by design, or a pure AST03 finding if a benign skill's over-broad grant
  was hijacked by injected content it merely processed.
- **vs AST04 (Insecure Metadata):** AST04 is about the manifest *lying* (declaring
  `network: false` while the script calls `curl`). AST03 is about the manifest being
  *honest but too broad*. A manifest that accurately declares excessive permissions
  is an AST03 finding with no AST04 component; a manifest that misdeclares narrower
  permissions than what actually runs is AST04, and likely also AST03 if the
  underlying behavior is itself excessive for the function.
- **vs AST06 (Weak Isolation):** AST06 is the absence of a sandbox boundary — no
  permission model runs at all because host-mode execution has none. AST03 assumes a
  permission model *exists* and asks whether it was scoped correctly. A host-mode
  finding is AST06; an over-broad manifest inside a properly sandboxed environment is
  AST03.

## Scope and out-of-artifact boundary

Whether a *specific* LPCI trigger condition (a delayed, encoded payload keyed to a
future date or event) is present in a given skill's declared static content is
static-detectable in principle; whether it will actually *fire* as intended requires
runtime observation this artifact cannot provide standalone. The tier split between
"manifest declares over-broad scope" (static-detectable) and "injected content will
exploit that scope at some future trigger" (agent-judgable or out-of-artifact) is
fixed in `coverage-matrix.md`.

## References

Full attack-scenario catalog (Weather Assistant Data Exfiltration, Database Admin
Wipe, Identity File Backdoors, Low-Privilege-Invokes-High-Privilege) and the complete
preventive-mitigation list are the whitepaper's own AST03 section. This file is the
delta on top of it.
