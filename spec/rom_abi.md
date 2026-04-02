# Custom ROM Checkpoint ABI

This document defines the required ABI for all owned Game Boy test ROMs in `iceboy`.
It is the contract between ROM authors, the symbol/hook adapter, and the oracle harness.

## Scope

- Applies to custom ROMs authored for `bench/roms/`.
- Assumes the current CPU bring-up defaults:
  - `ModelProfile = DMG`
  - `ResetProfile = SkipBoot`
  - `MemoryBehaviorProfile = DmgConservative` unless a manifest overrides it deliberately
- Complements, but does not replace, the per-ROM manifest entry in `bench/manifests/rom_inventory.yaml`.

## 1. Symbol File Requirement

Every custom ROM must produce an RGBDS-compatible `.sym` file, typically via:

```sh
rgblink -n out/test.sym -o out/test.gb ...
```

Required executable labels:

- `__pass`
- `__fail`

Optional executable labels:

- `__checkpoint_<name>`
- `__commit_<name>`
- `__inject_begin_<name>`
- `__inject_end_<name>`

These labels must point at executable ROM locations. They must not point into WRAM, HRAM, VRAM, SRAM, or I/O space because the harness uses symbol-driven instruction hooks.

## 2. WRAM Signature Block

Each ROM should expose a versioned WRAM signature block at `0xC000-0xC01F`.

Layout:

| Offset | Size | Meaning |
| --- | --- | --- |
| `0x00` | 1 | ABI version, currently `0x01` |
| `0x01` | 1 | Result byte: `0x00` running, `0x01` pass, `0xFF` fail |
| `0x02` | 2 | Test case count, little-endian |
| `0x04` | 2 | Pass count, little-endian |
| `0x06` | 2 | Fail count, little-endian |
| `0x08` | 8 | Reserved debug counters |
| `0x10` | 16 | ASCII test name, NUL-padded |

This block is the fallback verification path when symbol hooks are unavailable.

## 3. ROM Structure Conventions

- Entry point code begins at `0x0150`.
- Header should be finalized with `rgbfix`.
- ROMs should begin with `DI` unless the test is intentionally about interrupt behavior.
- Tests should be self-contained:
  1. setup
  2. execute
  3. verify
  4. write signature block
  5. jump to `__pass` or `__fail`
- Do not rely on uninitialized memory contents.

## 4. Manifest Integration

Each ROM manifest entry must record:

- `oracle_mode`
- `checkpoint_symbols`
- `compare_scope`
- `memory_behavior_profile`
- `model_profile`
- `reset_profile`

The symbol names recorded in the manifest must be a subset of the optional reserved-label prefixes above.

## 5. Validation Rules

The validator in `bench/tools/validate_rom_abi.py` currently enforces:

- required `__pass` / `__fail` symbols exist in `.sym`
- reserved labels use only the approved prefixes
- reserved labels resolve to executable ROM addresses
- template/source assembly declares:
  - ROM0 entry section at `0x0150`
  - WRAM0 signature section at `0xC000`
  - ABI version byte
  - pass/fail labels

Future ROM pipeline beads can extend validation to assembled ROM binaries and header checks once the assembler toolchain lands.
