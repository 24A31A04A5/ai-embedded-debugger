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


def test_split_and_abstain_cases() -> None:
    cases: list[dict[str, Any]] = runner.load_cases()
    abstain = [c for c in cases if c["expected"].get("abstain")]
    assert len(abstain) >= 4
    assert {c["split"] for c in abstain} == {"dev", "holdout"}


def test_dev_references_are_verbatim_with_metadata() -> None:
    for case in runner.load_cases(split="dev"):
        for ref in case["reference_context"]:
            assert ref.get("verification") in {"verified", "differs"}, case["id"]
            assert ref.get("revision"), case["id"]
            assert ref.get("url"), case["id"]


def test_abstention_is_scored() -> None:
    case: dict[str, Any] = runner.load_cases(only=["abstain-stm32-i2c-hal-error"])[0]
    good = runner.score_response(case, "grounded", 1, runner.mock_response(case, "grounded"))
    assert good.abstained and good.asked_needed_info and good.root_cause_keyword
    overconfident: dict[str, Any] = {
        "root_cause_summary": "The 7-bit address is not shifted left.",
        "confidence_level": "high",
        "proposed_fix": "Use dev_addr << 1.",
    }
    bad = runner.score_response(case, "grounded", 1, overconfident)
    assert not bad.root_cause_keyword
    assert bad.confidently_wrong


def test_unsupported_claims_are_flagged() -> None:
    case: dict[str, Any] = runner.load_cases(only=["esp32-gpio34-output"])[0]
    resp: dict[str, Any] = {
        "root_cause_summary": "GPIO34 is input-only; also set REG_GPIO_FAKE_CTRL to 0xDEAD.",
        "proposed_fix": "Use GPIO2 instead.",
    }
    flagged = runner.unsupported_claims(case, "grounded", resp)
    assert "0xdead" in flagged
    assert "reg_gpio_fake_ctrl" in flagged
    assert "gpio34" not in flagged


def test_summary_reports_each_repeat_and_spread() -> None:
    case: dict[str, Any] = runner.load_cases(only=["esp32-mpu6050-address"])[0]
    good = runner.mock_response(case, "grounded")
    bad: dict[str, Any] = {"root_cause_summary": "wiring", "proposed_fix": "check wiring"}
    scores = [
        runner.score_response(case, "grounded", 1, good),
        runner.score_response(case, "grounded", 2, bad),
    ]
    summary = runner.summarize(scores)
    assert set(summary["per_run"]["grounded"]) == {1, 2}
    spread = summary["spread"]["grounded"]["root_cause_accuracy"]
    assert spread["mean"] == 50.0 and spread["min"] == 0.0 and spread["max"] == 100.0
    assert spread["std"] > 0
