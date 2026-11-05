# Case corrections log

Originals (as first committed in `fe03a9d`) are kept unchanged in `cases_original/`.
Source of truth for current cases: `build_cases.py` (regenerate with `python build_cases.py`).
Holdout cases are NOT edited without the user's approval; proposals are in `HOLDOUT_PROPOSALS.md`.

## C1–C5: development-case factual corrections (approved by user 2026-11-05 17:13 IST)

| # | Case (split) | Field | Old | New | Reason | Source |
|---|---|---|---|---|---|---|
| C1 | esp32-gpio34-output (dev) | serial_logs | `I (322) gpio: GPIO[34]\| InputEn: 0\| OutputEn: 1\| ...` | `E (322) gpio: gpio_set_direction(277): io_num=34 can only be input` | `gpio_set_direction` rejects GPIO34 as output and logs an error; it never prints a config line with OutputEn: 1 | ESP-IDF v4.4 `components/driver/gpio.c` (`GPIO_CHECK(... "io_num=%d can only be input")`) |
| C1 | esp32-gpio34-output (dev) | target, user_question | `ESP32 / ESP-IDF`; "builds and runs without errors" | `ESP32 / ESP-IDF v4.4`; "builds and flashes fine" | Pin the version the log text comes from; the run does log an error | as above |
| C2 | esp32-gpio-sel-macro (dev) | expected.root_cause | "GPIO_SEL_x macros are not available in this ESP-IDF version" | "existed in ESP-IDF v4.4 (hal/gpio_types.h) but are not in v5.0" | State the actual version boundary | ESP-IDF v4.4 `components/hal/include/hal/gpio_types.h` (defines `GPIO_SEL_0`...); absent in v5.0 |
| C2 | esp32-gpio-sel-macro (dev) | reference snippet | paraphrase with fix hint "(1ULL << GPIO_NUM_2). BIT64(n) may also be used." | verbatim header text only | Remove answer leakage; snippet must be verbatim | ESP-IDF v5.0 `driver/gpio.h` `gpio_config_t` |
| C2 | esp32-gpio-sel-macro (dev) | target | `ESP32-S3 / ESP-IDF v5` | `ESP32-S3 / ESP-IDF v5.0 (code written for v4.4)` | Pin versions | as above |
| C3 | esp32-adc2-wifi (dev) | serial_logs | first failure logged at level `I` | level `E` for every failure line | The case code logs failures with ESP_LOGE | case firmware_code |
| C3 | esp32-adc2-wifi (dev) | target | `ESP32 / ESP-IDF` | `ESP32 / ESP-IDF v4.4 (legacy ADC driver)` | `adc2_get_raw` is the legacy API; behaviour with Wi-Fi differs in v5.x | ESP-IDF v4.2 ADC guide (ADC2/Wi-Fi sentence) |
| C4 | arduino-strcpy-overflow (dev) | firmware_code | separate globals `char deviceName[8]; int threshold` | `struct Config { char deviceName[8]; int threshold; }` | Global variable placement is up to the linker, so the corrupted value was not deterministic; struct member order is | C/C++ standard: struct members are laid out in declaration order |
| C4 | arduino-strcpy-overflow (dev) | serial_logs, expected.root_cause, expected.line | `threshold=12333`; line 6 | `threshold=25971` ('s','e' = 0x6573, little-endian AVR); line 9 | Value now follows from the string "greenhouse-node-01": bytes 8–9 are 's','e' | computed |
| C5 | arduino-multiple-definition (dev) | firmware_code | `lcd.print(counter);` (lcd undeclared) | `Serial.println(counter);` | An undeclared `lcd` would add a compile error unrelated to the bug | case review |

## C6: verbatim, page-referenced excerpts for DEV cases (2026-11-05)

All dev-case `reference_context` excerpts were replaced by verbatim text from the official documents,
with `document`, `revision`, `page_number` (+ `page_kind`: printed page or PDF index), `section`, `url`,
and `verification` (`verified` or `differs`). Data: `reference_sources.json`; applied by
`apply_verified_sources()` in `build_cases.py`. This also removes the answer hints that the paraphrased
snippets contained (e.g. "registers can't be written while the clock is disabled", "EXTI alone doesn't
route to the CPU", "may block on a lock").

Entries marked `differs` (the real document says less than the old paraphrase; the case still stands):
- arduino-missing-semicolon-cascade: GCC/ld docs never state that later errors follow from the first one; nearest text is `-Wfatal-errors` (weak citation).
- arduino-multiple-definition: GCC `-fno-common` supports the link error; it is default only since GCC 10.
- stm32-hal-i2c-address-shift ref 2: UM1725 Rev 8 p.547 lists only "HAL_I2C_ERROR_AF AF error".

Holdout excerpts are unchanged; their verified replacements are proposed in `HOLDOUT_PROPOSALS.md`.

## C7: insufficient-evidence cases added (2026-11-05)

New cases (no previous version): `abstain-esp32-stops-responding` (dev), `abstain-stm32-i2c-hal-error` (dev),
`abstain-arduino-analog-wrong` (holdout), `abstain-esp32-undecoded-backtrace` (holdout).
Totals: 30 cases = 20 dev + 10 holdout (the original 18/8 diagnostic split is unchanged).
