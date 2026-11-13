"""Spot-check the unsupported-claims and abstention detectors against hand labels.

Offline only (no model calls). Usage, from the repo root:
    python tests/evaluation/spot_checks/detector_spot_check.py
Writes spot_checks/detector_spot_check.md and prints the same report.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
EVAL_DIR = HERE.parent


def _runner() -> Any:
    spec = importlib.util.spec_from_file_location("run_eval", EVAL_DIR / "run_eval.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["run_eval"] = mod
    spec.loader.exec_module(mod)
    return mod


def _norm(t: str) -> str:
    return re.sub(r"\s+", "", t.lower())


def _prf(tp: int, fp: int, fn: int) -> tuple[float, float]:
    p = tp / (tp + fp) if tp + fp else 1.0
    r = tp / (tp + fn) if tp + fn else 1.0
    return round(p, 2), round(r, 2)


def run() -> dict[str, Any]:
    rv = _runner()
    labels = json.loads((HERE / "detector_labels.json").read_text(encoding="utf-8"))
    cases = {c["id"]: c for c in rv.load_cases()}

    # Unsupported claims: token level vs gold "untraceable"; also how many "wrong" claims get flagged.
    tp = fp = fn = 0
    wrong_total = wrong_flagged = 0
    u_rows = []
    for item in labels["unsupported_claims"]:
        resp = {"root_cause_summary": item["prose"]}
        flagged = {
            _norm(t) for t in rv.unsupported_claims(cases[item["case"]], item["condition"], resp)
        }
        gold = {_norm(t) for t in item["gold_untraceable"]}
        wrong = {_norm(t) for t in item["gold_wrong"]}
        tp += len(flagged & gold)
        fp += len(flagged - gold)
        fn += len(gold - flagged)
        wrong_total += len(wrong)
        wrong_flagged += len(wrong & flagged)
        u_rows.append(
            {
                "id": item["id"],
                "flagged": sorted(flagged),
                "gold": sorted(gold),
                "missed": sorted(gold - flagged),
                "false_flags": sorted(flagged - gold),
                "agree": flagged == gold,
            }
        )
    up, ur = _prf(tp, fp, fn)

    # Abstention: item level vs gold "correct abstention".
    atp = afp = afn = atn = 0
    a_rows = []
    for item in labels["abstention"]:
        case = cases[item["case"]]
        resp = {
            "root_cause_summary": item["summary"],
            "confidence_level": item["confidence"],
            "follow_up_required": item["follow_up"],
            "likely_causes": [],
            "proposed_fix": "",
            "datasheet_citations": [],
        }
        s = rv.score_response(case, "grounded", 1, resp)
        pred = bool(s.root_cause_keyword)  # abstained AND asked for needed info
        gold = bool(item["gold_correct_abstention"])
        atp += pred and gold
        afp += pred and not gold
        afn += (not pred) and gold
        atn += (not pred) and (not gold)
        a_rows.append({"id": item["id"], "predicted": pred, "gold": gold, "agree": pred == gold})
    ap, ar = _prf(atp, afp, afn)
    n = len(a_rows)

    return {
        "unsupported_claims": {
            "items": len(u_rows),
            "item_agreement": sum(r["agree"] for r in u_rows),
            "token_tp": tp,
            "token_fp": fp,
            "token_fn": fn,
            "precision": up,
            "recall": ur,
            "wrong_claims": wrong_total,
            "wrong_claims_flagged": wrong_flagged,
            "rows": u_rows,
        },
        "abstention": {
            "items": n,
            "agreement": round((atp + atn) / n, 2),
            "tp": atp,
            "fp": afp,
            "fn": afn,
            "tn": atn,
            "precision": ap,
            "recall": ar,
            "rows": a_rows,
        },
    }


def to_markdown(r: dict[str, Any]) -> str:
    u, a = r["unsupported_claims"], r["abstention"]
    lines = [
        "# Detector spot check (hand-labelled synthetic answers, no model calls)",
        "",
        "Labels: `detector_labels.json` (written by the assistant, pending human confirmation).",
        "",
        "## Unsupported-claims detector (token level, gold = untraceable claim)",
        f"- Items: {u['items']}, exact agreement on {u['item_agreement']}/{u['items']}",
        f"- TP {u['token_tp']}, FP {u['token_fp']}, FN {u['token_fn']}: "
        f"precision {u['precision']}, recall {u['recall']}",
        f"- Factually wrong claims flagged: {u['wrong_claims_flagged']}/{u['wrong_claims']}",
        "",
        "| Item | Flagged | Gold | Missed | False flags |",
        "|---|---|---|---|---|",
    ]
    for row in u["rows"]:
        if not row["agree"]:
            lines.append(
                f"| {row['id']} | {', '.join(row['flagged']) or '-'} | {', '.join(row['gold']) or '-'} | "
                f"{', '.join(row['missed']) or '-'} | {', '.join(row['false_flags']) or '-'} |"
            )
    lines += [
        "",
        "## Abstention detector (item level, gold = correct abstention)",
        f"- Items: {a['items']}, agreement {a['agreement']}",
        f"- TP {a['tp']}, FP {a['fp']}, FN {a['fn']}, TN {a['tn']}: "
        f"precision {a['precision']}, recall {a['recall']}",
        "- Disagreements: "
        + (
            ", ".join(
                f"{x['id']} (pred {x['predicted']}, gold {x['gold']})"
                for x in a["rows"]
                if not x["agree"]
            )
            or "none"
        ),
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    res = run()
    md = to_markdown(res)
    (HERE / "detector_spot_check.md").write_text(md, encoding="utf-8")
    print(md)
