#!/usr/bin/env python3
"""Smoke-verify the pinned PyBoy oracle flow in headless mode."""

from __future__ import annotations

import io
import sys
import tempfile
from pathlib import Path

from pyboy import PyBoy

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from roms.build_micro_rom import build_alu_loop


HOOK_ADDRS = (0x0150, 0x0152, 0x0154, 0x0155, 0x0156)


def record_hook(pyboy: PyBoy) -> None:
    pyboy.memory[0xC000] = (pyboy.memory[0xC000] + 1) & 0xFF


def main() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        rom_path = Path(tmpdir) / "alu_loop.gb"
        rom_path.write_bytes(build_alu_loop())

        with PyBoy(
            str(rom_path),
            window="null",
            sound_emulated=False,
            no_input=True,
            log_level="ERROR",
        ) as pyboy:
            pyboy.set_emulation_speed(0)

            assert pyboy.cartridge_title == "ALU_LOOP", pyboy.cartridge_title

            pyboy.memory[0xC000] = 0
            for addr in HOOK_ADDRS:
                pyboy.hook_register(0, addr, record_hook, pyboy)

            # Hooks give us instruction-boundary observability while running headless.
            pyboy.tick(70, False, False)

            hook_hits = pyboy.memory[0xC000]
            assert hook_hits >= len(HOOK_ADDRS), hook_hits

            register_file = pyboy.register_file
            assert register_file.PC >= 0x0150, register_file.PC
            assert register_file.A != 0 or register_file.B != 0

            pyboy.memory[0xC100] = 0x34
            assert pyboy.memory[0xC100] == 0x34

            snapshot = io.BytesIO()
            pyboy.save_state(snapshot)

            saved_a = register_file.A
            saved_pc = register_file.PC
            saved_mem = pyboy.memory[0xC100]

            register_file.A = 0x77
            register_file.PC = 0x0150
            pyboy.memory[0xC100] = 0x99

            snapshot.seek(0)
            pyboy.load_state(snapshot)

            assert register_file.A == saved_a, (register_file.A, saved_a)
            assert register_file.PC == saved_pc, (register_file.PC, saved_pc)
            assert pyboy.memory[0xC100] == saved_mem, (pyboy.memory[0xC100], saved_mem)

    print("PyBoy headless smoke verification passed.")


if __name__ == "__main__":
    main()
