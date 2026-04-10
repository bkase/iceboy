from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from bench.actions.generators import JoypadButtons, JoypadButtonsEvent
from test.harness import rom_runner
from test.harness.dut_driver import JoypadState, SimStimulus
from test.harness.rom_runner import (
    ABI_LOG_SIZE,
    ABI_RESULT_PASS,
    ABI_RESULT_RUNNING,
    ABI_SIGNATURE_SIZE,
    BLARGG_FAIL_MARKER,
    BLARGG_PASS_STRING,
    JOYPAD_IF_BIT,
    LCDC_ADDR,
    LY_ADDR,
    MOONEYE_FAIL_BYTES,
    MOONEYE_PASS_BYTES,
    MooneyeTerminalState,
    OAM_BASE,
    STAT_IF_BIT,
    STAT_ADDR,
    VBLANK_IF_BIT,
    VRAM_BASE,
    AbiSnapshot,
    DutTerminalState,
    ExternalMemoryBus,
    _ScriptedJoypadOracleState,
    _blob_frame_mismatch,
    _decode_png_grayscale,
    _decode_png_1bit_grayscale,
    _scanout_dmg_gray,
    _scanout_blob_bit,
    _shade_frame_mismatch,
    classify_blargg_serial_capture,
    classify_mooneye_register_signature,
    classify_mooneye_screen_text,
    classify_mooneye_serial_capture,
    classify_mooneye_assert_block,
    decode_vram_text,
    load_manifest_entry,
    mooneye_arch_state_signature,
    mooneye_register_signature,
    soc_mooneye_register_signature,
    soc_preview_bus_req,
)


MEALYBUG_EXPECTED_ROOT = (
    Path(__file__).resolve().parents[2] / "bench" / "expected" / "suite_owned" / "mealybug-tearoom-tests" / "DMG-blob"
)
DMG_ACID2_EXPECTED = (
    Path(__file__).resolve().parents[2] / "bench" / "expected" / "suite_owned" / "dmg-acid2" / "reference-dmg.png"
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

    @staticmethod
    def advance_idle_cycles(bus: ExternalMemoryBus, count: int) -> None:
        for _ in range(count):
            if_set_bits = bus.next_if_set_bits(write_en=False, write_addr=0, write_data=0)
            bus.advance_cycle(
                write_en=False,
                write_addr=0,
                write_data=0,
                if_set_bits=if_set_bits,
                irq_ack_valid=False,
                irq_ack_bit=0,
            )

    @staticmethod
    def advance_write_cycle(bus: ExternalMemoryBus, *, addr: int, value: int) -> None:
        if_set_bits = bus.next_if_set_bits(write_en=True, write_addr=addr, write_data=value)
        bus.advance_cycle(
            write_en=True,
            write_addr=addr,
            write_data=value,
            if_set_bits=if_set_bits,
            irq_ack_valid=False,
            irq_ack_bit=0,
        )

    def test_external_memory_bus_maps_rom_wram_and_hram(self) -> None:
        bus = ExternalMemoryBus(bytes([value & 0xFF for value in range(0x8000)]))
        self.assertEqual(bus.read(0x0012), 0x12)
        self.assertEqual(bus.read(0x8123), 0x00)

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
        bus = ExternalMemoryBus(self.build_mbc3_rom(bank_count=16, cart_type=0x10, ram_size_code=0x03))

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

    def test_external_memory_bus_models_serial_transfer_and_capture(self) -> None:
        bus = ExternalMemoryBus(bytes(0x8000))
        bus.write(0xFF01, 0x41)
        bus.write(0xFF02, 0x81)

        self.assertEqual(bus.read(0xFF01), 0x41)
        self.assertEqual(bus.read(0xFF02), 0x81)
        self.assertEqual(bus.serial_capture, [0x41])

        for cycles_left in range(8, 0, -1):
            self.advance_idle_cycles(bus, 1)
            self.assertEqual(bus.serial_cycles_left, cycles_left - 1)

        self.assertEqual(bus.read(0xFF01), 0xFF)
        self.assertEqual(bus.read(0xFF02), 0x01)
        self.assertEqual(bus.read(0xFF0F), 0x08)

    def test_external_memory_bus_applies_serial_inject_value_on_completion(self) -> None:
        bus = ExternalMemoryBus(bytes(0x8000))
        bus.apply_stimulus(SimStimulus(serial_inject=0xA5))
        bus.write(0xFF01, 0x99)
        bus.write(0xFF02, 0x81)

        self.advance_idle_cycles(bus, 8)

        self.assertEqual(bus.read(0xFF01), 0xA5)

    def test_external_memory_bus_models_oam_dma_copy_and_cpu_restrictions(self) -> None:
        bus = ExternalMemoryBus(bytes(0x8000), enforce_dma_cpu_restrictions=True)
        self.advance_write_cycle(bus, addr=LCDC_ADDR, value=0x00)
        bus.write(0xC100, 0x12)
        bus.write(0xC101, 0x34)
        bus.write(0xC123, 0x66)
        bus.write(0xC19F, 0xAB)

        bus.write(0xFF80, 0xC3)
        bus.write(0xFF01, 0x41)
        bus.write(0xFF46, 0xC1)

        self.assertTrue(bus.dma_active)
        self.assertEqual(bus.read(0xC100), 0xFF)
        self.assertEqual(bus.read(0xFE00), 0xFF)
        self.assertEqual(bus.read(0xFFFF), 0xFF)
        self.assertEqual(bus.read(0xFF80), 0xC3)
        self.assertEqual(bus.read(0xFF01), 0xFF)

        bus.write(0xC123, 0x99)
        bus.write(0xFF01, 0x55)
        self.assertEqual(bus.read(0xC123), 0xFF)
        self.assertEqual(bus.read(0xFF01), 0xFF)
        self.advance_idle_cycles(bus, 158)
        self.assertTrue(bus.dma_active)
        self.advance_idle_cycles(bus, 1)

        self.assertFalse(bus.dma_active)
        self.assertEqual(bus.read(0xC123), 0x66)
        self.assertEqual(bus.read(0xFE00), 0x12)
        self.assertEqual(bus.read(0xFE01), 0x34)
        self.assertEqual(bus.read(0xFE9F), 0xAB)
        self.assertEqual(bus.read(0xFF01), 0x41)

    def test_external_memory_bus_models_ppu_registers_and_access_gating(self) -> None:
        bus = ExternalMemoryBus(bytes(0x8000))

        self.assertEqual(bus.read(LY_ADDR), 0x00)
        self.assertEqual(bus.read(STAT_ADDR) & 0x03, 0x02)

        self.advance_write_cycle(bus, addr=LCDC_ADDR, value=0x00)
        self.assertEqual(bus.read(LY_ADDR), 0x00)
        self.assertEqual(bus.read(STAT_ADDR) & 0x03, 0x00)

        bus.write(VRAM_BASE, 0x12)
        bus.write(OAM_BASE, 0x34)
        self.assertEqual(bus.read(VRAM_BASE), 0x12)
        self.assertEqual(bus.read(OAM_BASE), 0x34)

        self.advance_write_cycle(bus, addr=LCDC_ADDR, value=0x91)
        for _ in range(200):
            if (bus.read(STAT_ADDR) & 0x03) == 0x03:
                break
            self.advance_idle_cycles(bus, 1)
        else:
            self.fail("PPU bus model did not reach mode 3 within 200 m-cycles")
        self.assertEqual(bus.read(VRAM_BASE), 0xFF)
        self.assertEqual(bus.read(OAM_BASE), 0xFF)

        bus.write(VRAM_BASE, 0x56)
        bus.write(OAM_BASE, 0x78)
        for _ in range(200):
            if (bus.read(STAT_ADDR) & 0x03) == 0x00:
                break
            self.advance_idle_cycles(bus, 1)
        else:
            self.fail("PPU bus model did not reach mode 0 within 200 m-cycles")
        self.assertEqual(bus.read(VRAM_BASE), 0x12)
        self.assertEqual(bus.read(OAM_BASE), 0x34)

    def test_external_memory_bus_sets_vblank_and_stat_if_bits_from_ppu_model(self) -> None:
        bus = ExternalMemoryBus(bytes(0x8000))

        self.advance_write_cycle(bus, addr=0xFF45, value=0x02)
        self.advance_write_cycle(bus, addr=STAT_ADDR, value=0x40)
        for _ in range(300):
            if (bus.read(STAT_ADDR) & 0x04) != 0:
                break
            self.advance_idle_cycles(bus, 1)
        else:
            self.fail("PPU bus model did not reach LYC coincidence within 300 m-cycles")
        self.assertEqual(bus.read(0xFF0F) & 0x02, 0x02)

        for _ in range(20000):
            if bus.read(LY_ADDR) == 144:
                break
            self.advance_idle_cycles(bus, 1)
        else:
            self.fail("PPU bus model did not reach line 144 within 20000 m-cycles")
        self.assertEqual(bus.read(0xFF0F) & 0x01, 0x01)

    def test_external_memory_bus_can_shadow_integrated_ppu_observations(self) -> None:
        bus = ExternalMemoryBus(bytes(0x8000), use_integrated_ppu=True)
        self.advance_write_cycle(bus, addr=LCDC_ADDR, value=0x91)
        self.advance_write_cycle(bus, addr=0xFF45, value=0x02)

        obs = SimpleNamespace(
            ppu_mode=4,
            ppu_ly=144,
            ppu_stat=0x79,
            ppu_vblank_req=True,
            ppu_stat_req=True,
        )
        bus.sync_integrated_ppu(obs)
        self.assertEqual(bus.read(LY_ADDR), 144)
        self.assertEqual(bus.read(STAT_ADDR), 0x79)

        bus.advance_cycle(
            write_en=False,
            write_addr=0,
            write_data=0,
            if_set_bits=0,
            irq_ack_valid=False,
            irq_ack_bit=0,
        )
        self.assertEqual(bus.read(0xFF0F) & 0x03, 0x03)

        bus.sync_integrated_ppu(SimpleNamespace(**obs.__dict__, m_ce=True))
        self.assertEqual(bus.read(LY_ADDR), 144)
        self.assertEqual(bus.read(STAT_ADDR), 0x79)

    def test_integrated_ppu_ack_does_not_reassert_same_cycle_window_bit(self) -> None:
        bus = ExternalMemoryBus(bytes(0x8000), use_integrated_ppu=True)
        bus.sync_integrated_ppu(
            SimpleNamespace(
                ppu_mode=4,
                ppu_ly=144,
                ppu_stat=0x81,
                ppu_vblank_req_window=True,
                ppu_stat_req_window=True,
                ppu_vblank_req=False,
                ppu_stat_req=False,
            )
        )

        bus.advance_cycle(
            write_en=False,
            write_addr=0,
            write_data=0,
            if_set_bits=0,
            irq_ack_valid=True,
            irq_ack_bit=1,
        )
        self.assertEqual(bus.read(0xFF0F) & 0x03, VBLANK_IF_BIT)

    def test_integrated_ppu_window_level_does_not_reassert_after_if_clear(self) -> None:
        bus = ExternalMemoryBus(bytes(0x8000), use_integrated_ppu=True)
        observation = SimpleNamespace(
            ppu_mode=4,
            ppu_ly=144,
            ppu_stat=0x81,
            ppu_vblank_req_window=False,
            ppu_stat_req_window=True,
            ppu_vblank_req=False,
            ppu_stat_req=False,
        )

        bus.sync_integrated_ppu(observation)
        bus.advance_cycle(
            write_en=False,
            write_addr=0,
            write_data=0,
            if_set_bits=0,
            irq_ack_valid=False,
            irq_ack_bit=0,
        )
        self.assertEqual(bus.read(0xFF0F) & STAT_IF_BIT, STAT_IF_BIT)

        bus.sync_integrated_ppu(observation)
        bus.advance_cycle(
            write_en=True,
            write_addr=0xFF0F,
            write_data=0x00,
            if_set_bits=0,
            irq_ack_valid=False,
            irq_ack_bit=0,
        )
        self.assertEqual(bus.read(0xFF0F) & STAT_IF_BIT, 0)

    def test_decode_vram_text_and_classify_mooneye_screen_text(self) -> None:
        bus = ExternalMemoryBus(bytes(0x8000), use_integrated_ppu=True)
        bus.vram[0x1800 : 0x1807] = b"Test OK"
        self.assertEqual(decode_vram_text(bus, rows=1, cols=7), ("Test OK",))
        self.assertEqual(classify_mooneye_screen_text(bus), "pass")

        bus.vram[0x1800 : 0x180F] = b"Fail: r1 step 3"
        self.assertEqual(classify_mooneye_screen_text(bus), "fail")

    def test_decode_png_1bit_grayscale_reads_pinned_mealybug_reference(self) -> None:
        image = _decode_png_1bit_grayscale(MEALYBUG_EXPECTED_ROOT / "m3_scx_low_3_bits.png")
        self.assertEqual(len(image), 144)
        self.assertTrue(all(len(row) == 160 for row in image))
        self.assertEqual(set(pixel for row in image for pixel in row), {0, 1})

    def test_blob_frame_helpers_report_binary_shades_and_first_mismatch(self) -> None:
        self.assertEqual(_scanout_blob_bit(0, light_shades=frozenset({0})), 1)
        self.assertEqual(_scanout_blob_bit(3, light_shades=frozenset({0})), 0)

        actual = ((1, 0), (0, 1))
        expected = ((1, 1), (0, 1))
        self.assertEqual(_blob_frame_mismatch(actual, expected), (1, (1, 0, 0, 1)))

    def test_decode_png_grayscale_reads_pinned_dmg_acid2_reference(self) -> None:
        image = _decode_png_grayscale(DMG_ACID2_EXPECTED)
        self.assertEqual(len(image), 144)
        self.assertTrue(all(len(row) == 160 for row in image))
        self.assertEqual(set(pixel for row in image for pixel in row), {0x00, 0x55, 0xAA, 0xFF})

    def test_shade_frame_helpers_report_canonical_dmg_shades_and_first_mismatch(self) -> None:
        self.assertEqual(_scanout_dmg_gray(0), 0xFF)
        self.assertEqual(_scanout_dmg_gray(1), 0xAA)
        self.assertEqual(_scanout_dmg_gray(2), 0x55)
        self.assertEqual(_scanout_dmg_gray(3), 0x00)

        actual = ((0xFF, 0x55), (0xAA, 0x00))
        expected = ((0xFF, 0xAA), (0xAA, 0x00))
        self.assertEqual(_shade_frame_mismatch(actual, expected), (1, (1, 0, 0x55, 0xAA)))

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

        self.advance_idle_cycles(bus, 6)

        self.assertEqual(bus.read(0xFF07), 0x05)
        self.assertGreater(bus.read(0xFF05), 0x00)

    def test_mooneye_serial_capture_classification_distinguishes_pass_fail_and_unknown(self) -> None:
        self.assertEqual(classify_mooneye_serial_capture(MOONEYE_PASS_BYTES), "pass")
        self.assertEqual(classify_mooneye_serial_capture(MOONEYE_FAIL_BYTES), "fail")
        self.assertEqual(classify_mooneye_serial_capture((0x99, 0x01, 0x02)), "unknown")

    def test_blargg_serial_capture_classification_distinguishes_pass_fail_and_incomplete(self) -> None:
        self.assertEqual(classify_blargg_serial_capture(BLARGG_PASS_STRING.encode("ascii")), "pass")
        self.assertEqual(classify_blargg_serial_capture(BLARGG_FAIL_MARKER.encode("ascii")), "fail")
        self.assertEqual(classify_blargg_serial_capture(b"cpu_instrs\n01:ok"), "incomplete")

    def test_mooneye_register_signature_classification_distinguishes_pass_fail_and_unknown(self) -> None:
        self.assertEqual(classify_mooneye_register_signature(MOONEYE_PASS_BYTES), "pass")
        self.assertEqual(classify_mooneye_register_signature(MOONEYE_FAIL_BYTES), "fail")
        self.assertEqual(classify_mooneye_register_signature((0x99, 0x01, 0x02)), "unknown")

    def test_mooneye_assert_block_classification_detects_matching_saved_registers(self) -> None:
        block = {
            "base": 0xFF80,
            "flags": 0x3C,
            "saved": bytes([0x80, 0x00, 0x00, 0x01, 0x00, 0x01, 0x85, 0xFF]),
            "asserts": bytes([0x00, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00]),
        }
        self.assertEqual(classify_mooneye_assert_block(block), "pass")

    def test_mooneye_assert_block_classification_detects_mismatched_saved_registers(self) -> None:
        block = {
            "base": 0xFF80,
            "flags": 0x3C,
            "saved": bytes([0x80, 0x00, 0x00, 0x00, 0x00, 0x00, 0x85, 0xFF]),
            "asserts": bytes([0x00, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00]),
        }
        self.assertEqual(classify_mooneye_assert_block(block), "fail")

    def test_mooneye_register_signature_reads_bcdehl_from_soc_observation(self) -> None:
        observation = SimpleNamespace(cpu_b=3, cpu_c=5, cpu_d=8, cpu_e=13, cpu_h=21, cpu_l=34)
        self.assertEqual(mooneye_register_signature(observation), MOONEYE_PASS_BYTES)

    def test_mooneye_arch_state_signature_reads_bcdehl_from_cpu_arch_state_encoding(self) -> None:
        regs = (
            (0x01 << 88)
            | (0xB0 << 80)
            | (0x03 << 72)
            | (0x05 << 64)
            | (0x08 << 56)
            | (0x0D << 48)
            | (0x15 << 40)
            | (0x22 << 32)
            | (0xFFFE << 16)
            | 0x0100
        )
        arch_state = (regs << 4) | 0x0
        self.assertEqual(mooneye_arch_state_signature(arch_state), MOONEYE_PASS_BYTES)

    def test_soc_mooneye_register_signature_prefers_packed_observation_fields(self) -> None:
        driver = SimpleNamespace(dut=SimpleNamespace())
        observation = SimpleNamespace(cpu_b=3, cpu_c=5, cpu_d=8, cpu_e=13, cpu_h=21, cpu_l=34)
        self.assertEqual(soc_mooneye_register_signature(driver, observation), MOONEYE_PASS_BYTES)

    def test_soc_mooneye_register_signature_falls_back_to_hierarchical_arch_state(self) -> None:
        regs = (
            (0x01 << 88)
            | (0xB0 << 80)
            | (0x03 << 72)
            | (0x05 << 64)
            | (0x08 << 56)
            | (0x0D << 48)
            | (0x15 << 40)
            | (0x22 << 32)
            | (0xFFFE << 16)
            | 0x0100
        )
        arch_state_value = (regs << 4) | 0x0
        driver = SimpleNamespace(
            dut=SimpleNamespace(cpu_core_0=SimpleNamespace(arch_state=SimpleNamespace(value=arch_state_value)))
        )
        observation = SimpleNamespace()
        self.assertEqual(soc_mooneye_register_signature(driver, observation), MOONEYE_PASS_BYTES)

    def test_soc_preview_bus_req_decodes_tail_of_cpu_core_output(self) -> None:
        encoded = (0x2 << 24) | (0xC123 << 8) | 0xAB
        driver = SimpleNamespace(
            dut=SimpleNamespace(cpu_core_0=SimpleNamespace(output__=SimpleNamespace(value=encoded)))
        )
        self.assertEqual(soc_preview_bus_req(driver), (0x2, 0xC123, 0xAB))

    def test_soc_preview_bus_req_falls_back_to_idle_without_cpu_core_output(self) -> None:
        driver = SimpleNamespace(dut=SimpleNamespace())
        self.assertEqual(soc_preview_bus_req(driver), (0, 0, 0))

    def test_sync_integrated_ppu_uses_raw_request_bits_when_window_bits_clear(self) -> None:
        bus = ExternalMemoryBus(bytes(0x8000), use_integrated_ppu=True)
        bus.sync_integrated_ppu(
            SimpleNamespace(
                ppu_mode=4,
                ppu_ly=144,
                ppu_stat=0x81,
                ppu_vblank_req_window=False,
                ppu_stat_req_window=False,
                ppu_vblank_req=True,
                ppu_stat_req=True,
            )
        )
        self.assertEqual(bus.integrated_ppu_if_bits, VBLANK_IF_BIT | STAT_IF_BIT)

    def test_integrated_ppu_live_mmio_state_updates_without_m_ce_shadow(self) -> None:
        bus = ExternalMemoryBus(bytes(0x8000), use_integrated_ppu=True)
        bus.sync_integrated_ppu(SimpleNamespace(ppu_mode=3, ppu_ly=9, ppu_stat=0x83, m_ce=False))
        self.assertEqual(bus.read(LY_ADDR), 9)
        self.assertEqual(bus.read(STAT_ADDR), 0x83)

        bus.sync_integrated_ppu(SimpleNamespace(ppu_mode=3, ppu_ly=9, ppu_stat=0x83, m_ce=True))
        self.assertEqual(bus.read(LY_ADDR), 9)
        self.assertEqual(bus.read(STAT_ADDR), 0x83)

    def test_integrated_ppu_mmio_read_from_observation_can_hold_mcycle_visible_stat(self) -> None:
        bus = ExternalMemoryBus(bytes(0x8000), use_integrated_ppu=True)
        self.advance_write_cycle(bus, addr=LCDC_ADDR, value=0x91)
        self.advance_write_cycle(bus, addr=0xFF45, value=0x00)

        start_obs = SimpleNamespace(ppu_mode=2, ppu_ly=1, ppu_stat=0x83)
        late_obs = SimpleNamespace(ppu_mode=3, ppu_ly=1, ppu_stat=0x80)

        bus.sync_integrated_ppu(late_obs)
        self.assertEqual(bus.read(STAT_ADDR), 0x80)
        self.assertEqual(bus.integrated_ppu_mmio_read_from_observation(start_obs, STAT_ADDR), 0x83)
        self.assertEqual(bus.integrated_ppu_mmio_read_from_observation(start_obs, LY_ADDR), 0x01)

    def test_integrated_ppu_cpu_write_from_observation_blocks_oam_in_mode2(self) -> None:
        bus = ExternalMemoryBus(bytes(0x8000), use_integrated_ppu=True)
        self.advance_write_cycle(bus, addr=LCDC_ADDR, value=0x91)
        bus.oam[0] = 0x00

        blocked_obs = SimpleNamespace(ppu_mode=1, ppu_ly=1, ppu_stat=0x86)
        bus.integrated_ppu_cpu_write_from_observation(blocked_obs, OAM_BASE, 0x81)

        self.assertEqual(bus.oam[0], 0x00)

    def test_integrated_ppu_cpu_write_from_observation_blocks_vram_in_mode3(self) -> None:
        bus = ExternalMemoryBus(bytes(0x8000), use_integrated_ppu=True)
        self.advance_write_cycle(bus, addr=LCDC_ADDR, value=0x91)
        bus.vram[0] = 0x00

        blocked_obs = SimpleNamespace(ppu_mode=2, ppu_ly=1, ppu_stat=0x87)
        bus.integrated_ppu_cpu_write_from_observation(blocked_obs, VRAM_BASE, 0x81)

        self.assertEqual(bus.vram[0], 0x00)

    def test_assert_mooneye_ppu_soc_rom_passes_reports_screen_on_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            rom_path = Path(tmpdir) / "lcdon_timing-GS.gb"
            rom_path.write_bytes(bytes(0x8000))
            failing_state = MooneyeTerminalState(
                signature=MOONEYE_FAIL_BYTES,
                cycles=1234,
                screen_lines=("Test failed:", "STAT LYC=0", "Cycle: $6E"),
                assert_block={"base": 0xFF80, "flags": 0x3C},
                last_pc=0x4D75,
                failure_triplet=(0x6E, 0x83, 0x84),
                oracle_history=((0x4D70, 0x84, 0xFE, 0x83),),
            )

            with patch.object(rom_runner, "run_soc_dut_to_mooneye_signature", AsyncMock(return_value=failing_state)):
                with self.assertRaisesRegex(
                    AssertionError,
                    r"lcdon_timing-GS\.gb produced register outcome fail: .*cycles=1234.*last_pc=0x4D75.*STAT LYC=0.*failure_triplet=\(cycle=0x6E, expected=0x83, actual=0x84\).*pc=0x4D70/a=0x84/op=0xFE/imm=0x83",
                ):
                    asyncio.run(rom_runner.assert_mooneye_ppu_soc_rom_passes(object(), rom_path=rom_path, max_mcycles=250000))

    def test_soc_step_to_commit_keeps_stat_on_mcycle_open_observation(self) -> None:
        async def exercise() -> None:
            bus = ExternalMemoryBus(bytes(0x8000), use_integrated_ppu=True)
            start_obs = SimpleNamespace(
                preview_bus_req_kind=rom_runner.BUS_REQ_READ,
                preview_bus_req_addr=STAT_ADDR,
                preview_bus_req_data=0,
                ppu_mode=2,
                ppu_ly=1,
                ppu_stat=0x83,
                ppu_vblank_req_window=False,
                ppu_stat_req_window=False,
                ppu_vblank_req=False,
                ppu_stat_req=False,
                m_ce=False,
                t_index=0,
            )
            mid_obs = SimpleNamespace(
                preview_bus_req_kind=rom_runner.BUS_REQ_READ,
                preview_bus_req_addr=STAT_ADDR,
                preview_bus_req_data=0,
                ppu_mode=2,
                ppu_ly=1,
                ppu_stat=0x83,
                ppu_vblank_req_window=False,
                ppu_stat_req_window=False,
                ppu_vblank_req=False,
                ppu_stat_req=False,
                m_ce=False,
                t_index=1,
            )
            late_obs = SimpleNamespace(
                preview_bus_req_kind=rom_runner.BUS_REQ_READ,
                preview_bus_req_addr=STAT_ADDR,
                preview_bus_req_data=0,
                ppu_mode=3,
                ppu_ly=1,
                ppu_stat=0x80,
                ppu_vblank_req_window=False,
                ppu_stat_req_window=False,
                ppu_vblank_req=False,
                ppu_stat_req=False,
                m_ce=False,
                t_index=2,
            )
            post = SimpleNamespace()
            step_mcycle_rom = AsyncMock(return_value=post)
            driver = SimpleNamespace(
                dut=SimpleNamespace(clk_i=object()),
                observe_rom=unittest.mock.Mock(side_effect=[start_obs, mid_obs, late_obs]),
                observe=unittest.mock.Mock(side_effect=AssertionError("observe fallback should not be used")),
                step_mcycle_rom=step_mcycle_rom,
                step_mcycle=AsyncMock(side_effect=AssertionError("step_mcycle fallback should not be used")),
                inject_stimulus=unittest.mock.Mock(),
                set_bus_inputs=unittest.mock.Mock(),
            )
            with patch("cocotb.triggers.ClockCycles", new=AsyncMock()):
                actual_post, preview_kind, preview_addr, preview_data, _video_sample, _write_allowed = await rom_runner._soc_step_to_commit(driver, bus)

            self.assertIs(actual_post, post)
            self.assertEqual((preview_kind, preview_addr, preview_data), (rom_runner.BUS_REQ_READ, STAT_ADDR, 0))
            driver.set_bus_inputs.assert_called_once()
            self.assertEqual(driver.set_bus_inputs.call_args.kwargs["bus_read_data"], 0x83)
            self.assertEqual(step_mcycle_rom.await_args.kwargs["bus_read_data"], 0x83)

        asyncio.run(exercise())

    def test_soc_step_to_commit_keeps_ly_on_mcycle_open_observation(self) -> None:
        async def exercise() -> None:
            bus = ExternalMemoryBus(bytes(0x8000), use_integrated_ppu=True)
            start_obs = SimpleNamespace(
                preview_bus_req_kind=rom_runner.BUS_REQ_READ,
                preview_bus_req_addr=LY_ADDR,
                preview_bus_req_data=0,
                ppu_mode=0,
                ppu_ly=0,
                ppu_stat=0x84,
                ppu_vblank_req_window=False,
                ppu_stat_req_window=False,
                ppu_vblank_req=False,
                ppu_stat_req=False,
                m_ce=False,
                t_index=0,
            )
            mid_obs = SimpleNamespace(
                preview_bus_req_kind=rom_runner.BUS_REQ_READ,
                preview_bus_req_addr=LY_ADDR,
                preview_bus_req_data=0,
                ppu_mode=0,
                ppu_ly=0,
                ppu_stat=0x84,
                ppu_vblank_req_window=False,
                ppu_stat_req_window=False,
                ppu_vblank_req=False,
                ppu_stat_req=False,
                m_ce=False,
                t_index=1,
            )
            late_obs = SimpleNamespace(
                preview_bus_req_kind=rom_runner.BUS_REQ_READ,
                preview_bus_req_addr=LY_ADDR,
                preview_bus_req_data=0,
                ppu_mode=1,
                ppu_ly=1,
                ppu_stat=0x82,
                ppu_vblank_req_window=False,
                ppu_stat_req_window=False,
                ppu_vblank_req=False,
                ppu_stat_req=False,
                m_ce=False,
                t_index=2,
            )
            post = SimpleNamespace()
            step_mcycle_rom = AsyncMock(return_value=post)
            driver = SimpleNamespace(
                dut=SimpleNamespace(clk_i=object()),
                observe_rom=unittest.mock.Mock(side_effect=[start_obs, mid_obs, late_obs]),
                observe=unittest.mock.Mock(side_effect=AssertionError("observe fallback should not be used")),
                step_mcycle_rom=step_mcycle_rom,
                step_mcycle=AsyncMock(side_effect=AssertionError("step_mcycle fallback should not be used")),
                inject_stimulus=unittest.mock.Mock(),
                set_bus_inputs=unittest.mock.Mock(),
            )
            with patch("cocotb.triggers.ClockCycles", new=AsyncMock()):
                actual_post, preview_kind, preview_addr, preview_data, _video_sample, _write_allowed = await rom_runner._soc_step_to_commit(driver, bus)

            self.assertIs(actual_post, post)
            self.assertEqual((preview_kind, preview_addr, preview_data), (rom_runner.BUS_REQ_READ, LY_ADDR, 0))
            driver.set_bus_inputs.assert_called_once()
            self.assertEqual(driver.set_bus_inputs.call_args.kwargs["bus_read_data"], 0x00)
            self.assertEqual(step_mcycle_rom.await_args.kwargs["bus_read_data"], 0x00)

        asyncio.run(exercise())

    def test_soc_step_to_commit_keeps_oam_access_on_mcycle_open_observation(self) -> None:
        async def exercise() -> None:
            bus = ExternalMemoryBus(bytes(0x8000), use_integrated_ppu=True)
            bus.oam[0] = 0x00
            self.advance_write_cycle(bus, addr=LCDC_ADDR, value=0x91)
            start_obs = SimpleNamespace(
                preview_bus_req_kind=rom_runner.BUS_REQ_READ,
                preview_bus_req_addr=OAM_BASE,
                preview_bus_req_data=0,
                ppu_mode=0,
                ppu_ly=0,
                ppu_stat=0x84,
                ppu_vblank_req_window=False,
                ppu_stat_req_window=False,
                ppu_vblank_req=False,
                ppu_stat_req=False,
                m_ce=False,
                t_index=0,
            )
            mid_obs = SimpleNamespace(
                preview_bus_req_kind=rom_runner.BUS_REQ_READ,
                preview_bus_req_addr=OAM_BASE,
                preview_bus_req_data=0,
                ppu_mode=2,
                ppu_ly=0,
                ppu_stat=0x83,
                ppu_vblank_req_window=False,
                ppu_stat_req_window=False,
                ppu_vblank_req=False,
                ppu_stat_req=False,
                m_ce=False,
                t_index=1,
            )
            late_obs = SimpleNamespace(
                preview_bus_req_kind=rom_runner.BUS_REQ_READ,
                preview_bus_req_addr=OAM_BASE,
                preview_bus_req_data=0,
                ppu_mode=2,
                ppu_ly=0,
                ppu_stat=0x83,
                ppu_vblank_req_window=False,
                ppu_stat_req_window=False,
                ppu_vblank_req=False,
                ppu_stat_req=False,
                m_ce=False,
                t_index=2,
            )
            post = SimpleNamespace()
            step_mcycle_rom = AsyncMock(return_value=post)
            driver = SimpleNamespace(
                dut=SimpleNamespace(clk_i=object()),
                observe_rom=unittest.mock.Mock(side_effect=[start_obs, mid_obs, late_obs]),
                observe=unittest.mock.Mock(side_effect=AssertionError("observe fallback should not be used")),
                step_mcycle_rom=step_mcycle_rom,
                step_mcycle=AsyncMock(side_effect=AssertionError("step_mcycle fallback should not be used")),
                inject_stimulus=unittest.mock.Mock(),
                set_bus_inputs=unittest.mock.Mock(),
            )
            with patch("cocotb.triggers.ClockCycles", new=AsyncMock()):
                actual_post, preview_kind, preview_addr, preview_data, _video_sample, _write_allowed = await rom_runner._soc_step_to_commit(driver, bus)

            self.assertIs(actual_post, post)
            self.assertEqual((preview_kind, preview_addr, preview_data), (rom_runner.BUS_REQ_READ, OAM_BASE, 0))
            driver.set_bus_inputs.assert_called_once()
            self.assertEqual(driver.set_bus_inputs.call_args.kwargs["bus_read_data"], 0x00)
            self.assertEqual(step_mcycle_rom.await_args.kwargs["bus_read_data"], 0x00)

        asyncio.run(exercise())

    def test_soc_step_to_commit_uses_midcycle_oam_access_for_later_lines(self) -> None:
        async def exercise() -> None:
            bus = ExternalMemoryBus(bytes(0x8000), use_integrated_ppu=True)
            bus.oam[0] = 0x00
            self.advance_write_cycle(bus, addr=LCDC_ADDR, value=0x91)
            start_obs = SimpleNamespace(
                preview_bus_req_kind=rom_runner.BUS_REQ_READ,
                preview_bus_req_addr=OAM_BASE,
                preview_bus_req_data=0,
                ppu_mode=0,
                ppu_ly=1,
                ppu_stat=0x80,
                ppu_vblank_req_window=False,
                ppu_stat_req_window=False,
                ppu_vblank_req=False,
                ppu_stat_req=False,
                m_ce=False,
                t_index=0,
            )
            mid_obs = SimpleNamespace(
                preview_bus_req_kind=rom_runner.BUS_REQ_READ,
                preview_bus_req_addr=OAM_BASE,
                preview_bus_req_data=0,
                ppu_mode=1,
                ppu_ly=1,
                ppu_stat=0x86,
                ppu_vblank_req_window=False,
                ppu_stat_req_window=False,
                ppu_vblank_req=False,
                ppu_stat_req=False,
                m_ce=False,
                t_index=1,
            )
            late_obs = SimpleNamespace(
                preview_bus_req_kind=rom_runner.BUS_REQ_READ,
                preview_bus_req_addr=OAM_BASE,
                preview_bus_req_data=0,
                ppu_mode=1,
                ppu_ly=1,
                ppu_stat=0x86,
                ppu_vblank_req_window=False,
                ppu_stat_req_window=False,
                ppu_vblank_req=False,
                ppu_stat_req=False,
                m_ce=False,
                t_index=2,
            )
            post = SimpleNamespace()
            step_mcycle_rom = AsyncMock(return_value=post)
            driver = SimpleNamespace(
                dut=SimpleNamespace(clk_i=object()),
                observe_rom=unittest.mock.Mock(side_effect=[start_obs, mid_obs, late_obs]),
                observe=unittest.mock.Mock(side_effect=AssertionError("observe fallback should not be used")),
                step_mcycle_rom=step_mcycle_rom,
                step_mcycle=AsyncMock(side_effect=AssertionError("step_mcycle fallback should not be used")),
                inject_stimulus=unittest.mock.Mock(),
                set_bus_inputs=unittest.mock.Mock(),
            )
            with patch("cocotb.triggers.ClockCycles", new=AsyncMock()):
                actual_post, preview_kind, preview_addr, preview_data, _video_sample, _write_allowed = await rom_runner._soc_step_to_commit(driver, bus)

            self.assertIs(actual_post, post)
            self.assertEqual((preview_kind, preview_addr, preview_data), (rom_runner.BUS_REQ_READ, OAM_BASE, 0))
            driver.set_bus_inputs.assert_called_once()
            self.assertEqual(driver.set_bus_inputs.call_args.kwargs["bus_read_data"], 0x00)
            self.assertEqual(step_mcycle_rom.await_args.kwargs["bus_read_data"], 0xFF)

        asyncio.run(exercise())

    def test_soc_step_to_commit_uses_midcycle_vram_access_for_later_lines(self) -> None:
        async def exercise() -> None:
            bus = ExternalMemoryBus(bytes(0x8000), use_integrated_ppu=True)
            bus.vram[0] = 0x00
            self.advance_write_cycle(bus, addr=LCDC_ADDR, value=0x91)
            start_obs = SimpleNamespace(
                preview_bus_req_kind=rom_runner.BUS_REQ_READ,
                preview_bus_req_addr=VRAM_BASE,
                preview_bus_req_data=0,
                ppu_mode=1,
                ppu_ly=1,
                ppu_stat=0x86,
                ppu_vblank_req_window=False,
                ppu_stat_req_window=False,
                ppu_vblank_req=False,
                ppu_stat_req=False,
                m_ce=False,
                t_index=0,
            )
            mid_obs = SimpleNamespace(
                preview_bus_req_kind=rom_runner.BUS_REQ_READ,
                preview_bus_req_addr=VRAM_BASE,
                preview_bus_req_data=0,
                ppu_mode=2,
                ppu_ly=1,
                ppu_stat=0x87,
                ppu_vblank_req_window=False,
                ppu_stat_req_window=False,
                ppu_vblank_req=False,
                ppu_stat_req=False,
                m_ce=False,
                t_index=1,
            )
            late_obs = SimpleNamespace(
                preview_bus_req_kind=rom_runner.BUS_REQ_READ,
                preview_bus_req_addr=VRAM_BASE,
                preview_bus_req_data=0,
                ppu_mode=2,
                ppu_ly=1,
                ppu_stat=0x87,
                ppu_vblank_req_window=False,
                ppu_stat_req_window=False,
                ppu_vblank_req=False,
                ppu_stat_req=False,
                m_ce=False,
                t_index=2,
            )
            post = SimpleNamespace()
            step_mcycle_rom = AsyncMock(return_value=post)
            driver = SimpleNamespace(
                dut=SimpleNamespace(clk_i=object()),
                observe_rom=unittest.mock.Mock(side_effect=[start_obs, mid_obs, late_obs]),
                observe=unittest.mock.Mock(side_effect=AssertionError("observe fallback should not be used")),
                step_mcycle_rom=step_mcycle_rom,
                step_mcycle=AsyncMock(side_effect=AssertionError("step_mcycle fallback should not be used")),
                inject_stimulus=unittest.mock.Mock(),
                set_bus_inputs=unittest.mock.Mock(),
            )
            with patch("cocotb.triggers.ClockCycles", new=AsyncMock()):
                actual_post, preview_kind, preview_addr, preview_data, _video_sample, _write_allowed = await rom_runner._soc_step_to_commit(driver, bus)

            self.assertIs(actual_post, post)
            self.assertEqual((preview_kind, preview_addr, preview_data), (rom_runner.BUS_REQ_READ, VRAM_BASE, 0))
            driver.set_bus_inputs.assert_called_once()
            self.assertEqual(driver.set_bus_inputs.call_args.kwargs["bus_read_data"], 0x00)
            self.assertEqual(step_mcycle_rom.await_args.kwargs["bus_read_data"], 0xFF)

        asyncio.run(exercise())

    def test_soc_step_to_commit_uses_open_sample_for_later_line_oam_write_mode0_to_mode1(self) -> None:
        async def exercise() -> None:
            bus = ExternalMemoryBus(bytes(0x8000), use_integrated_ppu=True)
            self.advance_write_cycle(bus, addr=LCDC_ADDR, value=0x91)
            start_obs = SimpleNamespace(
                preview_bus_req_kind=rom_runner.BUS_REQ_WRITE,
                preview_bus_req_addr=OAM_BASE,
                preview_bus_req_data=0x81,
                ppu_mode=0,
                ppu_ly=1,
                ppu_stat=0x80,
                ppu_vblank_req_window=False,
                ppu_stat_req_window=False,
                ppu_vblank_req=False,
                ppu_stat_req=False,
                m_ce=False,
                t_index=0,
            )
            mid_obs = SimpleNamespace(
                preview_bus_req_kind=rom_runner.BUS_REQ_WRITE,
                preview_bus_req_addr=OAM_BASE,
                preview_bus_req_data=0x81,
                ppu_mode=1,
                ppu_ly=1,
                ppu_stat=0x82,
                ppu_vblank_req_window=False,
                ppu_stat_req_window=False,
                ppu_vblank_req=False,
                ppu_stat_req=False,
                m_ce=False,
                t_index=1,
            )
            late_obs = SimpleNamespace(
                preview_bus_req_kind=rom_runner.BUS_REQ_WRITE,
                preview_bus_req_addr=OAM_BASE,
                preview_bus_req_data=0x81,
                ppu_mode=1,
                ppu_ly=1,
                ppu_stat=0x82,
                ppu_vblank_req_window=False,
                ppu_stat_req_window=False,
                ppu_vblank_req=False,
                ppu_stat_req=False,
                m_ce=False,
                t_index=2,
            )
            post = SimpleNamespace(bus_req_kind=rom_runner.BUS_REQ_WRITE, bus_req_addr=OAM_BASE, bus_req_data=0x81)
            step_mcycle_rom = AsyncMock(return_value=post)
            driver = SimpleNamespace(
                dut=SimpleNamespace(clk_i=object()),
                observe_rom=unittest.mock.Mock(side_effect=[start_obs, mid_obs, late_obs]),
                observe=unittest.mock.Mock(side_effect=AssertionError("observe fallback should not be used")),
                step_mcycle_rom=step_mcycle_rom,
                step_mcycle=AsyncMock(side_effect=AssertionError("step_mcycle fallback should not be used")),
                inject_stimulus=unittest.mock.Mock(),
                set_bus_inputs=unittest.mock.Mock(),
            )
            with patch("cocotb.triggers.ClockCycles", new=AsyncMock()):
                actual_post, preview_kind, preview_addr, preview_data, video_sample, write_allowed = await rom_runner._soc_step_to_commit(driver, bus)

            self.assertIs(actual_post, post)
            self.assertEqual((preview_kind, preview_addr, preview_data), (rom_runner.BUS_REQ_WRITE, OAM_BASE, 0x81))
            self.assertIs(video_sample, start_obs)
            self.assertTrue(write_allowed)

        asyncio.run(exercise())

    def test_soc_step_to_commit_uses_midcycle_sample_for_later_line_oam_write_mode1_to_mode2(self) -> None:
        async def exercise() -> None:
            bus = ExternalMemoryBus(bytes(0x8000), use_integrated_ppu=True)
            self.advance_write_cycle(bus, addr=LCDC_ADDR, value=0x91)
            start_obs = SimpleNamespace(
                preview_bus_req_kind=rom_runner.BUS_REQ_WRITE,
                preview_bus_req_addr=OAM_BASE,
                preview_bus_req_data=0x81,
                ppu_mode=1,
                ppu_ly=1,
                ppu_stat=0x82,
                ppu_vblank_req_window=False,
                ppu_stat_req_window=False,
                ppu_vblank_req=False,
                ppu_stat_req=False,
                m_ce=False,
                t_index=0,
            )
            mid_obs = SimpleNamespace(
                preview_bus_req_kind=rom_runner.BUS_REQ_WRITE,
                preview_bus_req_addr=OAM_BASE,
                preview_bus_req_data=0x81,
                ppu_mode=2,
                ppu_ly=1,
                ppu_stat=0x83,
                ppu_vblank_req_window=False,
                ppu_stat_req_window=False,
                ppu_vblank_req=False,
                ppu_stat_req=False,
                m_ce=False,
                t_index=1,
            )
            late_obs = SimpleNamespace(
                preview_bus_req_kind=rom_runner.BUS_REQ_WRITE,
                preview_bus_req_addr=OAM_BASE,
                preview_bus_req_data=0x81,
                ppu_mode=2,
                ppu_ly=1,
                ppu_stat=0x83,
                ppu_vblank_req_window=False,
                ppu_stat_req_window=False,
                ppu_vblank_req=False,
                ppu_stat_req=False,
                m_ce=False,
                t_index=2,
            )
            post = SimpleNamespace(bus_req_kind=rom_runner.BUS_REQ_WRITE, bus_req_addr=OAM_BASE, bus_req_data=0x81)
            step_mcycle_rom = AsyncMock(return_value=post)
            driver = SimpleNamespace(
                dut=SimpleNamespace(clk_i=object()),
                observe_rom=unittest.mock.Mock(side_effect=[start_obs, mid_obs, late_obs]),
                observe=unittest.mock.Mock(side_effect=AssertionError("observe fallback should not be used")),
                step_mcycle_rom=step_mcycle_rom,
                step_mcycle=AsyncMock(side_effect=AssertionError("step_mcycle fallback should not be used")),
                inject_stimulus=unittest.mock.Mock(),
                set_bus_inputs=unittest.mock.Mock(),
            )
            with patch("cocotb.triggers.ClockCycles", new=AsyncMock()):
                actual_post, preview_kind, preview_addr, preview_data, video_sample, write_allowed = await rom_runner._soc_step_to_commit(driver, bus)

            self.assertIs(actual_post, post)
            self.assertEqual((preview_kind, preview_addr, preview_data), (rom_runner.BUS_REQ_WRITE, OAM_BASE, 0x81))
            self.assertIs(video_sample, mid_obs)
            self.assertTrue(write_allowed)

        asyncio.run(exercise())

    def test_soc_step_to_commit_uses_midcycle_oam_access_for_line0_transfer(self) -> None:
        async def exercise() -> None:
            bus = ExternalMemoryBus(bytes(0x8000), use_integrated_ppu=True)
            bus.oam[0] = 0x00
            self.advance_write_cycle(bus, addr=LCDC_ADDR, value=0x91)
            start_obs = SimpleNamespace(
                preview_bus_req_kind=rom_runner.BUS_REQ_READ,
                preview_bus_req_addr=OAM_BASE,
                preview_bus_req_data=0,
                ppu_mode=2,
                ppu_ly=0,
                ppu_stat=0x83,
                ppu_vblank_req_window=False,
                ppu_stat_req_window=False,
                ppu_vblank_req=False,
                ppu_stat_req=False,
                m_ce=False,
                t_index=0,
            )
            mid_obs = SimpleNamespace(
                preview_bus_req_kind=rom_runner.BUS_REQ_READ,
                preview_bus_req_addr=OAM_BASE,
                preview_bus_req_data=0,
                ppu_mode=2,
                ppu_ly=0,
                ppu_stat=0x83,
                ppu_vblank_req_window=False,
                ppu_stat_req_window=False,
                ppu_vblank_req=False,
                ppu_stat_req=False,
                m_ce=False,
                t_index=1,
            )
            late_obs = SimpleNamespace(
                preview_bus_req_kind=rom_runner.BUS_REQ_READ,
                preview_bus_req_addr=OAM_BASE,
                preview_bus_req_data=0,
                ppu_mode=3,
                ppu_ly=0,
                ppu_stat=0x80,
                ppu_vblank_req_window=False,
                ppu_stat_req_window=False,
                ppu_vblank_req=False,
                ppu_stat_req=False,
                m_ce=False,
                t_index=2,
            )
            post = SimpleNamespace()
            step_mcycle_rom = AsyncMock(return_value=post)
            driver = SimpleNamespace(
                dut=SimpleNamespace(clk_i=object()),
                observe_rom=unittest.mock.Mock(side_effect=[start_obs, mid_obs, late_obs]),
                observe=unittest.mock.Mock(side_effect=AssertionError("observe fallback should not be used")),
                step_mcycle_rom=step_mcycle_rom,
                step_mcycle=AsyncMock(side_effect=AssertionError("step_mcycle fallback should not be used")),
                inject_stimulus=unittest.mock.Mock(),
                set_bus_inputs=unittest.mock.Mock(),
            )
            with patch("cocotb.triggers.ClockCycles", new=AsyncMock()):
                actual_post, preview_kind, preview_addr, preview_data, _video_sample, _write_allowed = await rom_runner._soc_step_to_commit(driver, bus)

            self.assertIs(actual_post, post)
            self.assertEqual((preview_kind, preview_addr, preview_data), (rom_runner.BUS_REQ_READ, OAM_BASE, 0))
            driver.set_bus_inputs.assert_called_once()
            self.assertEqual(driver.set_bus_inputs.call_args.kwargs["bus_read_data"], 0xFF)
            self.assertEqual(step_mcycle_rom.await_args.kwargs["bus_read_data"], 0xFF)

        asyncio.run(exercise())

    def test_run_soc_dut_to_mooneye_signature_keeps_oracle_history_on_assert_block_fail(self) -> None:
        async def exercise() -> None:
            rom_bytes = bytes(0x8000)
            post = SimpleNamespace(
                pc=0x1234,
                cpu_a=0x56,
                bus_req_kind=rom_runner.BUS_REQ_IDLE,
                bus_req_addr=0,
                bus_req_data=0,
                irq_ack_valid=False,
                irq_ack_bit=0,
            )

            with (
                patch.object(rom_runner, "_soc_step_to_commit", AsyncMock(return_value=(post, rom_runner.BUS_REQ_IDLE, 0, 0, None, None))),
                patch.object(rom_runner, "find_mooneye_assert_block", return_value={"base": 0xFF80, "flags": 0x3C}),
                patch.object(rom_runner, "classify_mooneye_assert_block", return_value="fail"),
                patch.object(
                    rom_runner,
                    "_capture_soc_failure_screen",
                    AsyncMock(return_value=(("Test failed:", "LY"), {"base": 0xFF80, "flags": 0x3C}, 0x1234)),
                ),
            ):
                state = await rom_runner.run_soc_dut_to_mooneye_signature(
                    object(),
                    rom_bytes=rom_bytes,
                    max_mcycles=1,
                )

            self.assertEqual(state.signature, MOONEYE_FAIL_BYTES)
            self.assertEqual(state.oracle_history, ((0x1234, 0x56, 0x00, 0x00),))

        asyncio.run(exercise())

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

    def test_load_manifest_entry_resolves_dma_rom(self) -> None:
        entry = load_manifest_entry("DMA_OAM_COPY")
        self.assertEqual(entry.rom_id, "DMA_OAM_COPY")
        self.assertEqual(entry.rom_path.name, "DMA_OAM_COPY.gb")
        self.assertEqual(entry.sym_path.name, "DMA_OAM_COPY.sym")
        self.assertEqual(entry.manifest_entry["requires"], ["cpu", "dma"])

    def test_load_manifest_entry_resolves_oam_dma_isolation_rom(self) -> None:
        entry = load_manifest_entry("OAM_DMA_ISOLATION")
        self.assertEqual(entry.rom_id, "OAM_DMA_ISOLATION")
        self.assertEqual(entry.rom_path.name, "OAM_DMA_ISOLATION.gb")
        self.assertEqual(entry.sym_path.name, "OAM_DMA_ISOLATION.sym")
        self.assertEqual(entry.manifest_entry["requires"], ["cpu", "dma"])

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
