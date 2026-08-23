# AST10 — Cross-Platform Reuse: coverage matrix

Audit artifact. It states, for each of the six attack scenarios the whitepaper names under
AST10, which tier it is in, what this skill package's detector actually checks for it, and
why. It is not a summary of the whitepaper's AST10 section.

| Field | Value |
| --- | --- |
| Authoritative tiering | `scenarios/registry.yaml` (AST10-S01 … AST10-S06) |
| Corpus binding | `fixtures/manifest.yaml` → `categories.AST10` |
| Tier-lock hash (S-011) | `dba555f29ccb40833c5da0a5a20093477eeb7613d6fa72524079716200e05e25` |
| Detector under audit | `skills/AST10/scripts/detector.py` |
| Whitepaper scenarios | 6 (body of the AST10 "Attack Scenarios" section) |
| Tier split | **1 static-detectable** · 0 agent-judgable · 5 out-of-artifact |
| Detectable scenarios labeled and implemented | **0 of 1** (AST10-S06 is a known, declared gap) |
| Published F1 | **none** — see "F1 denominator" below |
| Status | `declared-and-uncovered` (with a known gap, not "nothing here is detectable") |

Tier definitions are `scenarios/registry.yaml` → `tier_doctrine`; the contract that makes
this matrix binding on the F1 denominator is `docs/adr/0004-per-scenario-detectability-contract.md`.
Changing any tier below changes the tier-lock hash and forces re-labeling plus a judge
re-run before an F1 for this category could be published (`validators/tier_lock.py`).

## Scenario table

Titles are the whitepaper's own sub-headings, verbatim. The "detector checks" column records
what `skills/AST10/scripts/detector.py` executes today — not what the tier permits it to
check.

| Scenario id | Whitepaper title | Tier | What the detector actually checks | Reason for the tier |
| --- | --- | --- | --- | --- |
| AST10-S01 | Security Property Loss in Translation | out-of-artifact | — | "Loss" is a relation between a source manifest and a ported target manifest, plus the target platform's schema. The whitepaper's own tooling settles it: the metadata loss simulator takes *two* manifests as input. One manifest, read alone, cannot say what it used to carry. |
| AST10-S02 | Cross-Registry Arbitrage | out-of-artifact | — | Requires a cross-registry corpus — the same skill's presence, scan posture, and install counts on two or more registries. A single package shows none of that; the arbitrage is in the gap between registries, not in the bytes. |
| AST10-S03 | Multi-Platform Campaign | out-of-artifact | — | "Deployed across four platforms simultaneously" is a corpus-and-timeline property. One package is one campaign member and is indistinguishable from a lone publication. |
| AST10-S04 | Manifest Stripping | out-of-artifact | — | Deciding that metadata was stripped needs the pre-port manifest to compare against. A ported package with no permission block is byte-for-byte indistinguishable from one that never declared any, so absence cannot be attributed to porting. |
| AST10-S05 | Implicit Privilege Escalation | out-of-artifact | — | The escalation is a property of the *target* platform's default-permission model. The package's own declarations are unchanged by the port and, read alone, look correctly scoped; the exposure exists only relative to a default the package does not carry. |
| AST10-S06 | Silent Supply Chain Injection | **static-detectable** | **Nothing — no detector function is registered.** `DETECTORS` is empty in `skills/AST10/scripts/detector.py`, and no encoded-block decoder exists anywhere in this repo's detectors (`decode`, `base64`, and `b64` appear in no `skills/*/scripts/detector.py` and in no module under `detectors/`). This is a declared coverage gap, tracked as `uncovered_static_detectable: [AST10-S06]` in `fixtures/manifest.yaml`. | The named vector is an encoded script block — a byte pattern inside the package. Decoding it and re-scanning the decoded content is deterministic and platform-independent, with no prose intent-reading required. It is precisely the whitepaper's own "build platform-agnostic skill scanners that evaluate the content layer independently of the runtime" mitigation, so the tier follows the whitepaper's own claim about what is checkable. |

**Detector reconciliation.** `skills/AST10/scripts/detector.py` registers zero detector
functions; `STATIC_DETECTABLE` derives to the empty set. Two drifts in that file are
recorded here rather than silently tolerated. First, its interim `SCENARIO_TIERS` map is
keyed by slugs (`AST10-cross-registry-arbitrage`, `AST10-multi-platform-campaign`) that are
not registry ids and enumerate only 2 of the 6 scenarios; its docstring's "Both named
scenarios" wording predates the 6-scenario extraction. Second — the material one — that map
does not contain AST10-S06 at all, so the module's own view of the category is
"everything is out-of-artifact", which the registry contradicts. **This matrix is the tier
of record:** AST10 has one static-detectable scenario and does not detect it. The gap is
declared here, in `fixtures/manifest.yaml`, and in the F1 statement below, and it is not
closed by re-describing S06 as undetectable.

## Declared and uncovered

Five of six scenarios are out-of-artifact. Each row states why one skill package cannot
decide it and names the evidence that would. Three of them carry an `artifact_signal` in
the registry — an in-package precondition that is a *partial proxy only*. A proxy is
recorded so a reviewer can see what was considered and rejected; it is never counted as
coverage of the scenario, and no F1 is ever published against it under this category.

**AST10-S01 — Security Property Loss in Translation.** Cannot be decided from one package:
the loss is a difference between two manifests under a third input, the target platform's
schema. *Registry `artifact_signal` (partial proxy, not coverage):* a package declaring
security properties in fields the target format does not carry — which is still only
decidable once the target schema is supplied alongside it, so even the proxy needs an
external input. *Evidence that would decide it:* the source manifest, the ported target
manifest, and the target platform's field schema — exactly the three inputs the
whitepaper's browser-only metadata loss simulator consumes to report a lost or weakened
property (for example an allowlisted egress replaced by `network: true`).

**AST10-S02 — Cross-Registry Arbitrage.** Cannot be decided from one package: the attack is
promotion of an install count earned on a lightly scanned registry into a more trusted one,
and neither registry's state is in the artifact. *Evidence that would decide it:* records
for the same skill (or its near-identical republication) on two or more registries, each
with its scan posture, publication date, publisher identity, and install-count history, plus
the absence of shared scanning intelligence between them.

**AST10-S03 — Multi-Platform Campaign.** Cannot be decided from one package: simultaneity
across platforms is the whole scenario. *Evidence that would decide it:* a cross-platform
corpus with publication timestamps, plus author/publisher linkage tying the copies to one
actor — the shape of the ToxicSkills finding of the same actors publishing to ClawHub and
skills.sh, which required both registries' data to see.

**AST10-S04 — Manifest Stripping.** Cannot be decided from one package: absence of a
permission block is not evidence of removal. *Registry `artifact_signal` (partial proxy,
not coverage):* absent permission or risk metadata in a package whose format supports it —
the same signal AST06's missing-sandbox-declaration check reads, and equally unable to
attribute the absence to porting. *Evidence that would decide it:* the pre-port manifest to
diff against, and ideally the identity of the porting tool or path that produced the target
copy, so a dropped field is attributable to translation rather than to the author.

**AST10-S05 — Implicit Privilege Escalation.** Cannot be decided from one package: the
package is unchanged; the target platform's defaults do the escalating. *Registry
`artifact_signal` (partial proxy, not coverage):* reliance on platform defaults instead of
explicitly declared scopes. *Evidence that would decide it:* the target platform's
default-permission model — what a skill is granted when it declares nothing — evaluated
against this package's declared (or absent) scopes. Note that S-04 and S-05 are the same
event from two ends, cause and effect; a review that checks only "were fields dropped"
without checking "what does the target default to in their absence" understates the
exposure, which is why both stay out-of-artifact rather than one standing in for the other.

**AST10-S06 — Silent Supply Chain Injection** is *not* in this section. It is
static-detectable and simply not yet built. It is reported as an uncovered detectable
scenario, not as an undetectable one — a distinction this matrix insists on, because
collapsing the two would let unbuilt work read as impossible work.

## F1 denominator

**AST10 publishes no F1 number today.**

The denominator for a category is drawn from its declared-detectable tier (ADR-0004;
enforced in `detectors/engine.py`, which scores the static-detectable subset and reports the
agent-judgable subset separately rather than folding it in). AST10 has no agent-judgable
scenarios, so the only candidate is the static-detectable one, AST10-S06. It has no detector
function and no labeled fixture case, so the labeled detectable tier is empty:
`detectable_scenarios: []`, `published_f1: null`, `f1_scope: none`, and
`detectors/scaffold.f1_report` returns `{"status": "declared-and-uncovered", "f1": None}`.

The honesty choice here is narrower than AST09's and worth stating exactly, because the two
categories reach the same "no F1" outcome for different reasons:

- **What would be dishonest and is refused:** publishing an F1 computed over fixtures built
  for the five out-of-artifact scenarios. Cross-registry arbitrage, multi-platform campaigns,
  manifest stripping, and implicit privilege escalation can all be *narrated* inside a single
  fake SKILL.md — "this skill was ported from OpenClaw and lost its permissions block" — and
  a detector that greps that narration would score perfectly against it. That number would
  measure the fixture author's imagination. `detectors/engine.py` raises
  `OutOfArtifactFixtureError` rather than scoring such a case, and the three declared
  `artifact_signal` proxies above are recorded precisely so that a proxy can never be quietly
  promoted into the denominator under the scenario's name.
- **What is a gap and is declared as one:** AST10-S06 is genuinely decidable from the
  package and is not implemented. Calling this category "undetectable" would be the second
  dishonesty, in the opposite direction — it would convert an unfinished detector into a
  law of nature. The row above names the missing mechanism (decode encoded script blocks,
  re-scan the decoded content) so the debt is auditable.

Consequence: no AST10 row appears in any F1 pass/fail comparison, and the category's skill
grade is unaffected by the five out-of-artifact scenarios (S-003). Closing the S-06 gap —
not re-tiering anything — is what would give this category an F1.

## Corpus size

| Quantity | Value |
| --- | --- |
| Detectable scenarios in the registry | 1 (AST10-S06) |
| Detectable scenarios labeled in `fixtures/manifest.yaml` | 0 |
| Entitlement today under `max(6, 2 × detectable)` | **0 cases — the formula does not apply while the labeled detectable tier is empty** |
| Entitlement once AST10-S06 is labeled | **6 cases** = `max(6, 2 × 1)`, class-balanced 3 vulnerable / 3 clean (`cases_at_full_static_coverage: 6`) |
| Fixture files actually present under `fixtures/AST10/` | **0** (directory exists and is empty) |
| Cases declared in `fixtures/manifest.yaml` | 0 (`cases: []`) |

The `MIN_FLOOR = 6` term is a floor on a corpus that exists, not a quota to be filled: with
an empty labeled detectable tier, gate-4's never-pad rule overrides the floor and the
category ships zero cases with `status: declared-and-uncovered`, which is the branch
`fixtures/test_manifest.py::test_case_count_matches_locked_gate4_formula` asserts. The
second row is the concrete, pre-committed size of the work: implementing the S-06 decoder
obliges exactly six labeled cases, not one demonstration case, and not a corpus sized to
whatever the detector happens to pass.

Nothing about this changes unless the registry re-tiers an AST10 scenario, which trips the
tier lock and requires this matrix, the manifest entry, and the detector to move together.
