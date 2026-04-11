# iceboy

`iceboy` is a Game Boy hardware project centered on a DMG-style SoC written in Spade, with simulation, differential testing, and FPGA bring-up support in the same repository.

The repo contains:

- `src/`: CPU, PPU, bus, DMA, joypad, timer, and board-level hardware
- `test/`: unit, integration, ROM, and harness-driven regression coverage
- `tools/`: Verilator runners, ROM utilities, frame capture scripts, and gate scripts
- `bench/`: external suites, owned repro ROMs, and reference artifacts
- `docs/`: project notes, behavior references, and implementation details

## Current Focus

The project is aimed at high-fidelity DMG behavior, with a strong emphasis on:

- cycle-sensitive CPU/PPU interaction
- Pan Docs and mealybug-style raster correctness
- native Verilator playback and ROM-based regression testing
- differential comparison against external oracles such as PyBoy where useful

## Common Workflows

Build the hardware:

```bash
swim build
```

Run a focused unit test:

```bash
swim test test/ppu/unit/test_obj_penalty.py
```

Run a native Verilator ROM harness:

```bash
bash tools/run_dmg_acid2_verilator.sh --skip-build
```

Generate a native Pokemon Red playback video:

```bash
bash tools/run_pokered_playback_verilator.sh --skip-build
```

## Beads Workflow

Work is tracked in `.beads/` with `br` / `bd`.

Typical flow:

```bash
br ready
br show <id>
br update <id> --status=in_progress
br close <id> --reason="Completed"
```

## Notes

- Commit hooks run the curated precommit coverage automatically on `git commit`.
- For longer-running ROM/playback checks, prefer the native C++/Verilator harness over cocotb-style Python driving.
- The default cutoff for that preference is roughly `50_000` M-cycles.
