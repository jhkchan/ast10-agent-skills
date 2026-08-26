---
name: audit-ast03
description: >-
  Audit one candidate skill package against OWASP AST03 - Over-Privileged Skills alone,
  using the ast03-over-privileged-skills skill's decision rules and the frozen per-scenario
  detectability contract in skills/AST03/coverage-matrix.md. Runs the 4 static-detectable
  check(s) this category implements, then reports the tiering gap the run did not close.
nl_triggers:
  - "is this skill over-privileged"
  - "permission manifest too broad"
  - "least privilege for a skill"
  - "confused deputy between skills"
  - "LPCI check"
  - "AST03 audit"
  - "does this skill need shell and network"
  - "write access to secrets"
routes_to: ast03-over-privileged-skills
ast_category: AST03
---

# /owasp-ast10:audit-ast03

Activates the `ast03-over-privileged-skills` skill (`skills/AST03/`) and audits one
candidate skill package against **AST03 - Over-Privileged Skills** and nothing else. Use
`/owasp-ast10:audit-skill-package` when you want all ten categories in one pass.

## What AST03 actually is

Over-privilege here is not a static grant problem alone. Logic-layer Prompt Control
Injection (LPCI, arXiv:2507.10457) exercises permissions that were granted-but-unintended,
so a manifest that passes review at install time is still the attack surface at runtime. The
confused-deputy chain is the second seam: a low-privilege skill's request honored by a
high-privilege one means the effective permission set is the union across the chain, not the
manifest in front of you.

**Seam.** AST03 is the permission being too wide. AST06 is there being no boundary at all. A
skill with a tight manifest that the runtime ignores is AST06, not AST03.

## What it does

1. Normalises the package into the detector's input shape — `{"manifest": {...},
   "files": {"<relative/path>": "<text>"}}`. A `skill.usf.yaml` is read for the
   manifest half; a bare `SKILL.md` package yields an empty manifest, which is itself
   a finding in several categories.
2. Runs every function in `skills/AST03/scripts/detector.py`'s `DETECTORS` map
   (`run_all(pkg)`), each returning a `Finding(scenario, detected, evidence)`.
3. Cross-reads `skills/AST03/coverage-matrix.md` and `scenarios/registry.yaml`
   so the report states what the run did **not** decide, not just what it found.
4. Applies the `ast03-over-privileged-skills` skill's decision rules to every DETECTED
   finding to produce remediation, and to separate this category from its neighbours.

## Checks this command runs

| Check id | Tier | Fires when |
| --- | --- | --- |
| `AST03-identity-file-write-grant` | static-detectable | a declared `write` entry reaches `SOUL.md`, `MEMORY.md` or `AGENTS.md` and no `deny_write` entry shadows it — the only check here that decides a named registry scenario (AST03-S03) |
| `AST03-unbounded-write-scope` | static-detectable | no write floor is declared at all: no permissions block, or a files block with no `deny_write` key. An explicitly empty `deny_write: []` is a stated floor and does not fire |
| `AST03-shell-network-privilege-combo` | static-detectable | shell execution *and* an unbounded egress declaration are granted together, which is the exfiltration primitive |
| `AST03-wildcard-network-egress` | static-detectable | egress is declared as a blanket (`network: true`, `policy: allow-all`, or an allowlist entry carrying a glob) rather than an enumerated domain list |
| `AST03-task-scope-mismatch` | agent-judgable | *not implemented as code* — deciding a permission is broader than the skill's *stated function* needs the stated function read as prose |

Check ids are the detector's own, not registry scenario ids (`AST03-S01`, `AST03-S02`, …).
Which registry scenario each check maps to — and how honestly it measures that scenario,
versus measuring an enabling artifact signal — is recorded in `fixtures/manifest.yaml`'s
`covers:` field and expanded by `/owasp-ast10:check-coverage AST03`.

## Arguments

| Position | Argument | Required | Meaning |
| --- | --- | --- | --- |
| `$1` | `<package-path>` | yes | Directory (or archive) of the candidate skill package. Must contain a `SKILL.md`; a `skill.usf.yaml` beside it is read as the manifest. A repo path, an unpacked download, or one of this repo's own `fixtures/` directories all work. |
| `$2…` | `--strict` | no | Exit non-zero on any DETECTED finding. Without it the command reports and returns. |
| `$2…` | `--evidence-only` | no | Print the raw `Finding` triples and skip the remediation prose. |

With no `<package-path>`, the command asks for one rather than guessing a target.

## Example invocation

```text
/owasp-ast10:audit-ast03 ./invoice-helper
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
spec = importlib.util.spec_from_file_location('ast03_detector',
                                             Path('skills/AST03/scripts/detector.py'))
m = importlib.util.module_from_spec(spec); sys.modules[spec.name] = m
spec.loader.exec_module(m)
for f in m.run_all(pkg):         # pkg = the normalised package dict
    print(f.scenario, f.detected, f.evidence)
EOF
```

## Output

```text
PACKAGE:  ./invoice-helper
CATEGORY: AST03 - Over-Privileged Skills

CHECK:    AST03-unbounded-write-scope
VERDICT:  DETECTED
EVIDENCE: permissions declares no deny_write key: no write floor survives a port
TIER:     static-detectable

CHECK:    AST03-shell-network-privilege-combo
VERDICT:  DETECTED
EVIDENCE: shell_granted=True network_unbounded=True allowlist=['*']
TIER:     static-detectable

CHECKS RUN:  4 detector check(s) at the static-detectable tier, 2 DETECTED
REGISTRY:    5 named scenario(s): 1 static-detectable, 1 agent-judgable, 3 out-of-artifact
NOT DECIDED: 1 agent-judgable scenario needs a judge, not this run
NOT DECIDED: 3 out-of-artifact scenarios are not decidable from one package
F1:          scenario-level 1.00 (AST03-S03, n=2); artifact-signal-only 1.00 (n=4)
             status=proxy-covered, scope=mixed-proxy, corpus=6 case(s)
```

The coverage footer is not decoration. A DETECTED-free run of this command means
"none of the 4 implemented checks fired", never "AST03 is clean".

## Coverage caveat

Only one of the three labeled checks measures a named scenario (AST03-S03 Identity File
Backdoors). The other two measure artifact signals for an agent-judgable scenario
(AST03-S01) and an out-of-artifact one (AST06-S02), so two thirds of this category's F1 is
proxy F1 and must be reported as such.

## Related

- `/owasp-ast10:audit-skill-package` — the same package across all ten categories in one sweep.
- `/owasp-ast10:check-coverage AST03` — the full per-scenario tiering and the written reason
  behind every uncovered row above.
- `/owasp-ast10:triage-finding` — when you have a finding in prose and do not yet know it is
  AST03.
- `skills/AST03/coverage-matrix.md` — the authority this command's footer is read from.

