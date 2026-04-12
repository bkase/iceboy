import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class HardwareSocCoreAssetsTest(unittest.TestCase):
    def test_hardware_soc_core_exports_hw_safe_nucleus_and_test_top(self) -> None:
        soc_text = (ROOT / "src" / "board" / "hardware_soc_core.spade").read_text(encoding="utf-8")
        test_top_text = (ROOT / "src" / "board" / "hardware_soc_core_test_top.spade").read_text(encoding="utf-8")
        board_main_text = (ROOT / "src" / "board" / "main.spade").read_text(encoding="utf-8")

        self.assertIn("pub mod hardware_soc_core;", board_main_text)
        self.assertIn("pub mod hardware_soc_core_test_top;", board_main_text)
        self.assertIn("pub entity hardware_soc_core(", soc_text)
        self.assertIn("pub entity hardware_soc_core_alu_loop(", soc_text)
        self.assertIn("pub entity hardware_soc_core_bg_static_1k(", soc_text)
        self.assertIn("pub entity hardware_soc_core_joypad_bg_smoke_2k(", soc_text)
        self.assertIn("pub entity hardware_soc_core_rw(", soc_text)
        self.assertIn("use lib::ppu::rtl::core_hw_bg_window", soc_text)
        self.assertIn("inst oam_dma(", soc_text)
        self.assertIn("readback_register(", soc_text)
        self.assertNotIn("lib::sim::", soc_text)
        self.assertNotIn("let stat_ =", soc_text)
        self.assertNotIn("let bgp_ =", soc_text)
        self.assertIn("#[no_mangle(all)]", test_top_text)
        self.assertIn("hardware_soc_core_alu_loop(", test_top_text)


if __name__ == "__main__":
    unittest.main()
