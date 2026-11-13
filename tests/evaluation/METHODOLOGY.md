# Evaluation methodology (Phase 8)

Status: framework validated offline (Phase 8.1, prerequisites 2026-11-05). No Gemini run has been made yet, so this repo
contains no measured results. Numbers from `--dry-run` are mock answers and must never be quoted.

## Dataset
- 30 hand-written cases in `cases/*.json`, generated from `build_cases.py` (the source of truth):
  26 diagnostic cases (18 dev / 8 holdout) + 4 insufficient-evidence cases (2 dev / 2 holdout).
- Platforms: ESP32, STM32, Arduino AVR. Categories: gpio, i2c, spi, uart, adc,
  interrupts, memory, runtime, compiler, linker, logic, insufficient-evidence.
- Every case change is logged in `CORRECTIONS.md`; originals are in `cases_original/`.
- Reference excerpts are verbatim from official documents with document, revision, page (printed
  page or PDF index) or URL, and section (`reference_sources.json`): all dev excerpts, and the holdout
  excerpts verified verbatim (H4). Two holdout excerpts remain paraphrases and are flagged
  (esp32-brownout-wifi, stm32-missing-volatile; see `CORRECTIONS.md`).
- Frozen: `DATASET_MANIFEST.json` holds a SHA-256 per case file and one manifest hash per split
  (dev and holdout hashed separately; CRLF normalised). `run_eval.py` refuses to run when either
  split differs, and every run records both split hashes in `summary.json`.
- Split: 20 `dev`, 10 `holdout`. Dev cases may be used while tuning prompts and retrieval.
  Holdout cases are never used for tuning; they are reported separately as the honest number.
- Each case has: firmware code, compiler output and/or serial log, optional user question,
  reference excerpts (stand-ins for RAG retrieval), and the expected root cause, fix,
  citation and line.

## Conditions (same model, same JSON output schema, temperature 0.2, identical case inputs)
1. `baseline` — plain Gemini: generic system prompt, no datasheet excerpts.
2. `no_rag` — our embedded system instruction (`app/ai/gemini.py`), no excerpts (ablation).
3. `grounded` — full pipeline prompt: system instruction + excerpts passed through
   `AssembledDebugContext`, exactly as the API builds it.

## Input parity and leakage control (automated, runs before every evaluation and in CI)
- All three conditions receive the same problem inputs (target, code, compiler output, serial log,
  question). baseline and no_rag user prompts are byte-identical; the grounded prompt equals the
  no_rag prompt plus the excerpt block. baseline differs only in its system prompt.
- No 5-word sequence of the expected root cause or fix (or the whole text, for answers under five
  words) may appear in an excerpt's snippet, title or section unless it is already in the problem
  inputs. No prompt may contain the expected root cause or fix text, or any answer-key field name.
- `apps/api/tests/test_evaluation_integrity.py` checks this on the real cases and proves the check
  fires on planted leaks.
- Caveat: verbatim documentation can legitimately contain the keywords the rubric looks for (e.g.
  "GPIO pins 34-39 are input-only"). That is the evidence grounding is meant to supply, not leakage,
  but it means part of the grounded gain measures whether the model uses the evidence. The
  excerpt text alone satisfies the root-cause keywords in 12 of 26 diagnostic
  cases and the fix keywords in 7 (measured 2026-11-05).

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

## Detector spot check (2026-11-05, synthetic answers, no model calls)
`spot_checks/detector_labels.json` holds 36 hand-labelled synthetic answers (20 for unsupported
claims, 16 for abstention); `spot_checks/detector_spot_check.py` scores the detectors against them.
The answers were written to probe known edge cases, so the numbers describe failure modes rather
than the rate expected on real Gemini output.
- Unsupported claims (token level): precision 1.0, recall 0.76 (TP 16, FP 0, FN 5); 6 of 7
  factually wrong claims flagged. Misses: spaced pin names ("GPIO 35"), pin/AF names (PA2, AF7) not
  covered by the pattern, and a token that appears in the evidence for a different reason (0x68).
  A flag means "untraceable", not "wrong": 10 of 16 flags were correct but unsupported facts.
- Abstention (item level): agreement 0.62, precision 0.67, recall 0.50 (TP 4, FP 2, FN 4, TN 6).
  Misses: "I can't tell", "hard to say", "several possible causes", and an answer that asks to
  decode the backtrace without uncertainty words. False positives: "without a pull-down" and
  "more information is not needed" match the uncertainty pattern.
- Consequence: abstention results are hand-labelled for every run (4 cases × conditions × repeats);
  the detector is only a first pass. Proposed detector fixes are listed under Remaining gaps and are
  NOT applied (they would change the scoring rules, which needs approval).

## Repeats and reproducibility
- `--repeats N` runs each case N times (Gemini output varies). The summary reports every repeat
  separately plus mean, standard deviation, min and max per metric. Results go to
  `results/<timestamp>/` (raw.jsonl, summary.json, summary.md, human_verification.csv).
- CI (`apps/api/tests/test_evaluation_cases.py`) validates cases and scoring offline and never
  calls Gemini.

## Remaining gaps
1. Two holdout excerpts are unverified paraphrases (esp32-brownout-wifi, stm32-missing-volatile).
2. Model name: `apps/api/app/ai/gemini.py` and `run_eval.py` use `gemini-3.5-flash`; the homepage says
   "Gemini 2.5 Flash". Not changed. ListModels confirmation pending (see the Phase 8 report).
3. Proposed (not applied) detector fixes: widen the uncertainty pattern ("can't tell", "hard to say",
   "several possible causes", "not visible"), drop the bare "without a/the" alternative, ignore
   negated phrases ("is not needed"), and accept spaced pin names / port pins (PA2, AF7).
4. MPU-6050 excerpt was checked against Rev 3.1 (SparkFun mirror); the official Rev 3.4 PDF did not download.
