from __future__ import annotations

import tempfile
import sys
import unittest
import warnings
from pathlib import Path

from bench.actions.generators import IeOverrideEvent, IfClearBitsEvent, IfSetBitsEvent, MemoryWriteEvent
from bench.pyboy.oracle import (
    CommitPoint,
    PyBoyOracle,
    capture_checkpoint_hook_timings,
    capture_checkpoint_line_mode_timing,
    _normalize_rgba_to_dmg_shades,
    capture_checkpoint_frame_dmg_shades,
    capture_rendered_frame_dmg_shades,
)
from roms.build_micro_rom import build_alu_loop
from spec.profiles import BehaviorConfig, BehaviorFeature, ModelProfile, ResetProfile, SocRevision
from test.harness.rom_runner import _decode_png_grayscale


HOOK_ADDRS = (0x0150, 0x0152, 0x0154, 0x0155, 0x0156)
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

from resolve_checkpoint_pc import resolve_checkpoint_pc
from test.harness.obj_penalty_reference import (
    PYBOY_OBJ_PENALTY_ALIGNMENT_CASES,
    PYBOY_OBJ_PENALTY_REFERENCE_CASES,
)

DMG_ACID2_ROM = ROOT / "bench" / "external" / "dmg-acid2" / "dmg-acid2.gb"
DMG_ACID2_EXPECTED = ROOT / "bench" / "expected" / "suite_owned" / "dmg-acid2" / "reference-dmg.png"
OBJ_BASIC_ROM = ROOT / "bench" / "roms" / "out" / "OBJ_BASIC.gb"
OBJ_X_HIDDEN_STILL_COUNTS_ROM = ROOT / "bench" / "roms" / "out" / "OBJ_X_HIDDEN_STILL_COUNTS.gb"
OAM_DMA_ISOLATION_ROM = ROOT / "bench" / "roms" / "out" / "OAM_DMA_ISOLATION.gb"
DMA_MODE2_HIDE_ROM = ROOT / "bench" / "roms" / "out" / "DMA_MODE2_HIDE.gb"
OBJ_DMA_METADATA_CORRUPT_ROM = ROOT / "bench" / "roms" / "out" / "OBJ_DMA_METADATA_CORRUPT.gb"
CHECKER_BALL_ROM = ROOT / "bench" / "roms" / "out" / "CHECKER_BALL.gb"
CHECKER_BALL_CANCEL_ROM = ROOT / "bench" / "roms" / "out" / "CHECKER_BALL_CANCEL.gb"
CHECKER_BALL_CANCEL_OVERLAP_ROM = ROOT / "bench" / "roms" / "out" / "CHECKER_BALL_CANCEL_OVERLAP.gb"
OBJ_FETCH_CANCEL_LCDC1_ROM = ROOT / "bench" / "roms" / "out" / "OBJ_FETCH_CANCEL_LCDC1.gb"
MEALYBUG_PPU_ROOT = ROOT / "bench" / "external" / "mealybug-tearoom-tests" / "ppu"
MEALYBUG_EXPECTED_ROOT = ROOT / "bench" / "expected" / "suite_owned" / "mealybug-tearoom-tests" / "DMG-blob"


class PyBoyOracleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        warnings.filterwarnings("ignore", message="Using SDL2 binaries from pysdl2-dll.*")
        cls._tmpdir = tempfile.TemporaryDirectory()
        cls.rom_path = Path(cls._tmpdir.name) / "alu_loop.gb"
        cls.rom_path.write_bytes(build_alu_loop())
        cls.commit_points = tuple(
            CommitPoint(bank=0, addr=addr, label=f"hook_{addr:04X}") for addr in HOOK_ADDRS
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmpdir.cleanup()

    def make_oracle(self) -> PyBoyOracle:
        return PyBoyOracle(self.rom_path, commit_points=self.commit_points)

    def test_step_commit_replays_deterministically_after_restore(self) -> None:
        with self.make_oracle() as oracle:
            oracle.reset(ModelProfile.DMG, ResetProfile.SkipBoot)

            first = oracle.step_commit()
            self.assertEqual(first.label, "hook_0150")
            self.assertEqual(first.pc_before, 0x0150)
            self.assertEqual(first.opcode, 0x3E)
            self.assertEqual(first.bus_request.kind, "read")
            self.assertEqual(first.bus_request.addr, 0x0150)
            self.assertEqual(first.bus_response.kind, "data")
            self.assertEqual(first.bus_response.data, 0x3E)

            snapshot = oracle.snapshot()
            expected = [oracle.step_commit() for _ in range(3)]

            oracle.restore(snapshot)
            replayed = [oracle.step_commit() for _ in range(3)]

            self.assertEqual(expected, replayed)

    def test_memory_write_events_round_trip_through_snapshot(self) -> None:
        with self.make_oracle() as oracle:
            oracle.reset(ModelProfile.DMG, ResetProfile.SkipBoot)

            oracle.write_event(MemoryWriteEvent(addr=0xC100, value=0x34))
            self.assertEqual(oracle.read_mem(0xC100), 0x34)

            snapshot = oracle.snapshot()
            oracle.write_event(MemoryWriteEvent(addr=0xC100, value=0x99))
            self.assertEqual(oracle.read_mem(0xC100), 0x99)

            oracle.restore(snapshot)
            self.assertEqual(oracle.read_mem(0xC100), 0x34)

    def test_interrupt_sideband_events_update_if_and_ie(self) -> None:
        with self.make_oracle() as oracle:
            oracle.reset(ModelProfile.DMG, ResetProfile.SkipBoot)

            oracle.write_event(IeOverrideEvent(value=0x1B))
            self.assertEqual(oracle.read_mem(0xFFFF) & 0x1F, 0x1B)

            oracle.write_event(IfSetBitsEvent(bits=0x05))
            self.assertEqual(oracle.read_mem(0xFF0F) & 0x1F, 0x05)

            oracle.write_event(IfSetBitsEvent(bits=0x08))
            self.assertEqual(oracle.read_mem(0xFF0F) & 0x1F, 0x0D)

            oracle.write_event(IfClearBitsEvent(bits=0x09))
            self.assertEqual(oracle.read_mem(0xFF0F) & 0x1F, 0x04)

    def test_skipboot_reset_applies_dmg_post_boot_register_state(self) -> None:
        with self.make_oracle() as oracle:
            oracle.reset(ModelProfile.DMG, ResetProfile.SkipBoot)
            rf = oracle._require_pyboy().register_file
            self.assertEqual(int(rf.A), 0x01)
            self.assertEqual(int(rf.F), 0xB0)
            self.assertEqual(int(rf.B), 0x00)
            self.assertEqual(int(rf.C), 0x13)
            self.assertEqual(int(rf.D), 0x00)
            self.assertEqual(int(rf.E), 0xD8)
            self.assertEqual(int(rf.HL), 0x014D)
            self.assertEqual(int(rf.SP), 0xFFFE)
            self.assertEqual(int(rf.PC), 0x0100)
            self.assertEqual(oracle.read_mem(0xFF40), 0x91)
            self.assertEqual(oracle.read_mem(0xFF47), 0xFC)

    def test_reset_accepts_behavior_config_and_rejects_model_mismatches(self) -> None:
        with self.make_oracle() as oracle:
            oracle.reset(
                ModelProfile.DMG,
                ResetProfile.SkipBoot,
                BehaviorConfig(
                    model=ModelProfile.DMG,
                    soc_revision=SocRevision.DMGB,
                    features=(BehaviorFeature.DmgStatWriteQuirk,),
                ),
            )
            self.assertEqual(oracle.read_mem(0xFF40), 0x91)

            with self.assertRaisesRegex(ValueError, "BehaviorConfig.model"):
                oracle.reset(
                    ModelProfile.DMG,
                    ResetProfile.SkipBoot,
                    {"model": "CGB", "soc_revision": None, "features": []},
                )

    def test_frame_semantics_capture_surfaces_tilemaps_sprites_and_scroll_state(self) -> None:
        with self.make_oracle() as oracle:
            oracle.reset(ModelProfile.DMG, ResetProfile.SkipBoot)

            rgba = oracle.frame_buffer_rgba()
            self.assertEqual(tuple(rgba.shape), (144, 160, 4))

            shades = oracle.shade_buffer()
            self.assertEqual(len(shades), 144 * 160)
            self.assertTrue(set(shades))
            self.assertTrue(set(shades).issubset({0x00, 0x55, 0xAA, 0xFF}))

            semantics = oracle.frame_semantics()
            self.assertEqual((semantics.bg_tilemap.width, semantics.bg_tilemap.height), (32, 32))
            self.assertEqual((semantics.window_tilemap.width, semantics.window_tilemap.height), (32, 32))
            self.assertEqual(len(semantics.sprites), 40)
            self.assertEqual(len(semantics.line_scroll), 144)
            self.assertEqual(semantics.line_scroll[0].scx, 0)
            self.assertEqual(semantics.line_scroll[0].scy, 0)
            self.assertEqual(semantics.line_scroll[0].wx, 0)
            self.assertEqual(semantics.line_scroll[0].wy, 0)
            self.assertEqual(semantics.sprites[0].sprite_index, 0)

    def test_rgba_normalization_maps_luminance_order_to_canonical_dmg_shades(self) -> None:
        import numpy

        rgba = numpy.zeros((144, 160, 4), dtype=numpy.uint8)
        rgba[:, :, 3] = 0xFF
        rgba[:, 0:40, :3] = (0, 0, 0)
        rgba[:, 40:80, :3] = (85, 85, 85)
        rgba[:, 80:120, :3] = (170, 170, 170)
        rgba[:, 120:160, :3] = (255, 255, 255)

        normalized = _normalize_rgba_to_dmg_shades(rgba)

        self.assertEqual(set(normalized), {0x00, 0x55, 0xAA, 0xFF})
        self.assertEqual(normalized[0], 0x00)
        self.assertEqual(normalized[40], 0x55)
        self.assertEqual(normalized[80], 0xAA)
        self.assertEqual(normalized[120], 0xFF)

    def test_upstream_style_dmg_acid2_timing_matches_pinned_reference(self) -> None:
        actual = capture_rendered_frame_dmg_shades(DMG_ACID2_ROM, frame_batches=(59, 25))
        expected = bytes(value for row in _decode_png_grayscale(DMG_ACID2_EXPECTED) for value in row)
        self.assertEqual(actual, expected)

    def test_mealybug_scx_low_3_rendered_frame_characterization_differs_from_pinned_png(self) -> None:
        actual = capture_rendered_frame_dmg_shades(MEALYBUG_PPU_ROOT / "m3_scx_low_3_bits.gb")
        expected = bytes(
            value
            for row in _decode_png_grayscale(MEALYBUG_EXPECTED_ROOT / "m3_scx_low_3_bits.png")
            for value in row
        )

        mismatches = sum(1 for actual_px, expected_px in zip(actual, expected) if actual_px != expected_px)
        first = next(
            (
                (index % 160, index // 160, actual_px, expected_px)
                for index, (actual_px, expected_px) in enumerate(zip(actual, expected))
                if actual_px != expected_px
            ),
            None,
        )

        self.assertEqual(mismatches, 540)
        self.assertEqual(first, (154, 0, 0xFF, 0x00))

    def test_checkpoint_frame_capture_returns_canonical_dmg_shades(self) -> None:
        actual = capture_checkpoint_frame_dmg_shades(
            OBJ_BASIC_ROM,
            sym_path=OBJ_BASIC_ROM.with_suffix(".sym"),
        )
        self.assertEqual(len(actual), 144 * 160)
        self.assertTrue(set(actual))
        self.assertTrue(set(actual).issubset({0x00, 0x55, 0xAA, 0xFF}))

    def test_checkpoint_frame_capture_matches_obj_fetch_cancel_lcdc1_scene(self) -> None:
        actual = capture_checkpoint_frame_dmg_shades(
            OBJ_FETCH_CANCEL_LCDC1_ROM,
            sym_path=OBJ_FETCH_CANCEL_LCDC1_ROM.with_suffix(".sym"),
        )
        self.assertEqual(len(actual), 144 * 160)
        self.assertEqual(actual[(40 * 160) + 120], 0xFF)
        self.assertEqual(actual[(41 * 160) + 120], 0x00)
        self.assertEqual(actual[(41 * 160) + 128], 0xFF)
        self.assertEqual(actual[(41 * 160) + 136], 0x00)
        self.assertEqual(actual[(41 * 160) + 144], 0xFF)
        self.assertEqual(actual[(41 * 160) + 152], 0x00)

    def test_checkpoint_frame_capture_shows_hidden_x_entries_consuming_oam_slots(self) -> None:
        actual = capture_checkpoint_frame_dmg_shades(
            OBJ_X_HIDDEN_STILL_COUNTS_ROM,
            sym_path=OBJ_X_HIDDEN_STILL_COUNTS_ROM.with_suffix(".sym"),
        )
        line = 40
        for x in (8, 16, 24, 32, 40, 48, 56, 64):
            self.assertEqual(actual[(line * 160) + x], 0x00, x)
        for x in (72, 80):
            self.assertEqual(actual[(line * 160) + x], 0xFF, x)

    def test_oam_dma_isolation_rom_characterizes_pyboy_io_write_behavior(self) -> None:
        from test.harness.rom_runner import build_manifest, load_manifest_entry, run_oracle_to_terminal

        entry = load_manifest_entry("OAM_DMA_ISOLATION")
        manifest = build_manifest(entry)
        labels, abi = run_oracle_to_terminal(entry, manifest)

        self.assertEqual(labels, ("__fail",))
        self.assertEqual(abi.log, bytes.fromhex("0200ffe41b02"))

    def test_dma_mode2_hide_frame_shows_missing_top_sprite_rows(self) -> None:
        actual = capture_checkpoint_frame_dmg_shades(
            DMA_MODE2_HIDE_ROM,
            sym_path=DMA_MODE2_HIDE_ROM.with_suffix(".sym"),
            settle_rendered_frames=1,
        )
        self.assertEqual(actual[(0 * 160) + 40], 0xFF)
        self.assertEqual(actual[(1 * 160) + 40], 0xFF)
        self.assertEqual(actual[(2 * 160) + 40], 0xFF)
        self.assertEqual(actual[(7 * 160) + 40], 0xFF)

    def test_obj_dma_metadata_corrupt_frame_shows_gray_sprite_after_mode3_dma(self) -> None:
        actual = capture_checkpoint_frame_dmg_shades(
            OBJ_DMA_METADATA_CORRUPT_ROM,
            sym_path=OBJ_DMA_METADATA_CORRUPT_ROM.with_suffix(".sym"),
            settle_rendered_frames=2,
        )
        self.assertEqual(actual[(143 * 160) + 120], 0xAA)
        self.assertEqual(actual[(143 * 160) + 127], 0xAA)

    def test_checkpoint_frame_capture_tracks_checker_ball_motion(self) -> None:
        frame1 = capture_checkpoint_frame_dmg_shades(
            CHECKER_BALL_ROM,
            sym_path=CHECKER_BALL_ROM.with_suffix(".sym"),
            settle_rendered_frames=1,
        )
        frame2 = capture_checkpoint_frame_dmg_shades(
            CHECKER_BALL_ROM,
            sym_path=CHECKER_BALL_ROM.with_suffix(".sym"),
            settle_rendered_frames=2,
        )
        frame3 = capture_checkpoint_frame_dmg_shades(
            CHECKER_BALL_ROM,
            sym_path=CHECKER_BALL_ROM.with_suffix(".sym"),
            settle_rendered_frames=3,
        )
        self.assertNotEqual(frame1, frame2)
        self.assertNotEqual(frame2, frame3)
        self.assertEqual(frame1[(34 * 160) + 44], 0x00)
        self.assertEqual(frame2[(42 * 160) + 60], 0x00)
        self.assertEqual(frame3[(50 * 160) + 76], 0x00)

    def test_checkpoint_frame_capture_matches_checker_ball_cancel_scene(self) -> None:
        actual = capture_checkpoint_frame_dmg_shades(
            CHECKER_BALL_CANCEL_ROM,
            sym_path=CHECKER_BALL_CANCEL_ROM.with_suffix(".sym"),
        )
        self.assertEqual(actual[(27 * 160) + 27], 0x00)
        self.assertEqual(actual[(43 * 160) + 99], 0x00)

    def test_checkpoint_frame_capture_matches_checker_ball_cancel_overlap_scene(self) -> None:
        actual = capture_checkpoint_frame_dmg_shades(
            CHECKER_BALL_CANCEL_OVERLAP_ROM,
            sym_path=CHECKER_BALL_CANCEL_OVERLAP_ROM.with_suffix(".sym"),
        )
        self.assertEqual(actual[(27 * 160) + 27], 0x00)
        self.assertEqual(actual[(80 * 160) + 97], 0xFF)
        self.assertEqual(actual[(80 * 160) + 104], 0xFF)

    def test_capture_checkpoint_hook_timings_tracks_overlap_row_loop_order(self) -> None:
        captures = capture_checkpoint_hook_timings(
            CHECKER_BALL_CANCEL_OVERLAP_ROM,
            sym_path=CHECKER_BALL_CANCEL_OVERLAP_ROM.with_suffix(".sym"),
            hook_points=(
                CommitPoint(bank=None, addr="WaitForMode3"),
                CommitPoint(bank=None, addr="DelayCancel"),
                CommitPoint(bank=0, addr=0x01D5, label="WriteObjOff"),
            ),
            settle_rendered_frames=2,
            target_line=80,
        )
        labels = [capture.label for capture in captures]
        self.assertIn("WaitForMode3", labels)
        self.assertIn("DelayCancel", labels)
        self.assertIn("WriteObjOff", labels)

        wait = next(capture for capture in captures if capture.label == "WaitForMode3")
        delay = next(capture for capture in captures if capture.label == "DelayCancel")
        write = next(capture for capture in captures if capture.label == "WriteObjOff")
        self.assertEqual(wait.frame, 1)
        self.assertEqual(delay.frame, 1)
        self.assertEqual(write.frame, 1)
        self.assertEqual(wait.ly, 80)
        self.assertEqual(delay.ly, 80)
        self.assertEqual(write.ly, 80)
        self.assertLess(wait.seq, delay.seq)
        self.assertLess(delay.seq, write.seq)
        self.assertEqual(write.pc, 0x01D5)

    def test_capture_checkpoint_line_mode_timing_reports_dmg_lengths(self) -> None:
        timing = capture_checkpoint_line_mode_timing(
            CHECKER_BALL_CANCEL_OVERLAP_ROM,
            sym_path=CHECKER_BALL_CANCEL_OVERLAP_ROM.with_suffix(".sym"),
            settle_rendered_frames=2,
            target_line=80,
        )
        self.assertEqual(timing.line, 80)
        self.assertEqual(timing.mode2_len_dots, 80)
        self.assertEqual(timing.mode3_len_dots, 172)
        self.assertEqual(timing.hblank_len_dots, 204)

    def test_obj_penalty_reference_cases_match_pyboy_frame_semantics(self) -> None:
        for case in PYBOY_OBJ_PENALTY_REFERENCE_CASES:
            with self.subTest(case=case.name):
                with PyBoyOracle(
                    case.rom_path,
                    sym_path=case.sym_path,
                    commit_points=(CommitPoint(bank=None, addr="__checkpoint_scene_ready"),),
                ) as oracle:
                    oracle.reset(ModelProfile.DMG, ResetProfile.SkipBoot)
                    oracle.step_commit()
                    oracle._require_pyboy().tick(2, True, False)
                    semantics = oracle.frame_semantics()
                    line_scroll = semantics.line_scroll[case.target_line]

                self.assertEqual(line_scroll.scx, case.scx)
                self.assertEqual(line_scroll.scy, case.scy)
                self.assertEqual(line_scroll.wx, case.wx)
                self.assertEqual(line_scroll.wy, case.wy)

                if case.expected_source_window:
                    tile_id = semantics.window_tilemap.tile_id(case.expected_tile_x, case.expected_tile_y)
                else:
                    tile_id = semantics.bg_tilemap.tile_id(case.expected_tile_x, case.expected_tile_y)

                self.assertEqual(tile_id, case.expected_tile_id)

    def test_obj_penalty_alignment_fixture_covers_scx_zero_offsets(self) -> None:
        cases_by_x = {case.obj_x: case for case in PYBOY_OBJ_PENALTY_ALIGNMENT_CASES if case.scx == 0}
        self.assertEqual(set(cases_by_x), {0, 8, 9, 10, 11, 12, 13, 14, 15})
        self.assertEqual(cases_by_x[0].expected_total_penalty, 11)
        self.assertEqual(cases_by_x[8].expected_align_penalty, 6)
        self.assertEqual(cases_by_x[8].expected_total_penalty, 12)
        self.assertEqual(cases_by_x[9].expected_total_penalty, 11)
        self.assertEqual(cases_by_x[10].expected_total_penalty, 10)
        self.assertEqual(cases_by_x[11].expected_total_penalty, 9)
        self.assertEqual(cases_by_x[14].expected_total_penalty, 6)
        self.assertEqual(cases_by_x[15].expected_total_penalty, 6)

    def test_resolve_checkpoint_pc_finds_wave_c_scene_ready_label(self) -> None:
        self.assertEqual(
            resolve_checkpoint_pc(OBJ_FETCH_CANCEL_LCDC1_ROM.with_suffix(".sym")),
            0x01B9,
        )


if __name__ == "__main__":
    unittest.main()
