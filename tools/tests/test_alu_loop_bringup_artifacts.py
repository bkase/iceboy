from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class AluLoopBringupArtifactsTest(unittest.TestCase):
    def test_bringup_doc_and_baseline_record_are_checked_in(self) -> None:
        doc_text = (ROOT / "docs" / "hardware" / "bringup_alu_loop.md").read_text(encoding="utf-8")
        baseline = json.loads((ROOT / "docs" / "hardware" / "alu_loop_top_baseline.json").read_text(encoding="utf-8"))

        self.assertIn("build/bitstreams/alu_loop_icebreaker.bin", doc_text)
        self.assertIn("build/bitstreams/alu_loop_icebreaker.asc", doc_text)
        self.assertIn("build/rom_verilator/test_icebreaker_alu_loop_native/icebreaker_alu_loop.vcd", doc_text)
        self.assertIn("104090", doc_text)
        self.assertIn("4.001 ms", doc_text)
        self.assertIn("23.4375 kHz", doc_text)
        self.assertIn("does not execute `HALT`", doc_text)
        self.assertIn("P1B10", doc_text)
        self.assertIn("Loop-body cadence", doc_text)
        self.assertIn("__pass", doc_text)

        self.assertEqual(baseline["top"], "board::icebreaker_alu_loop_top::icebreaker_alu_loop_top")
        self.assertEqual(baseline["artifacts"]["asc"], "build/bitstreams/alu_loop_icebreaker.asc")
        self.assertEqual(baseline["artifacts"]["nextpnr_report"], "build/bitstreams/alu_loop_icebreaker.nextpnr-report.json")
        self.assertEqual(baseline["artifacts"]["nextpnr_log"], "build/bitstreams/alu_loop_icebreaker.nextpnr.log")
        self.assertEqual(baseline["artifacts"]["yosys_stat"], "build/bitstreams/synth_alu_loop_icebreaker/yosys-stat.txt")
        self.assertEqual(baseline["utilization"]["lut4_used"], 3808)
        self.assertEqual(baseline["utilization"]["dff_used"], 439)
        self.assertEqual(baseline["utilization"]["spram_used"], 1)
        self.assertEqual(baseline["utilization"]["ebr_used"], 5)
        self.assertTrue(baseline["clock_constraint"]["timing_met"])


if __name__ == "__main__":
    unittest.main()
