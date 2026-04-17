# Hardware Day Runbook

This is the arrival-day script for bringing up the breadboarded iCEBreaker stack from lowest risk to highest value.

## Power-On Sequence

1. Connect the LCD and board power rails before attaching the data PMODs.
2. Connect PMOD 2 for the LCD pins.
3. Connect PMOD 1A for buttons and DIP inputs.
4. Connect PMOD 1B to the logic analyzer.
5. Attach USB for FPGA programming and UART.
6. Confirm the board enumerates before flashing anything.

## Flash Order

Prepare all five images in one pass before heading to the bench:

`tools/prepare_hardware_day.sh`

1. `build/bitstreams/lcd_test_pattern.bin`
2. `build/bitstreams/alu_loop_icebreaker.bin`
3. `build/bitstreams/bg_static_icebreaker.bin`
4. `build/bitstreams/joypad_smoke_icebreaker.bin`
5. `build/bitstreams/uart_rom_icebreaker.bin`

Do not skip ahead. Each image narrows the failure surface for the next one.

## Logic Analyzer Baseline

- Probe PMOD 1B using the per-top mappings in [debug_bus.md](/Users/bkase/Documents/iceboy/docs/hardware/debug_bus.md)
- Probe PMOD 2 LCD lines: `LCD_SCK`, `LCD_MOSI`, `LCD_CS`, `LCD_DC`, `LCD_RES`, `LCD_BL`
- PulseView session source: generate a labeled `.sr` with `tools/vcd_to_sigrok.py`
- Recommended sample rate: `100 MS/s`

## Per-Bitstream Plan

### 1. LCD Test Pattern

Reference: [bringup_lcd_test.md](/Users/bkase/Documents/iceboy/docs/hardware/bringup_lcd_test.md)

- Flash: `iceprog build/bitstreams/lcd_test_pattern.bin`
- Expected behavior: LCD shows the 8-phase test pattern after init.
- Trigger: `LCD_RES` rising edge or first `LCD_CS` low pulse.
- If it fails:
  - dark panel: check power, backlight, and reset
  - no SPI traffic: check PMOD 2 wiring
  - wrong geometry: check offsets and panel assumptions

### 2. ALU Loop

Reference: [bringup_alu_loop.md](/Users/bkase/Documents/iceboy/docs/hardware/bringup_alu_loop.md)

- Flash: `iceprog build/bitstreams/alu_loop_icebreaker.bin`
- Expected behavior: LEDs settle, `DBG_MCE` pulses, `DBG_PC[3:0]` loops through the ALU ROM cadence.
- Trigger: first `DBG_MCE` pulse after reset.
- If it fails:
  - no `DBG_MCE`: clock/reset problem
  - `DBG_MCE` but no PC movement: ROM/bus issue
  - wrong PC cadence: CPU or ROM behavioral bug

### 3. BG Static

Reference: [bringup_bg_static.md](/Users/bkase/Documents/iceboy/docs/hardware/bringup_bg_static.md)

- Flash: `iceprog build/bitstreams/bg_static_icebreaker.bin`
- Expected behavior: LCD transitions to the static tiled background.
- Trigger: `DEBUG_GPIO0` frame-start pulse or `DBG_PHASE2` rising edge.
- If it fails:
  - `DBG_PHASE1=1`: CPU is halted when it should be running
  - `DBG_MCE=0`: LCD init never completed
  - `DBG_PHASE1=0` and no `DBG_PHASE2`: visible pipeline or LCD handoff issue
  - LCD traffic, wrong image: framebuffer or scanout issue
  - no CPU debug: fall back to `alu_loop_icebreaker.bin`

### 4. Joypad Smoke

Reference: [bringup_joypad_smoke.md](/Users/bkase/Documents/iceboy/docs/hardware/bringup_joypad_smoke.md)

- Flash: `iceprog build/bitstreams/joypad_smoke_icebreaker.bin`
- Expected behavior: checkerboard background plus cursor block; buttons change visible state.
- Trigger: `DEBUG_GPIO0` frame-start pulse or `DBG_PHASE2` rising edge.
- If it fails:
  - image but no input: PMOD 1A/button wiring issue
  - no image: fall back to `bg_static_icebreaker.bin`
  - unstable image: inspect LCD SPI and framebuffer timing

### 5. UART ROM Iteration Mode

Reference: [bringup_uart_rom.md](/Users/bkase/Documents/iceboy/docs/hardware/bringup_uart_rom.md)

- Flash: `iceprog build/bitstreams/uart_rom_icebreaker.bin`
- Expected behavior on boot: LCD stays dark while waiting for upload.
- Upload:
  - `python tools/upload_rom_icebreaker.py --rom bench/roms/out/bg_static.gb`
  - after success, LCD transitions from dark to the uploaded ROM output
- Trigger: `DEBUG_GPIO0` dropping after upload or first `DBG_PHASE2` pulse after release.
- If it fails:
  - no serial port: USB/UART enumeration issue
  - `NACK`: bad payload or oversize ROM
  - timeout: wrong bitstream or wrong serial port
  - upload succeeds, `DBG_PHASE1=1`: CPU never left the halted path after upload
  - upload succeeds, `DBG_PHASE1=0`, but no `DBG_PHASE2`: visible path is dead after release

## Known-Good ROM Choices

- `bench/roms/out/alu_loop.gb`
- `bench/roms/out/bg_static.gb`
- `bench/roms/out/joypad_bg_smoke.gb`

For the UART uploader, keep ROMs at `<= 32 KiB`.
