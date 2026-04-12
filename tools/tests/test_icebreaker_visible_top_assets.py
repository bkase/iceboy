from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"


class IcebreakerVisibleTopAssetsTest(unittest.TestCase):
    def test_visible_top_source_and_variant_helpers_are_checked_in(self) -> None:
        board_main = (ROOT / "src" / "board" / "main.spade").read_text(encoding="utf-8")
        top_text = (ROOT / "src" / "board" / "icebreaker_visible_top.spade").read_text(encoding="utf-8")
        common_text = (TOOLS / "entrypoint_common.sh").read_text(encoding="utf-8")
        build_text = (TOOLS / "build_icebreaker_variant.sh").read_text(encoding="utf-8")
        verify_text = (TOOLS / "verify_icebreaker_variant.sh").read_text(encoding="utf-8")

        self.assertIn("pub mod icebreaker_visible_top;", board_main)
        self.assertIn("entity icebreaker_visible_bg_output_stage(", top_text)
        self.assertIn("entity icebreaker_visible_joypad_output_stage(", top_text)
        self.assertIn("#[no_mangle(all)]", top_text)
        self.assertIn("entity icebreaker_visible_bg_static_top(", top_text)
        self.assertIn("entity icebreaker_visible_joypad_bg_smoke_top(", top_text)
        self.assertIn("inst reset_bridge(CLK, BTN_N, 48000u16, 16u16).rst", top_text)
        self.assertIn("joypad_buttons_from_inputs(dpad_buttons, dip_switches)", top_text)
        self.assertIn("inst hardware_soc_core_visible_bg_static_1k(", top_text)
        self.assertIn("inst hardware_soc_core_visible_joypad_bg_smoke_2k(", top_text)
        self.assertIn("fn scanout_valid(scanout: Option<ScanoutEvent>) -> bool", top_text)
        self.assertIn("fn scanout_is_frame_start(scanout: Option<ScanoutEvent>) -> bool", top_text)
        self.assertIn("fn scanout_when_ready(scanout: Option<ScanoutEvent>, ready: bool) -> Option<ScanoutEvent>", top_text)
        self.assertIn("inst framebuffer_spram(clk, false, scanout_when_ready(scanout_i, lcd.init_done), lcd.pixel_advance)", top_text)
        self.assertIn("inst st7789_lcd(", top_text)
        self.assertIn("set DEBUG_GPIO0 = framebuffer.frame_start;", top_text)
        self.assertIn("set DEBUG_GPIO1 = scanout_valid(scanout_i);", top_text)
        self.assertIn("set DBG_PC0 = framebuffer.reader_active;", top_text)
        self.assertIn("set DBG_PC1 = framebuffer.pixel_valid;", top_text)
        self.assertIn("set DBG_PC2 = lcd.frame_active;", top_text)
        self.assertIn("set DBG_PC3 = lcd.tx_active;", top_text)
        self.assertIn("set DBG_MCE = lcd.init_done;", top_text)
        self.assertIn("set DBG_PHASE0 = lcd.pixel_advance;", top_text)
        self.assertIn("set DBG_PHASE1 = cpu_halted_i;", top_text)
        self.assertIn("set DBG_PHASE2 = scanout_is_frame_start(scanout_i);", top_text)

        self.assertIn("iceboy_resolve_visible_rom_image()", common_text)
        self.assertIn("icebreaker_visible_bg_static_top", common_text)
        self.assertIn("icebreaker_visible_joypad_bg_smoke_top", common_text)
        self.assertIn("--rom-image <id>", build_text)
        self.assertIn("--rom-image <id>", verify_text)
        self.assertIn("iceboy_resolve_visible_rom_image", build_text)
        self.assertIn("iceboy_resolve_visible_rom_image", verify_text)


if __name__ == "__main__":
    unittest.main()
