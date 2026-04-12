from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class PpuCoreHwAssetsTest(unittest.TestCase):
    def test_core_hw_split_removes_sim_helper_from_hardware_path(self) -> None:
        core_hw_text = (ROOT / "src" / "ppu" / "rtl" / "core_hw.spade").read_text(encoding="utf-8")
        core_text = (ROOT / "src" / "ppu" / "rtl" / "core.spade").read_text(encoding="utf-8")
        step_text = (ROOT / "src" / "ppu" / "sem" / "step.spade").read_text(encoding="utf-8")
        sim_support_text = (ROOT / "src" / "sim" / "ppu_support.spade").read_text(encoding="utf-8")
        rtl_main_text = (ROOT / "src" / "ppu" / "rtl" / "main.spade").read_text(encoding="utf-8")

        self.assertIn("pub mod core_hw;", rtl_main_text)
        self.assertIn("pub mod core_hw_synth_top;", rtl_main_text)
        self.assertIn("pub mod core_debug_synth_top;", rtl_main_text)
        self.assertIn("pub entity ppu_core_hw(", core_hw_text)
        self.assertNotIn("lib::sim::", core_hw_text)
        self.assertIn("pub fn held_dot_output", step_text)
        self.assertIn("use lib::ppu::sem::step::{held_dot_output, step_dot};", core_text)
        self.assertNotIn("pub fn held_dot_output", sim_support_text)
        self.assertIn("#[no_mangle(all)]", (ROOT / "src" / "ppu" / "rtl" / "core_hw_synth_top.spade").read_text(encoding="utf-8"))
        self.assertIn("#[no_mangle(all)]", (ROOT / "src" / "ppu" / "rtl" / "core_debug_synth_top.spade").read_text(encoding="utf-8"))
