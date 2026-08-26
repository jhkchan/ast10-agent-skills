# What the numbers on the front page are not

Every figure this repository publishes, and the limit that travels with it. The README links
here from the results table; this is the long form.

## What 11 of 11 is, and what it is not

Every skill in the table above clears the ship rule. That is the best number this repository has
ever published and it is the one most likely to be misread, so the four limits on it sit here
rather than in a footnote. The full board, the per-judge bias table and the judge-quality
diagnostics are in [`docs/skill-judge-dashboard.md`](skill-judge-dashboard.md).

**The corpus is self-authored.** The same project wrote the eleven skills, the fixtures, the
scenario registry *and* the rubric-grounded prompt the judges read. A high pooled score is evidence
of **internal consistency** — these artifacts satisfy this repository's own statement of what a good
skill is — and it is **not** external validation. Nobody outside this project has scored these files.

**The panel disagrees by most of a grade band.** Across the same eleven files the six judges span
an **11.4-point spread**, from `bedrock/qwen3-235b` at +6.5 to `bedrock/gpt-oss-120b` at −4.9, while no
judge moves more than 2.3 points between its own rounds — so the spread is systematic bias, not
noise. `bedrock/qwen3-235b` is `COARSE` on this run (79% of its dimension scores sit at a
dimension's maximum, and 34% of its judgments return the full 120) and was flagged
`NON-DISCRIMINATING` on run 4. It is pooled into every published figure in both states, because
dropping a judge for what it said needs its own recorded decision. Dropping it alone takes the board
to **8 of 11**: `AST01`, `AST07` and `AST08` fall below the confidence bound, at 106.7, 107.7 and
107.5. `AST01` fails on two further exclusions as well — drop `anthropic-compatible/glm-5.2` and it
reads 107.2, drop `claude-cli/sonnet` and it reads 107.7 — so three of the six possible
single-judge exclusions block it, and only three leave the board whole. The full table is in
[How fragile 11 of 11 is](skill-judge-dashboard.md#how-fragile-11-of-11-is), and
[ADR-0005](adr/0005-judge-panel-calibration-and-the-lower-bound.md) explains why a pooled mean
may not be quoted beside a single-judge score.

**`k = 1.0` is one standard error of margin, and it is not a confidence level.** The judgments
behind a pooled mean are clustered — six judges reading about three times each, each carrying a
large fixed offset — so they are not independent draws. Measured on run 4, the panel's intraclass
correlation is 0.666 and its design effect 2.15, which means `σ/√n` understates the true standard
error of the mean by roughly **1.47×**. The clause is published in points — it moves the effective
bar from 108.0 to about 109.2 here — and never as a percentage, and
[ADR-0006](adr/0006-confidence-bound-on-the-pooled-mean.md) records the shortfall as the first
thing a future record should fix.

**Ten of the 198 attempted judgments never reached the pool, and the run that discarded them
recorded nothing.** The board is 188 binding judgments; the harness that refused the other ten built
its audit trail in memory, and the reasons and the raw responses are gone. Which skill, judge and
round each was is recoverable from the order the surviving judgments are stored in, and
[`eval/run5-refusals.md`](../eval/run5-refusals.md) is that reconstruction. It matters because the gap
is not neutral: `AST01` lost the two judges that scored `AST01` lowest (100.5 and 104.5 against its
pooled 110.1), and replacing each missing attempt with that judge's own observed mean on that skill
puts `AST01` at 109.2 with a confidence bound of **107.6** — below the bar. Nothing is imputed into
any published figure and no verdict is re-issued; the eleventh ship simply depends on two judgments
nobody can produce. The harness now persists every refusal, and `python3 scripts/refusal_ledger.py`
fails if a scorecard's pooled `n` ever again falls below its attempted `n` with nothing accounting
for the difference.

Two further things a reader is entitled to know before quoting the count. `AST01` and `AST08` clear
the confidence bound by 0.4 and 0.7 points respectively, and this repository's own doctrine says a
threshold cleared by less than the instrument's run-to-run movement is not cleared. And `AST09` went
BLOCKED → SHIP between runs 4 and 5 without its `SKILL.md` changing by a byte, on a pooled mean that
rose 2.9 points: ADR-0006 stopped the gate depending on how much the panel agreed, but nothing stops
the mean itself moving between runs.

---
## What this does not do

The single hardest limit: **a detector reads one skill package at one moment in time.**
Whole classes of AST risk are not properties of a snapshot, and this repo refuses to
pretend otherwise rather than shipping a proxy that scores well.

- **No runtime or multi-session observation.** AST01's Cognitive Degradation chain, AST07's
  drift, and AST09's governance failures are defined by accumulation across invocations.
  A package that will degrade its host and one that will not are byte-identical at install
  time. These are tiered `out-of-artifact` and published with the telemetry that *would*
  decide them.
- **No world knowledge.** Deciding that `gogle-workspace` is a deliberate near-miss of a
  legitimate name needs an external popularity and legitimate-name corpus the package does
  not carry. Typosquatting is `agent-judgable`, not static.
- **No organisational context.** Whether a skill is approved, inventoried, owned, or
  deprovisioned lives in your governance system, not in the artifact. AST09 is entirely
  out-of-artifact for that reason.
- **No sandbox, no enforcement, no blocking.** These skills report; they do not quarantine
  a package, revoke a signature, or stop an install. A verified signature answers *who
  published this*, never *is this safe*, and this repo will not conflate the two.
- **Every published F1 is a floor, not a rate.** The per-category numbers in the table above
  are measured over that category's own hand-labeled corpus at the locked gate-4 size —
  `max(6, 2 x detectable_scenarios)` — by authors who also wrote the checks. They establish
  that each check separates its vulnerable case from its clean one; they do not estimate
  performance on skills nobody here wrote. Categories reading `declared-and-uncovered`
  publish no number at any corpus size. A fourth state the tooling still understands,
  `pending-detector` — a labeled corpus exists that no detector consumes — is **unused
  today**: every labeled corpus in the repository is read by a detector, and
  `tests/test_coverage_matrix.py::test_every_authored_category_has_a_wired_corpus_or_is_declared_unwired`
  fails any category that publishes `pending-detector` while its corpus is wired. The coverage matrices name every gap.
- **The judge scores are a panel's reading, not a measurement of quality.** Five runs are
  recorded and all eleven skills clear the ship rule on the fifth, but a pooled mean is
  a statement about the rubric *as read by these six judges*: they span 11.4 points on the
  same eleven files, the corpus and the rubric prompt are both self-authored, and the most
  generous judge is `COARSE` and still pooled. See
  [What 11 of 11 is, and what it is not](#what-11-of-11-is-and-what-it-is-not) above.
  [`docs/skill-judge-dashboard.md`](skill-judge-dashboard.md) publishes the whole panel,
  the per-judge bias, the judge-quality diagnostics, and the providers that are unavailable
  from this environment and why. Do not quote a number from it next to a single-judge score:
  [ADR-0005](adr/0005-judge-panel-calibration-and-the-lower-bound.md) explains why the
  two have different units.
- **One declared platform.** Every `skill.usf.yaml` declares `platforms: [claude]`. Adding
  a platform is a re-validation event, not an edit — AST10's whole premise is that security
  properties are lost in translation between runtimes.
- **A signature is not a safety claim.** Every manifest is now signed and anchored to
  `did:web:jhkchan.github.io`, and `python3 scripts/sign_usf.py verify --identity
  did:web:jhkchan.github.io` checks all eleven against the key that domain publishes. That
  answers *who published this* and nothing else. It is not a review, not a scan
  (`scan_status.result` still reads `unscanned`, declared rather than omitted), and not a
  statement that the skills are safe to run. The anchor is worth exactly as much as
  control of `jhkchan.github.io` and its TLS: whoever can serve that path can publish a
  key of their own and every signature made with it will verify. Reading a green
  verification as an endorsement is the AST01 mistake these skills exist to catch, and
  [`docs/signing.md`](signing.md) states the ceiling in full.

---

---

[< Back to the README](../README.md)
