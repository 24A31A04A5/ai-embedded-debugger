"""Host-side model of the arduino-millis-int-overflow holdout case (no hardware, no Gemini).

Mirrors tests/evaluation/host_tests/millis_rollover.c in Python with explicit
ATmega328P widths: int = 16-bit signed, unsigned long = 32-bit unsigned.
"""

U32 = 1 << 32


def i16(x: int) -> int:
    x &= 0xFFFF
    return x - 0x10000 if x & 0x8000 else x


def u32(x: int) -> int:
    return x % U32


def toggles(variant: str, start: int, window_start: int, window_len: int = 10_000) -> int:
    last_i, last_ul, n = i16(start), u32(start), 0
    t = start
    while True:
        tt = u32(t)
        fire = False
        if variant == "original":  # int now = millis(); if (now - lastBlink >= 1000)
            now = i16(tt)
            if i16(now - last_i) >= 1000:
                fire, last_i = True, now
        elif variant == "int_sub":  # int lastBlink; millis() - lastBlink >= 1000
            if u32(tt - u32(last_i)) >= 1000:
                fire, last_i = True, i16(tt)
        elif variant == "safe":  # unsigned long lastBlink; millis() - lastBlink >= 1000
            if u32(tt - last_ul) >= 1000:
                fire, last_ul = True, tt
        elif variant == "ul_add":  # unsigned long; millis() > lastBlink + 1000
            if tt > u32(last_ul + 1000):
                fire, last_ul = True, tt
        rel = u32(tt - window_start)
        if fire and rel < window_len:
            n += 1
        if rel == window_len:
            return n
        t += 1


WRAP_START = U32 - 600_000
WRAP_WINDOW = U32 - 5_000


def test_original_case_code_keeps_blinking_after_int16_wrap() -> None:
    # The holdout case claims the LED stops at ~32 s; with 16-bit wrapping it does not.
    assert toggles("original", 0, 30_000) == 10
    assert toggles("original", 0, 60_000) == 10


def test_int_lastblink_with_unsigned_subtraction_toggles_every_loop() -> None:
    assert toggles("int_sub", 0, 0) == 9
    assert toggles("int_sub", 0, 60_000) == 10_000  # toggles every ms: LED looks constantly on


def test_unsigned_long_subtraction_is_rollover_safe_across_2_pow_32() -> None:
    assert toggles("safe", 0, 30_000) == 10
    assert toggles("safe", WRAP_START, WRAP_WINDOW) == 10


def test_addition_form_breaks_at_2_pow_32() -> None:
    assert toggles("ul_add", WRAP_START, WRAP_WINDOW) > 10
