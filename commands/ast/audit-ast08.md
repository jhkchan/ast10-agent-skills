---
name: audit-ast08
description: >-
  Audit one candidate skill package against OWASP AST08 - Poor Scanning alone, using the
  ast08-poor-scanning skill's decision rules and the frozen per-scenario detectability
  contract in skills/AST08/coverage-matrix.md. Runs the 1 static-detectable check(s) this
  category implements, then reports the tiering gap the run did not close.
nl_triggers:
  - "the scanner missed it"
  - "natural language bypass"
  - "obfuscated instruction"
  - "scanner coverage claim"
  - "AST08 audit"
  - "PASS FAIL INCOMPLETE verdict"
  - "shell parsing evasion"
  - "homoglyph smuggling"
routes_to: ast08-poor-scanning
ast_category: AST08
---

# /ast:audit-ast08

Activates the `ast08-poor-scanning` skill (`skills/AST08/`) and audits one candidate skill
package against **AST08 - Poor Scanning** and nothing else. Use `/ast:audit-skill-package`
when you want all ten categories in one pass.

## What AST08 actually is

The scanner's own coverage claim is the artifact under audit here, not the skill.
SkillSpector's result is a PASS/FAIL/INCOMPLETE triple, and collapsing INCOMPLETE into PASS
is the failure this category names. Two structural blind spots: natural-language-only
malicious intent carries no code pattern to match, and shell-parsing evasion (quote removal,
IFS splitting) means the string the scanner reads is not the string the shell runs.

**Seam.** AST08 is a control that *should* have caught it and did not. It is almost always a
*contributing* control failure recorded alongside a primary AST01/AST04 root cause — never
split one finding across both.

## What it does

1. Normalises the package into the detector's input shape — `{"manifest": {...},
   "files": {"<relative/path>": "<text>"}}`. A `skill.usf.yaml` is read for the
   manifest half; a bare `SKILL.md` package yields an empty manifest, which is itself
   a finding in several categories.
2. Runs every function in `skills/AST08/scripts/detector.py`'s `DETECTORS` map
   (`run_all(pkg)`), each returning a `Finding(scenario, detected, evidence)`.
3. Cross-reads `skills/AST08/coverage-matrix.md` and `scenarios/registry.yaml`
   so the report states what the run did **not** decide, not just what it found.
4. Applies the `ast08-poor-scanning` skill's decision rules to every DETECTED finding to
   produce remediation, and to separate this category from its neighbours.

## Checks this command runs

| Check id | Tier | Fires when |
| --- | --- | --- |
| `AST08-invisible-unicode-smuggling` | static-detectable | zero-width, bidi-override and word-joiner code points are present in the package's files or manifest description — content that must be canonicalized before any pattern match is meaningful |
| `AST08-scan-evasion-narrative` | agent-judgable | *not implemented as code* — deciding that prose is *written to evade a scanner* rather than merely verbose is a reading of intent |

Check ids are the detector's own, not registry scenario ids (`AST08-S01`, `AST08-S02`, …).
Which registry scenario each check maps to — and how honestly it measures that scenario,
versus measuring an enabling artifact signal — is recorded in `fixtures/manifest.yaml`'s
`covers:` field and expanded by `/ast:check-coverage AST08`.

## Arguments

| Position | Argument | Required | Meaning |
| --- | --- | --- | --- |
| `$1` | `<package-path>` | yes | Directory (or archive) of the candidate skill package. Must contain a `SKILL.md`; a `skill.usf.yaml` beside it is read as the manifest. A repo path, an unpacked download, or one of this repo's own `fixtures/` directories all work. |
| `$2…` | `--strict` | no | Exit non-zero on any DETECTED finding. Without it the command reports and returns. |
| `$2…` | `--evidence-only` | no | Print the raw `Finding` triples and skip the remediation prose. |

With no `<package-path>`, the command asks for one rather than guessing a target.

## Example invocation

```text
/ast:audit-ast08 ./invoice-helper
```

`invoice-helper` below is a package whose manifest declares no `content_hash`, an
empty `deny_write`, `shell.allowed: true` with no command allow-list, and
`network.policy: allow-all`, and whose `<package>/scripts/setup.py` parses config
through an unsafe YAML loader.

Equivalent deterministic run, straight against the detector module:

```bash
python3 - <<'EOF'
import importlib.util, sys
from pathlib import Path
sys.path.insert(0, '.')          # repo root, so `detectors.scaffold` resolves
spec = importlib.util.spec_from_file_location('ast08_detector',
                                             Path('skills/AST08/scripts/detector.py'))
m = importlib.util.module_from_spec(spec); sys.modules[spec.name] = m
spec.loader.exec_module(m)
for f in m.run_all(pkg):         # pkg = the normalised package dict
    print(f.scenario, f.detected, f.evidence)
EOF
```

## Output

```text
PACKAGE:  ./invoice-helper
CATEGORY: AST08 - Poor Scanning

CHECK:    AST08-invisible-unicode-smuggling
VERDICT:  CLEAN
EVIDENCE: no invisible Unicode control code points found
TIER:     static-detectable

CHECKS RUN:  1 detector check(s) at the static-detectable tier, 0 DETECTED
REGISTRY:    8 named scenario(s): 4 static-detectable, 2 agent-judgable, 2 out-of-artifact
UNCOVERED:   3 static-detectable scenarios with no labeled fixture:
             AST08-S04, AST08-S07, AST08-S08
NOT DECIDED: 2 agent-judgable scenarios need a judge, not this run
NOT DECIDED: 2 out-of-artifact scenarios are not decidable from one package
F1:          not published (pending-detector)
             status=proxy-covered, scope=category-precondition, corpus=6 case(s)
```

The coverage footer is not decoration. A DETECTED-free run of this command means
"the 1 implemented check did not fire", never "AST08 is clean".

## Coverage caveat

The single labeled check maps to no named AST08 scenario at all — it derives from the
category's preventive mitigations. Meanwhile the registry finds four static-detectable named
scenarios here (obfuscated instruction, context-dependent malice / logic bombs, scanner host
compromise, bytecode cache poisoning); one is exercised from AST01's corpus and three are
unlabeled. Labeling all four would raise this category's expected corpus from 6 to 8.

## Related

- `/ast:audit-skill-package` — the same package across all ten categories in one sweep.
- `/ast:check-coverage AST08` — the full per-scenario tiering and the written reason
  behind every uncovered row above.
- `/ast:triage-finding` — when you have a finding in prose and do not yet know it is
  AST08.
- `skills/AST08/coverage-matrix.md` — the authority this command's footer is read from.

