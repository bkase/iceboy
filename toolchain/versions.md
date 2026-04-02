# Toolchain Versions

## Python Oracle Layer

- PyBoy: `2.7.0`
- Source: `https://pypi.org/project/pyboy/`
- Python requirement: `>=3.9`
- Cocotb: `1.9.2`
- Source: `https://pypi.org/project/cocotb/`
- Compatibility note: `spade 0.17.0` currently expects `cocotb~=1.9.2`
- PyYAML: `6.0.3`
- Usage note: used for tracked manifest schema and inventory validation via `uv run --with-requirements toolchain/python.lock python tools/validate_rom_manifests.py`

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
- Spade compiler commit: `2f50feec89d7f72d406d74ddfa81d79add58e500`
- Pin source: `swim.lock`
- Project config: `swim.toml` pins `testbench_dir = "test"`, `simulator = "icarus"`, `synthesis.top = "icebreaker_top"`, and the `iCE40UP5K` / `sg48` target tuple

## SM83 ROM Toolchain

- `rgbds`: `1.0.1`
- Installed tools: `rgbasm`, `rgblink`, `rgbfix`
- Install path used on this machine: `nix profile install nixpkgs#rgbds`
- Verification commands:
  - `rgbasm --version`
  - `rgblink --version`
  - `rgbfix --version`
- Project pipeline: `bench/roms/build_roms.sh` builds `bench/roms/*.asm` into `bench/roms/out/` and validates each ROM + `.sym` pair against the checkpoint ABI

## Simulator Backend Policy

- Default simulator for authored development loops: `icarus`
- Optional long-regression backend: `verilator`
- Local machine verification currently has Verilator available at `/opt/homebrew/bin/verilator` (`5.046`)
- Rationale: keep all authored tests in Python/Cocotb, use the simpler backend by default, and reserve Verilator for longer-running regressions rather than maintaining a separate C++ test lane
- Supported entry points for the Verilator lane are `tools/run_tests.py --sim verilator`, `tools/smoke.sh --sim verilator`, and `tools/regress.sh --sim verilator`
- Local caveat: raw batched `SIM=verilator swim test test_` runs can race in generated build directories on the current toolchain; use the unified runner entry points above, which invoke the Cocotb benches one at a time

## Synthesis / P&R / Formal Toolchain

- Primary EDA distribution: `oss-cad-suite-darwin-arm64-20260401`
- Provisioning path: `~/.cargo/bin/swim install-tools`
- Compatibility note: this repo expects the `oss-cad-suite` cohort to supply a mutually compatible `yosys` + `nextpnr-ice40` + `icestorm` + `sby` stack rather than mixing unrelated package builds

### Synthesis

- `yosys`: `0.63+188` (`git sha1 cede13a74-dirty`)
- Verification command: `build/oss-cad-suite/bin/yosys -V`
- Install path: bundled by `swim install-tools`
- Compatibility note: verified local binary provides `synth_ice40`, which is the command used by `swim.toml`
- Project-level verification: `~/.cargo/bin/swim synth` succeeds and emits synthesized build artifacts for the current trivial top

### Place and Route

- `nextpnr-ice40`: `nextpnr-0.10-15-g77ccf518`
- Verification command: `build/oss-cad-suite/bin/nextpnr-ice40 --version`
- Install path: bundled by `swim install-tools`
- Compatibility note: paired with the same `oss-cad-suite` cohort as Yosys for iCE40UP5K work

### IceStorm Packing / Programming

- `icepack` / `iceprog`: pinned as part of the bundled `icestorm` package in `oss-cad-suite-darwin-arm64-20260401`
- Verification commands:
  - `build/oss-cad-suite/bin/icepack -h`
  - `build/oss-cad-suite/libexec/iceprog --help`
- Install path: bundled by `swim install-tools`
- Compatibility note: the local binaries do not print a standalone semantic version, so the suite cohort (`20260401`) is the reproducible pin for these utilities

### Formal

- `SymbiYosys (sby)`: `0.63-11-g6424d15`
- Verification command: `build/oss-cad-suite/bin/sby --version`
- Install path: bundled by `swim install-tools`
- Compatibility note: matches the bundled Yosys generation and should be kept in the same suite cohort

- Optional formal/equivalence helpers also present in the same suite cohort:
  - `eqy` via `build/oss-cad-suite/bin/eqy`
  - `yosys-smtbmc` via `build/oss-cad-suite/bin/yosys-smtbmc`

- Optional local SMT/formal backends can come from the suite or Nix as needed, but should be recorded alongside the suite cohort if they become required by a future bead

### Optional HDL Frontends / Backends

- `ghdl`: bundled in `oss-cad-suite-darwin-arm64-20260401`
- Install path: bundled by `swim install-tools`
- Local caveat: the current macOS binary emits duplicate `LC_RPATH` loader warnings before reporting a usable version string, so treat it as available-but-not-yet-qualified for this repo

- `iverilog`: `13.0` (`stable`, `v13_0`)
- Verification command: `iverilog -V`
- Install path used on this machine: `nix profile install nixpkgs#iverilog`
- Compatibility note: selected as the default authored-test backend for initial development per §16.4
