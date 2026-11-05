# Evaluation methodology (Phase 8)

Status: framework validated offline (Phase 8.1). No Gemini run has been made yet, so this repo
contains no measured results. Numbers from `--dry-run` are mock answers and must never be quoted.

## Dataset
- 30 hand-written cases in `cases/*.json`, generated from `build_cases.py` (the source of truth):
  26 diagnostic cases (18 dev / 8 holdout) + 4 insufficient-evidence cases (2 dev / 2 holdout).
- Platforms: ESP32, STM32, Arduino AVR. Categories: gpio, i2c, spi, uart, adc,
  interrupts, memory, runtime, compiler, linker, logic, insufficient-evidence.
- Every case change is logged in `CORRECTIONS.md`; originals are in `cases_original/`.
- Reference excerpts for dev cases are verbatim from official documents with document, revision,
  page (printed page or PDF index) or URL, and section (`reference_sources.json`). Holdout excerpts
  stay original until approved (`HOLDOUT_PROPOSALS.md`).
- Split: 20 `dev`, 10 `holdout`. Dev cases may be used while tuning prompts and retrieval.
  Holdout cases are never used for tuning; they are reported separately as the honest number.
- Each case has: firmware code, compiler output and/or serial log, optional user question,
  reference excerpts (stand-ins for RAG retrieval), and the expected root cause, fix,
  citation and line.

## Conditions (same model, same JSON output schema, temperature 0.2)
1. `baseline` — plain Gemini: generic system prompt, no datasheet excerpts.
2. `no_rag` — our embedded system instruction (`app/ai/gemini.py`), no excerpts (ablation).
3. `grounded` — full pipeline prompt: system instruction + excerpts passed through
   `AssembledDebugContext`, exactly as the API builds it.

## Scoring
- Root cause (primary): deterministic keyword rubric; every group must match (regex, case-insensitive).
- Root cause (secondary, optional `--judge --judge-model X`): LLM judge, temperature 0, YES/NO against
  the reference. Reported as "judge agreement" beside, never instead of, the rubric. Use a different
  model from the one tested; the runner warns when they are the same.
- Human verification: every run writes `human_verification.csv` (answer, automatic verdicts, flagged
  tokens, blank Y/N columns) for manual checking of a sample or all rows.
- Abstention (insufficient-evidence cases): correct when confidence is not "high", the answer states
  the evidence is insufficient, and it asks for at least one specific missing item (`needed_info_keywords`).
  Confidence "high" on these cases counts as confidently wrong.
- Unsupported claims: specific tokens in the answer's prose (hex values, GPIO/pin numbers,
  macro/register-style identifiers) that appear neither in the evidence given to the model nor in the
  reference answer. Deterministic and conservative: a flag means "untraceable", checked by a human.
- Citation page accuracy: when the expected excerpt has a page number, the cited page must match.
- Fix accuracy: keyword groups on proposed_fix + corrected_code.
- Citation accuracy (grounded only): the answer cites the expected document.
- Fabricated citation rate: the answer cites a document that was not provided to the model.
  For baseline/no_rag every citation is unverifiable by construction.
- Confidently wrong rate: root cause wrong while confidence_level == "high".
- Median latency per condition.

## Repeats and reproducibility
- `--repeats N` runs each case N times (Gemini output varies). The summary reports every repeat
  separately plus mean, standard deviation, min and max per metric. Results go to
  `results/<timestamp>/` (raw.jsonl, summary.json, summary.md, human_verification.csv).
- CI (`apps/api/tests/test_evaluation_cases.py`) validates cases and scoring offline and never
  calls Gemini.

## Remaining gaps
1. Holdout corrections H1–H4 await approval (`HOLDOUT_PROPOSALS.md`).
2. Model name: `apps/api/app/ai/gemini.py` and `run_eval.py` use `gemini-3.5-flash`; the homepage says
   "Gemini 2.5 Flash". Not changed. Must be confirmed with ListModels (needs the key) before the run.
3. Unsupported-claims and abstention checks are rubric heuristics; spot-check with the human sheet.
4. MPU-6050 excerpt was checked against Rev 3.1 (SparkFun mirror); the official Rev 3.4 PDF did not download.
