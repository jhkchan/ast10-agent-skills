---
name: audit-ast05
description: >-
  Audit one candidate skill package against OWASP AST05 - Untrusted External Instructions
  alone, using the ast05-untrusted-external-instructions skill's decision rules and the
  frozen per-scenario detectability contract in skills/AST05/coverage-matrix.md. Runs the 2
  static-detectable check(s) this category implements, then reports the tiering gap the run
  did not close.
nl_triggers:
  - "skill fetches a remote runbook"
  - "rug pull on a referenced document"
  - "bait and switch review"
  - "unpinned external reference"
  - "AST05 audit"
  - "is fetched content treated as instruction"
  - "wildcard domain allowlist"
routes_to: ast05-untrusted-external-instructions
ast_category: AST05
---

# /ast:audit-ast05

Activates the `ast05-untrusted-external-instructions` skill (`skills/AST05/`) and audits one
candidate skill package against **AST05 - Untrusted External Instructions** and nothing
else. Use `/ast:audit-skill-package` when you want all ten categories in one pass.

## What AST05 actually is

This is the category where the artifact is honest and the danger is elsewhere. Author
Rug-Pull needs the remote document at two points in time; Reviewer Bait-and-Switch needs two
fetch vantage points; transitive chaining needs the chain actually followed; relay
amplification needs the pipeline's per-node backbone models. None of that is in the package.
What the package *can* show is the enabling precondition: an unpinned reference and an
absent data/instruction boundary marker.

**Seam.** AST05 is external content the skill *pulls in*. AST02 is external content the
skill *is built from*. A poisoned dependency is AST02; a poisoned runbook URL the skill
reads at runtime is AST05.

## What it does

1. Normalises the package into the detector's input shape — `{"manifest": {...},
   "files": {"<relative/path>": "<text>"}}`. A `skill.usf.yaml` is read for the
   manifest half; a bare `SKILL.md` package yields an empty manifest, which is itself
   a finding in several categories.
2. Runs every function in `skills/AST05/scripts/detector.py`'s `DETECTORS` map
   (`run_all(pkg)`), each returning a `Finding(scenario, detected, evidence)`.
3. Cross-reads `skills/AST05/coverage-matrix.md` and `scenarios/registry.yaml`
   so the report states what the run did **not** decide, not just what it found.
4. Applies the `ast05-untrusted-external-instructions` skill's decision rules to every
   DETECTED finding to produce remediation, and to separate this category from its
   neighbours.

## Checks this command runs

| Check id | Tier | Fires when |
| --- | --- | --- |
| `AST05-unrestricted-network-fetch` | static-detectable | `network.policy == "allow-all"` — no host the skill fetches from is out of bounds |
| `AST05-wildcard-domain-allowlist` | static-detectable | the allow-list is nominally set but carries a wildcard entry, which is default-allow wearing a default-deny costume |
| `AST05-injected-instruction-compliance` | agent-judgable | *not implemented as code* — deciding that fetched text was *followed as instruction* rather than *used as data* is a reading of behaviour, not of bytes |

Check ids are the detector's own, not registry scenario ids (`AST05-S01`, `AST05-S02`, …).
Which registry scenario each check maps to — and how honestly it measures that scenario,
versus measuring an enabling artifact signal — is recorded in `fixtures/manifest.yaml`'s
`covers:` field and expanded by `/ast:check-coverage AST05`.

## Arguments

| Position | Argument | Required | Meaning |
| --- | --- | --- | --- |
| `$1` | `<package-path>` | yes | Directory (or archive) of the candidate skill package. Must contain a `SKILL.md`; a `skill.usf.yaml` beside it is read as the manifest. A repo path, an unpacked download, or one of this repo's own `fixtures/` directories all work. |
| `$2…` | `--strict` | no | Exit non-zero on any DETECTED finding. Without it the command reports and returns. |
| `$2…` | `--evidence-only` | no | Print the raw `Finding` triples and skip the remediation prose. |

With no `<package-path>`, the command asks for one rather than guessing a target.

## Example invocation

```text
/ast:audit-ast05 ./invoice-helper
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
spec = importlib.util.spec_from_file_location('ast05_detector',
                                             Path('skills/AST05/scripts/detector.py'))
m = importlib.util.module_from_spec(spec); sys.modules[spec.name] = m
spec.loader.exec_module(m)
for f in m.run_all(pkg):         # pkg = the normalised package dict
    print(f.scenario, f.detected, f.evidence)
EOF
```

## Output

```text
PACKAGE:  ./invoice-helper
CATEGORY: AST05 - Untrusted External Instructions

CHECK:    AST05-unrestricted-network-fetch
VERDICT:  DETECTED
EVIDENCE: network.policy=allow-all
TIER:     static-detectable

CHECK:    AST05-wildcard-domain-allowlist
VERDICT:  CLEAN
EVIDENCE: not in allow-list mode
TIER:     static-detectable

CHECKS RUN:  2 detector check(s) at the static-detectable tier, 1 DETECTED
REGISTRY:    6 named scenario(s): 0 static-detectable, 1 agent-judgable, 5 out-of-artifact
NOT DECIDED: 1 agent-judgable scenario needs a judge, not this run
NOT DECIDED: 5 out-of-artifact scenarios are not decidable from one package
F1:          not published (pending-detector)
             status=proxy-covered, scope=artifact-signal-only, corpus=6 case(s)
```

The coverage footer is not decoration. A DETECTED-free run of this command means
"none of the 2 implemented checks fired", never "AST05 is clean".

## Coverage caveat

The sharpest reconciliation finding in the repo. The registry tiers NONE of AST05's six
named scenarios static-detectable, so every case in this corpus measures an artifact signal,
never a named scenario. Any F1 published here must be labeled `artifact-signal-only` or it
overclaims.

## Related

- `/ast:audit-skill-package` — the same package across all ten categories in one sweep.
- `/ast:check-coverage AST05` — the full per-scenario tiering and the written reason
  behind every uncovered row above.
- `/ast:triage-finding` — when you have a finding in prose and do not yet know it is
  AST05.
- `skills/AST05/coverage-matrix.md` — the authority this command's footer is read from.

