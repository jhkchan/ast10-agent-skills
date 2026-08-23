"""Tests for scripts.eval_counts — spec.md gate-3 vendoring (T-2.2)."""

from __future__ import annotations

from scripts.eval_counts import (
    EVAL_COUNTS,
    MIN_EVALS,
    MIN_NEGATIVE_EVALS,
    is_negative_eval,
)


def test_floors_match_upstream_vendored_values():
    assert MIN_EVALS == 7
    assert MIN_NEGATIVE_EVALS == 2


def test_eval_counts_starts_empty_pending_t3x_skill_authoring():
    # Not REDACTED-SIBLING-REPO' skill names — this repo has none yet.
    assert EVAL_COUNTS == {}


def test_explicit_negative_flag_is_negative():
    assert is_negative_eval({"name": "some-eval", "negative": True}) is True


def test_negative_prefixed_name_is_negative():
    assert is_negative_eval({"name": "negative-no-write-outside-sandbox"}) is True


def test_negative_infix_name_is_negative():
    assert is_negative_eval({"name": "ast04-negative-toml-injection"}) is True


def test_refusal_expected_output_is_negative():
    assert (
        is_negative_eval(
            {"name": "clean", "expected_output": "No — this manifest is safe."}
        )
        is True
    )


def test_ordinary_eval_is_not_negative():
    assert (
        is_negative_eval(
            {"name": "detect-deny-write-bypass", "expected_output": "Flag AST04."}
        )
        is False
    )
