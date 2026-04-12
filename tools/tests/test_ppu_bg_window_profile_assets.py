from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"


class PpuBgWindowProfileAssetsTest(unittest.TestCase):
    def test_profile_assets_and_hook_membership_exist(self) -> None:
        regs_text = (ROOT / "src" / "ppu" / "rtl" / "regs.spade").read_text(encoding="utf-8")
        test_top_text = (ROOT / "src" / "ppu" / "rtl" / "regs_bg_window_test_top.spade").read_text(encoding="utf-8")
        test_text = (ROOT / "test" / "unit" / "test_regs_bg_window.py").read_text(encoding="utf-8")
        hook_text = (TOOLS / "run_precommit_checks.sh").read_text(encoding="utf-8")

        self.assertIn("pub fn apply_mmio_write_bg_window", regs_text)
        self.assertIn("decode_lcdc_bg_window", regs_text)
        self.assertIn("readback_register(0x40u8", test_top_text)
        self.assertIn("apply_mmio_write_bg_window", test_top_text)
        self.assertIn("# top = ppu::rtl::regs_bg_window_test_top::regs_bg_window_test_top", test_text)
        self.assertIn('"test/unit/test_regs_bg_window.py"', hook_text)


if __name__ == "__main__":
    unittest.main()
