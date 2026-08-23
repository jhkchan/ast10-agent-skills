---
name: ast07-update-drift
description: "Detect and triage OWASP AST07 Update Drift — skills installed without immutable pinning that fall behind known-good versions, or that auto-update onto a malicious 'patch' release, plus Rollback Attack and Hot-Reload Abuse. Use when auditing an installed skill's pin discipline (hash vs. version range), when an update mechanism applies upstream changes without human review, when a downgrade needs distinguishing from a legitimate version bump, or when deciding whether Rollback Attack / Hot-Reload Abuse are checkable from this artifact at all."
---

# AST07 - Update Drift

Pattern: Knowledge. The decision rule this category turns on: a version string is an
attacker-controlled claim, not a security property — "v1.0.1" looks like a patch and
can just as easily carry a new payload, because nothing about a semver bump is
cryptographically meaningful on its own. Mechanism (pin-vs-range detection, hash
verification) lives in `scripts/`; frozen scenario tiers live in
`coverage-matrix.md`.

## Why patch lag and blind auto-update are the same root cause read two ways

The whitepaper frames Update Drift as amplified by two factors specific to skills:
individual installers without enterprise patch management, and update mechanisms that
apply upstream changes with no verification step. These sound like opposite failure
modes (too slow to patch vs. too eager to patch) but share one root cause — the
absence of a *verified* target version to converge on. SecurityScorecard's Feb 2026
study found 35.4% of scanned OpenClaw deployments vulnerable to RCE at publication,
evidence of the slow-patch failure; a compromised maintainer account pushing v2.0 with
a payload that auto-updating agents receive silently is the fast-patch failure. Fixing
either without the other (rate-limiting updates without adding verification, or adding
verification without a freshness requirement) leaves the category open.

## Decision rules

1. **Pin to content hash, never to a version string.** A `sha256:` pin is
   unambiguous; a version-range pin ("latest v1.x") resolves to whatever the
   registry currently serves under that label, which is exactly the surface a
   Malicious Update or Rollback Attack manipulates. This is the same principle as
   AST02's dependency-pinning rule, applied to the *installed skill itself* rather
   than to a nested dependency.
2. **A downgrade is not intrinsically suspicious — an *unrequested* downgrade is.**
   Rollback Attack forces a version resolution to a known-vulnerable release via
   dependency-resolution manipulation, not via a user or admin explicitly choosing to
   roll back. The detectable signal is "resolved version decreased without an
   explicit operator action requesting that specific version," not "resolved version
   decreased."
3. **Hot-reload and "freeze mode" are mutually exclusive by design intent, not by
   accident.** A hot-reload watcher (e.g. OpenClaw's `SkillsWatcher`) makes a
   compromised upstream repository instantly active with no restart required — this
   is the intended feature working as designed, which is precisely why it is
   dangerous. The fix is not "detect malicious hot-reloaded content" (a losing
   detection race against arbitrary content) but "prohibit hot-reload in
   non-development environments" as a configuration-level control.
4. **An inventory without hash and last-verified timestamp cannot answer "are we
   drifted."** "Version" alone is insufficient provenance — recording hash and
   last-verified timestamp per installed skill is what lets a later CVE-match or
   audit actually determine whether a specific deployed artifact, not just a version
   label, is the vulnerable one.
5. **Human-in-the-loop review belongs on *substantive* changes, not on every
   update.** Gating every single update on manual approval is unworkable at fleet
   scale and trains reviewers to rubber-stamp; the whitepaper's own guidance is to
   validate changes through a semantic security check first and route only
   substantive changes to human review — a purely mechanical version bump with an
   unchanged semantic diff does not need the same gate as a permission-scope change.

## Distinguishing AST07 from its neighbors

- **vs AST02 (Supply Chain Compromise):** Maintainer Account Takeover is the
  compromise event (AST02); an agent auto-applying the resulting malicious update
  with no verification is the AST07 half of the same incident. Classify the account
  compromise as AST02 and the missing update-verification control as AST07 — they
  are two separate, separately-fixable failures that happened to occur together.
- **vs AST05 (Untrusted External Instructions):** AST07 is the *skill's own version*
  changing (with or without the skill's knowledge). AST05 is the identical drift
  phenomenon applied to *content the skill references*, which can change while the
  skill's pinned version stays byte-identical and every version-based control passes.
- **vs AST08 (Poor Scanning):** an updated skill that is not re-scanned after the
  update is an AST08 process gap (scanning only runs at initial install) that lets a
  newly-introduced AST07 vulnerability go undetected — the missing re-scan trigger is
  AST08's finding, not a duplicate AST07 finding.

## Scope and out-of-artifact boundary — read this before tiering

Rollback Attack and Hot-Reload Abuse are properties of version *history* and runtime
*event sequencing* — whether a resolved version decreased relative to a prior state,
or whether a file changed mid-session without a restart — neither of which a single,
point-in-time skill-package artifact carries. A static read of one SKILL.md cannot
observe "this is a downgrade" without an external record of what was previously
installed, and cannot observe "this changed without a restart" without runtime
process telemetry. This is the whitepaper-independent, structural reason both
scenarios are strong out-of-artifact candidates; the binding tier and its written
reason are fixed in `coverage-matrix.md`, not asserted here. What *is* checkable from
the artifact alone: whether a skill's own declared pinning mechanism uses a hash or a
mutable version range (decision rule 1) — that is a property of the manifest, not of
history.

## References

Full attack-scenario catalog and preventive-mitigation list are the whitepaper's own
AST07 section (source: `ast07.md`). This file is the delta on top of it.
