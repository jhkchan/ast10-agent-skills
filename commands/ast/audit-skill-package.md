---
name: audit-skill-package
description: >-
  Run the full AST01-AST10 sweep over one candidate skill directory: validate its Universal
  Skill Format manifest, run every implemented static-detectable check across all ten
  categories, and close with a coverage ledger that states which of the whitepaper's 62 named
  scenarios the sweep decided, which need a judge, and which are not decidable from one
  package at all.
nl_triggers:
  - "audit this skill package"
  - "full AST sweep"
  - "is this skill safe to install"
  - "run all ten categories on this directory"
  - "security review this skill before install"
  - "check this skill against the OWASP agentic skills top 10"
  - "what is wrong with this skill package"
  - "sweep this candidate skill"
  - "review this SKILL.md and its manifest"
  - "pre-install skill audit"
routes_to:
  - ast01-malicious-skills
  - ast02-supply-chain-compromise
  - ast03-over-privileged-skills
  - ast04-insecure-metadata
  - ast05-untrusted-external-instructions
  - ast06-weak-isolation
  - ast07-update-drift
  - ast08-poor-scanning
  - ast09-no-governance
  - ast10-cross-platform-reuse
  - advisory
---

# /owasp-ast10:audit-skill-package

Activates all ten detector skills (`skills/AST01/` … `skills/AST10/`) in numeric order over
one candidate package, then the `advisory` skill (`skills/advisory/`) to triage anything the
ten did not decide. Use `/owasp-ast10:audit-ast01` … `/owasp-ast10:audit-ast10` when you already know which
category you care about.

## What it does

1. **Normalise.** Reads the package into the detector input shape —
   `{"manifest": {...}, "files": {"<relative/path>": "<text>"}}`. A `skill.usf.yaml` beside
   `SKILL.md` supplies the manifest half; a package without one yields an empty manifest,
   which is itself a finding in AST03 and AST06.
2. **Validate the manifest.** If a `skill.usf.yaml` is present, `validators/usf.py` runs
   first — schema shape plus the semantic rules (deny_write precedence, default-deny
   network, identity-file protection, derived `risk_tier` floor, `content_hash` agreement).
   A manifest that fails here makes every downstream permission finding provisional, so the
   sweep says so rather than reporting them as settled.
3. **Sweep.** Runs each category's `DETECTORS` map via `run_all(pkg)`. Eight of the ten
   categories ship implemented checks — **36 in total** (`AST01` 10, `AST04` 6, `AST05` 5,
   `AST06` 5, `AST03` 4, `AST08` 4, `AST02` 1, `AST10` 1) — and two, `AST07` and `AST09`,
   ship none by design. `tests/test_docs.py` fails if that total drifts from the modules.
4. **Ledger.** Closes with the coverage accounting: what was decided, what needs a judge,
   what is not decidable from an artifact. This section is mandatory, not optional trim.
5. **Triage the remainder.** Anything the ten did not decide but a human flagged in prose
   goes through the `advisory` skill's decision tree, which records one primary root cause
   and any others as contributing control failures.

## Which categories can return a verdict

Counts are each module's own `DETECTORS` registry, and
`tests/test_docs.py::test_the_sweep_page_check_table_matches_the_detector_modules` fails if
this table and the code part company — which is what happened before: it carried a
scaffold-era roster (thirteen, spread over six categories) long after 36 shipped across
eight.

| Category | Implemented checks | Status |
| --- | --- | --- |
| AST01 Malicious Skills | 10 | covered (scenario-level) |
| AST02 Supply Chain Compromise | 1 | covered (scenario-level) |
| AST03 Over-Privileged Skills | 4 | proxy-covered (mixed-proxy) |
| AST04 Insecure Metadata | 6 | covered (scenario-level) |
| AST05 Untrusted External Instructions | 5 | proxy-covered (artifact-signal-only) |
| AST06 Weak Isolation | 5 | proxy-covered (mixed-proxy) |
| AST07 Update Drift | 0 | declared-and-uncovered |
| AST08 Poor Scanning | 4 | covered (scenario-level) |
| AST09 No Governance | 0 | declared-and-uncovered |
| AST10 Cross-Platform Reuse | 1 | covered (scenario-level) — AST10-S06 only; the manifest half lives in `validators/usf.py` |

The zero-check categories are not gaps in the sweep; they are the sweep's honest output.
Their scenarios turn on version history, registry state, organisational process, or a second
platform's copy of the manifest — none of which a single package snapshot contains.

## Arguments

| Position | Argument | Required | Meaning |
| --- | --- | --- | --- |
| `$1` | `<package-path>` | yes | Directory of the candidate skill package. Must contain `SKILL.md`. A `skill.usf.yaml`, `requirements.txt`, `package.json`, and a `scripts/` tree are all read when present. |
| `$2…` | `--only <ASTnn,…>` | no | Restrict the sweep to named categories. The coverage ledger still reports the categories that were skipped, so a narrowed run cannot be mistaken for a full one. |
| `$2…` | `--strict` | no | Exit non-zero if any check returns DETECTED, or if the USF manifest fails validation. |
| `$2…` | `--no-manifest` | no | Skip step 2. Every permission-derived finding is then marked provisional. |
| `$2…` | `--ledger-only` | no | Print step 4 alone — useful for answering "what could this sweep even have found?" before running it. |

With no `<package-path>`, the command asks for one rather than guessing a target.

## Example invocation

```text
/owasp-ast10:audit-skill-package ./invoice-helper
```

`invoice-helper` is a package whose manifest declares no `content_hash`, an empty
`deny_write`, `network.policy: allow-all`, and `shell.allowed: true` with no command
allow-list, and whose `<package>/scripts/setup.py` parses config through an unsafe YAML
loader.

## Output

**Abridged.** The shape below is the real report's; the per-category rows are cut down to
the ones that carry the example. A real sweep prints a line for every one of the 36 shipped
checks, so the `n/m` counts in the headers are the module's own roster and the ledger's
totals are the roster totals — neither is a per-example figure.

```text
PACKAGE: ./invoice-helper
MANIFEST: skill.usf.yaml present - validated first (see /owasp-ast10:validate-usf-manifest)

AST01  Malicious Skills                  1/10 DETECTED
  DETECTED  AST01-content-hash-missing        manifest.content_hash.value is unset
  CLEAN     AST01-content-hash-mismatch       no declared hash to compare
AST02  Supply Chain Compromise           0/1 DETECTED
AST03  Over-Privileged Skills            2/4 DETECTED
  DETECTED  AST03-unbounded-write-scope        permissions.deny_write is unset or empty
  DETECTED  AST03-shell-network-privilege-combo  shell.allowed=True network.policy=allow-all
AST04  Insecure Metadata                 1/6 DETECTED
  DETECTED  AST04-yaml-injection               scripts/setup.py: Loader=yaml.UnsafeLoader
  CLEAN     AST04-json-injection               no prototype-pollution keys found
  CLEAN     AST04-toml-injection               no unexpected top-level TOML keys found
  CLEAN     AST04-invisible-unicode-smuggling  no invisible Unicode control code points found
AST05  Untrusted External Instructions   1/5 DETECTED   [artifact-signal-only]
  DETECTED  AST05-unrestricted-network-fetch   network.policy=allow-all
  CLEAN     AST05-wildcard-domain-allowlist    not in allow-list mode
AST06  Weak Isolation                    1/5 DETECTED
  DETECTED  AST06-unrestricted-shell-exec      shell.allowed with no commands allow-list
  CLEAN     AST06-missing-sandbox-declaration  permissions block present
AST07  Update Drift                      DECLARED-AND-UNCOVERED  (0 checks by design)
AST08  Poor Scanning                     1/4 DETECTED   [scenario-level]
  DETECTED  AST08-S02  SKILL.md: base64 blob at decode depth 1 decodes to a layer
            matching rule 'remote-fetch-piped-to-shell'
  CLEAN     AST08-S04  no environment-keyed guard wraps a dangerous branch
  CLEAN     AST08-S07  within every declared bound (files, size, padding, archive
            depth and ratio, symlink escape, special files)
  CLEAN     AST08-S08  every shipped .pyc corresponds to shipped source
AST09  No Governance                     DECLARED-AND-UNCOVERED  (0 checks by design)
AST10  Cross-Platform Reuse              1/1 DETECTED   [scenario-level]
  DETECTED  AST10-S06  scripts/loader.py: base64+gzip blob decodes to
            identity-file-write+credential-harvest content layer

-------------------------------------------------------------------------------
COVERAGE LEDGER
  Checks run:        36 static-detectable across 8 of 10 categories
  DETECTED:          6
  Registry total:    62 named scenarios - 20 static-detectable,
                     8 agent-judgable, 34 out-of-artifact
  Not decided here:  8 agent-judgable scenarios need the judge harness
  Not decided here:  34 out-of-artifact scenarios are not decidable from one package
  No F1 published:   AST02, AST07, AST09 (empty detectable tier)
  Proxy-scoped F1:   AST03 mixed-proxy, AST05 artifact-signal-only,
                     AST06 mixed-proxy
-------------------------------------------------------------------------------

VERDICT: 6 DETECTED finding(s). Highest-severity seam: AST03 + AST06 together -
  arbitrary shell with unrestricted egress and no deny_write is the exfiltration
  primitive, not two independent hygiene nits.
NEXT: /owasp-ast10:check-coverage AST05   (why this category's number is proxy-scoped)
      /owasp-ast10:validate-usf-manifest ./invoice-helper/skill.usf.yaml
```

A sweep with zero DETECTED findings means "none of the 36 implemented checks fired against
this package". It does not mean the package is safe, and the ledger is there so the report
can never be read that way.

## Reading the seams, not just the rows

The rows are independent; the risk is not. Three combinations the sweep calls out explicitly
when they co-occur:

- **AST03 + AST06** — unrestricted shell plus unrestricted egress plus no `deny_write`. Each
  row is a permission finding; together they are a working exfiltration path.
- **AST01 + AST08** — a payload found *and* a scanner that should have caught it. File one
  finding with AST01 as the primary root cause and AST08 as a contributing control failure.
  Never two findings.
- **AST04 + AST10** — a manifest that under-declares its own permissions is an AST04 problem
  on this platform and becomes an AST10 problem the moment the package is ported, because
  the destination runtime's default fills the gap the manifest left.

## Related

- `/owasp-ast10:audit-ast01` … `/owasp-ast10:audit-ast10` — one category, with that category's decision
  rules and neighbour seams spelled out in full.
- `/owasp-ast10:validate-usf-manifest` — step 2 on its own.
- `/owasp-ast10:check-coverage <ASTnn>` — the full per-scenario expansion of any ledger line.
- `/owasp-ast10:triage-finding` — for the findings a human raises that no detector can.
