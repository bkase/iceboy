from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class BakedRomGeneratedAssetsTest(unittest.TestCase):
    def test_generated_module_scaffolding_exists(self) -> None:
        main_text = (ROOT / "src" / "mem" / "phys" / "main.spade").read_text(encoding="utf-8")
        generated_main = (ROOT / "src" / "mem" / "phys" / "generated" / "main.spade").read_text(encoding="utf-8")
        readme_text = (ROOT / "src" / "mem" / "phys" / "generated" / "README.md").read_text(encoding="utf-8")
        tool_text = (ROOT / "tools" / "bake_rom_image.py").read_text(encoding="utf-8")

        self.assertIn("pub mod generated;", main_text)
        self.assertIn("pub mod alu_loop_rom_data;", generated_main)
        self.assertIn("pub mod bg_static_rom_data;", generated_main)
        self.assertIn("pub mod joypad_bg_smoke_rom_data;", generated_main)
        self.assertIn("tools/bake_rom_image.py", readme_text)
        self.assertIn("DETERMINISTIC_GENERATED_AT", tool_text)
        self.assertIn("parse_sym", tool_text)

        for generated_name in (
            "alu_loop_rom_data.spade",
            "bg_static_rom_data.spade",
            "joypad_bg_smoke_rom_data.spade",
        ):
            self.assertTrue((ROOT / "src" / "mem" / "phys" / "generated" / generated_name).is_file(), generated_name)
