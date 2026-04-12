# iCEBreaker LCD Test Bring-Up

`build/bitstreams/lcd_test_pattern.bin` is the first bitstream to flash on hardware-arrival day.

It isolates only:
- `reset_bridge`
- `st7789_lcd`
- the fixed LCD pin map from `icebreaker.pcf`
- a tiny internal pattern generator

It does not depend on the CPU, PPU, framebuffer, ROM backends, or joypad path.

## Artifact

- Bitstream: `build/bitstreams/lcd_test_pattern.bin`
- Packed from: `build/bitstreams/lcd_test_pattern.asc`
- Baseline report: [lcd_test_top_baseline.json](/Users/bkase/Documents/iceboy/docs/hardware/lcd_test_top_baseline.json)
- Bitstream size: `104090` bytes
- Binary roundtrip: stable under `icepack -> iceunpack -> icepack`

## Measured Hardware Budget

- `SB_LUT4 = 283`
- `SB_DFF = 114`
- `SB_SPRAM256KA = 0`
- `SB_RAM40_4K = 0`
- `ICESTORM_LC = 389 / 5280`
- Achieved clock: `34.77 MHz` against a `12.0 MHz` target

## Expected Behavior

- `LEDR_N`: steady heartbeat tied to frame groups; visible blink a few times per second once the LCD is running.
- `LEDG_N`: mostly lit while frame data is actively streaming, with brief idle gaps between frames.
- LCD power-on sequence:
  1. brief blank interval during reset and sleep-out
  2. first valid frame appears after roughly `140 ms` (`10 ms` reset pulse + `10 ms` post-reset delay + `120 ms` sleep-out delay)
  3. repeating 8-phase pattern cycle:
     - solid white
     - light gray
     - dark gray
     - black
     - 8x8 checkerboard
     - moving vertical bars
     - four quadrants
     - diagonal 16x16 checker pattern

Each phase lasts `16` LCD frames. At about `16 fps`, each phase holds for about `1 second`.

## Expected ST7789 Init Transcript

Logic-analyzer decode on `LCD_CS/LCD_DC/LCD_SCK/LCD_MOSI` should show this command stream before the first pixel frame:

`01`
`11`
`3A 55`
`36 00`
`2A 00 00 01 3F`
`2B 00 00 00 EF`
`21`
`13`
`29`

The first frame write should then begin with:

`2A 00 50 00 EF`
`2B 00 30 00 BF`
`2C`

The first pixel payload bytes should be `FF FF` for the initial white fill.

## What To Check If Nothing Appears

- Backlight:
  - `LCD_BL` should go active after reset exits.
  - If the panel is completely dark, check LCD power and backlight wiring first.
- Reset:
  - `LCD_RES` should stay low only during the reset pulse, then remain high.
  - If it stays low, inspect `BTN_N`, the reset bridge path, and the LCD reset pin wiring.
- SPI wiring:
  - `LCD_CS` should assert low around init commands.
  - `LCD_DC` should be low for command bytes and high for parameter/pixel bytes.
  - `LCD_SCK` should toggle continuously during command and pixel bursts.
  - `LCD_MOSI` should carry the init bytes listed above.
- Geometry:
  - The controller programs `CASET` to columns `0x0050..0x00EF` and `RASET` to rows `0x0030..0x00BF`.
  - If the panel shows shifted content, re-check the display variant and offset assumptions.

## Logic Analyzer Clip Points

- Required LCD probes:
  - `LCD_CS`
  - `LCD_DC`
  - `LCD_SCK`
  - `LCD_MOSI`
  - `LCD_RES`
  - `LCD_BL`
- Optional board-status probes:
  - `LEDR_N`
  - `LEDG_N`

Expected analyzer story:
- `LCD_RES` low for the reset window, then high
- `LCD_CS` low around the init command bursts
- `LCD_DC` switching low/high around command vs data bytes
- `LCD_SCK` and `LCD_MOSI` active during the exact init transcript above
- repeated frame bursts once initialization completes

## Decision

This is the first flash candidate for arrival day because any failure narrows immediately to:
- panel power/backlight
- reset wiring
- SPI wiring or polarity
- ST7789 init assumptions

It avoids the much wider failure surface of CPU, PPU, VRAM, framebuffer, and ROM integration.
