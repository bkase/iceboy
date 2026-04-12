# EBR ROM Synth Probe

`bd-13nr` measures whether a nonzero initialized `clocked_memory_init` ROM can map to iCE40UP5K EBR (`SB_RAM40_4K`) rather than collapsing into LUT logic.

## Probe Shape

- Source: `src/mem/phys/ebr_rom_probe_top.spade`
- Construct under test: direct `clocked_memory_init`, not `dp_bram`
- Logical size: `1 KiB`
- Physical probe shape: `256 x 32-bit` words

The probe uses `256 x 32-bit` words instead of `1024 x 8-bit` bytes only to keep the compile-time literal manageable in Spade. The total stored data is still `8192` bits, so a successful EBR mapping would still need at least `2` `SB_RAM40_4K` blocks.

## Command

```bash
tools/run_ebr_rom_synth_probe.sh
```

## Measurement

- `SB_RAM40_4K = 0`
- `SB_LUT4 = 30`
- `SB_DFF = 0`

This came from the synthesized `ebr_rom_probe_top` netlist in `build/hw_probes/ebr_rom/` on April 12, 2026.

## Decision

`Decision: NO-GO`

Direct Spade `clocked_memory_init` with a baked nonzero image does **not** map to EBR on this flow. The initialized array stayed in logic instead of becoming `SB_RAM40_4K`.

## Chosen Pivot

`Option b1`

For `bd-29bw` (`rom_baked_ebr.spade`), pivot to a Verilog wrapper that loads ROM contents with `$readmemh`, then import that wrapper into Spade via `extern entity`. That keeps the ROM genuinely block-backed instead of relying on initialized Spade arrays.

## Follow-On Constraint

- `bd-29bw` must not use `dp_bram`; it cannot carry init data.
- `bd-29bw` must not use direct initialized `clocked_memory_init` as the final hardware ROM implementation on this flow.
- The synth probe script intentionally exits nonzero while the gate is red so the no-go result stays explicit.
