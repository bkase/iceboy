from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"


class HardwareSocCoreVerilatorAssetsTest(unittest.TestCase):
    def test_native_runner_assets_exist_and_are_hooked(self) -> None:
        board_main = (ROOT / "src" / "board" / "main.spade").read_text(encoding="utf-8")
        top_text = (ROOT / "src" / "board" / "hardware_soc_core_verilator_top.spade").read_text(encoding="utf-8")
        core_text = (ROOT / "src" / "board" / "hardware_soc_core.spade").read_text(encoding="utf-8")
        rom_images = (ROOT / "src" / "mem" / "phys" / "rom_baked_images.spade").read_text(encoding="utf-8")
        swim_text = (ROOT / "swim.toml").read_text(encoding="utf-8")
        raw_verilog = (ROOT / "test" / "harness" / "verilog" / "bg_static_rom_1k_raw.v").read_text(encoding="utf-8")
        wrapper_text = (ROOT / "test" / "harness" / "verilog" / "hardware_soc_core_verilator_wrapper.sv").read_text(encoding="utf-8")
        main_cpp = (TOOLS / "verilator" / "hardware_soc_core_main.cpp").read_text(encoding="utf-8")
        runner_text = (TOOLS / "run_hardware_soc_core_verilator.sh").read_text(encoding="utf-8")
        local_entrypoints_text = (TOOLS / "tests" / "test_local_entrypoints.py").read_text(encoding="utf-8")

        self.assertIn("pub mod hardware_soc_core_verilator_top;", board_main)
        self.assertIn("pub entity hardware_soc_core_bg_static_1k(", core_text)
        self.assertIn("pub entity hardware_soc_core_joypad_bg_smoke_2k(", core_text)
        self.assertIn("pub entity bg_static_rom_backend(", rom_images)
        self.assertIn("pub entity joypad_bg_smoke_rom_backend(", rom_images)
        self.assertIn("pub extern entity bg_static_rom_raw_1k(", rom_images)
        self.assertIn("pub extern entity joypad_bg_smoke_rom_raw_2k(", rom_images)
        self.assertIn("bg_static_rom_1k_raw.v", swim_text)
        self.assertIn("joypad_bg_smoke_rom_2k_raw.v", swim_text)
        self.assertIn("module bg_static_rom_raw_1k", raw_verilog)
        self.assertIn("$readmemh", raw_verilog)
        self.assertIn("rom_select_i", top_text)
        self.assertIn("joypad_buttons_i", top_text)
        self.assertIn("joypad_bg_smoke_rom_backend", top_text)
        self.assertIn("hardware_soc_core(", top_text)
        self.assertIn("scanout_kind", top_text)
        self.assertIn("module hardware_soc_core_verilator_wrapper", wrapper_text)
        self.assertIn("hardware_soc_core_verilator_top impl", wrapper_text)
        self.assertIn("joypad_buttons_i", wrapper_text)
        self.assertIn("rom_select_i", wrapper_text)
        self.assertIn("--rom-id=", main_cpp)
        self.assertIn("--expected-raw=", main_cpp)
        self.assertIn("first-diff=(", main_cpp)
        self.assertIn("bg_static_rom_1k.mem", runner_text)
        self.assertIn("write_rendered_shaded_frame.py", runner_text)
        self.assertIn("BG_STATIC.sym", runner_text)
        self.assertIn("__checkpoint_scene_ready", runner_text)
        self.assertIn("hardware_soc_core_verilator_wrapper", runner_text)
        self.assertIn("run_hardware_soc_core_verilator.sh", local_entrypoints_text)


if __name__ == "__main__":
    unittest.main()
