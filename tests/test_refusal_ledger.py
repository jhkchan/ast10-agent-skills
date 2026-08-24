"""No scorecard may ship a gap it cannot account for.

`tests/scripts/test_refusal_recording.py` asserts that a refusal is written down
when it happens. This file asserts the property that survives a run: for every
scorecard in this repository, `attempted - pooled` judgments are named somewhere
durable. A scorecard written by the current harness must name them in its own
`refusals` block; the frozen corpora that predate the recording path must have
them in the recovery ledger `eval/run5-refusals.md`, which
`scripts/refusal_ledger.py` re-derives from the judgment ordering rather than
trusting.

The exemption for the frozen corpora is keyed on the ABSENCE of the `attempted`
field, not on a directory name. That is deliberate and is tested below: the next
judge run writes `attempted`, so it cannot inherit the exemption by overwriting
`eval/scorecards/`.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import refusal_ledger as ledger

REPO = Path(__file__).resolve().parents[1]
LEDGER_MD = REPO / "eval" / "run5-refusals.md"

#: Run 5, the published corpus: 11 skills x 3 rounds x 6 providers.
RUN5_ATTEMPTED = 198
RUN5_POOLED = 188


def _judgment(provider: str) -> dict:
    return {"provider": provider, "scores": {"D1": 17}, "total": 110.0}


def _card(skill: str, providers: list[str], rounds_of: list[list[str]], **extra) -> dict:
    """A scorecard shaped like the harness writes one: rounds concatenated in
    roster order."""
    card = {
        "skill": skill,
        "rounds": len(rounds_of),
        "providers": providers,
        "judgments": [_judgment(p) for segment in rounds_of for p in providers if p in segment],
    }
    card.update(extra)
    return card


# ---------------------------------------------------------------------------
# 1. The reconstruction
# ---------------------------------------------------------------------------


def test_missing_attempts_names_the_provider_and_the_round():
    card = _card("AST01", ["a", "b", "c"], [["a", "b", "c"], ["a", "c"], ["a", "b", "c"]])
    assert [m.key() for m in ledger.missing_attempts(card)] == [("AST01", "b", 2)]


def test_missing_attempts_is_empty_for_a_complete_scorecard():
    card = _card("AST02", ["a", "b"], [["a", "b"], ["a", "b"]])
    assert ledger.missing_attempts(card) == []


def test_two_providers_lost_in_the_same_round_are_two_entries():
    card = _card("AST06", ["a", "b", "c"], [["a", "b", "c"], ["a", "b", "c"], ["a"]])
    assert [m.key() for m in ledger.missing_attempts(card)] == [("AST06", "b", 3), ("AST06", "c", 3)]


def test_an_unsegmentable_scorecard_reports_the_round_as_unknown():
    """An entirely empty round leaves no boundary in the ordering. The round is
    then unknowable, and an unknowable round is reported as None rather than
    guessed — the provider shortfall is still exact."""
    card = _card("AST04", ["a", "b"], [["a", "b"], [], ["a", "b"]])
    assert ledger.rounds_from_order(card) is None
    assert [m.key() for m in ledger.missing_attempts(card)] == [("AST04", "a", None), ("AST04", "b", None)]


def test_an_off_roster_provider_makes_the_segmentation_refuse_rather_than_guess():
    card = _card("AST05", ["a", "b"], [["a", "b"], ["a", "b"]])
    card["judgments"].append(_judgment("someone-not-on-the-roster"))
    assert ledger.rounds_from_order(card) is None


def test_attempted_is_read_when_stated_and_derived_when_not():
    stated = _card("AST01", ["a", "b"], [["a", "b"]], attempted=99)
    assert ledger.attempted_of(stated) == 99
    derived = _card("AST01", ["a", "b"], [["a", "b"], ["a", "b"], ["a", "b"]])
    assert ledger.attempted_of(derived) == 6


# ---------------------------------------------------------------------------
# 2. The guard
# ---------------------------------------------------------------------------


def _write(directory: Path, card: dict) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{card['skill']}.json").write_text(json.dumps(card), encoding="utf-8")


def test_a_modern_scorecard_that_loses_a_judgment_without_recording_it_fails(tmp_path):
    """The regression guard, stated as its own test: a gap with no record does
    not pass, whatever the ledger says."""
    corpus = tmp_path / "scorecards"
    _write(
        corpus,
        _card("AST01", ["a", "b"], [["a", "b"], ["a"]], attempted=4, refusals=[]),
    )

    found = ledger.problems([corpus], ledger_path=tmp_path / "absent.md")

    assert any("did not pool but the scorecard records 0 refusal" in line for line in found)


def test_a_modern_scorecard_that_records_its_refusal_passes(tmp_path):
    corpus = tmp_path / "scorecards"
    _write(
        corpus,
        _card(
            "AST01",
            ["a", "b"],
            [["a", "b"], ["a"]],
            attempted=4,
            refusals=[
                {
                    "provider": "b",
                    "skill": "AST01",
                    "round": 2,
                    "status": "malformed",
                    "reason": "D3: object has no 'why' key",
                    "response_excerpt": '{"D3": 14}',
                    "response_chars": 10,
                }
            ],
        ),
    )

    assert ledger.problems([corpus], ledger_path=tmp_path / "absent.md") == []


def test_a_recorded_refusal_that_names_the_wrong_round_fails(tmp_path):
    """The record has to match the hole in the judgment list, not merely exist."""
    corpus = tmp_path / "scorecards"
    _write(
        corpus,
        _card(
            "AST01",
            ["a", "b"],
            [["a", "b"], ["a"]],
            attempted=4,
            refusals=[{"provider": "b", "skill": "AST01", "round": 1, "status": "malformed", "reason": "no why key"}],
        ),
    )

    found = ledger.problems([corpus], ledger_path=tmp_path / "absent.md")
    assert any("do not match the attempts missing" in line for line in found)


@pytest.mark.parametrize(
    "entry,expected",
    [
        ({"provider": "", "skill": "AST01", "round": 2, "status": "malformed", "reason": "r"}, "names no provider"),
        ({"provider": "b", "skill": "", "round": 2, "status": "malformed", "reason": "r"}, "names no skill"),
        ({"provider": "b", "skill": "AST01", "status": "malformed", "reason": "r"}, "names no round"),
        ({"provider": "b", "skill": "AST01", "round": 2, "status": "skipped", "reason": "r"}, "is not one of"),
        ({"provider": "b", "skill": "AST01", "round": 2, "status": "malformed", "reason": " "}, "carries no reason"),
        (
            {
                "provider": "b",
                "skill": "AST01",
                "round": 2,
                "status": "malformed",
                "reason": "r",
                "response_chars": 400,
            },
            "kept none of it",
        ),
    ],
)
def test_a_refusal_entry_that_cannot_be_acted_on_is_not_a_record(tmp_path, entry, expected):
    corpus = tmp_path / "scorecards"
    _write(corpus, _card("AST01", ["a", "b"], [["a", "b"], ["a"]], attempted=4, refusals=[entry]))

    found = ledger.problems([corpus], ledger_path=tmp_path / "absent.md")
    assert any(expected in line for line in found), found


def test_a_frozen_scorecard_may_use_the_ledger_but_a_modern_one_may_not(tmp_path):
    """The exemption is keyed on the missing `attempted` field, so writing a
    scorecard with the fixed harness closes it for that file."""
    corpus = tmp_path / "scorecards"
    frozen = _card("AST01", ["a", "b"], [["a", "b"], ["a"]])
    _write(corpus, frozen)
    recovery = tmp_path / "run5-refusals.md"
    recovery.write_text(
        "| Corpus | Attempted | Pooled | Refused |\n"
        "| --- | ---: | ---: | ---: |\n"
        f"| `eval/{corpus.name}` | 4 | 3 | 1 |\n"
        "\n"
        "| Skill | Provider | Round |\n"
        "| --- | --- | ---: |\n"
        "| AST01 | b | 2 |\n",
        encoding="utf-8",
    )

    assert ledger.problems([corpus], ledger_path=recovery) == []

    # The same scorecard, written by the fixed harness: the ledger no longer
    # excuses it.
    modern = dict(frozen, attempted=4, refusals=[])
    _write(corpus, modern)
    found = ledger.problems([corpus], ledger_path=recovery)
    assert any("records 0 refusal" in line for line in found)


def test_a_scorecard_that_counts_its_attempts_but_has_no_refusals_field_fails(tmp_path):
    """Half-modern bytes get no ledger exemption: a file that knows how many
    attempts it made must say what became of the ones it lost."""
    corpus = tmp_path / "scorecards"
    _write(corpus, _card("AST01", ["a", "b"], [["a", "b"], ["a"]], attempted=4))
    recovery = tmp_path / "run5-refusals.md"
    recovery.write_text(
        "| Corpus | Attempted | Pooled | Refused |\n"
        "| --- | ---: | ---: | ---: |\n"
        f"| `eval/{corpus.name}` | 4 | 3 | 1 |\n"
        "\n"
        "| Skill | Provider | Round |\n"
        "| --- | --- | ---: |\n"
        "| AST01 | b | 2 |\n",
        encoding="utf-8",
    )

    found = ledger.problems([corpus], ledger_path=recovery)
    assert any("carries no `refusals` block" in line for line in found)


def test_a_ledger_row_with_no_missing_attempt_behind_it_fails(tmp_path):
    corpus = tmp_path / "scorecards"
    _write(corpus, _card("AST01", ["a", "b"], [["a", "b"], ["a"]]))
    recovery = tmp_path / "run5-refusals.md"
    recovery.write_text(
        "| Corpus | Attempted | Pooled | Refused |\n"
        "| --- | ---: | ---: | ---: |\n"
        f"| `eval/{corpus.name}` | 4 | 3 | 1 |\n"
        "\n"
        "| Skill | Provider | Round |\n"
        "| --- | --- | ---: |\n"
        "| AST01 | b | 2 |\n"
        "| AST01 | a | 1 |\n",
        encoding="utf-8",
    )

    found = ledger.problems([corpus], ledger_path=recovery)
    assert any("is not missing from any scorecard" in line for line in found)


def test_a_ledger_whose_totals_disagree_with_the_files_fails(tmp_path):
    corpus = tmp_path / "scorecards"
    _write(corpus, _card("AST01", ["a", "b"], [["a", "b"], ["a"]]))
    recovery = tmp_path / "run5-refusals.md"
    recovery.write_text(
        "| Corpus | Attempted | Pooled | Refused |\n"
        "| --- | ---: | ---: | ---: |\n"
        f"| `eval/{corpus.name}` | 4 | 4 | 0 |\n"
        "\n"
        "| Skill | Provider | Round |\n"
        "| --- | --- | ---: |\n"
        "| AST01 | b | 2 |\n",
        encoding="utf-8",
    )

    found = ledger.problems([corpus], ledger_path=recovery)
    assert any("attempted/pooled/refused" in line for line in found)


# ---------------------------------------------------------------------------
# 3. This repository, as it stands
# ---------------------------------------------------------------------------


def test_every_scorecard_in_this_repo_accounts_for_its_own_gap():
    found = ledger.problems()
    assert found == [], "unaccounted-for discards:\n" + "\n".join(found)


def test_the_published_corpus_lost_exactly_ten_judgments():
    """The headline arithmetic, re-derived from the files rather than quoted."""
    cards = ledger.load_cards(REPO / "eval" / "scorecards")
    assert len(cards) == 11
    attempted = sum(ledger.attempted_of(c) for _p, c in cards)
    pooled = sum(ledger.pooled_of(c) for _p, c in cards)
    assert (attempted, pooled) == (RUN5_ATTEMPTED, RUN5_POOLED)


def test_the_ledger_names_every_one_of_run_5s_ten():
    derived = sorted(
        attempt.key()
        for _p, card in ledger.load_cards(REPO / "eval" / "scorecards")
        for attempt in ledger.missing_attempts(card)
    )
    assert len(derived) == RUN5_ATTEMPTED - RUN5_POOLED
    rows = {row.key() for row in ledger.ledger_rows(LEDGER_MD.read_text(encoding="utf-8"))}
    assert set(derived) <= rows


def test_the_ledger_says_plainly_what_cannot_be_reconstructed():
    """The honest half of the record. If a future edit quietly drops the "we
    cannot recover the reasons" statement, the document stops being a record of
    a gap and becomes a table that looks complete."""
    text = LEDGER_MD.read_text(encoding="utf-8")
    assert "cannot reconstruct the reasons or the responses" in text
    # And it must not claim to know the refusal mechanism it did not record.
    assert "not supported by anything on disk" in text


def test_the_ledger_does_not_write_an_imputed_number_into_a_scorecard():
    """The what-if in the ledger is a sensitivity check. If it ever leaked into
    the published aggregate, AST01's stored n would have moved."""
    card = json.loads((REPO / "eval" / "scorecards" / "AST01.json").read_text(encoding="utf-8"))
    assert card["aggregate"]["n"] == len(card["judgments"]) == 16
    assert card["aggregate"]["mean"] == 110.1


def test_the_guard_runs_as_a_command_and_is_not_a_no_op():
    """A documented verification command that checks nothing is worse than no
    command. This one names how many judgments it accounted for."""
    result = subprocess.run(
        [sys.executable, "scripts/refusal_ledger.py"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "attempted judgments" in result.stdout
    assert "49 refused" in result.stdout


def test_the_report_regenerates_the_tables_the_ledger_publishes():
    result = subprocess.run(
        [sys.executable, "scripts/refusal_ledger.py", "--report"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    text = LEDGER_MD.read_text(encoding="utf-8")
    for line in result.stdout.splitlines():
        if line.startswith("| AST") or line.startswith("| advisory") or line.startswith("| `eval/"):
            assert line in text, f"the ledger is missing a derived row: {line}"


# ---------------------------------------------------------------------------
# 4. End to end: what the matrix writes is what the guard accepts
# ---------------------------------------------------------------------------


def _load_matrix():
    import importlib.util

    spec = importlib.util.spec_from_file_location("run_judge_matrix_under_test", REPO / "eval" / "run_judge_matrix.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Roster:
    def __init__(self, available):
        self.available = available
        self.unavailable = []


def test_a_scorecard_the_matrix_writes_accounts_for_its_own_refusals(tmp_path, monkeypatch):
    """The whole path in one test: a judge run with one deliberately malformed
    provider, through `eval/run_judge_matrix.py`, and the scorecard it writes
    satisfies the guard without anybody editing the ledger.

    Run 5 failed exactly here. Every seam it fell through — the in-memory audit
    trail, the deleted per-round file, the scorecard with no field for a
    discard — is crossed by this test.
    """
    from scripts.judge_harness import DIMENSIONS, load_rubric

    matrix = _load_matrix()
    maxima = load_rubric().maxima

    class _Fake:
        def __init__(self, name, response):
            self.name = name
            self._response = response

        def judge(self, prompt):
            return self._response

    good = json.dumps({d: {"score": min(14, maxima[d]), "why": f"{d}: cites the NEVER list."} for d in DIMENSIONS})
    adapters = [
        _Fake("bedrock/gpt-oss-120b", good),
        _Fake("claude-cli/sonnet", good),
        # Answers, and the answer will not bind: no justification anywhere.
        _Fake("bedrock/nova-pro", json.dumps({d: 15 for d in DIMENSIONS})),
    ]

    corpus = tmp_path / "scorecards"
    corpus.mkdir()
    monkeypatch.setattr(matrix, "SCORECARDS", corpus)
    monkeypatch.setattr(matrix, "build_adapters", lambda: adapters)
    monkeypatch.setattr(matrix, "build_roster", lambda _adapters: _Roster(adapters))

    audit = tmp_path / "audit.yml"
    assert matrix.main(["--rounds", "2", "--skills", "AST01", "--audit-path", str(audit)]) == 0

    card = json.loads((corpus / "AST01.json").read_text(encoding="utf-8"))
    assert (card["attempted"], card["pooled"]) == (6, 4)
    assert card["refusals_by_provider"] == {"bedrock/nova-pro": 2}
    assert [r["round"] for r in card["refusals"]] == [1, 2]
    assert all(r["status"] == "malformed" and r["skill"] == "AST01" for r in card["refusals"])
    assert all(r["response_excerpt"] for r in card["refusals"])

    # The per-round scratch files are deleted, as they were in run 5 — and this
    # time nothing is lost with them.
    assert not list(corpus.glob(".AST01.round*.json"))
    assert ledger.problems([corpus], ledger_path=tmp_path / "no-ledger.md") == []

    # And the same refusals reached the append-only audit trail independently.
    from adapters.base import runtime_entries

    entries = runtime_entries(audit)
    assert [(e["skill"], e["provider"], e["round"]) for e in entries] == [
        ("AST01", "bedrock/nova-pro", 1),
        ("AST01", "bedrock/nova-pro", 2),
    ]
