from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class IcebreakerAluLoopTopAssetsTest(unittest.TestCase):
    def test_sources_and_baseline_are_checked_in(self) -> None:
        board_main = (ROOT / "src" / "board" / "main.spade").read_text(encoding="utf-8")
        bus_main = (ROOT / "src" / "bus" / "main.spade").read_text(encoding="utf-8")
        top_text = (ROOT / "src" / "board" / "icebreaker_alu_loop_top.spade").read_text(encoding="utf-8")
        bus_text = (ROOT / "src" / "bus" / "membus_alu_loop.spade").read_text(encoding="utf-8")
        swim_toml = (ROOT / "swim.toml").read_text(encoding="utf-8")
        baseline = json.loads((ROOT / "docs" / "hardware" / "alu_loop_top_baseline.json").read_text(encoding="utf-8"))

        self.assertIn("pub mod icebreaker_alu_loop_top;", board_main)
        self.assertIn("pub mod membus_alu_loop;", bus_main)
        self.assertIn("pub mod membus_alu_loop_test_top;", bus_main)
        self.assertIn("entity icebreaker_alu_loop_top(", top_text)
        self.assertIn("inst reset_bridge(CLK, BTN_N, 48000u16, 16u16).rst", top_text)
        self.assertIn("inst button_bank::<8, 8>(clk, buttons_i)", top_text)
        self.assertIn("inst membus_alu_loop(", top_text)
        self.assertIn("decode_buttons(pack_bool8(bits))", top_text)
        self.assertNotIn("st7789_lcd", top_text)
        self.assertIn("inst alu_loop_rom_backend(", bus_text)
        self.assertNotIn("rom_image_spram", bus_text)
        self.assertIn("test/harness/verilog/alu_loop_rom_1k_raw.v", swim_toml)

        self.assertEqual(baseline["top"], "board::icebreaker_alu_loop_top::icebreaker_alu_loop_top")
        self.assertEqual(baseline["artifacts"]["asc"], "build/bitstreams/alu_loop_icebreaker.asc")
        self.assertEqual(baseline["artifacts"]["nextpnr_report"], "build/bitstreams/alu_loop_icebreaker.nextpnr-report.json")
        self.assertEqual(baseline["artifacts"]["nextpnr_log"], "build/bitstreams/alu_loop_icebreaker.nextpnr.log")
        self.assertEqual(baseline["artifacts"]["yosys_stat"], "build/bitstreams/synth_alu_loop_icebreaker/yosys-stat.txt")
        self.assertEqual(baseline["utilization"]["spram_used"], 1)
        self.assertEqual(baseline["utilization"]["ebr_used"], 5)
        self.assertTrue(baseline["clock_constraint"]["timing_met"])
