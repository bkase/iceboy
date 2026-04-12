from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"


class RomSpramRwAssetsTest(unittest.TestCase):
    def test_rom_spram_rw_assets_and_hook_membership_exist(self) -> None:
        main_text = (ROOT / "src" / "mem" / "phys" / "main.spade").read_text(encoding="utf-8")
        schedule_text = (ROOT / "src" / "mem" / "phys" / "ice40_spram.spade").read_text(encoding="utf-8")
        module_text = (ROOT / "src" / "mem" / "phys" / "rom_spram_rw.spade").read_text(encoding="utf-8")
        test_top_text = (ROOT / "src" / "mem" / "phys" / "rom_spram_rw_test_top.spade").read_text(encoding="utf-8")
        synth_top_text = (ROOT / "src" / "mem" / "phys" / "rom_spram_rw_synth_top.spade").read_text(encoding="utf-8")
        test_text = (ROOT / "test" / "unit" / "test_rom_spram_rw.py").read_text(encoding="utf-8")
        hook_text = (TOOLS / "run_precommit_checks.sh").read_text(encoding="utf-8")
        script_text = (TOOLS / "run_rom_spram_rw_synth_smoke.sh").read_text(encoding="utf-8")

        self.assertIn("pub mod rom_spram_rw;", main_text)
        self.assertIn("pub mod rom_spram_rw_synth_top;", main_text)
        self.assertIn("pub mod rom_spram_rw_test_top;", main_text)
        self.assertIn("pub fn rom_rw_schedule(", schedule_text)
        self.assertIn("rom_word_addr(loader_write_addr)", schedule_text)
        self.assertIn("pub entity rom_spram_rw(", module_text)
        self.assertIn("SPRAM contents are undefined after configuration", module_text)
        self.assertIn("rom_ready: !ports.loader_write_en", module_text)
        self.assertIn("entity rom_spram_rw_test_top(", test_top_text)
        self.assertIn("#[no_mangle(all)]", synth_top_text)
        self.assertIn("# top = mem::phys::rom_spram_rw_test_top::rom_spram_rw_test_top", test_text)
        self.assertIn('"test/unit/test_rom_spram_rw.py"', hook_text)
        self.assertIn("mem::phys::rom_spram_rw_synth_top::rom_spram_rw_synth_top", script_text)
        self.assertIn("SB_SPRAM256KA", script_text)
        self.assertIn("SB_RAM40_4K", script_text)
