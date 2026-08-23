---
name: audit-ast02
description: >-
  Audit one candidate skill package against OWASP AST02 - Supply Chain Compromise alone,
  using the ast02-supply-chain-compromise skill's decision rules and the frozen per-scenario
  detectability contract in skills/AST02/coverage-matrix.md. This category's
  declared-detectable tier is empty, so the command publishes no F1 and no DETECTED/CLEAN
  verdicts — it reports declared-and-uncovered and names the off-artifact evidence a
  reviewer has to gather instead.
nl_triggers:
  - "was this skill typosquatted"
  - "supply chain check on this skill"
  - "dependency confusion"
  - "registry flooding"
  - "maintainer account takeover"
  - "AST02 audit"
  - "is this registry entry trustworthy"
  - "config file hijacking"
routes_to: ast02-supply-chain-compromise
ast_category: AST02
---

# /ast:audit-ast02

Activates the `ast02-supply-chain-compromise` skill (`skills/AST02/`) and audits one
candidate skill package against **AST02 - Supply Chain Compromise** and nothing else. Use
`/ast:audit-skill-package` when you want all ten categories in one pass.

## What AST02 actually is

AST02 is the delivery mechanism, not the payload. The registry's own auth and session logs
hold the signal (who published this version, from what account, with what credential) and a
package snapshot cannot contain it. CVE-2025-59536 and CVE-2026-21852 are the whitepaper's
own evidence that the compromise lands upstream of anything a scanner reads.

**Seam.** If the malice is inside the file, that is AST01. If the question is how the file
got into the registry or onto the machine, it is AST02.

## What it does

1. Normalises the package into the detector's input shape — `{"manifest": {...},
   "files": {"<relative/path>": "<text>"}}`. A `skill.usf.yaml` is read for the
   manifest half; a bare `SKILL.md` package yields an empty manifest, which is itself
   a finding in several categories.
2. Confirms `skills/AST02/scripts/detector.py` ships zero detector functions —
   deliberate, per the empty-detectable-tier rule: a category whose declared-detectable
   tier is empty publishes no F1 rather than padding a corpus to manufacture one.
3. Reads `scenarios/registry.yaml` and `skills/AST02/coverage-matrix.md` and reports
   each named scenario with the written reason it is not decidable from one package.
4. Applies the `ast02-supply-chain-compromise` skill's decision rules to name the evidence
   that *would* decide each scenario, and where that evidence lives.

## Why there is nothing to run

| Scenario | Tier | Why one package cannot decide it |
| --- | --- | --- |
| AST02-S01 Registry Flooding | out-of-artifact | the flood is a property of the registry's contents, not of any one package in it |
| AST02-S02 Dependency Confusion | out-of-artifact | resolution order is a property of the installing client's index configuration |
| AST02-S04 Maintainer Account Takeover | out-of-artifact | a package carries no observable difference between a legitimate release and a hijacked account's release of the same content |

## Arguments

| Position | Argument | Required | Meaning |
| --- | --- | --- | --- |
| `$1` | `<package-path>` | yes | Directory (or archive) of the candidate skill package. Must contain a `SKILL.md`; a `skill.usf.yaml` beside it is read as the manifest. A repo path, an unpacked download, or one of this repo's own `fixtures/` directories all work. |
| `$2…` | `--evidence-plan` | no | Instead of the scenario table, emit the off-artifact evidence a reviewer must gather to decide each scenario, and where that evidence lives. |
| `$2…` | `--strict` | no | Accepted and ignored. There is no DETECTED verdict this command can return, so there is nothing for it to fail on — saying so is the point. |

With no `<package-path>`, the command asks for one rather than guessing a target.

## Example invocation

```text
/ast:audit-ast02 ./invoice-helper
```

The package argument is still required and still read — AST02 is *declared*, not
skipped. What the command returns is the declaration and its reasons, so the reviewer
leaves with a shortlist of off-artifact evidence rather than a false all-clear.

The empty-tier contract is checkable directly:

```bash
python3 - <<'EOF'
import importlib.util, sys
from pathlib import Path
sys.path.insert(0, '.')          # repo root, so `detectors.scaffold` resolves
spec = importlib.util.spec_from_file_location('ast02_detector',
                                             Path('skills/AST02/scripts/detector.py'))
m = importlib.util.module_from_spec(spec); sys.modules[spec.name] = m
spec.loader.exec_module(m)
print(m.DETECTORS)               # {} - zero detector functions, by design
print(m.run_all(pkg))            # []
print(m.f1_report([]))           # {'status': 'declared-and-uncovered', 'f1': None}
EOF
```

## Output

```text
PACKAGE:  ./invoice-helper
CATEGORY: AST02 - Supply Chain Compromise

STATUS:   DECLARED-AND-UNCOVERED
CHECKS RUN:  0 - this category ships zero detector functions by design
REGISTRY:    4 named scenario(s): 1 static-detectable, 0 agent-judgable, 3 out-of-artifact
NOT DECIDED: 3 out-of-artifact scenarios are not decidable from one package
F1:          not published
             status=declared-and-uncovered, scope=none, corpus=0 case(s)
```

`DECLARED-AND-UNCOVERED` is a verdict, not an error. It says AST02 was considered
and found undecidable from this artifact — which is a different, and far more useful,
statement than a silent pass.

## Coverage caveat

AST02's one static-detectable scenario (AST02-S03 Config-File Hijacking) is already
exercised at `covers: full` by AST01's destructive-postinstall fixture pair, so it is not
listed as uncovered here. AST02 itself publishes no F1: the three scenarios it would have to
label are all out-of-artifact.

## Related

- `/ast:audit-skill-package` — the same package across all ten categories in one sweep.
- `/ast:check-coverage AST02` — the full per-scenario tiering and the written reason
  behind every uncovered row above.
- `/ast:triage-finding` — when you have a finding in prose and do not yet know it is
  AST02.
- `skills/AST02/coverage-matrix.md` — the authority this command's footer is read from.

