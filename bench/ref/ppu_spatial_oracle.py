from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Sequence

from bench.ref.ppu_ref import Lcdc, PpuRegs


SCREEN_WIDTH = 160
SCREEN_HEIGHT = 144
VRAM_BASE = 0x8000
VRAM_SIZE = 0x2000
OAM_SIZE = 0x00A0
DMG_SHADE_VALUES = (0xFF, 0xAA, 0x55, 0x00)


class PixelSource(str, Enum):
    Background = "background"
    Window = "window"
    Object = "object"


@dataclass(frozen=True)
class ScanlineSnapshot:
    ly: int
    regs: PpuRegs
    vram: bytes
    oam: bytes
    wy_triggered: bool
    window_line_counter: int


@dataclass(frozen=True)
class LayerSample:
    source: PixelSource
    color_idx: int
    shade: int
    tile_id: int
    map_x: int
    map_y: int
    tile_x: int
    tile_y: int


@dataclass(frozen=True)
class ObjPixelSample:
    sprite_index: int
    x: int
    y: int
    tile_id: int
    color_idx: int
    shade: int
    palette: int
    bg_over_obj: bool
    x_flip: bool
    y_flip: bool


@dataclass(frozen=True)
class PixelResult:
    x: int
    y: int
    shade: int
    source: PixelSource
    bg: LayerSample
    window: LayerSample | None
    effective_bg: LayerSample
    obj: ObjPixelSample | None


@dataclass(frozen=True)
class PixelDiff:
    x: int
    y: int
    actual_shade: int
    expected_shade: int
    expected_source: PixelSource
    bg_tile_id: int
    window_tile_id: int | None
    obj_sprite_index: int | None
    obj_tile_id: int | None


def palette_lookup(color_idx: int, palette: int) -> int:
    return (palette >> (2 * (color_idx & 0x3))) & 0x3


def dmg_gray(shade: int) -> int:
    return DMG_SHADE_VALUES[shade & 0x3]


def decode_tile_row(lo: int, hi: int) -> tuple[int, ...]:
    return tuple((((hi >> bit) & 1) << 1) | ((lo >> bit) & 1) for bit in range(7, -1, -1))


def bgwin_tile_addr(lcdc: Lcdc, tile_id: int, row: int) -> int:
    row_offset = (row & 0x7) * 2
    if lcdc.bgwin_data_hi:
        return 0x8000 + ((tile_id & 0xFF) * 16) + row_offset
    if tile_id & 0x80:
        return 0x8800 + (((tile_id & 0xFF) - 0x80) * 16) + row_offset
    return 0x9000 + ((tile_id & 0xFF) * 16) + row_offset


def obj_tile_addr(*, obj_size_8x16: bool, tile_id: int, row: int, y_flip: bool) -> int:
    height = 16 if obj_size_8x16 else 8
    effective_row = (height - 1 - row) if y_flip else row
    row_in_tile = effective_row & 0x7
    base_tile = (tile_id & 0xFE) if obj_size_8x16 else (tile_id & 0xFF)
    tile_index = base_tile + (1 if obj_size_8x16 and effective_row >= 8 else 0)
    return 0x8000 + (tile_index * 16) + (row_in_tile * 2)


def _require_snapshot_shapes(snapshot: ScanlineSnapshot) -> None:
    if len(snapshot.vram) != VRAM_SIZE:
        raise ValueError(f"vram snapshot must be {VRAM_SIZE} bytes, got {len(snapshot.vram)}")
    if len(snapshot.oam) != OAM_SIZE:
        raise ValueError(f"oam snapshot must be {OAM_SIZE} bytes, got {len(snapshot.oam)}")


def _vram_read(snapshot: ScanlineSnapshot, addr: int) -> int:
    if not (VRAM_BASE <= addr < VRAM_BASE + VRAM_SIZE):
        raise ValueError(f"VRAM address out of range: 0x{addr:04X}")
    return snapshot.vram[addr - VRAM_BASE]


def _tile_row_from_addr(snapshot: ScanlineSnapshot, addr: int) -> tuple[int, ...]:
    lo = _vram_read(snapshot, addr)
    hi = _vram_read(snapshot, addr + 1)
    return decode_tile_row(lo, hi)


def _map_base(high: bool) -> int:
    return 0x9C00 if high else 0x9800


def bg_sample(x: int, snapshot: ScanlineSnapshot) -> LayerSample:
    global_x = (snapshot.regs.scx + x) & 0xFF
    global_y = (snapshot.regs.scy + snapshot.ly) & 0xFF
    map_x = (global_x >> 3) & 0x1F
    map_y = (global_y >> 3) & 0x1F
    tile_x = global_x & 0x7
    tile_y = global_y & 0x7
    tilemap_addr = _map_base(snapshot.regs.lcdc.bg_map_hi) + (map_y * 32) + map_x
    tile_id = _vram_read(snapshot, tilemap_addr)
    row = _tile_row_from_addr(snapshot, bgwin_tile_addr(snapshot.regs.lcdc, tile_id, tile_y))
    color_idx = row[tile_x]
    return LayerSample(
        source=PixelSource.Background,
        color_idx=color_idx,
        shade=palette_lookup(color_idx, snapshot.regs.bgp),
        tile_id=tile_id,
        map_x=map_x,
        map_y=map_y,
        tile_x=tile_x,
        tile_y=tile_y,
    )


def window_sample(x: int, snapshot: ScanlineSnapshot) -> LayerSample | None:
    if not snapshot.regs.lcdc.win_enable:
        return None
    if not snapshot.wy_triggered:
        return None
    win_origin_x = snapshot.regs.wx - 7
    if x < win_origin_x:
        return None
    win_x = x - win_origin_x
    if win_x < 0:
        return None
    win_y = snapshot.window_line_counter
    map_x = (win_x >> 3) & 0x1F
    map_y = (win_y >> 3) & 0x1F
    tile_x = win_x & 0x7
    tile_y = win_y & 0x7
    tilemap_addr = _map_base(snapshot.regs.lcdc.win_map_hi) + (map_y * 32) + map_x
    tile_id = _vram_read(snapshot, tilemap_addr)
    row = _tile_row_from_addr(snapshot, bgwin_tile_addr(snapshot.regs.lcdc, tile_id, tile_y))
    color_idx = row[tile_x]
    return LayerSample(
        source=PixelSource.Window,
        color_idx=color_idx,
        shade=palette_lookup(color_idx, snapshot.regs.bgp),
        tile_id=tile_id,
        map_x=map_x,
        map_y=map_y,
        tile_x=tile_x,
        tile_y=tile_y,
    )


def _selected_line_sprites(snapshot: ScanlineSnapshot) -> list[tuple[int, int, int, int, int]]:
    selected: list[tuple[int, int, int, int, int]] = []
    sprite_height = 16 if snapshot.regs.lcdc.obj_size_8x16 else 8
    scanline = snapshot.ly + 16
    for sprite_index in range(40):
        base = sprite_index * 4
        y_pos = snapshot.oam[base]
        x_pos = snapshot.oam[base + 1]
        if scanline >= y_pos and scanline < y_pos + sprite_height:
            selected.append((sprite_index, y_pos, x_pos, snapshot.oam[base + 2], snapshot.oam[base + 3]))
            if len(selected) == 10:
                break
    return selected


def obj_sample(x: int, snapshot: ScanlineSnapshot) -> ObjPixelSample | None:
    if not snapshot.regs.lcdc.obj_enable:
        return None
    sprite_height = 16 if snapshot.regs.lcdc.obj_size_8x16 else 8
    winner: ObjPixelSample | None = None
    winner_x = 0
    winner_index = 0
    for sprite_index, y_pos, x_pos, tile_id, flags in _selected_line_sprites(snapshot):
        sprite_x = x_pos - 8
        sprite_y = y_pos - 16
        if not (sprite_x <= x < sprite_x + 8):
            continue
        row = snapshot.ly - sprite_y
        if not (0 <= row < sprite_height):
            continue
        x_flip = bool(flags & 0x20)
        y_flip = bool(flags & 0x40)
        tile_addr = obj_tile_addr(
            obj_size_8x16=snapshot.regs.lcdc.obj_size_8x16,
            tile_id=tile_id,
            row=row,
            y_flip=y_flip,
        )
        row_pixels = _tile_row_from_addr(snapshot, tile_addr)
        col = x - sprite_x
        color_idx = row_pixels[7 - col] if x_flip else row_pixels[col]
        if color_idx == 0:
            continue
        palette = snapshot.regs.obp1 if (flags & 0x10) else snapshot.regs.obp0
        sample = ObjPixelSample(
            sprite_index=sprite_index,
            x=sprite_x,
            y=sprite_y,
            tile_id=(tile_id & 0xFE) if snapshot.regs.lcdc.obj_size_8x16 else tile_id,
            color_idx=color_idx,
            shade=palette_lookup(color_idx, palette),
            palette=palette,
            bg_over_obj=bool(flags & 0x80),
            x_flip=x_flip,
            y_flip=y_flip,
        )
        if winner is None or x_pos < winner_x or (x_pos == winner_x and sprite_index < winner_index):
            winner = sample
            winner_x = x_pos
            winner_index = sprite_index
    return winner


def pixel_shade(x: int, ly: int, snapshot: ScanlineSnapshot) -> PixelResult:
    if ly != snapshot.ly:
        raise ValueError(f"snapshot.ly={snapshot.ly} does not match requested ly={ly}")
    _require_snapshot_shapes(snapshot)
    bg = bg_sample(x, snapshot)
    window = window_sample(x, snapshot)
    effective_bg = window if window is not None else bg
    obj = obj_sample(x, snapshot)
    bg_enabled = snapshot.regs.lcdc.bg_enable
    bg_blocks_obj = bg_enabled and effective_bg.color_idx != 0 and obj is not None and obj.bg_over_obj

    if obj is not None and not bg_blocks_obj:
        return PixelResult(
            x=x,
            y=ly,
            shade=obj.shade,
            source=PixelSource.Object,
            bg=bg,
            window=window,
            effective_bg=effective_bg,
            obj=obj,
        )

    shade = effective_bg.shade if bg_enabled else 0
    return PixelResult(
        x=x,
        y=ly,
        shade=shade,
        source=effective_bg.source,
        bg=bg,
        window=window,
        effective_bg=effective_bg,
        obj=obj,
    )


def render_scanline(snapshot: ScanlineSnapshot) -> tuple[int, ...]:
    return tuple(dmg_gray(pixel_shade(x, snapshot.ly, snapshot).shade) for x in range(SCREEN_WIDTH))


def render_frame(scanlines: Sequence[ScanlineSnapshot]) -> tuple[tuple[int, ...], ...]:
    if len(scanlines) != SCREEN_HEIGHT:
        raise ValueError(f"expected {SCREEN_HEIGHT} scanline snapshots, got {len(scanlines)}")
    return tuple(render_scanline(snapshot) for snapshot in scanlines)


def diff_frame(
    actual_rows: Sequence[Sequence[int]],
    scanlines: Sequence[ScanlineSnapshot],
    *,
    limit: int = 8,
) -> list[PixelDiff]:
    expected_rows = render_frame(scanlines)
    if len(actual_rows) != len(expected_rows):
        raise ValueError(f"expected {len(expected_rows)} actual rows, got {len(actual_rows)}")
    diffs: list[PixelDiff] = []
    for y, (actual_row, expected_row, snapshot) in enumerate(zip(actual_rows, expected_rows, scanlines)):
        if len(actual_row) != len(expected_row):
            raise ValueError(f"row {y} width mismatch: expected {len(expected_row)} got {len(actual_row)}")
        for x, (actual, expected) in enumerate(zip(actual_row, expected_row)):
            if actual == expected:
                continue
            result = pixel_shade(x, y, snapshot)
            diffs.append(
                PixelDiff(
                    x=x,
                    y=y,
                    actual_shade=actual,
                    expected_shade=expected,
                    expected_source=result.source,
                    bg_tile_id=result.bg.tile_id,
                    window_tile_id=None if result.window is None else result.window.tile_id,
                    obj_sprite_index=None if result.obj is None else result.obj.sprite_index,
                    obj_tile_id=None if result.obj is None else result.obj.tile_id,
                )
            )
            if len(diffs) >= limit:
                return diffs
    return diffs


def rows_from_flat_shades(flat: bytes, *, width: int = SCREEN_WIDTH, height: int = SCREEN_HEIGHT) -> tuple[tuple[int, ...], ...]:
    expected_len = width * height
    if len(flat) != expected_len:
        raise ValueError(f"expected {expected_len} bytes, got {len(flat)}")
    return tuple(
        tuple(flat[row_start : row_start + width])
        for row_start in range(0, expected_len, width)
    )


def build_scanlines(
    *,
    regs_by_line: Sequence[PpuRegs],
    vram: bytes,
    oam: bytes,
    wy_triggered_by_line: Sequence[bool],
    window_line_counters: Sequence[int],
) -> tuple[ScanlineSnapshot, ...]:
    if not (
        len(regs_by_line) == len(wy_triggered_by_line) == len(window_line_counters) == SCREEN_HEIGHT
    ):
        raise ValueError("build_scanlines expects 144 entries for regs, wy_triggered, and window counters")
    return tuple(
        ScanlineSnapshot(
            ly=ly,
            regs=regs_by_line[ly],
            vram=vram,
            oam=oam,
            wy_triggered=wy_triggered_by_line[ly],
            window_line_counter=window_line_counters[ly],
        )
        for ly in range(SCREEN_HEIGHT)
    )


def flatten_rows(rows: Iterable[Sequence[int]]) -> bytes:
    flat = bytearray()
    for row in rows:
        flat.extend(pixel & 0xFF for pixel in row)
    return bytes(flat)
