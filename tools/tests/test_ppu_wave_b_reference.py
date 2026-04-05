from __future__ import annotations

import unittest
import warnings
from pathlib import Path

from bench.pyboy.oracle import PyBoyOracle
from spec.profiles import ModelProfile, ResetProfile


ROOT = Path(__file__).resolve().parents[2]

class PpuWaveBReferenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        warnings.filterwarnings("ignore", message="Using SDL2 binaries from pysdl2-dll.*")

    def capture_scene(self, rom_id: str, *, frames: int = 2):
        rom_path = ROOT / "bench" / "roms" / "out" / f"{rom_id}.gb"
        with PyBoyOracle(rom_path, sym_path=rom_path.with_suffix(".sym")) as oracle:
            oracle.reset(ModelProfile.DMG, ResetProfile.SkipBoot)
            pyboy = oracle._require_pyboy()
            for _ in range(frames):
                pyboy.tick(1, False, False)
            registers = {
                "lcdc": oracle.read_mem(0xFF40),
                "scy": oracle.read_mem(0xFF42),
                "scx": oracle.read_mem(0xFF43),
                "wy": oracle.read_mem(0xFF4A),
                "wx": oracle.read_mem(0xFF4B),
            }
            return oracle.frame_semantics(), registers

    def test_bg_static_scene_exposes_expected_tilemap(self) -> None:
        semantics, registers = self.capture_scene("BG_STATIC", frames=3)
        self.assertEqual(semantics.bg_tilemap.tile_id(0, 0), 0)
        self.assertEqual(semantics.bg_tilemap.tile_id(1, 0), 1)
        self.assertEqual(semantics.bg_tilemap.tile_id(0, 1), 2)
        self.assertEqual(semantics.bg_tilemap.tile_id(1, 1), 3)
        self.assertEqual(registers["scx"], 0)
        self.assertEqual(registers["scy"], 0)
        self.assertEqual(registers["lcdc"], 0x91)

    def test_bg_scroll_wrap_scene_pins_scroll_and_corner_tiles(self) -> None:
        semantics, registers = self.capture_scene("BG_SCROLL_WRAP", frames=3)
        self.assertEqual(registers["scx"], 0xFF)
        self.assertEqual(registers["scy"], 0x80)
        self.assertEqual(semantics.bg_tilemap.tile_id(0, 0), 0)
        self.assertEqual(semantics.bg_tilemap.tile_id(31, 0), 1)
        self.assertEqual(semantics.bg_tilemap.tile_id(0, 31), 2)
        self.assertEqual(semantics.bg_tilemap.tile_id(31, 31), 3)

    def test_bg_signed_addr_scene_keeps_signed_ids(self) -> None:
        semantics, registers = self.capture_scene("BG_SIGNED_ADDR", frames=3)
        self.assertEqual(registers["lcdc"], 0x81)
        self.assertEqual(semantics.bg_tilemap.tile_id(0, 0), 256)
        self.assertEqual(semantics.bg_tilemap.tile_id(1, 0), 128)
        self.assertEqual(semantics.bg_tilemap.tile_id(2, 0), 383)

    def test_window_basic_scene_exposes_window_registers_and_tilemap(self) -> None:
        semantics, registers = self.capture_scene("WINDOW_BASIC", frames=3)
        self.assertEqual(registers["wx"], 15)
        self.assertEqual(registers["wy"], 0)
        self.assertEqual(semantics.window_tilemap.tile_id(0, 0), 1)

    def test_window_line_counter_scene_programs_next_window_row(self) -> None:
        semantics, registers = self.capture_scene("WINDOW_LINE_COUNTER", frames=3)
        self.assertEqual(registers["wx"], 7)
        self.assertEqual(registers["wy"], 0)
        self.assertEqual(semantics.window_tilemap.tile_id(0, 0), 1)
        self.assertEqual(semantics.window_tilemap.tile_id(0, 1), 2)

    def test_window_edge_scene_preserves_programmed_wx_wy_values(self) -> None:
        semantics, registers = self.capture_scene("WINDOW_WX_WY_EDGE", frames=3)
        self.assertEqual(registers["wx"], 166)
        self.assertEqual(registers["wy"], 143)
        self.assertEqual(semantics.window_tilemap.tile_id(0, 0), 1)


if __name__ == "__main__":
    unittest.main()
