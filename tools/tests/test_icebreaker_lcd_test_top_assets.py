from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class IcebreakerLcdTestTopAssetsTest(unittest.TestCase):
    def test_lcd_test_top_is_checked_in_with_reset_bridge_and_st7789_wiring(self) -> None:
        board_main = (ROOT / "src" / "board" / "main.spade").read_text(encoding="utf-8")
        top_text = (ROOT / "src" / "board" / "icebreaker_lcd_test_top.spade").read_text(encoding="utf-8")
        reset_bridge_text = (ROOT / "src" / "board" / "reset_bridge.spade").read_text(encoding="utf-8")
        lcd_text = (ROOT / "src" / "periph" / "st7789_lcd.spade").read_text(encoding="utf-8")

        self.assertIn("pub mod icebreaker_lcd_test_top;", board_main)
        self.assertIn("#[no_mangle(all)]", top_text)
        self.assertIn("entity icebreaker_lcd_test_top(", top_text)
        self.assertIn("inst reset_bridge(CLK, BTN_N, 48000u16, 16u16).rst", top_text)
        self.assertIn("inst st7789_lcd(", top_text)
        self.assertIn("frame_start_pulse", top_text)
        self.assertIn("pattern_shade(frame_index_reg, pixel_x_reg, pixel_y_reg)", top_text)
        self.assertIn("set LCD_SCK = lcd.lcd_sck;", top_text)
        self.assertIn("set LCD_MOSI = lcd.lcd_mosi;", top_text)
        self.assertIn("set LCD_CS = lcd.lcd_cs;", top_text)
        self.assertIn("set LCD_DC = lcd.lcd_dc;", top_text)
        self.assertIn("set LCD_RES = lcd.lcd_res;", top_text)
        self.assertIn("set LCD_BL = lcd.lcd_bl;", top_text)
        self.assertIn("pub struct ResetBridgeOut", reset_bridge_text)
        self.assertIn("pub entity st7789_lcd(", lcd_text)
