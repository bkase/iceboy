#!/usr/bin/env python3
"""Exercise the direct oracle smoke path from a clean checkout."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bench.pyboy.oracle import PyBoyOracle
from bench.pyboy.symbols import SymbolTable
from roms.build_micro_rom import build_alu_loop
from spec.profiles import ModelProfile, ResetProfile


SYMBOL_TEXT = """\
00:0150 __commit_init
00:0154 __commit_loop
00:0155 __pass
"""


def write_oracle_fixture(tempdir: str | Path) -> tuple[Path, Path]:
    root = Path(tempdir)
    rom_path = root / "alu_loop.gb"
    sym_path = root / "alu_loop.sym"
    rom_path.write_bytes(build_alu_loop())
    sym_path.write_text(SYMBOL_TEXT, encoding="utf-8")
    return rom_path, sym_path


def main() -> None:
    with tempfile.TemporaryDirectory() as tempdir:
        rom_path, sym_path = write_oracle_fixture(tempdir)
        table = SymbolTable.load(sym_path)
        commit_symbol = table.lookup("__commit_loop")
        assert (commit_symbol.bank, commit_symbol.addr) == (0, 0x0154)

        with PyBoyOracle(rom_path, sym_path=sym_path) as oracle:
            oracle.reset(ModelProfile.DMG, ResetProfile.SkipBoot)
            first = oracle.step_commit()
            assert first.label is not None and "__commit_" in first.label

            snapshot = oracle.snapshot()
            expected = [oracle.step_commit() for _ in range(3)]

            table = SymbolTable.load(sym_path)
            assert table.lookup("__pass").addr == 0x0155

            oracle.restore(snapshot)
            replayed = [oracle.step_commit() for _ in range(3)]
            assert expected == replayed

    print("Oracle smoke verification passed.")


if __name__ == "__main__":
    main()
