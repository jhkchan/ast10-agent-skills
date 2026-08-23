# AST09 — No Governance: coverage matrix

Audit artifact. It states, for each of the seven attack scenarios the whitepaper names
under AST09, which tier it is in, what this skill package's detector actually checks for
it, and why. It is not a summary of the whitepaper's AST09 section.

| Field | Value |
| --- | --- |
| Authoritative tiering | `scenarios/registry.yaml` (AST09-S01 … AST09-S07) |
| Corpus binding | `fixtures/manifest.yaml` → `categories.AST09` |
| Tier-lock hash (S-011) | `d00ac953cdec9d37cf5d19e389772d067080cc2859bf54de715ee3f3ab8081bc` |
| Detector under audit | `skills/AST09/scripts/detector.py` |
| Whitepaper scenarios | 7 (body of the AST09 "Attack Scenarios" section) |
| Tier split | 0 static-detectable · 0 agent-judgable · **7 out-of-artifact** |
| Published F1 | **none** — see "F1 denominator" below |
| Status | `declared-and-uncovered` |

Tier definitions are `scenarios/registry.yaml` → `tier_doctrine`; the contract that makes
this matrix binding on the F1 denominator is `docs/adr/0004-per-scenario-detectability-contract.md`.
Changing any tier below changes the tier-lock hash and forces re-labeling plus a judge
re-run before an F1 for this category could be published (`validators/tier_lock.py`).

## Scenario table

Titles are the whitepaper's own sub-headings, verbatim. The "detector checks" column
records what `skills/AST09/scripts/detector.py` executes today — not what it could
plausibly be extended to check.

| Scenario id | Whitepaper title | Tier | What the detector actually checks | Reason for the tier |
| --- | --- | --- | --- | --- |
| AST09-S01 | Undetected Compromise | out-of-artifact | — | "No alert fires because no inventory exists" is a claim about the deploying organization's monitoring, not about any field, byte, or structure of the package. The identical artifact is caught on install at an organization that keeps an inventory and missed at one that does not, so the package cannot be the discriminator. |
| AST09-S02 | Unapproved Malicious Skill | out-of-artifact | — | Approval status is state held by the installing organization's workflow. A package carries no record of whether anyone reviewed it; an approved and an unapproved copy of the same skill are byte-identical. |
| AST09-S03 | Orphaned Skill | out-of-artifact | — | Employment status and credential lifecycle are HR and IAM state. Nothing inside the package changes when its installer leaves the organization. This is spec.md S-003's named example and the scenario ADR-0004 cites as the reason the denominator must be narrowed rather than inflated. |
| AST09-S04 | Regulatory Exposure | out-of-artifact | — | Whether the data a skill touches is regulated depends on the deploying organization's data classification and jurisdiction, both maintained outside the artifact; and "no audit trail" is a property of the runtime's logging, not of the manifest. A package cannot show either half. |
| AST09-S05 | Unreachable Skill | out-of-artifact | — | The whitepaper's own framing forecloses artifact analysis: "there is no host to scan and no local package manifest to read". The scenario is the absence of an obtainable artifact, so no artifact-side rule can have a subject to run against. |
| AST09-S06 | Cascading Agent Compromise | out-of-artifact | — | Propagation depends on the multi-agent pipeline's topology and on where human checkpoints sit — deployment facts spanning many packages. One package is one node and cannot see its own downstream. |
| AST09-S07 | Manipulated Trust Signals | out-of-artifact | — | Stars, install counts, and reputation are registry-side and platform-side state. A package cannot show that the reputation attached to it was farmed; a genuinely popular skill and an astroturfed one ship the same bytes. |

**Detector reconciliation.** `skills/AST09/scripts/detector.py` registers `DETECTORS = {}`
— zero detector functions — and `STATIC_DETECTABLE` derives to the empty set, which is
consistent with every row above. Two known drifts in that file, recorded here rather than
silently tolerated: its interim `SCENARIO_TIERS` map is keyed by slugs
(`AST09-orphaned-skill`, `AST09-regulatory-exposure`, `AST09-undetected-compromise`) that
are not registry ids, and it enumerates only 3 of the 7 scenarios. Its own docstring
declares it superseded by the registry and by this file. This matrix, not that map, is the
tier of record for AST09; the map's omissions change nothing about coverage, because all
seven scenarios are out-of-artifact and the detector set would be empty under either
enumeration.

## Declared and uncovered

Every AST09 scenario is out-of-artifact, so this section is the whole category. Each row
states why one skill package cannot decide it and names the evidence that would.

**AST09-S01 — Undetected Compromise.** Cannot be decided from a package: the scenario's
defining condition is that no alert fired, which is an event (or non-event) in the
organization's monitoring pipeline. *Evidence that would decide it:* a centralized skill
inventory carrying name, version, hash, install date, installer identity, and last scan
status, joined against workspace event telemetry for the interval after installation, so
that "a malicious skill was present" and "nothing alerted on it" can both be established.

**AST09-S02 — Unapproved Malicious Skill.** Cannot be decided from a package: approval is
an organizational act performed on the package, leaving its trace in the approver's system
rather than in the artifact. *Evidence that would decide it:* an approval-queue or change
record keyed to this skill's content hash showing a review decision (or its absence),
together with the installation record naming the registry the copy came from.

**AST09-S03 — Orphaned Skill.** Cannot be decided from a package: the defining facts are
that the installer has left and that their credentials remain live. *Evidence that would
decide it:* the offboarding record for the installer identity in the inventory entry,
joined to IAM/NHI state showing the credential or scoped non-human identity the skill still
runs under is unrevoked.

**AST09-S04 — Regulatory Exposure.** Cannot be decided from a package: both halves —
"the data is regulated" and "there is no audit trail" — live outside it. *Evidence that
would decide it:* the organization's data classification for the resources the skill
actually touched at runtime plus the applicable jurisdiction, and, for the audit-trail
half, the presence or absence of the whitepaper's bilateral receipts over real executions
(a signed admission receipt carrying `scope` and `policy_version` joined by `attempt_id`
to a signed outcome receipt carrying `terminal_state`).

**AST09-S05 — Unreachable Skill.** Cannot be decided from a package for the strongest
possible reason: there is no package to obtain. Endpoint- and registry-based discovery
never sees a skill living inside a managed SaaS copilot whose endpoints the security team
does not administer. *Evidence that would decide it:* identity- and posture-based discovery
from SaaS telemetry — OAuth consent grants, connected-app inventories, non-human-identity
activity, scope assignments — reconciled against the approved inventory so unmatched
identities surface. That evidence is identity-side by construction; no artifact-side
substitute exists, and reporting a clean endpoint scan over-claims coverage here.

**AST09-S06 — Cascading Agent Compromise.** Cannot be decided from a package: the scenario
is a relation between nodes in a pipeline. *Evidence that would decide it:* the pipeline's
topology, the location of human checkpoints in it, and per-hop provenance for the relayed
instruction — concretely, an admission-receipt chain linked by `parent_action_ref` back to
a root. Note the limit even then: the receipt model's version 1 covers a single upstream
parent, and fan-in joins remain an open proposal (OWASP issue #44), so a multi-parent
admission is not guaranteed a complete causal reconstruction. Evidence that would decide
this scenario is therefore not merely absent from the artifact; part of it is not yet
specified anywhere.

**AST09-S07 — Manipulated Trust Signals.** Cannot be decided from a package: reputation is
stored by the registry, not by the skill. *Evidence that would decide it:* a registry-side
time series of stars, installs, and reviews with the account provenance behind them —
account ages, creation clustering, and cross-registry correlation of the same publisher
identities.

No AST09 scenario carries an `artifact_signal` in the registry: for this category there is
not even a partial in-package proxy to record. That is unique to AST09 — AST10, by
contrast, has three scenarios with declared proxies (see that category's matrix).

## F1 denominator

**AST09 publishes no F1 number, at any corpus size.**

The denominator for a category is drawn from its declared-detectable tier
(ADR-0004; enforced in `detectors/engine.py`, which scores the static-detectable subset and
reports the agent-judgable subset separately rather than folding it in). For AST09 both
readings coincide and both are empty: 0 static-detectable and 0 agent-judgable out of 7
scenarios. Zero scenarios qualify, so precision and recall have no denominator and
`detectors/scaffold.f1_report` returns `{"status": "declared-and-uncovered", "f1": None}`
rather than a number.

This is a deliberate honesty choice, not a gap in the work. The only way to print an F1 here
would be to hand-write fixtures that encode an organizational fact — an "orphaned" skill
whose SKILL.md says the author left, a "regulated" skill whose description mentions PHI —
and then detect the string that was planted. That measures the fixture author, not the
detector, and it would let a reader believe the suite covers a scenario it demonstrably
cannot see. Gate-4's never-pad rule and spec.md S-003 both require the opposite: publish
the empty tier as `declared-and-uncovered`, with the seven written reasons above as the
audit trail. A reader who disagrees with a tier can attack a specific reason; a reader given
a manufactured 1.00 would have nothing to attack.

Consequence, stated plainly so it is not discovered later: **the AST09 skill's grade is
unaffected by its inability to detect any of these scenarios** (S-003), and no AST09 row
appears in any F1 pass/fail comparison.

## Corpus size

| Quantity | Value |
| --- | --- |
| Detectable scenarios (static-detectable, labeled) | 0 |
| Entitlement under `max(6, 2 × detectable)` | **0 cases — the formula does not apply** |
| At hypothetical full static coverage | n/a (`cases_at_full_static_coverage: null`) |
| Fixture files actually present under `fixtures/AST09/` | **0** (directory exists and is empty) |
| Cases declared in `fixtures/manifest.yaml` | 0 (`cases: []`) |

The `MIN_FLOOR = 6` term is a floor on a corpus that exists, not a quota to be filled. When
the detectable tier is empty, gate-4's never-pad rule overrides the floor: the category
ships zero cases and `status: declared-and-uncovered`, which is exactly what
`fixtures/test_manifest.py::test_case_count_matches_locked_gate4_formula` asserts for this
branch. Six fixture packages here would be six artifacts labeled against scenarios no
artifact can express, so the entitlement is 0 and the actual count of 0 matches it.

Nothing about this changes unless the registry re-tiers an AST09 scenario, which trips the
tier lock and requires this matrix, the manifest entry, and the detector to move together.
