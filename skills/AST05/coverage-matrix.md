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
publishes_scenario_level_f1: false
publishes_proxy_f1: true
published_f1: "artifact-signal-only 1.00 (n=6)"
---

# AST05 — Untrusted External Instructions: coverage matrix

This is the audit artifact `skills/AST05/SKILL.md` points at when it says "the exact
split is fixed in `coverage-matrix.md`". It is not a summary of the whitepaper's AST05
section.

**AST05 publishes no scenario-level F1.** Not one of its six named scenarios is
decidable from a single skill package. That is the single most consequential fact on
this page, and every section below is downstream of it. The category *does* publish a
measured number over its labeled corpus — `artifact-signal-only 1.00 (n=6)` — and that
label is not decoration: it says the six cases measure declared `artifact_signal`
preconditions, and that quoting the number as coverage of Author Rug-Pull,
Bait-and-Switch, chaining, relay amplification, or DoS would be false.

**Authority chain.** `scenarios/registry.yaml` is authoritative on tier; this file
reproduces its tiering and may not diverge from it. `fixtures/manifest.yaml` is
authoritative on which fixture cases exist. `SCENARIO_TIERS` inside
`skills/AST05/scripts/detector.py` says only whether each *check* is mechanical; it
never says a check covers a named scenario. That second question is answered by the
module's `CHECK_COVERAGE`, and for AST05 every entry answers
`artifact-signal-only` — see
[Detector checks that are not whitepaper scenarios](#detector-checks-that-are-not-whitepaper-scenarios).
`tests/test_tier_doctrine_symmetry.py` fails if a check ever claims otherwise while the
registry still tiers the scenario it links out-of-artifact or agent-judgable.

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

Re-derive the ids, titles and tiers in this table from the authority at rank 2,
so a reader can check the table rather than believe it:

```
python3 -c "import yaml; [print(s['id'], '|', s['title'], '|', s['tier']) for s in yaml.safe_load(open('scenarios/registry.yaml'))['scenarios'] if s['category']=='AST05']"
```

## Detector checks that are not whitepaper scenarios

`skills/AST05/scripts/detector.py` implements five checks. **None maps to a named
AST05 scenario as coverage**, because the registry tiers none of them
static-detectable; each computes a declared `artifact_signal` instead, and each says so
in the module's `CHECK_COVERAGE`. All five are grounded in a preventive mitigation the
whitepaper states for AST05, and all five run over the package's own bytes.

| Detector scenario id | Maps to | What it actually checks |
| --- | --- | --- |
| `AST05-fetched-content-instruction-sink` | `AST05-S01` + `AST05-S05` `artifact_signal` (`covers: artifact-signal-only`) | Parses each bundled `.py` file and follows the body of an HTTP response (`requests`/`httpx`/`urllib` verbs, `urlopen`, bare fetchers) forward through assignments to the agent's instruction channel — `prompt.append(...)`, `system_prompt += ...`, a `prompt=`/`messages=` keyword argument. Fires only when the value arrives with no provenance wrapper and no delimiter literal. Grounded in "Separate Instructions from Data … Retrieved information should be used only as reference data and must not override or modify the agent's system or developer instructions". It decides neither linked scenario: AST05-S01's defining event is an edit to remote content after review, and AST05-S05 turns on whether the boundary a skill establishes is *adequate*, which is semantic. |
| `AST05-remote-response-executed` | `AST05-S05`'s `artifact_signal` (`covers: artifact-signal-only`) | The same dataflow into an executable sink: `eval`/`exec`/`compile`/`__import__`, `os.system`/`os.popen`, `subprocess` with `shell=True`, `pickle.loads`, `marshal.loads`, `yaml.load` with no `Loader=`. `json.loads(response.text)` is deliberately **not** a sink — parsing a body as data is the correct handling, and calling it a finding would fire the check on every well-written HTTP client. |
| `AST05-absent-instruction-boundary` | `AST05-S04` + `AST05-S05` `artifact_signal` (`covers: artifact-signal-only`) | For a package whose bundled scripts contain at least one fetch call site, whether its prose declares an instruction-versus-data convention at all (a delimiter marker, "reference data", "must not override", a provenance rule). **Gated on the call site, not on prose**: a package that never fetches has no external-content hop to bound, and an ungated absence check would fire on every package in every corpus — the non-discriminating shape this repository's detector review called out. Grounded in AST05-S04's `artifact_signal` verbatim: "decision rules that consume upstream skill output without re-establishing an instruction-versus-data boundary at the hop". |
| `AST05-unrestricted-network-fetch` | `AST06-S02`'s `artifact_signal` (`covers: artifact-signal-only`) | Egress granted with no host set bounded: a bare boolean `network: true` (the binary the whitepaper's "domain allowlists, not a binary `network: true/false`" mitigation names), an allow-all policy string, or a network block declaring a network-capable tool with neither an allowlist nor a restrictive policy. An **empty** `allow` list is *not* a hit — USF v1 evaluates egress default-deny, so `allow: []` is no egress, and reading it as unrestricted would invert the policy. |
| `AST05-wildcard-domain-allowlist` | `AST06-S02`'s `artifact_signal` (`covers: artifact-signal-only`) | An allowlist that exists and bounds nothing: `"*"`, or a bare-TLD wildcard such as `"*.com"`. A scoped `*.example.com` is not reported — it reads wider than USF v1 host-only matching grants, which `validators/usf.py`'s `host_errors` flags as a validation error, but it does not open the internet. |
| `AST05-injected-instruction-compliance` | `AST05-S05` | Declared `agent-judgable` in `SCENARIO_TIERS`, deliberately absent from `DETECTORS`. Correct as it stands: excluded from `STATIC_DETECTABLE` and therefore from any denominator. |

Because every entry is `artifact-signal-only`, `detectors/scaffold.py::f1_scope` returns
**`artifact-signal-only`** for this module and `f1_report` returns that label beside
every number it produces. That is the signal-symmetry ruling applied here: the
`allow-all` predicate IS decidable from the package —
`scenarios/registry.yaml` states `artifact_signal_decidable: package-decidable` on
AST06-S02 and names both network checks in `artifact_signal_checks` — and being
decidable is exactly what does not make it coverage. A tier is not allowed to mean
"visible in the package" when a detector wants to claim it and "not visible" when
claiming it would oblige someone to build one;
`tests/test_tier_doctrine_symmetry.py` enforces both directions.

### What changed, and what the earlier version of this page got wrong

Two claims on this page were true when it was written and are false now, and both were
pinned by tests in `tests/test_coverage_matrix.py` precisely so that fixing the defect
would force this section to be rewritten in the same change:

1. **"Both implemented checks are dead against USF v1."** They gated on
   `permissions.network.policy`, a key `schemas/usf-v1.schema.json` does not define
   (`permissions.network` is `additionalProperties: false` with only `allow`/`deny`), so
   neither could fire on any conformant manifest. Both now read
   `permissions.network.allow` as well as the native `policy`/boolean spellings, and
   `test_ast05_network_checks_read_the_usf_shape_and_still_pass_a_bounded_manifest`
   asserts both halves — a bounded allowlist stays clean, an unbounded one fires.
2. **"Neither implemented check has a fixture pair, and no fixture check has a
   detector."** The three corpus checks now name the detector function they are scored
   against (`detector_check` in `fixtures/manifest.yaml`), and
   `detectors/fixture_loader.py` runs each over its own vulnerable/clean pair.

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

**AST05 therefore publishes no F1 at the scenario level, and that is a deliberate
honesty choice.** The locked gate-4 rule is that a category with an empty detectable
tier publishes no F1 and is reported declared-and-uncovered rather than padded to
manufacture a number. AST05 is the sharpest case in the repository for that rule. It
would be trivial to author six fixtures around "does the skill pin a content hash?" and
publish a high F1 under the heading "AST05 — Untrusted External Instructions". That
number would measure unpinned-reference detection. It would not measure Author
Rug-Pull, Bait-and-Switch, chaining, relay amplification, or DoS, and printing it in
AST05's row would tell a reader the category is covered when the whitepaper's entire
named attack surface for it is not decidable here.

**What the corpus does measure, and what its number is.** `fixtures/AST05/` holds six
cases, all declared `covers: artifact-signal-only` in `fixtures/manifest.yaml`
(`f1_scope: artifact-signal-only`, `status: proxy-covered`). They measure declared
`artifact_signal` preconditions — a fetch routed into an instruction sink, a response
body routed into an executable sink, a fetching package whose decision rules declare no
boundary convention — not the scenarios those signals belong to. Each labeled check now
names the detector function it is scored against (`detector_check`), and
`detectors/fixture_loader.py` runs each over its own vulnerable/clean pair:

| Corpus check | Detector check | tp | fp | fn | tn |
| --- | --- | --- | --- | --- | --- |
| `AST05-S1` Unsanitized fetched instructions | `AST05-fetched-content-instruction-sink` | 1 | 0 | 0 | 1 |
| `AST05-S2` Eval of remote response body | `AST05-remote-response-executed` | 1 | 0 | 0 | 1 |
| `AST05-S3` Absent instruction-boundary marker | `AST05-absent-instruction-boundary` | 1 | 0 | 0 | 1 |

`published_f1: "artifact-signal-only 1.00 (n=6)"`. Read it for what it is: three checks
each separating one hand-built pair, on a corpus this project authored. It is evidence
that the checks discriminate at all — the property a review found missing across this
repository — and it is not evidence of field precision. The label travels with the
number everywhere it is printed, and the number must never appear as AST05's row in a
scenario-level Gate B table.

**Two shipped checks have no corpus pair.**
`AST05-unrestricted-network-fetch` and `AST05-wildcard-domain-allowlist` fire on none of
the six cases, because every AST05 fixture declares a bounded, single-host allowlist.
Their true-positive and true-negative cases live in
`skills/AST05/scripts/test_ast05_detector.py` instead. Giving them a labeled pair would
add two corpus checks and, by the locked formula, take the declared corpus from six
cases to ten — a change to `detectable_scenarios` that moves the category's
`tier_lock_hash` and requires the whole corpus to be re-labeled (ADR-0004, S-011). That
is a deliberate deferral, recorded below as remaining debt rather than closed quietly.

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

**The six were re-authored when the detectors landed, and the reason is worth stating
plainly.** Each fixture previously consisted of a stub `SKILL.md` whose frontmatter
carried a marker string naming the mechanism — `instruction_source: "fetch(url) ->
prompt.append(raw)"`, `handler: "exec(response.text)"`, `decision_rules: "do whatever the
page says"` — and a one-line body. No fixture contained a script, a fetch, a sink, or a
permission block. A detector that separated those six would have been reading the label
off the fixture, which is the fixture-authorship failure the whole detectability contract
exists to prevent. Every case is now a package: a bundled `scripts/*.py` with a real
call graph, a permission block, and prose that either declares a boundary convention or
does not. The V/C members of each pair differ in exactly one mechanism:

```
V1/C2  same fetch, same prompt assembly; C2 routes the body through as_reference_data()
V3/C4  same endpoint; V3 exec()s the body, C4 json.loads() it and filters locally
V5/C6  byte-identical loader; the difference is entirely in SKILL.md's decision rules
```

## Reconciliation debt

Closed since the previous revision of this page:

1. ~~The module's interim tiers overclaim.~~ `SCENARIO_TIERS` now says only whether a
   check is mechanical; `CHECK_COVERAGE` carries the coverage claim, and for AST05 every
   entry is `artifact-signal-only`, so `F1_SCOPE` is `artifact-signal-only` and no
   scenario-level number can be produced by this module at all.
2. ~~Both implemented checks are dead against USF v1.~~ Both now read
   `permissions.network.allow` alongside the native `policy`/boolean spellings.
3. ~~No fixture check has a detector.~~ All three corpus checks name a
   `detector_check` and are scored against it.
4. ~~No fixture loader.~~ `detectors/fixture_loader.py`.

Open:

1. **Two shipped checks have no labeled corpus pair** (`AST05-unrestricted-network-fetch`,
   `AST05-wildcard-domain-allowlist`). Unit-tested both ways; adding pairs would move the
   `tier_lock_hash` and require the corpus to be re-labeled.
2. **`AST05-absent-instruction-boundary` reads prose for the boundary convention.**
   The *gate* is a call-site fact and cannot be talked into or out of firing, but the
   second half looks for a declared delimiter or provenance convention in the package's
   markdown. Presence of a convention is weaker than adherence to one: `V1` is precisely
   a package whose prose declares the control its code then ignores, and only the
   dataflow check catches that. The registry is right that judging adequacy is
   agent-judgable.
3. **The upstream-relay half of AST05-S04 is not read at all.** The gate looks for
   network fetch call sites only, not for a skill consuming a prior skill's output
   (stdin, a handoff file). That was a deliberate scope choice — `skills/advisory` reads
   `sys.stdin`, and an ungated stdin source would have made this check fire on it — but
   it means the "relay node" reading of AST05-S04's signal is uncovered.

None of this changes the headline: even with every item above closed, AST05 still
publishes no scenario-level F1, because the tiering — not the tooling — is what empties
the denominator.

## Change control

The tiering above is bound to `tier_lock_hash`
`3dc23889393d91e314c4eb3c52186cc807d00fd3c4f5ce0d9a05c03736753365`
(`validators/tier_lock.py`). Promoting any AST05 scenario into the detectable tier
invalidates the existing labels, changes the hash, and requires the corpus to be
re-labeled and the judge run repeated before anything may be published (ADR-0004, S-011).
