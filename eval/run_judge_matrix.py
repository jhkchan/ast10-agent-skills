#!/usr/bin/env python3
"""Run the multi-model skill-judge matrix over every shipped skill.

Judges each skills/<NAME>/SKILL.md across every AVAILABLE provider adapter, pools
the per-round totals with the vendored ship_floor rule (mean >= 108 AND
mean - 1.0 * stdev/sqrt(n) >= 108 AND per-dimension floors), and writes one
scorecard per skill to eval/scorecards/<name>.json.

The second clause read `mean - stdev >= 105` through run 4 and was retired on
2026-08-24 by docs/adr/0006-confidence-bound-on-the-pooled-mean.md -- the gate's
first and only change, recorded before the run it judges. Run 5 is the first corpus
judged under it and the first to carry the two statistics that clause publishes,
`sem` and `ci_lower`; the four archived runs do not have them.
ARCHIVE eval/scorecards/ before overwriting it (CONTRIBUTING.md). Every archived
run stays gated by the rule that scored it and must not be re-gated under a later
one.

Providers that are unavailable are recorded in config/audit.yml with a reason by
adapters.base.build_roster -- never silently dropped (spec.md S-004). A provider
that ANSWERS and is refused is recorded the same way, by scripts.judge_harness.run_judge,
and the entries are copied into the scorecard as `attempted`, `pooled`, `refusals` and
`refusals_by_provider` so one scorecard shows its own gaps. Run 5 predates that and lost
ten judgments with no record; eval/run5-refusals.md reconstructs what the bytes allow and
scripts/refusal_ledger.py fails the build if it ever happens again.

Usage:
    python3 eval/run_judge_matrix.py [--rounds N] [--skills AST01,AST04] [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import time

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from adapters.anthropic_compatible import AnthropicCompatibleAdapter  # noqa: E402
from adapters.base import build_roster  # noqa: E402
from adapters.bedrock import BedrockAdapter  # noqa: E402
from adapters.claude_cli import ClaudeCliAdapter  # noqa: E402
from scripts import ship_floor  # noqa: E402
from scripts.judge_harness import run_judge  # noqa: E402

SCORECARDS = REPO / "eval" / "scorecards"


def _zai_key() -> str | None:
    """Read ZAI_API_KEY from the env, else from the zai profile the shell fn sources."""
    if os.environ.get("ZAI_API_KEY"):
        return os.environ["ZAI_API_KEY"]
    prof = pathlib.Path.home() / ".claude" / "profiles" / "zai.env"
    if not prof.exists():
        return None
    for line in prof.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("export ZAI_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def _count_by_provider(refusals: list[dict]) -> dict[str, int]:
    """{provider: refused count} for one skill's scorecard.

    A one-line answer to "which judges are missing from this number", which
    is the first question the pooled mean invites and the one run 5 could not
    answer from its own files.
    """
    counts: dict[str, int] = {}
    for entry in refusals:
        provider = str(entry.get("provider", "unknown"))
        counts[provider] = counts.get(provider, 0) + 1
    return counts


def build_adapters() -> list:
    """The roster verified live 2026-08-21. Unavailable ones are declared, not dropped."""
    adapters = [
        BedrockAdapter(model="gpt-oss-120b"),
        BedrockAdapter(model="qwen3-235b"),
        BedrockAdapter(model="deepseek-v3.2"),
        BedrockAdapter(model="nova-pro"),
        ClaudeCliAdapter(),
    ]
    key = _zai_key()
    if key:
        adapters.append(AnthropicCompatibleAdapter(model="glm-5.2", api_key=key))
    return adapters


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=3, help="pooled judgment rounds per skill")
    ap.add_argument("--skills", default="", help="comma-separated subset, e.g. AST01,AST04")
    ap.add_argument("--dry-run", action="store_true", help="build the roster and exit")
    ap.add_argument(
        "--audit-path",
        default=None,
        help=(
            "where refusals are appended (default: config/audit.yml). There is no value that means "
            "'do not record'; tests point this at a scratch file."
        ),
    )
    args = ap.parse_args(argv)

    adapters = build_adapters()
    roster = build_roster(adapters)
    available = list(getattr(roster, "available", adapters))
    unavailable = list(getattr(roster, "unavailable", []))

    print(f"roster: {len(available)} available, {len(unavailable)} unavailable")
    for a in available:
        print(f"  + {getattr(a, 'name', a)}")
    for u in unavailable:
        print(f"  - {getattr(u, 'provider', u)}: {getattr(u, 'reason', '')}")
    if args.dry_run:
        return 0
    if not available:
        print("FATAL: no available judge providers", file=sys.stderr)
        return 2

    wanted = {s.strip() for s in args.skills.split(",") if s.strip()}
    skill_dirs = sorted(d for d in (REPO / "skills").iterdir() if (d / "SKILL.md").is_file())
    if wanted:
        skill_dirs = [d for d in skill_dirs if d.name in wanted]

    SCORECARDS.mkdir(parents=True, exist_ok=True)
    summary = []
    for d in skill_dirs:
        rounds = []
        for r in range(args.rounds):
            out = SCORECARDS / f".{d.name}.round{r}.json"
            t0 = time.time()
            res = run_judge(
                d / "SKILL.md",
                available,
                output_path=out,
                timeout=180.0,
                skill=d.name,
                round_index=r + 1,
                audit_path=args.audit_path,
            )
            rounds.append(res)
            n = len(res.get("judgments") or [])
            refused = len(res.get("audit_trail") or [])
            note = f", {refused} refused" if refused else ""
            print(
                f"  {d.name} round {r + 1}/{args.rounds}: {res['status']} "
                f"({n} judgments{note}, {time.time() - t0:.0f}s)"
            )

        judgments = [j for r in rounds for j in (r.get("judgments") or [])]
        # The per-round scores.json files are deleted at the end of this loop, so
        # anything a refusal knows has to be lifted out of them HERE. Run 5 did
        # not do this and lost ten refusals with the temp files
        # (eval/run5-refusals.md); config/audit.yml now holds the same entries
        # independently, and this block is the copy a reader of one scorecard
        # can see without leaving the file.
        refusals = [dict(entry) for r in rounds for entry in (r.get("audit_trail") or [])]
        attempted = args.rounds * len(available)
        totals, dimsets = [], []
        for j in judgments:
            sc = j.get("scores") or {}
            tot = sc.get("total")
            if tot is None and sc:
                tot = sum(v for k, v in sc.items() if k.startswith("D"))
            if tot:
                totals.append(float(tot))
            dims = {k: v for k, v in sc.items() if k.startswith("D")}
            if len(dims) == 8:
                dimsets.append(dims)

        agg = None
        verdict, reason = "BLOCKED", "no judgments"
        if totals:
            try:
                agg = ship_floor.pooled_stats(totals)
                # The gate recomputes every published number from `judgments`, so the
                # raw totals must travel with the stats they were derived from.
                agg["judgments"] = totals
                agg["method"] = ship_floor.AGG_METHOD
                agg["rubric_sha"] = ship_floor.RUBRIC_SHA
                agg["rubric_content_sha256"] = ship_floor.RUBRIC_CONTENT_SHA256
                agg["dim_n"] = len(dimsets)
                if dimsets:
                    agg["dim_means"] = ship_floor.dim_means_of(dimsets)
                verdict, reason = ship_floor.aggregate_verdict(d.name, agg)
            except Exception as exc:  # noqa: BLE001
                verdict, reason = "BLOCKED", f"{type(exc).__name__}: {exc}"

        card = {
            "skill": d.name,
            "rounds": args.rounds,
            "providers": [getattr(a, "name", str(a)) for a in available],
            "providers_unavailable": [
                {"provider": getattr(u, "provider", str(u)), "reason": getattr(u, "reason", "")} for u in unavailable
            ],
            # attempted - pooled == len(refusals), asserted by
            # tests/test_refusal_ledger.py. A scorecard that cannot say what
            # happened to its own missing judgments does not ship.
            "attempted": attempted,
            "pooled": len(judgments),
            "refusals": refusals,
            "refusals_by_provider": _count_by_provider(refusals),
            "judgments": judgments,
            "aggregate": agg,
            "verdict": verdict,
            "verdict_reason": reason,
        }
        (SCORECARDS / f"{d.name}.json").write_text(json.dumps(card, indent=2), encoding="utf-8")
        for r in range(args.rounds):
            (SCORECARDS / f".{d.name}.round{r}.json").unlink(missing_ok=True)

        mean = (agg or {}).get("mean")
        if len(judgments) != attempted:
            gap = attempted - len(judgments)
            print(f"  {d.name}: {gap} of {attempted} attempted judgments refused — {_count_by_provider(refusals)}")
        print(f"{d.name}: {verdict} — {reason} (mean={mean}, n={len(totals)})")
        summary.append((d.name, verdict, mean, len(totals)))

    print("\n=== SUMMARY ===")
    for name, verdict, mean, n in summary:
        print(f"  {name:<10} {verdict:<8} mean={mean} n={n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
