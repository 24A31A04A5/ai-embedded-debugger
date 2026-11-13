# Detector spot check (hand-labelled synthetic answers, no model calls)

Labels: `detector_labels.json` (written by the assistant, pending human confirmation).

## Unsupported-claims detector (token level, gold = untraceable claim)
- Items: 20, exact agreement on 17/20
- TP 16, FP 0, FN 5: precision 1.0, recall 0.76
- Factually wrong claims flagged: 6/7

| Item | Flagged | Gold | Missed | False flags |
|---|---|---|---|---|
| U02 | - | gpio35 | gpio35 | - |
| U09 | - | 0x68 | 0x68 | - |
| U17 | hal_uart_mspinit, use_hal_driver | af7, hal_uart_mspinit, pa2, pa3, use_hal_driver | af7, pa2, pa3 | - |

## Abstention detector (item level, gold = correct abstention)
- Items: 16, agreement 0.62
- TP 4, FP 2, FN 4, TN 6: precision 0.67, recall 0.5
- Disagreements: A03 (pred False, gold True), A04 (pred True, gold False), A08 (pred False, gold True), A11 (pred False, gold True), A13 (pred False, gold True), A16 (pred True, gold False)
