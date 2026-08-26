# What each detector decides

Per category: the checks that ship, the whitepaper scenarios they decide, and the ones they
deliberately do not. The README carries the roster; this is the check-by-check detail.


One block per skill, holding the description the roster above compresses to a line, the F1
exactly as `fixtures/manifest.yaml` records it, and that category's scenario-by-scenario matrix.

<details><summary><b>AST01</b> · <code>ast01-malicious-skills</code> · ten checks</summary>

Ten checks: `content_hash` absent or mismatched; install prose that pipes a remote fetch into a
shell; a declared or coded write to `SOUL.md`; the same for `MEMORY.md`; a script that both reads
an identity artifact and sends outbound; a WebSocket to an undeclared host; a hardcoded egress
destination outside the declared allowlist; concealed instructions in the package's own output
templates; an encoded blob decoded into an execution sink. Manifest F1
`scenario-level 1.000 (8 labeled checks, n=16)`;
[`skills/AST01/coverage-matrix.md`](../skills/AST01/coverage-matrix.md).

</details>

<details><summary><b>AST02</b> · <code>ast02-supply-chain-compromise</code> · one check</summary>

One check: a command-bearing value in a config file the host auto-executes **at project open** —
`.claude/settings.json` hooks, an MCP/env control-plane override, a `.vscode/tasks.json`
`folderOpen` task. Registry flooding, dependency confusion and maintainer-account takeover are
tiered `out-of-artifact` and no check claims them. Manifest F1
`scenario-level 1.000 (AST02-S03, n=6)`;
[`skills/AST02/coverage-matrix.md`](../skills/AST02/coverage-matrix.md).

</details>

<details><summary><b>AST03</b> · <code>ast03-over-privileged-skills</code> · four checks</summary>

Four checks: a declared write grant reaching the agent's own identity files (`SOUL.md`,
`MEMORY.md`, `AGENTS.md`); no declared write floor at all; shell execution combined with unbounded
egress; a blanket or wildcard egress declaration in place of an enumerated domain allowlist. Only
the first covers a named scenario — the other three are a precondition and two signals. Manifest
F1 `scenario-level 1.00 (AST03-S03, n=2); artifact-signal-only 1.00 (n=4)`;
[`skills/AST03/coverage-matrix.md`](../skills/AST03/coverage-matrix.md).

</details>

<details><summary><b>AST04</b> · <code>ast04-insecure-metadata</code> · six checks</summary>

Six checks: a declared allowlist contradicted by the destination a bundled script actually reaches;
`risk_tier` below the floor its own permissions derive; code-executing YAML tags and unsafe
loaders; `__proto__` / `constructor` keys in shipped JSON next to an unsafe merge site; redefined
TOML tables; invisible code points (flagged as a carrier class and stopped there, not convicted as
an instruction). Manifest F1 `scenario-level 1.00 (n=10)`;
[`skills/AST04/coverage-matrix.md`](../skills/AST04/coverage-matrix.md).

</details>

<details><summary><b>AST05</b> · <code>ast05-untrusted-external-instructions</code> · five checks, no scenario covered</summary>

Five checks, **every one a precondition**: a fetched document reaching an instruction sink; a
remote response body reaching an executable sink; decision rules that consume upstream content with
no provenance boundary; a blanket egress grant; a wildcard entry in the declared allowlist. The
registry tiers all six AST05 scenarios `agent-judgable` or `out-of-artifact`, so none of these
covers one. Manifest F1 `artifact-signal-only 1.00 (n=6)`;
[`skills/AST05/coverage-matrix.md`](../skills/AST05/coverage-matrix.md).

</details>

<details><summary><b>AST06</b> · <code>ast06-weak-isolation</code> · five checks</summary>

Five checks: a bundled script that shell-execs or writes a host-persistence path; a declared write
scope reaching the filesystem root or the home directory; shell granted with no bounding command
list; declared writes into a shared workspace namespace; an absent or empty permissions block. The
first two decide AST06-S01's two disjuncts; the rest are a precondition and two signals. Manifest
F1 `scenario-level 1.00 (AST06-S01, n=4); artifact-signal-only 1.00 (n=2)`;
[`skills/AST06/coverage-matrix.md`](../skills/AST06/coverage-matrix.md).

</details>

<details><summary><b>AST07</b> · <code>ast07-update-drift</code> · no check ships</summary>

**No check ships, and none can.** All three AST07 scenarios — malicious update, rollback,
hot-reload abuse — are defined by a *change between versions*, and one package at one moment
carries no second version to compare against. The skill is knowledge only; `coverage-matrix.md`
names the version-history evidence that would decide each one. Manifest F1
`declared-and-uncovered`; [`skills/AST07/coverage-matrix.md`](../skills/AST07/coverage-matrix.md).

</details>

<details><summary><b>AST08</b> · <code>ast08-poor-scanning</code> · four checks</summary>

Four checks: an obfuscated instruction found by decode-and-rescan over the normalized view
(comparing match counts per view, so a decoy in the clear cannot mask a smuggled copy); a branch
that arms only under a specific environment; scanner-host hazards (padding runs, recursive
archives, decompression ratio, symlink escape); bytecode the import machinery would prefer over its
own source. Manifest F1 `scenario-level 1.00 (4 scenario checks, n=8)`;
[`skills/AST08/coverage-matrix.md`](../skills/AST08/coverage-matrix.md).

</details>

<details><summary><b>AST09</b> · <code>ast09-no-governance</code> · no check ships</summary>

**No check ships, and none can.** All seven AST09 scenarios are `out-of-artifact`: inventory,
approval, ownership and offboarding live in an organisation's process, not in a package. The skill
is knowledge only; `coverage-matrix.md` names the governance-system evidence that would decide each
one. Manifest F1 `declared-and-uncovered`;
[`skills/AST09/coverage-matrix.md`](../skills/AST09/coverage-matrix.md).

</details>

<details><summary><b>AST10</b> · <code>ast10-cross-platform-reuse</code> · one check</summary>

One check: a payload hidden in an encoded blob that survives a port — decoded (base64, hex escapes,
gzip-under-base64), then judged at the *content* layer, so a package carrying a legitimate encoded
blob is not convicted for carrying one. Security metadata stripped during a port can be narrated
inside a fake `SKILL.md`, so it is tiered `out-of-artifact` and no check claims it. Manifest F1
`1.0`, its scope `scenario-level` carried in the sibling `f1_scope` field;
[`skills/AST10/coverage-matrix.md`](../skills/AST10/coverage-matrix.md).

</details>

<details><summary><b>advisory</b> · <code>advisory</code> · not a detector</summary>

Not a detector. Routes a free-text finding to its primary AST category via the whitepaper's
decision tree and returns category-specific remediation. It has no fixture corpus and no F1 at any
corpus size; the judge panel scores it on guidance quality like every other knowledge package,
which is why it carries a verdict and no number.

</details>

---

[< Back to the README](../README.md)
