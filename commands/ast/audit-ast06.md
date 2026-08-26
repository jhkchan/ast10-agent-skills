---
name: audit-ast06
description: >-
  Audit one candidate skill package against OWASP AST06 - Weak Isolation alone, using the
  ast06-weak-isolation skill's decision rules and the frozen per-scenario detectability
  contract in skills/AST06/coverage-matrix.md. Runs the 5 mechanical check(s) this category
  implements - two covering AST06-S01, three not covering any named scenario - then reports
  the tiering gap the run did not close.
nl_triggers:
  - "is this skill sandboxed"
  - "runs with full host access"
  - "no isolation declared"
  - "skill shadowing in a workspace"
  - "AST06 audit"
  - "unrestricted shell exec"
  - "localhost websocket exposure"
routes_to: ast06-weak-isolation
ast_category: AST06
---

# /owasp-ast10:audit-ast06

Activates the `ast06-weak-isolation` skill (`skills/AST06/`) and audits one candidate skill
package against **AST06 - Weak Isolation** and nothing else. Use `/owasp-ast10:audit-skill-package`
when you want all ten categories in one pass.

## What AST06 actually is

The default is the vulnerability. Skills execute in the host agent's own security context
unless a sandbox is both available and on by default, and ClawJacked / CVE-2026-32025 is the
whitepaper's evidence that opt-in isolation is isolation nobody opted into. Workspace
precedence is the second seam: a workspace-level skill that shadows a trusted global one
needs no escape at all.

**Seam.** AST06 is the absence of a boundary. AST03 is a boundary drawn too generously.
AST10 is a boundary that existed on the source platform and did not survive the port.

## What it does

1. Normalises the package into the detector's input shape — `{"manifest": {...},
   "files": {"<relative/path>": "<text>"}}`. A `skill.usf.yaml` is read for the
   manifest half; a bare `SKILL.md` package yields an empty manifest, which is itself
   a finding in several categories.
2. Runs every function in `skills/AST06/scripts/detector.py`'s `DETECTORS` map
   (`run_all(pkg)`), each returning a `Finding(scenario, detected, evidence)`.
3. Cross-reads `skills/AST06/coverage-matrix.md` and `scenarios/registry.yaml`
   so the report states what the run did **not** decide, not just what it found.
4. Applies the `ast06-weak-isolation` skill's decision rules to every DETECTED finding to
   produce remediation, and to separate this category from its neighbours.

## Checks this command runs

`Tier` is the check's own mechanism tier: is it decidable from bytes? (It is not read
from `SCENARIO_TIERS`, which mirrors `scenarios/registry.yaml`'s per-SCENARIO tiering
and says nothing about any individual check.) `Covers` is the separate question
(`CHECK_COVERAGE`): does deciding it cover a named whitepaper scenario? Only the first two do, and they decide the two disjuncts of the same
scenario — AST06-S01 Host Escape — which is why the published F1 is `mixed-proxy`.

| Check id | Tier | Covers | Fires when |
| --- | --- | --- | --- |
| `AST06-host-persistence-write` | static-detectable | AST06-S01 (full) | a bundled script shell-execs, or writes a file, into a host-persistence path outside the package |
| `AST06-root-write-scope` | static-detectable | AST06-S01 (full) | a declared write scope reaches the filesystem root or the home directory, or explicitly names a host path |
| `AST06-unrestricted-shell-exec` | static-detectable | category-precondition | shell is allowed with no bounding `commands` allow-list (a wildcard entry does not bound) — the skill can run anything the host user can |
| `AST06-unscoped-shared-state-write` | static-detectable | artifact-signal-only | declared writes to shared workspace, memory or credential paths with no agent-scoped namespace (AST06-S05's signal, not AST06-S05) |
| `AST06-missing-sandbox-declaration` | static-detectable | artifact-signal-only | there is no `permissions` block at all, or it is empty, so no isolation posture is declared and the runtime default decides |
| `AST06-cross-skill-data-leak` | out-of-artifact | — | *not implemented as code, and not implementable* — whether two skills share writable state is a deployment fact the package cannot assert |

Check ids are the detector's own, not registry scenario ids (`AST06-S01`, `AST06-S02`, …).
Which registry scenario each check maps to — and how honestly it measures that scenario,
versus measuring an enabling artifact signal — is recorded in `fixtures/manifest.yaml`'s
`covers:` field and expanded by `/owasp-ast10:check-coverage AST06`.

## Arguments

| Position | Argument | Required | Meaning |
| --- | --- | --- | --- |
| `$1` | `<package-path>` | yes | Directory (or archive) of the candidate skill package. Must contain a `SKILL.md`; a `skill.usf.yaml` beside it is read as the manifest. A repo path, an unpacked download, or one of this repo's own `fixtures/` directories all work. |
| `$2…` | `--strict` | no | Exit non-zero on any DETECTED finding. Without it the command reports and returns. |
| `$2…` | `--evidence-only` | no | Print the raw `Finding` triples and skip the remediation prose. |

With no `<package-path>`, the command asks for one rather than guessing a target.

## Example invocation

```text
/owasp-ast10:audit-ast06 ./invoice-helper
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
spec = importlib.util.spec_from_file_location('ast06_detector',
                                             Path('skills/AST06/scripts/detector.py'))
m = importlib.util.module_from_spec(spec); sys.modules[spec.name] = m
spec.loader.exec_module(m)
for f in m.run_all(pkg):         # pkg = the normalised package dict
    print(f.scenario, f.detected, f.evidence)
EOF
```

## Output

```text
PACKAGE:  ./invoice-helper
CATEGORY: AST06 - Weak Isolation

CHECK:    AST06-host-persistence-write
VERDICT:  CLEAN
EVIDENCE: no bundled script writes or execs into a host-persistence path
TIER:     static-detectable   COVERS: AST06-S01 (full)

CHECK:    AST06-root-write-scope
VERDICT:  CLEAN
EVIDENCE: declared write scope is bounded to the package directory
TIER:     static-detectable   COVERS: AST06-S01 (full)

CHECK:    AST06-unrestricted-shell-exec
VERDICT:  DETECTED
EVIDENCE: shell.allowed with no commands allow-list
TIER:     static-detectable   COVERS: category-precondition

CHECK:    AST06-unscoped-shared-state-write
VERDICT:  CLEAN
EVIDENCE: no declared write into a shared, un-namespaced path
TIER:     static-detectable   COVERS: artifact-signal-only

CHECK:    AST06-missing-sandbox-declaration
VERDICT:  CLEAN
EVIDENCE: permissions block present
TIER:     static-detectable   COVERS: artifact-signal-only

CHECKS RUN:  5 detector check(s), 1 DETECTED — 0 of them covering a named scenario
REGISTRY:    5 named scenario(s): 1 static-detectable, 0 agent-judgable, 4 out-of-artifact
NOT DECIDED: 4 out-of-artifact scenarios are not decidable from one package
F1:          scenario-level 1.00 (AST06-S01, n=4); artifact-signal-only 1.00 (n=2)
             status=proxy-covered, scope=mixed-proxy, corpus=6 case(s)
```

The coverage footer is not decoration. A DETECTED-free run of this command means
"none of the 5 implemented checks fired", never "AST06 is clean".

## Coverage caveat

Two checks measure the category's one static-detectable scenario (AST06-S01 Host Escape)
from two angles — write scope reaching filesystem root, and unrestricted privilege
escalation. The third is an artifact-signal proxy for AST06-S05, which is out-of-artifact
because whether two agents share writable state is a deployment fact.

## Related

- `/owasp-ast10:audit-skill-package` — the same package across all ten categories in one sweep.
- `/owasp-ast10:check-coverage AST06` — the full per-scenario tiering and the written reason
  behind every uncovered row above.
- `/owasp-ast10:triage-finding` — when you have a finding in prose and do not yet know it is
  AST06.
- `skills/AST06/coverage-matrix.md` — the authority this command's footer is read from.

