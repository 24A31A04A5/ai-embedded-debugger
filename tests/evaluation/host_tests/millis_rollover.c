/*
 * Host-side simulation of the arduino-millis-int-overflow case.
 * Models ATmega328P types explicitly: int = int16_t, unsigned long = uint32_t.
 * AVR int arithmetic is 16-bit; on the host int16_t operands promote to 32-bit int,
 * so 16-bit results are narrowed back with (int16_t) to mimic avr-gcc's 16-bit
 * code (signed overflow is formally UB in C; avr-gcc emits plain 16-bit wrapping
 * subtraction, which is what is modelled here).
 * Each variant runs "loop()" once per simulated millisecond and reports how many
 * LED toggles happen in selected 10-second windows. A correct 1 s blink gives 10.
 */
#include <stdint.h>
#include <stdio.h>
#include <inttypes.h>

typedef int16_t avr_int;
typedef uint32_t avr_ulong;

static int count_toggles(int variant, avr_ulong start, avr_ulong window_start, avr_ulong window_len) {
    avr_int last_i = (avr_int)start;   /* int lastBlink */
    avr_ulong last_ul = start;          /* unsigned long lastBlink */
    int toggles = 0;
    avr_ulong end = window_start + window_len; /* may wrap; loop counts iterations instead */
    (void)end;
    avr_ulong t = start;
    for (;; ++t) {
        int fire = 0;
        switch (variant) {
        case 0: { /* original case code: int now = millis(); if (now - lastBlink >= 1000) */
            avr_int now = (avr_int)t;
            avr_int diff = (avr_int)(now - last_i);
            if (diff >= 1000) { fire = 1; last_i = now; }
            break; }
        case 1: { /* int lastBlink; if (millis() - lastBlink >= 1000) ; lastBlink = millis(); */
            if ((avr_ulong)(t - (avr_ulong)(int32_t)last_i) >= 1000u) { fire = 1; last_i = (avr_int)t; }
            break; }
        case 2: { /* int lastBlink; if (millis() > lastBlink + 1000) ; lastBlink = millis(); */
            avr_int rhs = (avr_int)(last_i + 1000);           /* 16-bit int addition */
            if (t > (avr_ulong)(int32_t)rhs) { fire = 1; last_i = (avr_int)t; }
            break; }
        case 3: { /* unsigned long lastBlink; if (millis() - lastBlink >= 1000)  (rollover-safe) */
            if ((avr_ulong)(t - last_ul) >= 1000u) { fire = 1; last_ul = t; }
            break; }
        case 4: { /* unsigned long lastBlink; if (millis() > lastBlink + 1000)  (not rollover-safe) */
            if (t > (avr_ulong)(last_ul + 1000u)) { fire = 1; last_ul = t; }
            break; }
        }
        avr_ulong rel = t - window_start;
        if (fire && rel < window_len) toggles++;
        if ((avr_ulong)(t - window_start) == window_len) break;
    }
    return toggles;
}

int main(void) {
    const char *names[] = {
        "0 original: int now=millis(); now - lastBlink >= 1000",
        "1 int lastBlink; millis() - lastBlink >= 1000",
        "2 int lastBlink; millis() > lastBlink + 1000",
        "3 FIX unsigned long; millis() - lastBlink >= 1000",
        "4 unsigned long; millis() > lastBlink + 1000",
    };
    struct { const char *label; avr_ulong start, win; } w[] = {
        {"0-10 s", 0u, 0u},
        {"30-40 s (int16 wrap at 32.767 s)", 0u, 30000u},
        {"60-70 s", 0u, 60000u},
        {"2^32 wrap: 5 s before .. 5 s after (49.7 days)", 4294967296u - 600000u, 4294967296u - 5000u},
    };
    printf("Toggles per 10 s window (correct = 10)\n");
    for (int v = 0; v < 5; ++v) {
        printf("%-52s", names[v]);
        for (int k = 0; k < 4; ++k) {
            int n = count_toggles(v, w[k].start, w[k].win, 10000u);
            printf(" | %s: %d", w[k].label, n);
        }
        printf("\n");
    }
    return 0;
}
