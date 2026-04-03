from __future__ import annotations

import tempfile
import unittest
import warnings
from pathlib import Path

from bench.actions.generators import IeOverrideEvent, IfClearBitsEvent, IfSetBitsEvent, MemoryWriteEvent
from bench.pyboy.oracle import CommitPoint, PyBoyOracle
from roms.build_micro_rom import build_alu_loop
from spec.profiles import ModelProfile, ResetProfile


HOOK_ADDRS = (0x0150, 0x0152, 0x0154, 0x0155, 0x0156)


class PyBoyOracleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        warnings.filterwarnings("ignore", message="Using SDL2 binaries from pysdl2-dll.*")
        cls._tmpdir = tempfile.TemporaryDirectory()
        cls.rom_path = Path(cls._tmpdir.name) / "alu_loop.gb"
        cls.rom_path.write_bytes(build_alu_loop())
        cls.commit_points = tuple(
            CommitPoint(bank=0, addr=addr, label=f"hook_{addr:04X}") for addr in HOOK_ADDRS
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmpdir.cleanup()

    def make_oracle(self) -> PyBoyOracle:
        return PyBoyOracle(self.rom_path, commit_points=self.commit_points)

    def test_step_commit_replays_deterministically_after_restore(self) -> None:
        with self.make_oracle() as oracle:
            oracle.reset(ModelProfile.DMG, ResetProfile.SkipBoot)

            first = oracle.step_commit()
            self.assertEqual(first.label, "hook_0150")
            self.assertEqual(first.pc_before, 0x0150)
            self.assertEqual(first.opcode, 0x3E)

            snapshot = oracle.snapshot()
            expected = [oracle.step_commit() for _ in range(3)]

            oracle.restore(snapshot)
            replayed = [oracle.step_commit() for _ in range(3)]

            self.assertEqual(expected, replayed)

    def test_memory_write_events_round_trip_through_snapshot(self) -> None:
        with self.make_oracle() as oracle:
            oracle.reset(ModelProfile.DMG, ResetProfile.SkipBoot)

            oracle.write_event(MemoryWriteEvent(addr=0xC100, value=0x34))
            self.assertEqual(oracle.read_mem(0xC100), 0x34)

            snapshot = oracle.snapshot()
            oracle.write_event(MemoryWriteEvent(addr=0xC100, value=0x99))
            self.assertEqual(oracle.read_mem(0xC100), 0x99)

            oracle.restore(snapshot)
            self.assertEqual(oracle.read_mem(0xC100), 0x34)

    def test_interrupt_sideband_events_update_if_and_ie(self) -> None:
        with self.make_oracle() as oracle:
            oracle.reset(ModelProfile.DMG, ResetProfile.SkipBoot)

            oracle.write_event(IeOverrideEvent(value=0x1B))
            self.assertEqual(oracle.read_mem(0xFFFF) & 0x1F, 0x1B)

            oracle.write_event(IfSetBitsEvent(bits=0x05))
            self.assertEqual(oracle.read_mem(0xFF0F) & 0x1F, 0x05)

            oracle.write_event(IfSetBitsEvent(bits=0x08))
            self.assertEqual(oracle.read_mem(0xFF0F) & 0x1F, 0x0D)

            oracle.write_event(IfClearBitsEvent(bits=0x09))
            self.assertEqual(oracle.read_mem(0xFF0F) & 0x1F, 0x04)

    def test_skipboot_reset_applies_dmg_post_boot_register_state(self) -> None:
        with self.make_oracle() as oracle:
            oracle.reset(ModelProfile.DMG, ResetProfile.SkipBoot)
            rf = oracle._require_pyboy().register_file
            self.assertEqual(int(rf.A), 0x01)
            self.assertEqual(int(rf.F), 0xB0)
            self.assertEqual(int(rf.B), 0x00)
            self.assertEqual(int(rf.C), 0x13)
            self.assertEqual(int(rf.D), 0x00)
            self.assertEqual(int(rf.E), 0xD8)
            self.assertEqual(int(rf.HL), 0x014D)
            self.assertEqual(int(rf.SP), 0xFFFE)
            self.assertEqual(int(rf.PC), 0x0100)
            self.assertEqual(oracle.read_mem(0xFF40), 0x91)
            self.assertEqual(oracle.read_mem(0xFF47), 0xFC)


if __name__ == "__main__":
    unittest.main()
