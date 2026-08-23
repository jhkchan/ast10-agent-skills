---
name: check-coverage
description: >-
  Show what one AST category declares and does not cover - every named whitepaper scenario
  with its detectability tier and the written reason for that tier, which static-detectable
  scenarios have no labeled fixture, the corpus accounting behind the F1 (or the reason no F1
  is published at all), and the reconciliation note where the scenario registry overruled the
  fixture manifest.
nl_triggers:
  - "what does AST05 actually cover"
  - "why is there no F1 for AST09"
  - "declared and uncovered"
  - "which scenarios are out of artifact"
  - "coverage gap for this category"
  - "why is this scenario not detectable"
  - "show me the coverage matrix"
  - "is this category proxy covered"
  - "how big should the fixture corpus be"
  - "tier lock hash"
routes_to: advisory
---

# /ast:check-coverage

Activates the `advisory` skill (`skills/advisory/`) as the reader across all ten categories,
and reports one category's coverage honestly — including the parts that are empty.

This command exists because a detector that returns nothing is ambiguous. It can mean *this
package is clean* or *this category has no implemented check*. Those are opposite facts, and
every audit output in this repo is required to say which one it is.

## The three tiers, and what each one licenses you to claim

Read from `scenarios/registry.yaml`, which is authoritative on tier and overrules
`fixtures/manifest.yaml` wherever the two disagreed:

- **static-detectable** — a deterministic rule over the package's own bytes decides the
  scenario's *defining* condition. No prose intent-reading, no state from outside. Only
  these scenarios may enter an F1 denominator.
- **agent-judgable** — all the evidence is in the package, but the decision needs semantic
  judgement of prose, naming, or stated purpose. Scored by the judge harness, never folded
  into an F1.
- **out-of-artifact** — not decidable from one package at all. The defining condition lives
  in version history, remotely hosted content, another package, the host runtime, the
  registry's state, or an organisation's process.

**The defining-condition rule** is why the registry is conservative: a scenario is
static-detectable only if the package decides the scenario *itself*. Where the package can
only show an enabling precondition while the defining event happens elsewhere, the scenario
stays out-of-artifact. An F1 published over preconditions measures the fixture author's
imagination, not a detector.

## What "declared-and-uncovered" means

A category whose static-detectable tier is empty publishes **no F1 number at all** and is
reported `declared-and-uncovered`. It is never padded to manufacture a number. The
categories in that state today — AST02, AST07, AST09 — each say why. AST10 left that state
when its one static-detectable scenario, AST10-S06, was implemented and labeled.

Corpus sizing for the categories that do publish: `cases = max(6, 2 × detectable_scenarios)`,
class-balanced vulnerable/clean, drawn only from the static-detectable tier. The command
prints both the declared and the present count so an under-filled corpus cannot hide.

`f1_scope` is the honesty label on any number that does get published:

| `f1_scope` | Reading |
| --- | --- |
| `scenario-level` | The corpus measures the named scenarios themselves. |
| `mixed-proxy` | Some checks measure named scenarios, others measure an enabling artifact signal. |
| `artifact-signal-only` | No check measures a named scenario. Any F1 here is a proxy number and overclaims if reported plainly. |
| `category-precondition` | The check derives from the category's preventive mitigations, not from any named scenario. |
| `none` | Nothing is published. |

## Arguments

| Position | Argument | Required | Meaning |
| --- | --- | --- | --- |
| `$1` | `<ASTnn>` | yes | The category: `AST01` … `AST10`. Case-insensitive; `ast05` and `5` both resolve. |
| `$2…` | `--tier <tier>` | no | Show only one tier: `static-detectable`, `agent-judgable`, or `out-of-artifact`. |
| `$2…` | `--uncovered-only` | no | Show only static-detectable scenarios with no labeled fixture — the actionable coverage debt. |
| `$2…` | `--all` | no | Ignore `$1` and print the one-line status row for all ten categories. |

## Example invocation

```text
/ast:check-coverage AST05
```

Equivalent deterministic run:

```bash
python3 - AST05 <<'EOF'
import sys, yaml
cat = sys.argv[1]
reg = yaml.safe_load(open("scenarios/registry.yaml"))
man = yaml.safe_load(open("fixtures/manifest.yaml"))["categories"][cat]
rows = [s for s in reg["scenarios"] if s["category"] == cat]
rc = man.get("registry_coverage", {})
print(f"CATEGORY: {cat} - {reg['categories'][cat]['name']}")
print(f"STATUS:   {man['status']}   f1_scope={man['f1_scope']}   published_f1={man.get('published_f1')}")
print(f"CORPUS:   {rc.get('cases_present')} case(s) present / {rc.get('declared_expected_cases')} declared")
for t in ("static-detectable", "agent-judgable", "out-of-artifact"):
    hits = [s for s in rows if s["tier"] == t]
    print(f"\n{t.upper()} ({len(hits)}):")
    for s in hits:
        flag = "UNCOVERED" if s["id"] in (rc.get("uncovered_static_detectable") or []) else ""
        print(f"  {s['id']}  {s['title']}  {flag}")
        print(f"      why: {' '.join(s['reason'].split())}")
print(f"\nRECONCILIATION NOTE: {' '.join((rc.get('note') or 'none').split())}")
EOF
```

## Output

```text
CATEGORY: AST05 - Untrusted External Instructions
STATUS:   proxy-covered   f1_scope=artifact-signal-only   published_f1=artifact-signal-only 1.00 (n=6)
CORPUS:   6 case(s) present / 6 declared (max(6, 2 x 3 labeled checks))

STATIC-DETECTABLE (0):

AGENT-JUDGABLE (1):
  AST05-S05  Malicious Instructions Embedded in Documents
      why: The malicious document is supplied at runtime and is not in the package, but
           the whitepaper's stated cause is that the skill fails to distinguish document
           content from instruction.

OUT-OF-ARTIFACT (5):
  AST05-S01  Author Rug-Pull
      why: The defining event is an edit to remotely hosted content after review.
           Deciding it requires the referenced document at two points in time.
  AST05-S02  Reviewer Bait-and-Switch
      why: Requires fetching the reference from multiple vantage points at multiple
           times and diffing the responses. The package is identical in both worlds.
  AST05-S03  Transitive Reference Chaining
      why: Everything after the first hop lives on remote servers. The package shows one
           reference; the chain's depth and destinations are only discoverable by
           following it.
  AST05-S04  Relay-Node Amplification
      why: A chain's injection resistance is the minimum over the backbone models on its
           path, which no single package can enumerate.
  AST05-S06  Denial-of-Service (DoS) through Malicious Skills
      why: "Excessive" is measured against a runtime budget and shared infrastructure the
           package knows nothing about.

RECONCILIATION NOTE: The registry tiers NONE of AST05's six named scenarios
static-detectable. Every case in this corpus therefore measures an artifact signal, never
a named scenario. Any F1 published here must be labeled artifact-signal-only or it
overclaims.
```

### `--all`

```text
AST01  covered                 scenario-level          11 scenarios (7/3/1)   corpus 6
AST02  declared-and-uncovered  none                     4 scenarios (1/0/3)   corpus 0
AST03  proxy-covered           mixed-proxy              5 scenarios (1/1/3)   corpus 6
AST04  covered                 scenario-level           7 scenarios (5/1/1)   corpus 6
AST05  proxy-covered           artifact-signal-only     6 scenarios (0/1/5)   corpus 6
AST06  proxy-covered           mixed-proxy              5 scenarios (1/0/4)   corpus 6
AST07  declared-and-uncovered  none                     3 scenarios (0/0/3)   corpus 0
AST08  proxy-covered           category-precondition    8 scenarios (4/2/2)   corpus 6
AST09  declared-and-uncovered  none                     7 scenarios (0/0/7)   corpus 0
AST10  covered                 scenario-level           6 scenarios (1/0/5)   corpus 6
                                             (static-detectable/agent-judgable/out-of-artifact)
```

## Tier-lock tripwire

Each category's fixture labeling is bound to the tiering it was labeled against by a
`tier_lock_hash` — a sha256 over that category's sorted `scenario_id:tier` pairs. If a
scenario is later reclassified, the recomputed hash stops matching and the category is
flagged for re-labeling and a judge re-run before its F1 can be republished. Run
`validators/tier_lock.py`'s `check_manifest_tier_locks()` over the loaded manifest before
publishing any number this command reports.

## Related

- `/ast:audit-ast01` … `/ast:audit-ast10` — the audit whose coverage footer this command
  expands.
- `/ast:audit-skill-package` — the full sweep, which prints the one-line version of this
  for every category.
- `skills/AST05/coverage-matrix.md` (and its nine siblings) — the per-category authored
  matrix, including the coverage-debt itemisation where a detector's interim tier table
  diverges from the registry.
- `docs/adr/0004-per-scenario-detectability-contract.md` — the decision record the tier
  vocabulary comes from.
