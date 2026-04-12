from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"


class RomUploaderAssetsTest(unittest.TestCase):
    def test_rom_uploader_assets_and_hook_membership_exist(self) -> None:
        main_text = (ROOT / "src" / "periph" / "main.spade").read_text(encoding="utf-8")
        uploader_text = (ROOT / "src" / "periph" / "rom_uploader.spade").read_text(encoding="utf-8")
        tx_text = (ROOT / "src" / "periph" / "uart_tx.spade").read_text(encoding="utf-8")
        test_top_text = (ROOT / "src" / "periph" / "rom_uploader_test_top.spade").read_text(encoding="utf-8")
        synth_top_text = (ROOT / "src" / "periph" / "rom_uploader_synth_top.spade").read_text(encoding="utf-8")
        test_text = (ROOT / "test" / "unit" / "test_rom_uploader.py").read_text(encoding="utf-8")
        hook_text = (TOOLS / "run_precommit_checks.sh").read_text(encoding="utf-8")
        script_text = (TOOLS / "run_rom_uploader_synth_smoke.sh").read_text(encoding="utf-8")

        self.assertIn("pub mod rom_uploader;", main_text)
        self.assertIn("pub mod rom_uploader_synth_top;", main_text)
        self.assertIn("pub mod rom_uploader_test_top;", main_text)
        self.assertIn("pub mod uart_tx;", main_text)
        self.assertIn("pub struct RomUploaderOut", uploader_text)
        self.assertIn("crc32_step", uploader_text)
        self.assertIn("next_magic_window", uploader_text)
        self.assertIn("payload_write_slot", uploader_text)
        self.assertIn("pub struct UartTxOut", tx_text)
        self.assertIn("entity rom_uploader_test_top(", test_top_text)
        self.assertIn("#[no_mangle(all)]", synth_top_text)
        self.assertIn("# top = periph::rom_uploader_test_top::rom_uploader_test_top", test_text)
        self.assertIn('"test/unit/test_rom_uploader.py"', hook_text)
        self.assertIn("periph::rom_uploader_synth_top::rom_uploader_synth_top", script_text)
        self.assertIn("SB_LUT4", script_text)
