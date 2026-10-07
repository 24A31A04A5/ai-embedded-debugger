# AI Evaluation Harness

Measures how well the AI Embedded Debugger diagnoses real embedded bugs, and whether
our grounding actually helps compared with plain Gemini (SRS §19, Phase 8).

## What is in here

| Path | Purpose |
|---|---|
| `build_cases.py` | Source of truth for all cases. Edit here, then regenerate the JSON. |
| `cases/*.json` | 26 cases: ESP32, STM32, Arduino and FreeRTOS. 18 `dev`, 8 `holdout`. |
| `run_eval.py` | Runs every case under each condition, scores it and writes tables. |
| `results/<timestamp>/` | `raw.jsonl` (every answer), `summary.json`, `summary.md` (report-ready). |

Categories covered: GPIO, I2C, UART, SPI, ADC, interrupts, stack overflow, Guru Meditation /
HardFault memory errors, watchdog and brownout, compiler cascades, linker errors, type bugs.

## Conditions compared

All three use the same model, temperature 0.2 and the same `DebugResponse` JSON schema.

| Condition | System prompt | Datasheet excerpts |
|---|---|---|
| `baseline` | Generic "helpful assistant" | None (plain Gemini) |
| `no_rag` | Our embedded `SYSTEM_INSTRUCTION` | None (ablation) |
| `grounded` | Our embedded `SYSTEM_INSTRUCTION` | Case excerpts passed as `<retrieved_datasheets_and_documents>` via `AssembledDebugContext`, exactly like the API |

`baseline` vs `grounded` is the headline comparison. `no_rag` shows how much comes from the
prompt engineering versus the retrieved datasheet context.

## Metrics

- **Root-cause accuracy**: summary + top-ranked likely cause match the expected root cause
  (keyword groups; with `--judge`, an LLM judge decides instead and keyword score is kept too).
- **Fix accuracy**: `proposed_fix` + `corrected_code` contain the expected fix.
- **Correct datasheet citation**: a `datasheet_citations` entry names the expected document.
- **Fabricated citations**: cites a document that was never provided to the model.
- **Confidently wrong**: wrong root cause with `confidence_level = high`. Lower is better.
- **Holdout accuracy**: only the 8 holdout cases. Never tune prompts on these.

## Running

```bash
pip install -e ".[dev]"
export GEMINI_API_KEY=...            # Windows: set GEMINI_API_KEY=...

python tests/evaluation/run_eval.py --validate          # check case files
python tests/evaluation/run_eval.py --dry-run           # pipeline test, no API calls
python tests/evaluation/run_eval.py --repeats 3 --judge # the real run for the report
python tests/evaluation/run_eval.py --split holdout --conditions baseline grounded
```

Use `--repeats 3` for report numbers: Gemini answers vary between runs. Use `--delay` if you hit
rate limits. `--model` (or `EVAL_MODEL`) overrides the model; keep it the same as production.

## Adding a case

1. Add a dict to `CASES` in `build_cases.py` (copy an existing one).
2. Write keyword groups so the expected answer passes and vague answers fail. Every group must
   match at least one regex.
3. `python tests/evaluation/build_cases.py && python tests/evaluation/run_eval.py --validate`.

`apps/api/tests/test_evaluation_cases.py` validates cases and scoring in CI without API calls.

## Honest limitations (put these in the report)

- Reference excerpts are short paraphrases of the named datasheets and manuals, standing in for
  retrieval. Before publishing numbers, check each one against the source PDF and fill in
  `page_number`. A second run through the live API with the real PDFs uploaded tests retrieval too.
- Keyword scoring can miss a correct answer worded differently; report the `--judge` score
  alongside it and spot-check `raw.jsonl` by hand.
- 26 cases is a small benchmark; treat differences of a few percent as noise.
- Cases were written by the project team, which can bias them toward what the system handles.
  The holdout split reduces, but does not remove, this risk.
