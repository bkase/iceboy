from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class UartRomBringupArtifactsTest(unittest.TestCase):
    def test_uart_rom_bringup_doc_and_baseline_are_checked_in(self) -> None:
        doc_text = (ROOT / "docs" / "hardware" / "bringup_uart_rom.md").read_text(encoding="utf-8")
        baseline = json.loads((ROOT / "docs" / "hardware" / "uart_rom_top_baseline.json").read_text(encoding="utf-8"))

        self.assertIn("build/bitstreams/uart_rom_icebreaker.bin", doc_text)
        self.assertIn("build/bitstreams/uart_rom_icebreaker.asc", doc_text)
        self.assertIn("tools/upload_rom_icebreaker.py", doc_text)
        self.assertIn("Upload OK", doc_text)
        self.assertIn("Upload failed (DUT reported NACK)", doc_text)
        self.assertIn("Upload timed out", doc_text)
        self.assertIn("1-byte XOR checksum", doc_text)
        self.assertIn("Binary roundtrip: stable under `icepack -> iceunpack -> icepack`", doc_text)
        self.assertIn("LCD stays dark", doc_text)
        self.assertIn("bench/roms/out/bg_static.gb", doc_text)
        self.assertIn("bench/roms/out/joypad_bg_smoke.gb", doc_text)

        self.assertEqual(baseline["top"], "board::icebreaker_uart_rom_top::icebreaker_uart_rom_top")
        self.assertEqual(baseline["artifacts"]["asc"], "build/bitstreams/uart_rom_icebreaker.asc")
        self.assertEqual(baseline["artifacts"]["nextpnr_report"], "build/bitstreams/uart_rom_icebreaker.nextpnr-report.json")
        self.assertEqual(baseline["artifacts"]["nextpnr_log"], "build/bitstreams/uart_rom_icebreaker.nextpnr.log")
        self.assertEqual(baseline["artifacts"]["yosys_stat"], "build/bitstreams/synth_uart_rom_icebreaker/yosys-stat.txt")
        self.assertEqual(baseline["pnr"]["status"], "passed")
        self.assertIsNone(baseline["pnr"]["error"])
        self.assertEqual(baseline["utilization"]["lut4_used"], 4957)
        self.assertEqual(baseline["utilization"]["dff_used"], 757)
        self.assertEqual(baseline["utilization"]["spram_used"], 3)
        self.assertEqual(baseline["utilization"]["ebr_used"], 17)
        self.assertEqual(baseline["utilization"]["logic_cells_used"], 5240)
        self.assertFalse(baseline["clock_constraint"]["timing_met"])


if __name__ == "__main__":
    unittest.main()
