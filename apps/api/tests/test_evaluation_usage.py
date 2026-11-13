"""Offline tests for usage / served-model recording in run_eval.py (no Gemini calls)."""

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tests" / "evaluation"))

import run_eval  # noqa: E402


def test_usage_of_handles_missing_metadata():
    u = run_eval.usage_of(SimpleNamespace())
    assert u["model_version"] is None and u["prompt_tokens"] is None and u["thought_tokens"] is None
    assert run_eval.usage_of(None)["model_version"] is None


def test_usage_of_reads_counts_only():
    resp = SimpleNamespace(
        model_version="v-test",
        text="SECRET ANSWER",
        usage_metadata=SimpleNamespace(
            prompt_token_count=10, candidates_token_count=5, thoughts_token_count=3, total_token_count=18
        ),
    )
    u = run_eval.usage_of(resp)
    assert u == {"model_version": "v-test", "prompt_tokens": 10, "output_tokens": 5, "thought_tokens": 3, "total_tokens": 18}
    assert "SECRET" not in repr(u)


def test_served_versions_not_confirmed_when_missing():
    scores = [SimpleNamespace(usage={}, judge_usage=None), SimpleNamespace(usage={"model_version": None})]
    assert run_eval.served_versions(scores, "usage") == run_eval.NOT_CONFIRMED
    assert run_eval.served_versions(scores, "judge_usage") == run_eval.NOT_CONFIRMED
    assert run_eval.served_versions([], "usage") == "not independently confirmed"


def test_served_versions_collects_returned_values():
    scores = [SimpleNamespace(usage={"model_version": "b"}), SimpleNamespace(usage={"model_version": "a"})]
    assert run_eval.served_versions(scores, "usage") == ["a", "b"]
