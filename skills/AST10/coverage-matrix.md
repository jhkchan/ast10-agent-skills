# AST10 — Cross-Platform Reuse: coverage matrix

Audit artifact. It states, for each of the six attack scenarios the whitepaper names under
AST10, which tier it is in, what this skill package's detector actually checks for it, and
why. It is not a summary of the whitepaper's AST10 section.

| Field | Value |
| --- | --- |
| Authoritative tiering | `scenarios/registry.yaml` (AST10-S01 … AST10-S06) |
| Corpus binding | `fixtures/manifest.yaml` → `categories.AST10` |
| Tier-lock hash (S-011) | `42cb24ed85f5305ab26a57d54aec3361fc7b74d02155254342fd221b821bd4ae` |
| Detector under audit | `skills/AST10/scripts/detector.py` |
| Whitepaper scenarios | 6 (body of the AST10 "Attack Scenarios" section) |
| Tier split | **1 static-detectable** · 0 agent-judgable · 5 out-of-artifact |
| Detectable scenarios labeled and implemented | **1 of 1** (AST10-S06) |
| Published F1 | **1.00** over 6 labeled cases — scope `scenario-level`; read "F1 denominator" before quoting it |
| Status | `covered` |

Tier definitions are `scenarios/registry.yaml` → `tier_doctrine`; the contract that makes
this matrix binding on the F1 denominator is `docs/adr/0004-per-scenario-detectability-contract.md`.
Changing any tier below changes the tier-lock hash and forces re-labeling plus a judge
re-run before an F1 for this category could be republished (`validators/tier_lock.py`).

**Authority chain.** The whitepaper's own "Attack Scenarios" body for AST10 outranks
everything here on the enumeration itself — how many scenarios exist, and their titles
verbatim. `scenarios/registry.yaml` is authoritative on tier; this file reproduces its
tiering and may not diverge from it. This file is authoritative on the F1 denominator,
the corpus accounting and the coverage debt. `fixtures/manifest.yaml` is authoritative on
which fixture cases exist and what they are labeled against. The `SCENARIO_TIERS` dict
inside `skills/AST10/scripts/detector.py` is implementation and is subordinate to all of
them.

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
| AST10-S06 | Silent Supply Chain Injection | **static-detectable** | **`detect_encoded_payload_injection`.** Two conditions, either sufficient. **C1 decode-and-rescan:** every base64, bare-hex, `\xNN`-escape and percent-encoded run in the package's files *and* in its manifest values is decoded (plus one gzip/zlib layer beneath, and one further encoding layer for double-encoded blobs), and the DECODED text is matched against eight payload-behaviour signatures — interpreter invocation, destructive filesystem ops, credential harvesting, writes to the USF identity files (`SOUL.md`/`MEMORY.md`/`AGENTS.md`), fetch-and-execute, outbound exfiltration, reverse shells, dynamic-execution sinks. **C2 decode-then-execute:** an encoded literal decoded and handed to an execution sink, either on one line or across a single `name = <decode>` … `exec`-of-`name` def-use edge. Blobs that decode to binary (an icon), to configuration, or to nothing readable are **not** reported, and the hex `content_hash` / `signature` / `integrity` fields USF itself mandates are excluded by field name. | The named vector is an encoded script block — a byte pattern inside the package. Decoding it and re-scanning the decoded content is deterministic and platform-independent, with no prose intent-reading required. It is precisely the whitepaper's own "build platform-agnostic skill scanners that evaluate the content layer independently of the runtime" mitigation, so the tier follows the whitepaper's own claim about what is checkable. |

**Detector reconciliation.** `skills/AST10/scripts/detector.py` registers exactly one
detector function, keyed `AST10-S06`, and `STATIC_DETECTABLE` derives to `{"AST10-S06"}` —
which is the registry's static-detectable set for this category, so the module's coverage
and the registry's tiering are the same set rather than two lists that happen to agree.
The two drifts previous revisions of this matrix recorded are **closed, not tolerated**:
the module's `SCENARIO_TIERS` is now keyed by canonical registry ids and enumerates all six
scenarios, so it no longer speaks a private slug dialect (`AST10-cross-registry-arbitrage`)
nor omits AST10-S06. This matrix remains the tier of record, and it now agrees with the
module line for line; `tests/test_coverage_matrix_ast09_ast10.py` fails if they diverge
again.

**What C2 is for, since C1 looks like the whole check.** A payload can be encrypted, keyed
remotely, or wrapped in a third layer, and then C1 reads only noise. C2 fires on the
*structure* instead — an opaque literal decoded straight into an interpreter is the
"without structural validation" clause of the scenario, whatever the bytes turn out to say.
`test_an_unreadable_payload_reaching_a_sink_still_fires` pins that case, and asserts that C1
genuinely cannot read it, so the test cannot silently degrade into a second C1 test.

Re-derive the ids, titles and tiers in this table from the authority at rank 2,
so a reader can check the table rather than believe it:

```
python3 -c "import yaml; [print(s['id'], '|', s['title'], '|', s['tier']) for s in yaml.safe_load(open('scenarios/registry.yaml'))['scenarios'] if s['category']=='AST10']"
```

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

**AST10-S06 — Silent Supply Chain Injection** is *not* in this section, and no longer
appears in `uncovered_static_detectable` either. It is static-detectable, it is
implemented, and it is measured. It is listed here only to say where it went, because a
reader who remembers the earlier revision of this file will look for it among the gaps.

## F1 denominator

**AST10 publishes F1 = 1.00, scope `scenario-level`, over 6 labeled cases.**

The denominator is drawn from the declared-detectable tier and nothing else (ADR-0004;
enforced in `detectors/engine.py`, which scores the static-detectable subset and reports
the agent-judgable subset separately rather than folding it in). AST10 has no
agent-judgable scenarios, so the denominator is the single static-detectable one, AST10-S06,
and every one of the six cases is labeled against it. The measured confusion matrix is
**tp 3 · fp 0 · fn 0 · tn 3**.

**What that number is, stated before anyone quotes it.** It is a discrimination measurement
on a hand-built corpus of six packages, not an estimate of field performance. Its whole
value rests on the negatives being hard, so they were built to be:

| Clean case | Encoded content it really carries | Why a naive scanner fires on it |
| --- | --- | --- |
| `C2-encoded-shell-payload` | a base64 PNG icon in `SKILL.md` **and** a base64 JSON defaults block decoded at import | two base64 blobs, one of them decoded by the package itself |
| `C4-hex-escaped-payload` | a `\xNN`-escaped banner string, plus the USF `content_hash` (64 hex) and `signature` (128 hex) | three long hex runs, one of them an escape sequence |
| `C6-gzip-archive-payload` | a gzip-under-base64 blob — the same two-layer shape as the vulnerable case — holding a USF policy document | identical encoding structure to `V5`; only the decoded content and the sink differ |

Two degenerate strategies are measured against the same six packages, not merely asserted
to be worse. `test_the_corpus_defeats_both_degenerate_baselines` computes them:

| Strategy | tp | fp | fn | tn | precision | recall | F1 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| "the package contains an encoded blob" | 3 | 3 | 0 | 0 | 0.50 | 1.00 | **0.67** |
| "a payload signature matches the package's raw source, undecoded" | 3 | 3 | 0 | 0 | 0.50 | 1.00 | **0.67** |
| the shipped check (decode, then evaluate the content layer) | 3 | 0 | 0 | 3 | 1.00 | 1.00 | **1.00** |

0.67 with recall 1.00 and precision 0.50 is the coin flip: fire on everything, be right half
the time. Both naive strategies land exactly there, for different reasons — the first because
every clean package carries a real encoded blob, the second because `AGENTS.md` appears in
every package's `permissions.files.deny_write` where a source grep cannot tell a *protection*
from a *target*. The corpus is shaped so those two failure modes are visibly distinguishable
from the shipped check, and that separation is the only claim the 1.00 supports.

`skills/AST10/scripts/test_ast10_detector.py::test_published_f1_in_the_manifest_matches_what_the_detector_measures`
re-derives `published_f1` from the corpus through `detectors/corpus.py` — the shared join
that reads the manifest's own `detector_check` labels — so the number in
`fixtures/manifest.yaml` cannot be a hand-written aspiration. Two further tests guard the
corpus rather than the score: `test_every_clean_fixture_actually_carries_an_encoded_blob`
fails if a clean case is ever softened into a package with no encoded content, and
`test_the_same_separation_holds_under_the_shipped_cli_loader` replays the six packages
through `cli/lib/bridge.py`, which presents `skill.usf.yaml` as scannable text rather than
as a parsed manifest. The USF integrity fields are excluded by surface key under one reader
and by line context under the other; a separation that held under only one would be a check
tuned to a loader.

**Known limits, so a reviewer does not have to find them.** Three, each a consequence of the
mechanism rather than a bug in it. (1) A package that base64-encodes its own *documentation*
— a README whose prose quotes `curl … | sh` as an example — decodes to text matching a
payload signature and is reported. That is a false positive the check will produce, and the
right response is a reviewer reading the decoded excerpt the evidence string carries, not a
narrower signature set. (2) A payload encoded three or more layers deep, or encoded in a
scheme the extractor does not implement (base32, base85, custom alphabets), is invisible to
C1; C2 still catches it whenever the decode chain terminates in an execution sink, but a
deeply-encoded payload written to disk for a *later* process is not caught by either.
(3) The check reads text surfaces only. A payload inside a binary file the loader skips is
out of scope, and `cli/lib/bridge.py` records such files as `skipped_files` rather than
counting them clean.

**What is still refused.** No F1 is published over the five out-of-artifact scenarios, and
none can be. Cross-registry arbitrage, multi-platform campaigns, manifest stripping, and
implicit privilege escalation can all be *narrated* inside a single fake SKILL.md — "this
skill was ported from OpenClaw and lost its permissions block" — and a detector that
grepped that narration would score perfectly against it. That number would measure the
fixture author's imagination. `detectors/engine.py` raises `OutOfArtifactFixtureError`
rather than scoring such a case, and the three declared `artifact_signal` proxies above are
recorded precisely so that a proxy can never be quietly promoted into the denominator under
the scenario's name.

## Corpus size

| Quantity | Value |
| --- | --- |
| Detectable scenarios in the registry | 1 (AST10-S06) |
| Detectable scenarios labeled in `fixtures/manifest.yaml` | 1 |
| Entitlement under `max(6, 2 × detectable)` | **6 cases**, class-balanced 3 vulnerable / 3 clean |
| Cases declared in `fixtures/manifest.yaml` | 6 |
| Fixture packages present under `fixtures/AST10/` | **6** (`V1`/`C2`, `V3`/`C4`, `V5`/`C6`) |

The `MIN_FLOOR = 6` term binds here rather than the `2 × 1 = 2` term, and that is the
point of the floor: implementing one detectable scenario obliges six labeled cases, not one
demonstration case and not a corpus sized to whatever the detector happens to pass. The
cases are paired by mechanism — each clean case is the vulnerable case with the payload
removed and the encoding kept — so the pairing is what carries the discrimination claim,
not the raw count.

Nothing about this changes unless the registry re-tiers an AST10 scenario, which trips the
tier lock and requires this matrix, the manifest entry, and the detector to move together.
