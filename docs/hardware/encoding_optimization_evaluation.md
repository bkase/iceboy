# Encoding Optimization Evaluation

- Activity baseline: `/Users/bkase/Documents/iceboy/bench/manifests/activity_windows_baseline.json`
- Hardware baseline: `/Users/bkase/Documents/iceboy/docs/hardware/icebreaker_up5k_baseline.json`

## Summary

- Overall recommendation: keep current encodings for now
- LUT4 utilization: 3796/5280 (71.9%)
- Timing: 15.17 MHz achieved vs 12.00 MHz target (3.17 MHz margin)
- Evidence quality: mixed

## Candidate Decisions

### Phase enum

- Recommendation: defer
- No direct phase-bit hotspot appears in the captured top-toggle set.
- LUT4 utilization is 3796/5280 (71.9%), so one-hot growth is not free.
- Timing already clears the 12 MHz target with 15.17 MHz achieved (3.17 MHz margin).

### BusReq encoding

- Recommendation: defer
- Bus-related activity is visible, but the dominant paths are packed bus/commit surfaces rather than a leaf request encoding.
- LUT4 utilization is 3796/5280 (71.9%), so one-hot growth is not free.
- Timing already clears the 12 MHz target with 15.17 MHz achieved (3.17 MHz margin).

### AluReq encoding

- Recommendation: defer
- ALU work shows up as broad execute-step activity, not a focused request-encoding hotspot.
- LUT4 utilization is 3796/5280 (71.9%), so one-hot growth is not free.
- Timing already clears the 12 MHz target with 15.17 MHz achieved (3.17 MHz margin).

### Register select encoding

- Recommendation: defer
- The current captures do not isolate register-select signals strongly enough to justify a wider encoding.
- LUT4 utilization is 3796/5280 (71.9%), so one-hot growth is not free.
- Timing already clears the 12 MHz target with 15.17 MHz achieved (3.17 MHz margin).

### State machine encodings

- Recommendation: defer
- No critical-path or failing-timing evidence currently forces a control-FSM encoding change.
- LUT4 utilization is 3796/5280 (71.9%), so one-hot growth is not free.
- Timing already clears the 12 MHz target with 15.17 MHz achieved (3.17 MHz margin).
