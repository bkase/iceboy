from __future__ import annotations

import unittest

from test.harness.rom_runner import (
    ABI_RESULT_PASS,
    ABI_RESULT_RUNNING,
    ExternalMemoryBus,
    load_manifest_entry,
)


class RomRunnerTest(unittest.TestCase):
    def test_external_memory_bus_maps_rom_wram_and_hram(self) -> None:
        bus = ExternalMemoryBus(bytes([value & 0xFF for value in range(0x8000)]))
        self.assertEqual(bus.read(0x0012), 0x12)
        self.assertEqual(bus.read(0x8123), 0xFF)

        bus.write(0xC123, 0x5A)
        bus.write(0xFF80, 0xC3)
        bus.write(0x0150, 0x99)

        self.assertEqual(bus.read(0xC123), 0x5A)
        self.assertEqual(bus.read(0xFF80), 0xC3)
        self.assertEqual(bus.read(0x0150), 0x50)

    def test_abi_snapshot_tracks_result_and_log_bytes(self) -> None:
        bus = ExternalMemoryBus(bytes(0x8000))
        snapshot = bus.abi_snapshot()
        self.assertEqual(snapshot.result, ABI_RESULT_RUNNING)

        bus.write(0xC001, ABI_RESULT_PASS)
        bus.write(0xC020, 0x34)
        bus.write(0xC025, 0xAB)
        snapshot = bus.abi_snapshot()
        self.assertEqual(snapshot.result, ABI_RESULT_PASS)
        self.assertEqual(snapshot.log[0], 0x34)
        self.assertEqual(snapshot.log[5], 0xAB)

    def test_load_manifest_entry_resolves_wave_a_rom(self) -> None:
        entry = load_manifest_entry("LOADS_BASIC")
        self.assertEqual(entry.rom_id, "LOADS_BASIC")
        self.assertTrue(entry.rom_path.name.endswith(".gb"))
        self.assertTrue(entry.sym_path.name.endswith(".sym"))
        self.assertGreater(entry.timeout_commits, 0)
        self.assertIn("__checkpoint_ld_r_r", entry.checkpoint_symbols)


if __name__ == "__main__":
    unittest.main()
