# Vendored: softaworks/agent-toolkit — skills/skill-judge

| | |
| --- | --- |
| Upstream | `softaworks/agent-toolkit`, path `skills/skill-judge/SKILL.md` |
| Upstream commit | `3027f20f3181758385a1bb8c022d4041dfb4de84` (2026-03-06) — the value pinned as `RUBRIC_SHA` in `scripts/ship_floor.py` |
| Content sha256 | `737ef3628f0e11353114c3bd05a1c9d0c448dbfec1ae85db839253cbe93198b6` — pinned as `RUBRIC_CONTENT_SHA256` |
| Git blob id | `6d183975ba7369622a635184f1f8bfbaa9075bc0` |
| Licence | MIT, © 2026 Leonardo Flores — see `LICENSE` beside this file |

Vendored so the pinned rubric is **verifiable from inside this repository**. `RUBRIC_SHA`
is an upstream *commit* id and cannot be recomputed locally; `RUBRIC_CONTENT_SHA256` can,
and `tests/test_rubric_pin.py` recomputes it from this file on every run. A judged score
is only comparable to another judged score if both were graded against the same rubric
bytes, so an unverifiable pin is not a pin at all.

The rubric defines the 8 dimensions / 120 points this repo's scorecards use:
D1 Knowledge Delta 20 · D2 Mindset + Appropriate Procedures 15 · D3 Anti-Pattern Quality 15 ·
D4 Specification Compliance 15 · D5 Progressive Disclosure 15 · D6 Freedom Calibration 15 ·
D7 Pattern Recognition 10 · D8 Practical Usability 15.
