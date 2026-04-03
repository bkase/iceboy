from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from test.harness import rom_runner
from test.harness.rom_runner import (
    ABI_LOG_SIZE,
    ABI_RESULT_PASS,
    ABI_RESULT_RUNNING,
    ABI_SIGNATURE_SIZE,
    AbiSnapshot,
    DutTerminalState,
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

    def test_external_memory_bus_tracks_ie_if_mirrors(self) -> None:
        bus = ExternalMemoryBus(bytes(0x8000))

        bus.advance_cycle(
            write_en=True,
            write_addr=0xFFFF,
            write_data=0x04,
            if_set_bits=0,
            irq_ack_valid=False,
            irq_ack_bit=0,
        )
        bus.advance_cycle(
            write_en=True,
            write_addr=0xFF0F,
            write_data=0x04,
            if_set_bits=0,
            irq_ack_valid=False,
            irq_ack_bit=0,
        )
        self.assertEqual(bus.read(0xFFFF), 0x04)
        self.assertEqual(bus.read(0xFF0F), 0x04)

        bus.advance_cycle(
            write_en=False,
            write_addr=0,
            write_data=0,
            if_set_bits=0,
            irq_ack_valid=True,
            irq_ack_bit=2,
        )
        self.assertEqual(bus.read(0xFF0F), 0x00)

    def test_external_memory_bus_emulates_timer_register_progress(self) -> None:
        bus = ExternalMemoryBus(bytes(0x8000))
        bus.advance_cycle(
            write_en=True,
            write_addr=0xFF07,
            write_data=0x05,
            if_set_bits=0,
            irq_ack_valid=False,
            irq_ack_bit=0,
        )

        for _ in range(6):
            if_set_bits = bus.next_if_set_bits(write_en=False, write_addr=0, write_data=0)
            bus.advance_cycle(
                write_en=False,
                write_addr=0,
                write_data=0,
                if_set_bits=if_set_bits,
                irq_ack_valid=False,
                irq_ack_bit=0,
            )

        self.assertEqual(bus.read(0xFF07), 0x05)
        self.assertGreater(bus.read(0xFF05), 0x00)

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

    def test_load_manifest_entry_resolves_wave_b_rom(self) -> None:
        entry = load_manifest_entry("TIMER_DIV_BASIC")
        self.assertEqual(entry.rom_id, "TIMER_DIV_BASIC")
        self.assertEqual(entry.rom_path.name, "timer_div_basic.gb")
        self.assertEqual(entry.sym_path.name, "timer_div_basic.sym")
        self.assertIn("__checkpoint_div_count", entry.checkpoint_symbols)

    def test_assert_rom_matches_pyboy_signature_uses_manifest_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            rom_path = Path(tmpdir) / "alu_flags.gb"
            rom_bytes = bytes([0x3E, 0x12, 0x00])
            rom_path.write_bytes(rom_bytes)
            entry = rom_runner.RomManifestEntry(
                rom_id="ALU_FLAGS",
                rom_path=rom_path,
                sym_path=rom_path.with_suffix(".sym"),
                timeout_commits=17,
                checkpoint_symbols=("__checkpoint_add",),
            )
            abi = AbiSnapshot(signature=bytes([0x00, ABI_RESULT_PASS]) + bytes(ABI_SIGNATURE_SIZE - 2), log=bytes(ABI_LOG_SIZE))
            actual = DutTerminalState(abi=abi, cycles=11)
            run_dut = AsyncMock(return_value=actual)

            with (
                patch.object(rom_runner, "load_manifest_entry", return_value=entry),
                patch.object(rom_runner, "build_manifest", return_value=object()),
                patch.object(rom_runner, "run_oracle_to_terminal", return_value=(("__pass",), abi)),
                patch.object(rom_runner, "run_dut_to_abi_result", run_dut),
            ):
                result = asyncio.run(
                    rom_runner.assert_rom_matches_pyboy_signature(
                        object(),
                        rom_id="ALU_FLAGS",
                        max_mcycles=99,
                    )
                )

        self.assertEqual(result, actual)
        run_dut.assert_awaited_once_with(
            unittest.mock.ANY,
            rom_bytes=rom_bytes,
            max_mcycles=17,
        )


if __name__ == "__main__":
    unittest.main()
