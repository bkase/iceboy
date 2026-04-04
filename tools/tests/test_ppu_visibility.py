from __future__ import annotations

import unittest
from pathlib import Path

from bench.ppu.visibility import (
    READBACK_RULES,
    WRITE_VISIBILITY_RULES,
    assert_visibility_matrix_is_self_consistent,
    readback_rule_map,
    write_visibility_map,
)


ROOT = Path(__file__).resolve().parents[2]
BEHAVIOR_MATRIX_PATH = ROOT / "docs" / "ppu" / "behavior_matrix.md"
READBACK_MATRIX_PATH = ROOT / "docs" / "ppu" / "readback_matrix.md"
REGS_PATH = ROOT / "src" / "ppu" / "rtl" / "regs.spade"
SAMPLE_PATH = ROOT / "src" / "ppu" / "sem" / "sample.spade"


class PpuVisibilityMatrixTest(unittest.TestCase):
    def test_python_visibility_matrix_matches_expected_sampling_points(self) -> None:
        assert_visibility_matrix_is_self_consistent()

        writes = write_visibility_map()
        reads = readback_rule_map()

        self.assertEqual(writes["LYC"].visibility_point, "immediate")
        self.assertEqual(writes["STAT[6:3]"].visibility_point, "immediate")
        self.assertEqual(writes["SCX[2:0]"].visibility_point, "mode2_sample")
        self.assertEqual(writes["SCX[7:3]"].visibility_point, "tile_fetch_live")
        self.assertEqual(writes["WX"].visibility_point, "live_compare")
        self.assertEqual(writes["WY"].visibility_point, "mode2_sample")
        self.assertEqual(writes["BGP"].visibility_point, "pixel_pop")
        self.assertEqual(writes["LCDC.7"].visibility_point, "immediate")

        self.assertEqual(reads["LY"].readback_kind, "live_derived")
        self.assertEqual(reads["STAT"].readback_kind, "mixed_register")
        self.assertEqual(reads["STAT_LCD_OFF"].readback_kind, "derived_override")
        self.assertEqual(reads["VRAM_CPU_READ"].readback_kind, "access_policy")
        self.assertEqual(reads["OAM_CPU_READ"].readback_kind, "access_policy")
        self.assertEqual(reads["LCD_OFF_VIDEO"].readback_kind, "fully_accessible")

    def test_docs_exist_and_cover_authoritative_visibility_rows(self) -> None:
        behavior = BEHAVIOR_MATRIX_PATH.read_text(encoding="utf-8")
        readback = READBACK_MATRIX_PATH.read_text(encoding="utf-8")

        for text in [
            "SCX[2:0]",
            "Mode-2 boundary sample",
            "SCX[7:3]",
            "Tile-fetch live sample",
            "WX",
            "Live compare",
            "BGP",
            "Pixel-pop sample",
            "LCDC.7",
            "Immediate control transition",
        ]:
            self.assertIn(text, behavior)

        for text in [
            "LY",
            "Live derived",
            "STAT",
            "Mixed stored + derived",
            "mode-3 reads become `UndefinedRead` by default",
            "With LCD off, VRAM/OAM reads are unblocked",
        ]:
            self.assertIn(text, readback)

    def test_spade_sources_carry_matrix_anchor_comments(self) -> None:
        regs = REGS_PATH.read_text(encoding="utf-8")
        sample = SAMPLE_PATH.read_text(encoding="utf-8")

        self.assertIn("docs/ppu/behavior_matrix.md", regs)
        self.assertIn("mixed readback register", regs)
        self.assertIn("LY is live/read-only", regs)

        self.assertIn("Mode-2 boundary sampling captures", sample)
        self.assertIn("SCX low discard bits", sample)
        self.assertIn("Fetch/pop sampling keeps the live-read registers separate", sample)

    def test_matrix_modules_cover_expected_row_count(self) -> None:
        self.assertGreaterEqual(len(WRITE_VISIBILITY_RULES), 18)
        self.assertGreaterEqual(len(READBACK_RULES), 7)


if __name__ == "__main__":
    unittest.main()
