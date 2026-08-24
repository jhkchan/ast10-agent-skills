#!/usr/bin/env python3
"""scripts/refusal_ledger.py — every judgment a scorecard does not contain must be accounted for.

A pooled mean is a claim about the judgments that entered the pool. It is only
readable if the judgments that did NOT enter are also on the record, because
"188 of 198" is a different measurement depending on which ten went missing and
from which judges. Run 5 of this repo's judge matrix refused 10 of 198 attempted
judgments, recorded none of them, and deleted the per-round files that held the
responses. Two of the ten were AST01's, from the two judges that scored AST01
lowest — which is exactly the case where the gap can move a verdict. That is the
defect this module polices.

Three questions, answered from the bytes on disk:

**1. How many judgments did a scorecard lose?** `attempted_of` / `pooled_of`.
A scorecard written by the current harness states both. One written before
2026-08-24 states neither, and the attempt count is reconstructed as
``rounds x len(providers)`` — the loop `eval/run_judge_matrix.py` actually runs.

**2. WHICH ones?** `missing_attempts`. Every round appends its judgments in
roster order, and rounds are concatenated in order, so a provider index that
does not increase marks a round boundary. Segmenting on that recovers each
round's roster, and each round's absentees are the refusals. The reconstruction
is checked, not assumed: `rounds_from_order` returns None unless it recovers
exactly `card["rounds"]` segments, and a caller that gets None must say the
round is underivable rather than guess it.

**3. Is that loss ON THE RECORD?** `problems`. A scorecard written by the
current harness carries its own `refusals` block and must account for its gap
there, entry by entry, each naming provider, round, status and reason. A
scorecard written before the harness recorded anything cannot — those bytes are
frozen — so its gap must instead be covered row-for-row by the recovery ledger
`eval/run5-refusals.md`. The escape hatch is keyed on the ABSENCE of the
`attempted` field rather than on a directory allow-list, which is what stops the
next run from using it: the moment the fixed harness writes a scorecard, the
in-file account becomes mandatory for that file.

Run as a command it is a check, not a description:

    python3 scripts/refusal_ledger.py           # exit 1 if any gap is unaccounted
    python3 scripts/refusal_ledger.py --report  # the derivation, as Markdown tables
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import pathlib
import re
import sys
from collections import Counter
from collections.abc import Iterable, Sequence

ROOT = pathlib.Path(__file__).resolve().parent.parent
EVAL_DIR = ROOT / "eval"
LEDGER_PATH = EVAL_DIR / "run5-refusals.md"

#: Statuses a recorded refusal may carry. Mirrors
#: ``adapters.base.RECORDABLE_STATUSES`` and is duplicated here only as a
#: fallback for a checkout where the adapters package will not import; the
#: import below is the authority.
_FALLBACK_STATUSES = frozenset({"failed", "malformed"})
try:  # pragma: no cover - exercised implicitly by every run in this repo
    sys.path.insert(0, str(ROOT))
    from adapters.base import RECORDABLE_STATUSES
except Exception:  # pragma: no cover - defensive only
    RECORDABLE_STATUSES = _FALLBACK_STATUSES


@dataclasses.dataclass(frozen=True, order=True)
class MissingAttempt:
    """One (skill, provider, round) that was attempted and did not pool.

    `round_index` is 1-based, or None when the ordering could not be segmented
    into the recorded number of rounds — an underivable round is reported as
    unknown, never as a guess.
    """

    skill: str
    provider: str
    round_index: int | None

    def key(self) -> tuple[str, str, int | None]:
        return (self.skill, self.provider, self.round_index)


def scorecard_dirs(eval_dir: pathlib.Path = EVAL_DIR) -> list[pathlib.Path]:
    """Every `eval/scorecards*` directory, live corpus first."""
    return sorted(
        (d for d in eval_dir.iterdir() if d.is_dir() and d.name.startswith("scorecards")), key=lambda d: d.name
    )


def load_cards(directory: pathlib.Path) -> list[tuple[pathlib.Path, dict]]:
    """Scorecards in one directory, in filename order. Non-scorecard JSON is skipped."""
    cards = []
    for path in sorted(directory.glob("*.json")):
        try:
            card = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if isinstance(card, dict) and "judgments" in card and "providers" in card:
            cards.append((path, card))
    return cards


def pooled_of(card: dict) -> int:
    """How many judgments actually entered the pool."""
    return len(card.get("judgments") or [])


def attempted_of(card: dict) -> int:
    """How many judgments the run tried to collect.

    Stated by the current harness; reconstructed as ``rounds x providers`` for
    the frozen pre-2026-08-24 corpora, which is the loop that produced them.
    """
    if isinstance(card.get("attempted"), int):
        return int(card["attempted"])
    return int(card.get("rounds") or 0) * len(card.get("providers") or [])


def records_its_own_refusals(card: dict) -> bool:
    """True for a scorecard written by the harness that records refusals in-file."""
    return isinstance(card.get("attempted"), int) and isinstance(card.get("refusals"), list)


def rounds_from_order(card: dict) -> list[list[str]] | None:
    """Segment the judgment list back into rounds, or None if that is not safe.

    `run_judge` calls the adapters in roster order and `run_judge_matrix`
    concatenates the rounds in order, so within a round the provider's index in
    `card["providers"]` strictly increases and a non-increase is a round
    boundary. Two ways this can fail to be trustworthy, both of which return
    None rather than a plausible-looking answer: a provider that is not on the
    roster at all, and a segment count that does not match `card["rounds"]`
    (an entirely empty round leaves no boundary to see).
    """
    providers = list(card.get("providers") or [])
    order = {name: i for i, name in enumerate(providers)}
    expected_rounds = int(card.get("rounds") or 0)
    if not providers or expected_rounds <= 0:
        return None

    segments: list[list[str]] = [[]]
    previous = -1
    for judgment in card.get("judgments") or []:
        name = judgment.get("provider")
        if name not in order:
            return None
        index = order[name]
        if index <= previous:
            segments.append([])
        segments[-1].append(name)
        previous = index

    if segments == [[]]:
        segments = []
    return segments if len(segments) == expected_rounds else None


def missing_attempts(card: dict) -> list[MissingAttempt]:
    """The attempts this scorecard lost, one entry each, round-attributed where derivable."""
    skill = str(card.get("skill", "?"))
    providers = list(card.get("providers") or [])
    gap = attempted_of(card) - pooled_of(card)
    if gap <= 0:
        return []

    segments = rounds_from_order(card)
    if segments is None:
        # Round unknown: report the per-provider shortfall without inventing a
        # round for it. Ordering could not be segmented, so any round number
        # here would be fiction.
        present = Counter(j.get("provider") for j in card.get("judgments") or [])
        rounds = int(card.get("rounds") or 0)
        out = []
        for provider in providers:
            for _ in range(max(0, rounds - present.get(provider, 0))):
                out.append(MissingAttempt(skill, provider, None))
        return out

    out = []
    for number, segment in enumerate(segments, start=1):
        for provider in providers:
            if provider not in segment:
                out.append(MissingAttempt(skill, provider, number))
    return sorted(out)


def in_file_refusals(card: dict) -> list[MissingAttempt]:
    """The refusals a scorecard records about itself."""
    out = []
    for entry in card.get("refusals") or []:
        out.append(
            MissingAttempt(
                skill=str(entry.get("skill", card.get("skill", "?"))),
                provider=str(entry.get("provider", "?")),
                round_index=entry.get("round") if isinstance(entry.get("round"), int) else None,
            )
        )
    return sorted(out)


def refusal_entry_problems(card: dict, where: str) -> list[str]:
    """A recorded refusal that cannot be acted on is not a record.

    Each entry must name the provider, the skill, the round, a status the audit
    trail defines, a non-empty reason, and — whenever the provider answered at
    all — an excerpt of what it said. `response_excerpt` is required only when
    `response_chars` says there was a response to excerpt, because a provider
    that timed out has no bytes to keep.
    """
    problems = []
    for index, entry in enumerate(card.get("refusals") or []):
        tag = f"{where}: refusals[{index}]"
        if not str(entry.get("provider", "")).strip():
            problems.append(f"{tag} names no provider")
        if not str(entry.get("skill", "")).strip():
            problems.append(f"{tag} names no skill")
        if not isinstance(entry.get("round"), int):
            problems.append(f"{tag} names no round")
        status = entry.get("status")
        if status not in RECORDABLE_STATUSES:
            problems.append(f"{tag} status {status!r} is not one of {sorted(RECORDABLE_STATUSES)}")
        if not str(entry.get("reason", "")).strip():
            problems.append(f"{tag} carries no reason — a refusal with no reason cannot be diagnosed")
        if entry.get("response_chars") and not str(entry.get("response_excerpt", "")).strip():
            problems.append(f"{tag} recorded a {entry['response_chars']}-character response but kept none of it")
    return problems


# --- the recovery ledger ----------------------------------------------------

_TABLE_ROW = re.compile(r"^\s*\|(.+)\|\s*$")


def _cells(line: str) -> list[str]:
    match = _TABLE_ROW.match(line)
    if not match:
        return []
    return [c.strip() for c in match.group(1).split("|")]


def _is_divider(cells: Sequence[str]) -> bool:
    return bool(cells) and all(set(c) <= set("-: ") and c for c in cells)


def _tables(text: str) -> list[list[list[str]]]:
    """Every Markdown pipe-table in `text`, as a list of cell rows (header first)."""
    tables: list[list[list[str]]] = []
    current: list[list[str]] = []
    for line in text.splitlines():
        cells = _cells(line)
        if cells:
            if not _is_divider(cells):
                current.append(cells)
        elif current:
            tables.append(current)
            current = []
    if current:
        tables.append(current)
    return tables


def _tables_with(text: str, *headers: str) -> list[list[str]]:
    """Body rows of EVERY table whose header starts with `headers`.

    Every, not the first: the ledger carries one detail table per corpus, and a
    reader who adds a fourth must not silently stop being checked.
    """
    wanted = [h.casefold() for h in headers]
    rows: list[list[str]] = []
    for table in _tables(text):
        head = [c.casefold() for c in table[0]]
        if head[: len(wanted)] == wanted:
            rows.extend(table[1:])
    return rows


def ledger_rows(text: str) -> list[MissingAttempt]:
    """The per-attempt rows of the recovery ledger: skill, provider, round."""
    rows = []
    for cells in _tables_with(text, "skill", "provider", "round"):
        if len(cells) < 3:
            continue
        raw_round = cells[2].strip()
        rows.append(
            MissingAttempt(
                skill=cells[0].strip(),
                provider=cells[1].strip(),
                round_index=int(raw_round) if raw_round.isdigit() else None,
            )
        )
    return sorted(rows)


def ledger_coverage(text: str) -> dict[str, tuple[int, int, int]]:
    """The ledger's per-corpus totals: {corpus: (attempted, pooled, refused)}."""
    out: dict[str, tuple[int, int, int]] = {}
    for cells in _tables_with(text, "corpus", "attempted", "pooled", "refused"):
        if len(cells) < 4:
            continue
        name = cells[0].strip().strip("`").rstrip("/")
        try:
            out[name] = (int(cells[1]), int(cells[2]), int(cells[3]))
        except ValueError:
            continue
    return out


def _read_ledger(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


# --- the check ---------------------------------------------------------------


def problems(
    dirs: Iterable[pathlib.Path] | None = None,
    ledger_path: pathlib.Path = LEDGER_PATH,
    eval_dir: pathlib.Path = EVAL_DIR,
) -> list[str]:
    """Every unaccounted-for discard in this repository, as human-readable lines.

    Empty means: for every scorecard, `attempted - pooled` judgments are named
    somewhere durable — in the scorecard's own `refusals` block, or, for the
    frozen pre-recording corpora, in the recovery ledger.
    """
    dirs = list(dirs) if dirs is not None else scorecard_dirs(eval_dir)
    ledger_text = _read_ledger(ledger_path)
    rows = ledger_rows(ledger_text)
    coverage = ledger_coverage(ledger_text)
    found: list[str] = []

    for directory in dirs:
        corpus = f"eval/{directory.name}"
        corpus_attempted = corpus_pooled = 0
        needs_ledger = False

        for path, card in load_cards(directory):
            where = f"{corpus}/{path.name}"
            attempted, pooled = attempted_of(card), pooled_of(card)
            corpus_attempted += attempted
            corpus_pooled += pooled
            gap = attempted - pooled

            if attempted == 0:
                found.append(f"{where}: cannot tell how many judgments were attempted (no rounds/providers)")
                continue
            if gap < 0:
                found.append(f"{where}: pooled {pooled} judgments but only {attempted} were attempted")
                continue

            if isinstance(card.get("attempted"), int) and not isinstance(card.get("refusals"), list):
                # Half-modern: it states how many attempts it made and then has
                # no field to say what became of the ones it lost. Never allowed
                # to fall through to the ledger — the ledger exists for bytes
                # written before the field did.
                if gap > 0:
                    found.append(
                        f"{where}: states {attempted} attempted and pooled {pooled}, but carries no `refusals` "
                        "block to account for the difference"
                    )
                continue

            if records_its_own_refusals(card):
                found.extend(refusal_entry_problems(card, where))
                recorded = in_file_refusals(card)
                if len(recorded) != gap:
                    found.append(
                        f"{where}: {gap} of {attempted} judgments did not pool but the scorecard records "
                        f"{len(recorded)} refusal(s). Every discard must be recorded — see "
                        f"scripts/judge_harness.py::run_judge."
                    )
                derived = missing_attempts(card)
                if derived and Counter(r.key() for r in recorded) != Counter(d.key() for d in derived):
                    found.append(
                        f"{where}: the recorded refusals {sorted(r.key() for r in recorded)} do not match the "
                        f"attempts missing from the judgment list {sorted(d.key() for d in derived)}"
                    )
                continue

            # Frozen bytes, written before the harness recorded anything.
            if gap == 0:
                continue
            needs_ledger = True
            for attempt in missing_attempts(card):
                if attempt not in rows:
                    found.append(
                        f"{where}: {attempt.provider} round {attempt.round_index} was attempted, did not pool, "
                        f"and is recorded neither in the scorecard nor in {ledger_path.name}"
                    )

        if needs_ledger:
            stated = coverage.get(corpus)
            refused = corpus_attempted - corpus_pooled
            if stated is None:
                found.append(f"{corpus}: lost {refused} judgments and is not listed in {ledger_path.name}")
            elif stated != (corpus_attempted, corpus_pooled, refused):
                found.append(
                    f"{corpus}: {ledger_path.name} states {stated} attempted/pooled/refused, "
                    f"the files say {(corpus_attempted, corpus_pooled, refused)}"
                )

    # A ledger row with no missing attempt behind it is drift in the other
    # direction: a record of something that did not happen.
    if rows:
        derived_all = {
            attempt.key()
            for directory in dirs
            for _path, card in load_cards(directory)
            for attempt in missing_attempts(card)
        }
        for row in rows:
            if row.key() not in derived_all:
                found.append(
                    f"{ledger_path.name}: row {row.key()} names an attempt that is not missing from any scorecard"
                )

    return found


# --- the report --------------------------------------------------------------


def report(dirs: Iterable[pathlib.Path] | None = None, eval_dir: pathlib.Path = EVAL_DIR) -> str:
    """The derivation as Markdown: per-corpus totals, then every missing attempt."""
    dirs = list(dirs) if dirs is not None else scorecard_dirs(eval_dir)
    lines = ["| Corpus | Attempted | Pooled | Refused |", "| --- | ---: | ---: | ---: |"]
    detail: list[str] = []
    for directory in dirs:
        corpus = f"eval/{directory.name}"
        attempted = pooled = 0
        rows: list[MissingAttempt] = []
        for _path, card in load_cards(directory):
            attempted += attempted_of(card)
            pooled += pooled_of(card)
            rows.extend(missing_attempts(card))
        lines.append(f"| `{corpus}` | {attempted} | {pooled} | {attempted - pooled} |")
        if rows:
            detail.append(f"\n### {corpus}\n")
            detail.append("| Skill | Provider | Round |")
            detail.append("| --- | --- | ---: |")
            for row in rows:
                detail.append(f"| {row.skill} | {row.provider} | {row.round_index if row.round_index else '?'} |")
    return "\n".join(lines + detail) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--report", action="store_true", help="print the derivation instead of checking it")
    args = parser.parse_args(argv)

    if args.report:
        print(report(), end="")
        return 0

    found = problems()
    if found:
        print(f"FAIL: {len(found)} unaccounted-for discard(s):")
        for line in found:
            print(f"  - {line}")
        return 1
    total_attempted = total_pooled = 0
    for directory in scorecard_dirs():
        for _path, card in load_cards(directory):
            total_attempted += attempted_of(card)
            total_pooled += pooled_of(card)
    print(
        f"OK: {total_attempted} attempted judgments across {len(scorecard_dirs())} corpora, "
        f"{total_pooled} pooled, {total_attempted - total_pooled} refused and every one of them on the record."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
