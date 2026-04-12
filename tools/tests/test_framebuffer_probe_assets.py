from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class FramebufferProbeAssetsTest(unittest.TestCase):
    def test_probe_top_is_wired_into_video_module(self) -> None:
        module_text = (ROOT / "src" / "video" / "main.spade").read_text(encoding="utf-8")
        probe_text = (ROOT / "src" / "video" / "framebuffer_probe_top.spade").read_text(encoding="utf-8")

        self.assertIn("pub mod framebuffer_probe_top;", module_text)
        self.assertIn("SB_SPRAM256KA", probe_text)
        self.assertIn("phase_reg != 3u2", probe_text)
        self.assertIn("23039u15", probe_text)
        self.assertIn("status_o: inv uint<32>", probe_text)

    def test_probe_doc_records_go_measurement(self) -> None:
        doc_text = (ROOT / "docs" / "hardware" / "framebuffer_synth_probe.md").read_text(encoding="utf-8")

        self.assertIn("tools/run_framebuffer_synth_probe.sh", doc_text)
        self.assertIn("SB_SPRAM256KA = 1", doc_text)
        self.assertIn("SB_LUT4 = 93", doc_text)
        self.assertIn("SB_DFF = 42", doc_text)
        self.assertIn("SB_RAM40_4K = 0", doc_text)
        self.assertIn("Decision: GO", doc_text)
