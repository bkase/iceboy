# iCEBreaker ALU Loop Bring-Up

`build/bitstreams/alu_loop_icebreaker.bin` is the CPU-only first-light flash image for the `alu_loop` ladder.

It isolates:
- `reset_bridge`
- `timebase`
- `cpu_core`
- `membus_alu_loop`
- the baked `alu_loop` ROM backend
- the fixed PMOD debug bus from `icebreaker.pcf`

It does not depend on the LCD controller, PPU, framebuffer, or visible SoC path.

## Artifacts

- Bitstream: `build/bitstreams/alu_loop_icebreaker.bin`
- Packed from: `build/bitstreams/alu_loop_icebreaker.asc`
- Baseline report: [alu_loop_top_baseline.json](/Users/bkase/Documents/iceboy/docs/hardware/alu_loop_top_baseline.json)
- Reference VCD: `build/rom_verilator/test_icebreaker_alu_loop_native/icebreaker_alu_loop.vcd`
- Reference JSONL trace: `build/rom_verilator/test_icebreaker_alu_loop_native/icebreaker_alu_loop.trace.jsonl`
- Bitstream size: `104090` bytes
- Binary roundtrip: stable under `icepack -> iceunpack -> icepack`
- ASC roundtrip: `build/bitstreams/alu_loop_icebreaker.asc` is stored in canonical `icepack -u` form, so unpack reproduces it byte-for-byte

## Measured Hardware Budget

- `SB_LUT4 = 3808`
- `SB_DFF = 439`
- `SB_SPRAM256KA = 1`
- `SB_RAM40_4K = 5`
- `ICESTORM_LC = 4134 / 5280`
- Achieved clock: `16.99 MHz` against a `12.0 MHz` target

## Reset and LEDs

- Releasing `BTN_N` does not start execution immediately. `reset_bridge(CLK, BTN_N, 48000, 16)` holds internal reset for `48016` 12 MHz cycles, which is about `4.001 ms`.
- `LEDR_N` is driven from `sys_counter[8]`. At a 12 MHz board clock that toggles at `12_000_000 / 512 = 23.4375 kHz`, so the red LED does not visibly blink. Expect it to look steady to the eye.
- The current `alu_loop` ROM does not execute `HALT`. It finishes the arithmetic check, reaches `__pass` at `0x01B1`, and then self-loops forever with `jr __pass`.
- Because of that ROM behavior, there is no halt edge on `LEDG_N` in the reference capture. If you are expecting a halt transition, you are not looking at the current `alu_loop_icebreaker.bin`.

## Logic Analyzer Setup

Clip the PMOD 1B debug bus:

| PMOD | Signal | Meaning |
| --- | --- | --- |
| `P1B1` | `DBG_PC0` | CPU `PC[0]` |
| `P1B2` | `DBG_PC1` | CPU `PC[1]` |
| `P1B3` | `DBG_PC2` | CPU `PC[2]` |
| `P1B4` | `DBG_PC3` | CPU `PC[3]` |
| `P1B7` | `DBG_MCE` | 1-in-4 memory-cycle enable pulse |
| `P1B8` | `DBG_PHASE0` | CPU phase bit 0 |
| `P1B9` | `DBG_PHASE1` | CPU phase bit 1 |
| `P1B10` | `DBG_PHASE2` | CPU phase bit 2 |

Recommended analyzer setup:
- sample rate: `>= 50 MS/s`; `100 MS/s` is comfortable
- threshold: standard 3.3 V CMOS
- trigger: `BTN_N` release, or first rising edge on `DBG_MCE` after reset drops

Useful VCD signals in GTKWave:
- `BTN_N`
- `impl.rst`
- `impl.alu_loop_hardware_core_0.tb`
- `impl.DBG_PC0` .. `impl.DBG_PC3`
- `impl.DBG_MCE`
- `impl.DBG_PHASE0` .. `impl.DBG_PHASE2`
- `impl.LEDR_N`
- `impl.LEDG_N`
- `impl.alu_loop_hardware_core_0.prefetch_pc_reg`

Phase encoding on `DBG_PHASE[2:0]`:
- `0x0`: fetch
- `0x2`: execute
- `0x3`: read immediate byte
- `0x4`: read immediate low byte
- `0x5`: read immediate high byte
- `0x7`: write / taken-branch bookkeeping

## Expected Bring-Up Story

1. Hold `BTN_N` low: the CPU stays in reset while the timebase continues running.
2. Release `BTN_N`: internal reset remains asserted for about `4.001 ms`.
3. First fetch window: the CPU fetches from `0x0100`, walks through the reset/ABI setup, then enters the test body.
4. Loop body: the debug nibble repeatedly returns to `0x015D` while the eight-step `add a, b` / `dec b` / `jr nz` loop runs.
5. Done / pass: the compare completes at `0x0162`, then the ROM reaches `__pass` at `0x01B1` and spins there forever.

## Reference Wave Windows

Boot-to-loop entry from the captured native trace:

```text
mcycle : 107 108 109 110 111 112 113 114 115
pc_lo  :   7   8   8   9   A   B   C   D   E
phase  :   2   0   2   0   3   0   4   5   0
bus_lo :   0   7   0   8   9   A   B   C   D
LEDR_N :   0   0   0   0   0   0   0   0   0
LEDG_N :   1   1   1   1   1   1   1   1   1
```

Loop-body cadence. This is the pattern to look for on the P1B bus while the arithmetic loop is active:

```text
mcycle : 115 116 117 118 119 120 121 122
pc_lo  :   E   E   F   F   0   1   D   E
phase  :   0   2   0   2   0   3   2   0
bus_lo :   D   0   E   0   F   0   0   D
meaning: fetch add, exec add, fetch dec, exec dec, fetch jr, read imm8, branch, fetch loop
```

Checkpoint summary from the same run:

| Checkpoint | M-cycle | PC | `DBG_PC[3:0]` | `DBG_PHASE[2:0]` |
| --- | ---: | ---: | ---: | ---: |
| `__checkpoint_loop_setup` | `108` | `0x0157` | `0x8` | `0x0` |
| first `__checkpoint_loop_body` | `115` | `0x015D` | `0xE` | `0x0` |
| `__checkpoint_loop_done` | `172` | `0x0162` | `0x3` | `0x0` |
| `__pass` | `223` | `0x01B1` | `0x2` | `0x0` |

## What To Check If It Fails

- No activity at all:
  Check `CLK`, `BTN_N`, and board power first.
- `BTN_N` release does nothing for less than `4 ms`:
  That is expected; the reset bridge intentionally stretches release.
- Debug bus never leaves the boot pattern:
  Suspect ROM wiring or the `alu_loop` baked image path.
- `DBG_PC[3:0]` never revisits `0xE` / `0xF` / `0x0` / `0x1`:
  The ALU loop is not executing correctly.
- `__pass` is never reached:
  Compare the captured bus pattern against the VCD at `build/rom_verilator/test_icebreaker_alu_loop_native/icebreaker_alu_loop.vcd`.

## Decision

This is a valid flash candidate for hardware-arrival day. It proves:
- packed bitstream generation works
- the reset path releases correctly on hardware pins
- the CPU can boot from the baked ROM image
- the P1B debug bus is rich enough to diagnose first-light failures without the LCD path

It does not prove a visible halt indication yet, because the current `alu_loop` ROM intentionally parks in `__pass` instead of executing `HALT`.
