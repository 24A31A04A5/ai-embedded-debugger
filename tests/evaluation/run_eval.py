"""Evaluation runner for the AI Embedded Debugger.

Compares three conditions on the same cases, same model, same output schema:

  baseline  Plain Gemini: generic prompt, no embedded system instruction, no datasheets.
  no_rag    Our embedded system instruction, but no datasheet excerpts (ablation).
  grounded  Our full pipeline prompt: system instruction + datasheet excerpts passed
            through AssembledDebugContext exactly like the API does.

Usage (from repo root, with GEMINI_API_KEY set):

  python tests/evaluation/run_eval.py --validate
  python tests/evaluation/run_eval.py --dry-run
  python tests/evaluation/run_eval.py --repeats 3 --judge
  python tests/evaluation/run_eval.py --conditions grounded baseline --split holdout

Results are written to tests/evaluation/results/<timestamp>/ as raw.jsonl,
summary.json and summary.md (tables ready for the report).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
import time
import uuid
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
EVAL_DIR = Path(__file__).resolve().parent
CASES_DIR = EVAL_DIR / "cases"
RESULTS_DIR = EVAL_DIR / "results"
sys.path.insert(0, str(ROOT / "apps" / "api"))

# Keep in sync with the model used in apps/api/app/ai/gemini.py
DEFAULT_MODEL = os.getenv("EVAL_MODEL", "gemini-3.5-flash")
CONDITIONS = ("baseline", "no_rag", "grounded")

BASELINE_SYSTEM = "You are a helpful assistant. Diagnose the user's problem and answer in the requested JSON format."

REQUIRED_CASE_KEYS = {
    "id", "title", "category", "target", "difficulty", "split",
    "firmware_code", "compiler_output", "serial_logs", "reference_context", "expected",
}
REQUIRED_EXPECTED_KEYS = {"root_cause", "root_cause_keywords", "fix", "fix_keywords", "expected_citation"}


# ───────────────────────────── Cases ─────────────────────────────


def load_cases(split: str | None = None, only: list[str] | None = None) -> list[dict[str, Any]]:
    cases = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(CASES_DIR.glob("*.json"))]
    if split:
        cases = [c for c in cases if c["split"] == split]
    if only:
        cases = [c for c in cases if c["id"] in only]
    return cases


def validate_cases(cases: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    for c in cases:
        cid = c.get("id", "<missing id>")
        if cid in seen:
            errors.append(f"{cid}: duplicate id")
        seen.add(cid)
        missing = REQUIRED_CASE_KEYS - c.keys()
        if missing:
            errors.append(f"{cid}: missing keys {sorted(missing)}")
            continue
        exp = c["expected"]
        if REQUIRED_EXPECTED_KEYS - exp.keys():
            errors.append(f"{cid}: expected missing {sorted(REQUIRED_EXPECTED_KEYS - exp.keys())}")
            continue
        if not (c["firmware_code"] or c["compiler_output"] or c["serial_logs"]):
            errors.append(f"{cid}: no evidence (code, compiler output or logs)")
        if c["split"] not in ("dev", "holdout"):
            errors.append(f"{cid}: split must be dev or holdout")
        if not c["reference_context"]:
            errors.append(f"{cid}: needs at least one reference_context excerpt")
        titles = {r["title"] for r in c["reference_context"]}
        for t in exp["expected_citation"]:
            if t not in titles:
                errors.append(f"{cid}: expected_citation '{t}' not in reference_context")
        for key in ("root_cause_keywords", "fix_keywords"):
            for group in exp[key]:
                if not group:
                    errors.append(f"{cid}: empty keyword group in {key}")
                for pattern in group:
                    try:
                        re.compile(pattern)
                    except re.error as e:
                        errors.append(f"{cid}: bad regex {pattern!r}: {e}")
        # The expected answer must pass its own keyword checks.
        if not keywords_match(exp["root_cause"], exp["root_cause_keywords"]):
            errors.append(f"{cid}: expected.root_cause fails its own root_cause_keywords")
        if not keywords_match(exp["fix"], exp["fix_keywords"]):
            errors.append(f"{cid}: expected.fix fails its own fix_keywords")
    return errors


# ───────────────────────────── Prompts ─────────────────────────────


def build_prompt(case: dict[str, Any], condition: str) -> tuple[str, str]:
    """Return (system_instruction, user_prompt) for a case under a condition."""
    from app.ai.gemini import SYSTEM_INSTRUCTION
    from app.schemas.context import AssembledDebugContext, DocumentContext, ProjectContext

    docs: list[DocumentContext] = []
    if condition == "grounded":
        for i, r in enumerate(case["reference_context"]):
            docs.append(
                DocumentContext(
                    doc_id=f"eval-doc-{i}",
                    chunk_id=f"{case['id']}-chunk-{i}",
                    title=r["title"],
                    snippet=r["snippet"],
                    section=r.get("section"),
                    content_type=r.get("content_type"),
                    page_number=r.get("page_number"),
                )
            )

    ctx = AssembledDebugContext(
        project=ProjectContext(project_id=uuid.UUID(int=0), project_name=case["target"]),
        user_question=case.get("user_question"),
        firmware_code=case["firmware_code"],
        compiler_output=case["compiler_output"],
        serial_logs=case["serial_logs"],
        document_context=docs,
    )
    prompt = f"Please analyze the following embedded debugging context:\n\n{ctx.format_prompt()}\n"
    system = BASELINE_SYSTEM if condition == "baseline" else SYSTEM_INSTRUCTION
    return system, prompt


# ───────────────────────────── Model calls ─────────────────────────────


def call_model(system: str, prompt: str, model: str) -> dict[str, Any]:
    from google import genai
    from google.genai import types

    from app.schemas.debug import DebugResponse

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    resp = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            response_schema=DebugResponse,
            temperature=0.2,
        ),
    )
    if not resp.text:
        raise ValueError("empty response")
    data: dict[str, Any] = json.loads(resp.text)
    return data


JUDGE_PROMPT = """You are grading an embedded-systems debugging answer.

Reference root cause:
{expected}

Answer's root cause:
{answer}

Does the answer identify the SAME underlying root cause as the reference (wording may differ;
a vaguer or different cause is NOT the same)? Reply with exactly one word: YES or NO."""


def judge_root_cause(expected: str, answer: str, model: str) -> bool:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    resp = client.models.generate_content(
        model=model,
        contents=JUDGE_PROMPT.format(expected=expected, answer=answer),
        config=types.GenerateContentConfig(temperature=0.0),
    )
    return (resp.text or "").strip().upper().startswith("YES")


def mock_response(case: dict[str, Any], condition: str) -> dict[str, Any]:
    """Deterministic fake answers used by --dry-run to exercise the pipeline."""
    exp = case["expected"]
    good = condition == "grounded" or (condition == "no_rag" and case["split"] == "dev")
    cites = (
        [{"document_name": exp["expected_citation"][0], "relevant_snippet": "..."}]
        if condition == "grounded"
        else []
    )
    return {
        "problem_observed": case["title"],
        "root_cause_summary": exp["root_cause"] if good else "Possibly a wiring or power issue.",
        "confidence_level": "high",
        "evidence_used": [],
        "likely_causes": [{"cause": exp["root_cause"] if good else "wiring", "plausibility": "high"}],
        "recommended_steps": [],
        "proposed_fix": exp["fix"] if good else "Check the wiring.",
        "corrected_code": None,
        "datasheet_citations": cites,
    }


# ───────────────────────────── Scoring ─────────────────────────────


def keywords_match(text: str, groups: list[list[str]]) -> bool:
    t = text.lower()
    return all(any(re.search(p, t, re.IGNORECASE) for p in group) for group in groups)


def top_cause(resp: dict[str, Any]) -> str:
    causes = resp.get("likely_causes") or []
    order = {"high": 0, "medium": 1, "low": 2}
    if not causes:
        return ""
    best = sorted(causes, key=lambda c: order.get(c.get("plausibility", "low"), 3))[0]
    return str(best.get("cause", ""))


def root_cause_text(resp: dict[str, Any]) -> str:
    parts = [resp.get("root_cause_summary") or "", top_cause(resp)]
    return "\n".join(p for p in parts if p)


def fix_text(resp: dict[str, Any]) -> str:
    return "\n".join(p for p in (resp.get("proposed_fix") or "", resp.get("corrected_code") or "") if p)


def _doc_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", name.lower().split("(")[0]).strip()


def doc_matches(cited: str, title: str) -> bool:
    a, b = _doc_key(cited), _doc_key(title)
    return bool(a) and bool(b) and (a in b or b in a)


@dataclass
class Score:
    case_id: str
    condition: str
    run: int
    category: str
    split: str
    ok: bool = True
    error: str | None = None
    root_cause_keyword: bool = False
    root_cause_judge: bool | None = None
    fix_correct: bool = False
    cites_any: bool = False
    citation_correct: bool = False
    fabricated_citation: bool = False
    confidence: str | None = None
    confidently_wrong: bool = False
    latency_s: float = 0.0
    root_cause_answer: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def root_cause(self) -> bool:
        return self.root_cause_judge if self.root_cause_judge is not None else self.root_cause_keyword


def score_response(case: dict[str, Any], condition: str, run: int, resp: dict[str, Any]) -> Score:
    exp = case["expected"]
    s = Score(case_id=case["id"], condition=condition, run=run, category=case["category"], split=case["split"])
    rc = root_cause_text(resp)
    s.root_cause_answer = rc
    s.root_cause_keyword = keywords_match(rc, exp["root_cause_keywords"])
    s.fix_correct = keywords_match(fix_text(resp), exp["fix_keywords"])

    cites = [c.get("document_name", "") for c in (resp.get("datasheet_citations") or []) if c]
    provided = [r["title"] for r in case["reference_context"]] if condition == "grounded" else []
    s.cites_any = bool(cites)
    s.citation_correct = any(doc_matches(c, t) for c in cites for t in exp["expected_citation"]) and condition == "grounded"
    # A citation is fabricated when it names a document that was never given to the model.
    s.fabricated_citation = any(not any(doc_matches(c, t) for t in provided) for c in cites)

    s.confidence = resp.get("confidence_level")
    s.confidently_wrong = (not s.root_cause_keyword) and s.confidence == "high"
    return s


# ───────────────────────────── Reporting ─────────────────────────────


def pct(values: list[bool]) -> float:
    return round(100.0 * sum(values) / len(values), 1) if values else 0.0


def summarize(scores: list[Score]) -> dict[str, Any]:
    by_cond: dict[str, list[Score]] = defaultdict(list)
    for s in scores:
        if s.ok:
            by_cond[s.condition].append(s)

    summary: dict[str, Any] = {"conditions": {}, "by_category": {}, "errors": sum(not s.ok for s in scores)}
    for cond, ss in by_cond.items():
        summary["conditions"][cond] = {
            "n": len(ss),
            "root_cause_accuracy": pct([s.root_cause for s in ss]),
            "root_cause_keyword_accuracy": pct([s.root_cause_keyword for s in ss]),
            "fix_accuracy": pct([s.fix_correct for s in ss]),
            "citation_accuracy": pct([s.citation_correct for s in ss]),
            "fabricated_citation_rate": pct([s.fabricated_citation for s in ss]),
            "confidently_wrong_rate": pct([s.confidently_wrong for s in ss]),
            "median_latency_s": round(statistics.median([s.latency_s for s in ss]), 2) if ss else 0.0,
            "holdout_root_cause_accuracy": pct([s.root_cause for s in ss if s.split == "holdout"]),
        }
        cats: dict[str, list[Score]] = defaultdict(list)
        for s in ss:
            cats[s.category].append(s)
        summary["by_category"][cond] = {k: pct([s.root_cause for s in v]) for k, v in sorted(cats.items())}
    return summary


def to_markdown(summary: dict[str, Any], meta: dict[str, Any]) -> str:
    conds = [c for c in CONDITIONS if c in summary["conditions"]]
    names = {"baseline": "Plain Gemini", "no_rag": "Ours without RAG", "grounded": "Ours (RAG grounded)"}
    lines = [
        "# Evaluation results",
        "",
        f"- Model: `{meta['model']}`  ",
        f"- Cases: {meta['cases']} ({meta['split'] or 'all splits'}), repeats: {meta['repeats']}, judge: {meta['judge']}  ",
        f"- Run: {meta['timestamp']}{'  (DRY RUN, mock answers)' if meta['dry_run'] else ''}",
        "",
        "| Metric | " + " | ".join(names[c] for c in conds) + " |",
        "|---|" + "---|" * len(conds),
    ]
    rows = [
        ("Root-cause accuracy", "root_cause_accuracy", "%"),
        ("Root-cause accuracy (holdout only)", "holdout_root_cause_accuracy", "%"),
        ("Fix accuracy", "fix_accuracy", "%"),
        ("Correct datasheet citation", "citation_accuracy", "%"),
        ("Fabricated citations", "fabricated_citation_rate", "%"),
        ("Confidently wrong", "confidently_wrong_rate", "%"),
        ("Median latency", "median_latency_s", " s"),
    ]
    for label, key, unit in rows:
        lines.append(f"| {label} | " + " | ".join(f"{summary['conditions'][c][key]}{unit}" for c in conds) + " |")

    cats = sorted({k for c in conds for k in summary["by_category"][c]})
    lines += ["", "## Root-cause accuracy by category", "", "| Category | " + " | ".join(names[c] for c in conds) + " |", "|---|" + "---|" * len(conds)]
    for cat in cats:
        lines.append(f"| {cat} | " + " | ".join(f"{summary['by_category'][c].get(cat, 0.0)}%" for c in conds) + " |")
    if summary["errors"]:
        lines += ["", f"_{summary['errors']} model calls failed and are excluded._"]
    return "\n".join(lines) + "\n"


# ───────────────────────────── Main ─────────────────────────────


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--conditions", nargs="+", choices=CONDITIONS, default=list(CONDITIONS))
    ap.add_argument("--split", choices=("dev", "holdout"))
    ap.add_argument("--cases", nargs="+", help="Only run these case ids")
    ap.add_argument("--repeats", type=int, default=1, help="Runs per case (Gemini output varies)")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--judge", action="store_true", help="Also grade root cause with an LLM judge")
    ap.add_argument("--delay", type=float, default=1.0, help="Seconds between calls (rate limits)")
    ap.add_argument("--dry-run", action="store_true", help="Use mock answers, no API calls")
    ap.add_argument("--validate", action="store_true", help="Only validate case files")
    args = ap.parse_args(argv)

    cases = load_cases(args.split, args.cases)
    errors = validate_cases(cases)
    if errors:
        print("Case validation failed:\n  " + "\n  ".join(errors))
        return 1
    print(f"{len(cases)} cases valid.")
    if args.validate:
        return 0
    if not args.dry_run and not os.getenv("GEMINI_API_KEY"):
        print("Set GEMINI_API_KEY (or use --dry-run).")
        return 1

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = RESULTS_DIR / (stamp + ("-dry" if args.dry_run else ""))
    out.mkdir(parents=True, exist_ok=True)
    scores: list[Score] = []

    with (out / "raw.jsonl").open("w", encoding="utf-8") as raw:
        for case in cases:
            for cond in args.conditions:
                for run in range(1, args.repeats + 1):
                    t0 = time.perf_counter()
                    try:
                        if args.dry_run:
                            resp = mock_response(case, cond)
                        else:
                            system, prompt = build_prompt(case, cond)
                            resp = call_model(system, prompt, args.model)
                        s = score_response(case, cond, run, resp)
                        s.latency_s = round(time.perf_counter() - t0, 2)
                        if args.judge and not args.dry_run:
                            s.root_cause_judge = judge_root_cause(case["expected"]["root_cause"], s.root_cause_answer, args.model)
                    except Exception as e:  # keep going; failures are reported
                        resp = {}
                        s = Score(case["id"], cond, run, case["category"], case["split"], ok=False, error=f"{type(e).__name__}: {e}")
                    scores.append(s)
                    raw.write(json.dumps({"score": asdict(s), "response": resp}, ensure_ascii=False) + "\n")
                    mark = "ok " if s.ok and s.root_cause else ("ERR" if not s.ok else "-- ")
                    print(f"[{mark}] {case['id']:<36} {cond:<9} run {run}")
                    if not args.dry_run:
                        time.sleep(args.delay)

    summary = summarize(scores)
    meta = {
        "model": args.model, "cases": len(cases), "split": args.split, "repeats": args.repeats,
        "judge": args.judge, "timestamp": stamp, "dry_run": args.dry_run,
    }
    (out / "summary.json").write_text(json.dumps({"meta": meta, **summary}, indent=2), encoding="utf-8")
    md = to_markdown(summary, meta)
    (out / "summary.md").write_text(md, encoding="utf-8")
    print("\n" + md + f"\nSaved to {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
