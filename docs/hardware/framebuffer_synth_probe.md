# Framebuffer SPRAM Synth Probe

`bd-2gd2` measures whether a minimal framebuffer probe can stay within a single iCE40UP5K `SB_SPRAM256KA` while keeping the surrounding control logic small.

## Probe Shape

- Source: `src/video/framebuffer_probe_top.spade`
- Memory primitive under test: `SB_SPRAM256KA`
- Addressing model: one shared address bus, write priority over reads
- Write side: simple byte pattern generator
- Read side: pointer advances only when `ready_i` is asserted

The probe intentionally time-multiplexes write and read traffic onto one SPRAM port so the synthesis result answers the real implementation question for `Bi4.9`: whether a small arbiter plus byte-lane handling still fits cleanly inside the target budget.

## Command

```bash
tools/run_framebuffer_synth_probe.sh
```

## Measurement

- `SB_SPRAM256KA = 1`
- `SB_LUT4 = 93`
- `SB_DFF = 42`
- `SB_RAM40_4K = 0`

This came from the synthesized `framebuffer_probe_top` netlist in `build/hw_probes/framebuffer/` on April 12, 2026.

## Decision

`Decision: GO`

The single-port framebuffer probe fits the intended envelope:

- exactly one SPRAM block
- no EBR usage
- LUT cost comfortably below the `< 200` target
- DFF cost comfortably below the `< 50` target

## Implication For `Bi4.9`

The one-SPRAM framebuffer approach remains viable. A write-priority arbiter plus read-ready gating does not force extra memory blocks and leaves enough logic headroom for the follow-on framebuffer work in `bd-299z`.
