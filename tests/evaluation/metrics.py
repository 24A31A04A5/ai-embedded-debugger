"""Evaluation metrics for AI debugging benchmark."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class MetricResult:
    """Result of a single metric computation."""
    name: str
    value: float
    details: dict[str, Any] = None


def compute_root_cause_accuracy(predicted: str | None, expected: str) -> float:
    """Compute root cause accuracy using semantic similarity.

    Returns a score between 0.0 and 1.0.
    """
    if not predicted or not expected:
        return 0.0

    # Simple word overlap Jaccard similarity
    pred_words = set(predicted.lower().split())
    exp_words = set(expected.lower().split())

    if not pred_words or not exp_words:
        return 0.0

    intersection = pred_words & exp_words
    union = pred_words | exp_words

    return len(intersection) / len(union)


def compute_fix_accuracy(predicted: str | None, expected: str) -> float:
    """Compute fix accuracy using semantic similarity."""
    return compute_root_cause_accuracy(predicted, expected)


def compute_confidence_accuracy(predicted: str | None, expected: str) -> float:
    """Compute confidence level accuracy (exact match)."""
    if not predicted or not expected:
        return 0.0
    return 1.0 if predicted.lower() == expected.lower() else 0.0


def compute_citation_accuracy(
    predicted: list[dict[str, Any]],
    expected: list[dict[str, Any]] | None
) -> tuple[float, int]:
    """Compute citation accuracy and count of fabricated citations.

    Returns (accuracy, fabricated_count).
    """
    if not expected and not predicted:
        return 1.0, 0
    if not expected and predicted:
        return 0.0, len(predicted)
    if expected and not predicted:
        return 0.0, 0

    # Match by document_name and page_number
    matched = 0
    for exp in expected:
        for pred in predicted:
            if (pred.get("document_name") == exp.get("document_name") and
                pred.get("page_number") == exp.get("page_number")):
                matched += 1
                break

    accuracy = matched / len(expected)
    fabricated = len(predicted) - matched
    return accuracy, max(0, fabricated)


def compute_code_issue_f1(
    predicted: list[dict[str, Any]],
    expected: list[dict[str, Any]] | None
) -> float:
    """Compute F1 score for code issue detection."""
    if not expected and not predicted:
        return 1.0
    if not expected:
        return 0.0  # false positives
    if not predicted:
        return 0.0  # false negatives

    # Match by kind and location
    matched = 0
    matched_pred_indices = set()

    for i, exp in enumerate(expected):
        for j, pred in enumerate(predicted):
            if j in matched_pred_indices:
                continue
            if (pred.get("kind") == exp.get("kind") and
                pred.get("location") == exp.get("location")):
                matched += 1
                matched_pred_indices.add(j)
                break

    precision = matched / len(predicted) if predicted else 0
    recall = matched / len(expected) if expected else 0

    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def compute_uncertainty_handling(
    predicted_follow_up: str | None,
    expected_follow_up: str | None,
    confidence: str | None
) -> float:
    """Evaluate if uncertainty is handled correctly.

    Returns 1.0 if correct, 0.0 if incorrect.
    """
    # If expected follow_up exists, model should express uncertainty
    if expected_follow_up and expected_follow_up.strip():
        if predicted_follow_up and len(predicted_follow_up.strip()) > 10:
            return 1.0
        return 0.0

    # If no expected follow_up, model should be confident
    if confidence in ("high", "medium"):
        return 1.0
    return 0.0


def compute_fabricated_citation_rate(
    predicted: list[dict[str, Any]],
    expected: list[dict[str, Any]] | None
) -> float:
    """Compute rate of fabricated citations per case."""
    if not predicted:
        return 0.0
    if not expected:
        return float(len(predicted))

    matched = 0
    for exp in expected:
        for pred in predicted:
            if (pred.get("document_name") == exp.get("document_name") and
                pred.get("page_number") == exp.get("page_number")):
                matched += 1
                break

    fabricated = len(predicted) - matched
    return float(max(0, fabricated))


def compute_unsupported_claims(
    response: dict[str, Any],
    evidence_used: list[str] | None
) -> int:
    """Detect unsupported claims in the response.

    This is a simplified heuristic - in practice would use an LLM judge.
    """
    # Placeholder - would need more sophisticated analysis
    return 0


def aggregate_metrics(results: list[dict[str, Any]]) -> dict[str, float]:
    """Aggregate per-case metrics into overall scores."""
    if not results:
        return {}

    metrics = {}
    for key in results[0].keys():
        if key in ("test_case_id", "approach", "raw_response", "error"):
            continue
        values = [r.get(key, 0) for r in results if r.get(key) is not None]
        if values and isinstance(values[0], (int, float)):
            metrics[key] = sum(values) / len(values)

    return metrics


def print_metrics_table(metrics: dict[str, dict[str, float]]) -> None:
    """Print metrics in a formatted table."""
    approaches = list(metrics.keys())
    if not approaches:
        return

    all_keys = set()
    for m in metrics.values():
        all_keys.update(m.keys())

    print("\n" + "=" * 80)
    print("AGGREGATED METRICS")
    print("=" * 80)

    header = f"{'Metric':<35}" + "".join(f"{a:>15}" for a in approaches)
    print(header)
    print("-" * len(header))

    for key in sorted(all_keys):
        row = f"{key:<35}"
        for a in approaches:
            val = metrics[a].get(key, 0)
            if isinstance(val, float):
                row += f"{val:>15.1%}" if val <= 1.0 else f"{val:>15.2f}"
            else:
                row += f"{val:>15}"
        print(row)

    print("=" * 80)