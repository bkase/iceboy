from __future__ import annotations

import unittest

from bench.ref.ppu_ref import Lcdc, PpuRegs, StatSelect
from bench.ref.ppu_spatial_oracle import (
    PixelSource,
    ScanlineSnapshot,
    bgwin_tile_addr,
    decode_tile_row,
    diff_frame,
    dmg_gray,
    obj_tile_addr,
    palette_lookup,
    pixel_shade,
    render_scanline,
)


VRAM_SIZE = 0x2000
OAM_SIZE = 0xA0


def encode_row(colors: list[int]) -> tuple[int, int]:
    lo = 0
    hi = 0
    for index, color in enumerate(colors):
        bit = 7 - index
        lo |= (color & 0x1) << bit
        hi |= ((color >> 1) & 0x1) << bit
    return lo, hi


def write_tile(vram: bytearray, *, addr: int | None = None, tile_id: int | None = None, rows: list[list[int]]) -> None:
    if addr is None:
        if tile_id is None:
            raise ValueError("tile_id or addr is required")
        addr = 0x8000 + ((tile_id & 0xFF) * 16)
    offset = addr - 0x8000
    for row_index, colors in enumerate(rows):
        lo, hi = encode_row(colors)
        vram[offset + row_index * 2] = lo
        vram[offset + row_index * 2 + 1] = hi


def write_tilemap(vram: bytearray, *, base: int, x: int, y: int, tile_id: int) -> None:
    vram[(base - 0x8000) + y * 32 + x] = tile_id & 0xFF


def build_regs(
    *,
    bg_enable: bool = True,
    obj_enable: bool = False,
    obj_size_8x16: bool = False,
    win_enable: bool = False,
    bg_map_hi: bool = False,
    win_map_hi: bool = False,
    bgwin_data_hi: bool = True,
    scx: int = 0,
    scy: int = 0,
    wx: int = 7,
    wy: int = 0,
    bgp: int = 0xE4,
    obp0: int = 0xE4,
    obp1: int = 0x1B,
) -> PpuRegs:
    return PpuRegs(
        lcdc=Lcdc(
            lcd_enable=True,
            win_map_hi=win_map_hi,
            win_enable=win_enable,
            bgwin_data_hi=bgwin_data_hi,
            bg_map_hi=bg_map_hi,
            obj_size_8x16=obj_size_8x16,
            obj_enable=obj_enable,
            bg_enable=bg_enable,
        ),
        stat_sel=StatSelect(),
        scy=scy,
        scx=scx,
        lyc=0,
        wy=wy,
        wx=wx,
        bgp=bgp,
        obp0=obp0,
        obp1=obp1,
    )


def build_snapshot(
    *,
    ly: int = 0,
    regs: PpuRegs | None = None,
    vram: bytes | bytearray | None = None,
    oam: bytes | bytearray | None = None,
    wy_triggered: bool = False,
    window_line_counter: int = 0,
) -> ScanlineSnapshot:
    return ScanlineSnapshot(
        ly=ly,
        regs=build_regs() if regs is None else regs,
        vram=bytes(bytearray(VRAM_SIZE) if vram is None else vram),
        oam=bytes(bytearray(OAM_SIZE) if oam is None else oam),
        wy_triggered=wy_triggered,
        window_line_counter=window_line_counter,
    )


class PpuSpatialOracleTest(unittest.TestCase):
    def test_palette_lookup_and_dmg_gray_follow_dmg_encoding(self) -> None:
        self.assertEqual([palette_lookup(color, 0xE4) for color in range(4)], [0, 1, 2, 3])
        self.assertEqual([palette_lookup(color, 0x1B) for color in range(4)], [3, 2, 1, 0])
        self.assertEqual([dmg_gray(shade) for shade in range(4)], [0xFF, 0xAA, 0x55, 0x00])

    def test_decode_tile_row_matches_bitplane_order(self) -> None:
        lo, hi = encode_row([0, 1, 2, 3, 0, 0, 0, 0])
        self.assertEqual(decode_tile_row(lo, hi), (0, 1, 2, 3, 0, 0, 0, 0))

    def test_bgwin_tile_addr_matches_unsigned_and_signed_modes(self) -> None:
        unsigned = build_regs(bgwin_data_hi=True)
        signed = build_regs(bgwin_data_hi=False)
        self.assertEqual(bgwin_tile_addr(unsigned.lcdc, 0x00, 0), 0x8000)
        self.assertEqual(bgwin_tile_addr(unsigned.lcdc, 0xFF, 7), 0x8FFE)
        self.assertEqual(bgwin_tile_addr(signed.lcdc, 0x00, 0), 0x9000)
        self.assertEqual(bgwin_tile_addr(signed.lcdc, 0x80, 0), 0x8800)
        self.assertEqual(bgwin_tile_addr(signed.lcdc, 0x7F, 7), 0x97FE)

    def test_obj_tile_addr_matches_8x8_8x16_and_y_flip_rules(self) -> None:
        self.assertEqual(obj_tile_addr(obj_size_8x16=False, tile_id=0x24, row=3, y_flip=False), 0x8246)
        self.assertEqual(obj_tile_addr(obj_size_8x16=True, tile_id=0x01, row=0, y_flip=False), 0x8000)
        self.assertEqual(obj_tile_addr(obj_size_8x16=True, tile_id=0x01, row=8, y_flip=False), 0x8010)
        self.assertEqual(obj_tile_addr(obj_size_8x16=False, tile_id=0x24, row=0, y_flip=True), 0x824E)

    def test_bg_scroll_and_signed_addressing_render_expected_pixels(self) -> None:
        vram = bytearray(VRAM_SIZE)
        write_tile(vram, tile_id=1, rows=[[0, 1, 2, 3, 0, 1, 2, 3]] * 8)
        write_tile(vram, tile_id=2, rows=[[3, 2, 1, 0, 3, 2, 1, 0]] * 8)
        write_tilemap(vram, base=0x9800, x=0, y=0, tile_id=1)
        write_tilemap(vram, base=0x9800, x=1, y=0, tile_id=2)
        regs = build_regs(scx=3, scy=0, bgp=0xE4)
        row = render_scanline(build_snapshot(regs=regs, vram=vram))
        self.assertEqual(row[:8], (0x00, 0xFF, 0xAA, 0x55, 0x00, 0x00, 0x55, 0xAA))

        signed_vram = bytearray(VRAM_SIZE)
        write_tile(signed_vram, addr=0x9000, rows=[[1, 1, 1, 1, 2, 2, 2, 2]] * 8)
        write_tilemap(signed_vram, base=0x9800, x=0, y=0, tile_id=0x00)
        signed_regs = build_regs(bgwin_data_hi=False, bgp=0xE4)
        signed_row = render_scanline(build_snapshot(regs=signed_regs, vram=signed_vram))
        self.assertEqual(signed_row[:8], (0xAA, 0xAA, 0xAA, 0xAA, 0x55, 0x55, 0x55, 0x55))

    def test_window_overrides_background_and_uses_window_counter(self) -> None:
        vram = bytearray(VRAM_SIZE)
        write_tile(vram, tile_id=1, rows=[[1] * 8] * 8)
        write_tile(vram, tile_id=2, rows=[[2] * 8] * 8)
        write_tile(vram, tile_id=3, rows=[[3] * 8] * 8)
        write_tilemap(vram, base=0x9800, x=0, y=0, tile_id=1)
        write_tilemap(vram, base=0x9800, x=10, y=4, tile_id=2)
        write_tilemap(vram, base=0x9C00, x=0, y=0, tile_id=3)
        regs = build_regs(win_enable=True, win_map_hi=True, wx=15, wy=5, bgp=0xE4)
        snapshot = build_snapshot(ly=5, regs=regs, vram=vram, wy_triggered=True, window_line_counter=0)
        left = pixel_shade(7, 5, snapshot)
        right = pixel_shade(8, 5, snapshot)
        self.assertEqual(left.source, PixelSource.Background)
        self.assertEqual(right.source, PixelSource.Window)
        self.assertEqual(right.shade, 3)

    def test_object_palette_transparency_and_bg_priority_rules(self) -> None:
        vram = bytearray(VRAM_SIZE)
        write_tile(vram, tile_id=1, rows=[[1] * 8] * 8)
        write_tile(vram, tile_id=2, rows=[[0, 0, 0, 0, 3, 3, 3, 3]] * 8)
        write_tilemap(vram, base=0x9800, x=0, y=0, tile_id=1)
        oam = bytearray(OAM_SIZE)
        oam[0:4] = bytes((16, 8, 2, 0x10))
        regs = build_regs(obj_enable=True, bgp=0xE4, obp0=0xE4, obp1=0x1B)
        snapshot = build_snapshot(regs=regs, vram=vram, oam=oam)
        transparent = pixel_shade(2, 0, snapshot)
        opaque = pixel_shade(5, 0, snapshot)
        self.assertEqual(transparent.source, PixelSource.Background)
        self.assertEqual(opaque.source, PixelSource.Object)
        self.assertEqual(opaque.shade, 0)

        oam[3] = 0x80
        masked = pixel_shade(5, 0, build_snapshot(regs=regs, vram=vram, oam=oam))
        self.assertEqual(masked.source, PixelSource.Background)

    def test_object_8x16_xflip_yflip_and_priority(self) -> None:
        vram = bytearray(VRAM_SIZE)
        write_tile(vram, tile_id=2, rows=[[1, 0, 0, 0, 0, 0, 0, 0]] * 8)
        write_tile(vram, tile_id=3, rows=[[0, 0, 0, 0, 0, 0, 0, 2]] * 8)
        oam = bytearray(OAM_SIZE)
        oam[0:4] = bytes((16, 20, 2, 0x60))
        regs = build_regs(obj_enable=True, obj_size_8x16=True, obp0=0xE4)
        top = pixel_shade(12, 0, build_snapshot(regs=regs, vram=vram, oam=oam))
        bottom = pixel_shade(19, 15, build_snapshot(ly=15, regs=regs, vram=vram, oam=oam))
        self.assertEqual(top.source, PixelSource.Object)
        self.assertEqual(top.obj.tile_id, 2)
        self.assertEqual(bottom.source, PixelSource.Object)
        self.assertEqual(bottom.obj.tile_id, 2)

        priority_oam = bytearray(OAM_SIZE)
        priority_oam[0:4] = bytes((16, 20, 2, 0x00))
        priority_oam[4:8] = bytes((16, 18, 3, 0x00))
        write_tile(vram, tile_id=3, rows=[[3] * 8] * 8)
        winner = pixel_shade(12, 0, build_snapshot(regs=build_regs(obj_enable=True), vram=vram, oam=priority_oam))
        self.assertEqual(winner.source, PixelSource.Object)
        self.assertEqual(winner.obj.sprite_index, 1)

    def test_object_selection_respects_ten_per_line_limit_in_oam_order(self) -> None:
        vram = bytearray(VRAM_SIZE)
        write_tile(vram, tile_id=1, rows=[[3] * 8] * 8)
        oam = bytearray(OAM_SIZE)
        for index in range(11):
            base = index * 4
            oam[base : base + 4] = bytes((16, 24, 1, 0x00))
        result = pixel_shade(16, 0, build_snapshot(regs=build_regs(obj_enable=True), vram=vram, oam=oam))
        self.assertEqual(result.source, PixelSource.Object)
        self.assertEqual(result.obj.sprite_index, 0)

    def test_bg_disable_zeroes_bg_and_window_but_objects_still_draw(self) -> None:
        vram = bytearray(VRAM_SIZE)
        write_tile(vram, tile_id=1, rows=[[3] * 8] * 8)
        write_tilemap(vram, base=0x9800, x=0, y=0, tile_id=1)
        oam = bytearray(OAM_SIZE)
        oam[0:4] = bytes((16, 8, 1, 0x00))
        regs = build_regs(bg_enable=False, obj_enable=True)
        bg_only = pixel_shade(20, 0, build_snapshot(regs=regs, vram=vram))
        obj_only = pixel_shade(0, 0, build_snapshot(regs=regs, vram=vram, oam=oam))
        self.assertEqual(bg_only.shade, 0)
        self.assertEqual(obj_only.source, PixelSource.Object)

    def test_diff_frame_reports_actionable_layer_context(self) -> None:
        vram = bytearray(VRAM_SIZE)
        write_tile(vram, tile_id=1, rows=[[1] * 8] * 8)
        write_tilemap(vram, base=0x9800, x=0, y=0, tile_id=1)
        snapshot = build_snapshot(vram=vram)
        actual = [list(render_scanline(snapshot)) for _ in range(144)]
        actual[0][0] = 0x00
        diffs = diff_frame(actual, [snapshot] + [snapshot] * 143, limit=1)
        self.assertEqual(len(diffs), 1)
        self.assertEqual(diffs[0].x, 0)
        self.assertEqual(diffs[0].y, 0)
        self.assertEqual(diffs[0].expected_source, PixelSource.Background)
        self.assertEqual(diffs[0].bg_tile_id, 1)


if __name__ == "__main__":
    unittest.main()
