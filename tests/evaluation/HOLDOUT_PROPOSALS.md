# Holdout corrections H1–H4

Status (2026-11-05 18:05 IST): H1, H2, H3 approved and applied. H4 applied only for excerpts verified
verbatim; esp32-brownout-wifi and stm32-missing-volatile remain flagged. See `CORRECTIONS.md`.

## H1. arduino-millis-int-overflow — evidence contradicts the code

Original code (ATmega328P: `int` = 16-bit, `millis()` returns `unsigned long` = 32-bit):
```c
int lastBlink = 0;
void loop() {
  int now = millis();
  if (now - lastBlink >= 1000) { digitalWrite(LED_BUILTIN, !digitalRead(LED_BUILTIN)); lastBlink = now; }
}
```
Original log/claim: prints `t=31000 blink`... and "LED blinks for ~32 s then stops". Problems:
1. The code prints nothing, but the log shows output.
2. Both operands are 16-bit, so `now - lastBlink` wraps in 16 bits and stays correct across the 32.767 s wrap
   (formally signed overflow is UB; avr-gcc emits a plain 16-bit subtraction). Simulated result: it keeps
   blinking (10 toggles per 10 s at 30–40 s and 60–70 s).
3. My earlier suggestion `millis() > lastBlink + 1000` relies on 16-bit signed overflow in `lastBlink + 1000`
   (UB), so I withdraw it as the canonical version.

Evidence: `host_tests/millis_rollover.c` (output in `millis_rollover.expected.txt`) and the CI test
`apps/api/tests/test_millis_rollover_model.py`. Toggles per 10 s window (correct = 10):

| Code | 30–40 s | 60–70 s | across 2^32 wrap (49.7 days) |
|---|---|---|---|
| original (`int now`, `now - lastBlink`) | 10 | 10 | 10 |
| `int lastBlink; millis() - lastBlink >= 1000` | 7003 | 10000 | 10 |
| `int lastBlink; millis() > lastBlink + 1000` (UB) | 3 | 0 | 174 |
| **fix: `unsigned long lastBlink; millis() - lastBlink >= 1000`** | **10** | **10** | **10** |
| `unsigned long; millis() > lastBlink + 1000` | 10 | 10 | 409 |

Proposed version (well-defined C, deterministic symptom):
```c
int lastBlink = 0;                       // bug: should be unsigned long
void loop() {
  if (millis() - lastBlink >= 1000) {    // lastBlink is sign-extended to unsigned long
    digitalWrite(LED_BUILTIN, !digitalRead(LED_BUILTIN));
    lastBlink = millis();                // truncated to 16 bits; negative after 32.767 s
  }
}
```
- serial_logs: empty (the code prints nothing).
- user_question: "The LED blinks every second for about 33 seconds, then looks constantly on (dimmer)."
- expected.root_cause: lastBlink is a 16-bit int; after 32,767 ms the stored value goes negative and is
  sign-extended in the unsigned long subtraction, so the difference is always ≥ 1000 and the LED toggles on every loop.
- expected.fix: declare `unsigned long lastBlink` and keep the subtraction form `millis() - lastBlink >= interval`
  (rollover-safe across the 2^32 ms wrap); do not use `millis() > lastBlink + interval`.
- keywords unchanged in spirit: root cause [overflow|wrap|16-bit|32,767|negative|sign] + [int|lastBlink]; fix [unsigned long|uint32_t].
- citation: Arduino reference `millis()` (verified, see `reference_sources.json`).

## H2. stm32-uart-hal-not-enabled — wrong failure stage

With `HAL_UART_MODULE_ENABLED` commented out, `stm32f4xx_hal_conf.h` does not include
`stm32f4xx_hal_uart.h`, so the build fails at **compile** time in main.c, before linking. The case's
`undefined reference to HAL_UART_Init` (link stage) would not be reached.

Actual output (clang 22.1.8 via zig, cortex-m4, STM32F401xE, stm32f4xx-hal-driver v1.8.6; reproduce with
`host_tests/uart_hal/compile.sh`):
```
main.c:3:1: error: unknown type name 'UART_HandleTypeDef'
main.c:8:5: error: call to undeclared function 'HAL_UART_Init'; ISO C99 and later do not support implicit function declarations [-Wimplicit-function-declaration]
2 errors generated.
```
Not yet reproduced with arm-none-eabi-gcc (not installable in this sandbox). Expected GCC wording:
`error: unknown type name 'UART_HandleTypeDef'` and, for GCC ≥ 14, `error: implicit declaration of function 'HAL_UART_Init'`
(a warning on older GCC). Proposal: replace compiler_output with a GCC-format version of the two errors above,
set `failure_stage: "compile"`, keep root cause/fix keywords (HAL_UART_MODULE_ENABLED / hal_conf).
Alternatively, run compile.sh with arm-none-eabi-gcc on your machine to capture GCC's exact text.

## H3. stm32-hardfault-null-fnptr — register addresses vs register contents

Original log:
```
CFSR = 0x00020000  HFSR = 0x40000000
PC   = 0x00000000  LR = 0x08000a3b
MMFAR= 0xE000EDF4  BFAR = 0xE000EDF8
```
Facts (Arm DUI 0553B, Cortex-M4 Generic User Guide, §4.3):
- MMFAR **register address** is 0xE000ED34, BFAR is 0xE000ED38 (the log's 0xE000EDF4/0xE000EDF8 are neither;
  those are debug registers). A fault handler prints the **contents** of these registers, not their addresses.
- MMFAR contents are valid only when CFSR.MMARVALID (bit 7) = 1; BFAR only when CFSR.BFARVALID (bit 15) = 1.
- CFSR = 0x00020000 is UFSR.INVSTATE (bit 17) only; MMARVALID = 0 and BFARVALID = 0, so neither address is valid.
- A call through a NULL function pointer branches to 0x00000000 with bit[0] = 0, clearing EPSR.T → UsageFault
  INVSTATE, escalated to HardFault (HFSR.FORCED = bit 30 = 0x40000000) because UsageFault is not enabled.
  It is not a MemManage/BusFault data access, so MMFAR/BFAR carry no fault address here.

Proposed log lines:
```
CFSR = 0x00020000 (UFSR.INVSTATE)  HFSR = 0x40000000 (FORCED)
PC   = 0x00000000  LR = 0x08000a3b
MMFAR: not valid (CFSR.MMARVALID=0)  BFAR: not valid (CFSR.BFARVALID=0)
```
Root cause/fix unchanged.

## H4. Verbatim excerpts for the 8 holdout cases

`reference_sources.json` also holds verified excerpts (document, revision, page, url) for the holdout
cases. Two matter for correctness:
- esp32-brownout-wifi (`differs`): the datasheet (v5.3, Table 5-4, p.52) gives 240 mA as the *typical*
  802.11b TX current at 50% duty cycle, not a peak; "supply must deliver these peaks" is not in the document.
  Better support: Table 5-2, p.51, external supply should deliver at least 0.5 A.
- stm32-missing-volatile (`differs`): the "abstract machine" wording is from the C standard, not the GCC manual.
Proposal: apply the verified holdout excerpts the same way as for dev cases (C6).
