from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"


class HardwareSocCoreJoypadVerilatorAssetsTest(unittest.TestCase):
    def test_joypad_native_runner_assets_exist_and_are_hooked(self) -> None:
        ref_text = (ROOT / "bench" / "ref" / "joypad_bg_smoke.py").read_text(encoding="utf-8")
        raw_verilog = (ROOT / "test" / "harness" / "verilog" / "joypad_bg_smoke_rom_2k_raw.v").read_text(encoding="utf-8")
        runner_text = (TOOLS / "run_hardware_soc_core_joypad_bg_smoke_verilator.sh").read_text(encoding="utf-8")
        main_cpp = (TOOLS / "verilator" / "hardware_soc_core_main.cpp").read_text(encoding="utf-8")
        local_entrypoints_text = (TOOLS / "tests" / "test_local_entrypoints.py").read_text(encoding="utf-8")
        swim_text = (ROOT / "swim.toml").read_text(encoding="utf-8")

        self.assertIn("module joypad_bg_smoke_rom_raw_2k", raw_verilog)
        self.assertIn("$readmemh", raw_verilog)
        self.assertIn("joypad_bg_smoke_rom_2k.mem", raw_verilog)
        self.assertIn("joypad_bg_smoke_rom_2k_raw.v", swim_text)
        self.assertIn("bench/ref/joypad_bg_smoke.py", runner_text)
        self.assertIn("tools/write_action_script_joypad_schedule.py", runner_text)
        self.assertIn("--rom-id=joypad_bg_smoke", runner_text)
        self.assertIn("--joypad-schedule=", runner_text)
        self.assertIn("simulate_joypad_bg_smoke_state", ref_text)
        self.assertIn("render_joypad_bg_smoke_frame", ref_text)
        self.assertIn("--rom-id=", main_cpp)
        self.assertIn("--joypad-schedule=", main_cpp)
        self.assertIn("run_hardware_soc_core_joypad_bg_smoke_verilator.sh", local_entrypoints_text)


if __name__ == "__main__":
    unittest.main()
