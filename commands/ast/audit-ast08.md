---
name: audit-ast08
description: >-
  Audit one candidate skill package against OWASP AST08 - Poor Scanning alone, using the
  ast08-poor-scanning skill's decision rules and the frozen per-scenario detectability
  contract in skills/AST08/coverage-matrix.md. Runs the 4 static-detectable check(s) this
  category implements — one per registry scenario the whitepaper's AST08 section makes
  decidable from a package — then reports what the run did not decide.
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

# /ast10:audit-ast08

Activates the `ast08-poor-scanning` skill (`skills/AST08/`) and audits one candidate skill
package against **AST08 - Poor Scanning** and nothing else. Use `/ast10:audit-skill-package`
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
| `AST08-S02` | static-detectable | a detection rule matches a view the raw bytes hid — the normalized view (invisibles stripped, NFKC folded) matching more often than the raw bytes, a decoded layer of an embedded encoding within the depth-4 / 1 MiB bound, or a zero-width run that decodes to text. Never the mere presence of an encoded blob |
| `AST08-S04` | static-detectable | a branch keyed to *which environment is running it* — hostname, username, uid, an env-var comparison, a date comparison, a file-existence or debugger probe — wraps a call that executes, sends, or destroys. Neither half fires alone, and OS-portability branches are excluded by design |
| `AST08-S07` | static-detectable | the package exceeds a declared scan bound: file count, per-file size, a padding run, archive nesting depth, member count, declared decompression ratio, an archive member escaping the extraction root, a symlink escaping the scan root, or a non-regular file |
| `AST08-S08` | static-detectable | a `.pyc` ships whose provenance cannot be tied to shipped source: sourceless, unchecked hash-based, or a header whose recorded source hash or size contradicts the adjacent `.py` |

Check ids ARE the registry's scenario ids here, because each check decides that scenario's
defining condition; `fixtures/manifest.yaml` records all four as `covers: full`. Two of
AST08's eight scenarios (`AST08-S01` Natural-Language Bypass, `AST08-S03` Scanner
Impersonation) are agent-judgable and are not implemented as code — deciding that prose is
*written to evade a scanner* rather than merely verbose is a reading of intent — and two
(`AST08-S05`, `AST08-S06`) are not decidable from one package at all.
`/ast10:check-coverage AST08` expands every row.

An `INCOMPLETE:` prefix on a finding's evidence is not a payload: it means a bound or a
parser stopped the scan, which per this category's own rule is never a clean verdict.

## Arguments

| Position | Argument | Required | Meaning |
| --- | --- | --- | --- |
| `$1` | `<package-path>` | yes | Directory (or archive) of the candidate skill package. Must contain a `SKILL.md`; a `skill.usf.yaml` beside it is read as the manifest. A repo path, an unpacked download, or one of this repo's own `fixtures/` directories all work. |
| `$2…` | `--strict` | no | Exit non-zero on any DETECTED finding. Without it the command reports and returns. |
| `$2…` | `--evidence-only` | no | Print the raw `Finding` triples and skip the remediation prose. |

With no `<package-path>`, the command asks for one rather than guessing a target.

## Example invocation

```text
/ast10:audit-ast08 ./invoice-helper
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

CHECK:    AST08-S02  Obfuscated Instruction
VERDICT:  DETECTED
EVIDENCE: SKILL.md: base64 blob at decode depth 1 decodes to a layer matching rule
          'remote-fetch-piped-to-shell'; reported against the raw artifact with the
          decoded view retained as evidence
TIER:     static-detectable

CHECK:    AST08-S04  Context-Dependent Malice
VERDICT:  CLEAN
EVIDENCE: no environment-keyed guard wraps a dangerous branch
TIER:     static-detectable

CHECK:    AST08-S07  Scanner Host Compromise and Resource Exhaustion
VERDICT:  CLEAN
EVIDENCE: within every declared bound: <=500 entries, <=2097152 bytes/file, no padding
          run over 1000, archive depth <=1, ratio <=100:1, no escaping symlink, no
          special file
TIER:     static-detectable

CHECK:    AST08-S08  Bytecode Cache Poisoning
VERDICT:  CLEAN
EVIDENCE: every shipped .pyc corresponds to shipped source
TIER:     static-detectable

CHECKS RUN:  4 detector check(s) at the static-detectable tier, 1 DETECTED
REGISTRY:    8 named scenario(s): 4 static-detectable, 2 agent-judgable, 2 out-of-artifact
UNCOVERED:   0 static-detectable scenarios with no detector
NOT DECIDED: 2 agent-judgable scenarios need a judge, not this run
NOT DECIDED: 2 out-of-artifact scenarios are not decidable from one package
F1:          scenario-level 1.00 (4 scenario checks, n=8)
             status=covered, corpus=8 case(s), hand-authored — not a false-positive rate
```

The coverage footer is not decoration. A DETECTED-free run of this command means
"the 4 implemented checks did not fire", never "AST08 is clean" — half this category's
named scenarios are decided by a judge or not decidable from a package at all.

## Coverage caveat

All four static-detectable scenarios are implemented and labeled, and the category publishes
`scenario-level 1.00 (4 scenario checks, n=8)`. Read that number with this category's own
scepticism: n=8 is the smallest corpus the sizing rule permits for four checks, it was
authored by the same people who wrote the rules, and it is therefore **not** a
false-positive rate — AST08's own mitigations require one measured against a benign corpus
of real, widely installed skills, and no such corpus is used here. Nor is it a bypass rate:
every rule is public, so the adversary holds the scanner, and each check has a knowable
evasion. `skills/AST08/coverage-matrix.md` states each one.

## Related

- `/ast10:audit-skill-package` — the same package across all ten categories in one sweep.
- `/ast10:check-coverage AST08` — the full per-scenario tiering and the written reason
  behind every uncovered row above.
- `/ast10:triage-finding` — when you have a finding in prose and do not yet know it is
  AST08.
- `skills/AST08/coverage-matrix.md` — the authority this command's footer is read from.

