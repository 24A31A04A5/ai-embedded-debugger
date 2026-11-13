"""Frozen-dataset and answer-leakage checks for the evaluation harness (offline, no Gemini)."""

import copy
import importlib.util
import json
import shutil
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

EVAL_DIR = Path(__file__).resolve().parents[3] / "tests" / "evaluation"


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


runner = _load("run_eval", EVAL_DIR / "run_eval.py")
manifest = _load("dataset_manifest", EVAL_DIR / "dataset_manifest.py")


def test_frozen_manifest_matches_cases() -> None:
    assert manifest.verify() == []


def test_splits_are_hashed_separately(tmp_path: Path) -> None:
    cases_dir = tmp_path / "cases"
    shutil.copytree(EVAL_DIR / "cases", cases_dir)
    before = manifest.compute(cases_dir)
    target = cases_dir / "stm32-hardfault-null-fnptr.json"  # a holdout case
    data = json.loads(target.read_text(encoding="utf-8"))
    data["user_question"] += " "
    target.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    after = manifest.compute(cases_dir)
    assert after["dev"]["manifest_sha256"] == before["dev"]["manifest_sha256"]
    assert after["holdout"]["manifest_sha256"] != before["holdout"]["manifest_sha256"]
    problems = manifest.verify(cases_dir)
    assert problems == ["holdout: stm32-hardfault-null-fnptr.json changed"]


def test_crlf_checkout_hashes_the_same(tmp_path: Path) -> None:
    src = EVAL_DIR / "cases" / "esp32-mpu6050-address.json"
    crlf = tmp_path / src.name
    crlf.write_bytes(src.read_bytes().replace(b"\n", b"\r\n"))
    assert manifest.file_sha256(crlf) == manifest.file_sha256(src)


def test_real_cases_have_no_answer_leakage() -> None:
    assert runner.leakage_problems(runner.load_cases()) == []


def test_leak_in_excerpt_is_detected() -> None:
    case: dict[str, Any] = copy.deepcopy(runner.load_cases(only=["stm32-gpio-clock"])[0])
    case["reference_context"][0]["snippet"] += " " + case["expected"]["fix"]
    problems = runner.leakage_problems([case])
    assert any("excerpt 0 snippet repeats expected answer" in p for p in problems)
    assert any("prompt contains expected.fix" in p for p in problems)


def test_leak_in_question_is_detected_for_every_condition() -> None:
    case: dict[str, Any] = copy.deepcopy(runner.load_cases(only=["esp32-mpu6050-address"])[0])
    case["user_question"] = case["expected"]["root_cause"]
    problems = runner.leakage_problems([case])
    for cond in ("baseline", "no_rag", "grounded"):
        assert f"esp32-mpu6050-address/{cond}: prompt contains expected.root_cause" in problems


def test_conditions_receive_identical_inputs() -> None:
    for case in runner.load_cases():
        _, base = runner.build_prompt(case, "baseline")
        _, norag = runner.build_prompt(case, "no_rag")
        _, grounded = runner.build_prompt(case, "grounded")
        assert base == norag
        for part in runner.case_inputs(case):
            if part:
                assert part.strip() in grounded
        if case["reference_context"]:
            assert "<retrieved_datasheets_and_documents>" in grounded
            assert "<retrieved_datasheets_and_documents>" not in norag


def test_detector_spot_check_runs() -> None:
    spot = _load("detector_spot_check", EVAL_DIR / "spot_checks" / "detector_spot_check.py")
    result = spot.run()
    assert result["unsupported_claims"]["items"] == 20
    assert result["abstention"]["items"] == 16
