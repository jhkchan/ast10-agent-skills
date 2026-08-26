---
name: audit-ast09
description: >-
  Audit one candidate skill package against OWASP AST09 - No Governance alone, using the
  ast09-no-governance skill's decision rules and the frozen per-scenario detectability
  contract in skills/AST09/coverage-matrix.md. This category's declared-detectable tier is
  empty, so the command publishes no F1 and no DETECTED/CLEAN verdicts — it reports
  declared-and-uncovered and names the off-artifact evidence a reviewer has to gather
  instead.
nl_triggers:
  - "no skill inventory"
  - "no approval workflow"
  - "orphaned skill after offboarding"
  - "audit trail for skills"
  - "AST09 audit"
  - "bilateral receipt logging"
  - "regulated data with no record"
  - "unreachable skill in a SaaS platform"
routes_to: ast09-no-governance
ast_category: AST09
---

# /owasp-ast10:audit-ast09

Activates the `ast09-no-governance` skill (`skills/AST09/`) and audits one candidate skill
package against **AST09 - No Governance** and nothing else. Use `/owasp-ast10:audit-skill-package`
when you want all ten categories in one pass.

## What AST09 actually is

The only category where all seven named scenarios are out-of-artifact. The constructive half
is the audit-record design: a compliance-grade trail is a *bilateral receipt* — an admission
record written when the skill is allowed to act and an outcome record written when it
finishes, joined by a shared `attempt_id`. One-sided logging cannot distinguish "never
attempted" from "attempted and lost".

**Seam.** AST09 is the absence of process. When a finding is "nobody knew this was
installed", the root cause is AST09 even if the skill itself would also have tripped AST01.

## What it does

1. Normalises the package into the detector's input shape — `{"manifest": {...},
   "files": {"<relative/path>": "<text>"}}`. A `skill.usf.yaml` is read for the
   manifest half; a bare `SKILL.md` package yields an empty manifest, which is itself
   a finding in several categories.
2. Confirms `skills/AST09/scripts/detector.py` ships zero detector functions —
   deliberate, per the empty-detectable-tier rule: a category whose declared-detectable
   tier is empty publishes no F1 rather than padding a corpus to manufacture one.
3. Reads `scenarios/registry.yaml` and `skills/AST09/coverage-matrix.md` and reports
   each named scenario with the written reason it is not decidable from one package.
4. Applies the `ast09-no-governance` skill's decision rules to name the evidence that
   *would* decide each scenario, and where that evidence lives.

## Why there is nothing to run

| Scenario | Tier | Why one package cannot decide it |
| --- | --- | --- |
| AST09-S01 Undetected Compromise | out-of-artifact | "no alert fires because no inventory exists" is a statement about the organisation's monitoring |
| AST09-S02 Unapproved Malicious Skill | out-of-artifact | approval status is a property of the installing organisation's process |
| AST09-S03 Orphaned Skill | out-of-artifact | employment status and credential lifecycle are HR and IAM state |
| AST09-S04 Regulatory Exposure | out-of-artifact | data classification and jurisdiction are maintained outside the package |
| AST09-S05 Unreachable Skill | out-of-artifact | the whitepaper's own framing forecloses artifact analysis — "there is no host to scan and no local package manifest to read" |
| AST09-S06 Cascading Agent Compromise | out-of-artifact | propagation depends on pipeline topology and where human checkpoints sit |
| AST09-S07 Manipulated Trust Signals | out-of-artifact | stars and install counts are registry-side and platform-side state |

## Arguments

| Position | Argument | Required | Meaning |
| --- | --- | --- | --- |
| `$1` | `<package-path>` | yes | Directory (or archive) of the candidate skill package. Must contain a `SKILL.md`; a `skill.usf.yaml` beside it is read as the manifest. A repo path, an unpacked download, or one of this repo's own `fixtures/` directories all work. |
| `$2…` | `--evidence-plan` | no | Instead of the scenario table, emit the off-artifact evidence a reviewer must gather to decide each scenario, and where that evidence lives. |
| `$2…` | `--strict` | no | Accepted and ignored. There is no DETECTED verdict this command can return, so there is nothing for it to fail on — saying so is the point. |

With no `<package-path>`, the command asks for one rather than guessing a target.

## Example invocation

```text
/owasp-ast10:audit-ast09 ./invoice-helper
```

The package argument is still required and still read — AST09 is *declared*, not
skipped. What the command returns is the declaration and its reasons, so the reviewer
leaves with a shortlist of off-artifact evidence rather than a false all-clear.

The empty-tier contract is checkable directly:

```bash
python3 - <<'EOF'
import importlib.util, sys
from pathlib import Path
sys.path.insert(0, '.')          # repo root, so `detectors.scaffold` resolves
spec = importlib.util.spec_from_file_location('ast09_detector',
                                             Path('skills/AST09/scripts/detector.py'))
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
CATEGORY: AST09 - No Governance

STATUS:   DECLARED-AND-UNCOVERED
CHECKS RUN:  0 - this category ships zero detector functions by design
REGISTRY:    7 named scenario(s): 0 static-detectable, 0 agent-judgable, 7 out-of-artifact
NOT DECIDED: 7 out-of-artifact scenarios are not decidable from one package
F1:          not published
             status=declared-and-uncovered, scope=none, corpus=0 case(s)
```

`DECLARED-AND-UNCOVERED` is a verdict, not an error. It says AST09 was considered
and found undecidable from this artifact — which is a different, and far more useful,
statement than a silent pass.

## Coverage caveat

Every one of the seven turns on organisational process, inventory state, or pipeline
topology. No F1 is publishable for this category at any corpus size.

## Related

- `/owasp-ast10:audit-skill-package` — the same package across all ten categories in one sweep.
- `/owasp-ast10:check-coverage AST09` — the full per-scenario tiering and the written reason
  behind every uncovered row above.
- `/owasp-ast10:triage-finding` — when you have a finding in prose and do not yet know it is
  AST09.
- `skills/AST09/coverage-matrix.md` — the authority this command's footer is read from.

