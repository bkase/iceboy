from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BOARD_MAIN_PATH = ROOT / "src" / "board" / "main.spade"
CLOCKGEN_PATH = ROOT / "src" / "board" / "clockgen.spade"


class TimebaseScaffoldTest(unittest.TestCase):
    def test_board_module_exports_clockgen(self) -> None:
        text = BOARD_MAIN_PATH.read_text(encoding="utf-8")
        self.assertIn("pub mod clockgen;", text)

    def test_timebase_entity_contract_exists(self) -> None:
        text = CLOCKGEN_PATH.read_text(encoding="utf-8")
        for symbol in [
            "struct TimebaseOut",
            "t_ce: bool",
            "m_ce: bool",
            "sys_counter: uint<32>",
            "t_index: uint<2>",
            "m_index: uint<30>",
            "fn next_sys_counter(sys_counter: uint<32>) -> uint<32>",
            "fn t_cycle_index(sys_counter: uint<32>) -> uint<2>",
            "fn m_cycle_index(sys_counter: uint<32>) -> uint<30>",
            "fn m_cycle_enable(sys_counter: uint<32>) -> bool",
            "entity timebase(clk: clock, rst: bool) -> TimebaseOut",
            "reg(clk) sys_counter: uint<32> reset(rst: 0) = next_sys_counter(sys_counter);",
            "t_ce: true",
            "m_ce: m_cycle_enable(sys_counter)",
            "t_index: t_cycle_index(sys_counter)",
            "m_index: m_cycle_index(sys_counter)",
        ]:
            self.assertIn(symbol, text)


if __name__ == "__main__":
    unittest.main()
