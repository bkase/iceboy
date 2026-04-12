from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"


class RomBakedEbrAssetsTest(unittest.TestCase):
    def test_rom_baked_ebr_assets_and_hook_membership_exist(self) -> None:
        main_text = (ROOT / "src" / "mem" / "phys" / "main.spade").read_text(encoding="utf-8")
        module_text = (ROOT / "src" / "mem" / "phys" / "rom_baked_ebr.spade").read_text(encoding="utf-8")
        test_top_text = (ROOT / "src" / "mem" / "phys" / "rom_baked_ebr_test_top.spade").read_text(encoding="utf-8")
        synth_top_text = (ROOT / "src" / "mem" / "phys" / "rom_baked_ebr_synth_top.spade").read_text(encoding="utf-8")
        test_text = (ROOT / "test" / "unit" / "test_rom_baked_ebr.py").read_text(encoding="utf-8")
        hook_text = (TOOLS / "run_precommit_checks.sh").read_text(encoding="utf-8")
        script_text = (TOOLS / "run_rom_baked_ebr_synth_smoke.sh").read_text(encoding="utf-8")
        raw_verilog_text = (ROOT / "test" / "harness" / "verilog" / "rom_baked_ebr_raw.v").read_text(encoding="utf-8")
        swim_text = (ROOT / "swim.toml").read_text(encoding="utf-8")

        self.assertIn("pub mod rom_baked_ebr;", main_text)
        self.assertIn("pub mod rom_baked_ebr_synth_top;", main_text)
        self.assertIn("pub mod rom_baked_ebr_test_top;", main_text)
        self.assertIn("DMA reads from the ROM window return 0xff", module_text)
        self.assertIn("rom_baked_ebr_raw_1k", module_text)
        self.assertIn("rom_baked_ebr_raw_8k", module_text)
        self.assertIn("Loader writes are ignored", module_text)
        self.assertIn("rom_baked_ebr_1k(", test_top_text)
        self.assertIn("#[no_mangle(all)]", synth_top_text)
        self.assertIn("rom_baked_ebr_4k(", synth_top_text)
        self.assertIn("# top = mem::phys::rom_baked_ebr_test_top::rom_baked_ebr_test_top", test_text)
        self.assertIn('"test/unit/test_rom_baked_ebr.py"', hook_text)
        self.assertIn("--size <1024|4096>", script_text)
        self.assertIn("EXPECTED_EBR=8", script_text)
        self.assertIn("$readmemh", raw_verilog_text)
        self.assertIn("rom_baked_ebr_raw_4k", raw_verilog_text)
        self.assertIn("test/harness/verilog/rom_baked_ebr_raw.v", swim_text)

        for mem_name in (
            "rom_baked_ebr_1k.mem",
            "rom_baked_ebr_2k.mem",
            "rom_baked_ebr_4k.mem",
            "rom_baked_ebr_8k.mem",
        ):
            self.assertTrue((ROOT / "test" / "harness" / "verilog" / mem_name).is_file(), mem_name)
