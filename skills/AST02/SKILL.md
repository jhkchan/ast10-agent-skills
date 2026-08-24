---
name: ast02-supply-chain-compromise
description: "Detect and triage OWASP AST02 Supply Chain Compromise — registry flooding, dependency confusion in a skill's nested requirements.txt/package.json, config-file hijacking (.claude/settings.json, hooks), and maintainer-account takeover. Use when auditing a skill registry's provenance controls, when a skill's top-level files look clean but its dependency tree is unaudited, when a repository's config files (not its source) are the suspected execution path, or when deciding whether a finding belongs here versus AST01 (the payload) or AST08 (the missed detection)."
---

# AST02 - Supply Chain Compromise

Pattern: Knowledge. Read the orientation block, take a route, then descend only as far as
the route sends you. The one mechanism a package can decide — an execution path in a config
file the host auto-reads at project open — lives in `scripts/detector.py`; the frozen
scenario tiers, and the three scenarios no package decides, live in `coverage-matrix.md`.

## Orientation — read this much, then decide whether to read the rest

- **Fires when** the question is *delivery and provenance*: how a skill got onto the
  machine, whether the thing that arrived is the thing the publisher signed, and whether a
  config file the host opens unprompted carries an execution path.
- **Decides** exactly one scenario in-package — `AST02-S03` Config-File Hijacking. One
  check, deliberately. The rest of the file is the audit reasoning for the controls a
  reviewer has to check by hand.
- **Never decides** Registry Flooding, Dependency Confusion or Maintainer Account
  Takeover. Those are properties of a corpus, a resolver and an account; none is inside
  the package you are holding, and the emptiness of the matrix *is* the measurement.
- **Stop now** if the route below sends you elsewhere. This is the category where the
  in-artifact surface is smallest, so a wrong route wastes the most reading.

### Route first

| If the finding is | Go |
| --- | --- |
| a payload's *content* — what the delivered skill actually does | **AST01** — stop reading here |
| a poisoned document the skill merely reads at runtime, which no hash pin reaches | **AST05** — stop reading here |
| an agent auto-applying an upstream update without human review, or an unpatched install | **AST07** — stop reading here |
| a scanner that never walks the recursive dependency tree | **AST08** — stop reading here |
| provenance, signing, revocation, dependency pinning, or a repo config file that executes on open | this skill — continue below |
| a Maintainer Account Takeover incident | both — the takeover is AST02, the blind auto-apply is AST07; read the neighbors section, not the whole file |
| unclear, or it reads like several of these at once | `node cli/bin/cli.js route "<finding text>"` names the primary category and lists contributing control failures separately |

### Then descend only this far

| Section | Read it when |
| --- | --- |
| Why this category has almost no in-artifact surface | you are about to claim registry membership as a provenance signal, or to ask why only one check ships |
| Decision rules | always: six rules, and the reason this file exists |
| Distinguishing AST02 from its neighbors | the route above was contested, or one incident spans two categories |
| What the one shipped check decides, and the six ways it goes quiet | **MANDATORY before you report a negative `AST02-S03` result.** Every one of the six returns a negative verdict that is not a clean one |
| Scope and out-of-artifact boundary | you are being asked to detect a maintainer-account compromise from the artifact |

**Do NOT load `coverage-matrix.md`** to decide whether something is a finding. It is the
tier contract and the F1 denominator; open it only to cite the authoritative tier of a
named scenario, or the written reason a scenario is out-of-artifact. **Do NOT load
`scripts/detector.py`** to learn what the one check decides — the quiet list below states
its keying, its four firing shapes and its six silences in prose. Read the source only to
extend the closed path list.

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

**MANDATORY before you report a negative.** Each of the following returns a negative
verdict that is not a clean one.

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

## References — what is loadable, and when

| Resource | Load it when |
| --- | --- |
| `coverage-matrix.md` | you must cite the authoritative tier of a named AST02 scenario, or the written reason three of the four are out-of-artifact |
| `scripts/detector.py` | you are extending the closed config-path list for a new host — never to find out what the check decides |
| the whitepaper's own AST02 section (source: `ast02.md`) | you need the full attack-scenario catalog, the real-world config-hijacking evidence, the Trail of Bits (Jun 3, 2026) scanner-bypass result, or the preventive-mitigation list |

This file is the delta on top of that section, not a restatement of it.
