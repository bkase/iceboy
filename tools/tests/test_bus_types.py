from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BUS_MAIN_PATH = ROOT / "src" / "bus" / "main.spade"
BUS_TYPES_PATH = ROOT / "src" / "bus" / "types.spade"


class BusTypesContractTest(unittest.TestCase):
    def test_bus_module_exports_types_submodule(self) -> None:
        text = BUS_MAIN_PATH.read_text(encoding="utf-8")
        self.assertIn("pub mod types;", text)

    def test_bus_contract_matches_phase_two_bus_interface(self) -> None:
        text = BUS_TYPES_PATH.read_text(encoding="utf-8")

        for symbol in [
            "enum BusReq",
            "Idle",
            "Read { addr: uint<16> }",
            "Write { addr: uint<16>, data: uint<8> }",
            "struct BusResp",
            "data: uint<8>",
            "enum BusRegion",
            "Rom",
            "Vram",
            "CartRam",
            "Wram",
            "Echo",
            "Oam",
            "NotUsable",
            "Io",
            "Hram",
            "Ie",
            "enum BusOwner",
            "Cpu",
            "OamDma",
            "Ppu",
            "struct BusObs",
            "region: BusRegion",
            "blocked: bool",
            "owner: BusOwner",
            "pub fn idle_bus_req() -> BusReq",
            "pub fn idle_bus_resp() -> BusResp",
            "pub fn idle_bus_obs() -> BusObs",
            "pub fn default_bus_obs() -> BusObs",
            "BusObs$(region: BusRegion::Hram, blocked: false, owner: BusOwner::Idle)",
        ]:
            self.assertIn(symbol, text)


if __name__ == "__main__":
    unittest.main()
