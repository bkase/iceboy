# Toolchain Versions

## Python Oracle Layer

- PyBoy: `2.7.0`
- Source: `https://pypi.org/project/pyboy/`
- Python requirement: `>=3.9`

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
