# Toolchain Versions

## Python Oracle Layer

- PyBoy: `2.7.0`
- Source: `https://pypi.org/project/pyboy/`
- Python requirement: `>=3.9`
- Cocotb: `1.9.2`
- Source: `https://pypi.org/project/cocotb/`
- Compatibility note: `spade 0.17.0` currently expects `cocotb~=1.9.2`

## PyBoy Headless Configuration

For non-visual oracle and regression suites, initialize PyBoy with:

- `window="null"`
- `sound_emulated=False`
- `no_input=True`
- `set_emulation_speed(0)` for unlimited-speed execution

## PyBoy APIs We Depend On

The oracle layer and future hook-driven adapter rely on these public APIs from `https://docs.pyboy.dk/`:

- `PyBoy(...)` constructor with `window`, `sound_emulated`, `no_input`, `symbols`, and `bootrom`
- `tick(count=1, render=True, sound=True)` for advancing execution
- `set_emulation_speed(speed)` for uncapped headless runs
- `hook_register(bank, addr, callback, context)` and `hook_deregister(...)` for instruction-boundary callbacks
- `register_file` with `A`, `F`, `B`, `C`, `D`, `E`, `HL`, `SP`, and `PC`
- `memory[...]` for direct RAM/register reads and writes
- `save_state(file_like)` and `load_state(file_like)` for snapshot and restore
- `symbol_lookup(symbol)` for future symbol-driven hooks
- `cartridge_title` for ROM identity checks

## Spade / Simulation Tooling

- `swim`: `v0.17.0-r314-a9f0731`
- Spade compiler pin: tracked in `swim.lock`

## Simulator Backend Policy

- Default simulator for authored development loops: `icarus`
- Optional long-regression backend: `verilator`
- Local machine verification currently has Verilator available at `/opt/homebrew/bin/verilator` (`5.046`)
- Rationale: keep all authored tests in Python/Cocotb, use the simpler backend by default, and reserve Verilator for longer-running regressions rather than maintaining a separate C++ test lane
