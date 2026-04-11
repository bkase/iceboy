# First-Light Pinout

`icebreaker.pcf` now freezes the shared first-light pin map for the baseline top and the upcoming `alu_loop`, `lcd_test`, and visible SoC variants. The rule is simple: one canonical `.pcf`, stable signal names, and later tops reuse the same port surface instead of inventing per-variant aliases.

## On-board pins

| Signal | Pin | Purpose |
| --- | --- | --- |
| `CLK` | 35 | 12 MHz board clock |
| `BTN_N` | 10 | Global reset input |
| `LEDR_N` | 11 | Heartbeat / error LED |
| `LEDG_N` | 37 | CPU status / ready LED |

## PMOD 1A: button and DIP inputs

| PMOD | Pin | Signal |
| --- | --- | --- |
| P1A1 | 4 | `BTN_D_UP` |
| P1A2 | 2 | `BTN_D_DOWN` |
| P1A3 | 47 | `BTN_D_LEFT` |
| P1A4 | 45 | `BTN_D_RIGHT` |
| P1A7 | 3 | `DIP_A` |
| P1A8 | 48 | `DIP_B` |
| P1A9 | 46 | `DIP_START` |
| P1A10 | 44 | `DIP_SELECT` |

## PMOD 1B: debug bus

| PMOD | Pin | Signal |
| --- | --- | --- |
| P1B1 | 43 | `DBG_PC0` |
| P1B2 | 38 | `DBG_PC1` |
| P1B3 | 34 | `DBG_PC2` |
| P1B4 | 31 | `DBG_PC3` |
| P1B7 | 42 | `DBG_MCE` |
| P1B8 | 36 | `DBG_PHASE0` |
| P1B9 | 32 | `DBG_PHASE1` |
| P1B10 | 28 | `DBG_PHASE2` |

## PMOD 2: ST7789 LCD and spare GPIO

| PMOD | Pin | Signal |
| --- | --- | --- |
| P2_1 | 27 | `LCD_SCK` |
| P2_2 | 25 | `LCD_MOSI` |
| P2_3 | 21 | `LCD_CS` |
| P2_4 | 19 | `LCD_DC` |
| P2_7 | 26 | `LCD_RES` |
| P2_8 | 23 | `LCD_BL` |
| P2_9 | 20 | `DEBUG_GPIO0` |
| P2_10 | 18 | `DEBUG_GPIO1` |

## Baseline compatibility

The current `icebreaker_top` now exposes this full port surface and ties the future-use outputs to safe idle values. That keeps `icebreaker.pcf` legal for today's baseline build while reserving the exact names that later first-light tops will reuse.
