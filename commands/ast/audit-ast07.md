---
name: audit-ast07
description: >-
  Audit one candidate skill package against OWASP AST07 - Update Drift alone, using the
  ast07-update-drift skill's decision rules and the frozen per-scenario detectability
  contract in skills/AST07/coverage-matrix.md. This category's declared-detectable tier is
  empty, so the command publishes no F1 and no DETECTED/CLEAN verdicts — it reports
  declared-and-uncovered and names the off-artifact evidence a reviewer has to gather
  instead.
nl_triggers:
  - "is this skill pinned"
  - "auto update risk"
  - "rollback attack"
  - "hot reload abuse"
  - "version range instead of a hash"
  - "AST07 audit"
  - "stale skill version"
  - "did the update change what I reviewed"
routes_to: ast07-update-drift
ast_category: AST07
---

# /ast:audit-ast07

Activates the `ast07-update-drift` skill (`skills/AST07/`) and audits one candidate skill
package against **AST07 - Update Drift** and nothing else. Use `/ast:audit-skill-package`
when you want all ten categories in one pass.

## What AST07 actually is

Every AST07 scenario is temporal: it compares two versions or observes a reload event. That
is why pinning is the control and scanning is not. A version range is an unbounded future
grant — the bytes you reviewed are not the bytes that will run. Rollback Attack and
Hot-Reload Abuse are the two named cases where the update channel itself is the payload
delivery path.

**Seam.** AST07 is the *version* being wrong. AST02 is the *source* being wrong. An
auto-update that pulls a legitimately-published malicious release is AST07; the same release
published through a hijacked account is AST02.

## What it does

1. Normalises the package into the detector's input shape — `{"manifest": {...},
   "files": {"<relative/path>": "<text>"}}`. A `skill.usf.yaml` is read for the
   manifest half; a bare `SKILL.md` package yields an empty manifest, which is itself
   a finding in several categories.
2. Confirms `skills/AST07/scripts/detector.py` ships zero detector functions —
   deliberate, per the empty-detectable-tier rule: a category whose declared-detectable
   tier is empty publishes no F1 rather than padding a corpus to manufacture one.
3. Reads `scenarios/registry.yaml` and `skills/AST07/coverage-matrix.md` and reports
   each named scenario with the written reason it is not decidable from one package.
4. Applies the `ast07-update-drift` skill's decision rules to name the evidence that *would*
   decide each scenario, and where that evidence lives.

## Why there is nothing to run

| Scenario | Tier | Why one package cannot decide it |
| --- | --- | --- |
| AST07-S01 Malicious Update | out-of-artifact | requires the prior release to compare the new one against |
| AST07-S02 Rollback Attack | out-of-artifact | a lone package snapshot has no previous version to be a rollback *of* |
| AST07-S03 Hot-Reload Abuse | out-of-artifact | requires the update-event metadata — when a reload happened, from what source — that a static artifact does not carry |

## Arguments

| Position | Argument | Required | Meaning |
| --- | --- | --- | --- |
| `$1` | `<package-path>` | yes | Directory (or archive) of the candidate skill package. Must contain a `SKILL.md`; a `skill.usf.yaml` beside it is read as the manifest. A repo path, an unpacked download, or one of this repo's own `fixtures/` directories all work. |
| `$2…` | `--evidence-plan` | no | Instead of the scenario table, emit the off-artifact evidence a reviewer must gather to decide each scenario, and where that evidence lives. |
| `$2…` | `--strict` | no | Accepted and ignored. There is no DETECTED verdict this command can return, so there is nothing for it to fail on — saying so is the point. |

With no `<package-path>`, the command asks for one rather than guessing a target.

## Example invocation

```text
/ast:audit-ast07 ./invoice-helper
```

The package argument is still required and still read — AST07 is *declared*, not
skipped. What the command returns is the declaration and its reasons, so the reviewer
leaves with a shortlist of off-artifact evidence rather than a false all-clear.

The empty-tier contract is checkable directly:

```bash
python3 - <<'EOF'
import importlib.util, sys
from pathlib import Path
sys.path.insert(0, '.')          # repo root, so `detectors.scaffold` resolves
spec = importlib.util.spec_from_file_location('ast07_detector',
                                             Path('skills/AST07/scripts/detector.py'))
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
CATEGORY: AST07 - Update Drift

STATUS:   DECLARED-AND-UNCOVERED
CHECKS RUN:  0 - this category ships zero detector functions by design
REGISTRY:    3 named scenario(s): 0 static-detectable, 0 agent-judgable, 3 out-of-artifact
NOT DECIDED: 3 out-of-artifact scenarios are not decidable from one package
F1:          not published
             status=declared-and-uncovered, scope=none, corpus=0 case(s)
```

`DECLARED-AND-UNCOVERED` is a verdict, not an error. It says AST07 was considered
and found undecidable from this artifact — which is a different, and far more useful,
statement than a silent pass.

## Coverage caveat

No F1 is publishable for this category at any corpus size. Padding it would measure the
fixture author's imagination, not a detector.

## Related

- `/ast:audit-skill-package` — the same package across all ten categories in one sweep.
- `/ast:check-coverage AST07` — the full per-scenario tiering and the written reason
  behind every uncovered row above.
- `/ast:triage-finding` — when you have a finding in prose and do not yet know it is
  AST07.
- `skills/AST07/coverage-matrix.md` — the authority this command's footer is read from.

