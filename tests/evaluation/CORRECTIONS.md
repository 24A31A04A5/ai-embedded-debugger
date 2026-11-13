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

## H1–H4: holdout corrections (approved by user 2026-11-05 18:05 IST; H4 conditional)

Originals remain unchanged in `cases_original/` (as first committed in `fe03a9d`).

| # | Case (split) | Field | Old | New | Reason | Source |
|---|---|---|---|---|---|---|
| H1 | arduino-millis-int-overflow (holdout) | firmware_code | `int now = millis(); if (now - lastBlink >= 1000) {... lastBlink = now; }` | `if (millis() - lastBlink >= 1000) {... lastBlink = millis(); }` with `int lastBlink` | The old code's 16-bit subtraction keeps working across the 32.767 s wrap (LED keeps blinking), contradicting the claimed symptom; the new code fails deterministically and is well-defined C | `host_tests/millis_rollover.c` (+ `.expected.txt`), `apps/api/tests/test_millis_rollover_model.py` |
| H1 | same | serial_logs | `t=31000 blink` ... `(no further blinks)` | empty | The code prints nothing | case firmware_code |
| H1 | same | title, user_question | "Timer stops after about 32 seconds"; "LED blinks for ~32 s then stops." | "LED blinks for ~33 s, then looks constantly on"; "The LED blinks every second for about 33 seconds, then looks constantly on (dimmer)." | Symptom of the new code: lastBlink goes negative, is sign-extended, the difference is always >= 1000, LED toggles every loop | simulation above |
| H1 | same | expected.root_cause / fix / line / root_cause_keywords | 16-bit int overflow breaks the comparison; "use unsigned long for now and lastBlink"; line 4; groups [overflow…] + [int, millis] | sign extension of negative 16-bit lastBlink; `unsigned long lastBlink` with `millis() - lastBlink >= interval` (not `millis() > lastBlink + interval`); line 1; groups [overflow, wrap, 16-bit, 32,767, negative, sign] + [\bint\b, lastBlink] | Match the new code; the `>` form is not rollover-safe | Arduino reference `millis()` (verified) |
| H2 | stm32-uart-hal-not-enabled (holdout) | compiler_output, failure_stage | linker output `undefined reference to 'HAL_UART_Init'` / `collect2: error: ld returned 1 exit status` | measured compile errors `unknown type name 'UART_HandleTypeDef'`, `call to undeclared function 'HAL_UART_Init'`; `failure_stage: "compile"` | With HAL_UART_MODULE_ENABLED commented out, stm32f4xx_hal_conf.h does not include stm32f4xx_hal_uart.h, so main.c fails to compile before linking | `host_tests/uart_hal/` (clang 22.1.8 via zig, STM32F401xE, HAL v1.8.6). GCC wording NOT measured (arm-none-eabi-gcc unavailable here); output is clang's verbatim |
| H2 | same | firmware_code, title, category, expected.root_cause | no include in main.c; "undefined reference to HAL_UART_Init"; linker; "...unresolved at link time" | `#include "stm32f4xx_hal.h"` added (as in the measured main.c); "unknown type name UART_HandleTypeDef"; compiler; "...undeclared and main.c fails to compile" | Consistent with the measured output; keywords and fix unchanged | as above |
| H3 | stm32-hardfault-null-fnptr (holdout) | serial_logs | `CFSR = 0x00020000  HFSR = 0x40000000` / `MMFAR= 0xE000EDF4  BFAR = 0xE000EDF8` | `CFSR = 0x00020000 (UFSR.INVSTATE)  HFSR = 0x40000000 (FORCED)` / `MMFAR: not valid (CFSR.MMARVALID=0)  BFAR: not valid (CFSR.BFARVALID=0)` | The old values were neither register contents nor the registers' addresses (0xE000ED34 / 0xE000ED38); with MMARVALID=BFARVALID=0 neither holds a fault address | Arm DUI 0553B Cortex-M4 Generic User Guide §4.3 (pp. 245–246, verified) |
| H4 | arduino-millis-int-overflow, esp32-flash-pins, esp32-i2c-no-pullups, freertos-isr-priority-assert, stm32-hardfault-null-fnptr (2), stm32-uart-hal-not-enabled (holdout) | reference_context | paraphrased excerpts | verbatim excerpts with document, revision, page/URL, section, `verification: verified` | Only entries verified verbatim against the official document are applied | `reference_sources.json` |

**H4 not applied (flagged, unverified wording kept):**
- esp32-brownout-wifi (`differs`): the original excerpt says the supply "must deliver these peaks"; the datasheet (v5.3, Table 5-4, p.52) gives 240 mA as a *typical* 802.11b TX current, and the wording is not in the document. Better support is Table 5-2, p.51 (supply ≥ 0.5 A). This paraphrase also states the cause and the fix (see leakage note in METHODOLOGY.md). Needs your decision.
- stm32-missing-volatile (`differs`): the "abstract machine" wording comes from the C standard, not the cited GCC manual. Needs a correct source or a different excerpt.

## Freeze (2026-11-05)

After C1–C7, H1–H3 and H4 (verified only), both splits were frozen in `DATASET_MANIFEST.json`
(SHA-256 per file, CRLF normalised to LF; one manifest hash per split). `run_eval.py` refuses to run
if either split differs. Any later change needs approval, a row here, and `dataset_manifest.py --freeze`.
