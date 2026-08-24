# Scorecards

One JSON file per skill, written by a judge run and consumed by
`eval/generate_dashboard.py`. Empty until a judged run happens — see
[`../../docs/skill-judge-dashboard.md`](../../docs/skill-judge-dashboard.md) for the
file shape, the rubric, and the ship rule.

Only `*.json` files in this directory are read as scorecards; this README is ignored.

## The scorecards here predate the 2026-08-23 prompt rebuild

**Do not compare a new run against these files.** Every judgment in this directory (and in
`eval/scorecards-run1/`) was produced by a judge prompt that sent the eight dimension *names*
and their maxima and none of the rubric's scoring bands, and that forbade any prose — which
is why not one of the 198 recorded judgments carries a reason for any score.
`scripts/judge_harness.py` now quotes the pinned rubric's band tables verbatim and requires a
one-sentence justification per dimension, so a fresh run measures with a different instrument.

These files are kept exactly as written. They are the evidence of what the unanchored judge
produced, and a future run is a **new baseline** — not run 3 of this series. See the callout
at the top of [`../../docs/skill-judge-dashboard.md`](../../docs/skill-judge-dashboard.md).
