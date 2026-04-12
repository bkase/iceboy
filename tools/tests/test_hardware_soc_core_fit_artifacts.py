from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class HardwareSocCoreFitArtifactsTest(unittest.TestCase):
    def test_fit_probe_top_and_gate_decision_are_checked_in(self) -> None:
        board_main = (ROOT / "src" / "board" / "main.spade").read_text(encoding="utf-8")
        top_text = (ROOT / "src" / "board" / "icebreaker_hardware_soc_core_fit_top.spade").read_text(encoding="utf-8")
        doc_text = (ROOT / "docs" / "hardware" / "ppu_fit_decision.md").read_text(encoding="utf-8")
        baseline = json.loads((ROOT / "docs" / "hardware" / "hardware_soc_core_full_baseline.json").read_text(encoding="utf-8"))

        self.assertIn("pub mod icebreaker_hardware_soc_core_fit_top;", board_main)
        self.assertIn("entity icebreaker_hardware_soc_core_fit_top(", top_text)
        self.assertIn("inst reset_bridge(CLK, BTN_N, 48000u16, 16u16).rst", top_text)
        self.assertIn("inst button_bank::<8, 8>(CLK, buttons)", top_text)
        self.assertIn("inst hardware_soc_core_bg_static_1k(", top_text)
        self.assertNotIn("st7789_lcd", top_text)

        self.assertIn("does not fit the iCE40UP5K", doc_text)
        self.assertIn("build/hw_probes/hardware_soc_core_full/synth/yosys-stat.txt", doc_text)
        self.assertIn("build/hw_probes/hardware_soc_core_full/nextpnr.log", doc_text)
        self.assertIn("SB_LUT4 = 6637", doc_text)
        self.assertIn("SB_DFF = 1055", doc_text)
        self.assertIn("144%", doc_text)
        self.assertIn("Outcome `(c)`: full PPU does not fit.", doc_text)
        self.assertIn("Proceed with `bd-24li`", doc_text)
        self.assertIn("`bd-1u8i`", doc_text)

        self.assertEqual(
            baseline["top"],
            "board::icebreaker_hardware_soc_core_fit_top::icebreaker_hardware_soc_core_fit_top",
        )
        self.assertEqual(
            baseline["artifacts"]["asc"],
            "build/hw_probes/hardware_soc_core_full/icebreaker_hardware_soc_core_fit_top.asc",
        )
        self.assertEqual(
            baseline["artifacts"]["yosys_stat"],
            "build/hw_probes/hardware_soc_core_full/synth/yosys-stat.txt",
        )
        self.assertEqual(baseline["utilization"]["lut4_used"], 6637)
        self.assertEqual(baseline["utilization"]["dff_used"], 1055)
        self.assertEqual(baseline["utilization"]["spram_used"], 1)
        self.assertEqual(baseline["utilization"]["ebr_used"], 21)
        self.assertFalse(baseline["utilization"]["fits_up5k_lut4"])
        self.assertFalse(baseline["utilization"]["fits_up5k_dff"])
        self.assertEqual(baseline["pnr"]["status"], "failed")
        self.assertFalse(baseline["pnr"]["timing_report_available"])


if __name__ == "__main__":
    unittest.main()
