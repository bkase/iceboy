from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class VisibleBringupArtifactsTest(unittest.TestCase):
    def test_bg_static_bringup_doc_and_baseline_are_checked_in(self) -> None:
        doc_text = (ROOT / "docs" / "hardware" / "bringup_bg_static.md").read_text(encoding="utf-8")
        baseline = json.loads((ROOT / "docs" / "hardware" / "bg_static_top_baseline.json").read_text(encoding="utf-8"))

        self.assertIn("build/bitstreams/bg_static_icebreaker.bin", doc_text)
        self.assertIn("build/bitstreams/bg_static_icebreaker.asc", doc_text)
        self.assertIn("build/icebreaker_visible/bg_static/captured.png", doc_text)
        self.assertIn("Binary roundtrip: stable under `icepack -> iceunpack -> icepack`", doc_text)
        self.assertIn("timing-risk note", doc_text)
        self.assertIn("DBG_MCE", doc_text)
        self.assertIn("23040", doc_text)

        self.assertEqual(baseline["top"], "board::icebreaker_visible_top::icebreaker_visible_bg_static_top")
        self.assertEqual(baseline["artifacts"]["asc"], "build/bitstreams/bg_static_icebreaker.asc")
        self.assertEqual(baseline["artifacts"]["nextpnr_report"], "build/bitstreams/bg_static_icebreaker.nextpnr-report.json")
        self.assertEqual(baseline["artifacts"]["nextpnr_log"], "build/bitstreams/bg_static_icebreaker.nextpnr.log")
        self.assertEqual(baseline["artifacts"]["yosys_stat"], "build/bitstreams/synth_bg_static_icebreaker/yosys-stat.txt")
        self.assertEqual(baseline["utilization"]["lut4_used"], 4768)
        self.assertEqual(baseline["utilization"]["dff_used"], 627)
        self.assertEqual(baseline["utilization"]["spram_used"], 2)
        self.assertEqual(baseline["utilization"]["ebr_used"], 19)
        self.assertFalse(baseline["clock_constraint"]["timing_met"])

    def test_joypad_smoke_bringup_doc_and_baseline_are_checked_in(self) -> None:
        doc_text = (ROOT / "docs" / "hardware" / "bringup_joypad_smoke.md").read_text(encoding="utf-8")
        baseline = json.loads((ROOT / "docs" / "hardware" / "joypad_smoke_top_baseline.json").read_text(encoding="utf-8"))

        self.assertIn("build/bitstreams/joypad_smoke_icebreaker.bin", doc_text)
        self.assertIn("build/bitstreams/joypad_smoke_icebreaker.asc", doc_text)
        self.assertIn("build/icebreaker_visible/joypad_bg_smoke/captured.png", doc_text)
        self.assertIn("first-light visible milestone", doc_text)
        self.assertIn("D-pad: move the 2x2 cursor block", doc_text)
        self.assertIn("`A`: cycle through four palette presets.", doc_text)
        self.assertIn("`B`: toggle the cursor tile style.", doc_text)
        self.assertIn("`Start`: recenter the cursor", doc_text)
        self.assertIn("`Select`: invert the palette family.", doc_text)

        self.assertEqual(baseline["top"], "board::icebreaker_visible_top::icebreaker_visible_joypad_bg_smoke_top")
        self.assertEqual(baseline["artifacts"]["asc"], "build/bitstreams/joypad_smoke_icebreaker.asc")
        self.assertEqual(baseline["artifacts"]["nextpnr_report"], "build/bitstreams/joypad_smoke_icebreaker.nextpnr-report.json")
        self.assertEqual(baseline["artifacts"]["nextpnr_log"], "build/bitstreams/joypad_smoke_icebreaker.nextpnr.log")
        self.assertEqual(baseline["artifacts"]["yosys_stat"], "build/bitstreams/synth_joypad_smoke_icebreaker/yosys-stat.txt")
        self.assertEqual(baseline["utilization"]["lut4_used"], 4738)
        self.assertEqual(baseline["utilization"]["dff_used"], 628)
        self.assertEqual(baseline["utilization"]["spram_used"], 2)
        self.assertEqual(baseline["utilization"]["ebr_used"], 21)
        self.assertFalse(baseline["clock_constraint"]["timing_met"])


if __name__ == "__main__":
    unittest.main()
