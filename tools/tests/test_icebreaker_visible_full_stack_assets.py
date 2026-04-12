from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"


class IcebreakerVisibleFullStackAssetsTest(unittest.TestCase):
    def test_visible_full_stack_runner_assets_exist_and_palette_constants_match(self) -> None:
        runner_text = (TOOLS / "run_icebreaker_full_stack_verilator.sh").read_text(encoding="utf-8")
        main_text = (TOOLS / "verilator" / "icebreaker_visible_top_main.cpp").read_text(encoding="utf-8")
        wrapper_text = (ROOT / "test" / "harness" / "verilog" / "icebreaker_visible_top_verilator_wrapper.sv").read_text(encoding="utf-8")
        header_text = (TOOLS / "verilator" / "icebreaker_visible_palette.h").read_text(encoding="utf-8")
        schedule_text = (TOOLS / "write_action_script_joypad_schedule.py").read_text(encoding="utf-8")
        transcript_text = (TOOLS / "ref_st7789_transcript.py").read_text(encoding="utf-8")
        lcd_text = (ROOT / "src" / "periph" / "st7789_lcd.spade").read_text(encoding="utf-8")
        bg_ref_text = (ROOT / "bench" / "ref" / "BG_STATIC.py").read_text(encoding="utf-8")
        joypad_rom_text = (ROOT / "test" / "harness" / "verilog" / "joypad_bg_smoke_rom_2k_raw.v").read_text(encoding="utf-8")

        self.assertIn("icebreaker_visible_top_verilator_wrapper", wrapper_text)
        self.assertIn("icebreaker_visible_bg_static_top", wrapper_text)
        self.assertIn("icebreaker_visible_joypad_bg_smoke_top", wrapper_text)
        self.assertIn("BTN_D_UP", wrapper_text)
        self.assertIn("DIP_A", wrapper_text)
        self.assertIn("debug_gpio0_o", wrapper_text)
        self.assertIn("dbg_phase2_o", wrapper_text)
        self.assertIn("kRgb565Palette", header_text)
        self.assertIn("0xFFFFU", header_text)
        self.assertIn("0xAD55U", header_text)
        self.assertIn("0x52AAU", header_text)
        self.assertIn("0x0000U", header_text)
        self.assertIn("0xFFFF", transcript_text)
        self.assertIn("0xAD55", transcript_text)
        self.assertIn("0x52AA", transcript_text)
        self.assertIn("0x0000", transcript_text)
        self.assertIn("0xFFFFu16", lcd_text)
        self.assertIn("0xAD55u16", lcd_text)
        self.assertIn("0x52AAu16", lcd_text)
        self.assertIn("0x0000u16", lcd_text)
        self.assertIn("capture_bg_static_frame", bg_ref_text)
        self.assertIn("DMG_SHADE_VALUES", bg_ref_text)
        self.assertIn("bench/ref/BG_STATIC.py", runner_text)
        self.assertIn("bench/ref/joypad_bg_smoke.py", runner_text)
        self.assertIn("tools/write_action_script_joypad_schedule.py", runner_text)
        self.assertIn("tools/verilator/icebreaker_visible_top_main.cpp", runner_text)
        self.assertIn("--settle-frames=${JOYPAD_SETTLE_FRAMES}", runner_text)
        self.assertIn("--captured-png=", runner_text)
        self.assertIn("--reference-png=", runner_text)
        self.assertIn("--diff-png=", runner_text)
        self.assertIn("matched ", main_text)
        self.assertIn("icebreaker_visible_top mismatch first-diff=", main_text)
        self.assertIn("encode_png_grayscale", main_text)
        self.assertIn("source_completed_frames", main_text)
        self.assertIn("compare_armed", main_text)
        self.assertIn("source_frame_start", main_text)
        self.assertIn("dbg_phase2", main_text)
        self.assertIn("settle_frames", schedule_text)
        self.assertIn('reg [7:0] rom [0:2047];', joypad_rom_text)


if __name__ == "__main__":
    unittest.main()
