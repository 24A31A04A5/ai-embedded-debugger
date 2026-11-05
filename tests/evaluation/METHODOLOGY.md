# Evaluation methodology (Phase 8)

Status: framework validated offline (Phase 8.1). No Gemini run has been made yet, so this repo
contains no measured results. Numbers from `--dry-run` are mock answers and must never be quoted.

## Dataset
- 26 hand-written cases in `cases/*.json`, generated from `build_cases.py` (the source of truth).
- Platforms: ESP32 (13), STM32 (9), Arduino AVR (4). Categories: gpio, i2c, spi, uart, adc,
  interrupts, memory, runtime, compiler, linker, logic.
- Split: 18 `dev`, 8 `holdout`. Dev cases may be used while tuning prompts and retrieval.
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
- Root cause (primary): deterministic keyword groups; every group must match (regex, case-insensitive).
- Root cause (secondary, optional `--judge`): LLM judge, temperature 0, YES/NO against the reference.
  Caveat: the judge is the same model family being graded; it is reported beside, never instead
  of, the keyword score, and verdicts are stored in raw.jsonl for manual spot checks.
- Fix accuracy: keyword groups on proposed_fix + corrected_code.
- Citation accuracy (grounded only): the answer cites the expected document.
- Fabricated citation rate: the answer cites a document that was not provided to the model.
  For baseline/no_rag every citation is unverifiable by construction.
- Confidently wrong rate: root cause wrong while confidence_level == "high".
- Median latency per condition.

## Repeats and reproducibility
- `--repeats N` runs each case N times (Gemini output varies); results go to
  `results/<timestamp>/` as raw.jsonl, summary.json, summary.md with the model name and settings.
- CI (`apps/api/tests/test_evaluation_cases.py`) validates cases and scoring offline and never
  calls Gemini.

## Known gaps (to close before results are published)
1. Reference excerpts are paraphrases and lack page numbers; several hint at the fix. They must
   be replaced with verbatim text plus page (PDF) or section URL (HTML docs).
2. Citation accuracy checks the document title only, not the page/section.
3. No insufficient-evidence cases, so "I don't know" handling is not measured yet.
4. No unsupported-claims metric.
5. Summary does not yet report spread (min/max) across repeats.
6. Model name: code uses `gemini-3.5-flash`; the homepage says Gemini 2.5 Flash. Confirm before the run.
7. Three holdout cases have evidence that doesn't match real toolchain output
   (millis overflow, UART HAL module, HardFault fault-address registers); fixing them needs approval.
