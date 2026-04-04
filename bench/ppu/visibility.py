from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WriteVisibilityRule:
    register: str
    visibility_point: str
    contract: str


@dataclass(frozen=True)
class ReadbackRule:
    target: str
    readback_kind: str
    contract: str


WRITE_VISIBILITY_RULES: tuple[WriteVisibilityRule, ...] = (
    WriteVisibilityRule("LYC", "immediate", "LYC participates in live LY comparison immediately."),
    WriteVisibilityRule("STAT[6:3]", "immediate", "STAT select bits feed STAT-line evaluation immediately."),
    WriteVisibilityRule("SCX[2:0]", "mode2_sample", "SCX low bits are sampled at scanline start for discard."),
    WriteVisibilityRule("SCX[7:3]", "tile_fetch_live", "SCX high bits are re-read on tile fetch."),
    WriteVisibilityRule("SCY", "tile_fetch_live", "SCY is re-read on tile fetch."),
    WriteVisibilityRule("WX", "live_compare", "WX is checked live against rendered X + 7."),
    WriteVisibilityRule("WY", "mode2_sample", "WY is only armed at mode-2 start."),
    WriteVisibilityRule("BGP", "pixel_pop", "BGP is sampled at background pop / palette application."),
    WriteVisibilityRule("OBP0", "pixel_pop", "OBP0 is sampled at object pop / palette application."),
    WriteVisibilityRule("OBP1", "pixel_pop", "OBP1 is sampled at object pop / palette application."),
    WriteVisibilityRule("LCDC.7", "immediate", "LCDC.7 transitions the run state immediately."),
    WriteVisibilityRule("LCDC.6", "tile_fetch_live", "Window map selection is consumed on window tile fetch."),
    WriteVisibilityRule("LCDC.5", "mode2_sample", "Window enable is captured at mode-2 start."),
    WriteVisibilityRule("LCDC.4", "tile_fetch_live", "BG/window data select is consumed on tile fetch."),
    WriteVisibilityRule("LCDC.3", "tile_fetch_live", "BG map select is consumed on background tile fetch."),
    WriteVisibilityRule("LCDC.2", "object_metadata", "Object size is consumed when object row metadata resolves."),
    WriteVisibilityRule("LCDC.1", "object_pipeline", "Object enable gates object pipeline work when reached."),
    WriteVisibilityRule("LCDC.0", "pixel_mix", "BG enable affects contribution at mix/pop time."),
)

READBACK_RULES: tuple[ReadbackRule, ...] = (
    ReadbackRule("LY", "live_derived", "LY is read-only and reflects timing state directly."),
    ReadbackRule(
        "STAT",
        "mixed_register",
        "Bits 6:3 are stored, bit 2 is live LYC==LY, bits 1:0 come from visible_mode().",
    ),
    ReadbackRule("STAT_LCD_OFF", "derived_override", "LCD-off forces STAT mode bits to 0."),
    ReadbackRule("PPU_REG_BYTES", "stored_byte", "Plain register reads return the stored programmer-visible byte."),
    ReadbackRule("VRAM_CPU_READ", "access_policy", "Mode-3 CPU reads are UndefinedRead by default."),
    ReadbackRule("OAM_CPU_READ", "access_policy", "Modes 2 and 3 block CPU OAM reads by default."),
    ReadbackRule("LCD_OFF_VIDEO", "fully_accessible", "LCD off restores VRAM/OAM accessibility."),
)


def write_visibility_map() -> dict[str, WriteVisibilityRule]:
    return {rule.register: rule for rule in WRITE_VISIBILITY_RULES}


def readback_rule_map() -> dict[str, ReadbackRule]:
    return {rule.target: rule for rule in READBACK_RULES}


def assert_visibility_matrix_is_self_consistent() -> None:
    writes = write_visibility_map()
    reads = readback_rule_map()

    assert writes["SCX[2:0]"].visibility_point == "mode2_sample"
    assert writes["SCX[7:3]"].visibility_point == "tile_fetch_live"
    assert writes["WY"].visibility_point == "mode2_sample"
    assert writes["WX"].visibility_point == "live_compare"
    assert writes["BGP"].visibility_point == "pixel_pop"
    assert writes["LCDC.7"].visibility_point == "immediate"

    assert reads["LY"].readback_kind == "live_derived"
    assert reads["STAT"].readback_kind == "mixed_register"
    assert reads["STAT_LCD_OFF"].readback_kind == "derived_override"
    assert reads["VRAM_CPU_READ"].readback_kind == "access_policy"
    assert reads["LCD_OFF_VIDEO"].readback_kind == "fully_accessible"


__all__ = [
    "READBACK_RULES",
    "WRITE_VISIBILITY_RULES",
    "ReadbackRule",
    "WriteVisibilityRule",
    "assert_visibility_matrix_is_self_consistent",
    "readback_rule_map",
    "write_visibility_map",
]
