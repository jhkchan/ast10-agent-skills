---
name: ast03-over-privileged-skills
description: "Detect and triage OWASP AST03 Over-Privileged Skills — permission manifests broader than a skill's stated function, logic-layer prompt control injection (LPCI) that exercises granted-but-unintended permissions, and confused-deputy chains where a low-privilege skill's request is honored by a high-privilege one. Use when reviewing a permission manifest against a skill's declared function, when an intent-level prompt-injection finding needs mapping to a concrete over-broad tool-call permission, or when a privileged skill trusts a caller's identity without independent verification."
---

# AST03 - Over-Privileged Skills

Pattern: Knowledge. Read the orientation block, take a route, then descend only as far as
the route sends you. Mechanism (manifest-vs-behavior diffing) lives in
`scripts/detector.py`; frozen scenario tiers live in `coverage-matrix.md`.

## Orientation — read this much, then decide whether to read the rest

- **Fires when** a permission *grant* is the object under review: a manifest read against
  a stated function, a write scope that is the precondition for a later injection, or a
  privileged skill that trusts its caller instead of re-verifying it.
- **Decides** exactly one scenario — `AST03-S03` Identity File Backdoors, a declared write
  reaching `SOUL.md`/`MEMORY.md`/`AGENTS.md` that `deny_write` does not shadow. The other
  three checks are `artifact-signal-only` or `category-precondition` in the module's own
  `CHECK_COVERAGE`; reading them as coverage is the overclaim the tier lock exists to stop.
- **Never decides** whether a grant is broad *for this skill's function*, or whether an
  injected instruction will later exercise it. Grants are in the manifest; exercises happen
  in a runtime this package never sees.
- **Stop now** if the route below sends you elsewhere. The recurring rule underneath this
  whole category — permission checks at the tool-call level cannot see intent, and intent
  is where the attack lives — is also the reason its static surface is this narrow.

### Route first

| If the finding is | Go |
| --- | --- |
| the skill itself is malicious by design | **AST01** — stop reading here |
| the manifest *lies* (declares `network: false` while a script calls out) | **AST04** — stop reading here |
| no permission model runs at all, because host-mode execution has none | **AST06** — stop reading here |
| a manifest that is honest but too broad, or a delegation chain that trusts its caller | this skill — continue below |
| an intent-level prompt-injection report that needs mapping onto a concrete over-broad grant | this skill — read decision rule 2 first, then the quiet list |
| unclear, or it reads like several of these at once | `node cli/bin/cli.js route "<finding text>"` names the primary category and lists contributing control failures separately |

### Then descend only this far

| Section | Read it when |
| --- | --- |
| Why this is not "apply least privilege, harder" | you expected the detector to close the category, or you are about to file a purpose-versus-scope judgement as a static finding |
| Decision rules | always: six rules, and the reason this file exists |
| Distinguishing AST03 from its neighbors | the route above was contested, or one incident spans two categories |
| What the shipped checks decide, and where they go quiet | **MANDATORY before you report a negative, and before you extend any check by hand.** The last silence is why a previous version of the identity check false-positived against every conformant USF manifest |
| Scope and out-of-artifact boundary | you are being asked whether an LPCI trigger will actually fire |

**Do NOT load `coverage-matrix.md`** to decide whether something is a finding. It is the
tier contract and the F1 denominator; open it only to cite the authoritative tier of a
named scenario. **Do NOT load `scripts/detector.py`** to learn what the checks decide —
the quiet list below states each check's scope and each silence in prose, including which
of the four claim scenario coverage. Read the source only to change it, and read all three
permission spellings before you do.

## Why this is not "apply least privilege, harder"

Least privilege is a static grant problem, and every tool in the ecosystem solves it at
the call site: *is this tool call inside the manifest*. Skills add a layer that question
cannot see. A skill permitted to run `SELECT` can be talked into running `DELETE`, and
every check passes, because no component compares the call against the task the user
actually approved. The destructive-inbox-review incident the whitepaper records is that
shape exactly — no manifest bug and no escalation exploit, only a grant wide enough that
the approved reading task never had to be checked against the action taken.

The consequence for tooling, and it is the reason this category's static surface is so
narrow: a manifest audit can only find grants that are broad *on their face*. Whether a
grant is broad *for this skill's function* requires reading the stated purpose against
the scope, which is judgement, not a predicate — `scenarios/registry.yaml` tiers exactly
that scenario (`AST03-S01` Weather Assistant Data Exfiltration; the module's old local
slug `AST03-task-scope-mismatch` was retired for it) agent-judgable for that reason. Do not expect
the detector to close the category; expect it to close one structural corner of it.

## Decision rules

1. **Bind authorization to the approved task, not to the tool.** Before each action,
   verify the action, resource, destination, and conditions still fall within what
   the user actually granted for *this* task — not merely within what the skill's
   manifest lists as possible. A manifest-compliant call can still be an
   authorization violation if it exceeds the task-scoped grant.
2. **For LPCI, the reviewable object is the trigger, not the action — and the trigger
   is usually not in the package.** Logic-layer Prompt Control Injection plants a
   payload in memory, a vector store, or a tool output that the model later reads as an
   operator-level instruction; the skill under review may contain none of it and still
   be the vehicle. Two decisions follow. First, "what does this skill do right now" is
   the wrong question to ask a static scan, so a negative result carries no information
   about a conditional payload. Second, the reviewable surface shifts to the *stores the
   skill can write*: the grant that lets a skill write memory, an index, or another
   skill's input is the LPCI precondition, and that grant is in the manifest even when
   the payload is not. Audit the write scope as the trigger surface — the same reason
   decision rule 4 treats identity-file writes as function-independent.
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

## What the shipped checks decide, and where they go quiet

**MANDATORY before you report a negative, and before you extend a check.** Exactly one
check here claims scenario coverage: `AST03-S03` Identity File Backdoors — a
declared write naming `SOUL.md`, `MEMORY.md`, or `AGENTS.md` that `deny_write` does not
shadow, evaluated with USF's most-specific-wins precedence. The other three checks are
declared `artifact-signal-only` or `category-precondition` in the module's own
`CHECK_COVERAGE`, and reading them as coverage is the overclaim this repo's tier lock
exists to prevent.

- **The unbounded-write-scope check is blind to the content of a declared floor.** It
  fires only when *no* write floor is declared at all. A manifest carrying
  `deny_write: ['/etc/hosts']` satisfies it while leaving `SOUL.md` writable — that case
  belongs to the identity-file check, and neither check reports the other's miss.
- **An explicitly empty `deny_write` is a stated floor, not an absent one,** so it does
  not fire. That is correct behaviour and it is also the shape an author uses to look
  compliant while granting everything under `write`.
- **Shell-plus-unbounded-egress is breadth, not mismatch.** The combination is a real
  signal and the registry names it as an `artifact_signal`, but it decides neither
  `AST03-S01` (which needs the purpose-versus-scope judgement) nor `AST06-S02` (which
  needs the host's sandbox and co-located services). Escalate it; do not file it as a
  scenario finding.
- **Permission vocabularies differ and a check that reads only one is silently dead.**
  One package reaches these checks in three spellings — USF `permissions.files.deny_write`,
  the flattened detector shape, and bare-boolean SKILL.md frontmatter. A previous version
  of the identity check read only the flattened spelling and reported a false positive
  against every conformant USF manifest. When you extend a check by hand, read all three
  or your extension will be dead against the manifests that actually ship.

## Scope and out-of-artifact boundary

Whether a *specific* LPCI trigger condition (a delayed, encoded payload keyed to a
future date or event) is present in a given skill's declared static content is
static-detectable in principle; whether it will actually *fire* as intended requires
runtime observation this artifact cannot provide standalone. The tier split between
"manifest declares over-broad scope" (static-detectable) and "injected content will
exploit that scope at some future trigger" (agent-judgable or out-of-artifact) is
fixed in `coverage-matrix.md`.

## References — what is loadable, and when

| Resource | Load it when |
| --- | --- |
| `coverage-matrix.md` | you must cite the authoritative tier of a named AST03 scenario, or the written reason `AST03-S01` is agent-judgable rather than static-detectable |
| `scripts/detector.py` | you are changing a check — never to find out what one decides, and never without reading all three permission spellings |
| the whitepaper's own AST03 section | you need the full attack-scenario catalog (Weather Assistant Data Exfiltration, Database Admin Wipe, Identity File Backdoors, Low-Privilege-Invokes-High-Privilege) or the complete preventive-mitigation list |

This file is the delta on top of that section, not a restatement of it.
