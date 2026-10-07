"""Offline checks for the AI evaluation harness (no Gemini calls)."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

EVAL_DIR = Path(__file__).resolve().parents[3] / "tests" / "evaluation"


def _load_runner() -> ModuleType:
    spec = importlib.util.spec_from_file_location("run_eval", EVAL_DIR / "run_eval.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["run_eval"] = module  # dataclasses need the module registered
    spec.loader.exec_module(module)
    return module


runner = _load_runner()


def test_cases_are_valid() -> None:
    cases: list[dict[str, Any]] = runner.load_cases()
    assert len(cases) >= 20
    assert runner.validate_cases(cases) == []


def test_holdout_split_exists() -> None:
    cases: list[dict[str, Any]] = runner.load_cases()
    assert sum(c["split"] == "holdout" for c in cases) >= 5


def test_correct_answer_scores_full_marks() -> None:
    case: dict[str, Any] = runner.load_cases(only=["esp32-mpu6050-address"])[0]
    resp = runner.mock_response(case, "grounded")
    score = runner.score_response(case, "grounded", 1, resp)
    assert score.root_cause_keyword
    assert score.fix_correct
    assert score.citation_correct
    assert not score.fabricated_citation
    assert not score.confidently_wrong


def test_wrong_answer_and_fabricated_citation_are_caught() -> None:
    case: dict[str, Any] = runner.load_cases(only=["esp32-mpu6050-address"])[0]
    resp: dict[str, Any] = {
        "root_cause_summary": "The sensor is broken.",
        "confidence_level": "high",
        "likely_causes": [{"cause": "Faulty sensor", "plausibility": "high"}],
        "proposed_fix": "Replace the sensor.",
        "datasheet_citations": [{"document_name": "Bosch BME280 Datasheet"}],
    }
    score = runner.score_response(case, "baseline", 1, resp)
    assert not score.root_cause_keyword
    assert not score.fix_correct
    assert score.fabricated_citation
    assert score.confidently_wrong
