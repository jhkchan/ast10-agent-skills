---
name: audit-ast10
description: >-
  Audit one candidate skill package against OWASP AST10 - Cross-Platform Reuse alone, using
  the ast10-cross-platform-reuse skill's decision rules and the frozen per-scenario
  detectability contract in skills/AST10/coverage-matrix.md. This category's
  declared-detectable tier is empty, so the command publishes no F1 and no DETECTED/CLEAN
  verdicts — it reports declared-and-uncovered and names the off-artifact evidence a
  reviewer has to gather instead.
nl_triggers:
  - "ported this skill to another platform"
  - "permissions lost in translation"
  - "manifest stripping"
  - "cross registry arbitrage"
  - "AST10 audit"
  - "universal skill format check"
  - "deny_write did not survive the port"
routes_to: ast10-cross-platform-reuse
ast_category: AST10
---

# /ast:audit-ast10

Activates the `ast10-cross-platform-reuse` skill (`skills/AST10/`) and audits one candidate
skill package against **AST10 - Cross-Platform Reuse** and nothing else. Use
`/ast:audit-skill-package` when you want all ten categories in one pass.

## What AST10 actually is

The premise is that a skill's security properties are lost in translation between runtimes,
so the Universal Skill Format manifest is the mitigation and the validator is where the real
work happens. Three USF rules carry the load: `deny_write` always wins over `write` for any
path it lists; network evaluation is default-deny so `deny: "*"` is redundant with — not an
override of — an empty `allow`; and `risk_tier` is an untrusted author assertion that must
be re-derived from the declared permissions.

**Seam.** AST10 is a property that existed on platform A and does not exist on platform B.
If the property never existed anywhere, it is AST03/AST04/AST06 on the platform where it is
missing.

## What it does

1. Normalises the package into the detector's input shape — `{"manifest": {...},
   "files": {"<relative/path>": "<text>"}}`. A `skill.usf.yaml` is read for the
   manifest half; a bare `SKILL.md` package yields an empty manifest, which is itself
   a finding in several categories.
2. Confirms `skills/AST10/scripts/detector.py` ships zero detector functions —
   deliberate, per the empty-detectable-tier rule: a category whose declared-detectable
   tier is empty publishes no F1 rather than padding a corpus to manufacture one.
3. Reads `scenarios/registry.yaml` and `skills/AST10/coverage-matrix.md` and reports
   each named scenario with the written reason it is not decidable from one package.
4. Applies the `ast10-cross-platform-reuse` skill's decision rules to name the evidence that
   *would* decide each scenario, and where that evidence lives.

## Why there is nothing to run

| Scenario | Tier | Why one package cannot decide it |
| --- | --- | --- |
| AST10-S01 Security Property Loss in Translation | out-of-artifact | needs the source-platform manifest to compare the destination against |
| AST10-S02 Cross-Registry Arbitrage | out-of-artifact | a single package in isolation has nothing to be "cross" with |
| AST10-S03 Multi-Platform Campaign | out-of-artifact | needs cross-platform deployment telemetry |
| AST10-S04 Manifest Stripping | out-of-artifact | the stripped field's prior existence lives in the source platform's copy |
| AST10-S05 Implicit Privilege Escalation | out-of-artifact | depends on the destination runtime's default, not on the package |

## Arguments

| Position | Argument | Required | Meaning |
| --- | --- | --- | --- |
| `$1` | `<package-path>` | yes | Directory (or archive) of the candidate skill package. Must contain a `SKILL.md`; a `skill.usf.yaml` beside it is read as the manifest. A repo path, an unpacked download, or one of this repo's own `fixtures/` directories all work. |
| `$2…` | `--evidence-plan` | no | Instead of the scenario table, emit the off-artifact evidence a reviewer must gather to decide each scenario, and where that evidence lives. |
| `$2…` | `--strict` | no | Accepted and ignored. There is no DETECTED verdict this command can return, so there is nothing for it to fail on — saying so is the point. |

With no `<package-path>`, the command asks for one rather than guessing a target.

## Example invocation

```text
/ast:audit-ast10 ./invoice-helper
```

The package argument is still required and still read — AST10 is *declared*, not
skipped. What the command returns is the declaration and its reasons, so the reviewer
leaves with a shortlist of off-artifact evidence rather than a false all-clear.

The empty-tier contract is checkable directly:

```bash
python3 - <<'EOF'
import importlib.util, sys
from pathlib import Path
sys.path.insert(0, '.')          # repo root, so `detectors.scaffold` resolves
spec = importlib.util.spec_from_file_location('ast10_detector',
                                             Path('skills/AST10/scripts/detector.py'))
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
CATEGORY: AST10 - Cross-Platform Reuse

STATUS:   DECLARED-AND-UNCOVERED
CHECKS RUN:  0 - this category ships zero detector functions by design
REGISTRY:    6 named scenario(s): 1 static-detectable, 0 agent-judgable, 5 out-of-artifact
UNCOVERED:   1 static-detectable scenario with no labeled fixture: AST10-S06
NOT DECIDED: 5 out-of-artifact scenarios are not decidable from one package
F1:          not published
             status=declared-and-uncovered, scope=none, corpus=0 case(s)
```

`DECLARED-AND-UNCOVERED` is a verdict, not an error. It says AST10 was considered
and found undecidable from this artifact — which is a different, and far more useful,
statement than a silent pass.

## Coverage caveat

Reconciliation moved this category off "nothing here is detectable". AST10-S06 (Silent
Supply Chain Injection) names an encoded script block — a byte pattern in the package — so
the registry tiers it static-detectable. It is unlabeled, so AST10 still publishes no F1,
but it is declared-and-uncovered with a known gap rather than declared-and-undetectable.
Labeling it would set this category's expected corpus to 6.

## Related

- `/ast:audit-skill-package` — the same package across all ten categories in one sweep.
- `/ast:check-coverage AST10` — the full per-scenario tiering and the written reason
  behind every uncovered row above.
- `/ast:triage-finding` — when you have a finding in prose and do not yet know it is
  AST10.
- `/ast:validate-usf-manifest` — the executable half of this category: the USF rules
  live in `validators/usf.py`, not in a detector function.
- `skills/AST10/coverage-matrix.md` — the authority this command's footer is read from.

