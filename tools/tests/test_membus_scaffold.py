from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BUS_MAIN_PATH = ROOT / "src" / "bus" / "main.spade"
MEMBUS_PATH = ROOT / "src" / "bus" / "membus.spade"
MEMBUS_TEST_TOP_PATH = ROOT / "src" / "bus" / "membus_test_top.spade"
OBSERVE_REQ_TEST_TOP_PATH = ROOT / "src" / "bus" / "observe_req_test_top.spade"
PPU_EVENT_BRIDGE_PATH = ROOT / "src" / "bus" / "ppu_event_bridge.spade"
PPU_EVENT_BRIDGE_TEST_TOP_PATH = ROOT / "src" / "bus" / "ppu_event_bridge_test_top.spade"
MEM_MAIN_PATH = ROOT / "src" / "mem" / "main.spade"
MEM_LOGICAL_MAIN_PATH = ROOT / "src" / "mem" / "logical" / "main.spade"
MEM_PHYS_MAIN_PATH = ROOT / "src" / "mem" / "phys" / "main.spade"
MEM_MAP_PATH = ROOT / "src" / "mem" / "logical" / "map.spade"
SPRAM_PATH = ROOT / "src" / "mem" / "phys" / "spram.spade"
EBR_PATH = ROOT / "src" / "mem" / "phys" / "ebr.spade"


class MembusScaffoldTest(unittest.TestCase):
    def test_bus_module_exports_membus_surfaces(self) -> None:
        text = BUS_MAIN_PATH.read_text(encoding="utf-8")
        self.assertIn("pub mod membus;", text)
        self.assertIn("pub mod membus_test_top;", text)
        self.assertIn("pub mod observe_req_test_top;", text)
        self.assertIn("pub mod ppu_event_bridge;", text)
        self.assertIn("pub mod ppu_event_bridge_test_top;", text)

    def test_mem_module_exports_physical_and_logical_layers(self) -> None:
        self.assertIn("mod logical;", MEM_MAIN_PATH.read_text(encoding="utf-8"))
        self.assertIn("mod phys;", MEM_MAIN_PATH.read_text(encoding="utf-8"))
        self.assertIn("pub mod map;", MEM_LOGICAL_MAIN_PATH.read_text(encoding="utf-8"))
        phys_text = MEM_PHYS_MAIN_PATH.read_text(encoding="utf-8")
        self.assertIn("pub mod ebr;", phys_text)
        self.assertIn("pub mod spram;", phys_text)

    def test_memory_mapping_surface_declares_physical_memory_plan(self) -> None:
        text = MEM_MAP_PATH.read_text(encoding="utf-8")
        for symbol in [
            "pub enum PhysicalMemoryKind",
            "Spram",
            "Ebr",
            "Unmapped",
            "pub fn physical_memory_kind(region: BusRegion) -> PhysicalMemoryKind",
            "BusRegion::Rom => PhysicalMemoryKind::Spram",
            "BusRegion::Wram => PhysicalMemoryKind::Spram",
            "BusRegion::Oam => PhysicalMemoryKind::Ebr",
            "BusRegion::Hram => PhysicalMemoryKind::Ebr",
            "pub fn rom_addr(region: BusRegion, addr: uint<16>) -> uint<15>",
            "pub fn vram_addr(region: BusRegion, addr: uint<16>) -> uint<13>",
            "pub fn wram_addr(region: BusRegion, addr: uint<16>) -> uint<13>",
            "pub fn hram_addr(region: BusRegion, addr: uint<16>) -> uint<7>",
            "pub fn oam_addr(region: BusRegion, addr: uint<16>) -> uint<8>",
        ]:
            self.assertIn(symbol, text)

    def test_physical_memory_wrappers_exist_for_spram_and_ebr(self) -> None:
        spram_text = SPRAM_PATH.read_text(encoding="utf-8")
        for symbol in [
            "pub entity rom_image_spram(",
            "pub entity wram_spram(",
            "pub entity vram_spram(",
            "clocked_memory_init::<32768, 1, 15, uint<8>>",
            "clocked_memory_init::<8192, 1, 13, uint<8>>",
            "inst read_memory(mem, cpu_addr)",
            "inst read_memory(mem, dma_addr)",
        ]:
            self.assertIn(symbol, spram_text)

        ebr_text = EBR_PATH.read_text(encoding="utf-8")
        for symbol in [
            "pub entity hram_ebr(",
            "pub entity oam_ebr(",
            "clocked_memory_init::<127, 1, 7, uint<8>>",
            "clocked_memory_init::<256, 2, 8, uint<8>>",
            "inst read_memory(mem, read_addr)",
            "dma_write_en",
            "cpu_write_en",
        ]:
            self.assertIn(symbol, ebr_text)

    def test_membus_contract_matches_wave_a_memory_map(self) -> None:
        text = MEMBUS_PATH.read_text(encoding="utf-8")
        for symbol in [
            "pub entity membus(",
            "pub fn observe_req(",
            "clk: clock",
            "rst: bool",
            "m_ce: bool",
            "req: BusReq",
            "memory_behavior_profile: MemoryBehaviorProfile",
            "oam_dma_active: bool",
            "ppu_vram_active: bool",
            "ppu_oam_active: bool",
            ") -> (BusResp, BusObs)",
            "BusRegion::Rom",
            "BusRegion::Wram",
            "BusRegion::Io",
            "BusRegion::Hram",
            "BusRegion::Ie",
            "BusOwner::OamDma",
            "BusOwner::Ppu",
            "fn region_owner(region: BusRegion, oam_dma_active: bool, ppu_vram_active: bool, ppu_oam_active: bool) -> BusOwner",
            "fn blocked_req(req: BusReq, owner: BusOwner) -> bool",
            "use lib::mem::logical::map::{hram_addr, oam_addr, physical_memory_kind, rom_addr, wram_addr};",
            "clocked_memory_init::<32768, 1, 15, uint<8>>",
            "clocked_memory_init::<8192, 1, 13, uint<8>>",
            "clocked_memory_init::<127, 1, 7, uint<8>>",
            "clocked_memory_init::<256, 2, 8, uint<8>>",
            "let dma = inst oam_dma(",
            "fn dma_start(req: BusReq) -> (bool, uint<8>)",
            "idle_bus_obs()",
            "idle_bus_resp()",
            "physical_memory_kind(region)",
            "BusRegion::Oam => inst read_memory(oam_mem, oam_addr(region, addr))",
            "read_memory(",
        ]:
            self.assertIn(symbol, text)

    def test_membus_test_top_provides_stable_unit_projection(self) -> None:
        text = MEMBUS_TEST_TOP_PATH.read_text(encoding="utf-8")
        for symbol in [
            "pub entity membus_test_top(",
            "req_kind_i: uint<2>",
            "addr_i: uint<16>",
            "data_i: uint<8>",
            "memory_behavior_profile_i: uint<2>",
            "oam_dma_active_i: bool",
            "ppu_vram_active_i: bool",
            "ppu_oam_active_i: bool",
            ") -> uint<15>",
            "decode_memory_behavior_profile(memory_behavior_profile_i)",
            "let (resp, obs) = inst membus(",
        ]:
            self.assertIn(symbol, text)

    def test_observe_req_test_top_exists_for_formal_ownership_checks(self) -> None:
        text = OBSERVE_REQ_TEST_TOP_PATH.read_text(encoding="utf-8")
        for symbol in [
            "pub entity observe_req_test_top(",
            "let obs = observe_req(",
            ") -> uint<7>",
        ]:
            self.assertIn(symbol, text)

    def test_ppu_event_bridge_contract_matches_wave_a_event_replay_surface(self) -> None:
        text = PPU_EVENT_BRIDGE_PATH.read_text(encoding="utf-8")
        for symbol in [
            "pub entity ppu_event_bridge(",
            "req: BusReq",
            "frame_start: bool",
            "line_index: uint<8>",
            "dot_in_line: uint<9>",
            ") -> ([TimedPpuEvent; 4], uint<4>)",
            "fn decode_mmio_target(addr: uint<16>) -> (bool, MmioReg)",
            "0xff40u16 => (true, MmioReg::Lcdc)",
            "addr == 0xff46u16",
            "PpuEventKind::DmaStart$(source_high: source_high)",
            "PpuEventKind::ForceLcdPower$(enabled: enabled)",
            "reg(clk) lcdc7_shadow: bool",
            "reg(clk) seq_counter: uint<64>",
        ]:
            self.assertIn(symbol, text)

    def test_ppu_event_bridge_test_top_provides_stable_projection(self) -> None:
        text = PPU_EVENT_BRIDGE_TEST_TOP_PATH.read_text(encoding="utf-8")
        for symbol in [
            "pub entity ppu_event_bridge_test_top(",
            "req_kind_i: uint<2>",
            "frame_start_i: bool",
            "line_index_i: uint<8>",
            "dot_in_line_i: uint<9>",
            ") -> uint<77>",
            "let (events, count) = inst ppu_event_bridge(",
            "encode_slot(events[0], count != 0u4)",
            "encode_slot(events[1], count > 1u4)",
        ]:
            self.assertIn(symbol, text)


if __name__ == "__main__":
    unittest.main()
