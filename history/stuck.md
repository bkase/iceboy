# Stuck Note: `bd-1s1z` external mooneye PPU path

## What is working

The direct PPU core timing path now matches mooneye `lcdon_timing-GS` at the checkpoint level.

Relevant files:
- [`test/ppu/unit/test_lcdon_timing.py`](/Users/bkase/Documents/iceboy/test/ppu/unit/test_lcdon_timing.py)
- [`src/ppu/rtl/core_test_top.spade`](/Users/bkase/Documents/iceboy/src/ppu/rtl/core_test_top.spade)
- [`src/ppu/rtl/timing.spade`](/Users/bkase/Documents/iceboy/src/ppu/rtl/timing.spade)
- [`src/ppu/sem/step.spade`](/Users/bkase/Documents/iceboy/src/ppu/sem/step.spade)

That means the PPU core itself is not the remaining blocker for `lcdon_timing-GS`.

## What was actually broken

Two real integration bugs were present in the SoC-backed path.

Relevant files:
- [`src/bus/ppu_event_bridge.spade`](/Users/bkase/Documents/iceboy/src/bus/ppu_event_bridge.spade)
- [`src/bus/ppu_bridge_core_test_top.spade`](/Users/bkase/Documents/iceboy/src/bus/ppu_bridge_core_test_top.spade)
- [`test/unit/test_ppu_event_bridge_integration.py`](/Users/bkase/Documents/iceboy/test/unit/test_ppu_event_bridge_integration.py)
- [`test/unit/test_event_bridge.py`](/Users/bkase/Documents/iceboy/test/unit/test_event_bridge.py)
- [`test/harness/rom_runner.py`](/Users/bkase/Documents/iceboy/test/harness/rom_runner.py)
- [`tools/tests/test_rom_runner.py`](/Users/bkase/Documents/iceboy/tools/tests/test_rom_runner.py)

The first issue was `lcdc7_shadow` reset state. The bridge shadow started at `false`, but the PPU core reset state starts with LCD enabled in skipboot-style simulation. That meant the first `FF40` disable write was misclassified as only an MMIO register write, not a power transition.

Consequence:
- `FF40 <- 0x11` updated stored LCDC bits
- but it did **not** emit `ForceLcdPower(enabled: false)`
- so the PPU stayed running even though the bus-visible register value changed

The new focused bridge-plus-core regression proved that and now passes after fixing the shadow/reset alignment.

The second issue was a Python harness closure-capture bug in `_soc_step_to_commit()` in [`rom_runner.py`](/Users/bkase/Documents/iceboy/test/harness/rom_runner.py). The helper recomputed `preview_kind/addr/data` from a fresh prefinal observation, but integrated PPU MMIO reads for `FF41/FF44` still came from a stale outer `mcycle_mmio_observation` captured at the start of the M-cycle.

Consequence:
- general preview decode used the late observation
- but `STAT` / `LY` reads still used the old observation
- so the CPU saw PPU MMIO one M-cycle stale on the SoC ROM path

That bug is now fixed, but the follow-up finding is important: the real mooneye ROM still read `LY` and then `STAT` one full M-cycle late when the harness used the later same-cycle observation for PPU MMIO. The ROM moved through failures exactly one row later than the tables in [`test/ppu/unit/test_lcdon_timing.py`](/Users/bkase/Documents/iceboy/test/ppu/unit/test_lcdon_timing.py):

- first failure after the closure fix:
  - `LY`
  - `Cycle: $6E`
  - `Expected: $00`
  - raw fail bytes: `expected=0x00`, `actual=0x01`
- next failure after fixing `LY` only:
  - `STAT LYC=0`
  - `Cycle: $11`
  - `Expected: $84`
  - raw fail bytes: `expected=0x84`, `actual=0x87`

Those two mismatches line up with the next-row values in the mooneye checkpoint tables. That means the SoC ROM path needs to serve PPU MMIO from the opening observation of the current CPU M-cycle, not the later prefinal observation after additional dot steps.

There are now focused regressions in [`tools/tests/test_rom_runner.py`](/Users/bkase/Documents/iceboy/tools/tests/test_rom_runner.py) that lock this in for both `LY` and `STAT`.

## What is still unclear

The remaining uncertainty is no longer "is the PPU timing core wrong?".

The remaining question is now narrower: after fixing the bridge reset bug and the stale-MMIO observation bug, what concrete DUT-visible mismatch still causes `lcdon_timing-GS` to fail?

Relevant files:
- [`src/sim/soc_rom_top.spade`](/Users/bkase/Documents/iceboy/src/sim/soc_rom_top.spade)
- [`test/harness/dut_driver.py`](/Users/bkase/Documents/iceboy/test/harness/dut_driver.py)
- [`test/harness/rom_runner.py`](/Users/bkase/Documents/iceboy/test/harness/rom_runner.py)
- [`test/rom/test_ppu_wave_a_mooneye.py`](/Users/bkase/Documents/iceboy/test/rom/test_ppu_wave_a_mooneye.py)
- [`tools/run_ppu_wave_a_mooneye_verilator.sh`](/Users/bkase/Documents/iceboy/tools/run_ppu_wave_a_mooneye_verilator.sh)

Latest observed result:
- `timeout 900s tools/run_ppu_wave_a_mooneye_verilator.sh --skip-build -t test_lcdon_timing_gs_mooneye_passes`
- the test now runs materially farther than before
- after switching SoC PPU MMIO reads to the M-cycle-open observation, `lcdon_timing-GS` no longer dies first on `LY` or `STAT`
- the newest failure is:
  - `Test failed: OAM access`
  - `Cycle: $11`
  - `Expected: $00`
  - raw fail bytes: `expected=0x00`, `actual=0xFF`

That is a better blocker than before. The remaining failure is no longer generic timing-table drift on `LY/STAT`; it is now a specific bus-access gating failure.

## Current hypotheses if the external ROM still fails

Now that the stale MMIO observation bug is fixed, the next most likely causes are:

1. OAM accessibility on the SoC-backed path is still being sampled at the wrong sub-cycle boundary
Relevant files:
- [`src/sim/soc_rom_top.spade`](/Users/bkase/Documents/iceboy/src/sim/soc_rom_top.spade)
- [`test/harness/rom_runner.py`](/Users/bkase/Documents/iceboy/test/harness/rom_runner.py)
- [`test/harness/dut_driver.py`](/Users/bkase/Documents/iceboy/test/harness/dut_driver.py)
- [`test/unit/test_video_access.py`](/Users/bkase/Documents/iceboy/test/unit/test_video_access.py)
- [`src/video/access.spade`](/Users/bkase/Documents/iceboy/src/video/access.spade)

Hypothesis:
- just like `LY`/`STAT`, OAM gating may still be exposed from the wrong point within the CPU M-cycle on the SoC ROM path, so the CPU sees `0xFF` one M-cycle too early

2. The integrated PPU path may now be correct for MMIO timing but still wrong for OAM access timing during the same warmup window
Relevant files:
- [`src/ppu/rtl/timing.spade`](/Users/bkase/Documents/iceboy/src/ppu/rtl/timing.spade)
- [`src/ppu/sem/step.spade`](/Users/bkase/Documents/iceboy/src/ppu/sem/step.spade)
- [`src/ppu/rtl/core.spade`](/Users/bkase/Documents/iceboy/src/ppu/rtl/core.spade)
- [`src/video/access.spade`](/Users/bkase/Documents/iceboy/src/video/access.spade)

Hypothesis:
- the direct checkpoint/unit coverage is green for `LY/STAT`, but the OAM gating transition at `Cycle $11` might still be one phase early or late relative to mooneye

3. The mooneye ROM is now failing honestly, and the fastest route forward is still to identify the exact failing checkpoint rather than guessing from the final fail signature
Relevant files:
- [`test/harness/rom_runner.py`](/Users/bkase/Documents/iceboy/test/harness/rom_runner.py)
- [`test/rom/test_ppu_wave_a_mooneye.py`](/Users/bkase/Documents/iceboy/test/rom/test_ppu_wave_a_mooneye.py)

Hypothesis:
- the next useful data is the exact OAM-read point and whether the CPU should still see real OAM bytes instead of `0xFF`

## The oracle question I would ask

If I could ask one perfect oracle question, it would be:

> For `mooneye-test-suite/acceptance/ppu/lcdon_timing-GS`, starting from the exact skipboot state used here, at the first `OAM access` failure point (`Cycle $11`), should the CPU still see real OAM data or `0xFF`, and at which exact dot within that M-cycle does OAM become blocked?

Why this is the right question:
- the stale-harness-read question is already answered for `LY` and `STAT`
- the remaining blocker is now a specific OAM gating divergence
- once the exact access boundary is known, the next edit target should be obvious

## Practical next step

The next highest-signal move is:

1. Re-run `lcdon_timing-GS` with targeted capture of the OAM read site in [`rom_runner.py`](/Users/bkase/Documents/iceboy/test/harness/rom_runner.py)
2. Extract the first `OAM access` fail-site row/cycle and the corresponding `PC`, bus address, and returned byte
3. Line that up against the warmup/OAM access expectations already encoded in [`test/unit/test_video_access.py`](/Users/bkase/Documents/iceboy/test/unit/test_video_access.py) and [`test/ppu/unit/test_lcdon_timing.py`](/Users/bkase/Documents/iceboy/test/ppu/unit/test_lcdon_timing.py)
4. Fix the next real mismatch in the SoC path or access policy layer, whichever that first fail-site actually implicates

## Latest progress

The SoC-backed external mooneye path is materially healthier now.

Relevant files:
- [`test/harness/rom_runner.py`](/Users/bkase/Documents/iceboy/test/harness/rom_runner.py)
- [`tools/tests/test_rom_runner.py`](/Users/bkase/Documents/iceboy/tools/tests/test_rom_runner.py)
- [`test/rom/test_ppu_wave_a_mooneye.py`](/Users/bkase/Documents/iceboy/test/rom/test_ppu_wave_a_mooneye.py)
- [`tools/run_ppu_wave_a_mooneye_verilator.sh`](/Users/bkase/Documents/iceboy/tools/run_ppu_wave_a_mooneye_verilator.sh)

The runner now uses split observation rules for SoC-integrated video access:
- `LY` / `STAT` MMIO stays sampled from the opening observation of the CPU M-cycle
- OAM access uses a later mid-cycle observation only for later-line `mode 0 -> mode 1` transitions
- VRAM access uses a later mid-cycle observation only for later-line `mode 1 -> mode 2` transitions
- line 0 video access still uses the opening observation

That was enough to make these real external tests pass on the Verilator SoC path:
- `vblank_stat_intr-GS`
- `stat_lyc_onoff`
- `stat_irq_blocking`
- `lcdon_timing-GS`

Direct evidence:
- `timeout 2400s tools/run_ppu_wave_a_mooneye_verilator.sh --skip-build`
- result: `PASS=4 FAIL=1`

## Current blocker

Only one external Wave A mooneye case remains red:
- `lcdon_write_timing-GS`

Current real failure:
- `TimeoutError: SoC DUT did not reach a stable mooneye signature within 600000 M-cycles`
- `last_pc=0x4A6E`
- `last_if=0x01`
- `last_ie=0x00`
- `last_sig=['0x04', '0x67', '0x43', '0x89', '0x83', '0x99']`

This is different from the earlier `lcdon_timing-GS` failures:
- it is no longer a fast fail with a bad `LY` / `STAT` / `OAM` / `VRAM` compare row
- it now runs deep into the ROM and times out without reaching a mooneye pass/fail signature

## Best next question

If I could ask one targeted oracle question now, it would be:

> In `lcdon_write_timing-GS`, what exact bus-visible state or write-side effect is the ROM waiting on around `PC=0x4A6E`, and which register or memory location should change before the loop exits?

Why that is the right next question:
- the prior read-side timing bugs are mostly closed, proven by the 4 passing external cases
- the remaining failure looks like a write-timing or side-effect visibility issue, not the same earlier read-side gating problem
