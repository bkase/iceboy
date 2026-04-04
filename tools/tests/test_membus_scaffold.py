from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BUS_MAIN_PATH = ROOT / "src" / "bus" / "main.spade"
MEMBUS_PATH = ROOT / "src" / "bus" / "membus.spade"
MEMBUS_TEST_TOP_PATH = ROOT / "src" / "bus" / "membus_test_top.spade"


class MembusScaffoldTest(unittest.TestCase):
    def test_bus_module_exports_membus_surfaces(self) -> None:
        text = BUS_MAIN_PATH.read_text(encoding="utf-8")
        self.assertIn("pub mod membus;", text)
        self.assertIn("pub mod membus_test_top;", text)

    def test_membus_contract_matches_wave_a_memory_map(self) -> None:
        text = MEMBUS_PATH.read_text(encoding="utf-8")
        for symbol in [
            "pub entity membus(",
            "pub fn observe_req(",
            "clk: clock",
            "rst: bool",
            "m_ce: bool",
            "req: BusReq",
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
            "clocked_memory_init::<32768, 1, 15, uint<8>>",
            "clocked_memory_init::<8192, 1, 13, uint<8>>",
            "clocked_memory_init::<127, 1, 7, uint<8>>",
            "idle_bus_obs()",
            "idle_bus_resp()",
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
            "oam_dma_active_i: bool",
            "ppu_vram_active_i: bool",
            "ppu_oam_active_i: bool",
            ") -> uint<15>",
            "let (resp, obs) = inst membus(",
        ]:
            self.assertIn(symbol, text)


if __name__ == "__main__":
    unittest.main()
