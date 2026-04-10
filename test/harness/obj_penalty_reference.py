from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class ObjPenaltyReferenceCase:
    name: str
    rom_path: Path
    sym_path: Path
    target_line: int
    leftmost_pixel_x: int
    visible_ly: int
    scx: int
    scy: int
    wx: int
    wy: int
    window_enabled_line: bool
    window_line: int
    expected_source_window: bool
    expected_tile_x: int
    expected_tile_y: int
    expected_tile_id: int


@dataclass(frozen=True)
class ObjPenaltyAlignmentReferenceCase:
    name: str
    scx: int
    obj_x: int
    expected_align_penalty: int
    expected_total_penalty: int


CHECKER_BALL_CANCEL_OVERLAP_BG_CASE = ObjPenaltyReferenceCase(
    name="checker_ball_cancel_overlap_bg_tile",
    rom_path=ROOT / "bench" / "roms" / "out" / "CHECKER_BALL_CANCEL_OVERLAP.gb",
    sym_path=ROOT / "bench" / "roms" / "out" / "CHECKER_BALL_CANCEL_OVERLAP.sym",
    target_line=80,
    leftmost_pixel_x=112,
    visible_ly=80,
    scx=0,
    scy=0,
    wx=0,
    wy=0,
    window_enabled_line=False,
    window_line=0,
    expected_source_window=False,
    expected_tile_x=14,
    expected_tile_y=10,
    expected_tile_id=0,
)

WINDOW_BASIC_BG_CASE = ObjPenaltyReferenceCase(
    name="window_basic_bg_before_threshold",
    rom_path=ROOT / "bench" / "roms" / "out" / "WINDOW_BASIC.gb",
    sym_path=ROOT / "bench" / "roms" / "out" / "WINDOW_BASIC.sym",
    target_line=16,
    leftmost_pixel_x=7,
    visible_ly=16,
    scx=0,
    scy=0,
    wx=15,
    wy=0,
    window_enabled_line=True,
    window_line=16,
    expected_source_window=False,
    expected_tile_x=0,
    expected_tile_y=2,
    expected_tile_id=0,
)

WINDOW_BASIC_WINDOW_THRESHOLD_CASE = ObjPenaltyReferenceCase(
    name="window_basic_window_at_threshold",
    rom_path=ROOT / "bench" / "roms" / "out" / "WINDOW_BASIC.gb",
    sym_path=ROOT / "bench" / "roms" / "out" / "WINDOW_BASIC.sym",
    target_line=16,
    leftmost_pixel_x=8,
    visible_ly=16,
    scx=0,
    scy=0,
    wx=15,
    wy=0,
    window_enabled_line=True,
    window_line=16,
    expected_source_window=True,
    expected_tile_x=0,
    expected_tile_y=2,
    expected_tile_id=0,
)

WINDOW_BASIC_WINDOW_NEXT_TILE_CASE = ObjPenaltyReferenceCase(
    name="window_basic_window_second_tile",
    rom_path=ROOT / "bench" / "roms" / "out" / "WINDOW_BASIC.gb",
    sym_path=ROOT / "bench" / "roms" / "out" / "WINDOW_BASIC.sym",
    target_line=16,
    leftmost_pixel_x=20,
    visible_ly=16,
    scx=0,
    scy=0,
    wx=15,
    wy=0,
    window_enabled_line=True,
    window_line=16,
    expected_source_window=True,
    expected_tile_x=1,
    expected_tile_y=2,
    expected_tile_id=0,
)

PYBOY_OBJ_PENALTY_REFERENCE_CASES = (
    CHECKER_BALL_CANCEL_OVERLAP_BG_CASE,
    WINDOW_BASIC_BG_CASE,
    WINDOW_BASIC_WINDOW_THRESHOLD_CASE,
    WINDOW_BASIC_WINDOW_NEXT_TILE_CASE,
)

PYBOY_OBJ_PENALTY_ALIGNMENT_CASES = (
    ObjPenaltyAlignmentReferenceCase(
        name="scx0_x0_special_case",
        scx=0,
        obj_x=0,
        expected_align_penalty=5,
        expected_total_penalty=11,
    ),
    ObjPenaltyAlignmentReferenceCase(
        name="scx0_x8_offset0",
        scx=0,
        obj_x=8,
        expected_align_penalty=6,
        expected_total_penalty=12,
    ),
    ObjPenaltyAlignmentReferenceCase(
        name="scx0_x9_offset1",
        scx=0,
        obj_x=9,
        expected_align_penalty=5,
        expected_total_penalty=11,
    ),
    ObjPenaltyAlignmentReferenceCase(
        name="scx0_x10_offset2",
        scx=0,
        obj_x=10,
        expected_align_penalty=4,
        expected_total_penalty=10,
    ),
    ObjPenaltyAlignmentReferenceCase(
        name="scx0_x11_offset3",
        scx=0,
        obj_x=11,
        expected_align_penalty=3,
        expected_total_penalty=9,
    ),
    ObjPenaltyAlignmentReferenceCase(
        name="scx0_x12_offset4",
        scx=0,
        obj_x=12,
        expected_align_penalty=2,
        expected_total_penalty=8,
    ),
    ObjPenaltyAlignmentReferenceCase(
        name="scx0_x13_offset5",
        scx=0,
        obj_x=13,
        expected_align_penalty=1,
        expected_total_penalty=7,
    ),
    ObjPenaltyAlignmentReferenceCase(
        name="scx0_x14_offset6",
        scx=0,
        obj_x=14,
        expected_align_penalty=0,
        expected_total_penalty=6,
    ),
    ObjPenaltyAlignmentReferenceCase(
        name="scx0_x15_offset7",
        scx=0,
        obj_x=15,
        expected_align_penalty=0,
        expected_total_penalty=6,
    ),
)
