# iCEBreaker BG_STATIC Bring-Up

`build/bitstreams/bg_static_icebreaker.bin` is the static-image visible bring-up bitstream for the full `icebreaker_visible_top` ladder.

It proves:
- the packed visible top boots on the iCEBreaker pinout
- the LCD init sequence completes on the hardware pins
- the BG-only visible path reaches the expected `BG_STATIC` image
- the end-to-end reference from `bd-1xut` matches the captured LCD output

## Artifacts

- Bitstream: `build/bitstreams/bg_static_icebreaker.bin`
- Packed from: `build/bitstreams/bg_static_icebreaker.asc`
- Baseline report: [bg_static_top_baseline.json](/Users/bkase/Documents/iceboy/docs/hardware/bg_static_top_baseline.json)
- Reference capture from the full-stack Verilator oracle: `build/icebreaker_visible/bg_static/captured.png`
- Reference raw frame: `build/icebreaker_visible/bg_static/captured.raw`
- PyBoy oracle frame: `build/icebreaker_visible/bg_static/reference.png`
- Bitstream size: `104090` bytes
- Binary roundtrip: stable under `icepack -> iceunpack -> icepack`
- ASC roundtrip: functionally equivalent, but `iceunpack` normalizes `.comment` headers and blank lines

## Measured Hardware Budget

- `SB_LUT4 = 4768`
- `SB_DFF = 627`
- `SB_SPRAM256KA = 2`
- `SB_RAM40_4K = 19`
- `ICESTORM_LC = 5131 / 5280`
- Achieved clock: `8.49 MHz` against a `12.0 MHz` target

`nextpnr` places and routes this image successfully, but timing is currently below the 12 MHz board target. Treat this as a valid packaged bring-up image with a timing-risk note, not a timing-clean production build.

## Expected Hardware Behavior

1. Press and hold `BTN_N`: the design stays in reset.
2. Release `BTN_N`: internal reset stretches for about `4.001 ms` via `reset_bridge(CLK, BTN_N, 48000, 16)`.
3. LCD stays blank during controller init, then begins RAM writes into the visible `160x144` window.
4. The final stable image should match `build/icebreaker_visible/bg_static/captured.png`: a static tiled background pattern with no sprite activity.

LED expectations:
- `LEDR_N`: forced active for this variant, so expect the red LED to look steady.
- `LEDG_N`: tracks `cpu_halted`; the BG_STATIC ROM should leave the CPU running, so do not expect a visible halt transition.

## Debug Bus

PMOD 1B is repurposed from CPU PC bits to visible-pipeline health signals for this ladder:

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

Variant-specific extras stay on PMOD 2:
- `DEBUG_GPIO0`: framebuffer frame-start pulse
- `DEBUG_GPIO1`: scanout-valid indicator

Expected capture story:
- After reset, `DBG_MCE` goes high once the ST7789 init sequence finishes.
- `DBG_PC2` and `DBG_PC3` become active during LCD frame streaming.
- `DBG_PHASE2` continues pulsing once the PPU source frames are flowing.

PulseView / LA expectation:
- the ST7789 decoder should show `RAMWR`
- each visible frame should contain `23040` pixel writes (`160 x 144`)

## What Success Looks Like

- The panel shows the same tiled background as `build/icebreaker_visible/bg_static/captured.png`.
- No button interaction is required for this image.
- The SPI pins (`LCD_SCK`, `LCD_MOSI`, `LCD_CS`, `LCD_DC`) stay active after init.

## Troubleshooting

- LCD stays black:
  Flash `build/bitstreams/lcd_test_pattern.bin` first to isolate wiring and init issues.
- LCD shows garbage or repeated tearing:
  Check `LCD_MOSI`, `LCD_SCK`, `LCD_CS`, and `LCD_DC` with a logic analyzer and compare against `build/icebreaker_visible/bg_static/captured.png`.
- Debug bus never shows `DBG_MCE = 1`:
  The LCD controller never completed init; focus on reset and LCD wiring.
- Debug bus shows `DBG_MCE = 1` but no `DBG_PC2` / `DBG_PC3` activity:
  The framebuffer-to-LCD handoff is stalled.
