---
name: audit-ast04
description: >-
  Audit one candidate skill package against OWASP AST04 - Insecure Metadata alone, using the
  ast04-insecure-metadata skill's decision rules and the frozen per-scenario detectability
  contract in skills/AST04/coverage-matrix.md. Runs the 6 static-detectable check(s) this
  category implements, then reports the tiering gap the run did not close.
nl_triggers:
  - "is this manifest lying"
  - "unsafe yaml in frontmatter"
  - "risk_tier spoofing"
  - "permission understating"
  - "zero-width characters in metadata"
  - "AST04 audit"
  - "brand impersonating skill name"
  - "prototype pollution in skill metadata"
routes_to: ast04-insecure-metadata
ast_category: AST04
---

# /ast10:audit-ast04

Activates the `ast04-insecure-metadata` skill (`skills/AST04/`) and audits one candidate
skill package against **AST04 - Insecure Metadata** and nothing else. Use
`/ast10:audit-skill-package` when you want all ten categories in one pass.

## What AST04 actually is

The manifest is parsed *before* anything decides whether the skill is trustworthy, so the
parser is inside the trust boundary and the metadata is outside it. `yaml.load(...,
Loader=UnsafeLoader)` over frontmatter is arbitrary code execution during the review step
itself. The second half is assertion trust: `risk_tier` is an author claim, and it MUST be
independently derived from the declared permissions rather than believed.

**Seam.** AST04 is the metadata lying or the parser being unsafe. AST01 is the body being
malicious while the metadata tells the truth.

## What it does

1. Normalises the package into the detector's input shape — `{"manifest": {...},
   "files": {"<relative/path>": "<text>"}}`. A `skill.usf.yaml` is read for the
   manifest half; a bare `SKILL.md` package yields an empty manifest, which is itself
   a finding in several categories.
2. Runs every function in `skills/AST04/scripts/detector.py`'s `DETECTORS` map
   (`run_all(pkg)`), each returning a `Finding(scenario, detected, evidence)`.
3. Cross-reads `skills/AST04/coverage-matrix.md` and `scenarios/registry.yaml`
   so the report states what the run did **not** decide, not just what it found.
4. Applies the `ast04-insecure-metadata` skill's decision rules to every DETECTED finding to
   produce remediation, and to separate this category from its neighbours.

## Checks this command runs

| Check id | Tier | Fires when |
| --- | --- | --- |
| `AST04-permission-understating` | static-detectable | a bundled script reaches an `http(s)` host that `permissions.network.allow` does not permit, evaluated default-deny and host-exact (AST04-S02) |
| `AST04-risk-tier-spoofing` | static-detectable | the declared `risk_tier` ranks below the floor `validators/usf.py::derive_risk_tier` computes from the declared permission scope (AST04-S03) |
| `AST04-yaml-injection` | static-detectable | a `!!python/…` construction tag appears in shipped YAML or a SKILL.md frontmatter block, or bundled Python opts into an unsafe deserializer (`yaml.unsafe_load`, `Loader=yaml.UnsafeLoader`, a bare `yaml.load`) |
| `AST04-json-injection` | static-detectable | prototype-pollution keys (`__proto__`, `constructor`, `prototype`) appear in JSON metadata |
| `AST04-toml-injection` | static-detectable | a single-bracket `[table]` is redefined (a precedence violation `tomllib` refuses to parse), or an unexpected top-level TOML key smuggles configuration past the schema |
| `AST04-invisible-unicode-smuggling` | static-detectable | zero-width, bidi-override or word-joiner code points hide instructions inside the frontmatter or description |

Check ids are the detector's own, not registry scenario ids (`AST04-S01`, `AST04-S02`, …).
Which registry scenario each check maps to — and how honestly it measures that scenario,
versus measuring an enabling artifact signal — is recorded in `fixtures/manifest.yaml`'s
`covers:` field and expanded by `/ast10:check-coverage AST04`.

## Arguments

| Position | Argument | Required | Meaning |
| --- | --- | --- | --- |
| `$1` | `<package-path>` | yes | Directory (or archive) of the candidate skill package. Must contain a `SKILL.md`; a `skill.usf.yaml` beside it is read as the manifest. A repo path, an unpacked download, or one of this repo's own `fixtures/` directories all work. |
| `$2…` | `--strict` | no | Exit non-zero on any DETECTED finding. Without it the command reports and returns. |
| `$2…` | `--evidence-only` | no | Print the raw `Finding` triples and skip the remediation prose. |

With no `<package-path>`, the command asks for one rather than guessing a target.

## Example invocation

```text
/ast10:audit-ast04 ./invoice-helper
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
spec = importlib.util.spec_from_file_location('ast04_detector',
                                             Path('skills/AST04/scripts/detector.py'))
m = importlib.util.module_from_spec(spec); sys.modules[spec.name] = m
spec.loader.exec_module(m)
for f in m.run_all(pkg):         # pkg = the normalised package dict
    print(f.scenario, f.detected, f.evidence)
EOF
```

## Output

```text
PACKAGE:  ./invoice-helper
CATEGORY: AST04 - Insecure Metadata

CHECK:    AST04-yaml-injection
VERDICT:  DETECTED
EVIDENCE: scripts/setup.py: Loader=yaml.UnsafeLoader
TIER:     static-detectable

CHECK:    AST04-json-injection
VERDICT:  CLEAN
EVIDENCE: no prototype-pollution keys found
TIER:     static-detectable

CHECK:    AST04-toml-injection
VERDICT:  CLEAN
EVIDENCE: no unexpected top-level TOML keys found
TIER:     static-detectable

CHECK:    AST04-invisible-unicode-smuggling
VERDICT:  CLEAN
EVIDENCE: no invisible Unicode control code points found
TIER:     static-detectable

CHECKS RUN:  6 detector check(s) at the static-detectable tier, 1 DETECTED
REGISTRY:    7 named scenario(s): 5 static-detectable, 1 agent-judgable, 1 out-of-artifact
UNCOVERED:   2 static-detectable scenarios with no labeled fixture: AST04-S02, AST04-S03
NOT DECIDED: 1 agent-judgable scenario needs a judge, not this run
NOT DECIDED: 1 out-of-artifact scenario is not decidable from one package
F1:          scenario-level 1.00 (n=10)
             status=covered, scope=scenario-level, corpus=10 case(s)
```

The coverage footer is not decoration. A DETECTED-free run of this command means
"none of the 6 implemented checks fired", never "AST04 is clean".

## Coverage caveat

The only category whose corpus and the registry agreed outright: all three labeled checks
map one-to-one onto registry scenarios the registry independently tiers static-detectable.
Two named static-detectable scenarios stay unlabeled (AST04-S02 Permission Understating,
AST04-S03 Risk Tier Spoofing); labeling them would raise this category's expected corpus
from 6 to 10.

## Related

- `/ast10:audit-skill-package` — the same package across all ten categories in one sweep.
- `/ast10:check-coverage AST04` — the full per-scenario tiering and the written reason
  behind every uncovered row above.
- `/ast10:triage-finding` — when you have a finding in prose and do not yet know it is
  AST04.
- `skills/AST04/coverage-matrix.md` — the authority this command's footer is read from.

