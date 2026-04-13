# iCEBreaker Debug Bus

PMOD 1B is the logic-analyzer header for hardware day. The probe order stays fixed across all bitstreams, and this document records what each top actually drives today so the runbook and PulseView captures do not drift from the RTL.

## Probe Order

| PMOD | Pin | Signal |
| --- | ---: | --- |
| `P1B1` | `43` | `DBG_PC0` |
| `P1B2` | `38` | `DBG_PC1` |
| `P1B3` | `34` | `DBG_PC2` |
| `P1B4` | `31` | `DBG_PC3` |
| `P1B7` | `42` | `DBG_MCE` |
| `P1B8` | `36` | `DBG_PHASE0` |
| `P1B9` | `32` | `DBG_PHASE1` |
| `P1B10` | `28` | `DBG_PHASE2` |

## CPU Probe Top

`icebreaker_alu_loop_top` keeps the richest CPU-oriented bus:

- `DBG_PC0..DBG_PC3`: CPU `PC[3:0]`
- `DBG_MCE`: timebase `m_ce`
- `DBG_PHASE0..DBG_PHASE2`: CPU phase encoding

Use this image first when you need to answer “is the CPU executing ROM correctly at all?”

## Visible Bringup Tops

`icebreaker_visible_bg_static_top` and `icebreaker_visible_joypad_bg_smoke_top` repurpose PMOD 1B for visible-pipeline health:

- `DBG_PC0`: framebuffer reader active
- `DBG_PC1`: framebuffer pixel valid
- `DBG_PC2`: LCD frame active
- `DBG_PC3`: LCD SPI TX active
- `DBG_MCE`: LCD init complete
- `DBG_PHASE0`: LCD pixel-advance pulse
- `DBG_PHASE1`: CPU halted flag
- `DBG_PHASE2`: source-side frame-start pulse

These tops also use PMOD 2 for:

- `DEBUG_GPIO0`: framebuffer frame-start pulse
- `DEBUG_GPIO1`: scanout-valid indicator

## UART Uploader Top

`icebreaker_uart_rom_top` keeps a smaller PMOD 1B contract because the UART-visible package is tight on UP5K:

- `DBG_PC0..DBG_PC3`: held low
- `DBG_MCE`: held low
- `DBG_PHASE0`: held low
- `DBG_PHASE1`: CPU halted flag after upload release
- `DBG_PHASE2`: visible scanout-valid pulse

PMOD 2 stays variant-specific:

- `DEBUG_GPIO0`: upload-hold indicator
- `DEBUG_GPIO1`: UART TX-busy indicator

## LCD-Test Exception

`icebreaker_lcd_test_top` has no CPU, so PMOD 1B carries pattern-generator signals instead:

- `DBG_PC0..DBG_PC3`: pattern frame index bits `0..3`
- `DBG_MCE`: LCD init-complete flag
- `DBG_PHASE0..DBG_PHASE2`: pattern phase bits `0..2`

## PulseView / Sigrok

Use `tools/vcd_to_sigrok.py` to generate a labeled PulseView session from any debug-bus VCD:

```bash
python tools/vcd_to_sigrok.py \
  --vcd build/debug_bus.vcd \
  --out build/debug_bus.sr \
  --signals DBG_PC0,DBG_PC1,DBG_PC2,DBG_PC3,DBG_MCE,DBG_PHASE0,DBG_PHASE1,DBG_PHASE2
```

That `.sr` archive opens directly in PulseView with the probes labeled in PMOD 1B order.
