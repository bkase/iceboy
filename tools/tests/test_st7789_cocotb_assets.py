from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class St7789CocotbAssetsTest(unittest.TestCase):
    def test_cocotb_test_uses_golden_transcript_and_stays_in_precommit(self) -> None:
        test_text = (ROOT / "test" / "unit" / "test_st7789_lcd.py").read_text(encoding="utf-8")
        hook_text = (ROOT / "tools" / "run_precommit_checks.sh").read_text(encoding="utf-8")

        self.assertIn("from ref_st7789_transcript import generate_frame_transcript, generate_init_transcript", test_text)
        self.assertIn("assert_transcript_matches", test_text)
        self.assertIn("generate_init_transcript()", test_text)
        self.assertIn("generate_frame_transcript(bytes(frame))", test_text)
        self.assertIn('"test/unit/test_st7789_lcd.py"', hook_text)


if __name__ == "__main__":
    unittest.main()
