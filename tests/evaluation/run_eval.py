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
import csv
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
    "id",
    "title",
    "category",
    "target",
    "difficulty",
    "split",
    "firmware_code",
    "compiler_output",
    "serial_logs",
    "reference_context",
    "expected",
}
REQUIRED_EXPECTED_KEYS = {
    "root_cause",
    "root_cause_keywords",
    "fix",
    "fix_keywords",
    "expected_citation",
}


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
        abstain = bool(exp.get("abstain"))
        if not c["reference_context"] and not abstain:
            errors.append(f"{cid}: needs at least one reference_context excerpt")
        if abstain and not exp.get("needed_info_keywords"):
            errors.append(f"{cid}: abstain case needs needed_info_keywords")
        for r in c["reference_context"]:
            if r.get("page_number") is not None and not isinstance(r["page_number"], int):
                errors.append(f"{cid}: page_number must be int or null")
        titles = {r["title"] for r in c["reference_context"]}
        for t in exp["expected_citation"]:
            if t not in titles:
                errors.append(f"{cid}: expected_citation '{t}' not in reference_context")
        for key in ("root_cause_keywords", "fix_keywords", "needed_info_keywords"):
            for group in exp.get(key, []):
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


# ───────────────────────────── Integrity checks ─────────────────────────────

ANSWER_KEYS = ("root_cause_keywords", "fix_keywords", "needed_info_keywords", "expected_citation")
LEAK_SHINGLE = 5  # words; 4-word overlaps are common technical phrases ("the wi fi driver")


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9_]+(?:\.[a-z0-9_]+)*", text.lower())


def _shingles(text: str, n: int = LEAK_SHINGLE) -> set[str]:
    w = _words(text)
    if 0 < len(w) < n:  # short answers are matched whole
        return {" ".join(w)}
    return {" ".join(w[i : i + n]) for i in range(len(w) - n + 1)}


def case_inputs(case: dict[str, Any]) -> list[str]:
    """The problem evidence every condition receives (identical across conditions)."""
    return [
        case["target"],
        case["firmware_code"],
        case["compiler_output"],
        case["serial_logs"],
        case.get("user_question") or "",
    ]


def leakage_problems(cases: list[dict[str, Any]]) -> list[str]:
    """Check that expected answers / fix hints cannot reach the model, and inputs are identical.

    1. No 5-word sequence from expected.root_cause or expected.fix appears in a retrieved excerpt
       unless it is already part of the problem inputs (code, logs, question).
    2. The full prompt (system + user) of every condition contains neither the expected root cause
       nor the expected fix text, nor any answer-key field name.
    3. All three conditions receive the same problem inputs; only `grounded` adds excerpts, and
       baseline/no_rag user prompts are byte-identical.
    """
    problems: list[str] = []
    for case in cases:
        cid, exp = case["id"], case["expected"]
        answer = _shingles(exp["root_cause"]) | _shingles(exp["fix"])
        inputs = _shingles(" ".join(case_inputs(case)))
        short = [
            " ".join(_words(t)) for t in (exp["root_cause"], exp["fix"]) if len(_words(t)) < LEAK_SHINGLE
        ]
        for i, r in enumerate(case["reference_context"]):
            for field_name in ("snippet", "title", "section"):
                value = str(r.get(field_name) or "")
                hit = (answer & _shingles(value)) - inputs
                hit |= {t for t in short if t and f" {t} " in f" {' '.join(_words(value))} "}
                if hit:
                    problems.append(f"{cid}: excerpt {i} {field_name} repeats expected answer: {sorted(hit)[:3]}")
        prompts = {cond: build_prompt(case, cond) for cond in CONDITIONS}
        for cond, (system, user) in prompts.items():
            text = (system + "\n" + user).lower()
            for key in ("root_cause", "fix"):
                if exp[key].lower() in text:
                    problems.append(f"{cid}/{cond}: prompt contains expected.{key}")
            for key in ANSWER_KEYS:
                if key in text:
                    problems.append(f"{cid}/{cond}: prompt mentions answer key '{key}'")
            for part in case_inputs(case):
                if part and part.strip() not in user:
                    problems.append(f"{cid}/{cond}: prompt is missing part of the case inputs")
                    break
        if prompts["baseline"][1] != prompts["no_rag"][1]:
            problems.append(f"{cid}: baseline and no_rag user prompts differ")
        no_docs = dict(case, reference_context=[])
        if build_prompt(no_docs, "grounded")[1] != prompts["no_rag"][1]:
            problems.append(f"{cid}: grounded prompt differs from no_rag beyond the excerpts")
    return problems


def integrity_problems(cases: list[dict[str, Any]], check_manifest: bool = True) -> list[str]:
    problems: list[str] = []
    if check_manifest:
        sys.path.insert(0, str(EVAL_DIR))
        from dataset_manifest import verify

        problems += verify()
    problems += leakage_problems(cases)
    return problems


# ───────────────────────────── Model calls ─────────────────────────────


def usage_of(resp: Any) -> dict[str, Any]:
    """Token counts and the served model version only; never prompt or answer text."""
    um = getattr(resp, "usage_metadata", None)

    def n(name: str) -> int | None:
        v = getattr(um, name, None) if um is not None else None
        return int(v) if v is not None else None

    return {
        "model_version": getattr(resp, "model_version", None) if resp is not None else None,
        "prompt_tokens": n("prompt_token_count"),
        "output_tokens": n("candidates_token_count"),
        "thought_tokens": n("thoughts_token_count"),
        "total_tokens": n("total_token_count"),
    }


NOT_CONFIRMED = "not independently confirmed"


def served_versions(scores: list[Any], attr: str) -> list[str] | str:
    """Served model versions Google returned (modelVersion); NOT_CONFIRMED when none were returned."""
    found: set[str] = set()
    for sc in scores:
        u = getattr(sc, attr, None)
        if isinstance(u, dict):
            v = u.get("model_version")
            if isinstance(v, str) and v:
                found.add(v)
    return sorted(found) if found else NOT_CONFIRMED


def call_model(system: str, prompt: str, model: str, usage: dict[str, Any] | None = None) -> dict[str, Any]:
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
    if usage is not None:
        usage.update(usage_of(resp))
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


def judge_root_cause(expected: str, answer: str, model: str, usage: dict[str, Any] | None = None) -> bool:
    """Secondary signal only. Use --judge-model to grade with a different model than the one tested."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    resp = client.models.generate_content(
        model=model,
        contents=JUDGE_PROMPT.format(expected=expected, answer=answer),
        config=types.GenerateContentConfig(temperature=0.0),
    )
    if usage is not None:
        usage.update(usage_of(resp))
    return (resp.text or "").strip().upper().startswith("YES")


def mock_response(case: dict[str, Any], condition: str) -> dict[str, Any]:
    """Deterministic fake answers used by --dry-run to exercise the pipeline."""
    exp = case["expected"]
    if exp.get("abstain"):
        return {
            "problem_observed": case["title"],
            "root_cause_summary": exp["root_cause"],
            "confidence_level": "low",
            "likely_causes": [],
            "proposed_fix": exp["fix"],
            "follow_up_required": exp["fix"],
            "datasheet_citations": [],
        }
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
        "likely_causes": [
            {"cause": exp["root_cause"] if good else "wiring", "plausibility": "high"}
        ],
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
    return "\n".join(
        p for p in (resp.get("proposed_fix") or "", resp.get("corrected_code") or "") if p
    )


def _doc_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", name.lower().split("(")[0]).strip()


def doc_matches(cited: str, title: str) -> bool:
    a, b = _doc_key(cited), _doc_key(title)
    return bool(a) and bool(b) and (a in b or b in a)


UNCERTAINTY = re.compile(
    r"insufficient|not enough (?:information|evidence)|cannot (?:be )?(?:determin|identif|confirm)|"
    r"need(?:s|ed)? more|more information|unclear|unknown|not provided|without (?:the|a|more)",
    re.IGNORECASE,
)

# Specific, checkable technical tokens: hex values, pin numbers, register/macro-style identifiers.
SPECIFIC_TOKEN = re.compile(
    r"\b0x[0-9a-f]+\b|\bGPIO_?(?:NUM_)?\d+\b|\b(?:pin|io)\s?\d+\b|\b[A-Z][A-Z0-9]*_[A-Z0-9_]{2,}\b",
    re.IGNORECASE,
)


def claim_text(resp: dict[str, Any]) -> str:
    """Prose claims (not corrected_code, which may legitimately introduce new identifiers)."""
    parts = [
        resp.get("root_cause_summary") or "",
        resp.get("proposed_fix") or "",
        resp.get("grounded_summary") or "",
    ]
    parts += [
        str(c.get("cause", "")) for c in (resp.get("likely_causes") or []) if isinstance(c, dict)
    ]
    return "\n".join(p for p in parts if p)


def evidence_text(case: dict[str, Any], condition: str) -> str:
    parts = [
        case["firmware_code"],
        case["compiler_output"],
        case["serial_logs"],
        case.get("user_question") or "",
    ]
    if condition == "grounded":
        parts += [r["snippet"] for r in case["reference_context"]]
    return "\n".join(parts).lower()


def _norm_token(tok: str) -> str:
    return re.sub(r"\s+", "", tok.lower())


def unsupported_claims(case: dict[str, Any], condition: str, resp: dict[str, Any]) -> list[str]:
    """Specific tokens in the answer's prose found neither in the evidence nor in the reference answer.

    Deterministic and deliberately conservative: a flagged token is not proof of a wrong claim,
    only of a claim that cannot be traced to the inputs. Flags go to the human verification sheet.
    """
    evid = re.sub(r"\s+", "", evidence_text(case, condition))
    exp = case["expected"]
    # Tokens in the reference answer are verified facts for this case, so they are not flagged.
    reference = re.sub(r"\s+", "", (exp["root_cause"] + "\n" + exp["fix"]).lower())
    allowed = {_norm_token(t) for t in exp.get("allowed_terms", [])}
    flagged: list[str] = []
    for m in SPECIFIC_TOKEN.finditer(claim_text(resp)):
        tok = _norm_token(m.group(0))
        if tok in allowed or tok in evid or tok in reference:
            continue
        if re.fullmatch(r"(?:pin|io)\d+", tok) and re.sub(r"\D", "", tok) in evid:
            continue
        if tok not in flagged:
            flagged.append(tok)
    return flagged


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
    citation_page_correct: bool | None = None
    unsupported_claims: list[str] = field(default_factory=list)
    abstain_case: bool = False
    abstained: bool = False
    asked_needed_info: bool = False
    confidence: str | None = None
    confidently_wrong: bool = False
    latency_s: float = 0.0
    usage: dict[str, Any] = field(default_factory=dict)
    judge_usage: dict[str, Any] = field(default_factory=dict)
    root_cause_answer: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def root_cause(self) -> bool:
        """Primary metric: deterministic keyword rubric. The LLM judge is reported separately."""
        return self.root_cause_keyword


def score_response(case: dict[str, Any], condition: str, run: int, resp: dict[str, Any]) -> Score:
    exp = case["expected"]
    s = Score(
        case_id=case["id"],
        condition=condition,
        run=run,
        category=case["category"],
        split=case["split"],
    )
    rc = root_cause_text(resp)
    s.root_cause_answer = rc
    s.confidence = resp.get("confidence_level")
    s.unsupported_claims = unsupported_claims(case, condition, resp)
    cites_full = [c for c in (resp.get("datasheet_citations") or []) if c]

    if exp.get("abstain"):
        s.abstain_case = True
        full = "\n".join([rc, resp.get("follow_up_required") or "", resp.get("proposed_fix") or ""])
        s.abstained = s.confidence != "high" and bool(UNCERTAINTY.search(full))
        s.asked_needed_info = keywords_match(full, exp["needed_info_keywords"])
        s.root_cause_keyword = s.abstained and s.asked_needed_info
        s.fix_correct = s.asked_needed_info
        s.cites_any = bool(cites_full)
        s.fabricated_citation = s.cites_any  # no documents were provided for these cases
        s.confidently_wrong = s.confidence == "high"
        return s

    rc_kw = keywords_match(rc, exp["root_cause_keywords"])
    s.root_cause_keyword = rc_kw
    s.fix_correct = keywords_match(fix_text(resp), exp["fix_keywords"])

    cites = [c.get("document_name", "") for c in (resp.get("datasheet_citations") or []) if c]
    provided = [r["title"] for r in case["reference_context"]] if condition == "grounded" else []
    s.cites_any = bool(cites)
    s.citation_correct = (
        any(doc_matches(c, t) for c in cites for t in exp["expected_citation"])
        and condition == "grounded"
    )
    # A citation is fabricated when it names a document that was never given to the model.
    s.fabricated_citation = any(not any(doc_matches(c, t) for t in provided) for c in cites)
    # Page-level check, only where the provided excerpt has a page number.
    exp_pages = {
        r.get("page_number")
        for r in case["reference_context"]
        if r["title"] in exp["expected_citation"] and r.get("page_number") is not None
    }
    if condition == "grounded" and exp_pages:
        s.citation_page_correct = any(
            doc_matches(c.get("document_name", ""), t) and c.get("page_number") in exp_pages
            for c in cites_full
            for t in exp["expected_citation"]
        )

    s.confidently_wrong = (not s.root_cause_keyword) and s.confidence == "high"
    return s


# ───────────────────────────── Reporting ─────────────────────────────


def pct(values: list[bool]) -> float:
    return round(100.0 * sum(values) / len(values), 1) if values else 0.0


def _metrics(ss: list[Score]) -> dict[str, Any]:
    diag = [s for s in ss if not s.abstain_case]
    abst = [s for s in ss if s.abstain_case]
    paged = [s.citation_page_correct for s in diag if s.citation_page_correct is not None]
    judged = [s.root_cause_judge for s in diag if s.root_cause_judge is not None]
    return {
        "n": len(ss),
        "root_cause_accuracy": pct([s.root_cause_keyword for s in diag]),
        "root_cause_judge_agreement": pct([bool(j) for j in judged]) if judged else None,
        "fix_accuracy": pct([s.fix_correct for s in diag]),
        "citation_accuracy": pct([s.citation_correct for s in diag]),
        "citation_page_accuracy": pct([bool(p) for p in paged]) if paged else None,
        "fabricated_citation_rate": pct([s.fabricated_citation for s in ss]),
        "unsupported_claim_rate": pct([bool(s.unsupported_claims) for s in ss]),
        "mean_unsupported_claims": round(
            statistics.mean([len(s.unsupported_claims) for s in ss]), 2
        )
        if ss
        else 0.0,
        "confidently_wrong_rate": pct([s.confidently_wrong for s in ss]),
        "abstention_accuracy": pct([s.root_cause_keyword for s in abst]) if abst else None,
        "holdout_root_cause_accuracy": pct(
            [s.root_cause_keyword for s in diag if s.split == "holdout"]
        ),
        "median_latency_s": round(statistics.median([s.latency_s for s in ss]), 2) if ss else 0.0,
    }


def _spread(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"mean": None, "std": None, "min": None, "max": None}
    return {
        "mean": round(statistics.mean(values), 1),
        "std": round(statistics.stdev(values), 1) if len(values) > 1 else 0.0,
        "min": round(min(values), 1),
        "max": round(max(values), 1),
    }


SPREAD_KEYS = (
    "root_cause_accuracy",
    "fix_accuracy",
    "citation_accuracy",
    "fabricated_citation_rate",
    "unsupported_claim_rate",
    "confidently_wrong_rate",
    "abstention_accuracy",
    "holdout_root_cause_accuracy",
)


def summarize(scores: list[Score]) -> dict[str, Any]:
    by_cond: dict[str, list[Score]] = defaultdict(list)
    for s in scores:
        if s.ok:
            by_cond[s.condition].append(s)

    summary: dict[str, Any] = {
        "conditions": {},
        "by_category": {},
        "errors": sum(not s.ok for s in scores),
    }
    for cond, ss in by_cond.items():
        summary["conditions"][cond] = _metrics(ss)
        runs: dict[int, list[Score]] = defaultdict(list)
        for s in ss:
            runs[s.run].append(s)
        per_run = {r: _metrics(v) for r, v in sorted(runs.items())}
        summary.setdefault("per_run", {})[cond] = per_run
        summary.setdefault("spread", {})[cond] = {
            k: _spread([m[k] for m in per_run.values() if m[k] is not None]) for k in SPREAD_KEYS
        }
        cats: dict[str, list[Score]] = defaultdict(list)
        for s in ss:
            cats[s.category].append(s)
        summary["by_category"][cond] = {
            k: pct([s.root_cause_keyword for s in v]) for k, v in sorted(cats.items())
        }
    return summary


def to_markdown(summary: dict[str, Any], meta: dict[str, Any]) -> str:
    conds = [c for c in CONDITIONS if c in summary["conditions"]]
    names = {
        "baseline": "Plain Gemini",
        "no_rag": "Ours without RAG",
        "grounded": "Ours (RAG grounded)",
    }
    lines = [
        "# Evaluation results",
        "",
        f"- Model: `{meta['model']}`  ",
        f"- Cases: {meta['cases']} ({meta['split'] or 'all splits'}), repeats: {meta['repeats']}, "
        f"judge: {meta['judge_model'] or 'off'}  ",
        f"- Run: {meta['timestamp']}{'  (DRY RUN, mock answers)' if meta['dry_run'] else ''}",
        "",
        "| Metric | " + " | ".join(names[c] for c in conds) + " |",
        "|---|" + "---|" * len(conds),
    ]
    rows = [
        ("Root-cause accuracy (keyword rubric)", "root_cause_accuracy", "%"),
        ("Root-cause accuracy (holdout only)", "holdout_root_cause_accuracy", "%"),
        ("LLM-judge agreement (secondary)", "root_cause_judge_agreement", "%"),
        ("Fix accuracy", "fix_accuracy", "%"),
        ("Correct document cited", "citation_accuracy", "%"),
        ("Correct page cited", "citation_page_accuracy", "%"),
        ("Unverifiable/fabricated citations", "fabricated_citation_rate", "%"),
        ("Answers with untraceable specifics", "unsupported_claim_rate", "%"),
        ("Correct abstention (insufficient evidence)", "abstention_accuracy", "%"),
        ("Confidently wrong", "confidently_wrong_rate", "%"),
        ("Median latency", "median_latency_s", " s"),
    ]

    def cell(v: Any, unit: str) -> str:
        return "n/a" if v is None else f"{v}{unit}"

    for label, key, unit in rows:
        lines.append(
            f"| {label} | "
            + " | ".join(cell(summary["conditions"][c][key], unit) for c in conds)
            + " |"
        )

    if meta["repeats"] > 1:
        lines += [
            "",
            "## Spread across repeats (mean ± std, min–max)",
            "",
            "| Metric | " + " | ".join(names[c] for c in conds) + " |",
            "|---|" + "---|" * len(conds),
        ]
        for key in SPREAD_KEYS:
            cells = []
            for c in conds:
                sp = summary["spread"][c][key]
                cells.append(
                    "n/a"
                    if sp["mean"] is None
                    else f"{sp['mean']} ± {sp['std']} ({sp['min']}–{sp['max']})"
                )
            lines.append(f"| {key} | " + " | ".join(cells) + " |")
        lines += [
            "",
            "## Each repeat",
            "",
            "| Condition | Run | Root cause | Fix | Citation | Abstention |",
            "|---|---|---|---|---|---|",
        ]
        for c in conds:
            for r, m in summary["per_run"][c].items():
                lines.append(
                    f"| {names[c]} | {r} | {m['root_cause_accuracy']}% | {m['fix_accuracy']}% | "
                    f"{m['citation_accuracy']}% | {cell(m['abstention_accuracy'], '%')} |"
                )

    cats = sorted({k for c in conds for k in summary["by_category"][c]})
    lines += [
        "",
        "## Root-cause accuracy by category",
        "",
        "| Category | " + " | ".join(names[c] for c in conds) + " |",
        "|---|" + "---|" * len(conds),
    ]
    for cat in cats:
        lines.append(
            f"| {cat} | "
            + " | ".join(f"{summary['by_category'][c].get(cat, 0.0)}%" for c in conds)
            + " |"
        )
    if summary["errors"]:
        lines += ["", f"_{summary['errors']} model calls failed and are excluded._"]
    return "\n".join(lines) + "\n"


def write_human_sheet(
    path: Path, cases: list[dict[str, Any]], rows: list[tuple[Score, dict[str, Any]]]
) -> None:
    """CSV for manual verification of automatic verdicts (the reported numbers stay automatic)."""
    by_id = {c["id"]: c for c in cases}
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "case_id",
                "split",
                "condition",
                "run",
                "expected_root_cause",
                "answer_root_cause",
                "answer_fix",
                "auto_root_cause",
                "judge_root_cause",
                "auto_fix",
                "auto_citation",
                "unsupported_tokens",
                "human_root_cause_ok (Y/N)",
                "human_fix_ok (Y/N)",
                "human_unsupported_claim (Y/N)",
                "human_notes",
            ]
        )
        for s, resp in rows:
            if not s.ok:
                continue
            w.writerow(
                [
                    s.case_id,
                    s.split,
                    s.condition,
                    s.run,
                    by_id[s.case_id]["expected"]["root_cause"],
                    s.root_cause_answer,
                    fix_text(resp)[:2000],
                    s.root_cause_keyword,
                    s.root_cause_judge,
                    s.fix_correct,
                    s.citation_correct,
                    " ".join(s.unsupported_claims),
                    "",
                    "",
                    "",
                    "",
                ]
            )


# ───────────────────────────── Main ─────────────────────────────


def _manifest_hashes() -> dict[str, str] | None:
    path = EVAL_DIR / "DATASET_MANIFEST.json"
    if not path.exists():
        return None
    splits = json.loads(path.read_text(encoding="utf-8"))["splits"]
    return {k: v["manifest_sha256"] for k, v in splits.items()}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--conditions", nargs="+", choices=CONDITIONS, default=list(CONDITIONS))
    ap.add_argument("--split", choices=("dev", "holdout"))
    ap.add_argument("--cases", nargs="+", help="Only run these case ids")
    ap.add_argument("--repeats", type=int, default=1, help="Runs per case (Gemini output varies)")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument(
        "--model-version",
        default=os.getenv("EVAL_MODEL_VERSION", "3.5-flash-05-2026"),
        help="Version reported by GetModel for --model (verified 2026-11-05); recorded, not sent",
    )
    ap.add_argument("--judge-model-version", default=os.getenv("EVAL_JUDGE_MODEL_VERSION"))
    ap.add_argument(
        "--judge", action="store_true", help="Also grade root cause with an LLM judge (secondary)"
    )
    ap.add_argument(
        "--judge-model", help="Judge model; should differ from --model to reduce self-grading bias"
    )
    ap.add_argument("--delay", type=float, default=1.0, help="Seconds between calls (rate limits)")
    ap.add_argument("--dry-run", action="store_true", help="Use mock answers, no API calls")
    ap.add_argument("--validate", action="store_true", help="Only validate case files")
    ap.add_argument(
        "--no-manifest-check",
        action="store_true",
        help="Skip the frozen-dataset check (only while editing cases; never for reported runs)",
    )
    args = ap.parse_args(argv)

    cases = load_cases(args.split, args.cases)
    errors = validate_cases(cases)
    if errors:
        print("Case validation failed:\n  " + "\n  ".join(errors))
        return 1
    print(f"{len(cases)} cases valid.")
    integrity = integrity_problems(load_cases(), check_manifest=not args.no_manifest_check)
    if integrity:
        print("Integrity check failed (frozen datasets / leakage):\n  " + "\n  ".join(integrity))
        return 1
    print(
        "Integrity OK: "
        + ("dev and holdout match DATASET_MANIFEST.json; " if not args.no_manifest_check else "")
        + "no answer leakage; identical inputs across conditions."
    )
    if args.validate:
        return 0
    if not args.dry_run and not os.getenv("GEMINI_API_KEY"):
        print("Set GEMINI_API_KEY (or use --dry-run).")
        return 1

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = RESULTS_DIR / (stamp + ("-dry" if args.dry_run else ""))
    out.mkdir(parents=True, exist_ok=True)
    scores: list[Score] = []
    sheet_rows: list[tuple[Score, dict[str, Any]]] = []
    judge_model = (args.judge_model or args.model) if args.judge else None
    if args.judge and judge_model == args.model:
        print(
            "WARNING: judge model equals the tested model; judge results are reported as secondary only."
        )

    with (out / "raw.jsonl").open("w", encoding="utf-8") as raw:
        for case in cases:
            for cond in args.conditions:
                for run in range(1, args.repeats + 1):
                    t0 = time.perf_counter()
                    usage: dict[str, Any] = {}
                    try:
                        if args.dry_run:
                            resp = mock_response(case, cond)
                        else:
                            system, prompt = build_prompt(case, cond)
                            resp = call_model(system, prompt, args.model, usage)
                        s = score_response(case, cond, run, resp)
                        s.usage = usage
                        s.latency_s = round(time.perf_counter() - t0, 2)
                        if args.judge and not args.dry_run:
                            if not case["expected"].get("abstain"):
                                s.root_cause_judge = judge_root_cause(
                                    case["expected"]["root_cause"],
                                    s.root_cause_answer,
                                    judge_model or args.model,
                                    s.judge_usage,
                                )
                    except Exception as e:  # keep going; failures are reported
                        resp = {}
                        s = Score(
                            case["id"],
                            cond,
                            run,
                            case["category"],
                            case["split"],
                            ok=False,
                            error=f"{type(e).__name__}: {e}",
                        )
                    scores.append(s)
                    sheet_rows.append((s, resp))
                    raw.write(
                        json.dumps({"score": asdict(s), "response": resp}, ensure_ascii=False)
                        + "\n"
                    )
                    mark = "ok " if s.ok and s.root_cause else ("ERR" if not s.ok else "-- ")
                    print(f"[{mark}] {case['id']:<36} {cond:<9} run {run}")
                    if not args.dry_run:
                        time.sleep(args.delay)

    summary = summarize(scores)
    meta = {
        "model": args.model,
        "requested_model": args.model,
        "requested_model_version_getmodel": args.model_version,
        "judge_model_version_getmodel": args.judge_model_version,
        # Served model: only what Google returns in each response (modelVersion). Empty means
        # routing is not independently confirmed.
        "served_model_versions": served_versions(scores, "usage"),
        "served_judge_model_versions": served_versions(scores, "judge_usage"),
        "cases": len(cases),
        "split": args.split,
        "repeats": args.repeats,
        "judge": args.judge,
        "judge_model": judge_model,
        "timestamp": stamp,
        "dry_run": args.dry_run,
        "dataset_manifest": _manifest_hashes(),
    }
    write_human_sheet(out / "human_verification.csv", cases, sheet_rows)
    (out / "summary.json").write_text(
        json.dumps({"meta": meta, **summary}, indent=2), encoding="utf-8"
    )
    md = to_markdown(summary, meta)
    (out / "summary.md").write_text(md, encoding="utf-8")
    print("\n" + md + f"\nSaved to {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
