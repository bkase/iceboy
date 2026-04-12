from __future__ import annotations

import unittest

from bench.ref.joypad_bg_smoke import (
    CURSOR_HOME_X,
    CURSOR_HOME_Y,
    capture_joypad_bg_smoke_frame,
    palette_byte_for_state,
    simulate_joypad_bg_smoke_state,
)


class JoypadBgSmokeRefTest(unittest.TestCase):
    def test_scripted_final_state_matches_authored_intent(self) -> None:
        state = simulate_joypad_bg_smoke_state()
        self.assertEqual(state.cursor_x, CURSOR_HOME_X)
        self.assertEqual(state.cursor_y, CURSOR_HOME_Y)
        self.assertEqual(state.palette_index, 1)
        self.assertEqual(state.cursor_style, 1)
        self.assertEqual(state.invert_palette, 1)
        self.assertEqual(palette_byte_for_state(state), 0x39)

    def test_capture_emits_full_frame_with_expected_cursor_tiles(self) -> None:
        frame = capture_joypad_bg_smoke_frame()
        self.assertEqual(len(frame), 160 * 144)
        self.assertEqual(frame[(9 * 8 * 160) + (10 * 8)], 0xAA)
        self.assertEqual(frame[(9 * 8 * 160) + (11 * 8)], 0x55)
        self.assertEqual(frame[(10 * 8 * 160) + (10 * 8)], 0xFF)
        self.assertEqual(frame[(10 * 8 * 160) + (11 * 8)], 0x00)


if __name__ == "__main__":
    unittest.main()
