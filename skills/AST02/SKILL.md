---
name: ast02-supply-chain-compromise
description: "Detect and triage OWASP AST02 Supply Chain Compromise — registry flooding, dependency confusion in a skill's nested requirements.txt/package.json, config-file hijacking (.claude/settings.json, hooks), and maintainer-account takeover. Use when auditing a skill registry's provenance controls, when a skill's top-level files look clean but its dependency tree is unaudited, when a repository's config files (not its source) are the suspected execution path, or when deciding whether a finding belongs here versus AST01 (the payload) or AST08 (the missed detection)."
---

# AST02 - Supply Chain Compromise

Pattern: Knowledge. Decision rules for where AST02 controls reach and where they
structurally cannot. The one mechanism a package can decide — an execution path in a
config file the host auto-reads at project open — lives in `scripts/`; the frozen scenario
tiers, and the three scenarios no package decides, live in `coverage-matrix.md`.

## Why this category has almost no in-artifact surface

Three of AST02's four named scenarios are properties of a *corpus over time*, not of a
package: Registry Flooding is a publication rate, Dependency Confusion is a resolver
outcome in a namespace the package does not contain, and Maintainer Account Takeover
produces a release that verifies exactly as an honest one does — the attacker holds the
legitimate key. One package is indistinguishable from one member of a flood, and the
registry records no in-package signal for any of the three. That is why this skill
ships exactly one check and why its coverage matrix is mostly empty: the emptiness is
the measurement, and padding it with proxy checks filed under scenario ids would be an
overclaim, not coverage.

The corollary for review practice: "the skill is on a registry" carries near-zero
provenance signal. Registry membership and cryptographic verification are two different
assertions answered by two different mechanisms; a lookup that returns *found* has not
verified anything.

## Decision rules

1. **"Listed", "signed", and "unrewritten" are three separate questions, and a system
   that answers only the first reports PASS for all three.** A membership lookup
   answers *does this digest appear in what the log currently serves*. It does not
   answer *is this the digest the publisher actually signed* (that needs a signature
   over a canonical serialization, verified against a resolvable publisher key), and it
   does not answer *has the log's own history been rewritten* (that needs inclusion and
   consistency proofs against a monitored root). The failure mode is silent by
   construction: each unanswered question degrades to a pass, so the composite verdict
   looks identical whether all three controls exist or only the cheapest one does. When
   auditing, name which of the three a given implementation performs — the absence of
   the other two is the finding, and it will not appear as an error anywhere.
2. **Sign the bundle, not the entry point.** The signature must cover a canonical
   digest of SKILL.md *plus every declared resource file*, so a post-publish edit to
   any declared file — not just the top-level manifest — invalidates it. A signature
   scheme that only hashes SKILL.md leaves every referenced resource file an
   unauthenticated attack surface. The in-package half of this *is* decidable and this
   repository decides it: a declared `content_hash` that contradicts the shipped bytes
   is a self-contained contradiction, owned by AST01's check and recorded there as a
   category precondition — never as coverage of an AST02 scenario.
3. **The payload is usually in the nested dependency, not the top-level skill.**
   Dependency Confusion tampers with a transitive package, not the surface skill file
   — this is precisely why a scanner that only inspects the skill's own top-level
   files (the AST08 failure mode) misses it. A skill named "Summarize YouTube Videos"
   that imports `yutube-dl-core` instead of the legitimate package is the canonical
   shape: the surface skill reads clean.
4. **Version ranges are not a security control; hash pins are.** `requests>=2.25.0`
   permits any future release under that range, including a compromised one, to satisfy
   the dependency at install time with no new review. `requests==2.31.0
   --hash=sha256:<digest>` pins to bytes, not to a mutable name+range. Hash-checking
   mode requires *every* package in the transitive tree to carry a hash — a partial
   pin is not a pin.
5. **Repository configuration files are executable code, not passive metadata — treat
   them as first-class attack surface.** `.claude/settings.json`, hooks, and
   environment-override files (e.g. `ANTHROPIC_BASE_URL`) can trigger on repo-open,
   before any user action and before any skill even runs — this is a distinct trigger
   condition from AST01's "user installs/invokes a malicious skill."
6. **Revocation must be addressable at three granularities, or it isn't usable.** A
   compromised signing key, one bad skill version by content digest, and an entire
   publisher are three different blast radii; a revocation mechanism that can only
   revoke "the whole publisher" over-blocks every other skill from a large publisher
   for one bad release, and under-scopes when only a single key is compromised. Hosts
   must consult a revocation endpoint at load time with a bounded freshness window —
   a revocation list checked only at publish time misses post-publish compromise.

## Distinguishing AST02 from its neighbors

- **vs AST01:** AST02 is delivery/provenance; AST01 is payload. "Publishers could
  upload unlimited packages with no scanning" is an AST02 finding about the registry
  even if every uploaded skill that day happened to be benign.
- **vs AST05 (Untrusted External Instructions):** AST02's code-integrity controls
  (hash pins, signed digests) can pin and verify a *dependency*. They cannot pin a
  *document a skill merely reads at runtime* — that is AST05's surface exactly because
  those integrity controls do not reach it. A CVE fixed in a pinned dependency and a
  poisoned referenced runbook are different attack surfaces requiring different
  controls, even when both are "external content the skill trusts."
- **vs AST07 (Update Drift):** AST02 is compromise at publish/delivery time
  (Maintainer Account Takeover pushing v2.0 with a payload); AST07 is drift after a
  *legitimate* install goes unpatched, or an update mechanism blindly applying
  upstream changes. The Maintainer Account Takeover scenario sits at the seam: the
  takeover itself is AST02, and an agent auto-applying that malicious update without
  human review is the AST07 half of the same incident.
- **vs AST08:** a scanner that never inspects the recursive dependency tree — only
  the top-level skill file — is an AST08 gap that *causes* AST02 dependency-confusion
  attacks to go undetected. Classify the missed detection capability as AST08 and the
  underlying compromise as AST02; they are not interchangeable labels for one finding.

## What the one shipped check decides, and the six ways it goes quiet

`AST02-S03` is keyed on the **config surface**, not on the presence of a command
string: the same shell command is unremarkable inside a bundled script and is an
execution path the host enters unprompted inside `.claude/settings.json`. CVE-2025-59536
and CVE-2026-21852 are why the keying is that way round — cloning and opening a
repository was sufficient, with no dialog shown. Within those files the check fires on
four auto-executed shapes only: a hook entry carrying a command, an MCP server entry
that spawns a process, a control-plane environment override, and a folder-open task.

Each of the following returns a negative verdict that is not a clean one.

- **The check reads config files shipped *inside the package*. The incident shape is a
  config file in the repository the agent opens.** That repository is not part of any
  skill package, so a clean AST02-S03 result on a skill says nothing about the
  workspace it will run in. Scan the target repo separately; this check does not.
- **The scanned path list is closed and host-specific.** Eight exact path tails are
  covered. `.devcontainer/devcontainer.json` (whose `postCreateCommand` is precisely
  this scenario), `.envrc`, `.github/workflows/*`, `.zed/`, `.idea/`, and any newer
  agent host's config directory are not. Extend the list per host before relying on a
  negative.
- **The parse is strict JSON, and an unparseable file ends the whole scan.** A settings
  file with comments or trailing commas (the JSONC dialect editors actually accept), or
  a YAML/TOML equivalent, raises — and the check returns immediately with `unparseable
  JSON; no execution path decided`, so config files sorted after it are never examined.
  That is an INCOMPLETE result wearing a negative verdict; read the evidence string, not
  the boolean.
- **Environment overrides are only found inside a block named `env`, `environment`, or
  `envVars`.** VS Code's dotted `terminal.integrated.env.osx` key and any override set
  at the document root fall outside that shape and are missed even when the variable
  itself is on the control-plane list.
- **An MCP command must hang off a *named server* child.** A command scalar placed
  directly on the `mcpServers` mapping is skipped deliberately, so the container itself
  cannot be convicted — a host that reads a command from that position is uncovered.
- **Command detection is a fixed key set of scalars** (`command`, `cmd`, `script`,
  `exec`, `run`, `shellcmd`). An entry that carries only `args`, or that spells the key
  `entrypoint` or `program`, yields no command value and clears — inside a hook block
  that the host will still execute.

## Scope and out-of-artifact boundary

Maintainer Account Takeover is a registry-side event — whether a given publisher
account was actually compromised is not observable from the skill artifact itself; a
detector can only observe *symptoms* (a signing-key change, an anomalous version jump)
that a coverage matrix may tier as agent-judgable rather than static-detectable. The
authoritative tier and its written reason live in `coverage-matrix.md`; this file does
not pre-empt that lock.

## References

Full attack-scenario catalog, the real-world config-hijacking evidence, the Trail of
Bits (Jun 3, 2026) scanner-bypass result, and the preventive-mitigation list are the
whitepaper's own AST02 section (source: `ast02.md`). This file is the delta on top of it.
