# iCEBreaker JOYPAD_BG_SMOKE Bring-Up

`build/bitstreams/joypad_smoke_icebreaker.bin` is the first-light visible milestone for the project. This is the image that satisfies the user-facing goal: a ROM is running, pixels appear on the LCD, and button presses visibly change the scene.

## Artifacts

- Bitstream: `build/bitstreams/joypad_smoke_icebreaker.bin`
- Packed from: `build/bitstreams/joypad_smoke_icebreaker.asc`
- Baseline report: [joypad_smoke_top_baseline.json](/Users/bkase/Documents/iceboy/docs/hardware/joypad_smoke_top_baseline.json)
- Captured visible output from the full-stack Verilator oracle: `build/icebreaker_visible/joypad_bg_smoke/captured.png`
- Oracle diff image: `build/icebreaker_visible/joypad_bg_smoke/diff.png`
- PyBoy reference frame: `build/icebreaker_visible/joypad_bg_smoke/reference.png`
- Bitstream size: `104090` bytes
- Binary roundtrip: stable under `icepack -> iceunpack -> icepack`
- ASC roundtrip: functionally equivalent, but `iceunpack` normalizes `.comment` headers and blank lines

## Measured Hardware Budget

- `SB_LUT4 = 4738`
- `SB_DFF = 628`
- `SB_SPRAM256KA = 2`
- `SB_RAM40_4K = 21`
- `ICESTORM_LC = 5102 / 5280`
- Achieved clock: `9.41 MHz` against a `12.0 MHz` target

This variant also places and routes successfully but misses the 12 MHz timing target. The packaged image is ready for first-light testing, with the same timing-risk note as `bg_static_icebreaker.bin`.

## Expected Hardware Behavior

1. Hold `BTN_N` low: the design stays in reset.
2. Release `BTN_N`: reset stretches for about `4.001 ms`.
3. The LCD stays blank during init, then the `joypad_bg_smoke` scene appears.
4. The stable scene should match `build/icebreaker_visible/joypad_bg_smoke/captured.png`: a checkerboard-like background plus a 2x2 tile cursor block.

LED expectations:
- `LEDR_N`: toggles from `framebuffer.frame_start`, so expect visible heartbeat activity once frames are flowing.
- `LEDG_N`: tracks `cpu_halted`; the joypad smoke ROM should remain in its running loop.

## Button Map

The visible response is defined by the reference model in [bench/ref/joypad_bg_smoke.py](/Users/bkase/Documents/iceboy/bench/ref/joypad_bg_smoke.py:61):

- D-pad: move the 2x2 cursor block by one tile on each new press edge.
- `A`: cycle through four palette presets.
- `B`: toggle the cursor tile style.
- `Start`: recenter the cursor to its home position.
- `Select`: invert the palette family.

This is the hardware-day bitstream to flash when you want to prove the full goal, not just a static image.

## Debug Bus

PMOD 1B uses the same visible-pipeline debug mapping as `bg_static_icebreaker.bin`:

| PMOD | Signal | Meaning |
| --- | --- | --- |
| `P1B1` | `DBG_PC0` | framebuffer reader active |
| `P1B2` | `DBG_PC1` | framebuffer pixel valid |
| `P1B3` | `DBG_PC2` | LCD frame active |
| `P1B4` | `DBG_PC3` | LCD SPI TX active |
| `P1B7` | `DBG_MCE` | LCD init complete |
| `P1B8` | `DBG_PHASE0` | LCD pixel advance pulse |
| `P1B9` | `DBG_PHASE1` | CPU halted flag |
| `P1B10` | `DBG_PHASE2` | source-side PPU frame-start pulse |

If a button appears dead:
- probe the corresponding PMOD 1A input pin from [pinout_firstlight.md](/Users/bkase/Documents/iceboy/docs/hardware/pinout_firstlight.md)
- confirm the button edge reaches the debounced joypad path
- verify that `DBG_PHASE2` continues pulsing while the LCD side is alive

## What Success Looks Like

- The LCD shows the checkerboard background and cursor block from `build/icebreaker_visible/joypad_bg_smoke/captured.png`.
- Pressing buttons changes the visible state according to the button map above.
- `joypad_smoke_icebreaker.bin` is the first bitstream in this repo that demonstrates the full "pixels plus input" milestone on hardware.

## Troubleshooting

- No image:
  Fall back to `build/bitstreams/lcd_test_pattern.bin`, then `build/bitstreams/bg_static_icebreaker.bin`, before debugging the interactive path.
- Image appears but no buttons work:
  Probe PMOD 1A inputs and compare them against the debounced button-bank outputs.
- Cursor moves, but palette/style buttons do nothing:
  Recheck the `A`, `B`, `Select`, and `Start` wiring specifically; the reference model uses edge-triggered actions, not held-repeat behavior.
- LCD updates intermittently:
  Check `DBG_PC2`, `DBG_PC3`, and the SPI pins for stalled frame transmission.

