---
name: audit-ast10
description: >-
  Audit one candidate skill package against OWASP AST10 - Cross-Platform Reuse alone, using
  the ast10-cross-platform-reuse skill's decision rules and the frozen per-scenario
  detectability contract in skills/AST10/coverage-matrix.md. One of this category's six
  scenarios is static-detectable and is checked: Silent Supply Chain Injection, decided by
  decoding the package's encoded blobs and evaluating the decoded content layer. The other
  five are out-of-artifact and are reported as declarations with the off-artifact evidence a
  reviewer has to gather instead.
nl_triggers:
  - "ported this skill to another platform"
  - "permissions lost in translation"
  - "manifest stripping"
  - "cross registry arbitrage"
  - "AST10 audit"
  - "universal skill format check"
  - "deny_write did not survive the port"
  - "base64 blob in a skill I imported"
  - "encoded payload hidden in a ported skill"
routes_to: ast10-cross-platform-reuse
ast_category: AST10
---

# /ast:audit-ast10

Activates the `ast10-cross-platform-reuse` skill (`skills/AST10/`) and audits one candidate
skill package against **AST10 - Cross-Platform Reuse** and nothing else. Use
`/ast:audit-skill-package` when you want all ten categories in one pass.

## What AST10 actually is

The premise is that a skill's security properties are lost in translation between runtimes,
so the Universal Skill Format manifest is the mitigation and the validator is where most of
the work happens. Three USF rules carry the load: `deny_write` always wins over `write` for
any path it lists; network evaluation is default-deny so `deny: "*"` is redundant with — not
an override of — an empty `allow`; and `risk_tier` is an untrusted author assertion that
must be re-derived from the declared permissions.

The category's sixth scenario is the exception, and it is the one this command *runs*
something for. Silent Supply Chain Injection is a payload hidden inside an encoded script
block that "execute[s] at agent speed once imported into a new ecosystem without structural
validation". The structural validation is the check.

**Seam.** AST10 is a property that existed on platform A and does not exist on platform B.
If the property never existed anywhere, it is AST03/AST04/AST06 on the platform where it is
missing. A payload that is *visible in the package's readable text* is AST01 or AST08; AST10
covers the case where the bytes are opaque until decoded.

## What it does

1. Normalises the package into the detector's input shape — `{"manifest": {...},
   "files": {"<relative/path>": "<text>"}}`. A `skill.usf.yaml` is read for the
   manifest half; a bare `SKILL.md` package yields an empty manifest, which is itself
   a finding in several categories.
2. Runs `skills/AST10/scripts/detector.py`'s single check, `AST10-S06`, over both halves —
   files and manifest values alike, because a SKILL.md-only skill ships its payload in a
   frontmatter field. Two conditions fire it:
   - **decode and rescan** — every base64, bare-hex, `\xNN`-escape and percent-encoded run
     is decoded (plus one gzip/zlib layer beneath it, and one further encoding layer), and
     the *decoded* text is matched against payload behaviour: interpreter invocation,
     destructive filesystem operations, credential harvesting, writes to the USF identity
     files, fetch-and-execute, outbound exfiltration, reverse shells, execution sinks;
   - **decode then execute** — a decoded literal reaching an execution sink, on one line or
     across a single assignment. This one fires even when the payload is unreadable, which
     is why a second cipher layer is not a free pass.
3. Reads `scenarios/registry.yaml` and `skills/AST10/coverage-matrix.md` and reports each of
   the other five named scenarios with the written reason it is not decidable from one
   package.
4. Applies the `ast10-cross-platform-reuse` skill's decision rules to name the evidence that
   *would* decide those five, and where that evidence lives.

## Checks this command runs

`Tier` is the check's own mechanism tier: is it decidable from bytes? (It is not read
from `SCENARIO_TIERS`, which mirrors `scenarios/registry.yaml`'s per-SCENARIO tiering
and says nothing about any individual check.) `Covers` is the separate question
(`CHECK_COVERAGE`): does deciding it cover a named whitepaper scenario? AST10 ships
exactly one check, and it does. That check is named after the single scenario it decides
in full, so `AST10-S06` reads in both columns — an identity, not the two tables collapsing
into one.

| Check id | Tier | Covers | Fires when |
| --- | --- | --- | --- |
| `AST10-S06` | static-detectable | AST10-S06 (full) | an encoded run (base64, bare hex, `\xNN` escape, percent-encoding, plus one gzip/zlib layer and one further encoding layer beneath it) **decodes** to payload behaviour, or a decoded literal reaches an execution sink. The presence of an encoded blob alone never fires it |

The other five AST10 scenarios are `out-of-artifact` and are tabled below rather than
checked; `/ast:check-coverage AST10` expands every row.

## What it deliberately does not flag

Encoding is not the finding; an unvalidated encoded *payload* is. A base64 icon, a base64
configuration block, a gzip-compressed policy document, and the hex `content_hash` /
`signature` fields the Universal Skill Format itself mandates all decode to something that
matches no payload signature, and none of them is reported. Three of the six labeled
fixtures under `fixtures/AST10/` are exactly those cases, which is what the published F1
measures.

## What is still declared rather than run

| Scenario | Tier | Why one package cannot decide it |
| --- | --- | --- |
| AST10-S01 Security Property Loss in Translation | out-of-artifact | needs the source-platform manifest to compare the destination against |
| AST10-S02 Cross-Registry Arbitrage | out-of-artifact | a single package in isolation has nothing to be "cross" with |
| AST10-S03 Multi-Platform Campaign | out-of-artifact | needs cross-platform deployment telemetry and a timeline |
| AST10-S04 Manifest Stripping | out-of-artifact | the stripped field's prior existence lives in the source platform's copy |
| AST10-S05 Implicit Privilege Escalation | out-of-artifact | depends on the destination runtime's default, not on the package |

## Arguments

| Position | Argument | Required | Meaning |
| --- | --- | --- | --- |
| `$1` | `<package-path>` | yes | Directory (or archive) of the candidate skill package. Must contain a `SKILL.md`; a `skill.usf.yaml` beside it is read as the manifest. A repo path, an unpacked download, or one of this repo's own `fixtures/` directories all work. |
| `$2…` | `--evidence-plan` | no | In addition to the AST10-S06 verdict, emit the off-artifact evidence a reviewer must gather to decide the five out-of-artifact scenarios, and where that evidence lives. |
| `$2…` | `--strict` | no | Exit non-zero when AST10-S06 fires. It has no effect on the five declared scenarios, which have no verdict to fail on. |

With no `<package-path>`, the command asks for one rather than guessing a target.

## Example invocation

```text
/ast:audit-ast10 ./invoice-helper
```

The declared half of the category is still reported, not skipped: the reviewer leaves with
a verdict on the one scenario the package can decide *and* a shortlist of off-artifact
evidence for the five it cannot.

The contract is checkable directly:

```bash
python3 - <<'EOF'
import importlib.util, sys
from pathlib import Path
sys.path.insert(0, '.')          # repo root, so `detectors.scaffold` resolves
spec = importlib.util.spec_from_file_location('ast10_detector',
                                             Path('skills/AST10/scripts/detector.py'))
m = importlib.util.module_from_spec(spec); sys.modules[spec.name] = m
spec.loader.exec_module(m)
print(sorted(m.DETECTORS))       # ['AST10-S06'] - one check, for the one detectable scenario
print(m.STATIC_DETECTABLE)       # {'AST10-S06'}
print(m.F1_SCOPE)                # scenario-level
EOF
```

Or over this repository's own labeled corpus:

```bash
python3 cli/lib/bridge.py audit fixtures/AST10/V5-gzip-archive-payload
python3 cli/lib/bridge.py audit fixtures/AST10/C6-gzip-archive-payload
```

The two packages carry the same gzip-under-base64 structure. Only the decoded content and
the sink differ, and only the first is a finding.

## Output

```text
PACKAGE:  ./invoice-helper
CATEGORY: AST10 - Cross-Platform Reuse

AST10-S06 Silent Supply Chain Injection ..... DETECTED
  scripts/loader.py: base64+gzip blob 'H4sIAAAAAAACE22OMWsDMQyFd...' decodes to
  identity-file-write+credential-harvest+outbound-exfiltration content layer
  scripts/loader.py:8: decoded literal executed in place

CHECKS RUN:  1 of 1 static-detectable scenario
REGISTRY:    6 named scenario(s): 1 static-detectable, 0 agent-judgable, 5 out-of-artifact
NOT DECIDED: 5 out-of-artifact scenarios are not decidable from one package
F1:          1.00 (scope=scenario-level, corpus=6 labeled case(s), tp 3 / fp 0 / fn 0)
```

`NOT DECIDED` is a verdict, not an error. It says those five scenarios were considered and
found undecidable from this artifact — a different, and far more useful, statement than a
silent pass.

## Coverage caveat

The published 1.00 is a discrimination measurement on six hand-built packages, three of them
clean packages that each carry a real encoded blob. It says the check separates payload from
encoding on that corpus. It is not an estimate of field performance, and it says nothing at
all about the five out-of-artifact scenarios, which publish no number and cannot.

## Related

- `/ast:audit-skill-package` — the same package across all ten categories in one sweep.
- `/ast:check-coverage AST10` — the full per-scenario tiering and the written reason
  behind every declared row above.
- `/ast:triage-finding` — when you have a finding in prose and do not yet know it is
  AST10.
- `/ast:validate-usf-manifest` — the manifest half of this category: the USF rules
  live in `validators/usf.py`.
- `skills/AST10/coverage-matrix.md` — the authority this command's footer is read from.
