---
artifact: coverage-matrix
category: AST05
category_name: Untrusted External Instructions
version: "1.0"
created: 2026-08-23
task: T-3.1b
tier_authority: scenarios/registry.yaml
corpus_authority: fixtures/manifest.yaml
detector: skills/AST05/scripts/detector.py
tier_lock_hash: "3dc23889393d91e314c4eb3c52186cc807d00fd3c4f5ce0d9a05c03736753365"
registry_scenarios: 6
static_detectable: 0
agent_judgable: 1
out_of_artifact: 5
publishes_f1: false
---

# AST05 — Untrusted External Instructions: coverage matrix

This is the audit artifact `skills/AST05/SKILL.md` points at when it says "the exact
split is fixed in `coverage-matrix.md`". It is not a summary of the whitepaper's AST05
section.

**AST05 publishes no F1.** Not one of its six named scenarios is decidable from a single
skill package. That is the single most consequential fact on this page, and every
section below is downstream of it.

**Authority chain.** `scenarios/registry.yaml` is authoritative on tier; this file
reproduces its tiering and may not diverge from it. `fixtures/manifest.yaml` is
authoritative on which fixture cases exist. The `SCENARIO_TIERS` dict inside
`skills/AST05/scripts/detector.py` is an interim declaration by its own docstring
("superseded by … T-3.1's authored `skills/AST05/coverage-matrix.md` once locked") —
where it disagrees with this file, this file wins. The disagreement is real and is
recorded in [Detector checks that are not whitepaper scenarios](#detector-checks-that-are-not-whitepaper-scenarios).

## Scenario table

Legend for the detector column: `—` means no deterministic check over the package's own
bytes can decide the scenario. For AST05 that is every row, which is the finding, not an
omission.

| Scenario | Whitepaper title | Tier | What the detector actually checks | Reason for the tier |
| --- | --- | --- | --- | --- |
| `AST05-S01` | Author Rug-Pull | out-of-artifact | `—` | The defining event is an edit to remotely hosted content *after* review. The package is byte-identical before and after the rug-pull, so no function over its bytes can separate the two states. Deciding it requires the referenced document at two points in time. |
| `AST05-S02` | Reviewer Bait-and-Switch | out-of-artifact | `—` | The URL serves clean content keyed on IP, user-agent, or timing and malicious content to live runs. The package is identical in the reviewed case and the exploited case; only the server differs. The registry records no `artifact_signal` for this scenario at all — there is nothing in the artifact that even hints at it. |
| `AST05-S03` | Transitive Reference Chaining | out-of-artifact | `—` | Everything after the first hop lives on remote servers. The package shows one reference; the chain's depth, destinations, and content are discoverable only by fetching and following. |
| `AST05-S04` | Relay-Node Amplification | out-of-artifact | `—` | The whitepaper states the property directly: "a chain's injection resistance is the minimum over the backbone models on its path", and "certifying the endpoints does not certify the chain". That is deployment topology and per-node model assignment — facts about a pipeline, not about a package. |
| `AST05-S05` | Malicious Instructions Embedded in Documents | agent-judgable | `—` | The malicious document arrives at runtime and is not in the package, but the whitepaper's stated cause is the skill's own failure: "the skill fails to distinguish document content from executable instructions". That failure is in-artifact — prose in `SKILL.md` and code in the bundle — so the evidence is present; judging whether the boundary a skill establishes is *adequate* is semantic, not mechanical. `skills/AST05/scripts/detector.py` declares an id for it (`AST05-injected-instruction-compliance`) and correctly implements nothing, keeping it out of `STATIC_DETECTABLE`. |
| `AST05-S06` | Denial-of-Service (DoS) through Malicious Skills | out-of-artifact | `—` | "Excessive" is measured against a runtime budget and shared infrastructure the package knows nothing about. The identical loop is efficient on one deployment and exhausting on another, so the package cannot carry the fact that decides it. |

## Detector checks that are not whitepaper scenarios

`skills/AST05/scripts/detector.py` implements two checks. **Neither maps to any named
AST05 scenario**, and — verified against `schemas/usf-v1.schema.json` — neither can fire
on a schema-valid USF manifest.

| Detector scenario id | Maps to | Status |
| --- | --- | --- |
| `AST05-unrestricted-network-fetch` | *no named scenario* | Reads `manifest.permissions.network.policy` and fires when it equals `"allow-all"`. Derives from AST05's preventive-mitigation list ("Allowlist permitted reference domains: using the OWASP Universal Agentic Skill Format, restrict the external hosts a skill may fetch from to a vetted allowlist"), i.e. it is a category precondition. **Dead against USF v1:** `permissions.network` is `additionalProperties: false` with only `allow` and `deny`, so `policy` is always absent and the check returns `network.policy=None`, `detected=False`, on every conformant manifest. |
| `AST05-wildcard-domain-allowlist` | *no named scenario* | Fires only when `permissions.network.policy == "allow-list"` and the `allow` list contains `"*"` or a bare-TLD wildcard such as `"*.com"`. Same mitigation basis, same defect: the `policy` gate is never satisfied by a USF v1 manifest, so the wildcard logic below it is unreachable. On a hand-built dict carrying `policy: "allow-list"` it does work as documented. |
| `AST05-injected-instruction-compliance` | `AST05-S05` | Declared `agent-judgable` in `SCENARIO_TIERS`, deliberately absent from `DETECTORS`. Correct as it stands: it is excluded from `STATIC_DETECTABLE` and therefore from the F1 denominator. |

The consequence for `f1_report`: because two ids are declared `static-detectable` in the
module, `detectors/scaffold.py::f1_report` returns `status: "measured"` for AST05 rather
than the `declared-and-uncovered` this matrix requires. Reconciling the module's
`SCENARIO_TIERS` to this file empties `STATIC_DETECTABLE` and makes `f1_report` return
`{"status": "declared-and-uncovered", "f1": None}` — the right answer.

## Declared and uncovered

Five of AST05's six scenarios are out-of-artifact. None enters the fixture corpus
(`detectors/engine.py::run_category` raises `OutOfArtifactFixtureError` if one ever
does). For each: why one package cannot decide it, the enabling precondition the package
*can* show, and the evidence that would actually decide it.

### `AST05-S01` — Author Rug-Pull

- **Why one package cannot decide it.** The package that passed review and the package
  that is exploited are the same bytes. The malicious change happens in a document the
  package merely names. There is no state in the artifact that differs before and after.
- **Enabling precondition the package shows** (`artifact_signal`): an external
  instruction reference carried with no pinned content hash — the precondition the
  whitepaper's "record a content hash … re-verify it on every load" mitigation targets.
  A partial proxy; never coverage.
- **Evidence that would decide it.** Two fetches of the referenced document separated in
  time, both attributable to the same URL, plus the review-time digest to anchor the
  first — i.e. the pin-and-re-verify control operating as a *record*, not as a check.
  That is host-side and lifecycle state, not package state.

### `AST05-S02` — Reviewer Bait-and-Switch

- **Why one package cannot decide it.** The attack is keyed on the *requester*, not on
  the content. Every artifact-side observation is one vantage point, and one vantage
  point cannot show that the server discriminates. The registry deliberately records
  **no** `artifact_signal` here: there is not even a partial proxy, because a pinned,
  allowlisted, perfectly declared reference is equally susceptible.
- **Evidence that would decide it.** The same URL fetched from multiple network
  vantage points, under multiple user-agents, at multiple times, with the responses
  diffed — plus an agent-identity-shaped fetch to elicit the live-run variant. That is a
  measurement campaign against a live host.

### `AST05-S03` — Transitive Reference Chaining

- **Why one package cannot decide it.** The package shows hop one. The attacker's link
  is at hop N, past where review stopped, on a server the package never names.
- **Enabling precondition the package shows** (`artifact_signal`): references that are
  neither enumerated nor pinned transitively, leaving the chain unbounded from the
  package's point of view.
- **Evidence that would decide it.** A full transitive fetch-and-follow of the reference
  graph to a declared depth, with every node's content and digest recorded — the
  whitepaper's "audit references transitively" mitigation executed, with its depth limit
  written down as a declared scope boundary rather than a silent truncation.

### `AST05-S04` — Relay-Node Amplification

- **Why one package cannot decide it.** The vulnerable object is a *chain*, not a skill.
  Which backbone model runs each node, and in what order the nodes are wired, are
  deployment facts. The same skill definitions compose into a resistant chain on one
  deployment and a vulnerable one on another after a model swap alone.
- **Enabling precondition the package shows** (`artifact_signal`): decision rules that
  consume upstream skill output without re-establishing an instruction-versus-data
  boundary at the hop.
- **Evidence that would decide it.** The pipeline topology (node order and adjacency),
  the backbone model bound to each node, and a per-node injection-resistance measurement
  — then the chain's resistance read off as the minimum over that path, per the
  whitepaper's own statement of the property. None of that is package content.

### `AST05-S06` — Denial-of-Service (DoS) through Malicious Skills

- **Why one package cannot decide it.** "Excessive" is defined by a budget the package
  does not carry: the host's token quota, API rate limits, memory ceiling, and how many
  other agents share the same infrastructure.
- **Enabling precondition the package shows** (`artifact_signal`): unbounded loops or
  retries and absent rate, token, or timeout budgets in bundled scripts.
- **Evidence that would decide it.** The deployment's resource budget plus measured
  consumption under representative load — a runtime observation against a stated quota,
  which is what turns "a loop" into "a denial of service".

### Agent-judgable (in-artifact, not mechanically decidable)

- **`AST05-S05` Malicious Instructions Embedded in Documents.** Not uncovered — the
  evidence is in the package — but scored by the judge harness, never by a deterministic
  detector, and never in the F1 denominator. Deciding it requires reading the skill's
  document-handling prose and code and judging whether the instruction-versus-data
  boundary it establishes is adequate. A mechanical proxy ("is there a delimiter?")
  answers a different, easier question.

## F1 denominator statement

**Which scenarios count: none.** AST05's static-detectable tier is empty. `AST05-S05` is
agent-judgable and is routed to the judge harness, never folded into F1
(`detectors/engine.py::run_category` returns it in the separate `agent_judgable` tuple).
The other five are out-of-artifact and are reported as declared-and-uncovered above.

**AST05 therefore publishes no F1, and that is a deliberate honesty choice.** The locked
gate-4 rule is that a category with an empty detectable tier publishes no F1 and is
reported declared-and-uncovered rather than padded to manufacture a number. AST05 is the
sharpest case in the repository for that rule. It would be trivial to author six fixtures
around "does the skill pin a content hash?" and publish a high F1 under the heading
"AST05 — Untrusted External Instructions". That number would measure unpinned-reference
detection. It would not measure Author Rug-Pull, Bait-and-Switch, chaining, relay
amplification, or DoS, and printing it in AST05's row would tell a reader the category is
covered when the whitepaper's entire named attack surface for it is not decidable here.
Publishing nothing is the accurate report.

**What the existing corpus is, then.** `fixtures/AST05/` does hold six cases, and all six
are declared `covers: artifact-signal-only` in `fixtures/manifest.yaml`
(`f1_scope: artifact-signal-only`, `status: proxy-covered`). They measure declared
`artifact_signal` preconditions — a fetch routed into an instruction sink, a response body
routed into an executable sink, a missing boundary marker — not the scenarios those
signals belong to. If that corpus is ever scored, the number must carry the
`artifact-signal-only` label and must not appear as AST05's row in the Gate B
per-category F1 table. `published_f1` is currently `pending-detector`; that is also
accurate, since no loader converts these fixtures into the `pkg` mapping the detector
consumes, and neither implemented check can fire on a USF-conformant manifest anyway.

## Corpus entitlement and actual count

| Quantity | Value | Source |
| --- | --- | --- |
| Registry scenarios in AST05 | 6 | `scenarios/registry.yaml` |
| Registry static-detectable | **0** | no scenario qualifies |
| Entitlement at full registry coverage — `max(6, 2 × 0)` | **none** (`null`) | `cases_at_full_static_coverage`; the formula is not applied to an empty tier |
| Labeled proxy checks in the corpus | 3 | `AST05-S1`, `AST05-S2`, `AST05-S3` in `fixtures/manifest.yaml`, all `covers: artifact-signal-only` |
| Declared expected cases for the proxy corpus — `max(6, 2 × 3)` | **6** | `declared_expected_cases` |
| Fixture files actually present under `fixtures/AST05/` | **6** | 3 vulnerable + 3 clean, class-balanced |

AST05's scenario-level entitlement is zero cases. The six present are the proxy corpus,
sized by the same formula applied to the three artifact-signal checks it labels. They are
not padding toward a scenario F1: the manifest declares up front what they measure and
withholds the scenario-level claim.

Present on disk, all six matching the manifest's declared paths:

```
fixtures/AST05/V1-unsanitized-fetched-instructions/SKILL.md  vulnerable  -> proxy for AST05-S01 / AST05-S05
fixtures/AST05/C2-unsanitized-fetched-instructions/SKILL.md  clean       -> proxy for AST05-S01 / AST05-S05
fixtures/AST05/V3-eval-remote-response/SKILL.md              vulnerable  -> proxy for AST05-S05
fixtures/AST05/C4-eval-remote-response/SKILL.md              clean       -> proxy for AST05-S05
fixtures/AST05/V5-absent-boundary-marker/SKILL.md            vulnerable  -> proxy for AST05-S04 / AST05-S05
fixtures/AST05/C6-absent-boundary-marker/SKILL.md            clean       -> proxy for AST05-S04 / AST05-S05
```

## Reconciliation debt

1. **The module's interim tiers overclaim.** `SCENARIO_TIERS` declares two ids
   `static-detectable`, which makes `f1_report` report `measured` for a category whose
   detectable tier this matrix (and the registry) hold empty. Reconcile the module to
   this file.
2. **Both implemented checks are dead against USF v1.** They read
   `permissions.network.policy`; `schemas/usf-v1.schema.json` defines
   `permissions.network` with `allow` and an optional `deny` only, and rejects unknown
   keys. Re-express them against `permissions.network.allow` (empty list = no egress;
   wildcard entries = over-broad) or retire them.
3. **Neither implemented check has a fixture pair, and no fixture check has a
   detector.** The corpus labels fetch-to-sink dataflow, `eval` of a response body, and a
   missing boundary marker; the detector implements neither of those three. The two
   halves of this category do not currently meet.
4. **No fixture loader.** Nothing maps `fixtures/AST05/*/SKILL.md` onto the detector's
   `pkg` shape.

None of this changes the headline: even with every item above closed, AST05 still
publishes no scenario-level F1, because the tiering — not the tooling — is what empties
the denominator.

## Change control

The tiering above is bound to `tier_lock_hash`
`3dc23889393d91e314c4eb3c52186cc807d00fd3c4f5ce0d9a05c03736753365`
(`validators/tier_lock.py`). Promoting any AST05 scenario into the detectable tier
invalidates the existing labels, changes the hash, and requires the corpus to be
re-labeled and the judge run repeated before anything may be published (ADR-0004, S-011).
