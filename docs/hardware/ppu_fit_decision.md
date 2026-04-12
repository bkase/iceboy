# Gate 3 fit decision: full `hardware_soc_core`

Full `hardware_soc_core` with `ppu_core_hw`, `vram_ebr`, and `rom_baked_ebr` does not fit the iCE40UP5K. The project should pivot to the conditional `PpuBgWindow` profile bead (`bd-24li`) before any visible-top or LCD integration work continues.

## Measured probe

- Board top: `board::icebreaker_hardware_soc_core_fit_top::icebreaker_hardware_soc_core_fit_top`
- Command:
  `tools/build_icebreaker_variant.sh --top board::icebreaker_hardware_soc_core_fit_top::icebreaker_hardware_soc_core_fit_top --module icebreaker_hardware_soc_core_fit_top --board-top src/board/icebreaker_hardware_soc_core_fit_top.spade --out-dir build/hw_probes/hardware_soc_core_full --record-json docs/hardware/hardware_soc_core_full_baseline.json --skip-build`
- Artifacts:
  `build/hw_probes/hardware_soc_core_full/synth/yosys-stat.txt`
  `build/hw_probes/hardware_soc_core_full/nextpnr.log`
  `docs/hardware/hardware_soc_core_full_baseline.json`

## Result

- `SB_LUT4 = 6637` vs budget `5280` (`+1357`, `125.7%` of budget)
- `SB_DFF = 1055` vs budget `1024` (`+31`)
- `SB_SPRAM256KA = 1` vs budget `4`
- `SB_RAM40_4K = 21` vs budget `30`
- `ICESTORM_LC = 7650 / 5280` (`144%`)
- Place-and-route failed before timing analysis:
  `ERROR: Unable to place cell ... no BELs remaining to implement cell type 'ICESTORM_LC'`

This is not an EBR-pressure problem. The full-PPI build is already over both LUT4 and DFF budget while still leaving `9` EBRs and `3` SPRAM blocks unused. Moving ROM back into SPRAM would free only `2` EBRs and would not address the actual limiting resources.

## Decision

Outcome `(c)`: full PPU does not fit.

Proceed with `bd-24li` and gate the visible path down to the `PpuBgWindow` profile:

- remove the OBJ path (`oam_scan`, `obj_fetch`, `obj_penalty`, OBJ FIFO, OBJ-over-BG mixing`)
- remeasure against the same board-top probe
- keep `rom_baked_ebr` for now unless a later reduced-profile measurement shows EBR, not LUT/DFF, becoming the binding constraint

`bd-1u8i` and the later visible-top beads stay blocked on that profile reduction.
