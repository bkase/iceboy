from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"


class FramebufferSpramAssetsTest(unittest.TestCase):
    def test_module_and_test_assets_exist(self) -> None:
        module_text = (ROOT / "src" / "video" / "framebuffer_spram.spade").read_text(encoding="utf-8")
        synth_top_text = (ROOT / "src" / "video" / "framebuffer_spram_synth_top.spade").read_text(encoding="utf-8")
        top_text = (ROOT / "src" / "video" / "framebuffer_spram_test_top.spade").read_text(encoding="utf-8")
        test_text = (ROOT / "test" / "unit" / "test_framebuffer_spram.py").read_text(encoding="utf-8")
        hook_text = (TOOLS / "run_precommit_checks.sh").read_text(encoding="utf-8")
        script_text = (TOOLS / "run_framebuffer_spram_synth_smoke.sh").read_text(encoding="utf-8")

        self.assertIn("pub mod framebuffer_spram;", (ROOT / "src" / "video" / "main.spade").read_text(encoding="utf-8"))
        self.assertIn("pub mod framebuffer_spram_synth_top;", (ROOT / "src" / "video" / "main.spade").read_text(encoding="utf-8"))
        self.assertIn("SB_SPRAM256KA", module_text)
        self.assertIn("joypad_bg_smoke", module_text)
        self.assertIn("high-motion content is explicitly out of scope", module_text)
        self.assertIn("#[no_mangle(all)]", synth_top_text)
        self.assertIn("framebuffer_spram(", synth_top_text)
        self.assertIn("framebuffer_spram(", top_text)
        self.assertIn("# top = video::framebuffer_spram_test_top::framebuffer_spram_test_top", test_text)
        self.assertIn('"test/unit/test_framebuffer_spram.py"', hook_text)
        self.assertIn("video::framebuffer_spram_synth_top::framebuffer_spram_synth_top", script_text)
        self.assertIn("SB_SPRAM256KA", script_text)
        self.assertIn("SB_RAM40_4K", script_text)
