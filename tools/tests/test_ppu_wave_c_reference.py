from __future__ import annotations

import unittest
import warnings
from pathlib import Path

from bench.pyboy.oracle import CommitPoint, PyBoyOracle
from spec.profiles import ModelProfile, ResetProfile


ROOT = Path(__file__).resolve().parents[2]

class PpuWaveCReferenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        warnings.filterwarnings("ignore", message="Using SDL2 binaries from pysdl2-dll.*")

    def capture_scene(self, rom_id: str, *, frames: int = 3):
        rom_path = ROOT / "bench" / "roms" / "out" / f"{rom_id}.gb"
        with PyBoyOracle(
            rom_path,
            sym_path=rom_path.with_suffix(".sym"),
            commit_points=(CommitPoint(bank=None, addr="__checkpoint_scene_ready"),),
        ) as oracle:
            oracle.reset(ModelProfile.DMG, ResetProfile.SkipBoot)
            checkpoint = oracle.step_commit()
            registers = {
                "lcdc": oracle.read_mem(0xFF40),
                "obp0": oracle.read_mem(0xFF48),
                "obp1": oracle.read_mem(0xFF49),
                "bgp": oracle.read_mem(0xFF47),
            }
            return oracle.frame_semantics(), registers, checkpoint

    def test_obj_basic_scene_renders_one_black_sprite(self) -> None:
        semantics, registers, checkpoint = self.capture_scene("OBJ_BASIC")
        self.assertEqual(checkpoint.label, "__checkpoint_scene_ready")
        self.assertEqual(registers["lcdc"], 0x93)
        self.assertEqual(registers["obp0"], 0xE4)
        self.assertTrue(semantics.sprites[0].on_screen)
        self.assertEqual((semantics.sprites[0].x, semantics.sprites[0].y), (32, 40))
        self.assertEqual(semantics.sprites[0].tile_identifier, 1)
        self.assertEqual(semantics.sprites[0].height, 8)
        self.assertFalse(semantics.sprites[0].x_flip)
        self.assertFalse(semantics.sprites[0].y_flip)

    def test_obj_priority_scene_resolves_overlap_to_smaller_x(self) -> None:
        semantics, registers, _checkpoint = self.capture_scene("OBJ_PRIORITY")
        self.assertEqual(registers["lcdc"], 0x93)
        self.assertEqual(semantics.sprites[0].tile_identifier, 1)
        self.assertEqual(semantics.sprites[1].tile_identifier, 2)
        self.assertEqual((semantics.sprites[0].x, semantics.sprites[0].y), (40, 40))
        self.assertEqual((semantics.sprites[1].x, semantics.sprites[1].y), (42, 40))
        self.assertLess(semantics.sprites[0].x, semantics.sprites[1].x)

    def test_obj_8x16_scene_uses_paired_tiles(self) -> None:
        semantics, registers, _checkpoint = self.capture_scene("OBJ_8X16")
        self.assertEqual(registers["lcdc"], 0x97)
        self.assertEqual((semantics.sprites[0].x, semantics.sprites[0].y), (64, 40))
        self.assertEqual(semantics.sprites[0].height, 16)
        self.assertEqual(semantics.sprites[0].tile_identifier & 0xFE, 2)

    def test_obj_flip_scene_keeps_flip_flags_and_mirrors_pattern(self) -> None:
        semantics, registers, _checkpoint = self.capture_scene("OBJ_FLIP")
        self.assertEqual(registers["lcdc"], 0x93)
        self.assertEqual((semantics.sprites[0].x, semantics.sprites[0].y), (32, 40))
        self.assertTrue(semantics.sprites[0].x_flip)
        self.assertTrue(semantics.sprites[0].y_flip)
        self.assertEqual(semantics.sprites[0].tile_identifier, 4)

    def test_obj_bg_mask_scene_hides_sprite_behind_nonzero_bg(self) -> None:
        semantics, registers, _checkpoint = self.capture_scene("OBJ_BG_MASK")
        self.assertEqual(registers["lcdc"], 0x93)
        self.assertTrue(semantics.sprites[0].obj_bg_priority)
        self.assertEqual((semantics.sprites[0].x, semantics.sprites[0].y), (0, 0))
        self.assertEqual(semantics.bg_tilemap.tile_id(0, 0), 1)


if __name__ == "__main__":
    unittest.main()
