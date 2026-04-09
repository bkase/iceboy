from __future__ import annotations

import unittest
import warnings
from pathlib import Path

from bench.pyboy.oracle import CommitPoint, PyBoyOracle
from bench.ref.ppu_ref import Lcdc, PpuRegs, StatSelect
from bench.ref.ppu_spatial_oracle import build_scanlines, render_frame, rows_from_flat_shades
from spec.profiles import ModelProfile, ResetProfile


ROOT = Path(__file__).resolve().parents[2]
VRAM_BASE = 0x8000
VRAM_SIZE = 0x2000
OAM_BASE = 0xFE00
OAM_SIZE = 0xA0


def _lcdc_from_byte(value: int) -> Lcdc:
    return Lcdc(
        lcd_enable=bool((value >> 7) & 1),
        win_map_hi=bool((value >> 6) & 1),
        win_enable=bool((value >> 5) & 1),
        bgwin_data_hi=bool((value >> 4) & 1),
        bg_map_hi=bool((value >> 3) & 1),
        obj_size_8x16=bool((value >> 2) & 1),
        obj_enable=bool((value >> 1) & 1),
        bg_enable=bool(value & 1),
    )


def _ppu_regs_from_line(oracle: PyBoyOracle, *, scx: int, scy: int, wx: int, wy: int) -> PpuRegs:
    stat = oracle.read_mem(0xFF41)
    return PpuRegs(
        lcdc=_lcdc_from_byte(oracle.read_mem(0xFF40)),
        stat_sel=StatSelect(
            lyc_sel=bool((stat >> 6) & 1),
            mode2_sel=bool((stat >> 5) & 1),
            mode1_sel=bool((stat >> 4) & 1),
            mode0_sel=bool((stat >> 3) & 1),
        ),
        scy=scy,
        scx=scx,
        lyc=oracle.read_mem(0xFF45),
        wy=wy,
        wx=wx,
        bgp=oracle.read_mem(0xFF47),
        obp0=oracle.read_mem(0xFF48),
        obp1=oracle.read_mem(0xFF49),
    )


def _capture_scene_frame(rom_id: str) -> tuple[tuple[tuple[int, ...], ...], tuple[PpuRegs, ...], bytes, bytes, tuple[bool, ...], tuple[int, ...]]:
    rom_path = ROOT / "bench" / "roms" / "out" / f"{rom_id}.gb"
    with PyBoyOracle(
        rom_path,
        sym_path=rom_path.with_suffix(".sym"),
        commit_points=(CommitPoint(bank=None, addr="__checkpoint_scene_ready"),),
    ) as oracle:
        oracle.reset(ModelProfile.DMG, ResetProfile.SkipBoot)
        oracle.step_commit()
        oracle._require_pyboy().tick(2, True, False)
        actual_rows = rows_from_flat_shades(oracle.shade_buffer())
        semantics = oracle.frame_semantics()
        vram = bytes(oracle.read_mem(VRAM_BASE + offset) for offset in range(VRAM_SIZE))
        oam = bytes(oracle.read_mem(OAM_BASE + offset) for offset in range(OAM_SIZE))
        regs_by_line = []
        wy_triggered = []
        window_line_counters = []
        lcdc = _lcdc_from_byte(oracle.read_mem(0xFF40))
        current_window_line = 0
        for line in semantics.line_scroll:
            regs = _ppu_regs_from_line(oracle, scx=line.scx, scy=line.scy, wx=line.wx, wy=line.wy)
            regs_by_line.append(regs)
            line_triggered = lcdc.win_enable and line.line >= line.wy
            wy_triggered.append(line_triggered)
            window_line_counters.append(current_window_line if line_triggered else 0)
            if line_triggered:
                current_window_line += 1
        return actual_rows, tuple(regs_by_line), vram, oam, tuple(wy_triggered), tuple(window_line_counters)


class PpuSpatialOracleWaveCTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        warnings.filterwarnings("ignore", message="Using SDL2 binaries from pysdl2-dll.*")

    def assert_scene_matches_pyboy(self, rom_id: str) -> None:
        actual_rows, regs_by_line, vram, oam, wy_triggered, window_line_counters = _capture_scene_frame(rom_id)
        scanlines = build_scanlines(
            regs_by_line=regs_by_line,
            vram=vram,
            oam=oam,
            wy_triggered_by_line=wy_triggered,
            window_line_counters=window_line_counters,
        )
        expected_rows = render_frame(scanlines)
        self.assertEqual(actual_rows, expected_rows)

    def test_obj_basic_scene_matches_pyboy(self) -> None:
        self.assert_scene_matches_pyboy("OBJ_BASIC")

    def test_obj_priority_scene_matches_pyboy(self) -> None:
        self.assert_scene_matches_pyboy("OBJ_PRIORITY")

    def test_obj_8x16_scene_matches_pyboy(self) -> None:
        self.assert_scene_matches_pyboy("OBJ_8X16")

    def test_obj_flip_scene_matches_pyboy(self) -> None:
        self.assert_scene_matches_pyboy("OBJ_FLIP")

    def test_obj_bg_mask_scene_matches_pyboy(self) -> None:
        self.assert_scene_matches_pyboy("OBJ_BG_MASK")


if __name__ == "__main__":
    unittest.main()
