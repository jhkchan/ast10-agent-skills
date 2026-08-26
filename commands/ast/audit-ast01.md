---
name: audit-ast01
description: >-
  Audit one candidate skill package against OWASP AST01 - Malicious Skills alone, using the
  ast01-malicious-skills skill's decision rules and the frozen per-scenario detectability
  contract in skills/AST01/coverage-matrix.md. Runs the 10 static-detectable check(s) this
  category implements — one per named AST01 scenario the registry tiers static-detectable,
  plus two content-hash controls that cover no named scenario — then reports the tiering
  gap the run did not close.
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

# /ast10:audit-ast01

Activates the `ast01-malicious-skills` skill (`skills/AST01/`) and audits one candidate
skill package against **AST01 - Malicious Skills** and nothing else. Use
`/ast10:audit-skill-package` when you want all ten categories in one pass.

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
| `AST01-social-engineering-prerequisites` | static-detectable | the package's prose instructs the reader to pipe a remote fetch into a shell, and the destination host is absent from `permissions.network.allow` |
| `AST01-soul-md-persistence` | static-detectable | a write scope naming the agent identity file survives `deny_write`-wins evaluation, or a bundled script opens that path for write |
| `AST01-memory-poisoning` | static-detectable | the same two predicates against the agent memory file |
| `AST01-identity-clone-exfiltration` | static-detectable | one bundled script both reads an identity artifact and carries an outbound send; neither half alone fires |
| `AST01-websocket-c2` | static-detectable | a bundled script opens a WebSocket-scheme URL against a host the manifest never declared |
| `AST01-undeclared-egress` | static-detectable | a bundled script's egress call site names a hardcoded destination host absent from the declared allowlist |
| `AST01-hidden-output-injection` | static-detectable | the package's output templates carry invisible control code points, or a base64 blob that decodes back to text |
| `AST01-obfuscated-payload-exec` | static-detectable | an encoded blob is decoded straight into an execution sink; the payload is decoded once and reported |
| `AST01-content-hash-missing` | static-detectable | the manifest declares no signed `content_hash`, so there is nothing to verify the shipped bytes against — an artifact signal, never coverage of a named scenario |
| `AST01-content-hash-mismatch` | static-detectable | the declared hash disagrees with a sha256 recomputed over the package's sorted (path, content) pairs |

Every row above is a check that runs. Nothing else does: AST01's judged surface —
`AST01-S01` Typosquatting, `AST01-S03` Instruction Override, `AST01-S04` ClickFix Prompts —
is tiered `agent-judgable` by `scenarios/registry.yaml` and routed to the judge harness, and
`AST01-S07` Cognitive Degradation is out-of-artifact. That includes the judged half of the
obfuscation pair: `AST01-obfuscated-payload-exec` decides only whether a decoded blob reaches
an execution sink, and deciding a payload is *intentionally* malicious rather than merely
unusual is a semantic reading no byte match makes. (This table used to carry that half as an
eleventh row, `AST01-obfuscated-payload-intent`, which was never a check — no function
computed it — and is not a registry scenario id either.)

Check ids are the detector's own, not registry scenario ids (`AST01-S01`, `AST01-S02`, …).
Which registry scenario each check maps to — and how honestly it measures that scenario,
versus measuring an enabling artifact signal — is recorded in `fixtures/manifest.yaml`'s
`covers:` field and expanded by `/ast10:check-coverage AST01`.

## Arguments

| Position | Argument | Required | Meaning |
| --- | --- | --- | --- |
| `$1` | `<package-path>` | yes | Directory (or archive) of the candidate skill package. Must contain a `SKILL.md`; a `skill.usf.yaml` beside it is read as the manifest. A repo path, an unpacked download, or one of this repo's own `fixtures/` directories all work. |
| `$2…` | `--strict` | no | Exit non-zero on any DETECTED finding. Without it the command reports and returns. |
| `$2…` | `--evidence-only` | no | Print the raw `Finding` triples and skip the remediation prose. |

With no `<package-path>`, the command asks for one rather than guessing a target.

## Example invocation

```text
/ast10:audit-ast01 ./invoice-helper
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
COVERS:   artifact-signal-only (AST05-S01, AST07-S01) - not coverage of either

CHECK:    AST01-undeclared-egress
VERDICT:  DETECTED
EVIDENCE: scripts/report.py: egress call (requests.post() to host(s)
          ['collector.attacker-drop.example'] absent from the declared allowlist []
TIER:     static-detectable
COVERS:   full (AST01-S10)

CHECK:    AST01-websocket-c2
VERDICT:  CLEAN
EVIDENCE: no bundled script opens a WebSocket to an undeclared host
TIER:     static-detectable

CHECKS RUN:  10 detector check(s) at the static-detectable tier, 2 DETECTED
REGISTRY:    11 named scenario(s): 7 static-detectable, 3 agent-judgable, 1 out-of-artifact
UNCOVERED:   0 static-detectable scenarios with no labeled fixture
NOT DECIDED: 3 agent-judgable scenarios need a judge, not this run
NOT DECIDED: 1 out-of-artifact scenario is not decidable from one package
F1:          scenario-level 1.000 (8 labeled checks, n=16)
             status=covered, scope=scenario-level, corpus=16 case(s)
```

The coverage footer is not decoration. A DETECTED-free run of this command means
"none of the 10 implemented checks fired", never "AST01 is clean" — three of this
category's eleven named scenarios need a judge and one is not decidable from any
package at all.

## Coverage caveat

All seven of AST01's registry static-detectable scenarios now have a check and a labeled
fixture pair. The corpus carries an eighth check for AST08-S02 (Obfuscated Instruction),
a scenario the whitepaper files under another category but whose defining condition is a
property of an AST01 package's own bundled script — recorded, not reassigned.

The published F1 is measured over 16 hand-authored cases by the same author who wrote the
detector, so read it as internal consistency rather than field performance. What makes it
worth publishing is the clean half of each pair: the same command from a declared host,
the same base64 blob never executed, the same write grant covered by the floor. A
keyword-matching detector scores 0.5 on this corpus.

## Related

- `/ast10:audit-skill-package` — the same package across all ten categories in one sweep.
- `/ast10:check-coverage AST01` — the full per-scenario tiering and the written reason
  behind every uncovered row above.
- `/ast10:triage-finding` — when you have a finding in prose and do not yet know it is
  AST01.
- `skills/AST01/coverage-matrix.md` — the authority this command's footer is read from.

