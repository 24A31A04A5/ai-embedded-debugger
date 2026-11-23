"""Pytest tests for the evaluation benchmark.

Run with: pytest tests/evaluation/test_benchmark.py -v
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.evaluation.benchmark import (
    BenchmarkResult,
    TestCase,
    EvaluationResult,
    load_test_cases,
    run_benchmark,
    print_benchmark_results,
)
from tests.evaluation.metrics import (
    compute_root_cause_accuracy,
    compute_fix_accuracy,
    compute_confidence_accuracy,
    compute_citation_accuracy,
    compute_code_issue_f1,
    compute_uncertainty_handling,
    aggregate_metrics,
)


class TestMetrics:
    """Test individual metric functions."""

    def test_root_cause_accuracy_exact_match(self):
        assert compute_root_cause_accuracy("Missing semicolon causes error", "Missing semicolon causes error") == 1.0

    def test_root_cause_accuracy_partial_match(self):
        score = compute_root_cause_accuracy("Missing semicolon on line 5", "Missing semicolon causes cascading errors")
        assert 0.0 < score < 1.0

    def test_root_cause_accuracy_no_match(self):
        assert compute_root_cause_accuracy("Wrong variable type", "Missing semicolon") == 0.0

    def test_root_cause_accuracy_none_predicted(self):
        assert compute_root_cause_accuracy(None, "Expected cause") == 0.0

    def test_root_cause_accuracy_none_expected(self):
        assert compute_root_cause_accuracy("Predicted cause", None) == 0.0

    def test_fix_accuracy(self):
        assert compute_fix_accuracy("Add semicolon", "Add semicolon") == 1.0
        assert compute_fix_accuracy("Add semicolon at end", "Add semicolon") >= 0.5

    def test_confidence_accuracy(self):
        assert compute_confidence_accuracy("high", "high") == 1.0
        assert compute_confidence_accuracy("medium", "high") == 0.0
        assert compute_confidence_accuracy(None, "high") == 0.0

    def test_citation_accuracy_perfect(self):
        pred = [{"document_name": "ESP32 Datasheet", "page_number": 42}]
        exp = [{"document_name": "ESP32 Datasheet", "page_number": 42}]
        acc, fab = compute_citation_accuracy(pred, exp)
        assert acc == 1.0
        assert fab == 0

    def test_citation_accuracy_fabricated(self):
        pred = [{"document_name": "Fake Doc", "page_number": 1}]
        exp = []
        acc, fab = compute_citation_accuracy(pred, exp)
        assert acc == 0.0
        assert fab == 1

    def test_citation_accuracy_missing(self):
        pred = []
        exp = [{"document_name": "ESP32 Datasheet", "page_number": 42}]
        acc, fab = compute_citation_accuracy(pred, exp)
        assert acc == 0.0
        assert fab == 0

    def test_citation_accuracy_partial(self):
        pred = [
            {"document_name": "ESP32 Datasheet", "page_number": 42},
            {"document_name": "Fake Doc", "page_number": 1},
        ]
        exp = [{"document_name": "ESP32 Datasheet", "page_number": 42}]
        acc, fab = compute_citation_accuracy(pred, exp)
        assert acc == 1.0
        assert fab == 1

    def test_code_issue_f1_perfect(self):
        pred = [{"kind": "syntax_error", "location": "main.c:5"}]
        exp = [{"kind": "syntax_error", "location": "main.c:5"}]
        assert compute_code_issue_f1(pred, exp) == 1.0

    def test_code_issue_f1_partial(self):
        pred = [
            {"kind": "syntax_error", "location": "main.c:5"},
            {"kind": "buffer_overflow", "location": "main.c:10"},
        ]
        exp = [{"kind": "syntax_error", "location": "main.c:5"}]
        # Precision = 0.5, Recall = 1.0, F1 = 2*0.5*1.0/1.5 = 0.667
        f1 = compute_code_issue_f1(pred, exp)
        assert 0.6 < f1 < 0.7

    def test_code_issue_f1_none(self):
        assert compute_code_issue_f1([], None) == 1.0
        assert compute_code_issue_f1([{"kind": "syntax_error"}], None) == 0.0
        assert compute_code_issue_f1(None, [{"kind": "syntax_error"}]) == 0.0

    def test_uncertainty_handling_with_followup(self):
        assert compute_uncertainty_handling("Need more info", "Need ELF file", "low") == 1.0
        assert compute_uncertainty_handling(None, "Need ELF file", "low") == 0.0
        assert compute_uncertainty_handling("Short", "Need ELF file", "low") == 0.0

    def test_uncertainty_handling_without_followup(self):
        assert compute_uncertainty_handling(None, None, "high") == 1.0
        assert compute_uncertainty_handling(None, None, "medium") == 1.0
        assert compute_uncertainty_handling(None, None, "low") == 0.0


class TestDataLoading:
    """Test loading of test cases."""

    def test_load_dev_cases(self):
        cases = load_test_cases("dev")
        assert len(cases) == 18
        assert all(isinstance(c, TestCase) for c in cases)
        assert all(c.id.startswith("dev_") for c in cases)

    def test_load_holdout_cases(self):
        cases = load_test_cases("holdout")
        assert len(cases) == 8
        assert all(isinstance(c, TestCase) for c in cases)
        assert all(c.id.startswith("holdout_") for c in cases)

    def test_case_structure(self):
        cases = load_test_cases("dev")
        case = cases[0]
        assert case.id
        assert case.category
        assert case.firmware_code
        assert case.expected_root_cause
        assert case.expected_fix
        assert case.expected_confidence_level in ("high", "medium", "low")


class TestBenchmarkRunner:
    """Test the benchmark runner."""

    def test_run_benchmark_dev(self):
        cases = load_test_cases("dev")
        results = run_benchmark(cases)

        assert "plain_gemini" in results
        assert "prompt_only" in results
        assert "full_pipeline" in results

        for approach, result in results.items():
            assert isinstance(result, BenchmarkResult)
            assert result.total_cases == 18
            assert result.successful_cases == 18
            assert 0.0 <= result.root_cause_accuracy <= 1.0
            assert 0.0 <= result.fix_accuracy <= 1.0
            assert 0.0 <= result.confidence_accuracy <= 1.0

    def test_run_benchmark_holdout(self):
        cases = load_test_cases("holdout")
        results = run_benchmark(cases)

        for approach, result in results.items():
            assert result.total_cases == 8
            assert result.successful_cases == 8

    def test_benchmark_results_saved(self):
        cases = load_test_cases("dev")
        results = run_benchmark(cases)

        output_path = Path(__file__).parent / "benchmark_results.json"
        assert output_path.exists()

        with open(output_path) as f:
            data = json.load(f)

        assert "dev" in data
        assert "plain_gemini" in data["dev"]
        assert data["dev"]["plain_gemini"]["total_cases"] == 18


class TestMetricAggregation:
    """Test metric aggregation."""

    def test_aggregate_metrics(self):
        results = [
            {"root_cause_accuracy": 0.8, "fix_accuracy": 0.9, "test_case_id": "1"},
            {"root_cause_accuracy": 0.6, "fix_accuracy": 0.7, "test_case_id": "2"},
        ]
        aggregated = aggregate_metrics(results)
        assert aggregated["root_cause_accuracy"] == 0.7
        assert aggregated["fix_accuracy"] == 0.8


# Integration-style tests that would run with real API (marked as integration)
@pytest.mark.integration
class TestRealAPIBenchmark:
    """Benchmark tests that call the real Gemini API.

    These require RUN_DATABASE_INTEGRATION_TESTS=1 and GEMINI_API_KEY set.
    """

    @pytest.fixture
    def real_cases(self):
        return load_test_cases("dev")

    def test_real_plain_gemini(self, real_cases):
        """Test plain Gemini approach with real API."""
        # This would call the actual analyze_debugging_context function
        # Skipped unless integration tests are enabled
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])