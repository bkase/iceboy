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
            "dot_ce: bool",
            "line_start: bool",
            "frame_start: bool",
            "line_index: uint<8>",
            "dot_in_line: uint<9>",
            "fn next_sys_counter(sys_counter: uint<32>) -> uint<32>",
            "fn t_cycle_index(sys_counter: uint<32>) -> uint<2>",
            "fn m_cycle_index(sys_counter: uint<32>) -> uint<30>",
            "fn m_cycle_enable(sys_counter: uint<32>) -> bool",
            "fn next_dot_in_line(dot_in_line: uint<9>) -> uint<9>",
            "fn next_line_index(dot_in_line: uint<9>, line_index: uint<8>) -> uint<8>",
            "entity timebase(clk: clock, rst: bool) -> TimebaseOut",
            "reg(clk) sys_counter: uint<32> reset(rst: 0) = next_sys_counter(sys_counter);",
            "reg(clk) line_index: uint<8> reset(rst: 0u8) = next_line_index(dot_in_line, line_index);",
            "reg(clk) dot_in_line: uint<9> reset(rst: 0u9) = next_dot_in_line(dot_in_line);",
            "t_ce: true",
            "m_ce: m_cycle_enable(sys_counter)",
            "t_index: t_cycle_index(sys_counter)",
            "m_index: m_cycle_index(sys_counter)",
            "dot_ce: true",
            "line_start: dot_in_line == 0u9",
            "frame_start: dot_in_line == 0u9 && line_index == 0u8",
            "line_index: line_index",
            "dot_in_line: dot_in_line",
        ]:
            self.assertIn(symbol, text)


if __name__ == "__main__":
    unittest.main()
