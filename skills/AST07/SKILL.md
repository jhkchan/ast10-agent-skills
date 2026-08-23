---
name: ast07-update-drift
description: "Detect and triage OWASP AST07 Update Drift — skills installed without immutable pinning that fall behind known-good versions, or that auto-update onto a malicious 'patch' release, plus Rollback Attack and Hot-Reload Abuse. Use when auditing an installed skill's pin discipline (hash vs. version range), when an update mechanism applies upstream changes without human review, when a downgrade needs distinguishing from a legitimate version bump, or when deciding whether Rollback Attack / Hot-Reload Abuse are checkable from this artifact at all."
---

# AST07 - Update Drift

Pattern: Knowledge. The decision rule this category turns on: a version string is an
attacker-controlled claim, not a security property — "v1.0.1" looks like a patch and
can just as easily carry a new payload, because nothing about a semver bump is
cryptographically meaningful on its own. `scripts/` ships **no detector** for this
category and the section below explains why that is the finished state; frozen scenario
tiers live in `coverage-matrix.md`.

## Why patch lag and blind auto-update are the same root cause read two ways

Update Drift presents as two opposite complaints — deployments too slow to patch, and
agents too eager to apply whatever upstream published — and teams treat them as a
trade-off to be tuned between. They are not opposite; they are one missing thing seen
from two sides: **there is no verified target version to converge on.** Slow-patch
deployments have nothing authoritative to converge *to*; eager-update deployments
converge to whatever the registry currently serves, which is the same absence with the
sign flipped.

The practical consequence is a rejection rule for proposed fixes. Rate-limiting or
staging updates without adding a verification step just lengthens the window on the
slow side. Adding signature verification without a freshness requirement leaves a
verified-but-ancient artifact looking healthy forever. A remediation that moves only one
of the two has not closed anything — check both halves before accepting one.

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

## This category ships zero detectors, and that is the result

All three AST07 scenarios — Malicious Update, Rollback Attack, Hot-Reload Abuse — are
tiered out-of-artifact, so the static-detectable tier is empty and the module ships an
empty detector map. Two things about that are worth more than the rules above, because
they are where honest coverage accounting is usually lost.

**The tempting move is to promote a precondition into coverage, and it is precisely
wrong.** Two preconditions *are* decidable from one package: whether a content hash is
declared at all, and whether the pin is a hash or a mutable range. The registry records
them as `artifact_signal` for AST07-S01 and AST07-S02, and AST01's content-hash check
already reads the first. Filing either under an AST07 scenario id would produce a
coverage table that looks complete and a number that measures nothing — a hash-pinned
skill can still be maliciously updated the moment an operator accepts the new hash, and
an unpinned one may never receive a malicious update at all. The signal is real; the
inference from signal to scenario is not.

**An empty column must publish no F1 rather than a manufactured one.** With no scenario
in the tier there is no denominator, so this category reports `declared-and-uncovered`
and a corpus of zero. That is a measurement refusal, and it is guarded in both
directions by tests that pin the module's detector map to its static-detectable set and
that set to the registry: if a tier is ever promoted, the pair fails loudly in the same
change and a detector is owed. When you read this category's report, the empty cell is
the finding — do not fill it.

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
