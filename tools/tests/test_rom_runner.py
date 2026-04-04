from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from bench.actions.generators import JoypadButtons, JoypadButtonsEvent
from test.harness import rom_runner
from test.harness.dut_driver import JoypadState, SimStimulus
from test.harness.rom_runner import (
    ABI_LOG_SIZE,
    ABI_RESULT_PASS,
    ABI_RESULT_RUNNING,
    ABI_SIGNATURE_SIZE,
    JOYPAD_IF_BIT,
    AbiSnapshot,
    DutTerminalState,
    ExternalMemoryBus,
    _ScriptedJoypadOracleState,
    load_manifest_entry,
)


class RomRunnerTest(unittest.TestCase):
    @staticmethod
    def build_banked_rom(*, bank_count: int, cart_type: int, ram_size_code: int) -> bytes:
        rom = bytearray(bank_count * 0x4000)
        for bank in range(bank_count):
            start = bank * 0x4000
            rom[start : start + 0x4000] = bytes([bank & 0xFF]) * 0x4000
        rom[0x0147] = cart_type & 0xFF
        rom[0x0149] = ram_size_code & 0xFF
        return bytes(rom)

    @staticmethod
    def build_mbc1_rom(*, bank_count: int, cart_type: int = 0x03, ram_size_code: int = 0x03) -> bytes:
        return RomRunnerTest.build_banked_rom(bank_count=bank_count, cart_type=cart_type, ram_size_code=ram_size_code)

    @staticmethod
    def build_mbc3_rom(*, bank_count: int, cart_type: int = 0x13, ram_size_code: int = 0x03) -> bytes:
        return RomRunnerTest.build_banked_rom(bank_count=bank_count, cart_type=cart_type, ram_size_code=ram_size_code)

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

    def test_external_memory_bus_models_mbc1_rom_bank_switching(self) -> None:
        bus = ExternalMemoryBus(self.build_mbc1_rom(bank_count=64, cart_type=0x01, ram_size_code=0x00))

        self.assertEqual(bus.read(0x0150), 0x00)
        self.assertEqual(bus.read(0x4000), 0x01)

        bus.write(0x2000, 0x00)
        self.assertEqual(bus.read(0x4000), 0x01)

        bus.write(0x2000, 0x02)
        self.assertEqual(bus.read(0x4000), 0x02)

        bus.write(0x4000, 0x01)
        bus.write(0x2000, 0x00)
        self.assertEqual(bus.read(0x4000), 0x21)

        bus.write(0x6000, 0x01)
        self.assertEqual(bus.read(0x0150), 0x20)
        self.assertEqual(bus.read(0x4000), 0x21)

    def test_external_memory_bus_models_mbc1_ram_enable_and_banking(self) -> None:
        bus = ExternalMemoryBus(self.build_mbc1_rom(bank_count=8, cart_type=0x03, ram_size_code=0x03))

        self.assertEqual(bus.read(0xA000), 0xFF)
        bus.write(0xA000, 0x11)
        self.assertEqual(bus.read(0xA000), 0xFF)

        bus.write(0x0000, 0x0A)
        bus.write(0xA000, 0x12)
        self.assertEqual(bus.read(0xA000), 0x12)

        bus.write(0x6000, 0x01)
        bus.write(0x4000, 0x02)
        bus.write(0xA000, 0x34)
        self.assertEqual(bus.read(0xA000), 0x34)

        bus.write(0x4000, 0x00)
        self.assertEqual(bus.read(0xA000), 0x12)

        bus.write(0x4000, 0x02)
        self.assertEqual(bus.read(0xA000), 0x34)

        bus.write(0x0000, 0x00)
        self.assertEqual(bus.read(0xA000), 0xFF)

    def test_external_memory_bus_models_mbc3_rom_bank_switching(self) -> None:
        bus = ExternalMemoryBus(self.build_mbc3_rom(bank_count=128, cart_type=0x11, ram_size_code=0x00))

        self.assertEqual(bus.read(0x0150), 0x00)
        self.assertEqual(bus.read(0x4000), 0x01)

        bus.write(0x2000, 0x00)
        self.assertEqual(bus.read(0x4000), 0x01)

        bus.write(0x2000, 0x20)
        self.assertEqual(bus.read(0x4000), 0x20)

        bus.write(0x2000, 0x40)
        self.assertEqual(bus.read(0x4000), 0x40)

        bus.write(0x2000, 0x7F)
        self.assertEqual(bus.read(0x4000), 0x7F)

    def test_external_memory_bus_models_mbc3_ram_enable_banking_and_stub_rtc(self) -> None:
        bus = ExternalMemoryBus(self.build_mbc3_rom(bank_count=16, cart_type=0x13, ram_size_code=0x03))

        self.assertEqual(bus.read(0xA000), 0xFF)
        bus.write(0xA000, 0x11)
        self.assertEqual(bus.read(0xA000), 0xFF)

        bus.write(0x0000, 0x0A)
        bus.write(0x4000, 0x00)
        bus.write(0xA000, 0x12)
        self.assertEqual(bus.read(0xA000), 0x12)

        bus.write(0x4000, 0x03)
        bus.write(0xA000, 0x34)
        self.assertEqual(bus.read(0xA000), 0x34)

        bus.write(0x4000, 0x00)
        self.assertEqual(bus.read(0xA000), 0x12)

        bus.write(0x4000, 0x08)
        self.assertEqual(bus.read(0xA000), 0x00)
        bus.write(0xA000, 0x56)
        self.assertEqual(bus.read(0xA000), 0x00)
        bus.write(0x6000, 0x00)
        bus.write(0x6000, 0x01)
        self.assertEqual(bus.read(0xA000), 0x56)

        bus.write(0x0000, 0x00)
        self.assertEqual(bus.read(0xA000), 0xFF)

    def test_external_memory_bus_models_joyp_selection_and_press_edges(self) -> None:
        bus = ExternalMemoryBus(bytes(0x8000))
        self.assertEqual(bus.read(0xFF00), 0xFF)

        bus.write(0xFF00, 0x20)
        joyp_irq = bus.apply_stimulus(SimStimulus(joyp_buttons=JoypadState(left=True)))
        self.assertEqual(joyp_irq, 0x10)
        self.assertEqual(bus.read(0xFF00), 0xED)

        joyp_irq = bus.apply_stimulus(SimStimulus(joyp_buttons=JoypadState()))
        self.assertEqual(joyp_irq, 0x00)
        self.assertEqual(bus.read(0xFF00), 0xEF)

        bus.write(0xFF00, 0x10)
        bus.apply_stimulus(SimStimulus(joyp_buttons=JoypadState(start=True)))
        self.assertEqual(bus.read(0xFF00), 0xD7)

    def test_scripted_joypad_oracle_state_tracks_persistent_buttons_and_fresh_press_if(self) -> None:
        state = _ScriptedJoypadOracleState()

        class _Schedule:
            def __init__(self) -> None:
                self._events = {
                    0: (JoypadButtonsEvent(JoypadButtons.from_pressed(["left"])),),
                    1: (JoypadButtonsEvent(JoypadButtons.from_pressed(["start"])),),
                    2: (JoypadButtonsEvent(JoypadButtons()),),
                }

            def events_for_commit(self, commit_index: int):
                return self._events.get(commit_index, ())

        schedule = _Schedule()

        state.advance(schedule)
        self.assertEqual(state.joyp_read(directions_selected=True), 0xED)
        self.assertEqual(state.joyp_read(directions_selected=False), 0xDF)
        self.assertEqual(state.if_bits, JOYPAD_IF_BIT)

        state.advance(schedule)
        self.assertEqual(state.joyp_read(directions_selected=True), 0xEF)
        self.assertEqual(state.joyp_read(directions_selected=False), 0xD7)
        self.assertEqual(state.if_bits, JOYPAD_IF_BIT)

        state.advance(schedule)
        self.assertEqual(state.joyp_read(directions_selected=True), 0xEF)
        self.assertEqual(state.joyp_read(directions_selected=False), 0xDF)
        self.assertEqual(state.if_bits, 0x00)

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

    def test_load_manifest_entry_resolves_joy_rom(self) -> None:
        entry = load_manifest_entry("JOY_DIVERGE_PERSIST")
        self.assertEqual(entry.rom_path.name, "joy_diverge_persist.gb")
        self.assertEqual(entry.sym_path.name, "joy_diverge_persist.sym")
        self.assertEqual(entry.timeout_commits, 4)
        self.assertEqual(entry.checkpoint_symbols, ("__checkpoint_poll",))
        self.assertEqual(entry.manifest_entry["action_script"], "bench/actions/joy_diverge_persist.yaml")
        self.assertIsNone(entry.manifest_entry["action_gen"])

    def test_load_manifest_entry_resolves_mbc3_rom(self) -> None:
        entry = load_manifest_entry("MBC3_SWITCH")
        self.assertEqual(entry.rom_id, "MBC3_SWITCH")
        self.assertEqual(entry.rom_path.name, "MBC3_SWITCH.gb")
        self.assertEqual(entry.sym_path.name, "MBC3_SWITCH.sym")
        self.assertEqual(entry.manifest_entry["requires"], ["cpu", "mbc3"])

    def test_assert_rom_matches_pyboy_signature_uses_manifest_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            rom_path = Path(tmpdir) / "alu_flags.gb"
            rom_bytes = bytes([0x3E, 0x12, 0x00])
            rom_path.write_bytes(rom_bytes)
            entry = rom_runner.RomManifestEntry(
                rom_id="ALU_FLAGS",
                rom_path=rom_path,
                sym_path=rom_path.with_suffix(".sym"),
                profiles=rom_runner.SimulationProfiles.from_mapping(
                    {
                        "model_profile": "DMG",
                        "reset_profile": "SkipBoot",
                        "memory_behavior_profile": "DmgConservative",
                    }
                ),
                timeout_commits=17,
                checkpoint_symbols=("__checkpoint_add",),
                manifest_entry={"id": "ALU_FLAGS", "timeout_commits": 17, "action_script": None, "action_gen": None},
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
            checkpoint_addr=None,
            event_schedule=unittest.mock.ANY,
        )


if __name__ == "__main__":
    unittest.main()
