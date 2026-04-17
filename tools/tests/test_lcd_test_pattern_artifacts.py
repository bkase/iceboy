from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class LcdTestPatternArtifactsTest(unittest.TestCase):
    def test_bringup_doc_and_baseline_record_are_checked_in(self) -> None:
        doc_text = (ROOT / "docs" / "hardware" / "bringup_lcd_test.md").read_text(encoding="utf-8")
        baseline = json.loads((ROOT / "docs" / "hardware" / "lcd_test_top_baseline.json").read_text(encoding="utf-8"))

        self.assertIn("build/bitstreams/lcd_test_pattern.bin", doc_text)
        self.assertIn("first bitstream to flash", doc_text)
        self.assertIn("104090", doc_text)
        self.assertIn("stable under `icepack -> iceunpack -> icepack`", doc_text)
        self.assertIn("SB_LUT4 = 283", doc_text)
        self.assertIn("first valid frame appears after roughly `140 ms`", doc_text)
        self.assertIn("2A 00 50 00 EF", doc_text)
        self.assertIn("2C", doc_text)
        self.assertIn("first flash candidate", doc_text)

        self.assertEqual(baseline["top"], "board::icebreaker_lcd_test_top::icebreaker_lcd_test_top")
        self.assertEqual(baseline["artifacts"]["asc"], "build/bitstreams/lcd_test_pattern.asc")
        self.assertEqual(baseline["artifacts"]["nextpnr_report"], "build/bitstreams/lcd_test_pattern.nextpnr-report.json")
        self.assertEqual(baseline["artifacts"]["nextpnr_log"], "build/bitstreams/lcd_test_pattern.nextpnr.log")
        self.assertEqual(baseline["artifacts"]["yosys_stat"], "build/bitstreams/synth_lcd_test_pattern/yosys-stat.txt")
        self.assertEqual(baseline["utilization"]["lut4_used"], 283)
        self.assertEqual(baseline["utilization"]["dff_used"], 114)
        self.assertEqual(baseline["utilization"]["spram_used"], 0)
        self.assertEqual(baseline["utilization"]["ebr_used"], 0)
        self.assertTrue(baseline["clock_constraint"]["timing_met"])
