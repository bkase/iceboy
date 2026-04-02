from __future__ import annotations

import tempfile
import unittest
import warnings
from pathlib import Path

from bench.pyboy.oracle import CommitPoint, MemoryWriteEvent, PyBoyOracle
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


if __name__ == "__main__":
    unittest.main()
