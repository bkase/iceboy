# iCEBreaker UART ROM Bring-Up

`build/bitstreams/uart_rom_icebreaker.bin` is the iteration-speed hardware image for the UART uploader ladder. Flash this once, then swap ROM payloads with `tools/upload_rom_icebreaker.py` instead of rebuilding the bitstream.

## Artifacts

- Bitstream: `build/bitstreams/uart_rom_icebreaker.bin`
- Packed from: `build/bitstreams/uart_rom_icebreaker.asc`
- Baseline report: [uart_rom_top_baseline.json](/Users/bkase/Documents/iceboy/docs/hardware/uart_rom_top_baseline.json)
- Host uploader: [tools/upload_rom_icebreaker.py](/Users/bkase/Documents/iceboy/tools/upload_rom_icebreaker.py)
- Native full-stack oracle: `tools/run_icebreaker_uart_rom_verilator.sh --skip-build`
- Bitstream size: `104090` bytes
- Binary roundtrip: stable under `icepack -> iceunpack -> icepack`
- ASC roundtrip: functionally equivalent, but `iceunpack` normalizes comments and layout

## Measured Hardware Budget

- `SB_LUT4 = 4957`
- `SB_DFF = 757`
- `SB_SPRAM256KA = 3`
- `SB_RAM40_4K = 17`
- `ICESTORM_LC = 5240 / 5280`
- Achieved clock: `10.05 MHz` against a `12.0 MHz` target

This top now places and routes successfully on the UP5K, but it still misses the 12 MHz target. Treat it as a valid packaged bring-up image with a timing-risk note, not a timing-clean production image.

## Flash Procedure

1. Program the UART uploader bitstream:
   `iceprog build/bitstreams/uart_rom_icebreaker.bin`
2. Power-cycle or press `BTN_N` after programming if your board does not auto-reload.
3. On boot, expect the LCD to remain dark while the top waits for an upload.

LED expectations before upload:
- `LEDR_N`: follows `upload_hold`; while the uploader is waiting, the red LED should appear asserted.
- `LEDG_N`: held active while the core is still under uploader reset.

## Upload Procedure

1. Choose any supported ROM at or below `32 KiB`.
2. Run:
   `python tools/upload_rom_icebreaker.py --rom <path.gb>`
3. Optional sanity path before touching hardware:
   `python tools/upload_rom_icebreaker.py --rom <path.gb> --dry-run`

Expected host responses:
- success: `Upload OK`
- checksum failure or oversize rejection: `Upload failed (DUT reported NACK)`
- no board response: `Upload timed out`
- no serial port found: attach the board or pass `--port`

Protocol summary:
- frame prefix: `ROM!`
- length field: little-endian `uint16`
- payload checksum: 1-byte XOR checksum of the payload
- success ACK byte: `A`
- failure ACK byte: `N`

## Expected Hardware Behavior

1. Before upload, the LCD stays dark and the CPU core remains held in reset.
2. After a valid upload completes, the host prints `Upload OK`.
3. The LCD transitions from dark to the uploaded ROM’s rendered output.
4. `tools/run_icebreaker_uart_rom_verilator.sh --skip-build` is the reference oracle for this transition and currently matches `24` completed visible frames after upload.

Known working ROMs:
- `bench/roms/out/alu_loop.gb`
- `bench/roms/out/bg_static.gb`
- `bench/roms/out/joypad_bg_smoke.gb`
- any other ROM from `bench/roms/out/` that is `<= 32 KiB`

## Troubleshooting

- `no serial port found`:
  Check the USB cable, board power, and enumerate `/dev/tty.usbserial-*`; on Linux also check `dmesg`.
- `Upload failed (DUT reported NACK)`:
  Retry the transfer, confirm the ROM is `<= 32 KiB`, and re-run `--dry-run` if you suspect a bad payload.
- `Upload timed out`:
  Confirm the UART uploader bitstream is actually flashed and that `--port` points at the board.
- upload succeeds but nothing appears on the LCD:
  Check that `LEDR_N` drops after upload, then probe the LCD SPI pins and PMOD debug signals for post-upload activity.
- uploader path looks alive but rendering never starts:
  Verify the ROM itself is known-good by comparing against the native oracle or one of the reference visible tops.

## Debug Cues

Shared PMOD 1B debug bus:
- `DBG_PC0..DBG_PC3`: held low
- `DBG_MCE`: held low
- `DBG_PHASE0`: held low
- `DBG_PHASE1`: CPU halted flag
- `DBG_PHASE2`: visible scanout-valid pulse

Variant-specific PMOD 2 extras:
- `DEBUG_GPIO0`: upload hold indicator
- `DEBUG_GPIO1`: UART TX busy indicator

If `DEBUG_GPIO0` never drops after `Upload OK`, the core was not released. If `DEBUG_GPIO0` drops but `DBG_PHASE2` stays quiet, the upload path worked and the failure is downstream in ROM execution or scanout.
