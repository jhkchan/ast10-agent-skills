---
name: audit-ast01
description: >-
  Audit one candidate skill package against OWASP AST01 - Malicious Skills alone, using the
  ast01-malicious-skills skill's decision rules and the frozen per-scenario detectability
  contract in skills/AST01/coverage-matrix.md. Runs the 2 static-detectable check(s) this
  category implements, then reports the tiering gap the run did not close.
nl_triggers:
  - "is this skill malicious"
  - "hidden payload in SKILL.md"
  - "credential stealer in a skill"
  - "check this skill before I install it"
  - "does this package match its signed hash"
  - "AST01 audit"
  - "backdoor in a skill package"
  - "social engineering prose in a skill"
routes_to: ast01-malicious-skills
ast_category: AST01
---

# /ast:audit-ast01

Activates the `ast01-malicious-skills` skill (`skills/AST01/`) and audits one candidate
skill package against **AST01 - Malicious Skills** and nothing else. Use
`/ast:audit-skill-package` when you want all ten categories in one pass.

## What AST01 actually is

AST01 payloads split across two layers that do not share a detector: the code layer
(shell/Python fragments) and the natural-language instruction layer (SKILL.md prose that
persuades the host agent). Three lines of markdown were enough to exfiltrate SSH keys, so a
clean code-layer scan closes nothing. A verified signature answers *who published this*,
never *is this safe* — treat signed-but-unscanned as unscanned.

**Seam.** AST02 owns how the package *reached* you; AST01 owns what is *in* it. AST04 owns a
lying manifest; AST01 owns a truthful manifest over a malicious body.

## What it does

1. Normalises the package into the detector's input shape — `{"manifest": {...},
   "files": {"<relative/path>": "<text>"}}`. A `skill.usf.yaml` is read for the
   manifest half; a bare `SKILL.md` package yields an empty manifest, which is itself
   a finding in several categories.
2. Runs every function in `skills/AST01/scripts/detector.py`'s `DETECTORS` map
   (`run_all(pkg)`), each returning a `Finding(scenario, detected, evidence)`.
3. Cross-reads `skills/AST01/coverage-matrix.md` and `scenarios/registry.yaml`
   so the report states what the run did **not** decide, not just what it found.
4. Applies the `ast01-malicious-skills` skill's decision rules to every DETECTED finding to
   produce remediation, and to separate this category from its neighbours.

## Checks this command runs

| Check id | Tier | Fires when |
| --- | --- | --- |
| `AST01-content-hash-missing` | static-detectable | the manifest declares no signed `content_hash.value`, so there is nothing to verify the shipped bytes against |
| `AST01-content-hash-mismatch` | static-detectable | the declared hash disagrees with a sha256 recomputed over the package's sorted (path, content) pairs |
| `AST01-obfuscated-payload-intent` | agent-judgable | *not implemented as code* — deciding a payload is *intentionally* malicious rather than merely unusual is a semantic reading, not a byte match |

Check ids are the detector's own, not registry scenario ids (`AST01-S01`, `AST01-S02`, …).
Which registry scenario each check maps to — and how honestly it measures that scenario,
versus measuring an enabling artifact signal — is recorded in `fixtures/manifest.yaml`'s
`covers:` field and expanded by `/ast:check-coverage AST01`.

## Arguments

| Position | Argument | Required | Meaning |
| --- | --- | --- | --- |
| `$1` | `<package-path>` | yes | Directory (or archive) of the candidate skill package. Must contain a `SKILL.md`; a `skill.usf.yaml` beside it is read as the manifest. A repo path, an unpacked download, or one of this repo's own `fixtures/` directories all work. |
| `$2…` | `--strict` | no | Exit non-zero on any DETECTED finding. Without it the command reports and returns. |
| `$2…` | `--evidence-only` | no | Print the raw `Finding` triples and skip the remediation prose. |

With no `<package-path>`, the command asks for one rather than guessing a target.

## Example invocation

```text
/ast:audit-ast01 ./invoice-helper
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
spec = importlib.util.spec_from_file_location('ast01_detector',
                                             Path('skills/AST01/scripts/detector.py'))
m = importlib.util.module_from_spec(spec); sys.modules[spec.name] = m
spec.loader.exec_module(m)
for f in m.run_all(pkg):         # pkg = the normalised package dict
    print(f.scenario, f.detected, f.evidence)
EOF
```

## Output

```text
PACKAGE:  ./invoice-helper
CATEGORY: AST01 - Malicious Skills

CHECK:    AST01-content-hash-missing
VERDICT:  DETECTED
EVIDENCE: manifest.content_hash.value is unset
TIER:     static-detectable

CHECK:    AST01-content-hash-mismatch
VERDICT:  CLEAN
EVIDENCE: no declared hash to compare
TIER:     static-detectable

CHECKS RUN:  2 detector check(s) at the static-detectable tier, 1 DETECTED
REGISTRY:    11 named scenario(s): 7 static-detectable, 3 agent-judgable, 1 out-of-artifact
UNCOVERED:   6 static-detectable scenarios with no labeled fixture:
             AST01-S02, AST01-S05, AST01-S06, AST01-S08, AST01-S09, AST01-S11
NOT DECIDED: 3 agent-judgable scenarios need a judge, not this run
NOT DECIDED: 1 out-of-artifact scenario is not decidable from one package
F1:          not published (pending-detector)
             status=covered, scope=scenario-level, corpus=6 case(s)
```

The coverage footer is not decoration. A DETECTED-free run of this command means
"none of the 2 implemented checks fired", never "AST01 is clean".

## Coverage caveat

Two of the three labeled fixture checks are drawn from registry scenarios the whitepaper
files under other categories (AST08-S02, AST02-S03). Recorded, not reassigned — AST01's own
named static-detectable surface is 6 of 7 uncovered.

## Related

- `/ast:audit-skill-package` — the same package across all ten categories in one sweep.
- `/ast:check-coverage AST01` — the full per-scenario tiering and the written reason
  behind every uncovered row above.
- `/ast:triage-finding` — when you have a finding in prose and do not yet know it is
  AST01.
- `skills/AST01/coverage-matrix.md` — the authority this command's footer is read from.

