from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SIM_TYPES_PATH = ROOT / "src" / "sim" / "types.spade"
CPU_TOP_PATH = ROOT / "src" / "sim" / "cpu_test_top.spade"
SOC_TOP_PATH = ROOT / "src" / "sim" / "soc_lockstep_top.spade"


class SimScaffoldTest(unittest.TestCase):
    def test_sim_stimulus_fields_match_architecture_contract(self) -> None:
        text = SIM_TYPES_PATH.read_text(encoding="utf-8")
        for field in [
            "joyp_buttons: Option<JoypButtons>",
            "if_set_bits: uint<5>",
            "if_clear_bits: uint<5>",
            "ie_override: Option<uint<5>>",
            "dma_start: Option<uint<8>>",
            "serial_inject: Option<uint<8>>",
            "freeze_arch_time: bool",
            "cpu_hold_only: bool",
        ]:
            self.assertIn(field, text)

    def test_sim_top_scaffolds_exist_with_stable_entity_names(self) -> None:
        text = CPU_TOP_PATH.read_text(encoding="utf-8")
        self.assertIn("entity cpu_test_top(", text)
        for symbol in [
            "commit_seq: uint<64>",
            "pc: uint<16>",
            "bus_req_kind: uint<2>",
            "bus_req_addr: uint<16>",
            "bus_req_data: uint<8>",
            "let cpu = inst cpu_core(",
        ]:
            self.assertIn(symbol, text)
        soc_text = SOC_TOP_PATH.read_text(encoding="utf-8")
        self.assertIn("entity soc_lockstep_top(", soc_text)
        for symbol in [
            "commit_seq: uint<64>",
            "sys_counter: uint<32>",
            "m_ce: bool",
            "bus_region: uint<4>",
            "let tb = inst timebase(",
            "let cpu = inst cpu_core(",
        ]:
            self.assertIn(symbol, soc_text)


if __name__ == "__main__":
    unittest.main()
